"""Sonda rapida: reporta si cada PDF tiene capa de texto (digital) o no (escaneado)."""
import sys, pathlib
import fitz  # PyMuPDF

root = pathlib.Path(__file__).resolve().parent.parent
pdf_dir = root / "pdfs data"

print(f"{'ARCHIVO':<48} {'PAGS':>5} {'CHARS/PAG':>10}  TIPO")
print("-" * 80)
for pdf in sorted(pdf_dir.glob("*.pdf")):
    doc = fitz.open(pdf)
    n = doc.page_count
    sample = min(n, 5)
    chars = sum(len(doc[i].get_text()) for i in range(sample))
    per_page = chars / sample if sample else 0
    tipo = "DIGITAL (texto)" if per_page > 200 else "ESCANEADO? (OCR)"
    print(f"{pdf.name[:48]:<48} {n:>5} {per_page:>10.0f}  {tipo}")
    doc.close()
