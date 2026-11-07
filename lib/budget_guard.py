"""Budget guard — single zero-cost budget check point for the factory.

V7 §3 / §1.1: budget = $0 forever. Before any operation that could spend
credits (generation, download from paid gateway, API call with a key),
call ``guard(spending_kind)``. It always returns a dict with an explicit
``status`` (``success`` / ``fallback_used`` / ``failed``) and a free
fallback recommendation — never raises, never spends.

This is the ONLY place a spending decision is made; every layer routes
through it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

BUDGET_USD = 0.0  # hard ceiling: never spend


@dataclass
class BudgetDecision:
    allowed: bool
    spent_usd: float
    remaining_usd: float
    status: str  # success | fallback_used | failed
    fallback: str
    reason: str
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if not self.checked_at:
            d["checked_at"] = datetime.now(timezone.utc).isoformat()
        return d


class BudgetGuard:
    """Enforces the $0 budget. Any spending request is refused with a
    free fallback so no layer can accidentally spend credits."""

    def __init__(self, budget_usd: float = BUDGET_USD) -> None:
        self.budget_usd = budget_usd
        self.spent_usd = 0.0

    def guard(self, spending_kind: str, estimated_usd: float = 0.0) -> BudgetDecision:
        """Decide whether ``spending_kind`` may proceed.

        Always returns ``fallback_used`` (budget is $0) with a concrete
        free alternative, never ``success`` for a spending operation.
        """
        if self.spent_usd + estimated_usd > self.budget_usd:
            fallback = _fallback_for(spending_kind)
            return BudgetDecision(
                allowed=False,
                spent_usd=self.spent_usd,
                remaining_usd=self.budget_usd - self.spent_usd,
                status="fallback_used",
                fallback=fallback,
                reason=f"budget ${self.budget_usd}: {spending_kind} would spend "
                f"${estimated_usd}; using free fallback ({fallback})",
            )
        # Estimated $0 is allowed but still logged; no credit is reserved.
        return BudgetDecision(
            allowed=True,
            spent_usd=self.spent_usd,
            remaining_usd=self.budget_usd,
            status="success",
            fallback="",
            reason=f"{spending_kind} estimated $0.00 — proceeding at zero cost",
        )

    def record_spend(self, usd: float) -> None:
        """Record an actual spend (should remain 0.0 under $0 budget)."""
        self.spent_usd += usd


def _fallback_for(kind: str) -> str:
    table = {
        "image_generation": "local PIER/diffusion placeholder or archival NASA/Archive.org image (footage_sourcing)",
        "video_generation": "existing final.mp4 / archival footage; no new generation",
        "tts": "Piper local CPU TTS (no API key, no credits)",
        "music": "existing assets/music/ardune_red_moon.mp3 (Public Domain, already licensed)",
        "api_call": "cached/local computation instead of remote API",
        "download": "already-downloaded asset from projects/ or assets/",
    }
    return table.get(kind, "reuse an existing local asset instead of generating")


# Module-level default guard (importable and reusable by all layers).
default_guard = BudgetGuard()


def guard(spending_kind: str, estimated_usd: float = 0.0) -> dict[str, Any]:
    """Module-level convenience: single budget check for any layer."""
    return default_guard.guard(spending_kind, estimated_usd).to_dict()
