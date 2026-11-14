from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.staticfiles import StaticFiles
from utils.almacenamiento import guardar_archivo

# Importación de routers existentes
from routers import personas, autorizaciones, usuarios, indicadores, trazabilidad, valoracion, consultas, documentos, exportar
from utils.huella_digital import generar_huella_servidor


# Variable global para guardar la identidad del servidor en ejecución
HUELLA_ACTIVA = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- CÓDIGO AL INICIAR EL SERVIDOR (STARTUP) ---
    global HUELLA_ACTIVA
    HUELLA_ACTIVA = generar_huella_servidor()

    print("\n" + "=" * 60)
    print("🔒 HUELLA DIGITAL DEL SERVIDOR GENERADA:")
    print(f"   Llave Única : {HUELLA_ACTIVA['huella_servidor']}")
    print(f"   Entorno     : {HUELLA_ACTIVA['sistema']} ({HUELLA_ACTIVA['nodo']})")
    print("=" * 60 + "\n")

    yield  # Aquí la aplicación permanece corriendo y atendiendo peticiones

    # --- CÓDIGO AL APAGAR EL SERVIDOR (SHUTDOWN) ---
    print("\n🛑 Apagando servidor de Alcaldía de Ramiriquí...")


# Instancia de FastAPI con lifespan configurado
app = FastAPI(
    title="Alcaldia Ramiriqui API",
    description="API REST modular para gestión de salud y fichas médicas",
    version="1.0.0",
    lifespan=lifespan

)


# Configuración de CORS
origins = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,        # Permite peticiones desde Angular
    allow_credentials=True,
    allow_methods=["*"],          # Permite OPTIONS, POST, GET, PUT, etc.
    allow_headers=["*"],          # Permite Content-Type y demás headers
)


# REGISTRO CENTRAL DE TODOS LOS ROUTERS / ENDPOINTS

# Registro central de todos los routers
app.include_router(personas.router)
app.include_router(autorizaciones.router)
app.include_router(usuarios.router)
app.include_router(indicadores.router)
app.include_router(trazabilidad.router)
app.include_router(valoracion.router)
app.include_router(consultas.router)
app.include_router(valoracion.router)
app.include_router(documentos.router)
app.include_router(exportar.router)

@app.get("/")
def ruta_raiz():
    return {"mensaje": "API Alcaldía de Ramiriquí en funcionamiento"}

@app.get("/sistema/huella", tags=["Sistema"])
def consultar_huella_servidor():
    """Permite verificar la llave asignada al entorno actual."""
    return HUELLA_ACTIVA

# ==========================================================
# SERVICIO DE ARCHIVOS ESTÁTICOS (FOTOS Y PDFs)
# ==========================================================
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")


# Endpoint para subir foto (Cámara o Explorador de archivos - Puntos #3 y #4)
@app.post("/archivos/subir-foto", tags=["Archivos"])
async def subir_foto_persona(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Formato inválido. Debes subir una imagen (JPG, PNG, WEBP)."
        )
    url_foto = await guardar_archivo(file, subcarpeta="fotos")
    return {"url": url_foto}


# Endpoint para subir PDF o documento soporte (Punto #5)
@app.post("/archivos/subir-documento", tags=["Archivos"])
async def subir_documento_pdf(file: UploadFile = File(...)):
    tipos_permitidos = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in tipos_permitidos:
        raise HTTPException(
            status_code=400,
            detail="Formato inválido. Solo se permiten archivos PDF o imágenes."
        )
    url_doc = await guardar_archivo(file, subcarpeta="documentos")
    return {"url": url_doc}