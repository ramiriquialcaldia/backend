from database import get_connection
from utils.huella_digital import generar_huella_servidor

def registrar_evento_auditoria(
    cursor,
    usuario_id: int | None,
    accion: str,
    tabla_afectada: str,
    ip_cliente: str = "127.0.0.1",
    detalle_extra: str = ""
):
    """
    Inserta un evento en TRAZABILIDAD_AUDITORIA usando la transacción activa.
    """
    try:
        datos_huella = generar_huella_servidor()
        huella_servidor = datos_huella.get("huella_servidor", "LOCAL-DEV")
        dispositivo_info = f"Servidor: {huella_servidor} | OS: {datos_huella.get('sistema', 'N/A')}"
        if detalle_extra:
            dispositivo_info += f" | {detalle_extra}"

        query = """
            INSERT INTO TRAZABILIDAD_AUDITORIA (
                UsuarioId, AccionRealizada, TablaAfectada, DireccionIP, Dispositivo
            ) VALUES (?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            usuario_id,
            accion[:50],            # Truncar al límite varchar(50)
            tabla_afectada[:100],   # Truncar al límite varchar(100)
            ip_cliente[:50],
            dispositivo_info[:255]
        ))
    except Exception as err:
        print(f"Error al registrar auditoría: {err}")