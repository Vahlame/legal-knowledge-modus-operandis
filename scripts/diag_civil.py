"""Inspecciona los bytes exactos alrededor de la divergencia 'minado el usufructo'."""
import sys, pathlib, fitz
sys.stdout.reconfigure(encoding="utf-8")

root = pathlib.Path(__file__).resolve().parent.parent
doc = fitz.open(root / "pdfs data" / "Cdigo Civil 2026.pdf")
src = "\n".join(doc[i].get_text() for i in range(doc.page_count))
doc.close()
md = (root / "markdown" / "codigo-civil-2026.md").read_text(encoding="utf-8")

for label, t in [("SRC (PDF)", src), ("MD", md)]:
    i = t.lower().find("frutos de un fundo")
    print(f"--- {label}  (idx={i}) ---")
    print(repr(t[i - 95:i + 25]))
    print()
