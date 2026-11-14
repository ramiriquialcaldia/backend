import os
import io
import urllib.request
from fastapi import APIRouter, HTTPException
from pypdf import PdfReader
from database import get_connection

router = APIRouter(
    prefix="/indicadores",
    tags=["Indicadores IA"]
)


def extraer_texto_pdf(url_pdf: str, max_caracteres: int = 2500) -> str:
    """Extrae el texto de un PDF almacenado en uploads/ o URL externa."""
    if not url_pdf:
        return ""
    try:
        pdf_bytes = None
        if "127.0.0.1:8000/uploads/" in url_pdf or "localhost:8000/uploads/" in url_pdf:
            ruta_relativa = url_pdf.split("/uploads/")[1]
            ruta_local = os.path.join("uploads", ruta_relativa)
            if os.path.exists(ruta_local):
                with open(ruta_local, "rb") as f:
                    pdf_bytes = f.read()
        elif url_pdf.startswith("http"):
            req = urllib.request.urlopen(url_pdf, timeout=5)
            pdf_bytes = req.read()

        if not pdf_bytes:
            return ""

        reader = PdfReader(io.BytesIO(pdf_bytes))
        texto = []
        for page in reader.pages:
            contenido = page.extract_text()
            if contenido:
                texto.append(contenido.strip())
        return " ".join(texto)[:max_caracteres]
    except Exception:
        return ""


def redactar_concepto_local(p: dict, valoraciones: list, textos_pdfs: list) -> str:
    """
    Párrafo 1: Cuidados prioritarios, precauciones de movimiento y alertas médicas.
    Párrafo 2: Síntesis del seguimiento interdisciplinario, medicamentos y apoyo familiar.
    """
    nombre = f"{p.get('Nombres') or ''} {p.get('Apellidos') or ''}".strip()
    diag = (p.get("DiagnosticoPrincipal") or "").strip()
    cirugias = (p.get("CirugiasRealizadas") or "").strip()
    meds = (p.get("MedicamentosConsume") or "").strip()
    obs = (p.get("ObservacionGeneral") or "").strip()
    disc = (p.get("CondicionDiscapacidad") or "NO").strip()
    convive = (p.get("ConQuienVive") or "").strip()
    hijos = (p.get("HijosYCuantosResponden") or "").strip()

    # Unificar todo el contexto clínico para detectar riesgos y cuidados clave
    contexto_total = f"{diag} {cirugias} {obs} {' '.join([v[3] for v in valoraciones])} {' '.join(textos_pdfs)}".lower()

    cuidados = []

    # Cuidados articulares / movilidad / rodillas
    if any(k in contexto_total for k in ["rodilla", "articular", "artritis", "escaleras", "cojear", "caminar"]):
        cuidados.append(
            "tener precaución con caminatas prolongadas, terrenos irregulares y el ascenso o descenso frecuente de escaleras para evitar sobrecarga articular en rodillas, priorizando caminatas cortas en terreno plano y calzado cómodo"
        )

    # Cuidados por cirugías (hernia, cataratas, etc.)
    if "hernia" in contexto_total:
        cuidados.append(
            "evitar levantar objetos pesados o realizar esfuerzos abdominales bruscos debido a su antecedente quirúrgico de hernia"
        )
    if "cataratas" in contexto_total or disc.upper() != "NO":
        cuidados.append(
            "mantener espacios bien iluminados y libres de obstáculos para prevenir caídas"
        )

    # Cuidados metabólicos / cardiovasculares
    if "diabetes" in contexto_total or "glucosa" in contexto_total:
        cuidados.append(
            "vigilar signos de descompensación glucémica, mantener alimentación balanceada y revisar el cuidado de los pies"
        )
    if any(k in contexto_total for k in ["presión alta", "hipertensión", "tension", "arterial"]):
        cuidados.append(
            "realizar monitoreo periódico de la presión arterial y evitar esfuerzos físicos intensos o cambios bruscos de postura"
        )

    if not cuidados:
        cuidados.append(
            "realizar actividad física moderada según tolerancia, evitando esfuerzos bruscos, fatiga excesiva o caídas"
        )

    # PÁRRAFO 1: DIRECTO A LOS CUIDADOS QUE HAY QUE TENER CON LA PERSONA
    parrafo_1 = (
        f"Como concepto y recomendación principal para el cuidado de {nombre}, se sugiere "
        f"{', además de '.join(cuidados)}."
    )
    if meds and meds.lower() not in ["ninguno", "ninguna", "no"]:
        parrafo_1 += (
            f" Asimismo, es fundamental garantizar estricta adherencia a su tratamiento farmacológico ({meds.rstrip('.')}), "
            "acompañado de hidratación adecuada y consulta médica inmediata si aparece dolor persistente, inflamación o dificultad para apoyar."
        )

    # PÁRRAFO 2: SÍNTESIS BREVE DE QUIÉNES LO HAN VALORADO Y SU ENTORNO DE APOYO
    partes_p2 = []
    if valoraciones:
        areas = []
        for prof, cargo, _, _ in valoraciones:
            etiqueta = f"{prof} ({cargo})" if cargo else prof
            if etiqueta not in areas:
                areas.append(etiqueta)
        partes_p2.append(
            f"Este concepto integra {len(valoraciones)} valoración(es) profesional(es) ({', '.join(areas)})"
            + (f" y {len(textos_pdfs)} soporte(s) clínico(s) en PDF" if textos_pdfs else "")
            + ", evidenciando buena actitud y autonomía básica en casa"
        )
    else:
        partes_p2.append("Pendiente de complementar con valoraciones profesionales periódicas en el programa")

    if convive or hijos:
        apoyo = []
        if convive:
            apoyo.append(f"vive {convive.lower()}")
        if hijos:
            apoyo.append(f"cuenta con respaldo familiar ({hijos.rstrip('.').lower()})")
        partes_p2.append(f"En su entorno social {' y '.join(apoyo)}, aspecto clave para acompañar sus controles médicos.")
    else:
        partes_p2.append("Se recomienda verificar su red de apoyo familiar para el seguimiento de controles.")

    parrafo_2 = ". ".join(partes_p2).replace("..", ".")

    return f"{parrafo_1}\n\n{parrafo_2}"


