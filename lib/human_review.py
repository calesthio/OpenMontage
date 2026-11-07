"""Human review gate (V8 §8.17).

Never publish without explicit human approval in the current task.
Review is required before:
- Publishing / uploading any video
- Releasing a version with disputed scientific claims
- Using assets with unclear or unverified licenses
- Making creative decisions that deviate from the style playbook

Integrates with lib.checkpoint (awaiting_human → completed requires
human_approved=True) and lib.state_store (requires_approval flag).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ReviewDecision:
    """Outcome of a human review gate."""

    stage: str
    project_id: str
    approved: bool
    reviewer: str | None = None
    reviewed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    reason: str = ""
    conditions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReviewGate:
    """Tracks which stages require human review and their status.

    A stage is "cleared" only when it has an explicit ReviewDecision with
    approved=True.  Unreviewed or rejected stages block downstream publish.
    """

    project_id: str
    required_stages: list[str] = field(default_factory=list)
    decisions: dict[str, ReviewDecision] = field(default_factory=dict)

    def require(self, stage: str) -> None:
        if stage not in self.required_stages:
            self.required_stages.append(stage)

    def decide(
        self,
        stage: str,
        approved: bool,
        *,
        reviewer: str | None = None,
        reason: str = "",
        conditions: list[str] | None = None,
    ) -> ReviewDecision:
        d = ReviewDecision(
            stage=stage,
            project_id=self.project_id,
            approved=approved,
            reviewer=reviewer,
            reason=reason,
            conditions=list(conditions or []),
        )
        self.decisions[stage] = d
        return d

    def is_cleared(self, stage: str) -> bool:
        d = self.decisions.get(stage)
        return d is not None and d.approved

    def pending_reviews(self) -> list[str]:
        """Stages that require review but are not yet cleared."""
        return [s for s in self.required_stages if not self.is_cleared(s)]

    def all_cleared(self) -> bool:
        return len(self.pending_reviews()) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "required_stages": self.required_stages,
            "decisions": {s: d.to_dict() for s, d in self.decisions.items()},
            "pending_reviews": self.pending_reviews(),
            "all_cleared": self.all_cleared(),
        }


def human_review_gate(
    project_id: str,
    required_stages: list[str],
    decisions: dict[str, ReviewDecision],
) -> dict[str, Any]:
    """Module-level convenience: evaluate human review gate.

    Returns {all_cleared, pending_reviews, decisions}.
    """
    gate = ReviewGate(project_id=project_id, required_stages=list(required_stages))
    gate.decisions = dict(decisions)
    return gate.to_dict()
