from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_connection
from utils.huella_digital import generar_huella_servidor

router = APIRouter(
    prefix="/trazabilidad",
    tags=["Trazabilidad y Auditoría"]
)

# MODELO PYDANTIC

class AuditoriaCreate(BaseModel):
    UsuarioId: Optional[int] = None
    AccionRealizada: str
    TablaAfectada: str
    DireccionIP: Optional[str] = None
    Dispositivo: Optional[str] = None
    UbicacionGeo: Optional[str] = None


# ENDPOINT: REGISTRAR EVENTO DE AUDITORÍA (POST)
# ==========================================
# 1. REGISTRAR EVENTO MANUAL (POST)
# ==========================================
@router.post("", status_code=201)
def registrar_evento(evento: AuditoriaCreate, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Obtener la IP real del cliente
        ip_cliente = evento.DireccionIP or (request.client.host if request.client else "127.0.0.1")

        # 2. Generar huella digital del servidor actual
        info_huella = generar_huella_servidor()
        huella = info_huella.get("huella_servidor", "LOCAL-DEV")
        sistema = info_huella.get("sistema", "SO")

        # 3. Combinar dispositivo con la firma de hardware de la máquina
        cliente_navegador = evento.Dispositivo or request.headers.get("user-agent", "Web")
        dispositivo_completo = f"Servidor: {huella} ({sistema}) | Cliente: {cliente_navegador}"

        # 4. Inserción con truncado de seguridad según el esquema SQL Server
        query = """
            INSERT INTO TRAZABILIDAD_AUDITORIA (
                UsuarioId,
                AccionRealizada,
                TablaAfectada,
                DireccionIP,
                Dispositivo,
                UbicacionGeo
            )
            OUTPUT INSERTED.Id, INSERTED.FechaHoraServer
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            evento.UsuarioId,
            evento.AccionRealizada[:50],        # varchar(50)
            evento.TablaAfectada[:100],         # varchar(100)
            ip_cliente[:50],                    # varchar(50)
            dispositivo_completo[:255],         # varchar(255)
            (evento.UbicacionGeo[:150] if evento.UbicacionGeo else None) # varchar(150)
        ))
        res = cursor.fetchone()
        conn.commit()

        return {
            "mensaje": "Evento de auditoría registrado exitosamente",
            "id": res[0],
            "fecha": str(res[1]),
            "huella_servidor": huella
        }
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


# ==========================================
# 2. CONSULTAR REGISTROS DE TRAZABILIDAD (GET)
# ==========================================
@router.get("")
def consultar_auditoria(limite: int = 100):
    """Retorna los últimos eventos auditados cruzando con el nombre del usuario."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = f"""
            SELECT TOP ({limite})
                A.Id,
                A.UsuarioId,
                ISNULL(U.NombreCompleto, U.Usuario) AS NombreUsuario,
                A.AccionRealizada,
                A.TablaAfectada,
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

        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()