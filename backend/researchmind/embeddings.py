"""Text embeddings for semantic retrieval and claim similarity.

Primary backend: SentenceTransformers (all-MiniLM-L6-v2, 384 dims).
Fallback: a deterministic hashed bag-of-words embedding with the same dimension,
so the app still works offline or if the model cannot be downloaded.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import threading
from functools import lru_cache

import numpy as np

from .config import get_settings

log = logging.getLogger(__name__)

DIM = 384
_STOP = set(
    "a an the of and or to in on for with by from at as is are was were be been this that these those "
    "we our it its into than then there their which who whom what when where while using use used based "
    "can could may might also both such not no only more most other over under between".split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9][a-z0-9\-]+", text.lower()) if t not in _STOP]


class HashingEmbedder:
    name = "hashing-bow-384"
    dim = DIM

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, text in enumerate(texts):
            tokens = tokenize(text)
            grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
            for g in grams:
                h = int.from_bytes(hashlib.md5(g.encode()).digest()[:4], "little")
                out[i, h % self.dim] += 1.0 if (h >> 31) & 1 else -1.0
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out


class SentenceTransformerEmbedder:
    dim = DIM

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # heavy import, keep lazy

        self.model = SentenceTransformer(model_name, device="cpu")
        self.name = model_name.split("/")[-1]
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        self.dim = get_dim()

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


_load_lock = threading.Lock()


def get_embedder():
    """Shared embedder; the lock stops concurrent first calls (e.g. API warm-up + a request) loading twice."""
    with _load_lock:
        return _load_embedder()


def is_loaded() -> bool:
    return _load_embedder.cache_info().currsize > 0


@lru_cache(maxsize=1)
def _load_embedder():
    settings = get_settings()
    if settings.embedding_backend in ("auto", "sentence-transformers"):
        try:
            emb = SentenceTransformerEmbedder(settings.embedding_model)
            if emb.dim != DIM:
                raise ValueError(f"expected a {DIM}-dim model, got {emb.dim}")
            return emb
        except Exception as e:
            if settings.embedding_backend == "sentence-transformers":
                raise
            log.warning("SentenceTransformers unavailable (%s); using hashing embedder.", e)
    return HashingEmbedder()


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denom) if denom else 0.0


def jaccard(a: str, b: str) -> float:
    ta, tb = set(tokenize(a)), set(tokenize(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / math.sqrt(len(ta) * len(tb))
