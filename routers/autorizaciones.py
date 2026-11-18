from datetime import date, datetime
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from database import get_connection
from utils.contexto_auditoria import establecer_contexto_auditoria

router = APIRouter(
    prefix="/autorizaciones",
    tags=["Autorizaciones"]
)


class AutorizacionCreate(BaseModel):
    PersonaId: int
    NombreUsuarioAutoriza: str = Field(..., max_length=200, description="Nombres y apellidos de quien autoriza")
    SeInformoAdultoMayor: Literal["Sí", "No"]
    ManifestoAutorizacion: Literal["Sí", "No", "No consta"]
    ExisteSoporteDocumental: Literal["Sí", "No"]
    FechaAutorizacion: date = Field(..., description="Fecha física en el documento (formato YYYY-MM-DD)")
    UbicacionDocumentoFisico: str = Field(..., max_length=300, description="Ubicación física en archivo/carpeta")
    SupervisorVerifico: str = Field(..., max_length=100, description="Usuario institucional del supervisor")
    # Opcional: si el frontend no la envía, SQL Server o la BD asigna la fecha y hora actual automáticamente
    FechaHoraVerificacion: Optional[datetime] = None

class DocumentoUpdate(BaseModel):
    UbicacionDocumentoFisico: str


@router.patch("/persona/{persona_id}/documento")
def actualizar_documento_autorizacion(persona_id: int, req: DocumentoUpdate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE AUTORIZACION_FICHAMEDICA SET UbicacionDocumentoFisico = ? WHERE PersonaId = ?",
            (req.UbicacionDocumentoFisico.strip(), persona_id)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="No se encontró autorización para esta persona.")
        conn.commit()
        return {"mensaje": "Documento PDF actualizado correctamente en la base de datos"}
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


@router.get("/autorizacion")
def listar_autorizaciones():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                Id,
                PersonaId,
                NombreUsuarioAutoriza,
                SeInformoAdultoMayor,
                ManifestoAutorizacion,
                ExisteSoporteDocumental,
                FechaAutorizacion,
                UbicacionDocumentoFisico,
                SupervisorVerifico,
                FechaHoraVerificacion
            FROM AUTORIZACION_FICHAMEDICA
        """)
        columnas = [col[0] for col in cursor.description]
        registros = []
        for fila in cursor.fetchall():
            item = dict(zip(columnas, fila))
            if item.get("FechaAutorizacion"):
                item["FechaAutorizacion"] = str(item["FechaAutorizacion"])
            if item.get("FechaHoraVerificacion"):
                item["FechaHoraVerificacion"] = str(item["FechaHoraVerificacion"])
            registros.append(item)
            
        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=201)
def crear_autorizacion(autorizacion: AutorizacionCreate, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        fecha_hora_verif = autorizacion.FechaHoraVerificacion or datetime.now()

        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (autorizacion.SupervisorVerifico.strip(),))
        usr = cursor.fetchone()
        usuario_id = usr[0] if usr else None

        establecer_contexto_auditoria(cursor, request, usuario_id=usuario_id)

        query = """
            INSERT INTO AUTORIZACION_FICHAMEDICA (
                PersonaId,
                NombreUsuarioAutoriza,
                SeInformoAdultoMayor,
                ManifestoAutorizacion,
                ExisteSoporteDocumental,
                FechaAutorizacion,
                UbicacionDocumentoFisico,
                SupervisorVerifico,
                FechaHoraVerificacion
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            autorizacion.PersonaId,
            autorizacion.NombreUsuarioAutoriza.strip(),
            autorizacion.SeInformoAdultoMayor,
            autorizacion.ManifestoAutorizacion,
            autorizacion.ExisteSoporteDocumental,
            autorizacion.FechaAutorizacion,
            autorizacion.UbicacionDocumentoFisico.strip(),
            autorizacion.SupervisorVerifico.strip(),
            fecha_hora_verif
        ))
        
        # Recuperar el ID de forma segura compatible con triggers activos
        cursor.execute("SELECT @@IDENTITY")
        fila_id = cursor.fetchone()
        nuevo_id = int(fila_id[0]) if fila_id and fila_id[0] is not None else 0

        conn.commit()

        return {
            "mensaje": "Autorización médica registrada con éxito",
            "id_autorizacion": nuevo_id
        }
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()