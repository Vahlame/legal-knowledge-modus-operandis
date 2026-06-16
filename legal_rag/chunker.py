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


# Notas de historia legislativa SCIJ. Se separan POR PÁRRAFOS (no por paréntesis):
# el texto legal tiene paréntesis DESBALANCEADOS ("inciso a)", "aparte b)") que
# romperían cualquier emparejamiento. En el Markdown las notas son párrafos propios,
# así que un párrafo que EMPIEZA con un encabezado de nota es historia; el resto es
# texto operativo. No toca paréntesis operativos ("(en adelante, el Comprador)").
_NOTE_START = re.compile(
    r"^\(\s*(?:"
    r"as[ií]\s+(?:reformad|adicionad|corrid|modificad|reubicad|ampliad|derogad|"
    r"interpretad|reenumerad|trasladad|aclarad|reform)"
    r"|nota\s+(?:de\s+sinalevi|del\s+editor)"
    r"|mediante\s+resoluci[oó]n"
    r"|(?:reformad[oa]|adicionad[oa]|derogad[oa]|interpretad[oa])\s+por"
    r")", re.I)


def split_reformas(body: str):
    """Separa, por párrafos, las notas SCIJ del texto operativo. Robusto ante
    paréntesis desbalanceados. Devuelve (operativo, [notas])."""
    operative, notes = [], []
    for p in re.split(r"\n\s*\n", body):
        p = re.sub(r"\s+", " ", p).strip()
        if p:
            (notes if _NOTE_START.match(p) else operative).append(p)
    return " ".join(operative).strip(), notes


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
            body = "\n".join(buf).strip()
            if body:
                es_ley = cur["doc_type"] == "ley"
                vig = (not es_ley) or es_vigente(body)
                cur["vigente"] = 1 if vig else 0
                if es_ley and vig:
                    operative, notes = split_reformas(body)
                    cur["text"] = operative or body          # nunca dejar vacío
                    cur["reformas"] = " ".join(notes)
                else:
                    cur["text"] = body                       # derogado/temario: tal cual
                    cur["reformas"] = ""
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
                           "section": f"{slug}#0", "citation": name, "text": p,
                           "vigente": 1, "reformas": ""})
    return chunks
