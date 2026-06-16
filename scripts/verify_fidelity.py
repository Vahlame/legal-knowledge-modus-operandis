"""
Auditoría de fidelidad ROBUSTA: prueba que el Markdown no pierde ni altera contenido.

Método independiente del marcador de artículo (evita falsos positivos por el borde
encabezado/cuerpo):

  1. PALABRAS: multiconjunto de tokens \\w+ (acento-plegado) de PDF vs MD. Si son
     idénticos, ninguna palabra se perdió, duplicó ni alteró. Se neutralizan solo
     diferencias no sustantivas: ligaduras (ﬁ->fi), ruido "Ficha articulo", pies de
     impresión. El reformateo del marcador (ARTÍCULO->## Artículo) no afecta: misma
     palabra "artículo" + mismo número en ambos lados.

  2. PUNTUACIÓN DE CUERPO: censo de , ; : ( ) ¿ ? ¡ ! « » que NO forman parte del
     marcador. La COMA es el invariante crítico ("hasta las comas importan"): debe
     cuadrar exacto. (El punto y el guion del marcador ".-" sí bajan ~#artículos; eso
     es reformateo, no pérdida, y se informa aparte.)
"""
import sys, re, pathlib
from collections import Counter
import fitz
sys.stdout.reconfigure(encoding="utf-8")

ROOT = pathlib.Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdfs data"
MD_DIR = ROOT / "markdown"

LIG = {"ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"}
WORD = re.compile(r"\w+", re.UNICODE)
BODY_PUNCT = ",;:()¿?¡!«»"


def clean(s):
    for k, v in LIG.items():
        s = s.replace(k, v)
    s = re.sub(r"(?i)ficha\s+articulo", " ", s)
    s = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}:\d{2}\s*Texto Completo.*?\.html\s*\d+\s*/\s*\d+",
               " ", s, flags=re.S | re.I)
    s = re.sub(r"https?://\S+|www\.\S+", " ", s)
    s = re.sub(r"\bTexto Completo acta:\s*\w+", " ", s, flags=re.I)
    s = re.sub(r"\b\d{1,4}\s+de\s+\d{1,4}\b", " ", s)   # paginación "N de M" (no legal)
    s = s.replace("º", " ").replace("ª", " ")            # marca de ordinal (2º -> 2), simétrico
    return s


def words(s):
    toks = WORD.findall(clean(s).casefold())
    toks = ["articulo" if t == "artículo" else t for t in toks]  # rótulo: acento del encabezado
    return Counter(toks)


def commas(s):
    return clean(s).count(",")


def body_punct(s):
    c = clean(s)
    return Counter(ch for ch in c if ch in BODY_PUNCT)


def slug(stem):
    s = stem.lower().replace("cdigo", "codigo")
    for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u")]:
        s = s.replace(a, b)
    s = re.sub(r"\(.*?\)", "", s)
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def md_body(text):
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return text[m.end():] if m else text


def main():
    print(f"{'ARCHIVO':<42}{'PALABRAS':>10}{'COMAS src=md':>16}{'PUNT.CUERPO':>13}")
    print("-" * 81)
    all_ok = True
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        doc = fitz.open(pdf)
        src = "\n".join(doc[i].get_text() for i in range(doc.page_count))
        doc.close()
        md = md_body((MD_DIR / f"{slug(pdf.stem)}.md").read_text(encoding="utf-8"))

        ws, wm = words(src), words(md)
        lost, added = ws - wm, wm - ws
        word_ok = not lost and not added
        cs, cm = commas(src), commas(md)
        comma_ok = cs == cm
        bp_ok = body_punct(src) == body_punct(md)
        all_ok &= word_ok and comma_ok and bp_ok

        wv = "OK ✓" if word_ok else f"DIFF -{sum(lost.values())}/+{sum(added.values())}"
        cv = f"{cs}={cm} ✓" if comma_ok else f"{cs}≠{cm} ✗"
        pv = "OK ✓" if bp_ok else "DIFF ✗"
        print(f"{pdf.name[:42]:<42}{wv:>10}{cv:>16}{pv:>13}")
        if not word_ok:
            if lost:
                print(f"    solo en PDF: {dict(lost.most_common(8))}")
            if added:
                print(f"    solo en MD : {dict(added.most_common(8))}")
        if not bp_ok:
            d = body_punct(src); e = body_punct(md)
            print(f"    PDF: {dict(d)}\n    MD : {dict(e)}")
    print("-" * 81)
    print("RESULTADO:", "FIDELIDAD TOTAL ✓ (cero pérdida de palabras y comas)" if all_ok
          else "REVISAR diferencias arriba")


if __name__ == "__main__":
    main()
