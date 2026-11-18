from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import get_connection
from utils.contexto_auditoria import establecer_contexto_auditoria

router = APIRouter(
    prefix="/valoracion",
    tags=["Valoraciones Institucionales"]
)


class ValoracionCreate(BaseModel):
    PersonaId: int
    UsuarioId: Optional[int] = None
    NombreProfesional: Optional[str] = None
    NombreUsuarioPaciente: Optional[str] = None
    ValoracionDetalle: str
    FechaValoracion: Optional[str] = None



@router.post("", status_code=201)
def crear_valoracion(val: ValoracionCreate, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Id, Nombres, Apellidos FROM PERSONAS WHERE Id = ?", (val.PersonaId,))
        persona = cursor.fetchone()
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró ninguna persona con el PersonaId = {val.PersonaId}"
            )

        fecha_val = val.FechaValoracion or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nombre_prof = (val.NombreProfesional or "No especificado").strip()

        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (nombre_prof,))
        usr = cursor.fetchone()
        usuario_id = usr[0] if usr else val.UsuarioId

        establecer_contexto_auditoria(cursor, request, usuario_id=usuario_id)

        # Inserción estándar compatible con triggers de auditoría
        query = """
            INSERT INTO VALORACIONES_INSTITUCIONALES (
                PersonaId,
                NombreProfesional,
                ValoracionDetalle,
                FechaValoracion
            )
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (
            val.PersonaId,
            nombre_prof,
            val.ValoracionDetalle.strip(),
            fecha_val
        ))
        
        # Obtener el ID generado usando @@IDENTITY de forma segura
        cursor.execute("SELECT @@IDENTITY")
        fila_id = cursor.fetchone()
        nuevo_id = int(fila_id[0]) if fila_id and fila_id[0] is not None else 0

        fecha_creacion = fecha_val

        conn.commit()

        return {
            "mensaje": "Valoración institucional registrada con éxito",
            "id_valoracion": nuevo_id,
            "persona_id": val.PersonaId,
            "nombre_profesional": nombre_prof,
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
        