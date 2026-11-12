from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_connection
from utils.huella_digital import generar_huella_servidor
from utils.auditoria import registrar_evento_auditoria

router = APIRouter(
    prefix="/personas",
    tags=["Personas"]
)

# ==========================================
# MODELOS PYDANTIC
# ==========================================

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
    GrupoSanguineo: Optional[str] = None


# Modelo para actualizar únicamente el Estado con control de Rol
class EstadoPersonaUpdate(BaseModel):
    Estado: str
    RolUsuario: Optional[str] = "CONTRATISTA"


# ==========================================
# ENDPOINTS 
# ==========================================

# GET /personas (Listar)
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
            persona.GrupoSanguineo
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


# ==========================================
# NUEVO ENDPOINT: CAMBIAR ESTADO (PATCH)
# ==========================================
@router.patch("/{persona_id}/estado")
def cambiar_estado_persona(persona_id: int, req: EstadoPersonaUpdate, request: Request):
    # 1. Validar permisos: Solo ADMIN y SUPERVISOR pueden cambiar el estado
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

        # 2. Validar que la persona exista en la base de datos
        cursor.execute("SELECT Id, Nombres, Apellidos FROM PERSONAS WHERE Id = ?", (persona_id,))
        persona = cursor.fetchone()
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró ninguna persona con el Id = {persona_id}"
            )

        # 3. Actualizar únicamente la columna Estado
        query = "UPDATE PERSONAS SET Estado = ? WHERE Id = ?"
        cursor.execute(query, (nuevo_estado, persona_id))

        # 4. Obtener el ID del usuario responsable de la acción
        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (req.RolUsuario.strip(),))
        usr = cursor.fetchone()
        usuario_id = usr[0] if usr else None

        # 5. Registrar en auditoría estampando la huella digital del servidor
        ip_cliente = request.client.host if request.client else "127.0.0.1"
        registrar_evento_auditoria(
            cursor=cursor,
            usuario_id=usuario_id,
            accion=f"CAMBIO_ESTADO_{nuevo_estado}_ID_{persona_id}",
            tabla_afectada="PERSONAS",
            ip_cliente=ip_cliente,
            detalle_extra=f"Persona: {persona[1]} {persona[2]}"
        )

        # 6. Guardar ambas operaciones juntas de forma atómica
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