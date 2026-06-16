"""
Capa de asesoría y formación (F5).

Ensambla, para una pregunta o tema, el material que un agente de IA necesita para
asesorar/formar a un abogado citando SIEMPRE la fuente:

  - core    : artículos directamente relevantes (recuperación híbrida, N adaptativo)
  - related : artículos conectados por el grafo de concordancias (cita / citado por /
              misma materia) — los "artículos relacionados que ayudan al caso"
  - topics  : entradas del temario (currículo del examen de incorporación) que tocan
              el tema, para estudio/formación

Regla anti-alucinación: todo proviene del corpus indexado y va citado. El agente NO
inventa norma; si algo no está, lo dice.

Uso:  python -m legal_rag.advisor "puede el inquilino subarrendar" [--code codigo-civil-2026]
"""
import re
import sys
import sqlite3
import argparse
import pathlib

from legal_rag import search, graph

DB = pathlib.Path(__file__).resolve().parent.parent / "legal.db"


def _excerpt(t, n=220):
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n] + " …"


def _article_row(con, slug, art):
    return con.execute(
        "SELECT citation, structure, text FROM chunks WHERE slug=? AND article=? LIMIT 1",
        (slug, art)).fetchone()


def _topic_hits(con, question, k=6):
    toks = re.findall(r"\w+", question, re.UNICODE)
    if not toks:
        return []
    match = " OR ".join(f'"{t}"' for t in toks)
    rows = con.execute(
        "SELECT citation, rama, text FROM chunks WHERE chunks MATCH ? AND doc_type='temario' "
        "ORDER BY rank LIMIT ?", (match, k)).fetchall()
    return [{"citation": c, "rama": rama, "topic": _excerpt(t, 100)} for c, rama, t in rows]


def consult(question, code=None, expand_top=6, neighbor_top=2, max_related=40):
    """Bundle de asesoría: núcleo + relacionados (grafo) + temario. JSON-serializable."""
    core = search.hybrid(question, code)
    con = sqlite3.connect(DB)

    core_arts = [r for r in core if r["doc_type"] == "ley"]
    core_keys = {(r["slug"], r["article"]) for r in core if r["article"]}

    related, order = {}, []  # (slug,art) -> relación
    for i, r in enumerate(a for a in core_arts if a["article"]):
        if i >= expand_top:
            break
        rel = graph.related(r["slug"], r["article"])
        groups = [("cita", rel["cites"]), ("citado_por", rel["cited_by"])]
        if i < neighbor_top:
            groups.append(("misma_materia", rel["neighbors"]))
        for relation, arts in groups:
            for a in arts:
                key = (r["slug"], a)
                if key not in core_keys and key not in related:
                    related[key] = relation
                    order.append(key)

    related_items = []
    for slug, art in order[:max_related]:
        row = _article_row(con, slug, art)
        if row:
            cite, struct, text = row
            related_items.append({"slug": slug, "article": art, "relation": related[(slug, art)],
                                  "citation": cite, "structure": struct, "excerpt": _excerpt(text)})

    topics = _topic_hits(con, question)
    con.close()
    return {
        "question": question,
        "core": [{"doc_type": r["doc_type"], "rama": r["rama"], "citation": r["citation"],
                  "structure": r["structure"], "slug": r["slug"], "article": r["article"],
                  "score": r["score"], "text": r["text"]}
                 for r in core_arts],
        "related": related_items,
        "topics": topics,
    }


def format_consult(b):
    out = [f"PREGUNTA: {b['question']}", ""]
    out.append(f"== FUENTES DE LEY ({len(b['core'])} artículos directamente relevantes) ==")
    for r in b["core"]:
        loc = f"  ·  {r['structure']}" if r["structure"] else ""
        out.append(f"\n[ley · {r['rama']}] {r['citation']}{loc}")
        out.append(f"   {_excerpt(r['text'], 300)}")
    if b["related"]:
        out.append(f"\n== ARTÍCULOS RELACIONADOS ({len(b['related'])} por concordancia) ==")
        for r in b["related"]:
            out.append(f"\n({r['relation']}) {r['citation']}")
            out.append(f"   {r['excerpt']}")
    if b["topics"]:
        out.append("\n== TEMARIO — guía de estudio (NO es la ley) ==")
        for t in b["topics"]:
            out.append(f"   • [temario · {t['rama']}] {t['topic']}")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description="Asesoría legal: núcleo + relacionados + temario")
    ap.add_argument("question", nargs="+")
    ap.add_argument("--code", help="filtrar el núcleo por código (slug)")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    print(format_consult(consult(" ".join(a.question), a.code)))


if __name__ == "__main__":
    main()
