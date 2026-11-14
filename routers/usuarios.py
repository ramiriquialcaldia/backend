from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
from database import get_connection
import bcrypt
from typing import Literal
from utils.auditoria import registrar_evento_auditoria

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
    AdminUsuarioId: Optional[int] = None 

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
    Profesion: Optional[str] = None


# FUNCIONES DE SEGURIDAD (BCRYPT)

def encriptar_contrasena(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verificar_contrasena(password_plano: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password_plano.encode('utf-8'), password_hash.encode('utf-8'))

class CambiarEstadoUsuarioRequest(BaseModel):
    EstadoActivo: bool
    UsuarioResponsableId: Optional[int] = None


# ENDPOINT 1 : CREAR USUARIO DIRECTO Y COMPLETO

@router.post("/crear-completo", status_code=201)
def crear_usuario_completo(req: UsuarioCompletoCreate, request: Request):
    """Crea un usuario con todos sus campos de una sola vez."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        usuario_limpio = req.Usuario.strip()

        # Validar si el usuario ya existe
        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (usuario_limpio,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está registrado.")

        clave_encriptada = encriptar_contrasena(req.Contrasena)
        correo = req.CorreoInstitucional or f"{usuario_limpio}@ramiriqui-boyaca.gov.co"
        estado = 1 if req.EstadoActivo else 0
        rol = req.PermisosRol.strip().upper() if req.PermisosRol else "CONTRATISTA"

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
            usuario_limpio,
            correo,
            clave_encriptada,
            rol,
            estado
        ))
        nuevo_id = cursor.fetchone()[0]

        # REGISTRO DE TRAZABILIDAD
        ip_cliente = request.client.host if request.client else "127.0.0.1"
        registrar_evento_auditoria(
            cursor=cursor,
            usuario_id=nuevo_id,
            accion=f"CREAR_USUARIO_{usuario_limpio}",
            tabla_afectada="USUARIOS",
            ip_cliente=ip_cliente,
            detalle_extra=f"Rol: {rol} | Nombre: {req.NombreCompleto.strip()}"
        )

        conn.commit()

        return {
            "mensaje": "Usuario completo creado exitosamente",
            "id_usuario": nuevo_id,
            "usuario": usuario_limpio,
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


# ==========================================
# ENDPOINT 2: ADMIN PRE-CREA USUARIO
# ==========================================
@router.post("/pre-crear", status_code=201)
def pre_crear_usuario(req: PreCrearContratista, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        usuario_limpio = req.Usuario.strip()

        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (usuario_limpio,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso.")

        rol_destino = (req.PermisosRol or "CONTRATISTA").strip().upper()
        clave_encriptada = encriptar_contrasena(req.Contrasena)

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
        cursor.execute(
            query,
            (nombre_temporal, usuario_limpio, correo_temporal, clave_encriptada, rol_destino)
        )
        nuevo_id = cursor.fetchone()[0]

        # REGISTRO DE TRAZABILIDAD:
        # Se asocia al Admin que realiza la acción, NO al nuevo ID creado
        admin_responsable_id = req.AdminUsuarioId
        if not admin_responsable_id:
            # Si no viene en el body, busca el usuario 'administrador'
            cursor.execute("SELECT TOP 1 Id FROM USUARIOS WHERE Usuario = 'administrador'")
            admin_row = cursor.fetchone()
            admin_responsable_id = admin_row[0] if admin_row else None

        ip_cliente = request.client.host if request.client else "127.0.0.1"
        registrar_evento_auditoria(
            cursor=cursor,
            usuario_id=admin_responsable_id,  # <-- AQUÍ QUEDA EL ADMIN
            accion=f"PRE_CREAR_USUARIO_{usuario_limpio}",
            tabla_afectada="USUARIOS",
            ip_cliente=ip_cliente,
            detalle_extra=f"Nuevo usuario: {usuario_limpio} (Rol: {rol_destino})"
        )

        conn.commit()

        return {
            "mensaje": f"Usuario {rol_destino.lower()} pre-creado con éxito",
            "id_usuario": nuevo_id,
            "usuario": usuario_limpio,
            "correo": correo_temporal,
            "rol": rol_destino,
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

# ==========================================
# ENDPOINT 3: LOGIN
# ==========================================
@router.post("/login")
def login(req: LoginRequest):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT Id, Usuario, ContrasenaHash, NombreCompleto, CorreoInstitucional, PermisosRol, EstadoActivo
            FROM USUARIOS
            WHERE Usuario = ?
        """, (req.Usuario.strip(),))
        
        usuario = cursor.fetchone()

        if not usuario:
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

        id_usr, user_name, hash_guardado, nombre, correo, rol, activo = usuario

        # Validar estado activo
        estado_texto = "ACTIVO" if activo in [1, True] else "INACTIVO"
        if estado_texto == "INACTIVO":
            raise HTTPException(status_code=403, detail="El usuario se encuentra inactivo.")

        # Validar contraseña encriptada
        if not verificar_contrasena(req.Contrasena, hash_guardado):
            raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos.")

        # Evaluar si requiere completar datos
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


