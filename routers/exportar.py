import io
import os
import urllib.request
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from database import get_connection

router = APIRouter(
    prefix="/exportar",
    tags=["Exportación Word"]
)

NAVY_HEX = "0F2942"
SLATE_HEX = "F1F5F9"
BORDER_HEX = "CBD5E1"


def aplicar_fondo_celda(celda, color_hex: str):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
    celda._tc.get_or_add_tcPr().append(shading)


def aplicar_bordes_tabla(tabla, color_hex: str = BORDER_HEX):
    tblPr = tabla._tbl.tblPr
    borders = parse_xml(f'''
        <w:tblBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
            <w:bottom w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
            <w:left w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
            <w:right w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
            <w:insideH w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
            <w:insideV w:val="single" w:sz="4" w:space="0" w:color="{color_hex}"/>
        </w:tblBorders>
    ''')
    tblPr.append(borders)


def agregar_encabezado_institucional(doc: Document, titulo_documento: str):
    # Configurar márgenes limpios
    for section in doc.sections:
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)
        section.left_margin = Inches(0.7)
        section.right_margin = Inches(0.7)

    p_entidad = doc.add_paragraph()
    p_entidad.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_entidad = p_entidad.add_run("ALCALDÍA MUNICIPAL DE RAMIRIQUÍ - BOYACÁ\n")
    run_entidad.bold = True
    run_entidad.font.size = Pt(13)
    run_entidad.font.color.rgb = RGBColor(15, 41, 66)

    run_sub = p_entidad.add_run("Secretaría de Desarrollo Social • Programa de Atención al Adulto Mayor\n")
    run_sub.font.size = Pt(9.5)
    run_sub.font.color.rgb = RGBColor(100, 116, 139)

    run_titulo = p_entidad.add_run(titulo_documento.upper())
    run_titulo.bold = True
    run_titulo.font.size = Pt(11.5)
    run_titulo.font.color.rgb = RGBColor(15, 41, 66)

    p_fecha = doc.add_paragraph()
    p_fecha.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_fecha = p_fecha.add_run(f"Fecha de generación: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    r_fecha.font.size = Pt(8.5)
    r_fecha.font.color.rgb = RGBColor(100, 116, 139)


def agregar_titulo_seccion(doc: Document, texto: str):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(texto.upper())
    run.bold = True
    run.font.size = Pt(10.5)
    run.font.color.rgb = RGBColor(15, 41, 66)


def obtener_stream_imagen(url_foto: str):
    if not url_foto:
        return None
    try:
        # Si es archivo local en uploads/fotos/...
        if "127.0.0.1:8000/uploads/" in url_foto or "localhost:8000/uploads/" in url_foto:
            ruta_relativa = url_foto.split("/uploads/")[1]
            ruta_local = os.path.join("uploads", ruta_relativa)
            if os.path.exists(ruta_local):
                with open(ruta_local, "rb") as f:
                    return io.BytesIO(f.read())
        # Si es URL externa (Azure Blob Storage u otro servidor)
        elif url_foto.startswith("http"):
            req = urllib.request.urlopen(url_foto, timeout=5)
            return io.BytesIO(req.read())
    except Exception:
        return None
    return None


def agregar_tabla_pares(doc: Document, pares: list):
    """Dibuja una tabla elegante de 4 columnas (Etiqueta | Valor | Etiqueta | Valor)."""
    filas = (len(pares) + 1) // 2
    tabla = doc.add_table(rows=filas, cols=4)
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    aplicar_bordes_tabla(tabla)

    anchos = [Inches(1.6), Inches(1.95), Inches(1.6), Inches(1.95)]

    for idx_fila in range(filas):
        row = tabla.rows[idx_fila]
        for col_i, ancho in enumerate(anchos):
            row.cells[col_i].width = ancho
            row.cells[col_i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER

        # Par izquierdo
        etq1, val1 = pares[idx_fila * 2]
        c0, c1 = row.cells[0], row.cells[1]
        aplicar_fondo_celda(c0, SLATE_HEX)
        r0 = c0.paragraphs[0].add_run(etq1)
        r0.bold = True
        r0.font.size = Pt(8.5)
        r0.font.color.rgb = RGBColor(51, 65, 85)

        r1 = c1.paragraphs[0].add_run(str(val1) if val1 not in [None, ""] else "No registra")
        r1.font.size = Pt(9)

        # Par derecho (si existe)
        if idx_fila * 2 + 1 < len(pares):
            etq2, val2 = pares[idx_fila * 2 + 1]
            c2, c3 = row.cells[2], row.cells[3]
            aplicar_fondo_celda(c2, SLATE_HEX)
            r2 = c2.paragraphs[0].add_run(etq2)
            r2.bold = True
            r2.font.size = Pt(8.5)
            r2.font.color.rgb = RGBColor(51, 65, 85)

            r3 = c3.paragraphs[0].add_run(str(val2) if val2 not in [None, ""] else "No registra")
            r3.font.size = Pt(9)


# ==============================================================================
# 1. DESCARGAR HOJA DE VIDA COMPLETA EN WORD (.docx)
# ==============================================================================
@router.get("/hoja-vida/{persona_id}")
def descargar_hoja_vida_word(persona_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # 1. Consultar Persona
        cursor.execute("SELECT * FROM PERSONAS WHERE Id = ?", (persona_id,))
        row_p = cursor.fetchone()
        if not row_p:
            raise HTTPException(status_code=404, detail="Persona no encontrada.")
        cols_p = [c[0] for c in cursor.description]
        persona = dict(zip(cols_p, row_p))

        # 2. Consultar Autorización
        cursor.execute("SELECT * FROM AUTORIZACION_FICHAMEDICA WHERE PersonaId = ?", (persona_id,))
        row_a = cursor.fetchone()
        autorizacion = dict(zip([c[0] for c in cursor.description], row_a)) if row_a else None

        # 3. Consultar Valoraciones
        cursor.execute("""
            SELECT NombreProfesional, ValoracionDetalle, FechaValoracion
            FROM VALORACIONES_INSTITUCIONALES
            WHERE PersonaId = ?
            ORDER BY FechaValoracion DESC
        """, (persona_id,))
        valoraciones = cursor.fetchall()

        # Crear documento Word
        doc = Document()
        estilo_normal = doc.styles['Normal']
        estilo_normal.font.name = 'Calibri'
        estilo_normal.font.size = Pt(10)

        agregar_encabezado_institucional(doc, "Hoja de Vida Institucional del Adulto Mayor")

        # Bloque superior con Foto + Resumen de Identificación
        tabla_top = doc.add_table(rows=1, cols=2)
        tabla_top.alignment = WD_TABLE_ALIGNMENT.CENTER
        aplicar_bordes_tabla(tabla_top)
        celda_foto = tabla_top.rows[0].cells[0]
        celda_info = tabla_top.rows[0].cells[1]
        celda_foto.width = Inches(1.6)
        celda_info.width = Inches(5.5)

        p_foto = celda_foto.paragraphs[0]
        p_foto.alignment = WD_ALIGN_PARAGRAPH.CENTER
        img_stream = obtener_stream_imagen(persona.get("Foto"))
        if img_stream:
            p_foto.add_run().add_picture(img_stream, width=Inches(1.25))
        else:
            r_sin = p_foto.add_run("\n[Sin Fotografía]\n")
            r_sin.font.size = Pt(8.5)
            r_sin.font.color.rgb = RGBColor(100, 116, 139)

        p_info = celda_info.paragraphs[0]
        nombre_completo = f"{persona.get('Nombres', '')} {persona.get('Apellidos', '')}".strip()
        r_nom = p_info.add_run(f"{nombre_completo}\n")
        r_nom.bold = True
        r_nom.font.size = Pt(13)
        r_nom.font.color.rgb = RGBColor(15, 41, 66)

        r_doc = p_info.add_run(
            f"Documento: {persona.get('TipoDocumento', 'CC')} {persona.get('NumeroDocumento', '')}   |   "
            f"Estado: {(persona.get('Estado') or 'ACTIVO').upper()}\n"
            f"EPS: {persona.get('Eps') or 'No registra'}   |   "
            f"Grupo Sanguíneo (RH): {persona.get('GrupoSanguineo') or 'No registra'}\n"
            f"Teléfono: {persona.get('Telefono') or 'No registra'}   |   "
            f"Dirección: {persona.get('Direccion') or 'No registra'}"
        )
        r_doc.font.size = Pt(9.5)

        # Sección 1: Datos Completos de la Persona
        agregar_titulo_seccion(doc, "1. Datos Completos de la Persona")
        datos_personales = [
            ("ID Sistema", persona.get("Id")),
            ("Fecha Nacimiento", persona.get("FechaNacimiento")),
            ("Sexo", persona.get("Sexo")),
            ("Peso", persona.get("Peso")),
            ("Altura", persona.get("Altura")),
            ("Discapacidad", persona.get("CondicionDiscapacidad")),
            ("Grupo Étnico", persona.get("PerteneceGrupoEtnico")),
            ("Religión", persona.get("Religion")),
            ("Víctima Conflicto", persona.get("VictimaConflicto")),
            ("Nivel de Estudio", persona.get("Estudio")),
            ("Con Quién Vive", persona.get("ConQuienVive")),
            ("Hijos / Responden", persona.get("HijosYCuantosResponden")),
            ("Contacto Emergencia", persona.get("NombreEmergencia")),
            ("Tel. Emergencia", persona.get("NumeroEmergencia")),
        ]
        agregar_tabla_pares(doc, datos_personales)

        # Campos clínicos largos en tabla de 2 columnas
        tabla_clinica = doc.add_table(rows=4, cols=2)
        tabla_clinica.alignment = WD_TABLE_ALIGNMENT.CENTER
        aplicar_bordes_tabla(tabla_clinica)
        campos_largos = [
            ("Diagnóstico Principal", persona.get("DiagnosticoPrincipal") or "Ninguno"),
            ("Cirugías Realizadas", persona.get("CirugiasRealizadas") or "Ninguna"),
            ("Medicamentos Consume", persona.get("MedicamentosConsume") or "Ninguno"),
            ("Observación General", persona.get("ObservacionGeneral") or "Sin observaciones"),
        ]
        for i, (etq, val) in enumerate(campos_largos):
            c0, c1 = tabla_clinica.rows[i].cells[0], tabla_clinica.rows[i].cells[1]
            c0.width = Inches(1.8)
            c1.width = Inches(5.3)
            aplicar_fondo_celda(c0, SLATE_HEX)
            r0 = c0.paragraphs[0].add_run(etq)
            r0.bold = True
            r0.font.size = Pt(8.5)
            r1 = c1.paragraphs[0].add_run(str(val))
            r1.font.size = Pt(9)

        # Sección 2: Autorización de Ficha Médica
        agregar_titulo_seccion(doc, "2. Autorización de Ficha Médica")
        if autorizacion:
            datos_aut = [
                ("Persona que Autorizó", autorizacion.get("NombreUsuarioAutoriza")),
                ("Fecha Autorización", autorizacion.get("FechaAutorizacion")),
                ("¿Se informó?", autorizacion.get("SeInformoAdultoMayor")),
                ("Manifestó Autorización", autorizacion.get("ManifestoAutorizacion")),
                ("Soporte Documental", autorizacion.get("ExisteSoporteDocumental")),
                ("Supervisor Verificó", autorizacion.get("SupervisorVerifico")),
                ("Ubicación Física", autorizacion.get("UbicacionDocumentoFisico")),
                ("Fecha Verificación", str(autorizacion.get("FechaHoraVerificacion"))[:19]),
            ]
            agregar_tabla_pares(doc, datos_aut)
        else:
            p_sin_aut = doc.add_paragraph("No tiene autorización registrada para esta persona.")
            p_sin_aut.runs[0].italic = True

        # Sección 3: Historial de Valoraciones Institucionales
        agregar_titulo_seccion(doc, f"3. Historial de Valoraciones Institucionales ({len(valoraciones)})")
        if valoraciones:
            t_val = doc.add_table(rows=len(valoraciones) + 1, cols=3)
            t_val.alignment = WD_TABLE_ALIGNMENT.CENTER
            aplicar_bordes_tabla(t_val)

            encabezados = ["Fecha", "Profesional Evaluador", "Detalle de la Valoración"]
            anchos_v = [Inches(1.3), Inches(1.8), Inches(4.0)]
            for idx, tit in enumerate(encabezados):
                celda = t_val.rows[0].cells[idx]
                celda.width = anchos_v[idx]
                aplicar_fondo_celda(celda, NAVY_HEX)
                r = celda.paragraphs[0].add_run(tit)
                r.bold = True
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(255, 255, 255)

            for idx_v, (prof, detalle, fecha_v) in enumerate(valoraciones, start=1):
                fila = t_val.rows[idx_v]
                fila.cells[0].width = anchos_v[0]
                fila.cells[1].width = anchos_v[1]
                fila.cells[2].width = anchos_v[2]
                fila.cells[0].paragraphs[0].add_run(str(fecha_v)[:16]).font.size = Pt(8.5)
                fila.cells[1].paragraphs[0].add_run(prof or "No registra").font.size = Pt(8.5)
                fila.cells[2].paragraphs[0].add_run(detalle or "").font.size = Pt(8.5)
        else:
            p_sin_val = doc.add_paragraph("Sin valoraciones institucionales registradas.")
            p_sin_val.runs[0].italic = True

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        nombre_archivo = f"Hoja_de_Vida_{persona.get('NumeroDocumento', persona_id)}.docx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
        )
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


# ==============================================================================
# 2. DESCARGAR SOLO VALORACIONES INSTITUCIONALES EN WORD (.docx)
# ==============================================================================
@router.get("/valoraciones/{persona_id}")
def descargar_valoraciones_word(persona_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT Id, Nombres, Apellidos, TipoDocumento, NumeroDocumento, Eps, DiagnosticoPrincipal
            FROM PERSONAS WHERE Id = ?
        """, (persona_id,))
        row_p = cursor.fetchone()
        if not row_p:
            raise HTTPException(status_code=404, detail="Persona no encontrada.")

        cursor.execute("""
            SELECT NombreProfesional, ValoracionDetalle, FechaValoracion
            FROM VALORACIONES_INSTITUCIONALES
            WHERE PersonaId = ?
            ORDER BY FechaValoracion DESC
        """, (persona_id,))
        valoraciones = cursor.fetchall()

        doc = Document()
        doc.styles['Normal'].font.name = 'Calibri'
        agregar_encabezado_institucional(doc, "Reporte de Valoraciones Institucionales")

        agregar_titulo_seccion(doc, "Datos del Paciente")
        agregar_tabla_pares(doc, [
            ("Nombres y Apellidos", f"{row_p[1]} {row_p[2]}"),
            ("Documento", f"{row_p[3]} {row_p[4]}"),
            ("EPS", row_p[5]),
            ("Diagnóstico Base", row_p[6]),
        ])

        agregar_titulo_seccion(doc, f"Historial de Valoraciones ({len(valoraciones)})")
        if valoraciones:
            t_val = doc.add_table(rows=len(valoraciones) + 1, cols=3)
            t_val.alignment = WD_TABLE_ALIGNMENT.CENTER
            aplicar_bordes_tabla(t_val)

            encabezados = ["Fecha y Hora", "Profesional Evaluador", "Concepto / Valoración Clínica"]
            anchos_v = [Inches(1.35), Inches(1.85), Inches(3.9)]
            for idx, tit in enumerate(encabezados):
                celda = t_val.rows[0].cells[idx]
                celda.width = anchos_v[idx]
                aplicar_fondo_celda(celda, NAVY_HEX)
                r = celda.paragraphs[0].add_run(tit)
                r.bold = True
                r.font.size = Pt(9)
                r.font.color.rgb = RGBColor(255, 255, 255)

            for idx_v, (prof, detalle, fecha_v) in enumerate(valoraciones, start=1):
                fila = t_val.rows[idx_v]
                fila.cells[0].width = anchos_v[0]
                fila.cells[1].width = anchos_v[1]
                fila.cells[2].width = anchos_v[2]
                fila.cells[0].paragraphs[0].add_run(str(fecha_v)[:16]).font.size = Pt(8.5)
                fila.cells[1].paragraphs[0].add_run(prof or "No registra").font.size = Pt(8.5)
                fila.cells[2].paragraphs[0].add_run(detalle or "").font.size = Pt(8.5)
        else:
            doc.add_paragraph("No existen valoraciones registradas para este adulto mayor.")

        buffer = io.BytesIO()
        doc.save(buffer)
        buffer.seek(0)

        nombre_archivo = f"Valoraciones_{row_p[4]}.docx"
        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{nombre_archivo}"'}
        )
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()