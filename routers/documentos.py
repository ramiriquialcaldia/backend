from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_connection
from utils.contexto_auditoria import establecer_contexto_auditoria

router = APIRouter(
    prefix="/documentos",
    tags=["Documentos PDF"]
)


class DocumentoPersonaCreate(BaseModel):
    PersonaId: int
    NombrePaciente: str
    NombreArchivo: Optional[str] = "Documento.pdf"
    TipoDocumento: Optional[str] = "Soporte PDF"
    UrlDocumento: str
    SubidoPor: Optional[str] = None


@router.get("/persona/{persona_id}")
def listar_documentos_persona(persona_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                Id, PersonaId, NombrePaciente, NombreArchivo, 
                TipoDocumento, UrlDocumento, SubidoPor, FechaSubida
            FROM DOCUMENTOS_PERSONAS
            WHERE PersonaId = ?
            ORDER BY FechaSubida DESC
        """, (persona_id,))
        columnas = [col[0] for col in cursor.description]
        registros = []
        for fila in cursor.fetchall():
            item = dict(zip(columnas, fila))
            if item.get("FechaSubida"):
                item["FechaSubida"] = str(item["FechaSubida"])
            registros.append(item)
        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


@router.post("", status_code=201)
def registrar_documento_persona(doc: DocumentoPersonaCreate, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Id, Nombres, Apellidos FROM PERSONAS WHERE Id = ?", (doc.PersonaId,))
        persona = cursor.fetchone()
        if not persona:
            raise HTTPException(status_code=404, detail="La persona seleccionada no existe.")

        nombre_paciente_real = f"{persona[1]} {persona[2]}".strip()

        usuario_id = None
        if doc.SubidoPor:
            cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (doc.SubidoPor.strip(),))
            usr = cursor.fetchone()
            if usr:
                usuario_id = usr[0]

        establecer_contexto_auditoria(cursor, request, usuario_id=usuario_id)

        query = """
            INSERT INTO DOCUMENTOS_PERSONAS (
                PersonaId, NombrePaciente, NombreArchivo, 
                TipoDocumento, UrlDocumento, SubidoPor
            )
            OUTPUT INSERTED.Id, INSERTED.FechaSubida
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            doc.PersonaId,
            nombre_paciente_real,
            doc.NombreArchivo,
            doc.TipoDocumento,
            doc.UrlDocumento.strip(),
            doc.SubidoPor.strip() if doc.SubidoPor else None
        ))
        fila_doc = cursor.fetchone()
        nuevo_doc_id = fila_doc[0]
        fecha_subida = fila_doc[1]

        conn.commit()

        return {
            "mensaje": "Documento PDF registrado con éxito",
            "id_documento": nuevo_doc_id,
            "fecha_subida": str(fecha_subida)
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()