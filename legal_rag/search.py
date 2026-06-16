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

from legal_rag.paths import DB, VEC as VEC_PATH
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


def _pack(row, score):
    slug, article, cite, struct, doc_type, rama, text, name, vigente = row
    return {"score": round(float(score), 4), "slug": slug, "article": article, "citation": cite,
            "structure": struct, "doc_type": doc_type, "rama": rama, "name": name,
            "vigente": bool(vigente), "text": text}


def _focus(query, text, head=900, win=900):
    """Para artículos largos (el reranker trunca ~512 tokens): envía la cabeza + la
    ventana de texto con más solapamiento con la consulta, para no juzgarlo solo por
    su inicio. Los cortos pasan completos."""
    if len(text) <= head + win:
        return text
    qtok = {t for t in re.findall(r"\w+", embed.fold(query)) if len(t) > 2}
    folded = embed.fold(text)
    best_i, best = head, -1
    for i in range(head, len(text) - win + 1, 250):
        s = sum(1 for t in qtok if t in folded[i:i + win])
        if s > best:
            best, best_i = s, i
    return text[:head] + " … " + text[best_i:best_i + win]


def hybrid(query, code=None, pool=200, k=60, cap=25, margin=2.0,
           types=("ley", "jurisprudencia"), include_derogadas=False, rerank=True):
    """Recuperación de máxima calidad para RESPUESTA legal (solo artículos de código;
    los temarios van por su stream de estudio aparte):
       1) candidatos = RRF(BM25, semántico)  -> recall
       2) RERANK cross-encoder (pregunta+artículo juntos) -> precisión
       3) corte ADAPTATIVO por margen de score respecto al top (sin tope fijo).
    Si no hay reranker, cae al orden RRF con corte por ratio."""
    con = sqlite3.connect(DB)
    rrf = defaultdict(float)
    for pos, rid in enumerate(_bm25_rank(con, query, pool, code)):
        rrf[rid] += 1.0 / (k + pos + 1)
    for pos, rid in enumerate(_semantic_rank(con, query, pool)):
        rrf[rid] += 1.0 / (k + pos + 1)
    if not rrf:
        con.close()
        return []

    cand = [rid for rid, _ in sorted(rrf.items(), key=lambda x: -x[1])[:pool]]
    rows = {}
    for rid in cand:
        r = con.execute(
            "SELECT slug, article, citation, structure, doc_type, rama, text, name, vigente "
            "FROM chunks WHERE rowid=?", (rid,)).fetchone()
        if r and (types is None or r[4] in types) and not (code and r[0] != code) \
                and (include_derogadas or r[8] == 1):
            rows[rid] = r
    con.close()
    cand = [rid for rid in cand if rid in rows]
    if not cand:
        return []

    if rerank and embed.reranker_enabled():
        sc = embed.rerank_scores(query, [_focus(query, rows[rid][6]) for rid in cand])
        order = sorted(zip(cand, sc), key=lambda x: -x[1])
        top = order[0][1]
        kept = [(rid, s) for rid, s in order if s >= top - margin] or order[:3]
        return [_pack(rows[rid], s) for rid, s in kept[:cap]]

    # fallback sin reranker: orden RRF con corte por ratio del top
    order = sorted(((rid, s) for rid, s in rrf.items() if rid in rows), key=lambda x: -x[1])
    top = order[0][1]
    return [_pack(rows[rid], s) for rid, s in order if s >= 0.30 * top][:cap]


def lexical(query, k=5, code=None):
    con = sqlite3.connect(DB)
    sql = ("SELECT citation, structure, doc_type, snippet(chunks, 7, '«', '»', ' … ', 16), rank "
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
    sql = "SELECT citation, structure, text, vigente, reformas FROM chunks WHERE article = ?"
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
        for cite, struct, text, vig, reformas in rows or []:
            flag = "" if vig else "   ⚠ DEROGADO — NO es ley vigente"
            print(f"\n### {cite}{flag}" + (f"  ·  {struct}" if struct else ""))
            print(text)
            if reformas:
                print(f"   ↳ historia legislativa: {reformas}")
        if not rows:
            print("(sin resultados)")
        return

    q = " ".join(a.query)
    if a.lexical:
        rows = lexical(q, a.k, a.code)
        for cite, struct, doc_type, snip, _ in rows or []:
            print(f"\n[{doc_type}] {cite}" + (f"  ·  {struct}" if struct else ""))
            print(f"   {snip}")
        if not rows:
            print("(sin resultados)")
        return

    res = hybrid(q, a.code)
    print(f"{len(res)} artículos de LEY relevantes (N adaptativo):")
    for r in res:
        loc = f"  ·  {r['structure']}" if r["structure"] else ""
        print(f"\n[{r['rama']}] {r['citation']}{loc}")
        print(f"   {_excerpt(r['text'])}")
    if not res:
        print("(sin resultados)")


if __name__ == "__main__":
    main()
