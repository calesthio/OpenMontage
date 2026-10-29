"""Semantic knowledge graph of IDEAS (not videos).

Each Concept node records the 8 signals from the v2 design:
popularity, velocity, sentiment, controversy, novelty, saturation,
viewer_overlap, historical_retention.

Edges record viewer-overlap between concepts so Hermes can *combine*
adjacent ideas instead of imitating a single video.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# The 8 canonical per-node signals (the v2 spec). Stored as 0..1 floats.
SIGNALS = (
    "popularity", "velocity", "sentiment", "controversy",
    "novelty", "saturation", "viewer_overlap", "historical_retention",
)


@dataclass
class Concept:
    label: str
    parent: Optional[str] = None
    # 0..1 strength signals
    popularity: float = 0.0
    velocity: float = 0.0
    sentiment: float = 0.5      # 0 neg .. 1 pos
    controversy: float = 0.0
    novelty: float = 0.0
    saturation: float = 0.0
    # overlap to the *whole graph* (pre-computed aggregate)
    viewer_overlap: float = 0.0
    historical_retention: float = 0.0
    # ids of published videos that used this concept (for backtesting)
    published: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Concept":
        return cls(**{k: d.get(k, field_default(cls, k)) for k in d})


def field_default(cls, name):
    for f in cls.__dataclass_fields__.values():
        if f.name == name:
            return f.default if f.default is not None else []
    return None


@dataclass
class Edge:
    a: str
    b: str
    overlap: float = 0.0     # viewer overlap 0..1

    def to_dict(self) -> dict:
        return asdict(self)


class ConceptGraph:
    """Concept nodes + viewer-overlap edges + combination synthesis."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Concept] = {}
        self.edges: Dict[frozenset, Edge] = {}

    # ---- mutation ------------------------------------------------------
    def add(self, concept: Concept) -> Concept:
        self.nodes[concept.label] = concept
        self._recompute_overlaps()
        return concept

    def upsert(self, label: str, **signals) -> Concept:
        c = self.nodes.get(label) or Concept(label=label)
        for k, v in signals.items():
            if hasattr(c, k):
                setattr(c, k, float(v))
        self.nodes[label] = c
        self._recompute_overlaps()
        return c

    def link(self, a: str, b: str, overlap: float = 0.5) -> Edge:
        key = frozenset({a, b})
        e = self.edges.get(key, Edge(a=a, b=b))
        e.overlap = max(e.overlap, float(overlap))
        self.edges[key] = e
        return e

    def _recompute_overlaps(self) -> None:
        """Aggregate pairwise viewer overlap into a per-node average."""
        if not self.edges:
            return
        for c in self.nodes.values():
            c.viewer_overlap = 0.0
        totals: Dict[str, List[float]] = {n: [] for n in self.nodes}
        for e in self.edges.values():
            if e.a in totals and e.b in totals:
                totals[e.a].append(e.overlap)
                totals[e.b].append(e.overlap)
        for n, vals in totals.items():
            if vals:
                self.nodes[n].viewer_overlap = sum(vals) / len(vals)

    # ---- query ---------------------------------------------------------
    def get(self, label: str) -> Optional[Concept]:
        return self.nodes.get(label)

    def neighbours(self, label: str) -> List[Concept]:
        out = []
        for e in self.edges.values():
            if e.a == label and e.b in self.nodes:
                out.append(self.nodes[e.b])
            elif e.b == label and e.a in self.nodes:
                out.append(self.nodes[e.a])
        return out

    def emerging(self, top: int = 10) -> List[Concept]:
        """Ideas gaining traction but not yet saturated."""
        scored = [
            (c, (c.velocity * 0.6 + c.novelty * 0.4) * (1.0 - c.saturation))
            for c in self.nodes.values()
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:top]]

    def synthesize(self, *labels: str, max_depth: int = 2) -> List[str]:
        """Combine 2-4 concepts into candidate *idea spaces*.

        Returns short labels like "Claude + Productivity + Military Strategy"
        for each requested combination (depth <= max_depth). The combination
        itself is an undiscovered *space* until it's been saturated.
        """
        labels = [l for l in labels if l in self.nodes]
        if not labels:
            return []
        combos = []
        for r in range(2, min(max_depth + 1, len(labels) + 1)):
            combos.extend(itertools.combinations(labels, r))
        return [f"{' + '.join(c)}" for c in combos]

    # ---- persistence ----------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges.values()],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ConceptGraph":
        g = cls()
        for label, nd in (d.get("nodes") or {}).items():
            g.nodes[label] = Concept.from_dict({"label": label, **nd})
        for ed in (d.get("edges") or []):
            a = ed.get("a"); b = ed.get("b")
            if a is not None and b is not None:
                g.edges[frozenset({a, b})] = Edge(a=a, b=b, overlap=float(ed.get("overlap", 0.0)))
        return g

    def from_json(cls, text: str) -> "ConceptGraph":
        import json
        return cls.from_dict(json.loads(text))
