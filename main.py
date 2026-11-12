from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Importación de routers existentes
from routers import personas, autorizaciones, usuarios, indicadores, trazabilidad, valoracion, consultas
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

@app.get("/")
def ruta_raiz():
    return {"mensaje": "API Alcaldía de Ramiriquí en funcionamiento"}

@app.get("/sistema/huella", tags=["Sistema"])
def consultar_huella_servidor():
    """Permite verificar la llave asignada al entorno actual."""
    return HUELLA_ACTIVA