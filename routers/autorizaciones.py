from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database import get_connection

router = APIRouter(
    prefix="/autorizaciones",
    tags=["Autorizaciones"]
)

# Modelo Pydantic de la tabla AUTORIZACION_FICHAMEDICA
class AutorizacionCreate(BaseModel):
    PersonaId: int
    NombreUsuarioAutoriza: str
    TextoAutorizacion: str
    FotoFirmaUrl: str

# GET /autorizaciones
@router.get("/autorizacion")
def listar_autorizaciones():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM AUTORIZACION_FICHAMEDICA")
        columnas = [col[0] for col in cursor.description]
        registros = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# POST /autorizaciones
@router.post("", status_code=201)
def crear_autorizacion(autorizacion: AutorizacionCreate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO AUTORIZACION_FICHAMEDICA (PersonaId, NombreUsuarioAutoriza, TextoAutorizacion, FotoFirmaUrl)
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (
            autorizacion.PersonaId,
            autorizacion.NombreUsuarioAutoriza,
            autorizacion.TextoAutorizacion,
            autorizacion.FotoFirmaUrl
        ))
        conn.commit()
        return {"mensaje": "Autorización médica registrada con éxito"}
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()