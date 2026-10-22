from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_connection

router = APIRouter(
    prefix="/personas",
    tags=["Personas"]
)

# Modelo Pydantic de la tabla PERSONAS
class PersonaCreate(BaseModel):
    Foto: Optional[str] = None
    Nombres: str
    Apellidos: str
    CondicionDiscapacidad: Optional[str] = None
    PerteneceGrupoEtnico: Optional[str] = None
    Religion: Optional[str] = None
    VictimaConflicto: Optional[str] = None
    TipoDocumento: Optional[str] = None
    NumeroDocumento: str
    FechaNacimiento: Optional[str] = None  # Formato YYYY-MM-DD
    Sexo: Optional[str] = None
    Peso: Optional[float] = None
    Altura: Optional[float] = None
    Eps: Optional[str] = None
    Direccion: Optional[str] = None
    Telefono: Optional[str] = None
    Estudio: Optional[str] = None
    ConQuienVive: Optional[str] = None
    DiagnosticoPrincipal: Optional[str] = None
    CirugiasRealizadas: Optional[str] = None
    MedicamentosConsume: Optional[str] = None
    HijosYCuantosResponden: Optional[str] = None
    NombreEmergencia: Optional[str] = None
    NumeroEmergencia: Optional[str] = None
    ObservacionGeneral: Optional[str] = None
    Estado: Optional[str] = "ACTIVO"
    GrupoSanguineo: Optional[str] = None  # <--- NUEVA COLUMNA (ej: O+, A+, B-)

# GET /personas (Listar)
@router.get("/personas")
def listar_personas():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM PERSONAS")
        columnas = [col[0] for col in cursor.description]
        registros = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# POST /personas (Crear)
@router.post("", status_code=201)
def crear_persona(persona: PersonaCreate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            INSERT INTO PERSONAS (
                Foto, Nombres, Apellidos, CondicionDiscapacidad,
                PerteneceGrupoEtnico, Religion, VictimaConflicto,
                TipoDocumento, NumeroDocumento, FechaNacimiento,
                Sexo, Peso, Altura, Eps, Direccion, Telefono,
                Estudio, ConQuienVive, DiagnosticoPrincipal,
                CirugiasRealizadas, MedicamentosConsume,
                HijosYCuantosResponden, NombreEmergencia,
                NumeroEmergencia, ObservacionGeneral, Estado,
                GrupoSanguineo
            )
            OUTPUT INSERTED.Id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        valores = (
            persona.Foto, persona.Nombres, persona.Apellidos, persona.CondicionDiscapacidad,
            persona.PerteneceGrupoEtnico, persona.Religion, persona.VictimaConflicto,
            persona.TipoDocumento, persona.NumeroDocumento, persona.FechaNacimiento,
            persona.Sexo, persona.Peso, persona.Altura, persona.Eps, persona.Direccion, persona.Telefono,
            persona.Estudio, persona.ConQuienVive, persona.DiagnosticoPrincipal,
            persona.CirugiasRealizadas, persona.MedicamentosConsume,
            persona.HijosYCuantosResponden, persona.NombreEmergencia,
            persona.NumeroEmergencia, persona.ObservacionGeneral, persona.Estado,
            persona.GrupoSanguineo  # <--- SE ENVÍA AQUÍ
        )
        cursor.execute(query, valores)
        nuevo_id = cursor.fetchone()[0]
        conn.commit()
        return {"mensaje": "Persona creada exitosamente", "id_persona": nuevo_id}
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()