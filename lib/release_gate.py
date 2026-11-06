"""Release Gate — P5 final publish decision for OpenMontage Factory.

Takes a QCReport (from lib.final_qc.FinalQC) and produces a GateDecision:

  * PASS  — all blocking checks PASS; no WARNINGS; release allowed.
  * WARNING — all blocking checks PASS, but one or more WARNING-level
    issues exist; release allowed but flagged for human review.
  * FAIL  — any blocking check FAIL or BLOCKED; release NOT allowed.

The gate never auto-publishes on FAIL.  It is the final hard stop before
package_draft / upload preparation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from lib.final_qc import QCReport


@dataclass
class GateDecision:
    """Outcome of the release gate evaluation."""

    decision: str  # PASS | WARNING | FAIL
    can_publish: bool
    blocking_checks: list[str] = field(default_factory=list)
    warning_checks: list[str] = field(default_factory=list)
    not_run_checks: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ReleaseGate:
    """Evaluate a QCReport and decide whether the project may proceed to
    publication preparation (package_draft)."""

    VALID_DECISIONS = ("PASS", "WARNING", "FAIL")

    def __init__(self, *, require_all_blocking_pass: bool = True) -> None:
        self.require_all_blocking_pass = require_all_blocking_pass

    def evaluate(self, report: QCReport) -> GateDecision:
        """Evaluate the report and return a GateDecision.

        Logic:
          * FAIL: any blocking check has status FAIL or BLOCKED.
          * WARNING: no blocking failures, but at least one WARNING-level
            check exists.
          * PASS: all blocking checks PASS and no warnings.
        """
        blocking_failures = report.blocking_failures
        warnings = report.warnings
        not_run = [c for c in report.checks if c.status == "NOT_RUN"]

        if blocking_failures:
            decision = "FAIL"
            can_publish = False
            reason = (
                f"{len(blocking_failures)} blocking check(s) failed: "
                + "; ".join(c.check_id for c in blocking_failures[:5])
            )
        elif warnings:
            decision = "WARNING"
            can_publish = True
            reason = (
                f"{len(warnings)} warning check(s); release allowed but "
                + "human review recommended: "
                + "; ".join(c.check_id for c in warnings[:5])
            )
        elif not_run:
            decision = "WARNING"
            can_publish = True
            reason = (
                f"{len(not_run)} check(s) could not run; release allowed "
                + "but coverage is incomplete: "
                + "; ".join(c.check_id for c in not_run[:5])
            )
        else:
            decision = "PASS"
            can_publish = True
            reason = "all blocking checks passed; no warnings"

        return GateDecision(
            decision=decision,
            can_publish=can_publish,
            blocking_checks=[c.check_id for c in blocking_failures],
            warning_checks=[c.check_id for c in warnings],
            not_run_checks=[c.check_id for c in not_run],
            summary={
                "total_checks": len(report.checks),
                "pass": sum(1 for c in report.checks if c.status == "PASS"),
                "warning": sum(1 for c in report.checks if c.status == "WARNING"),
                "fail": sum(1 for c in report.checks if c.status == "FAIL"),
                "blocked": sum(1 for c in report.checks if c.status == "BLOCKED"),
                "not_run": sum(1 for c in report.checks if c.status == "NOT_RUN"),
                "blocking_failures": len(blocking_failures),
                "warnings": len(warnings),
                "can_publish": can_publish,
            },
            reason=reason,
        )

    def gate_report_path(self, report: QCReport, output_path: str) -> None:
        """Write the gate decision as JSON to output_path (side effect)."""
        decision = self.evaluate(report)
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(decision.to_dict(), indent=2), encoding="utf-8")
