from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_connection
from utils.contexto_auditoria import establecer_contexto_auditoria

router = APIRouter(
    prefix="/personas",
    tags=["Personas"]
)


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
    FechaNacimiento: Optional[str] = None
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
    GrupoSanguineo: Optional[str] = None


class EstadoPersonaUpdate(BaseModel):
    Estado: str
    RolUsuario: Optional[str] = "CONTRATISTA"


@router.get("")
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



@router.post("", status_code=201)
def crear_persona(persona: PersonaCreate, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        establecer_contexto_auditoria(cursor, request)

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
            persona.GrupoSanguineo
        )
        cursor.execute(query, valores)
        
        # Recuperar el ID de forma segura compatible con triggers activos
        cursor.execute("SELECT @@IDENTITY")
        fila_id = cursor.fetchone()
        nuevo_id = int(fila_id[0]) if fila_id and fila_id[0] is not None else 0

        conn.commit()
        return {"mensaje": "Persona creada exitosamente", "id_persona": nuevo_id}
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

@router.patch("/{persona_id}/estado")
def cambiar_estado_persona(persona_id: int, req: EstadoPersonaUpdate, request: Request):
    rol = (req.RolUsuario or "").strip().upper()
    if rol not in ["ADMIN", "ADMINISTRADOR", "SUPERVISOR"]:
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado: El rol Contratista no tiene permisos para modificar el estado de una persona."
        )

    conn = get_connection()
    cursor = conn.cursor()
    try:
        nuevo_estado = req.Estado.strip().upper()

        cursor.execute("SELECT Id, Nombres, Apellidos FROM PERSONAS WHERE Id = ?", (persona_id,))
        persona = cursor.fetchone()
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró ninguna persona con el Id = {persona_id}"
            )

        cursor.execute("SELECT TOP 1 Id FROM USUARIOS WHERE Usuario = ? OR PermisosRol = ?", (req.RolUsuario.strip(), rol))
        usr = cursor.fetchone()
        usuario_id = usr[0] if usr else None

        establecer_contexto_auditoria(cursor, request, usuario_id=usuario_id)

        query = "UPDATE PERSONAS SET Estado = ? WHERE Id = ?"
        cursor.execute(query, (nuevo_estado, persona_id))

        conn.commit()

        return {
            "mensaje": f"Estado de {persona[1]} {persona[2]} actualizado a {nuevo_estado}",
            "id_persona": persona_id,
            "nuevo_estado": nuevo_estado
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()