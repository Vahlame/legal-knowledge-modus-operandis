"""
Construye el índice híbrido sobre los chunks legales:
  - FTS5 BM25 (léxico, término exacto)
  - Semántico stdlib (tf-idf disperso, índice invertido por dimensión) + idf

Ejecutar:  python -m legal_rag.index
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


def build():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.execute(
        """CREATE VIRTUAL TABLE chunks USING fts5(
               slug UNINDEXED, name UNINDEXED, kind UNINDEXED,
               heading, article UNINDEXED, structure, citation UNINDEXED, text,
               section UNINDEXED,
               tokenize='unicode61 remove_diacritics 2')"""
    )
    docs = sorted(MD_DIR.glob("*.md"))
    chunks = [c for md in docs for c in chunk_file(md)]
    con.executemany(
        "INSERT INTO chunks(slug,name,kind,heading,article,structure,citation,text,section)"
        " VALUES(?,?,?,?,?,?,?,?,?)",
        [(c["slug"], c["name"], c["kind"], c["heading"], c["article"],
          c["structure"], c["citation"], c["text"], c["section"]) for c in chunks],
    )

    # --- capa semántica ---
    counters, df = [], Counter()
    for c in chunks:
        ct = embed.counter(" ".join([c["heading"], c["structure"], c["text"]]))
        counters.append(ct)
        for d in {embed.h(f) for f in ct}:
            df[d] += 1
    N = len(chunks)
    idf = {d: math.log(N / v) for d, v in df.items() if 0 < v < N}

    postings = defaultdict(list)
    for rowid, ct in enumerate(counters, start=1):     # rowid FTS5 = orden de inserción
        for d, w in embed.vector(ct, idf).items():
            postings[d].append((rowid, round(w, 5)))

    con.execute("CREATE TABLE sempost(dim INTEGER PRIMARY KEY, data TEXT)")
    con.executemany("INSERT INTO sempost VALUES(?,?)",
                    [(d, json.dumps(p)) for d, p in postings.items()])
    con.execute("CREATE TABLE semidf(dim INTEGER PRIMARY KEY, v REAL)")
    con.executemany("INSERT INTO semidf VALUES(?,?)",
                    [(d, round(v, 5)) for d, v in idf.items()])
    con.execute("CREATE TABLE seminfo(k TEXT PRIMARY KEY, v TEXT)")
    con.executemany("INSERT INTO seminfo VALUES(?,?)",
                    [("N", str(N)), ("embedder", embed.NAME), ("dims", str(len(postings)))])

    # --- grafo de concordancias (F4) ---
    n_edges = graph.build_into(con, chunks)

    con.commit()
    con.close()
    print(f"Indexados {N} chunks de {len(docs)} documentos "
          f"(BM25 + semántico '{embed.NAME}', {len(postings)} dims, "
          f"{n_edges} concordancias) -> {DB}")


if __name__ == "__main__":
    build()
