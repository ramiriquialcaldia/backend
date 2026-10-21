from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import get_connection

router = APIRouter(
    prefix="/valoracion",
    tags=["Valoraciones Institucionales"]
)


# MODELO PYDANTIC

class ValoracionCreate(BaseModel):
    PersonaId: int
    UsuarioId: Optional[int] = None
    NombreProfesional: Optional[str] = None
    NombreUsuarioPaciente: Optional[str] = None
    ValoracionDetalle: str
    FechaValoracion: Optional[str] = None  # Formato: YYYY-MM-DD HH:MM:SS (si no se envía, toma la hora actual)


# ENDPOINT: CREAR VALORACIÓN (POST)

@router.post("/CREAR-VALORACIÓN", status_code=201)
def crear_valoracion(val: ValoracionCreate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Validar que la persona exista y obtener su nombre si no viene en el body
        cursor.execute("SELECT Id, Nombres, Apellidos FROM PERSONAS WHERE Id = ?", (val.PersonaId,))
        persona = cursor.fetchone()
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró una persona con PersonaId = {val.PersonaId}"
            )

        nombre_paciente = val.NombreUsuarioPaciente
        if not nombre_paciente:
            nombre_paciente = f"{persona[1]} {persona[2]}".strip()

        # 2. Si se suministra UsuarioId y no viene NombreProfesional, obtenerlo de USUARIOS
        nombre_prof = val.NombreProfesional
        if val.UsuarioId and not nombre_prof:
            cursor.execute("SELECT NombreCompleto FROM USUARIOS WHERE Id = ?", (val.UsuarioId,))
            usuario_row = cursor.fetchone()
            if usuario_row:
                nombre_prof = usuario_row[0]

        # 3. Asignar fecha actual si no se proporciona
        fecha_val = val.FechaValoracion or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 4. Insertar registro en VALORACIONES_INSTITUCIONALES
        query = """
            INSERT INTO VALORACIONES_INSTITUCIONALES (
                PersonaId,
                UsuarioId,
                NombreProfesional,
                NombreUsuarioPaciente,
                ValoracionDetalle,
                FechaValoracion
            )
            OUTPUT INSERTED.Id, INSERTED.FechaValoracion
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            val.PersonaId,
            val.UsuarioId,
            nombre_prof,
            nombre_paciente,
            val.ValoracionDetalle,
            fecha_val
        ))
        resultado = cursor.fetchone()
        nuevo_id = resultado[0]
        fecha_creacion = resultado[1]

        conn.commit()

        return {
            "mensaje": "Valoración institucional registrada con éxito",
            "id_valoracion": nuevo_id,
            "paciente": nombre_paciente,
            "profesional": nombre_prof,
            "fecha_valoracion": str(fecha_creacion)
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# ENDPOINT: LISTAR TODAS LAS VALORACIONES (GET)

@router.get("/LISTAR-VALORACIONES")
def listar_valoraciones():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                Id,
                PersonaId,
                UsuarioId,
                NombreProfesional,
                NombreUsuarioPaciente,
                ValoracionDetalle,
                FechaValoracion
            FROM VALORACIONES_INSTITUCIONALES
            ORDER BY FechaValoracion DESC
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


# ENDPOINT: CONSULTAR VALORACIONES POR PERSONA

@router.get("/persona/{persona_id}")
def valoraciones_por_persona(persona_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        query = """
            SELECT 
                Id,
                PersonaId,
                UsuarioId,
                NombreProfesional,
                NombreUsuarioPaciente,
                ValoracionDetalle,
                FechaValoracion
            FROM VALORACIONES_INSTITUCIONALES
            WHERE PersonaId = ?
            ORDER BY FechaValoracion DESC
        """
        cursor.execute(query, (persona_id,))
        columnas = [col[0] for col in cursor.description]
        registros = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"persona_id": persona_id, "total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()