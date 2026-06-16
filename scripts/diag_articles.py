"""Diagnostico: que patron de 'articulo' usa cada codigo (para medir cobertura)."""
import sys, re, pathlib, unicodedata
import fitz
sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs data"

pats = {
    "UPPER ARTICULO N": re.compile(r'^ART[IÍ]CULO\s+\d+'),
    "Title Articulo N":  re.compile(r'^Art[ií]culo\s+\d+'),
    "Art. N":            re.compile(r'^Art\.?\s+\d+', re.IGNORECASE),
    "ARTICULO any":      re.compile(r'ART[IÍ]CULO\s+\d+', re.IGNORECASE),
}

for pdf in sorted(PDF_DIR.glob("*.pdf")):
    if "codigo" not in pdf.name.lower() and not pdf.name.lower().startswith("cdigo"):
        continue
    doc = fitz.open(pdf)
    raw = unicodedata.normalize("NFKC", "\n".join(doc[i].get_text() for i in range(doc.page_count)))
    doc.close()
    blocks = [re.sub(r"\s+", " ", b).strip() for b in re.split(r"\n\s*\n", raw)]
    counts = {k: 0 for k in pats}
    for b in blocks:
        for k, rx in pats.items():
            if k == "ARTICULO any":
                counts[k] += len(rx.findall(b))
            elif rx.match(b):
                counts[k] += 1
    print(f"\n{pdf.name}")
    for k, v in counts.items():
        print(f"   {k:<20} {v}")
    # muestra los primeros 3 bloques que contienen 'articulo' pero NO matchean UPPER al inicio
    print("   -- ejemplos no detectados al inicio de bloque:")
    shown = 0
    up = pats["UPPER ARTICULO N"]
    anyrx = re.compile(r'art[ií]culo\s+\d+', re.IGNORECASE)
    for b in blocks:
        if anyrx.search(b) and not up.match(b):
            print(f"      | {b[:110]}")
            shown += 1
            if shown >= 3:
                break
