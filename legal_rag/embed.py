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
