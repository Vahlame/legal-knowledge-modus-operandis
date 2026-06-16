"""Trocea los Markdown legales en chunks recuperables (uno por artículo).

Cada chunk lleva su clasificación EXPLÍCITA por archivo (doc_type/rama/source vía
`sources.classify`) además de su cita y ruta estructural — así nunca se confunde la
ley (la materia) con un temario (guía de estudio).
"""
import re
import pathlib

from legal_rag import sources

ART_RE = re.compile(r"^Art[ií]culo\s+(.+)$")

# Norma muerta: el cuerpo del artículo EMPIEZA con la marca de derogación en forma
# pasiva ("Derogado/Derogada"). NO se confunde con cláusulas operativas que derogan
# OTRAS normas ("Deróguese...", "Quedan derogadas las disposiciones que se opongan"),
# que sí son ley vigente. Por eso se ancla a ^ y se exige el participio.
_DEROG = re.compile(
    r"^\(?\s*(?:derogad[oa]s?\b|sin\s+vigencia\b|t[eé]ngase\s+por\s+derogad)", re.I)


def es_vigente(text: str) -> bool:
    """False si el artículo está derogado/sin vigencia (no es ley aplicable)."""
    return not _DEROG.match(text.strip())


def parse_frontmatter(text: str):
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            meta = {}
            for line in text[3:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
            return meta, text[end + 4:]
    return {}, text


def chunk_file(path: pathlib.Path):
    meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
    slug = path.stem
    info = sources.classify(slug)                 # clasificación por nombre de archivo
    name = info["label"]
    base = {"slug": slug, "name": name, "doc_type": info["doc_type"],
            "rama": info["rama"], "source": meta.get("source", slug)}

    chunks, structure, cur, buf = [], "", None, []
    sec = 0  # id de sección estructural: único por Capítulo físico, no por su título

    def flush():
        if cur is not None:
            cur["text"] = "\n".join(buf).strip()
            if cur["text"]:
                cur["vigente"] = 1 if (cur["doc_type"] != "ley" or es_vigente(cur["text"])) else 0
                chunks.append(cur)

    for line in body.splitlines():
        if line.startswith("### "):           # divisor estructural
            flush()
            cur, buf = None, []
            sec += 1
            structure = line[4:].strip()
        elif line.startswith("## "):           # artículo = unidad de recuperación
            flush()
            buf = []
            heading = line[3:].strip()
            m = ART_RE.match(heading)
            art = m.group(1).strip() if m else None
            cite = f"{name}, art. {art}" if art else f"{name} — {heading}"
            cur = {**base, "heading": heading, "article": art, "structure": structure,
                   "section": f"{slug}#{sec}", "citation": cite}
        else:
            buf.append(line)
    flush()

    if not chunks:  # temarios / examen: trocear por párrafo
        for para in re.split(r"\n\s*\n", body):
            p = para.strip().lstrip("# ").strip()
            if len(p) < 15:
                continue
            chunks.append({**base, "heading": name, "article": None, "structure": "",
                           "section": f"{slug}#0", "citation": name, "text": p, "vigente": 1})
    return chunks
