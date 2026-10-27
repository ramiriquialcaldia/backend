from fastapi import FastAPI
from routers import personas, autorizaciones, usuarios, indicadores, trazabilidad, valoracion, consultas
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "http://localhost:4200",
    "http://127.0.0.1:4200",
]

app = FastAPI(
    title="Alcaldia Ramiriqui API",
    description="API REST modular para la gestión de salud y fichas médicas",
    version="1.0.0"
)

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

# Ruta base de bienvenida o estado
@app.get("/")
def ruta_raiz():
    return {"mensaje": "API Alcaldía de Ramiriquí en funcionamiento"}