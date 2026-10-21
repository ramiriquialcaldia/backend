from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from database import get_connection
import bcrypt
from typing import Literal

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"]
)

# MODELOS PYDANTIC

# 1. Creación directa con todos los datos (Endpoint temporal/administrativo)
class UsuarioCompletoCreate(BaseModel):
    NombreCompleto: str
    Usuario: str
    CorreoInstitucional: Optional[str] = None
    Contrasena: str
    PermisosRol: Literal["CONTRATISTA", "SUPERVISOR"]
    EstadoActivo: Optional[bool] = True

# 2. Datos mínimos que envía el Administrador para pre-crear
class PreCrearContratista(BaseModel):
    Usuario: str
    Contrasena: str
    PermisosRol: Literal["CONTRATISTA", "SUPERVISOR"]

# 3. Login para validar credenciales
class LoginRequest(BaseModel):
    Usuario: str
    Contrasena: str

# 4. Datos que llena el contratista en su primer ingreso
class CompletarPerfilRequest(BaseModel):
    Usuario: str
    NombreCompleto: str
    CorreoInstitucional: str
    NuevaContrasena: str


# FUNCIONES DE SEGURIDAD (BCRYPT)

def encriptar_contrasena(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verificar_contrasena(password_plano: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password_plano.encode('utf-8'), password_hash.encode('utf-8'))


# ENDPOINT 1 : CREAR USUARIO DIRECTO Y COMPLETO

@router.post("/crear-completo", status_code=201)
def crear_usuario_completo(req: UsuarioCompletoCreate):
    """Crea un usuario con todos sus campos de una sola vez."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Validar si el usuario ya existe
        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (req.Usuario.strip(),))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado.")

        clave_encriptada = encriptar_contrasena(req.Contrasena)
        correo = req.CorreoInstitucional or f"{req.Usuario.strip()}@ramiriqui-boyaca.gov.co"
        estado = 1 if req.EstadoActivo else 0
        rol = req.PermisosRol.strip() if req.PermisosRol else "CONTRATISTA"

        query = """
            INSERT INTO USUARIOS (
                NombreCompleto,
                Usuario,
                CorreoInstitucional,
                ContrasenaHash,
                PermisosRol,
                EstadoActivo
            )
            OUTPUT INSERTED.Id
            VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(query, (
            req.NombreCompleto.strip(),
            req.Usuario.strip(),
            correo,
            clave_encriptada,
            rol,
            estado
        ))
        nuevo_id = cursor.fetchone()[0]
        conn.commit()

        return {
            "mensaje": "Usuario completo creado exitosamente",
            "id_usuario": nuevo_id,
            "usuario": req.Usuario.strip(),
            "rol": rol
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


# ENDPOINT 2: ADMIN REGISTRA USUARIO Y CLAVE PROVISIONAL

@router.post("/pre-crear", status_code=201)
def pre_crear_usuario(req: PreCrearContratista):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        usuario_limpio = req.Usuario.strip()

        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (usuario_limpio,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")

        clave_encriptada = encriptar_contrasena(req.Contrasena)

        # Correo y Nombre temporales únicos para no violar la restricción UNIQUE
        nombre_temporal = f"PENDIENTE_{usuario_limpio}"
        correo_temporal = f"pendiente_{usuario_limpio}@temporal.local"

        query = """
            INSERT INTO USUARIOS (
                NombreCompleto,
                Usuario,
                CorreoInstitucional,
                ContrasenaHash,
                PermisosRol,
                EstadoActivo
            )
            OUTPUT INSERTED.Id
            VALUES (?, ?, ?, ?, ?, 1)
        """
        # Se envían los valores temporales únicos
        cursor.execute(
            query,
            (nombre_temporal, usuario_limpio, correo_temporal, clave_encriptada, req.PermisosRol)
        )
        nuevo_id = cursor.fetchone()[0]
        conn.commit()

        return {
            "mensaje": f"Usuario {req.PermisosRol.lower()} pre-creado con éxito",
            "id_usuario": nuevo_id,
            "usuario": usuario_limpio,
            "correo": correo_temporal,
            "rol": req.PermisosRol,
            "estado": "ACTIVO"
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# ENDPOINT: LOGIN (Estado y validación limpia)

@router.post("/login")
def login(req: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Consulta completa idéntica a la que funcionaba
        cursor.execute("""
            SELECT Id, Usuario, ContrasenaHash, NombreCompleto, CorreoInstitucional, PermisosRol, EstadoActivo
            FROM USUARIOS
            WHERE Usuario = ?
        """, (req.Usuario.strip(),))
        
        usuario = cursor.fetchone()

        if not usuario:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

        # Desempaquetado seguro de la tupla (evita el error de user.ContrasenaHash)
        id_usr, user_name, hash_guardado, nombre, correo, rol, activo = usuario

        # Validar estado activo
        estado_texto = "ACTIVO" if activo in [1, True] else "INACTIVO"
        if estado_texto == "INACTIVO":
            raise HTTPException(status_code=403, detail="El usuario se encuentra inactivo.")

        # Validar contraseña encriptada
        if not verificar_contrasena(req.Contrasena, hash_guardado):
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

        # Evaluar si el nombre o correo inician con 'PENDIENTE'
        nombre_str = str(nombre or "").strip().upper()
        correo_str = str(correo or "").strip().upper()

        requiere_completar_datos = (
            nombre is None 
            or nombre_str == "" 
            or nombre_str.startswith("PENDIENTE")
            or correo is None 
            or correo_str == "" 
            or correo_str.startswith("PENDIENTE")
        )

        return {
            "mensaje": "Inicio de sesión correcto",
            "id_usuario": id_usr,
            "usuario": user_name,
            "rol": rol,
            "estado": estado_texto,
            "primer_ingreso": requiere_completar_datos
        }
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()

# ENDPOINT 4: ACTUALIZAR MISMA FILA CON LOS DATOS FINALES

@router.put("/completar-registro")
def completar_registro(req: CompletarPerfilRequest):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (req.Usuario.strip(),))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        nueva_clave_hash = encriptar_contrasena(req.NuevaContrasena)

        query = """
            UPDATE USUARIOS
            SET NombreCompleto = ?,
                CorreoInstitucional = ?,
                ContrasenaHash = ?
            WHERE Usuario = ?
        """
        cursor.execute(query, (
            req.NombreCompleto.strip(),
            req.CorreoInstitucional.strip(),
            nueva_clave_hash,
            req.Usuario.strip()
        ))
        conn.commit()

        return {
            "mensaje": "Perfil completado y contraseña actualizada exitosamente",
            "usuario": req.Usuario.strip(),
            "nombre_completo": req.NombreCompleto.strip()
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()