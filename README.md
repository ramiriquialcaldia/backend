# Configuración de Base de Datos Local (SQL Server)
DB_SERVER=localhost
DB_PORT=1433
DB_NAME=AlcaldiaRamiriquiDB
DB_USER=backend_user
DB_PASSWORD=    jhNLRKEYj_oFpPSAiDE

Instalación de dependencias (en caso de desplegar en otro entorno):
pip install fastapi uvicorn pyodbc pydantic
pip install bcrypt
pip install python-multipart azure-storage-blob

Ejecutar el servidor en modo desarrollo:
uvicorn main:app --reload

# 🏛️ Backend - Alcaldía de Ramiriquí (Salud)

API REST desarrollada con **FastAPI** y conectada a **Microsoft SQL Server** para la gestión y registro de historias, fichas médicas y datos sociodemográficos de la comunidad.

---

## 🛠️ Tecnologías y Librerías Instaladas

### 1. Entorno y Lenguaje
- **Python 3.13 (64-bit)**: Entorno base de ejecución del backend.

### 2. Paquetes de Python (`pip`)
- **`fastapi`**: Framework web para estructurar la API REST, gestionar endpoints y documentación OpenAPI.
- **`uvicorn[standard]`**: Servidor web ASGI para levantar y ejecutar la aplicación en tiempo real (`--reload`).
- **`pydantic`**: Validación y control de esquemas de datos entrantes (`PersonaCreate`, `AutorizacionCreate`).
- **`pyodbc`**: Conector ODBC de Python para ejecutar consultas y transacciones directas en SQL Server.

### 3. Software y Componentes del Sistema
- **Microsoft ODBC Driver 17 for SQL Server**: Controlador oficial para la comunicación entre Windows/Python y SQL Server.
- **Microsoft SQL Server Express (`SQLEXPRESS`)**: Motor de base de datos relacional (Base de datos: `AlcaldiaRamiriquiDB`).
- **DBeaver Community**: Administrador visual de base de datos para diseño de esquemas y ejecución de scripts SQL.
- **Postman**: Cliente HTTP para pruebas de consumo de endpoints (`GET` y `POST`).

---

## ⚙️ Configuración del Entorno y Base de Datos

1. **Autenticación Mixta en SQL Server:**
   - Se habilitó la autenticación mixta (Modo SQL Server y Windows, `LoginMode = 2`).
   - Se activó y desbloqueó el usuario administrador `sa`.

2. **Servicios de Windows:**
   - **SQL Server Browser:** Configurado en tipo de inicio *Automático* y *En ejecución*.
   - **SQL Server (SQLEXPRESS):** En ejecución y reiniciado para aplicar el modo mixto.

3. **Conexión (`database.py`):**
   - Host / Puerto: `127.0.0.1,1433`
   - Driver: `ODBC Driver 17 for SQL Server`
   - Base de datos: `AlcaldiaRamiriquiDB`
   - Parámetros de seguridad: `TrustServerCertificate=yes`

---

## 📁 Estructura del Backend

```text
backend/
├── database.py       # Configuración y conexión a SQL Server vía pyodbc
├── main.py           # Modelos Pydantic y controladores (endpoints)
├── requirements.txt  # Lista de dependencias del proyecto
└── README.md         # Documentación general del proyecto


