from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_connection

router = APIRouter(
    prefix="/indicadores",
    tags=["Indicadores IA"]
)

# MODELO DE VALIDACIÓN PYDANTIC

class IndicadorCreate(BaseModel):
    PersonaId: int
    NombrePersona: Optional[str] = None
    ResumenInformacion: str

# ENDPOINT: INSERTAR REGISTRO EN INDICADORES_IA

@router.post("/REGISTRO-INDICADORES", status_code=201)
def crear_indicador(indicador: IndicadorCreate):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Validar que la persona exista en la tabla PERSONAS
        cursor.execute("SELECT Id, Nombres, Apellidos FROM PERSONAS WHERE Id = ?", (indicador.PersonaId,))
        persona = cursor.fetchone()
        if not persona:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró ninguna persona con el PersonaId = {indicador.PersonaId}"
            )

        # Si no se envía NombrePersona en el body, se completa automáticamente con el de la BD
        nombre_completo = indicador.NombrePersona
        if not nombre_completo:
            nombre_completo = f"{persona[1]} {persona[2]}".strip()

        # 2. Insertar en INDICADORES_IA (FechaGeneracion toma el valor por defecto GETDATE())
        query = """
            INSERT INTO INDICADORES_IA (PersonaId, NombrePersona, ResumenInformacion)
            OUTPUT INSERTED.Id, INSERTED.FechaGeneracion
            VALUES (?, ?, ?)
        """
        cursor.execute(query, (indicador.PersonaId, nombre_completo, indicador.ResumenInformacion))
        resultado = cursor.fetchone()
        nuevo_id = resultado[0]
        fecha_generada = resultado[1]

        conn.commit()

        return {
            "mensaje": "Indicador guardado exitosamente",
            "id_indicador": nuevo_id,
            "persona_id": indicador.PersonaId,
            "nombre_persona": nombre_completo,
            "fecha_generacion": str(fecha_generada)
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# ==========================================
# ENDPOINT: LISTAR INDICADORES
@router.get("/LISTAR-INDICADORES")
def listar_indicadores():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT Id, PersonaId, NombrePersona, ResumenInformacion, FechaGeneracion
            FROM INDICADORES_IA
            ORDER BY FechaGeneracion DESC
        """)
        columnas = [col[0] for col in cursor.description]
        registros = [dict(zip(columnas, fila)) for fila in cursor.fetchall()]
        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()