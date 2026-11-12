from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import get_connection
from utils.auditoria import registrar_evento_auditoria

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

@router.post("", status_code=201)
def crear_valoracion(val: ValoracionCreate, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Validar que la persona exista en la tabla PERSONAS
        cursor.execute("SELECT Id, Nombres, Apellidos FROM PERSONAS WHERE Id = ?", (val.PersonaId,))
        persona = cursor.fetchone()
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró ninguna persona con el PersonaId = {val.PersonaId}"
            )

        fecha_val = val.FechaValoracion or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        nombre_prof = (val.NombreProfesional or "No especificado").strip()

        # 2. Insertar únicamente en las 4 columnas activas de la BD
        query = """
            INSERT INTO VALORACIONES_INSTITUCIONALES (
                PersonaId,
                NombreProfesional,
                ValoracionDetalle,
                FechaValoracion
            )
            OUTPUT INSERTED.Id, INSERTED.FechaValoracion
            VALUES (?, ?, ?, ?)
        """
        cursor.execute(query, (
            val.PersonaId,
            nombre_prof,
            val.ValoracionDetalle.strip(),
            fecha_val
        ))
        fila = cursor.fetchone()
        nuevo_id = fila[0]
        fecha_creacion = fila[1]

        # 3. Obtener el ID del usuario en sesión si existe
        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (nombre_prof,))
        usr = cursor.fetchone()
        usuario_id = usr[0] if usr else None

        # 4. Registrar trazabilidad con huella digital de hardware
        ip_cliente = request.client.host if request.client else "127.0.0.1"
        registrar_evento_auditoria(
            cursor=cursor,
            usuario_id=usuario_id,
            accion=f"CREAR_VALORACION_ID_{nuevo_id}",
            tabla_afectada="VALORACIONES_INSTITUCIONALES",
            ip_cliente=ip_cliente,
            detalle_extra=f"PersonaId: {val.PersonaId} | Paciente: {persona[1]} {persona[2]}"
        )

        # 5. Confirmar ambas inserciones de forma atómica
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