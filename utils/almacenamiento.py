import os
import uuid
from fastapi import UploadFile

AZURE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "").strip()

UPLOAD_LOCAL_DIR = "uploads"
os.makedirs(os.path.join(UPLOAD_LOCAL_DIR, "fotos"), exist_ok=True)
os.makedirs(os.path.join(UPLOAD_LOCAL_DIR, "documentos"), exist_ok=True)


async def guardar_archivo(file: UploadFile, subcarpeta: str = "fotos") -> str:
    nombre_original = file.filename or "archivo"
    extension = os.path.splitext(nombre_original)[1].lower()
    if not extension:
        extension = ".jpg" if subcarpeta == "fotos" else ".pdf"

    nombre_unico = f"{uuid.uuid4().hex}{extension}"
    contenido = await file.read()

    if AZURE_CONNECTION_STRING:
        from azure.storage.blob import BlobServiceClient, ContentSettings

        blob_service = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        contenedor_nombre = f"alcaldia-{subcarpeta}"
        contenedor_client = blob_service.get_container_client(contenedor_nombre)

        if not contenedor_client.exists():
            contenedor_client.create_container(public_access="blob")

        blob_client = contenedor_client.get_blob_client(nombre_unico)
        blob_client.upload_blob(
            contenido,
            overwrite=True,
            content_settings=ContentSettings(content_type=file.content_type)
        )
        return blob_client.url

    ruta_carpeta = os.path.join(UPLOAD_LOCAL_DIR, subcarpeta)
    os.makedirs(ruta_carpeta, exist_ok=True)
    ruta_archivo = os.path.join(ruta_carpeta, nombre_unico)

    with open(ruta_archivo, "wb") as f:
        f.write(contenido)

    return f"http://127.0.0.1:8000/uploads/{subcarpeta}/{nombre_unico}"