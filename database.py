import pyodbc

# Conexión directa por IP y puerto estándar
DB_SERVER = "127.0.0.1,1433"
DB_NAME = "AlcaldiaRamiriquiDB"
DB_USER = "sa"
DB_PASSWORD = "jhNLRKEYj_oFpPSAIdE"

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    f"UID={DB_USER};"
    f"PWD={DB_PASSWORD};"
    "TrustServerCertificate=yes;"
)

def get_connection():
    try:
        # timeout=5 evita que se quede colgado si hay problema de red
        conn = pyodbc.connect(CONNECTION_STRING, timeout=5)
        return conn
    except Exception as e:
        print(f"Error al conectar con SQL Server: {e}")
        raise e