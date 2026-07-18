"""Deterministic, dependency-free semantic embedding.

Production note
----------------
This is a *stand-in* for a real sentence-embedding model. It is intentionally
pure-stdlib so the intelligence layer is testable without numpy/sklearn/torch.
It tokensises, hashes each token into a fixed-dim vector, and pools. It captures
*lexical + simple compound* similarity well enough to gate imitations, but it is
NOT a semantic model. Swap `Embedding.embed` for a sentence-transformer in
production — every downstream engine calls this one function, so the change is
local.

The cosine function is real and correct; only the vectorisation is approximate.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Dict, Iterable, List

_DIM = 256
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+#./-]{1,}")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _ngrams(text: str, n: int) -> List[str]:
    """Character n-grams (cheap order-aware signal for the stand-in)."""
    low = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    if len(low) < n:
        return [low] if low else []
    return [low[i:i + n] for i in range(len(low) - n + 1)]


def _hash_dim(token: str) -> int:
    """Map a token to a stable dimension index in [0, _DIM)."""
    h = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") % _DIM


class Embedding:
    """Fixed-dim, hashed bag-of-tokens + char-ngram embedding + cosine.

    Two cheap order-aware signals (token unigrams + 3-char n-grams) make the
    stand-in catch single-word synonym swaps (Humans/People) far better than a
    pure bag-of-words model, while staying pure-stdlib. It is still NOT a
    semantic model — swap `Embedding.embed` for a sentence-transformer in
    production; every downstream engine calls only this function.
    """

    DIM = _DIM

    @staticmethod
    def embed(text: str) -> List[float]:
        vec = [0.0] * _DIM
        # token unigrams (lexical)
        counts: Dict[str, int] = {}
        for tok in _tokenize(text):
            counts[tok] = counts.get(tok, 0) + 1
        # character 3-grams (captures near-duplicate phrasing)
        for g in _ngrams(text, 3):
            counts["#" + g] = counts.get("#" + g, 0) + 1
        if not counts:
            return vec
        for tok, c in counts.items():
            d = _hash_dim(tok)
            sign = 1.0 if (hash(tok) & 1) == 0 else -1.0
            vec[d] += sign * math.log1p(c)
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        return vec

    @staticmethod
    def cosine(a: Iterable[float], b: Iterable[float]) -> float:
        av, bv = list(a), list(b)
        n = min(len(av), len(bv))
        dot = sum(av[i] * bv[i] for i in range(n))
        na = math.sqrt(sum(v * v for v in av))
        nb = math.sqrt(sum(v * v for v in bv))
        if na == 0 or nb == 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (na * nb)))


def embed(text: str) -> List[float]:
    return Embedding.embed(text)


def cosine(a: Iterable[float], b: Iterable[float]) -> float:
    return Embedding.cosine(a, b)
