"""Cost tracker core: estimate, reserve, reconcile, and persist to cost_log.json.

Implements the budget governance rules from the spec:
- Every paid operation produces a preflight estimate
- The orchestrator reserves estimated budget before execution
- Budget overruns trigger pauses (in warn/cap mode)
- Actual spend is reconciled when the tool finishes or fails

Spend is also recorded without anyone calling this module: every tool call
reports its cost into the project's events.jsonl (tools/base_tool.py), and
``sync_tool_events`` turns those reports into ledger entries. ``write_checkpoint``
does that on every checkpoint, so the cost meter never depends on an agent
typing a number. Spend that no tool reports — rented GPU time, a subscription
— goes in through ``record_spend`` (or ``python -m tools.cost_tracker record``).

One budget, resolved in one place (``resolve_budget_usd``): the budget the user
approved at proposal, else the pipeline's ``orchestration.budget_default_usd``
capped by ``budget.total_usd`` in config.yaml, else ``budget.total_usd``.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from lib.config_model import BudgetMode


class EntryStatus(str, Enum):
    ESTIMATED = "estimated"
    RESERVED = "reserved"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class BudgetExceededError(Exception):
    """Raised when an operation would exceed the budget in cap mode."""
    pass


class ApprovalRequiredError(Exception):
    """Raised when an operation needs user approval before proceeding."""
    pass


COST_LOG_FILENAME = "cost_log.json"


def _marker_pipeline_type(project_dir: Path) -> Optional[str]:
    try:
        with open(project_dir / "project.json", encoding="utf-8") as handle:
            marker = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    value = marker.get("pipeline_type") if isinstance(marker, dict) else None
    return value if isinstance(value, str) and value and value != "unknown" else None


def resolve_budget_usd(
    pipeline_type: Optional[str] = None,
    *,
    approved_usd: Optional[float] = None,
    config: Any = None,
) -> tuple[float, str]:
    """The run's total budget and where it came from.

    1. ``approved_usd`` — what the user approved at proposal
       (``proposal_packet.approval.approved_budget_usd``). It replaces every
       default, in either direction.
    2. the pipeline manifest's ``orchestration.budget_default_usd``, never above
       ``budget.total_usd`` in config.yaml (the user's machine-wide ceiling).
    3. ``budget.total_usd`` in config.yaml.

    Returns ``(budget_usd, source)``; ``source`` is recorded in the cost log so
    the number on the board can always be traced back.
    """
    if approved_usd is not None:
        if approved_usd < 0:
            raise ValueError("approved_usd must not be negative")
        return float(approved_usd), "approved"
    if config is None:
        from lib.config_model import OpenMontageConfig

        config = OpenMontageConfig.load()
    ceiling = float(config.budget.total_usd)
    if pipeline_type and pipeline_type != "unknown":
        try:
            from lib.pipeline_loader import load_pipeline_readonly

            default = (
                load_pipeline_readonly(pipeline_type).get("orchestration") or {}
            ).get("budget_default_usd")
        except Exception:
            default = None
        if isinstance(default, (int, float)) and not isinstance(default, bool) and default >= 0:
            if default > ceiling:
                return ceiling, f"config.yaml budget.total_usd (caps {pipeline_type} default ${default:.2f})"
            return float(default), f"pipeline_defs/{pipeline_type}.yaml orchestration.budget_default_usd"
    return ceiling, "config.yaml budget.total_usd"


def project_cost_snapshot(
    project_dir: Path | str, *, pipeline_type: Optional[str] = None
) -> Optional[dict[str, float]]:
    """Cost snapshot for a checkpoint, derived from what the tools reported.

    Syncs the project's tool events into its ledger and returns the snapshot.
    Returns None when nothing has been spent or reserved: a zero written into
    a checkpoint would hide the asset manifest's own total on the board, which
    is the board's fallback when no spend was recorded.
    """
    project_dir = Path(project_dir)
    ledger = project_dir / COST_LOG_FILENAME
    if not ledger.exists() and not _events_with_cost(project_dir):
        return None
    tracker = CostTracker.for_project(project_dir, pipeline_type=pipeline_type)
    tracker.sync_tool_events()
    if tracker.budget_spent_usd <= 0 and tracker.budget_reserved_usd <= 0:
        return None
    return tracker.cost_snapshot()


def _events_with_cost(project_dir: Path) -> list[dict[str, Any]]:
    """Top-level tool calls in events.jsonl that reported a cost above zero.

    Nested calls (a selector delegating to a provider) are skipped: the outer
    call's finish already carries the cost, and counting both would double it.
    """
    from lib.events import read_events

    costed = []
    for event in read_events(project_dir):
        if event.get("event") != "finish" or event.get("depth"):
            continue
        cost = event.get("cost_usd")
        if isinstance(cost, (int, float)) and not isinstance(cost, bool) and cost > 0:
            costed.append(event)
    return costed


class CostTracker:
    """Tracks estimated, reserved, and actual costs for a pipeline project."""

    def __init__(
        self,
        budget_total_usd: float = 10.0,
        reserve_pct: float = 0.10,
        single_action_approval_usd: float = 0.50,
        require_approval_for_new_paid_tool: bool = True,
        mode: BudgetMode = BudgetMode.WARN,
        cost_log_path: Optional[Path] = None,
    ) -> None:
        self.budget_total_usd = budget_total_usd
        self.reserve_pct = reserve_pct
        self.single_action_approval_usd = single_action_approval_usd
        self.require_approval_for_new_paid_tool = require_approval_for_new_paid_tool
        self.mode = mode
        self.cost_log_path = cost_log_path
        self.entries: list[dict[str, Any]] = []
        self._approved_tools: set[str] = set()
        self.budget_source: Optional[str] = None

        if cost_log_path and cost_log_path.exists():
            self._load()

    @classmethod
    def for_project(
        cls,
        project_dir: Path | str,
        *,
        budget_total_usd: Optional[float] = None,
        pipeline_type: Optional[str] = None,
        config: Any = None,
    ) -> "CostTracker":
        """Tracker for one project, governed by the ``budget`` block of config.yaml.

        Persists to ``<project_dir>/cost_log.json``. On first use the budget
        comes from ``resolve_budget_usd`` — ``budget_total_usd`` if given (the
        budget the user approved at proposal), else the pipeline's default
        under the configured ceiling (``pipeline_type`` defaults to the one in
        the project's ``project.json``). Afterwards the log is authoritative,
        so use ``set_budget()`` to change it.
        """
        if config is None:
            from lib.config_model import OpenMontageConfig

            config = OpenMontageConfig.load()
        project_dir = Path(project_dir)
        budget = config.budget
        total, source = resolve_budget_usd(
            pipeline_type or _marker_pipeline_type(project_dir),
            approved_usd=budget_total_usd,
            config=config,
        )
        ledger = project_dir / COST_LOG_FILENAME
        seeded = not ledger.exists()
        tracker = cls(
            budget_total_usd=total,
            reserve_pct=budget.reserve_pct,
            single_action_approval_usd=budget.single_action_approval_usd,
            require_approval_for_new_paid_tool=budget.require_approval_for_new_paid_tool,
            mode=budget.mode,
            cost_log_path=ledger,
        )
        if seeded:
            tracker.budget_source = source
        return tracker

    def set_budget(self, budget_total_usd: float, *, source: str = "approved") -> None:
        """Change the total budget and persist it.

        The constructor's ``budget_total_usd`` only seeds a new log; once a log
        exists its recorded budget wins, so a raised or lowered budget has to
        come through here to take effect. Call it with the amount the user
        approved at the proposal gate.
        """
        if budget_total_usd < 0:
            raise ValueError("budget_total_usd must not be negative")
        self.budget_total_usd = float(budget_total_usd)
        self.budget_source = source
        self._save()

    @property
    def over_budget(self) -> bool:
        """Spend plus reservations already exceed the total budget."""
        return self.budget_remaining_usd < 0

    # ---- Budget calculations ----

    @property
    def budget_reserved_usd(self) -> float:
        return sum(
            e.get("reserved_usd", 0.0)
            for e in self.entries
            if e["status"] == EntryStatus.RESERVED.value
        )

    @property
    def budget_spent_usd(self) -> float:
        return sum(
            e.get("actual_usd", 0.0)
            for e in self.entries
            if e["status"] in (EntryStatus.COMPLETED.value, EntryStatus.FAILED.value)
        )

    @property
    def budget_remaining_usd(self) -> float:
        return self.budget_total_usd - self.budget_spent_usd - self.budget_reserved_usd

    @property
    def usable_budget_usd(self) -> float:
        """Budget minus the reserve holdback."""
        holdback = self.budget_total_usd * self.reserve_pct
        return max(0.0, self.budget_remaining_usd - holdback)

    def cost_snapshot(self) -> dict[str, float]:
        return {
            "total_spent_usd": round(self.budget_spent_usd, 4),
            "total_reserved_usd": round(self.budget_reserved_usd, 4),
            "budget_remaining_usd": round(self.budget_remaining_usd, 4),
        }

    # ---- Core operations ----

    def estimate(self, tool: str, operation: str, estimated_usd: float) -> str:
        """Record an estimate. Returns entry ID."""
        entry_id = self._new_id()
        self.entries.append({
            "id": entry_id,
            "tool": tool,
            "operation": operation,
            "status": EntryStatus.ESTIMATED.value,
            "estimated_usd": round(estimated_usd, 4),
            "reserved_usd": 0.0,
            "actual_usd": 0.0,
            "timestamp": self._now(),
        })
        self._save()
        return entry_id

    def reserve(self, entry_id: str, *, approved: bool = False) -> None:
        """Reserve budget for an estimated entry.

        Raises BudgetExceededError in cap mode, or ApprovalRequiredError
        when the action exceeds the single-action approval threshold or is
        the first paid use of a tool.

        ``approved=True`` records that the user explicitly approved THIS
        action. It clears both approval gates (and approves the tool for later
        paid calls) so an approved action can actually be reserved; it never
        lifts the cap-mode budget limit.
        """
        entry = self._find(entry_id)
        self._require_status(entry, EntryStatus.ESTIMATED, "reserve")
        estimated = entry["estimated_usd"]

        if approved:
            entry["approved"] = True
            if estimated > 0:
                self._approved_tools.add(entry["tool"])

        # Check single-action approval threshold
        if estimated > self.single_action_approval_usd and not approved:
            if self.mode != BudgetMode.OBSERVE:
                raise ApprovalRequiredError(
                    f"Action costs ${estimated:.2f}, exceeds "
                    f"single-action threshold ${self.single_action_approval_usd:.2f}. "
                    f"Ask the user, then call reserve(entry_id, approved=True)."
                )

        # Check new paid tool approval
        if self.require_approval_for_new_paid_tool and estimated > 0:
            if entry["tool"] not in self._approved_tools:
                if self.mode != BudgetMode.OBSERVE:
                    raise ApprovalRequiredError(
                        f"First paid use of tool {entry['tool']!r} requires approval. "
                        f"Ask the user, then call approve_tool({entry['tool']!r}) "
                        f"or reserve(entry_id, approved=True)."
                    )

        # Check budget
        if estimated > self.usable_budget_usd:
            message = (
                f"Reservation of ${estimated:.2f} exceeds usable budget "
                f"${self.usable_budget_usd:.2f}"
            )
            if self.mode == BudgetMode.CAP:
                raise BudgetExceededError(message)
            if self.mode == BudgetMode.WARN:
                entry["budget_warning"] = True
                entry["budget_warning_message"] = message

        entry["status"] = EntryStatus.RESERVED.value
        entry["reserved_usd"] = estimated
        entry["timestamp"] = self._now()
        self._save()

    def approve_tool(self, tool: str) -> None:
        """Mark a tool as approved for paid operations."""
        self._approved_tools.add(tool)
        self._save()

    def reconcile(self, entry_id: str, actual_usd: float, success: bool = True) -> None:
        """Reconcile actual spend after tool execution."""
        entry = self._find(entry_id)
        self._require_status(entry, EntryStatus.RESERVED, "reconcile")
        entry["status"] = EntryStatus.COMPLETED.value if success else EntryStatus.FAILED.value
        entry["actual_usd"] = round(actual_usd, 4)
        entry["reserved_usd"] = 0.0
        entry["timestamp"] = self._now()
        self._save()

    def refund(self, entry_id: str) -> None:
        """Cancel a reservation without executing."""
        entry = self._find(entry_id)
        self._require_status(entry, EntryStatus.RESERVED, "refund")
        entry["status"] = EntryStatus.REFUNDED.value
        entry["reserved_usd"] = 0.0
        entry["timestamp"] = self._now()
        self._save()

    # ---- Spend that does not go through estimate -> reserve -> reconcile ----

    def record_spend(
        self,
        tool: str,
        operation: str,
        actual_usd: float,
        *,
        details: Optional[str] = None,
        source: str = "external",
    ) -> str:
        """Record money that was spent outside a tool call. Returns the entry id.

        For cost no tool reports: rented GPU time (``tool="vastai_gpu"``,
        ``operation="RTX 4090, 31 min at $0.40/h"``), a per-run subscription
        share, a manual purchase. The entry is written ``completed`` straight
        away — there is nothing to reserve after the fact.
        """
        if actual_usd < 0:
            raise ValueError("actual_usd must not be negative")
        entry_id = self._new_id()
        entry: dict[str, Any] = {
            "id": entry_id,
            "tool": tool,
            "operation": operation,
            "status": EntryStatus.COMPLETED.value,
            "estimated_usd": 0.0,
            "reserved_usd": 0.0,
            "actual_usd": round(actual_usd, 4),
            "timestamp": self._now(),
            "source": source,
        }
        if details:
            entry["details"] = details
        self.entries.append(entry)
        self._save()
        return entry_id

    def record_rental(
        self, provider: str, hours: float, usd_per_hour: float, *, details: Optional[str] = None
    ) -> str:
        """Record rented compute time (GPU instance, cloud VM) as spend."""
        if hours < 0 or usd_per_hour < 0:
            raise ValueError("hours and usd_per_hour must not be negative")
        return self.record_spend(
            provider,
            f"rental {hours:.3f} h at ${usd_per_hour:.4f}/h",
            hours * usd_per_hour,
            details=details,
            source="rental",
        )

    def sync_tool_events(self, project_dir: Optional[Path | str] = None) -> int:
        """Add the cost every tool call reported to the ledger. Returns how many.

        Reads ``events.jsonl`` next to the cost log (or in ``project_dir``).
        Idempotent: each call is keyed by its ``call_id``. A paid call that was
        ALSO taken through estimate/reserve/reconcile is matched to that entry
        (same tool, same amount) instead of being counted twice.
        """
        if project_dir is None:
            if self.cost_log_path is None:
                return 0
            project_dir = self.cost_log_path.parent
        events = _events_with_cost(Path(project_dir))
        if not events:
            return 0
        seen = {e.get("call_id") for e in self.entries if e.get("call_id")}
        added = 0
        changed = False
        for event in events:
            call_id = event.get("call_id") or f"legacy:{event.get('ts')}:{event.get('tool')}"
            if call_id in seen:
                continue
            seen.add(call_id)
            cost = round(float(event["cost_usd"]), 4)
            tool = str(event.get("tool") or "unknown")
            match = next(
                (
                    e for e in self.entries
                    if not e.get("call_id")
                    and e.get("tool") == tool
                    and e.get("status") == EntryStatus.COMPLETED.value
                    and e.get("source") is None
                    and abs(float(e.get("actual_usd", 0.0)) - cost) < 0.00005
                ),
                None,
            )
            changed = True
            if match is not None:
                match["call_id"] = call_id  # already counted by reconcile()
                continue
            operation = "tool call"
            if event.get("scene_id") is not None:
                operation = f"tool call (scene {event['scene_id']})"
            self.entries.append({
                "id": self._new_id(),
                "tool": tool,
                "operation": operation,
                "status": (
                    EntryStatus.COMPLETED.value
                    if event.get("success") is not False
                    else EntryStatus.FAILED.value
                ),
                "estimated_usd": 0.0,
                "reserved_usd": 0.0,
                "actual_usd": cost,
                "timestamp": str(event.get("ts") or self._now()),
                "source": "tool_event",
                "call_id": call_id,
            })
            added += 1
        if changed:
            self._save()
        return added

    # ---- Reference-driven estimation ----

    def estimate_from_reference(
        self,
        video_analysis_brief: dict,
        target_duration_seconds: int,
        tool_plan: dict,
    ) -> dict:
        """Estimate production cost based on reference analysis + target duration.

        Args:
            video_analysis_brief: The VideoAnalysisBrief artifact from video analysis
            target_duration_seconds: How long the output video should be
            tool_plan: Which tools will be used for each asset type, e.g.:
                {
                    "image_generation": {"tool": "flux_fal", "cost_per_unit": 0.05},
                    "video_generation": {"tool": "kling_fal", "cost_per_unit": 0.30,
                                         "clip_duration_seconds": 5},
                    "tts": {"tool": "elevenlabs_tts", "cost_per_word": 0.00003},
                    "music": {"tool": "music_gen", "cost_per_track": 0.10},
                }

        Returns:
            Itemized cost breakdown with line items, total, sample cost, and assumptions.
        """
        structure = video_analysis_brief.get("structure_analysis", {})
        pacing = structure.get("pacing_profile", {})
        narration = video_analysis_brief.get("narration_transcript", {})
        ref_duration = video_analysis_brief.get("source", {}).get("duration_seconds", 60)
        pacing_style = pacing.get("pacing_style", "steady_educational")

        # ── Scene count estimation ──
        # Don't just scale linearly — use the PACING DENSITY from the reference.
        # A music video with 8 scenes in 162s has ~3 cuts/min.
        # Scaling to 60s should PRESERVE that cut rate, not reduce scene count.
        ref_scenes = structure.get("total_scenes", 8)
        if ref_duration > 0:
            cuts_per_minute = ref_scenes / (ref_duration / 60)
        else:
            cuts_per_minute = 4.0  # default: moderate pacing

        # Apply pacing-aware minimums (a fast-cut video doesn't become a slideshow)
        min_scenes_by_pacing = {
            "rapid_fire": 10,
            "dynamic_social": 8,
            "steady_educational": 5,
            "slow_contemplative": 3,
            "variable": 6,
        }
        min_scenes = min_scenes_by_pacing.get(pacing_style, 5)

        # Scene count = max(pacing-density-based, minimum for style)
        density_based_scenes = round(cuts_per_minute * (target_duration_seconds / 60))
        estimated_scenes = max(min_scenes, density_based_scenes)

        # ── Narration word count ──
        ref_word_count = narration.get("word_count", 0)
        if ref_duration > 0 and ref_word_count > 0:
            actual_wpm = (ref_word_count / ref_duration) * 60
        else:
            actual_wpm = 150  # default conversational pace
        estimated_words = round(actual_wpm * (target_duration_seconds / 60))

        # ── Motion ratio from reference ──
        scenes_list = structure.get("scenes", [])
        motion_ratio, motion_basis = self._estimate_motion_ratio(
            video_analysis_brief=video_analysis_brief,
            scenes_list=scenes_list,
            pacing_style=pacing_style,
        )

        estimated_motion_scenes = (
            max(1, round(estimated_scenes * motion_ratio))
            if motion_ratio > 0
            else 0
        )
        estimated_still_scenes = estimated_scenes - estimated_motion_scenes

        # ── Video clip coverage ──
        # Video gen tools produce clips of limited duration (typically 5-10s).
        # A 60s video with motion needs enough clips to COVER the duration,
        # not just 1 per scene.
        vid_plan = tool_plan.get("video_generation", {})
        clip_duration = vid_plan.get("clip_duration_seconds", 5) if vid_plan else 5
        motion_seconds = target_duration_seconds * motion_ratio
        clips_needed_for_coverage = max(
            estimated_motion_scenes,
            round(motion_seconds / clip_duration)
        ) if vid_plan else 0

        # ── Retry/waste buffer ──
        # Not every generation succeeds or looks good. Add a buffer.
        retry_multiplier = 1.3  # ~30% extra for retries and rejected outputs

        # ── Image count ──
        # Images per scene depends on visual variety needs:
        # - Explainer: 1-2 images per scene
        # - Music video / cinematic: 2-3 images per scene (mood shifts, variety)
        images_per_scene = 2.0 if pacing_style in ("dynamic_social", "rapid_fire") else 1.5
        estimated_images = max(
            estimated_scenes,
            round(estimated_scenes * images_per_scene)
        )

        # Build line items
        line_items = []
        assumptions = []

        assumptions.append(
            f"{estimated_scenes} scenes (reference has {cuts_per_minute:.1f} cuts/min, "
            f"pacing: {pacing_style})"
        )
        assumptions.append(motion_basis)

        # Image generation
        img_plan = tool_plan.get("image_generation", {})
        if img_plan:
            img_count = round(estimated_images * retry_multiplier)
            unit_cost = img_plan.get("cost_per_unit", 0.05)
            line_items.append({
                "category": "image_generation",
                "provider": img_plan.get("tool", "unknown"),
                "quantity": img_count,
                "unit_cost_usd": unit_cost,
                "total_usd": round(img_count * unit_cost, 4),
                "basis": (
                    f"~{images_per_scene:.0f} images/scene x {estimated_scenes} scenes "
                    f"+ {round((retry_multiplier - 1) * 100)}% retry buffer"
                ),
            })

        # Video generation
        if vid_plan and clips_needed_for_coverage > 0:
            clip_count = round(clips_needed_for_coverage * retry_multiplier)
            unit_cost = vid_plan.get("cost_per_unit", 0.30)
            line_items.append({
                "category": "video_generation",
                "provider": vid_plan.get("tool", "unknown"),
                "quantity": clip_count,
                "unit_cost_usd": unit_cost,
                "total_usd": round(clip_count * unit_cost, 4),
                "basis": (
                    f"{motion_seconds:.0f}s of motion / {clip_duration}s clips = "
                    f"{clips_needed_for_coverage} clips + retry buffer"
                ),
            })
            assumptions.append(
                f"{round(motion_ratio * 100)}% motion ratio → "
                f"{motion_seconds:.0f}s needs {clips_needed_for_coverage} clips "
                f"({clip_duration}s each)"
            )

        # TTS narration
        tts_plan = tool_plan.get("tts", {})
        if tts_plan and estimated_words > 10:
            cost_per_word = tts_plan.get("cost_per_word", 0.00003)
            tts_cost = round(estimated_words * cost_per_word, 4)
            line_items.append({
                "category": "tts_narration",
                "provider": tts_plan.get("tool", "unknown"),
                "quantity": estimated_words,
                "unit_cost_usd": cost_per_word,
                "total_usd": tts_cost,
                "basis": f"Narration at {round(actual_wpm)} WPM = ~{estimated_words} words",
            })
            assumptions.append(
                f"Narration at {round(actual_wpm)} WPM = ~{estimated_words} words "
                f"for {target_duration_seconds} seconds"
            )

        # Music
        music_plan = tool_plan.get("music", {})
        if music_plan:
            music_cost = music_plan.get("cost_per_track", 0.0)
            line_items.append({
                "category": "music",
                "provider": music_plan.get("tool", "unknown"),
                "quantity": 1,
                "unit_cost_usd": music_cost,
                "total_usd": music_cost,
                "basis": "1 background music track",
            })

        subtotal = round(sum(item["total_usd"] for item in line_items), 4)

        # ── Cost range instead of single number ──
        # Low: everything works first try. High: retry buffer fully consumed.
        low_total = round(subtotal / retry_multiplier, 4)
        high_total = round(subtotal * 1.15, 4)  # 15% above retry-buffered estimate

        # Sample cost: 2 scenes worth of assets (hook + 1 middle)
        sample_scenes = 2
        sample_fraction = sample_scenes / max(estimated_scenes, 1)
        sample_cost = round(subtotal * sample_fraction, 4)

        # Confidence based on how much data we have
        if scenes_list and narration.get("word_count", 0) > 0:
            confidence = "high"
        elif scenes_list or narration.get("word_count", 0) > 0:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "line_items": line_items,
            "total_usd": subtotal,
            "total_range_usd": {"low": low_total, "high": high_total},
            "sample_cost_usd": sample_cost,
            "confidence": confidence,
            "assumptions": assumptions,
            "estimated_scenes": estimated_scenes,
            "estimated_images": estimated_images,
            "estimated_clips": clips_needed_for_coverage,
            "estimated_words": estimated_words,
            "motion_ratio": round(motion_ratio, 2),
            "cuts_per_minute": round(cuts_per_minute, 1),
            "target_duration_seconds": target_duration_seconds,
        }

    def _estimate_motion_ratio(
        self,
        *,
        video_analysis_brief: dict,
        scenes_list: list[dict[str, Any]],
        pacing_style: str,
    ) -> tuple[float, str]:
        """Estimate how much of the target treatment truly needs motion."""
        motion_weights = {
            "animation": 1.0,
            "b_roll": 1.0,
            "stock_footage": 1.0,
            "product_shot": 0.9,
            "transition": 0.6,
            "screen_recording": 0.45,
            "talking_head": 0.35,
            "diagram": 0.25,
            "chart": 0.25,
            "text_card": 0.2,
        }
        classified_weights = [
            motion_weights[visual_type]
            for scene in scenes_list
            if (visual_type := scene.get("visual_type")) in motion_weights
        ]
        if classified_weights:
            ratio = sum(classified_weights) / len(classified_weights)
            unknown_count = max(0, len(scenes_list) - len(classified_weights))
            if unknown_count:
                fallback_ratio, _ = self._fallback_motion_ratio(
                    video_analysis_brief=video_analysis_brief,
                    pacing_style=pacing_style,
                )
                ratio = (
                    (sum(classified_weights) + fallback_ratio * unknown_count)
                    / len(scenes_list)
                )
                basis = (
                    "motion ratio blended from classified scene types and "
                    "reference-style fallback for unclassified scenes"
                )
            else:
                basis = "motion ratio derived from classified scene types"
            return round(min(max(ratio, 0.0), 0.95), 2), basis

        return self._fallback_motion_ratio(
            video_analysis_brief=video_analysis_brief,
            pacing_style=pacing_style,
        )

    def _fallback_motion_ratio(
        self,
        *,
        video_analysis_brief: dict,
        pacing_style: str,
    ) -> tuple[float, str]:
        """Fallback heuristic for motion ratio before scene vision enrichment."""
        source_type = video_analysis_brief.get("source", {}).get("type", "")
        replication = video_analysis_brief.get("replication_guidance", {})
        motion_required = bool(replication.get("motion_required"))
        suggested_pipeline = replication.get("suggested_pipeline", "")

        base_by_pacing = {
            "rapid_fire": 0.8,
            "dynamic_social": 0.65,
            "steady_educational": 0.35,
            "slow_contemplative": 0.2,
            "variable": 0.5,
        }
        ratio = base_by_pacing.get(pacing_style, 0.5)

        if source_type in ("shorts", "instagram", "tiktok"):
            ratio = max(ratio, 0.7)
        if motion_required:
            ratio = max(ratio, 0.6)
        if suggested_pipeline == "cinematic":
            ratio = max(ratio, 0.55)

        ratio = round(min(max(ratio, 0.1), 0.95), 2)
        basis = (
            "motion ratio inferred from pacing/style because scene visual types "
            "have not been enriched yet"
        )
        return ratio, basis

    # ---- Persistence ----

    def _save(self) -> None:
        if self.cost_log_path is None:
            return
        data: dict[str, Any] = {
            "version": "1.0",
            "budget_total_usd": self.budget_total_usd,
            "budget_reserved_usd": round(self.budget_reserved_usd, 4),
            "budget_spent_usd": round(self.budget_spent_usd, 4),
            "approved_tools": sorted(self._approved_tools),
            "entries": self.entries,
        }
        if self.budget_source:
            data["metadata"] = {"budget_source": self.budget_source}
        self.cost_log_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic swap: every estimate/reserve/reconcile rewrites the whole log,
        # and a crash mid-write must not leave a truncated ledger behind.
        tmp_path = self.cost_log_path.with_name(self.cost_log_path.name + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, self.cost_log_path)

    def _load(self) -> None:
        try:
            with open(self.cost_log_path, encoding="utf-8") as f:  # type: ignore[arg-type]
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Cost log {self.cost_log_path} is not valid JSON ({exc}). It is "
                f"the spend ledger, so it is not reset automatically: repair it "
                f"or move it aside before tracking further spend."
            ) from exc
        if not isinstance(data, dict):
            raise ValueError(f"Cost log {self.cost_log_path} must be a JSON object")
        self.entries = data.get("entries", [])
        self.budget_total_usd = data.get("budget_total_usd", self.budget_total_usd)
        self._approved_tools = set(data.get("approved_tools", []))
        metadata = data.get("metadata")
        if isinstance(metadata, dict) and isinstance(metadata.get("budget_source"), str):
            self.budget_source = metadata["budget_source"]

    # ---- Helpers ----

    def _find(self, entry_id: str) -> dict[str, Any]:
        for entry in self.entries:
            if entry["id"] == entry_id:
                return entry
        raise KeyError(f"Cost entry {entry_id!r} not found")

    @staticmethod
    def _require_status(
        entry: dict[str, Any], expected: EntryStatus, operation: str
    ) -> None:
        if entry["status"] != expected.value:
            raise ValueError(
                f"Cannot {operation} cost entry {entry['id']!r} with status "
                f"{entry['status']!r}; expected {expected.value!r}"
            )

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Command line: the ledger without writing Python.
#
#   python -m tools.cost_tracker show   <project-id>
#   python -m tools.cost_tracker sync   <project-id>
#   python -m tools.cost_tracker budget <project-id> --usd 0.64
#   python -m tools.cost_tracker record <project-id> --tool vastai_gpu \
#       --hours 0.52 --rate 0.40 --details "RTX 4090, assets stage"
#   python -m tools.cost_tracker record <project-id> --tool stock_license \
#       --usd 1.50 --operation "one licensed clip"
# ---------------------------------------------------------------------------


def _project_dir(project: str) -> Path:
    from lib.paths import PROJECTS_DIR

    candidate = Path(project)
    project_dir = candidate if candidate.is_dir() else PROJECTS_DIR / project
    if not project_dir.is_dir():
        raise SystemExit(f"cost_tracker: no project directory for {project!r} ({project_dir})")
    return project_dir


def main(argv: Optional[list[str]] = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tools.cost_tracker", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("show", "print the ledger summary (syncs tool events first)"),
        ("sync", "add the cost tool calls reported in events.jsonl to the ledger"),
    ):
        sub.add_parser(name, help=help_text).add_argument("project")
    p_budget = sub.add_parser("budget", help="set the run's total budget (the amount the user approved)")
    p_budget.add_argument("project")
    p_budget.add_argument("--usd", type=float, required=True)
    p_record = sub.add_parser("record", help="record spend no tool reports (rented GPU time, a purchase)")
    p_record.add_argument("project")
    p_record.add_argument("--tool", required=True, help="what was paid for, e.g. vastai_gpu")
    p_record.add_argument("--usd", type=float, help="amount spent")
    p_record.add_argument("--hours", type=float, help="rented time (use with --rate)")
    p_record.add_argument("--rate", type=float, help="USD per hour (use with --hours)")
    p_record.add_argument("--operation", default=None)
    p_record.add_argument("--details", default=None)
    args = parser.parse_args(argv)

    tracker = CostTracker.for_project(_project_dir(args.project))
    if args.command == "budget":
        tracker.set_budget(args.usd)
    elif args.command == "record":
        if args.hours is not None and args.rate is not None:
            tracker.record_rental(args.tool, args.hours, args.rate, details=args.details)
        elif args.usd is not None:
            tracker.record_spend(
                args.tool, args.operation or "manual entry", args.usd, details=args.details
            )
        else:
            parser.error("record needs --usd, or --hours together with --rate")
    synced = tracker.sync_tool_events()
    summary = {
        "project": str(tracker.cost_log_path.parent.name) if tracker.cost_log_path else None,
        "budget_total_usd": tracker.budget_total_usd,
        "budget_source": tracker.budget_source,
        "mode": tracker.mode.value,
        "over_budget": tracker.over_budget,
        "tool_events_synced": synced,
        "entries": len(tracker.entries),
        **tracker.cost_snapshot(),
    }
    by_tool: dict[str, float] = {}
    for entry in tracker.entries:
        if entry["status"] in (EntryStatus.COMPLETED.value, EntryStatus.FAILED.value):
            by_tool[entry["tool"]] = round(
                by_tool.get(entry["tool"], 0.0) + float(entry.get("actual_usd", 0.0)), 4
            )
    summary["spent_by_tool"] = dict(sorted(by_tool.items(), key=lambda kv: -kv[1]))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
