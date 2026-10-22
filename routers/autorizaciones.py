from datetime import date, datetime
from typing import Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from database import get_connection

router = APIRouter(
    prefix="/autorizaciones",
    tags=["Autorizaciones"]
)

# 1. Modelo Pydantic para validar los datos que ingresa el usuario
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


# 2. GET /autorizaciones/autorizacion (Listar autorizaciones)
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
            # Convertir fechas a string para evitar errores de serialización JSON
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


# 3. POST /autorizaciones (Crear nueva autorización médica)
@router.post("", status_code=201)
def crear_autorizacion(autorizacion: AutorizacionCreate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Si no viene FechaHoraVerificacion desde el frontend, se toma el momento actual
        fecha_hora_verif = autorizacion.FechaHoraVerificacion or datetime.now()

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
            OUTPUT INSERTED.Id
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
        
        nuevo_id = cursor.fetchone()[0]
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