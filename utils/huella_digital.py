import platform
import subprocess
import hashlib
import uuid
import os

# Sal secreta fija para vincular la llave al proyecto
SALT_INSTITUCIONAL = "AlcaldiaRamiriqui_Salud2026_KeyMaster"

def _obtener_id_hardware_crudo() -> str:
    """Extrae el identificador de hardware nativo según el sistema operativo."""
    sistema = platform.system().lower()
    hardware_id = ""

    try:
        if sistema == "windows":
            # 1. Consulta estándar por PowerShell
            cmd = "powershell -NoProfile -Command \"(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID\""
            salida = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
            if salida and len(salida) > 8:
                hardware_id = salida
            else:
                # 2. Respaldo por wmic
                cmd_wmic = "wmic csproduct get uuid"
                salida_wmic = subprocess.check_output(cmd_wmic, shell=True, text=True, stderr=subprocess.DEVNULL)
                lineas = [l.strip() for l in salida_wmic.splitlines() if l.strip()]
                if len(lineas) > 1:
                    hardware_id = lineas[1]

        elif sistema == "linux":
            # Rutas estándar en Linux y Azure App Service
            for ruta in ["/etc/machine-id", "/var/lib/dbus/machine-id", "/sys/class/dmi/id/product_uuid"]:
                if os.path.exists(ruta):
                    with open(ruta, "r") as f:
                        contenido = f.read().strip()
                        if contenido:
                            hardware_id = contenido
                            break

    except Exception:
        hardware_id = ""

    # Respaldo si el SO tiene restricciones de permisos
    if not hardware_id or "00000000" in hardware_id:
        hardware_id = f"{uuid.getnode()}-{platform.node()}-{platform.processor()}"

    return hardware_id


def generar_huella_servidor() -> dict:
    """
    Genera una huella digital determinista y única.
    El mismo servidor siempre producirá la misma clave.
    """
    raw_id = _obtener_id_hardware_crudo()
    sistema = platform.system()
    maquina = platform.node()

    cadena_base = f"{raw_id}:{sistema}:{maquina}:{SALT_INSTITUCIONAL}"
    hash_completo = hashlib.sha256(cadena_base.encode("utf-8")).hexdigest().upper()

    bloque = f"RAM-{hash_completo[0:4]}-{hash_completo[4:8]}-{hash_completo[8:12]}-{hash_completo[12:16]}"

    return {
        "huella_servidor": bloque,
        "hash_seguridad": hash_completo,
        "sistema": sistema,
        "nodo": maquina
    }