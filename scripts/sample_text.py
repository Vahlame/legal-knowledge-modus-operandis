"""Muestra texto crudo de unas paginas para disenar el troceo por articulo."""
import sys, pathlib, fitz
sys.stdout.reconfigure(encoding="utf-8")

root = pathlib.Path(__file__).resolve().parent.parent
pdf_dir = root / "pdfs data"

def dump(name, pages):
    doc = fitz.open(pdf_dir / name)
    print("=" * 90)
    print(name)
    print("=" * 90)
    for p in pages:
        if p < doc.page_count:
            print(f"\n----- pagina {p} -----")
            print(doc[p].get_text()[:1400])
    doc.close()

# Codigo Civil: saltar portada/indice, ver cuerpo
dump("Cdigo Civil 2026.pdf", [5, 6, 40])
# Un temario (estructura distinta)
dump("Temario-Derecho-Civil-2025.pdf", [0, 1])
