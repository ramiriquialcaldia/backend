from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_connection

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

@router.post("/REGISTRAR-TRAZABILIDAD", status_code=201)
def registrar_auditoria(evento: AuditoriaCreate, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Si no se envía la IP o el Dispositivo de forma manual,
        # FastAPI los extrae automáticamente de la cabecera del cliente
        ip_cliente = evento.DireccionIP or (request.client.host if request.client else None)
        dispositivo_cliente = evento.Dispositivo or request.headers.get("user-agent")

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
        valores = (
            evento.UsuarioId,
            evento.AccionRealizada,
            evento.TablaAfectada,
            ip_cliente,
            dispositivo_cliente,
            evento.UbicacionGeo
        )

        cursor.execute(query, valores)
        resultado = cursor.fetchone()
        nuevo_id = resultado[0]
        fecha_servidor = resultado[1]

        conn.commit()

        return {
            "mensaje": "Evento de trazabilidad registrado con éxito",
            "id_auditoria": nuevo_id,
            "fecha_servidor": str(fecha_servidor)
        }
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# ENDPOINT: CONSULTAR AUDITORÍA (GET - Para Rol 1 Super Admin)

@router.get("/CONSULTAR-TRAZABILIDAD")
def consultar_auditoria(limite: int = 100):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = f"""
            SELECT TOP ({limite})
                A.Id,
                A.UsuarioId,
                U.NombreCompleto AS NombreUsuario,
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
        registros = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()