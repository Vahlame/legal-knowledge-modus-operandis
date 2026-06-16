"""
Grafo de concordancias entre artículos (para "artículos relacionados que ayudan
al caso").

Tres tipos de relación:
  - cites     : artículos que el artículo X menciona en su texto (mismo código).
  - cited_by  : artículos que mencionan a X (concordancia inversa).
  - neighbors : artículos en la misma unidad estructural (Capítulo/Sección) = misma
                materia jurídica.

CORRECTITUD (un enlace falso es peor que ninguno): solo se enlazan referencias
INTERNAS. Una referencia "artículo 5 DE LA LEY N° 7020" / "de la Constitución" /
"del Código Penal" apunta a otra norma -> se descarta. Además, solo se enlaza a
números de artículo que EXISTEN en ese código.
"""
import re
import sqlite3
import pathlib

DB = pathlib.Path(__file__).resolve().parent.parent / "legal.db"

# "artículo(s) N", "artículos 5, 6 y 7", "artículos 5 a 9", "artículo 408 bis"
REF_HEAD = re.compile(
    r"art[ií]culos?\b[\s:]*"
    r"(\d{1,4}(?:\s*(?:bis|ter))?(?:(?:[\s,ye]+|\s+a\s+)\d{1,4}(?:\s*(?:bis|ter))?)*)",
    re.I,
)
# Inmediatamente después de los números: marca de OTRA norma -> referencia externa.
EXTERNAL = re.compile(
    r"^\s*(?:de\s+la\s+(?:ley|constituci|convenci)|de\s+los?\s+c[oó]digos?|del\s+c[oó]digo)",
    re.I,
)
NUM = re.compile(r"\d{1,4}")


def refs_in(text: str):
    """Conjunto de números de artículo (mismo código) citados en el texto."""
    out = set()
    for m in REF_HEAD.finditer(text):
        if EXTERNAL.match(text[m.end():m.end() + 20]):
            continue
        out.update(NUM.findall(m.group(1)))
    return out


def _key(a):
    m = re.match(r"\d+", a)
    return (int(m.group()) if m else 9999, a)


def build_into(con, chunks):
    """Crea la tabla refs(slug, src, dst) con solo enlaces internos válidos."""
    valid = {}
    for c in chunks:
        if c["article"]:
            valid.setdefault(c["slug"], set()).add(c["article"])
    edges = []
    for c in chunks:
        if c["kind"] == "codigo" and c["article"]:
            vset = valid.get(c["slug"], set())
            for dst in refs_in(c["text"]):
                if dst != c["article"] and dst in vset:
                    edges.append((c["slug"], c["article"], dst))
    con.execute("CREATE TABLE refs(slug TEXT, src TEXT, dst TEXT)")
    con.executemany("INSERT INTO refs VALUES(?,?,?)", edges)
    con.execute("CREATE INDEX idx_refs_src ON refs(slug, src)")
    con.execute("CREATE INDEX idx_refs_dst ON refs(slug, dst)")
    return len(edges)


def related(slug: str, art: str):
    con = sqlite3.connect(DB)
    cites = [r[0] for r in con.execute(
        "SELECT DISTINCT dst FROM refs WHERE slug=? AND src=?", (slug, art))]
    cited_by = [r[0] for r in con.execute(
        "SELECT DISTINCT src FROM refs WHERE slug=? AND dst=?", (slug, art))]
    row = con.execute(
        "SELECT section FROM chunks WHERE slug=? AND article=? LIMIT 1", (slug, art)).fetchone()
    neighbors = []
    if row and row[0]:
        neighbors = [r[0] for r in con.execute(
            "SELECT DISTINCT article FROM chunks WHERE section=? "
            "AND article IS NOT NULL AND article != ?", (row[0], art))]
    con.close()
    return {"cites": sorted(cites, key=_key),
            "cited_by": sorted(cited_by, key=_key),
            "neighbors": sorted(set(neighbors), key=_key)}


def _citation(con, slug, art):
    row = con.execute(
        "SELECT citation FROM chunks WHERE slug=? AND article=? LIMIT 1", (slug, art)).fetchone()
    return row[0] if row else f"{slug} art. {art}"


def main():
    import argparse, sys
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Concordancias de un artículo")
    ap.add_argument("--art", required=True)
    ap.add_argument("--code", required=True, help="slug del código, p.ej. codigo-civil-2026")
    a = ap.parse_args()
    rel = related(a.code, a.art)
    con = sqlite3.connect(DB)
    print(f"Concordancias de {_citation(con, a.code, a.art)}:")
    print(f"  cita a        : {', '.join(rel['cites']) or '—'}")
    print(f"  citado por    : {', '.join(rel['cited_by']) or '—'}")
    n = rel["neighbors"]
    print(f"  misma materia : {', '.join(n[:25])}{' …' if len(n) > 25 else ''}  ({len(n)} arts.)")
    con.close()


if __name__ == "__main__":
    main()
