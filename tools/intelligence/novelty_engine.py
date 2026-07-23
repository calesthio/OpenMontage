"""Novelty Engine — prevents imitation by embedding every published idea.

Rule (v2 spec): reject a candidate whose cosine similarity to ANY previously
published idea exceeds the threshold (default 0.9). This forces the flywheel
to explore *adjacent* concept spaces rather than reusing the same structure.

Embeddings come from tools.intelligence.embedding — a stand-in for a real
sentence model. Only that one function needs swapping for production.
"""
from __future__ import annotations

from typing import Iterable, List, Optional, Tuple

from .embedding import Embedding, embed


class NoveltyEngine:
    def __init__(self, threshold: float = 0.9, embedding: Optional["Embedding"] = None) -> None:
        self.threshold = float(threshold)
        self._emb = embedding or Embedding
        # store (id, label, embedding) for every published/seen idea
        self._seen: List[Tuple[str, str, List[float]]] = []

    def register_published(self, idea_id: str, text: str, label: str = "") -> None:
        self._seen.append((idea_id, label or text, self._emb.embed(text)))

    def most_similar(self, text: str) -> Optional[Tuple[str, float]]:
        vec = self._emb.embed(text)
        best = None
        for cid, label, cvec in self._seen:
            sim = self._emb.cosine(vec, cvec)
            if best is None or sim > best[1]:
                best = (label or cid, sim)
        return best

    def is_novel(self, text: str) -> bool:
        return self.novelty(text) > (1.0 - self.threshold)

    def novelty(self, text: str) -> float:
        """1 - max similarity to any seen idea. 1.0 == completely novel."""
        m = self.most_similar(text)
        if m is None:
            return 1.0
        return 1.0 - m[1]

    def check(self, text: str) -> Tuple[bool, float, Optional[str]]:
        """(is_novel, novelty_score, nearest_label)."""
        m = self.most_similar(text)
        if m is None:
            return (True, 1.0, None)
        sim = m[1]
        return (sim <= self.threshold, 1.0 - sim, m[0])

    def filter(self, candidates: Iterable[str]) -> List[str]:
        """Keep only novel candidates, preserving input order."""
        return [c for c in candidates if self.is_novel(c)]