# ==========================================
# ENDPOINT 4: COMPLETAR REGISTRO
# ==========================================
@router.put("/completar-registro")
def completar_registro(req: CompletarPerfilRequest, request: Request):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        usuario_limpio = req.Usuario.strip()

        cursor.execute("SELECT Id FROM USUARIOS WHERE Usuario = ?", (usuario_limpio,))
        usuario = cursor.fetchone()
        if not usuario:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        id_usuario = usuario[0]
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
            usuario_limpio
        ))

        # REGISTRO DE TRAZABILIDAD
        ip_cliente = request.client.host if request.client else "127.0.0.1"
        registrar_evento_auditoria(
            cursor=cursor,
            usuario_id=id_usuario,
            accion=f"COMPLETAR_PERFIL_{usuario_limpio}",
            tabla_afectada="USUARIOS",
            ip_cliente=ip_cliente,
            detalle_extra=f"Nombre: {req.NombreCompleto.strip()} | Correo: {req.CorreoInstitucional.strip()}"
        )

        conn.commit()

        return {
            "mensaje": "Perfil completado y contraseña actualizada exitosamente",
            "usuario": usuario_limpio,
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






@router.get("/gestion")
def listar_usuarios_gestion():
    """Lista los usuarios de la tabla USUARIOS para administrar su acceso."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT 
                u.Id,
                u.NombreCompleto,
                u.Usuario,
                u.CorreoInstitucional,
                u.PermisosRol,
                u.Profesion,
                u.EstadoActivo,
                u.FechaCreacion,
                u.FechaEliminacion,
                resp.Usuario AS EliminadoPorUsuario
            FROM USUARIOS u
            LEFT JOIN USUARIOS resp ON u.EliminadoPor = resp.Id
            ORDER BY u.Id DESC
        """)
        columnas = [col[0] for col in cursor.description]
        usuarios = []
        for fila in cursor.fetchall():
            item = dict(zip(columnas, fila))
            item["EstadoActivo"] = True if item["EstadoActivo"] in [1, True] else False
            if item.get("FechaCreacion"):
                item["FechaCreacion"] = str(item["FechaCreacion"])[:19]
            if item.get("FechaEliminacion"):
                item["FechaEliminacion"] = str(item["FechaEliminacion"])[:19]
            usuarios.append(item)
        return {"total": len(usuarios), "data": usuarios}
    except Exception as err:
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()


@router.patch("/{usuario_id}/estado")
def cambiar_estado_usuario(usuario_id: int, req: CambiarEstadoUsuarioRequest, request: Request):
    """Revoca o reactiva el acceso en USUARIOS y registra trazabilidad solo si el cambio es exitoso."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT Usuario, PermisosRol, EstadoActivo FROM USUARIOS WHERE Id = ?", (usuario_id,))
        fila = cursor.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Usuario no encontrado.")

        nombre_usr, rol_usr, estado_actual = fila
        estado_actual_bool = True if estado_actual in [1, True] else False

        if str(rol_usr).upper() in ["ADMIN", "ADMINISTRADOR"] and not req.EstadoActivo:
            raise HTTPException(status_code=403, detail="No se puede desactivar la cuenta del Administrador principal.")

        # Si el estado ya es el mismo, no hacer nada ni ensuciar la trazabilidad
        if estado_actual_bool == req.EstadoActivo:
            return {"mensaje": "Sin cambios en el estado del usuario."}

        if not req.EstadoActivo:
            cursor.execute("""
                UPDATE USUARIOS
                SET EstadoActivo = 0,
                    FechaEliminacion = GETDATE(),
                    EliminadoPor = ?
                WHERE Id = ?
            """, (req.UsuarioResponsableId, usuario_id))
            accion_log = f"QUITAR_ACCESO_USUARIO_{nombre_usr}"
        else:
            cursor.execute("""
                UPDATE USUARIOS
                SET EstadoActivo = 1,
                    FechaEliminacion = NULL,
                    EliminadoPor = NULL
                WHERE Id = ?
            """, (usuario_id,))
            accion_log = f"REACTIVAR_ACCESO_USUARIO_{nombre_usr}"

        # Registrar trazabilidad en la misma transacción (solo si el UPDATE tuvo éxito)
        ip_cliente = request.client.host if request.client else "127.0.0.1"
        dispositivo = (request.headers.get("user-agent") or "Web")[:250]

        cursor.execute("""
            INSERT INTO TRAZABILIDAD_AUDITORIA (
                UsuarioId,
                AccionRealizada,
                TablaAfectada,
                DireccionIP,
                Dispositivo,
                UbicacionGeo
            )
            VALUES (?, ?, 'USUARIOS', ?, ?, ?)
        """, (
            req.UsuarioResponsableId,
            accion_log[:50],
            ip_cliente,
            dispositivo,
            f"UsuarioId afectado: {usuario_id} ({rol_usr})"
        ))

        conn.commit()
        return {
            "mensaje": f"Estado de '{nombre_usr}' actualizado correctamente.",
            "id_usuario": usuario_id,
            "estado_activo": req.EstadoActivo
        }
    except HTTPException:
        raise
    except Exception as err:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(err))
    finally:
        cursor.close()
        conn.close()