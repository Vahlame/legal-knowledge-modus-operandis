"""Construye el índice SQLite FTS5 sobre los chunks legales.

FTS5 con tokenizer unicode61 + remove_diacritics: "prescripcion" encuentra
"prescripción". Columnas de metadata UNINDEXED (no entran al ranking BM25).
Ejecutar:  python -m legal_rag.index
"""
import sqlite3
import pathlib

from legal_rag.chunker import chunk_file

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
               tokenize='unicode61 remove_diacritics 2')"""
    )
    docs = sorted(MD_DIR.glob("*.md"))
    n = 0
    for md in docs:
        rows = [
            (c["slug"], c["name"], c["kind"], c["heading"], c["article"],
             c["structure"], c["citation"], c["text"])
            for c in chunk_file(md)
        ]
        con.executemany(
            "INSERT INTO chunks(slug,name,kind,heading,article,structure,citation,text)"
            " VALUES(?,?,?,?,?,?,?,?)",
            rows,
        )
        n += len(rows)
    con.commit()
    con.close()
    print(f"Indexados {n} chunks de {len(docs)} documentos -> {DB}")


if __name__ == "__main__":
    build()
