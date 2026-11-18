from fastapi import Request
from utils.huella_digital import generar_huella_servidor


def establecer_contexto_auditoria(
    cursor,
    request: Request,
    usuario_id: int | None = None,
    usuario_nombre: str | None = None
):
    """
    Envía UsuarioId, IP y Huella de Hardware a la sesión de SQL Server
    para que los Triggers los capturen solo si el INSERT/UPDATE tiene éxito.
    """
    ip_cliente = request.client.host if request.client else "127.0.0.1"
    info_huella = generar_huella_servidor()
    huella = info_huella.get("huella_servidor", "LOCAL-DEV")
    sistema = info_huella.get("sistema", "SO")
    cliente = (request.headers.get("user-agent") or "Web")[:130]
    dispositivo = f"Servidor: {huella} ({sistema}) | Cliente: {cliente}"[:255]

    cursor.execute("""
        EXEC sp_set_session_context @key = N'UsuarioId', @value = ?;
        EXEC sp_set_session_context @key = N'DireccionIP', @value = ?;
        EXEC sp_set_session_context @key = N'Dispositivo', @value = ?;
        EXEC sp_set_session_context @key = N'UsuarioNombre', @value = ?;
    """, (usuario_id, ip_cliente[:50], dispositivo, (usuario_nombre or "")[:100]))