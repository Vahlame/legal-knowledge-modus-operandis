"""Trocea los Markdown legales en chunks recuperables (uno por artículo).

Cada chunk lleva su cita exacta y su ruta estructural (Libro/Título/Capítulo),
que es lo que un abogado necesita para citar la fuente.
"""
import re
import pathlib

# slug de archivo -> nombre citable
DISPLAY = {
    "codigo-civil-2026": "Código Civil",
    "codigo-penal-2026": "Código Penal",
    "codigo-procesal-civil-2026": "Código Procesal Civil",
    "codigo-procesal-penal-2026": "Código Procesal Penal",
    "codigo-procesal-de-familia-2026": "Código Procesal de Familia",
    "codigo-de-familia": "Código de Familia",
    "examen-incorporacion-caacr-2026": "Examen de Incorporación CAACR 2026",
}
ART_RE = re.compile(r"^Art[ií]culo\s+(.+)$")


def display_name(slug: str) -> str:
    return DISPLAY.get(slug) or slug.replace("-", " ").title()


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
    slug, name = path.stem, display_name(path.stem)
    kind = meta.get("doc_kind", "")
    chunks, structure, cur, buf = [], "", None, []

    def flush():
        if cur is not None:
            cur["text"] = "\n".join(buf).strip()
            if cur["text"]:
                chunks.append(cur)

    for line in body.splitlines():
        if line.startswith("### "):           # divisor estructural
            flush()
            cur, buf = None, []
            structure = line[4:].strip()
        elif line.startswith("## "):           # artículo = unidad de recuperación
            flush()
            buf = []
            heading = line[3:].strip()
            m = ART_RE.match(heading)
            art = m.group(1).strip() if m else None
            cite = f"{name}, art. {art}" if art else f"{name} — {heading}"
            cur = {"slug": slug, "name": name, "kind": kind, "heading": heading,
                   "article": art, "structure": structure, "citation": cite}
        else:
            buf.append(line)
    flush()

    if not chunks:  # temarios / examen: trocear por párrafo
        for para in re.split(r"\n\s*\n", body):
            p = para.strip().lstrip("# ").strip()
            if len(p) < 15:
                continue
            chunks.append({"slug": slug, "name": name, "kind": kind, "heading": name,
                           "article": None, "structure": "", "citation": name, "text": p})
    return chunks
