"""
Convierte los PDFs legales (CR) a Markdown estructurado y FIEL al original.

Modos:
  - codigo : detecta encabezados de artículo -> `## Artículo N` (unidad de recuperación).
  - temario: preserva TODO el contenido en orden (título como encabezado).
  - generic: reflow a párrafos (examen).

FIDELIDAD (texto legal, "hasta las comas importan"):
  - NO se usa NFKC: alteraría ordinales (º->o, Nº->No). Se preserva el carácter original.
  - Solo se deshacen ligaduras tipográficas (ﬁ->fi), que es corrección real de render.
  - Palabras, puntuación, acentos y ortografía original se preservan intactos.
  - Solo se quita ruido NO legal: marcador "Ficha articulo" y pies de impresión.

Salida: markdown/<nombre>.md con frontmatter YAML.
"""
import sys, re, pathlib, datetime
import fitz  # PyMuPDF

sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs data"
OUT_DIR = ROOT / "markdown"
TODAY = datetime.date.today().isoformat()

# Ligaduras tipográficas -> letras (corrección de render, no alteración de contenido).
_LIG = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}


def delig(t):
    for k, v in _LIG.items():
        t = t.replace(k, v)
    return t


def reflow(block):
    return re.sub(r"\s+", " ", block).strip()


_ART_CORE = r'Art[ií]culo\s+(\d+|[ÚU]NICO)\s*(BIS|TER)?\s*[ºo°ªa]?\s*[.\-]+\s*'
ART_HEAD = re.compile(r'^' + _ART_CORE, re.IGNORECASE)
SPLIT_HEAD = re.compile(r'(?:Ficha\s+articulo\s+)?(' + _ART_CORE + r')', re.IGNORECASE)
STRUCT_RE = re.compile(
    r'^(LIBRO|T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N|DISPOSICIONES|PARTE)\b', re.IGNORECASE)
PAGENUM_RE = re.compile(r'^\d{1,4}(\s+de\s+\d{1,4})?$', re.IGNORECASE)


def read_pages(path):
    doc = fitz.open(path)
    pages = [delig(doc[i].get_text()) for i in range(doc.page_count)]
    n = doc.page_count
    doc.close()
    return pages, n


def strip_footers(raw):
    """Quita pies de impresión pgrweb y URLs sueltas (ruido por página, no legal)."""
    raw = re.sub(r'\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*Texto Completo.*?\.html\s*\d+\s*/\s*\d+',
                 ' ', raw, flags=re.S | re.I)
    raw = re.sub(r'https?://\S+|www\.\S+', ' ', raw)
    raw = re.sub(r'\bTexto Completo acta:\s*\w+', ' ', raw, flags=re.I)
    return raw


def is_noise(b):
    return (not b) or bool(PAGENUM_RE.match(b))


def art_label(num, suf):
    label = num if num[0].isdigit() else num.capitalize()
    return f"{label} {suf.lower()}" if suf else label


def convert_codigo(pages):
    raw = strip_footers("\n".join(pages))
    raw = re.sub(r'Ficha\s+articulo', '\n\n', raw, flags=re.IGNORECASE)   # ruido -> separador
    raw = SPLIT_HEAD.sub(lambda m: "\n\n" + m.group(1), raw)              # rompe artículos pegados
    blocks = [reflow(p) for p in re.split(r"\n\s*\n", raw)]
    lines, n_art = [], 0
    for b in blocks:
        if is_noise(b):
            continue
        m = ART_HEAD.match(b)
        if m:
            n_art += 1
            body = b[m.end():].strip()
            lines.append(f"\n## Artículo {art_label(m.group(1), m.group(2))}\n")
            if body:
                lines.append(body)
            continue
        if STRUCT_RE.match(b) and len(b) < 90:
            lines.append(f"\n### {b}\n")
            continue
        lines.append(b)
    return "\n\n".join(lines).strip(), n_art


def convert_temario(pages):
    """Verbatim: conserva todo el contenido en orden; solo descarta líneas vacías
    y números de página puros (no legales)."""
    out, titled = [], False
    for ln in delig("\n".join(pages)).splitlines():
        s = ln.strip()
        if not s or re.fullmatch(r"\d{1,4}\s+de\s+\d{1,4}", s):  # solo paginación "N de M"
            continue
        if not titled and "temario" in s.lower():
            out.append(f"# {s}")
            titled = True
        else:
            out.append(s)
    return "\n\n".join(out), 0


def convert_generic(pages):
    raw = strip_footers("\n".join(pages))
    blocks = [reflow(p) for p in re.split(r"\n\s*\n", raw)]
    return "\n\n".join(b for b in blocks if not is_noise(b)).strip(), 0


def doc_kind(name):
    low = name.lower()
    if low.startswith("temario"):
        return "temario"
    if low.startswith("cdigo") or "codigo" in low:
        return "codigo"
    return "examen" if "examen" in low else "generic"


def slug(name):
    s = name.lower().replace("cdigo", "codigo")
    for a, b in [("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")]:
        s = s.replace(a, b)
    s = re.sub(r"\(.*?\)", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    rows = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        pages, npg = read_pages(pdf)
        kind = doc_kind(pdf.name)
        body, n_art = {"codigo": convert_codigo, "temario": convert_temario}.get(
            kind, convert_generic)(pages)
        fm = ("---\ntype: reference\n"
              f"doc_kind: {kind}\n"
              f'source: "{pdf.name}"\n'
              "jurisdiction: Costa Rica\n"
              f"converted: {TODAY}\npages: {npg}\narticles: {n_art}\n---\n\n")
        (OUT_DIR / f"{slug(pdf.stem)}.md").write_text(fm + body + "\n", encoding="utf-8")
        rows.append((pdf.name, npg, n_art, len(body), round(len(body) / 4)))

    print(f"{'ARCHIVO':<46}{'PAG':>5}{'ART':>6}{'CHARS':>9}{'~TOK':>9}")
    print("-" * 75)
    tc = tt = 0
    for name, npg, na, ch, tok in rows:
        print(f"{name[:46]:<46}{npg:>5}{na:>6}{ch:>9}{tok:>9}")
        tc += ch; tt += tok
    print("-" * 75)
    print(f"{'TOTAL':<46}{'':>5}{'':>6}{tc:>9}{tt:>9}")


if __name__ == "__main__":
    main()