@router.get("")
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
        registros = []
        for fila in cursor.fetchall():
            item = dict(zip(columnas, fila))
            if item.get("FechaGeneracion"):
                item["FechaGeneracion"] = str(item["FechaGeneracion"])
            registros.append(item)
        return {"total": len(registros), "data": registros}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


@router.post("/generar/{persona_id}", status_code=201)
def generar_indicador_consolidado(persona_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Consultar datos personales para concatenar y los campos clínicos/sociales
        cursor.execute("""
            SELECT 
                Nombres, Apellidos, Direccion, Eps, GrupoSanguineo,
                FechaNacimiento, Peso, CondicionDiscapacidad,
                ConQuienVive, HijosYCuantosResponden, DiagnosticoPrincipal,
                CirugiasRealizadas, MedicamentosConsume, ObservacionGeneral
            FROM PERSONAS
            WHERE Id = ?
        """, (persona_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="La persona seleccionada no existe.")

        p = dict(zip([col[0] for col in cursor.description], row))

        # 2. Concatenar: Nombres, Apellidos, Dirección, EPS y Grupo Sanguíneo (RH)
        nombres_completos = f"{p.get('Nombres') or ''} {p.get('Apellidos') or ''}".strip()
        direccion = p.get("Direccion") or "Sin dirección"
        eps = p.get("Eps") or "Sin EPS"
        rh = p.get("GrupoSanguineo") or "RH N/R"
        nombre_persona_bd = f"{nombres_completos} | Dir: {direccion} | EPS: {eps} | RH: {rh}"[:150]

        # 3. Obtener TODAS las valoraciones con profesión/cargo del evaluador
        cursor.execute("""
            SELECT v.NombreProfesional, u.Profesion, v.FechaValoracion, v.ValoracionDetalle
            FROM VALORACIONES_INSTITUCIONALES v
            LEFT JOIN USUARIOS u ON v.NombreProfesional = u.Usuario OR v.NombreProfesional = u.NombreCompleto
            WHERE v.PersonaId = ?
            ORDER BY v.FechaValoracion ASC
        """, (persona_id,))
        valoraciones = cursor.fetchall()

        # 4. Obtener todos los archivos PDF cargados de esta persona
        cursor.execute("""
            SELECT NombreArchivo, UrlDocumento
            FROM DOCUMENTOS_PERSONAS
            WHERE PersonaId = ?
            ORDER BY FechaSubida ASC
        """, (persona_id,))
        documentos = cursor.fetchall()
        textos_pdfs = [extraer_texto_pdf(url_doc) for _, url_doc in documentos if url_doc]

        # 5. Generar concepto de 2 párrafos (usa Gemini si hay API Key, o redactor clínico local)
        resumen_final = ""
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key:
            try:
                from google import genai
                prompt = f"""
Redacta exactamente 2 párrafos cortos y claros en español sobre el adulto mayor {nombre_persona_bd} (SIN copiar y pegar su historia clínica ni hacer listas):
- PÁRRAFO 1 (Prioridad absoluta): Empieza directamente con "Como concepto y recomendación general para el cuidado de {nombres_completos}, se sugiere..." detallando qué movimientos o esfuerzos físicos debe evitar (por rodillas, hernia, caídas, etc.), cuidados con su condición médica, hidratación y adherencia a sus medicamentos ({p.get('MedicamentosConsume')}).
- PÁRRAFO 2: Resume en 3 líneas el acompañamiento que lleva con los profesionales que lo valoraron, los soportes PDF revisados y su red de apoyo familiar ({p.get('ConQuienVive')}, {p.get('HijosYCuantosResponden')}).

Datos clínicos de referencia:
Diagnóstico: {p.get('DiagnosticoPrincipal')} | Cirugías: {p.get('CirugiasRealizadas')} | Discapacidad: {p.get('CondicionDiscapacidad')}
Valoraciones: {[(v[0], v[1], v[3]) for v in valoraciones]}
PDFs: {textos_pdfs}
"""
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
                resumen_final = (resp.text or "").strip()
            except Exception:
                resumen_final = ""

        if not resumen_final:
            resumen_final = redactar_concepto_local(p, valoraciones, textos_pdfs)

        # 6. Guardar o actualizar en INDICADORES_IA (sin trazabilidad)
        cursor.execute("SELECT Id FROM INDICADORES_IA WHERE PersonaId = ?", (persona_id,))
        existente = cursor.fetchone()

        if existente:
            indicador_id = existente[0]
            cursor.execute("""
                UPDATE INDICADORES_IA
                SET NombrePersona = ?, ResumenInformacion = ?, FechaGeneracion = GETDATE()
                WHERE Id = ?
            """, (nombre_persona_bd, resumen_final, indicador_id))
        else:
            cursor.execute("""
                INSERT INTO INDICADORES_IA (PersonaId, NombrePersona, ResumenInformacion)
                OUTPUT INSERTED.Id
                VALUES (?, ?, ?)
            """, (persona_id, nombre_persona_bd, resumen_final))
            indicador_id = cursor.fetchone()[0]

        conn.commit()

        return {
            "mensaje": "Indicador actualizado correctamente",
            "id_indicador": indicador_id,
            "nombre_persona": nombre_persona_bd,
            "resumen": resumen_final
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()