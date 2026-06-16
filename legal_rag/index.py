"""
Construye el índice híbrido sobre los chunks legales:
  - FTS5 BM25 (léxico, término exacto)
  - Semántico: NEURONAL (fastembed, recomendado) o stdlib tf-idf (fallback sin deps)
  - Grafo de concordancias (F4)

El backend semántico se elige solo: neuronal si fastembed está instalado, si no stdlib.
Forzar con  LEGAL_EMBEDDER=stdlib|neural.   Ejecutar:  python -m legal_rag.index
"""
import sqlite3
import pathlib
import math
import json
from collections import defaultdict, Counter

from legal_rag.chunker import chunk_file
from legal_rag import embed, graph

ROOT = pathlib.Path(__file__).resolve().parent.parent
MD_DIR = ROOT / "markdown"
DB = ROOT / "legal.db"
VEC_PATH = ROOT / "legal_vectors.npy"


def _build_semantic(con, chunks):
    """Crea las estructuras semánticas; devuelve (etiqueta_embedder, descripción)."""
    N = len(chunks)
    backend = embed.select_backend()
    texts = [" ".join([c["heading"], c["structure"], c["text"]]) for c in chunks]

    if backend == "neural":
        import numpy as np
        vecs = embed.neural_encode(texts)        # (N, dim), L2-normalizado
        np.save(VEC_PATH, vecs)
        return "neural:" + embed.NEURAL_MODEL_NAME, f"neuronal {vecs.shape[1]}d"

    # --- stdlib tf-idf disperso (sin dependencias) ---
    if VEC_PATH.exists():
        VEC_PATH.unlink()
    counters, df = [], Counter()
    for t in texts:
        ct = embed.counter(t)
        counters.append(ct)
        for d in {embed.h(f) for f in ct}:
            df[d] += 1
    idf = {d: math.log(N / v) for d, v in df.items() if 0 < v < N}
    postings = defaultdict(list)
    for rowid, ct in enumerate(counters, start=1):
        for d, w in embed.vector(ct, idf).items():
            postings[d].append((rowid, round(w, 5)))
    con.execute("CREATE TABLE sempost(dim INTEGER PRIMARY KEY, data TEXT)")
    con.executemany("INSERT INTO sempost VALUES(?,?)",
                    [(d, json.dumps(p)) for d, p in postings.items()])
    con.execute("CREATE TABLE semidf(dim INTEGER PRIMARY KEY, v REAL)")
    con.executemany("INSERT INTO semidf VALUES(?,?)",
                    [(d, round(v, 5)) for d, v in idf.items()])
    return embed.NAME, f"{embed.NAME}, {len(postings)} dims"


def build():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute(
        """CREATE VIRTUAL TABLE chunks USING fts5(
               slug UNINDEXED, name UNINDEXED, doc_type UNINDEXED,
               heading, article UNINDEXED, structure, citation UNINDEXED, text,
               section UNINDEXED, rama UNINDEXED, source UNINDEXED,
               tokenize='unicode61 remove_diacritics 2')"""
    )
    docs = sorted(MD_DIR.glob("*.md"))
    chunks = [c for md in docs for c in chunk_file(md)]
    con.executemany(
        "INSERT INTO chunks(slug,name,doc_type,heading,article,structure,citation,text,section,rama,source)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        [(c["slug"], c["name"], c["doc_type"], c["heading"], c["article"],
          c["structure"], c["citation"], c["text"], c["section"], c["rama"], c["source"])
         for c in chunks],
    )

    embedder, sem_desc = _build_semantic(con, chunks)
    con.execute("CREATE TABLE seminfo(k TEXT PRIMARY KEY, v TEXT)")
    con.executemany("INSERT INTO seminfo VALUES(?,?)",
                    [("N", str(len(chunks))), ("embedder", embedder)])

    n_edges = graph.build_into(con, chunks)
    con.commit()
    con.close()
    print(f"Indexados {len(chunks)} chunks de {len(docs)} documentos "
          f"(BM25 + {sem_desc}, {n_edges} concordancias) -> {DB}")


if __name__ == "__main__":
    build()
