from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_connection

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
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]



# ENDPOINTPARA CONSULTAS DEPENDIENDO SI DEL ROL MUESTRA LA INFORMACION

@router.post("/panel")
def consultar_panel_por_sesion(req: SesionUsuarioRequest):
    # 1. Validar que el estado sea exactamente ACTIVO
    if req.estado.strip().upper() != "ACTIVO":
        raise HTTPException(
            status_code=403, 
            detail="Acceso denegado: El usuario no se encuentra activo."
        )

    # 2. Si es su primer ingreso y no ha completado datos, no muestra tablas
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

        # 3. Condicionales IF / ELIF / ELSE para filtrar la información por rol
        if rol_limpio in ["ADMIN", "ADMINISTRADOR"]:
            # El ADMIN ve absolutamente todas las tablas
            respuesta["tablas"]["TRAZABILIDAD_AUDITORIA"] = obtener_datos_tabla(cursor, "TRAZABILIDAD_AUDITORIA")
            respuesta["tablas"]["PERSONAS"] = obtener_datos_tabla(cursor, "PERSONAS")
            respuesta["tablas"]["AUTORIZACION_FICHAMEDICA"] = obtener_datos_tabla(cursor, "AUTORIZACION_FICHAMEDICA")
            respuesta["tablas"]["INDICADORES_IA"] = obtener_datos_tabla(cursor, "INDICADORES_IA")
            respuesta["tablas"]["VALORACIONES_INSTITUCIONALES"] = obtener_datos_tabla(cursor, "VALORACIONES_INSTITUCIONALES")

        elif rol_limpio == "SUPERVISOR":
            # El SUPERVISOR ve todo MENOS la tabla de TRAZABILIDAD_AUDITORIA
            respuesta["tablas"]["PERSONAS"] = obtener_datos_tabla(cursor, "PERSONAS")
            respuesta["tablas"]["AUTORIZACION_FICHAMEDICA"] = obtener_datos_tabla(cursor, "AUTORIZACION_FICHAMEDICA")
            respuesta["tablas"]["INDICADORES_IA"] = obtener_datos_tabla(cursor, "INDICADORES_IA")
            respuesta["tablas"]["VALORACIONES_INSTITUCIONALES"] = obtener_datos_tabla(cursor, "VALORACIONES_INSTITUCIONALES")

        elif rol_limpio == "CONTRATISTA":
            # El CONTRATISTA solo ve PERSONAS, INDICADORES_IA y VALORACIONES_INSTITUCIONALES
            respuesta["tablas"]["PERSONAS"] = obtener_datos_tabla(cursor, "PERSONAS")
            respuesta["tablas"]["INDICADORES_IA"] = obtener_datos_tabla(cursor, "INDICADORES_IA")
            respuesta["tablas"]["VALORACIONES_INSTITUCIONALES"] = obtener_datos_tabla(cursor, "VALORACIONES_INSTITUCIONALES")

        else:
            # Cualquier otra palabra o rol no autorizado se rechaza
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