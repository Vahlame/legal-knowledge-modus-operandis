"""
Resolución central de rutas de datos (índice, vectores, corpus).

Por defecto resuelve junto al paquete (instalación editable / repo). Se puede
mover con la variable de entorno LEGAL_MEMORY_HOME (útil para empaquetar, para
un índice compartido, o para correr el MCP desde cualquier carpeta).
"""
import os
import pathlib


def home() -> pathlib.Path:
    env = os.environ.get("LEGAL_MEMORY_HOME")
    if env:
        return pathlib.Path(env).expanduser()
    return pathlib.Path(__file__).resolve().parent.parent


HOME = home()
DB = HOME / "legal.db"
VEC = HOME / "legal_vectors.npy"
MD_DIR = HOME / "markdown"
PDF_DIR = HOME / "pdfs data"
