"""
Clasificación explícita de cada archivo fuente POR SU NOMBRE, en un solo lugar.

Distingue tajantemente (para no confundir nunca la ley con una guía de estudio):
  - ley      : el derecho aplicable — códigos y demás normativa = "LA MATERIA".
  - temario  : guías de estudio del examen de incorporación (NO son derecho citable).
  - examen   : el examen de incorporación (práctica/autoevaluación).

Regla del sistema: para RESPONDER casos se usa solo `doc_type == "ley"`; los temarios
van por su stream de estudio aparte. Registro deliberado y auditable, con fallback
heurístico para archivos nuevos. `classify()` recibe el slug del archivo.
"""

# slug -> (doc_type, rama, etiqueta citable)
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

# para fallback: el "procesal X" debe ganar a "X" -> va primero
_RAMAS = [
    ("procesal de familia", "Derecho Procesal de Familia"),
    ("procesal civil",      "Derecho Procesal Civil"),
    ("procesal penal",      "Derecho Procesal Penal"),
    ("civil",               "Derecho Civil"),
    ("penal",               "Derecho Penal"),
    ("familia",             "Derecho de Familia"),
    ("comercial",           "Derecho Comercial"),
    ("constitucional",      "Derecho Constitucional"),
    ("laboral",             "Derecho Laboral"),
    ("administrativo",      "Derecho Administrativo"),
]


def _rama(low: str) -> str:
    norm = low.replace("-", " ")
    for key, rama in _RAMAS:
        if key in norm:
            return rama
    return "General"


def classify(slug: str) -> dict:
    """Devuelve {doc_type, rama, label, is_law} para el slug de un archivo."""
    if slug in REGISTRY:
        t, rama, label = REGISTRY[slug]
    else:  # archivo nuevo: heurística por nombre
        low = slug.lower()
        rama = _rama(low)
        title = slug.replace("-", " ").title()
        if low.startswith("temario"):
            t, label = "temario", title
        elif "examen" in low:
            t, label = "examen", title
        elif low.startswith("codigo") or "codigo" in low or low.startswith("ley") or "-ley-" in low:
            t, label = "ley", title
        else:
            t, label = "otro", title
    return {"doc_type": t, "rama": rama, "label": label, "is_law": t == "ley"}
