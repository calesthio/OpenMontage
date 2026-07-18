"""Seed Miner — turns the intelligence layer into flywheel seeds.

Pipeline:
  1. ConceptGraph holds idea nodes + viewer-overlap edges.
  2. synthesize() combines concepts into candidate IDEA SPACES.
  3. OpportunityEngine scores each space (novelty x demand x retention x
     creator_gap x monetization x evergreen).
  4. NoveltyEngine rejects spaces too similar to anything already
     published/seen (the v2 "don't imitate" gate).
  5. Ranked, novel, high-opportunity spaces become seeds for the
     evolutionary flywheel.

Everything here is deterministic and offline. To make it *live*, plug real
signal sources into ConceptGraph.upsert() (YouTube/Reddit/Trends/HN/arXiv…)
and recompute the opportunity factors — the miner doesn't change.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Dict, List, Optional

from .knowledge_graph import ConceptGraph, Concept
from .novelty_engine import NoveltyEngine
from .opportunity import IdeaSpace, OpportunityEngine


# Curated seed concepts (a starting graph; real runs ingest external signals).
# Strength values are 0..1 placeholders until a live Source feeds them.
_SEED_CONCEPTS = [
    ("LLMs", None, dict(popularity=0.9, velocity=0.6, novelty=0.3, saturation=0.8)),
    ("Claude", "LLMs", dict(popularity=0.8, velocity=0.7, novelty=0.4, saturation=0.6)),
    ("GPT", "LLMs", dict(popularity=0.9, velocity=0.4, novelty=0.2, saturation=0.85)),
    ("Gemini", "LLMs", dict(popularity=0.7, velocity=0.5, novelty=0.3, saturation=0.6)),
    ("Open-source models", "LLMs", dict(popularity=0.6, velocity=0.8, novelty=0.6, saturation=0.4)),
    ("AI Agents", "LLMs", dict(popularity=0.8, velocity=0.9, novelty=0.5, saturation=0.5)),
    ("MCP", "AI Agents", dict(popularity=0.5, velocity=0.9, novelty=0.7, saturation=0.3)),
    ("Productivity", None, dict(popularity=0.8, velocity=0.4, novelty=0.1, saturation=0.7)),
    ("Military Strategy", None, dict(popularity=0.5, velocity=0.3, novelty=0.4, saturation=0.4)),
    ("Psychology", None, dict(popularity=0.7, velocity=0.4, novelty=0.2, saturation=0.6)),
    ("Biology", None, dict(popularity=0.6, velocity=0.4, novelty=0.3, saturation=0.5)),
    ("Everyday workflows", "Productivity", dict(popularity=0.6, velocity=0.6, novelty=0.2, saturation=0.6)),
]


class SeedMiner:
    def __init__(self, novelty_threshold: float = 0.9,
                 opportunity_floor: float = 0.05) -> None:
        self.graph = ConceptGraph()
        self.opp = OpportunityEngine()
        self.novelty = NoveltyEngine(threshold=novelty_threshold)
        self.opp_floor = opportunity_floor
        self._seeded = False

    def bootstrap(self) -> None:
        if self._seeded:
            return
        for label, parent, sig in _SEED_CONCEPTS:
            self.graph.add(Concept(label=label, parent=parent, **sig))
        # viewer-overlap edges (illustrative; live data would set real overlaps)
        self.graph.link("Claude", "Productivity", 0.4)
        self.graph.link("Claude", "Military Strategy", 0.25)
        self.graph.link("Claude", "Psychology", 0.3)
        self.graph.link("Open-source models", "MCP", 0.5)
        self.graph.link("AI Agents", "MCP", 0.6)
        self.graph.link("Productivity", "Everyday workflows", 0.7)
        self.graph.link("Biology", "Psychology", 0.35)
        self._seeded = True

    def mine(self, top: int = 5, max_depth: int = 3) -> List[IdeaSpace]:
        """Return ranked, novel idea spaces ready to seed the flywheel."""
        self.bootstrap()
        # 1) synthesize candidate spaces from the graph
        labels = list(self.graph.nodes.keys())
        spaces: List[str] = []
        for lbl in labels:
            nbrs = [n.label for n in self.graph.neighbours(lbl)]
            if nbrs:
                spaces += self.graph.synthesize(lbl, *nbrs, max_depth=max_depth)
        # also consider each single emerging concept as its own space
        spaces += [c.label for c in self.graph.emerging(top=8)]

        results: List[IdeaSpace] = []
        for label in dict.fromkeys(spaces):  # dedupe, preserve order
            space = self._score_space(label)
            if space is None:
                continue
            # 2) novelty gate — reject imitations
            ok, nov, nearest = self.novelty.check(label)
            if not ok:
                # too similar to a seen idea — skip (force exploration)
                continue
            space.novelty = max(space.novelty, nov)
            results.append(space)

        # 3) rank by opportunity, keep above floor
        results.sort(key=lambda s: s.score(), reverse=True)
        return [r for r in results if r.score() >= self.opp_floor][:top]

    def _score_space(self, label: str) -> Optional[IdeaSpace]:
        # derive opportunity factors from the concepts in the space
        parts = [p.strip() for p in label.split("+")]
        concepts = [self.graph.get(p) for p in parts if self.graph.get(p)]
        if not concepts:
            return None
        avg = lambda f: sum(getattr(c, f) for c in concepts) / len(concepts)
        space = IdeaSpace(
            label=label,
            novelty=avg("novelty"),
            demand=avg("popularity"),
            retention_potential=min(1.0, avg("velocity") + 0.2 * (1 - avg("saturation"))),
            creator_gap=1.0 - avg("saturation"),
            monetization=0.6 - 0.3 * avg("saturation"),
            evergreen=0.5 + 0.3 * (1 - avg("velocity")),
            sources=["seed-graph"],
        )
        self.opp.add(space)
        return space

    def register_published(self, idea_id: str, text: str) -> None:
        """Feed back a published/winning idea so future mines stay novel."""
        self.novelty.register_published(idea_id, text, label=text)

    def to_dict(self) -> dict:
        return {
            "graph": self.graph.to_dict(),
            "opportunity": self.opp.to_dict(),
        }

    def write(self, path) -> None:
        path = str(path)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)


def mine_seeds(top: int = 5) -> List[IdeaSpace]:
    m = SeedMiner()
    return m.mine(top=top)
