"""
Embedder léxico-morfológico stdlib (cero dependencias).

Convierte texto en un vector disperso tf-idf normalizado, hasheando dos tipos de
features:
  - palabras completas (acento-plegadas)         -> señal léxica
  - n-gramas de caracteres (tamaño 4) por palabra -> señal morfológica: empareja
    variantes como arrendamiento / arrendatario / subarriendo sin modelo neuronal.

Complementa a BM25 (que es palabra-exacta) y se fusiona con él por RRF. Para recall
de sinónimos REALES (inquilino~arrendatario) se puede sustituir por un embedder
neuronal (fastembed) detrás de esta misma interfaz: features()/vector().
"""
import re
import math
import zlib
import unicodedata
from collections import Counter

NAME = "stdlib-hashing-v1"
DIM = 1 << 20  # 1.048.576 dimensiones (espacio de hashing)


def fold(s: str) -> str:
    """Minúsculas sin diacríticos (para emparejar prescripción≈prescripcion)."""
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def features(text: str):
    """Palabras + n-gramas de caracteres (4) de palabras de >=5 letras."""
    feats = []
    for w in re.findall(r"[a-z0-9]+", fold(text)):
        feats.append("w:" + w)
        if len(w) >= 5:
            p = "#" + w + "#"
            for i in range(len(p) - 3):
                feats.append("c:" + p[i:i + 4])
    return feats


def h(feat: str) -> int:
    return zlib.crc32(feat.encode("utf-8")) % DIM


def counter(text: str) -> Counter:
    return Counter(features(text))


def vector(feat_counter: Counter, idf_by_dim: dict) -> dict:
    """Vector disperso tf-idf normalizado L2: {dim: peso}. El coseno entre dos
    de estos vectores = producto punto (porque están normalizados)."""
    vec = {}
    for feat, tf in feat_counter.items():
        d = h(feat)
        idf = idf_by_dim.get(d, 0.0)
        if idf <= 0.0:
            continue
        vec[d] = vec.get(d, 0.0) + (1.0 + math.log(tf)) * idf
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {d: v / norm for d, v in vec.items()}


# ---------------------------------------------------------------------------
# Backend neuronal opcional (fastembed) — recall de SINÓNIMOS reales
# (inquilino≈arrendatario), que el embedder léxico de arriba no captura.
# Si fastembed está instalado se usa por defecto; si no, cae al stdlib.
# Override:  env LEGAL_EMBEDDER = stdlib | neural
# ---------------------------------------------------------------------------
import os

NEURAL_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_neural_model = None


def neural_available():
    try:
        import fastembed  # noqa: F401
        return True
    except Exception:
        return False


def _neural():
    global _neural_model
    if _neural_model is None:
        import warnings
        warnings.filterwarnings("ignore", message=".*mean pooling.*")
        from fastembed import TextEmbedding
        _neural_model = TextEmbedding(NEURAL_MODEL_NAME)
    return _neural_model


def neural_encode(texts, kind="passage"):
    """Matriz np.float32 (n, dim) L2-normalizada (coseno = producto punto).
    Para modelos e5 se antepone el prefijo asimétrico 'query:' / 'passage:'."""
    import numpy as np
    items = list(texts)
    if "e5" in NEURAL_MODEL_NAME.lower():
        items = [f"{kind}: {t}" for t in items]
    arr = np.asarray([list(v) for v in _neural().embed(items)], dtype="float32")
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def select_backend():
    pref = os.environ.get("LEGAL_EMBEDDER", "").strip().lower()
    if pref in ("stdlib", "neural"):
        return pref
    return "neural" if neural_available() else "stdlib"
