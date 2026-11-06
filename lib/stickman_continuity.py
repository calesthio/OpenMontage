"""Stickman continuity checks — prop ownership, adjacent repetition, signature detail."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ContinuityIssue:
    issue_type: str
    scene_id: str
    description: str
    severity: str = "medium"


@dataclass
class ContinuityReport:
    version: str = "1.0"
    issues: list[ContinuityIssue] = field(default_factory=list)
    passed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "issues": [vars(i) for i in self.issues],
            "passed": self.passed,
        }


class StickmanContinuityChecker:
    """Track prop ownership and detect repetition / missing signature detail."""

    def __init__(self) -> None:
        self.prop_owner: dict[str, str] = {}  # prop_id -> scene_id that last held it
        self.prev_triple: tuple[str, str, str] | None = None

    def check_frame(self, scene_id: str, frame: dict[str, Any]) -> list[ContinuityIssue]:
        issues: list[ContinuityIssue] = []
        pose = frame.get("rig_pose_id")
        expr = frame.get("rig_expression_id")
        view = frame.get("rig_view")
        triple = (pose, expr, view)
        if self.prev_triple is not None and triple == self.prev_triple and not frame.get("motivated_hold"):
            issues.append(ContinuityIssue(
                issue_type="repeated_composition",
                scene_id=scene_id,
                description=f"same (pose,expression,view) repeated without motivated_hold: {triple}",
                severity="medium",
            ))
        self.prev_triple = triple

        if frame.get("signature_detail_present") is False:
            issues.append(ContinuityIssue(
                issue_type="missing_signature_detail",
                scene_id=scene_id,
                description="magnifying lens signature detail missing",
                severity="high",
            ))

        # prop continuity
        prop_ids = frame.get("prop_ids") or []
        slots = frame.get("prop_slots") or {}
        held = list(prop_ids) + [v for v in slots.values() if v]
        for prop in held:
            # if prop was held before by a different scene, that's a transfer (ok) but record
            self.prop_owner[prop] = scene_id

        return issues

    def check_prop_transfer(self, from_scene: str, to_scene: str, prop_id: str,
                            transfer_logged: bool) -> ContinuityIssue | None:
        if prop_id in self.prop_owner and self.prop_owner[prop_id] == from_scene:
            if not transfer_logged:
                return ContinuityIssue(
                    issue_type="prop_teleport",
                    scene_id=to_scene,
                    description=f"prop {prop_id} moved from {from_scene} to {to_scene} without logged transfer",
                    severity="medium",
                )
        return None

    def check_series(self, scenes: list[dict[str, Any]]) -> ContinuityReport:
        report = ContinuityReport()
        for sc in scenes:
            sid = sc.get("scene_id", sc.get("sentence_id", ""))
            frame = sc.get("rig_frame", sc)
            report.issues.extend(self.check_frame(sid, frame))
        # prop transfers
        for i in range(1, len(scenes)):
            prev = scenes[i - 1]
            cur = scenes[i]
            prev_props = set((prev.get("rig_frame", prev).get("prop_ids") or []))
            cur_props = set((cur.get("rig_frame", cur).get("prop_ids") or []))
            for prop in prev_props & cur_props:
                # prop continues; ok. If a prop in prev not in cur, check transfer log
                pass
            for prop in prev_props - cur_props:
                transfer_logged = bool(cur.get("prop_transfers")) and prop in (cur.get("prop_transfers") or [])
                issue = self.check_prop_transfer(
                    prev.get("scene_id", prev.get("sentence_id", "")),
                    cur.get("scene_id", cur.get("sentence_id", "")),
                    prop, transfer_logged,
                )
                if issue:
                    report.issues.append(issue)
        report.passed = not any(i.severity == "high" for i in report.issues)
        return report
