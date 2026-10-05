"""Opportunity Engine — scores IDEA SPACES, not individual videos.

Opportunity Score  (v2 spec, multiplicative):

    Novelty x Demand x RetentionPotential x CreatorGap x
    Monetization x EvergreenValue

Goal: surface *promising content spaces before they become crowded*,
instead of copying one viral video.

Each factor is a 0..1 float. A single near-zero factor zeroes the score
(consistent with a multiplicative model), so the engine refuses to chase
spaces that are novel but undemanded, or demanded but saturated.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional

FACTORS = (
    "novelty", "demand", "retention_potential",
    "creator_gap", "monetization", "evergreen",
)


@dataclass
class IdeaSpace:
    label: str
    novelty: float = 0.0
    demand: float = 0.0
    retention_potential: float = 0.0
    creator_gap: float = 0.0
    monetization: float = 0.0
    evergreen: float = 0.0
    # optional context (where the weak signals came from)
    sources: List[str] = field(default_factory=list)
    notes: str = ""

    def score(self) -> float:
        prod = 1.0
        for f in FACTORS:
            v = float(getattr(self, f))
            v = max(0.0, min(1.0, v))
            prod *= v
        return prod

    def to_dict(self) -> dict:
        d = asdict(self)
        d["score"] = round(self.score(), 5)
        return d


class OpportunityEngine:
    def __init__(self) -> None:
        self.spaces: Dict[str, IdeaSpace] = {}

    def add(self, space: IdeaSpace) -> IdeaSpace:
        self.spaces[space.label] = space
        return space

    def rank(self, top: Optional[int] = None) -> List[IdeaSpace]:
        ordered = sorted(
            self.spaces.values(),
            key=lambda s: (s.score(), s.novelty * s.creator_gap),
            reverse=True,
        )
        return ordered[:top] if top else ordered

    def recommend(self, top: int = 5) -> List[IdeaSpace]:
        """Top spaces with a usable score (>0)."""
        return [s for s in self.rank(top) if s.score() > 0.0][:top]

    def to_dict(self) -> dict:
        ranked = self.rank()
        return {
            "count": len(ranked),
            "ranked": [s.to_dict() for s in ranked],
        }
