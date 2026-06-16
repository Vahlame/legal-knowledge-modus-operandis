"""
Clasificación de cada archivo fuente POR SU NOMBRE — escalable a muchos documentos
con nombres distintos.

Dos niveles:
  1) REGISTRY  — overrides curados para los archivos conocidos (etiquetas bonitas).
  2) inferencia por palabras clave — para CUALQUIER archivo nuevo, sin tocar código:
     "Ley General de la Administración Pública", "Constitución Política",
     "Reglamento de Tránsito", "Jurisprudencia Sala Primera"… se clasifican solos.

Tipos: ley (la materia: códigos y demás normativa) · temario (guía de estudio) ·
examen · jurisprudencia · doctrina · otro. Para RESPONDER se usa solo `is_law`
(ley + jurisprudencia); los temarios van por su stream de estudio aparte.
"""
import re
import unicodedata


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"[\s_\-]+", " ", s).strip()


# slug -> (doc_type, rama, etiqueta citable) — overrides curados
REGISTRY = {
    "codigo-civil-2026":                ("ley", "Derecho Civil",               "Código Civil"),
    "codigo-procesal-civil-2026":       ("ley", "Derecho Procesal Civil",      "Código Procesal Civil"),
    "codigo-de-familia":                ("ley", "Derecho de Familia",          "Código de Familia"),
    "codigo-procesal-de-familia-2026":  ("ley", "Derecho Procesal de Familia", "Código Procesal de Familia"),
    "codigo-penal-2026":                ("ley", "Derecho Penal",               "Código Penal"),
    "codigo-procesal-penal-2026":       ("ley", "Derecho Procesal Penal",      "Código Procesal Penal"),
    "temario-derecho-civil-2025":          ("temario", "Derecho Civil",          "Temario de Derecho Civil"),
    "temario-derecho-penal-2025":          ("temario", "Derecho Penal",          "Temario de Derecho Penal"),
    "temario-derecho-de-familia-2025":     ("temario", "Derecho de Familia",     "Temario de Derecho de Familia"),
    "temario-derecho-comercial-2025":      ("temario", "Derecho Comercial",      "Temario de Derecho Comercial"),
    "temario-derecho-constitucional-2025": ("temario", "Derecho Constitucional", "Temario de Derecho Constitucional"),
    "temario-derecho-laboral-2025":        ("temario", "Derecho Laboral",        "Temario de Derecho Laboral"),
    "temario-derecho-administrativo-2025": ("temario", "Derecho Administrativo", "Temario de Derecho Administrativo"),
    "examen-incorporacion-caacr-2026":     ("examen",  "General",                "Examen de Incorporación CAACR 2026"),
}

# Inferencia de TIPO por palabras clave (en orden de prioridad).
_TYPE_RULES = [
    ("temario",        ["temario", "programa de estudio", "syllabus", "guia de estudio", "plan de estudio"]),
    ("examen",         ["examen", "prueba ", "evaluacion", "cuestionario"]),
    ("jurisprudencia", ["jurisprudencia", "sentencia", "voto ", "resolucion de la sala",
                        "dictamen", "sala constitucional", "sala primera", "sala segunda", "sala tercera"]),
    ("doctrina",       ["doctrina", "manual de", "tratado de", "comentario", "ensayo", "articulo academico"]),
    ("ley",            ["codigo", "ley", "constitucion", "reglamento", "decreto", "norma",
                        "estatuto", "convencion", "tratado", "directriz", "ordenanza",
                        "acuerdo", "protocolo", "lineamiento"]),
]

# Inferencia de RAMA (los compuestos "procesal X" primero).
_RAMA_RULES = [
    ("Derecho Procesal de Familia", ["procesal de familia", "procesal familia"]),
    ("Derecho Procesal Civil",      ["procesal civil"]),
    ("Derecho Procesal Penal",      ["procesal penal"]),
    ("Derecho Procesal Laboral",    ["procesal laboral", "procesal de trabajo"]),
    ("Derecho Constitucional",      ["constitucional", "constitucion"]),
    ("Derecho Administrativo",      ["administrativo", "administracion publica", "contencioso"]),
    ("Derecho Tributario",          ["tributario", "fiscal", "impuesto", "renta"]),
    ("Derecho Laboral",             ["laboral", "trabajo"]),
    ("Derecho Comercial",           ["comercial", "mercantil", "comercio", "sociedades"]),
    ("Derecho de la Niñez",         ["ninez", "adolescencia", "menores", "ninez"]),
    ("Derecho de Familia",          ["familia"]),
    ("Derecho Notarial",            ["notarial", "notariado"]),
    ("Derecho Registral",           ["registral", "registro publico"]),
    ("Derecho Ambiental",           ["ambiental", "ambiente"]),
    ("Derecho Agrario",             ["agrario", "agraria"]),
    ("Derecho Municipal",           ["municipal", "municipalidad"]),
    ("Derecho Internacional",       ["internacional"]),
    ("Derecho Penal",               ["penal"]),
    ("Derecho Civil",               ["civil"]),
]


def _infer_type(norm: str) -> str:
    for t, kws in _TYPE_RULES:
        if any(k in norm for k in kws):
            return t
    return "otro"


def _infer_rama(norm: str) -> str:
    for rama, kws in _RAMA_RULES:
        if any(k in norm for k in kws):
            return rama
    return "General"


def _label(slug: str) -> str:
    words = [w for w in re.split(r"[\s_\-]+", slug) if not re.fullmatch(r"(19|20)\d{2}", w)]
    s = " ".join(words).title()
    s = re.sub(r"\bCdigo\b|\bCodigo\b", "Código", s)
    return s.strip() or slug


def classify(slug: str) -> dict:
    """{doc_type, rama, label, is_law} para el slug de un archivo (conocido o nuevo)."""
    if slug in REGISTRY:
        t, rama, label = REGISTRY[slug]
    else:
        norm = _norm(slug)
        t, rama, label = _infer_type(norm), _infer_rama(norm), _label(slug)
    return {"doc_type": t, "rama": rama, "label": label, "is_law": t in ("ley", "jurisprudencia")}
