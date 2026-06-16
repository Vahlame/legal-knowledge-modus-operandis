"""
Búsqueda híbrida sobre el índice legal: BM25 (léxico) + semántico (tf-idf), fusión
RRF, con N ADAPTATIVO (sin tope fijo: devuelve todos los artículos relevantes por
encima de un umbral relativo). Cada resultado cita el artículo y el código.

Ejemplos:
  python -m legal_rag.search puede el inquilino subarrendar
  python -m legal_rag.search prescripcion adquisitiva --code codigo-civil-2026
  python -m legal_rag.search --art 1045 --code codigo-civil-2026
  python -m legal_rag.search homicidio culposo --lexical
"""
import sqlite3
import re
import sys
import json
import argparse
import pathlib
from collections import defaultdict

from legal_rag import embed

DB = pathlib.Path(__file__).resolve().parent.parent / "legal.db"
VEC_PATH = pathlib.Path(__file__).resolve().parent.parent / "legal_vectors.npy"
_NEURAL_VEC = None  # caché de la matriz densa (se carga una vez)


def _fts_match(q: str) -> str:
    toks = re.findall(r"\w+", q, re.UNICODE)
    return " OR ".join(f'"{t}"' for t in toks)


def _bm25_rank(con, query, pool, code):
    sql = "SELECT rowid FROM chunks WHERE chunks MATCH ?"
    args = [_fts_match(query)]
    if code:
        sql += " AND slug = ?"
        args.append(code)
    sql += " ORDER BY rank LIMIT ?"
    args.append(pool)
    return [r[0] for r in con.execute(sql, args).fetchall()]


def _embedder(con):
    row = con.execute("SELECT v FROM seminfo WHERE k='embedder'").fetchone()
    return row[0] if row else "stdlib"


def _semantic_neural(query, pool):
    import numpy as np
    global _NEURAL_VEC
    if _NEURAL_VEC is None:
        _NEURAL_VEC = np.load(VEC_PATH)
    q = embed.neural_encode([query], kind="query")[0]   # (dim,) normalizado
    scores = _NEURAL_VEC @ q                      # coseno vs todos los chunks
    return [int(i) + 1 for i in np.argsort(-scores)[:pool]]   # rowid = i+1


def _semantic_stdlib(con, query, pool):
    ct = embed.counter(query)
    dims = list({embed.h(f) for f in ct})
    if not dims:
        return []
    ph = ",".join("?" * len(dims))
    idf = dict(con.execute(f"SELECT dim, v FROM semidf WHERE dim IN ({ph})", dims).fetchall())
    qvec = embed.vector(ct, idf)
    if not qvec:
        return []
    qd = list(qvec)
    ph2 = ",".join("?" * len(qd))
    scores = defaultdict(float)
    for d, data in con.execute(f"SELECT dim, data FROM sempost WHERE dim IN ({ph2})", qd).fetchall():
        qw = qvec[d]
        for rid, cw in json.loads(data):
            scores[rid] += qw * cw
    return [rid for rid, _ in sorted(scores.items(), key=lambda x: -x[1])[:pool]]


def _semantic_rank(con, query, pool):
    if _embedder(con).startswith("neural"):
        return _semantic_neural(query, pool)
    return _semantic_stdlib(con, query, pool)


def hybrid(query, code=None, pool=120, k=60, ratio=0.30, cap=40):
    """RRF(BM25, semántico) + corte adaptativo (>= ratio*top, máx cap)."""
    con = sqlite3.connect(DB)
    rrf = defaultdict(float)
    for pos, rid in enumerate(_bm25_rank(con, query, pool, code)):
        rrf[rid] += 1.0 / (k + pos + 1)
    for pos, rid in enumerate(_semantic_rank(con, query, pool)):
        rrf[rid] += 1.0 / (k + pos + 1)
    if not rrf:
        con.close()
        return []
    fused = sorted(rrf.items(), key=lambda x: -x[1])
    top = fused[0][1]
    out = []
    for rid, s in fused[:cap]:
        if s < ratio * top:
            break
        row = con.execute(
            "SELECT slug, article, citation, structure, kind, text FROM chunks WHERE rowid = ?", (rid,)
        ).fetchone()
        if not row:
            continue
        slug, article, cite, struct, kind, text = row
        if code and slug != code:
            continue
        out.append({"rowid": rid, "score": round(s, 5), "slug": slug, "article": article,
                    "citation": cite, "structure": struct, "kind": kind, "text": text})
    con.close()
    return out


def lexical(query, k=5, code=None):
    con = sqlite3.connect(DB)
    sql = ("SELECT citation, structure, kind, snippet(chunks, 7, '«', '»', ' … ', 16), rank "
           "FROM chunks WHERE chunks MATCH ?")
    args = [_fts_match(query)]
    if code:
        sql += " AND slug = ?"
        args.append(code)
    sql += " ORDER BY rank LIMIT ?"
    args.append(k)
    rows = con.execute(sql, args).fetchall()
    con.close()
    return rows


def get_article(num, code=None):
    con = sqlite3.connect(DB)
    sql = "SELECT citation, structure, text FROM chunks WHERE article = ?"
    args = [str(num)]
    if code:
        sql += " AND slug = ?"
        args.append(code)
    rows = con.execute(sql, args).fetchall()
    con.close()
    return rows


def _excerpt(text, n=240):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[:n] + " …"


def main():
    ap = argparse.ArgumentParser(description="Búsqueda en la memoria legal CR (híbrida)")
    ap.add_argument("query", nargs="*", help="texto a buscar")
    ap.add_argument("--art", help="traer artículo exacto, p.ej. --art 1045")
    ap.add_argument("--code", help="filtrar por código (slug)")
    ap.add_argument("--lexical", action="store_true", help="solo BM25 (sin semántica)")
    ap.add_argument("-k", type=int, default=5, help="resultados en modo --lexical")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if a.art:
        rows = get_article(a.art, a.code)
        for cite, struct, text in rows or []:
            print(f"\n### {cite}" + (f"  ·  {struct}" if struct else ""))
            print(text)
        if not rows:
            print("(sin resultados)")
        return

    q = " ".join(a.query)
    if a.lexical:
        rows = lexical(q, a.k, a.code)
        for cite, struct, kind, snip, _ in rows or []:
            print(f"\n[{kind}] {cite}" + (f"  ·  {struct}" if struct else ""))
            print(f"   {snip}")
        if not rows:
            print("(sin resultados)")
        return

    res = hybrid(q, a.code)
    print(f"{len(res)} artículos relevantes (N adaptativo):")
    for r in res:
        loc = f"  ·  {r['structure']}" if r["structure"] else ""
        print(f"\n[{r['score']}] {r['citation']}{loc}")
        print(f"   {_excerpt(r['text'])}")
    if not res:
        print("(sin resultados)")


if __name__ == "__main__":
    main()
