from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_connection
# from utils.auditoria import registrar_evento_auditoria

router = APIRouter(
    prefix="/consultas",
    tags=["Consultas"]
)

# 1. Modelo Pydantic que mapea exactamente el JSON recibido
class SesionUsuarioRequest(BaseModel):
    mensaje: Optional[str] = None
    id_usuario: int
    usuario: str
    rol: str
    estado: str
    primer_ingreso: Optional[bool] = False


def obtener_datos_tabla(cursor, nombre_tabla: str):
    """Función auxiliar para leer todos los registros de una tabla."""
    query = f"SELECT * FROM {nombre_tabla}"
    cursor.execute(query)
    columnas = [col[0] for col in cursor.description]
    registros = []
    for fila in cursor.fetchall():
        item = dict(zip(columnas, fila))
        for k, v in item.items():
            if hasattr(v, 'isoformat'):
                item[k] = v.isoformat()
        registros.append(item)
    return registros


def obtener_auditoria_con_usuarios(cursor):
    """
    Cruza TRAZABILIDAD_AUDITORIA con USUARIOS por el UsuarioId (Id)
    para devolver el nombre de usuario exacto en lugar del ID numérico.
    """
    query = """
        SELECT 
            A.Id,
            A.AccionRealizada,
            A.TablaAfectada,
            ISNULL(U.Usuario, 'Sistema') AS Usuario,
            A.FechaHoraServer,
            A.DireccionIP,
            A.Dispositivo,
            A.UbicacionGeo
        FROM TRAZABILIDAD_AUDITORIA A
        LEFT JOIN USUARIOS U ON A.UsuarioId = U.Id
        ORDER BY A.FechaHoraServer DESC
    """
    cursor.execute(query)
    columnas = [col[0] for col in cursor.description]
    registros = []
    for fila in cursor.fetchall():
        item = dict(zip(columnas, fila))
        if item.get("FechaHoraServer"):
            item["FechaHoraServer"] = str(item["FechaHoraServer"])
        registros.append(item)
    return registros


def obtener_valoraciones_con_profesion(cursor):
    """
    Cruza VALORACIONES_INSTITUCIONALES con USUARIOS por el NombreProfesional (Usuario)
    para incluir la columna Profesion sin modificar tablas.
    """
    query = """
        SELECT 
            v.Id,
            v.PersonaId,
            v.NombreProfesional,
            ISNULL(u.Profesion, 'No especificada') AS Profesion,
            v.ValoracionDetalle,
            v.FechaValoracion
        FROM dbo.VALORACIONES_INSTITUCIONALES v
        LEFT JOIN dbo.USUARIOS u 
            ON RTRIM(LTRIM(v.NombreProfesional)) = RTRIM(LTRIM(u.Usuario))
        ORDER BY v.FechaValoracion DESC
    """
    cursor.execute(query)
    columnas = [col[0] for col in cursor.description]
    registros = []
    for fila in cursor.fetchall():
        item = dict(zip(columnas, fila))
        if item.get("FechaValoracion"):
            item["FechaValoracion"] = str(item["FechaValoracion"])
        registros.append(item)
    return registros


# ENDPOINT PARA CONSULTAS DEPENDIENDO DEL ROL
@router.post("/panel")
def consultar_panel_por_sesion(req: SesionUsuarioRequest, request: Request):
    ip_cliente = request.client.host if request.client else "127.0.0.1"

    # 1. Validar que el usuario esté activo
    if req.estado.strip().upper() != "ACTIVO":
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # registrar_evento_auditoria(
            #     cursor=cursor,
            #     usuario_id=req.id_usuario,
            #     accion="ACCESO_DENEGADO_USUARIO_INACTIVO",
            #     tabla_afectada="USUARIOS",
            #     ip_cliente=ip_cliente,
            #     detalle_extra=f"Usuario: {req.usuario} intentó consultar panel estando inactivo"
            # )
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        raise HTTPException(
            status_code=403, 
            detail="Acceso denegado: El usuario no se encuentra activo."
        )

    # 2. Validar que no sea primer ingreso sin completar datos
    if req.primer_ingreso:
        raise HTTPException(
            status_code=400, 
            detail="Debe completar su registro antes de consultar información."
        )

    conn = get_connection()
    cursor = conn.cursor()
    try:
        rol_limpio = req.rol.strip().upper()

        respuesta = {
            "usuario_consultor": req.usuario,
            "id_usuario": req.id_usuario,
            "rol": rol_limpio,
            "estado": req.estado,
            "tablas": {}
        }

        # 3. Filtrado estricto de tablas según el rol
        if rol_limpio in ["ADMIN", "ADMINISTRADOR"]:
            # El Administrador ve todas las tablas con auditoría cruzada con nombres de usuario
            respuesta["tablas"]["TRAZABILIDAD_AUDITORIA"] = obtener_auditoria_con_usuarios(cursor)
            respuesta["tablas"]["PERSONAS"] = obtener_datos_tabla(cursor, "PERSONAS")
            respuesta["tablas"]["AUTORIZACION_FICHAMEDICA"] = obtener_datos_tabla(cursor, "AUTORIZACION_FICHAMEDICA")
            respuesta["tablas"]["INDICADORES_IA"] = obtener_datos_tabla(cursor, "INDICADORES_IA")
            respuesta["tablas"]["VALORACIONES_INSTITUCIONALES"] = obtener_valoraciones_con_profesion(cursor)

        elif rol_limpio in ["SUPERVISOR", "CONTROL"]:
            # Supervisor ve todas las tablas excepto TRAZABILIDAD_AUDITORIA
            respuesta["tablas"]["PERSONAS"] = obtener_datos_tabla(cursor, "PERSONAS")
            respuesta["tablas"]["AUTORIZACION_FICHAMEDICA"] = obtener_datos_tabla(cursor, "AUTORIZACION_FICHAMEDICA")
            respuesta["tablas"]["INDICADORES_IA"] = obtener_datos_tabla(cursor, "INDICADORES_IA")
            respuesta["tablas"]["VALORACIONES_INSTITUCIONALES"] = obtener_valoraciones_con_profesion(cursor)

        elif rol_limpio == "CONTRATISTA":
            # Contratista ve PERSONAS, INDICADORES_IA y VALORACIONES
            respuesta["tablas"]["PERSONAS"] = obtener_datos_tabla(cursor, "PERSONAS")
            respuesta["tablas"]["INDICADORES_IA"] = obtener_datos_tabla(cursor, "INDICADORES_IA")
            respuesta["tablas"]["VALORACIONES_INSTITUCIONALES"] = obtener_valoraciones_con_profesion(cursor)

        else:
            # Rol no reconocido: auditar intento no autorizado
            # registrar_evento_auditoria(
            #     cursor=cursor,
            #     usuario_id=req.id_usuario,
            #     accion="ACCESO_DENEGADO_ROL_NO_PERMITIDO",
            #     tabla_afectada="USUARIOS",
            #     ip_cliente=ip_cliente,
            #     detalle_extra=f"Intento de acceso con rol desconocido: {req.rol}"
            # )
            conn.commit()

            raise HTTPException(
                status_code=403, 
                detail=f"El rol '{req.rol}' no tiene permisos configurados en el sistema."
            )

        return respuesta

    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Error en la consulta: {str(err)}")
    finally:
        cursor.close()
        conn.close()