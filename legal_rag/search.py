"""Búsqueda léxica (BM25) sobre el índice legal, con cita de artículo.

Ejemplos:
  python -m legal_rag.search usufructo y habitación
  python -m legal_rag.search prescripción adquisitiva --code codigo-civil-2026
  python -m legal_rag.search --art 1045 --code codigo-civil-2026
"""
import sqlite3
import re
import sys
import argparse
import pathlib

DB = pathlib.Path(__file__).resolve().parent.parent / "legal.db"


def _match(q: str) -> str:
    """Texto libre -> query FTS5 (OR de términos; BM25 ordena por relevancia)."""
    toks = re.findall(r"\w+", q, re.UNICODE)
    return " OR ".join(f'"{t}"' for t in toks)


def search(query: str, k: int = 5, code: str | None = None):
    con = sqlite3.connect(DB)
    sql = ("SELECT citation, structure, kind, "
           "snippet(chunks, 7, '«', '»', ' … ', 16) AS snip, rank "
           "FROM chunks WHERE chunks MATCH ?")
    args = [_match(query)]
    if code:
        sql += " AND slug = ?"
        args.append(code)
    sql += " ORDER BY rank LIMIT ?"
    args.append(k)
    rows = con.execute(sql, args).fetchall()
    con.close()
    return rows


def get_article(num: str, code: str | None = None):
    con = sqlite3.connect(DB)
    sql = "SELECT citation, structure, text FROM chunks WHERE article = ?"
    args = [str(num)]
    if code:
        sql += " AND slug = ?"
        args.append(code)
    rows = con.execute(sql, args).fetchall()
    con.close()
    return rows


def main():
    ap = argparse.ArgumentParser(description="Búsqueda en la memoria legal CR")
    ap.add_argument("query", nargs="*", help="texto a buscar")
    ap.add_argument("--art", help="traer artículo exacto, p.ej. --art 1045")
    ap.add_argument("--code", help="filtrar por código (slug), p.ej. codigo-civil-2026")
    ap.add_argument("-k", type=int, default=5, help="número de resultados")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if a.art:
        rows = get_article(a.art, a.code)
        if not rows:
            print("(sin resultados)")
        for cite, struct, text in rows:
            print(f"\n### {cite}" + (f"  ·  {struct}" if struct else ""))
            print(text)
        return

    rows = search(" ".join(a.query), a.k, a.code)
    if not rows:
        print("(sin resultados)")
    for cite, struct, kind, snip, _rank in rows:
        loc = f"  ·  {struct}" if struct else ""
        print(f"\n[{kind}] {cite}{loc}")
        print(f"   {snip}")


if __name__ == "__main__":
    main()
