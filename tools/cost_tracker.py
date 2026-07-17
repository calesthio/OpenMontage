"""Cost tracker core: estimate, reserve, reconcile, and persist to cost_log.json.

Implements the budget governance rules from the spec:
- Every paid operation produces a preflight estimate
- The budget gate reserves estimated budget before execution
- Budget overruns are blocked (cap) or flagged (warn)
- Actual spend is reconciled when the tool finishes or fails

Enforcement is wired in via lib/budget_gate.py, which is called from
BaseTool's execute() wrapper. This module is the ledger; it does not know
about tools or providers.

Daily buckets
-------------
`total_usd` is a per-CALENDAR-DAY cap, not a lifetime one. Every entry carries
an immutable `budget_date` (YYYY-MM-DD in the configured timezone) assigned
when the entry is created and never recomputed. A day's available budget is
derived only from that day's spend and that day's unresolved reservations, so
a reservation opened at 23:59 keeps consuming its own day's bucket after
midnight and never leaks into the new day. History is never rewritten or
cleared to free budget.

Three independent controls
--------------------------
`mode` governs the AGGREGATE daily total ONLY:
  observe - record, never block
  warn    - flag an over-budget reservation, proceed (holdback-aware)
  cap     - block when spent(day) + reserved(day) + estimated > total_usd

`single_action_approval_usd` and `require_approval_for_new_paid_tool` are
SEPARATE, explicitly configured safeguards. They are evaluated independently
of `mode` -- set them to None/0/False to disable. They were previously
coupled to `mode != OBSERVE`, which made `cap` implicitly inherit warn's
"raise on first paid tool use" behavior; that coupling is removed.

Concurrency
-----------
Every public operation runs inside _transaction(): an in-process reentrant
lock plus a cross-process OS file lock, inside which the ledger is RELOADED
from disk before the bucket is computed and atomically saved afterwards.
Reloading under the lock is what makes concurrent processes safe -- in-memory
state cannot be trusted when another process may have written since.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator, Optional

from lib.config_model import BudgetMode
from lib.ledger_lock import ledger_lock

# Comparisons are made against values rounded to 4dp; this tolerance keeps an
# exact-cap request (estimated == remaining) on the allowed side of the line
# rather than losing it to float representation error.
_EPSILON = 1e-6


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


class CostLogCorruptError(Exception):
    """Raised when the persisted cost log exists but cannot be read.

    Callers must treat this as fail-closed. An unreadable ledger means
    accumulated spend is unknown, and unknown spend must never be allowed to
    proceed to a paid provider.
    """
    pass


class BudgetPeriodError(Exception):
    """Raised when the configured budget period/timezone cannot be honoured."""
    pass


class CostTracker:
    """Tracks estimated, reserved, and actual costs against a daily budget.

    Safe across threads AND processes: every public operation reloads the
    ledger from disk inside a cross-process file lock before computing the
    day's bucket, so two callers cannot independently consume the same
    remaining daily budget.
    """

    def __init__(
        self,
        budget_total_usd: float = 10.0,
        reserve_pct: float = 0.10,
        single_action_approval_usd: Optional[float] = 0.50,
        require_approval_for_new_paid_tool: bool = True,
        mode: BudgetMode = BudgetMode.WARN,
        cost_log_path: Optional[Path] = None,
        period: str = "daily",
        tz_name: str = "system_local",
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        if period != "daily":
            raise BudgetPeriodError(
                f"budget.period={period!r} is not supported; only 'daily' is "
                f"implemented. Refusing to proceed (fail closed) rather than "
                f"silently applying daily semantics to a different period."
            )
        self.budget_total_usd = budget_total_usd
        self.reserve_pct = reserve_pct
        self.single_action_approval_usd = single_action_approval_usd
        self.require_approval_for_new_paid_tool = require_approval_for_new_paid_tool
        self.mode = mode
        self.cost_log_path = cost_log_path
        self.period = period
        self.tz_name = tz_name
        self._tzinfo = self._resolve_tz(tz_name)
        self._clock = clock or self._default_clock
        self.entries: list[dict[str, Any]] = []
        self._approved_tools: set[str] = set()
        self._overrun_dates: set[str] = set()
        # Reentrant: _transaction() is entered once per public op, and the
        # helpers it calls must not try to re-acquire the cross-process lock
        # (msvcrt byte locks are not reentrant across fds).
        self._lock = threading.RLock()

        if cost_log_path and cost_log_path.exists():
            with self._lock:
                self._load()

    # ---- Clock / period ----

    @staticmethod
    def _resolve_tz(tz_name: str):
        if tz_name == "system_local":
            return None  # means: use the system local offset
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(tz_name)
        except Exception as exc:
            raise BudgetPeriodError(
                f"budget.timezone={tz_name!r} could not be resolved ({exc}). "
                f"Refusing to proceed (fail closed): the daily boundary must be "
                f"unambiguous. Use 'system_local' or a valid IANA name."
            ) from exc

    def _default_clock(self) -> datetime:
        if self._tzinfo is None:
            return datetime.now().astimezone()
        return datetime.now(self._tzinfo)

    def current_budget_date(self) -> str:
        """Today's bucket key (YYYY-MM-DD) in the configured timezone."""
        return self._clock().date().isoformat()

    def _entry_date(self, entry: dict[str, Any]) -> str:
        """The entry's immutable bucket key.

        Legacy v1.0 rows have no budget_date; derive one from the recorded
        timestamp READ-ONLY. Prior-day history is never rewritten.
        """
        existing = entry.get("budget_date")
        if existing:
            return str(existing)
        raw = entry.get("timestamp")
        try:
            parsed = datetime.fromisoformat(str(raw))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            local = (
                parsed.astimezone() if self._tzinfo is None
                else parsed.astimezone(self._tzinfo)
            )
            return local.date().isoformat()
        except (TypeError, ValueError) as exc:
            raise CostLogCorruptError(
                f"Cost entry {entry.get('id')!r} has neither a budget_date nor a "
                f"parseable timestamp ({raw!r}); its day's spend cannot be "
                f"determined. Refusing to proceed (fail closed)."
            ) from exc

    # ---- Budget calculations (per-day) ----

    def reserved_on(self, budget_date: str) -> float:
        return sum(
            e.get("reserved_usd", 0.0)
            for e in self.entries
            if e["status"] == EntryStatus.RESERVED.value
            and self._entry_date(e) == budget_date
        )

    def spent_on(self, budget_date: str) -> float:
        return sum(
            e.get("actual_usd", 0.0)
            for e in self.entries
            if e["status"] in (EntryStatus.COMPLETED.value, EntryStatus.FAILED.value)
            and self._entry_date(e) == budget_date
        )

    def remaining_on(self, budget_date: str) -> float:
        return self.budget_total_usd - self.spent_on(budget_date) - self.reserved_on(budget_date)

    def is_overrun(self, budget_date: str) -> bool:
        """True once a day's actual spend has breached its reservation/cap."""
        return budget_date in self._overrun_dates

    # ---- Today-scoped conveniences (backwards-compatible property names) ----

    @property
    def budget_reserved_usd(self) -> float:
        return self.reserved_on(self.current_budget_date())

    @property
    def budget_spent_usd(self) -> float:
        return self.spent_on(self.current_budget_date())

    @property
    def budget_remaining_usd(self) -> float:
        return self.remaining_on(self.current_budget_date())

    @property
    def usable_budget_usd(self) -> float:
        """Today's budget minus the reserve holdback (warn-mode planning only)."""
        holdback = self.budget_total_usd * self.reserve_pct
        return max(0.0, self.budget_remaining_usd - holdback)

    def cost_snapshot(self) -> dict[str, Any]:
        today = self.current_budget_date()
        return {
            "budget_date": today,
            "total_spent_usd": round(self.spent_on(today), 4),
            "total_reserved_usd": round(self.reserved_on(today), 4),
            "budget_remaining_usd": round(self.remaining_on(today), 4),
            "overrun": self.is_overrun(today),
        }

    # ---- Transaction ----

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        """Serialize a full read-modify-write across threads and processes.

        Reload happens INSIDE the lock: another process may have reserved since
        we last read, and a stale in-memory bucket is exactly how two callers
        independently spend the same remaining budget.
        """
        with self._lock:
            if self.cost_log_path is None:
                yield  # in-memory tracker (tests): no file, nothing to lock
                return
            with ledger_lock(self.cost_log_path):
                if self.cost_log_path.exists():
                    self._load()
                yield

    # ---- Core operations ----

    def estimate(self, tool: str, operation: str, estimated_usd: float) -> str:
        """Record an estimate and stamp its immutable budget_date.

        The date is assigned here, at entry creation, and never recomputed --
        that is what keeps a reservation opened at 23:59 bound to its own day.
        """
        with self._transaction():
            entry_id = self._new_id()
            self.entries.append({
                "id": entry_id,
                "tool": tool,
                "operation": operation,
                "status": EntryStatus.ESTIMATED.value,
                # Immutable. Assigned once, never recalculated on reconcile.
                "budget_date": self.current_budget_date(),
                # Never record a negative cost: a provider or estimator that
                # returns one must not be able to credit the ledger.
                "estimated_usd": round(max(0.0, estimated_usd), 4),
                "reserved_usd": 0.0,
                "actual_usd": 0.0,
                "timestamp": self._now(),
            })
            self._save()
            return entry_id

    def reserve(self, entry_id: str) -> None:
        """Reserve budget for an estimated entry, before the paid call runs.

        Three independent checks, in order:

        1. single_action_approval_usd -- independent safeguard, evaluated
           regardless of `mode`. None or <= 0 disables it.
        2. require_approval_for_new_paid_tool -- independent safeguard,
           evaluated regardless of `mode`. False disables it.
        3. `mode` -- governs the aggregate total budget ONLY.
           cap:     block if spent + reserved + estimated > total_usd.
                    An exact-cap request (estimated == remaining) is ALLOWED.
                    The reserve_pct holdback does not apply -- cap enforces the
                    true aggregate the user configured, nothing tighter.
           warn:    flag and proceed, measured against the holdback-aware
                    usable budget (unchanged pre-existing semantics).
           observe: record only.

        The check is made against the entry's OWN budget_date bucket, not
        today's -- so a reservation stamped 23:59 is measured against that day
        even if reserve() runs a moment after midnight.

        Raises ApprovalRequiredError or BudgetExceededError. The entry is left
        ESTIMATED (not RESERVED) when a check rejects it, so a rejected call
        consumes no budget.
        """
        with self._transaction():
            entry = self._find(entry_id)
            estimated = entry["estimated_usd"]
            budget_date = self._entry_date(entry)

            # --- Safeguard 1: single-action threshold (independent of mode) ---
            threshold = self.single_action_approval_usd
            if threshold is not None and threshold > 0 and estimated - threshold > _EPSILON:
                raise ApprovalRequiredError(
                    f"Action costs ${estimated:.2f}, which exceeds the configured "
                    f"single-action approval threshold of ${threshold:.2f}. "
                    f"This safeguard is independent of budget mode "
                    f"({self.mode.value}); raise or disable "
                    f"budget.single_action_approval_usd to permit it."
                )

            # --- Safeguard 2: first paid use of a tool (independent of mode) ---
            if self.require_approval_for_new_paid_tool and estimated > 0:
                if entry["tool"] not in self._approved_tools:
                    raise ApprovalRequiredError(
                        f"First paid use of tool {entry['tool']!r} requires approval. "
                        f"This safeguard is independent of budget mode "
                        f"({self.mode.value}); call approve_tool({entry['tool']!r}) or "
                        f"disable budget.require_approval_for_new_paid_tool."
                    )

            # --- Control 3: the day's aggregate budget (governed by mode) ---
            if self.mode == BudgetMode.CAP:
                # A day whose actual spend already breached its reservations is
                # closed for business, regardless of how small this request is.
                if budget_date in self._overrun_dates:
                    raise BudgetExceededError(self._overrun_message(budget_date, estimated))
                remaining = self.remaining_on(budget_date)
                if estimated - remaining > _EPSILON:
                    raise BudgetExceededError(self._cap_message(budget_date, estimated))
            elif self.mode == BudgetMode.WARN:
                if estimated > self.usable_budget_usd:
                    message = (
                        f"Reservation of ${estimated:.2f} exceeds usable budget "
                        f"${self.usable_budget_usd:.2f}"
                    )
                    entry["budget_warning"] = True
                    entry["budget_warning_message"] = message

            entry["status"] = EntryStatus.RESERVED.value
            entry["reserved_usd"] = estimated
            entry["timestamp"] = self._now()
            self._save()

    def _cap_message(self, budget_date: str, estimated: float) -> str:
        """Operator-readable refusal. Contains no credentials or provider keys."""
        return (
            f"Daily budget hard cap reached for {budget_date}: this request is "
            f"blocked before any paid provider call was made.\n"
            f"  budget date:          {budget_date} (timezone: {self.tz_name})\n"
            f"  configured daily cap: ${self.budget_total_usd:.2f}\n"
            f"  recorded spend today: ${self.spent_on(budget_date):.2f}\n"
            f"  reserved (in-flight): ${self.reserved_on(budget_date):.2f}\n"
            f"  this request:         ${estimated:.2f}\n"
            f"  remaining today:      ${self.remaining_on(budget_date):.2f}\n"
            f"The budget resets at midnight ({self.tz_name}). Raise "
            f"budget.total_usd in config.yaml to permit more spend today."
        )

    def _overrun_message(self, budget_date: str, estimated: float) -> str:
        return (
            f"Daily bucket {budget_date} is marked OVER BUDGET: actual spend "
            f"exceeded what was reserved, so the cap for this date can no longer "
            f"be guaranteed. All further paid calls for {budget_date} are "
            f"blocked.\n"
            f"  configured daily cap: ${self.budget_total_usd:.2f}\n"
            f"  recorded spend today: ${self.spent_on(budget_date):.2f}\n"
            f"  this request:         ${estimated:.2f}\n"
            f"The budget resets at midnight ({self.tz_name}). Prior-day history "
            f"is preserved and is not cleared to free budget."
        )

    def approve_tool(self, tool: str) -> None:
        """Mark a tool as approved for paid operations."""
        with self._transaction():
            self._approved_tools.add(tool)
            self._save()

    def reconcile(self, entry_id: str, actual_usd: float, success: bool = True) -> None:
        """Reconcile actual spend after tool execution.

        Lands in the entry's ORIGINAL budget_date bucket -- never the date on
        which reconciliation happens to run.

        Called for successful AND failed calls: a provider that charged and
        then errored still consumed real money, so FAILED entries keep their
        actual spend and continue to count against that day (see spent_on).
        Spend is never recorded below zero and never truncated to the
        reservation: if actual exceeds what was reserved, the FULL actual is
        recorded and the day is marked over budget, which blocks further paid
        calls for that date.
        """
        with self._transaction():
            entry = self._find(entry_id)
            budget_date = self._entry_date(entry)
            reserved_before = entry.get("reserved_usd", 0.0)
            actual = round(max(0.0, actual_usd), 4)

            entry["status"] = (
                EntryStatus.COMPLETED.value if success else EntryStatus.FAILED.value
            )
            # Full actual, always. Truncating to the reservation would hide
            # real money and make the ledger lie about the day's spend.
            entry["actual_usd"] = actual
            entry["reserved_usd"] = 0.0
            entry["timestamp"] = self._now()

            overran = actual - reserved_before > _EPSILON
            entry["actual_exceeded_reservation"] = overran
            if overran or self.spent_on(budget_date) - self.budget_total_usd > _EPSILON:
                self._overrun_dates.add(budget_date)

            self._save()

    def refund(self, entry_id: str) -> None:
        """Release a reservation for a call that never reached the provider.

        Only correct when the request was cancelled BEFORE dispatch. A call
        that may have reached the provider must go through reconcile(), not
        refund(), or real spend would be silently dropped from the ledger.
        """
        with self._transaction():
            entry = self._find(entry_id)
            entry["status"] = EntryStatus.REFUNDED.value
            entry["reserved_usd"] = 0.0
            entry["timestamp"] = self._now()
            self._save()

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
        """Persist the ledger atomically.

        Writes a sibling temp file and os.replace()s it onto the target
        (atomic on Windows and POSIX). A crash mid-write can therefore leave
        the previous complete ledger or the new one, never a truncated file
        that would strand the cap on the next start.
        """
        if self.cost_log_path is None:
            return
        with self._lock:
            today = self.current_budget_date()
            data = {
                "version": "2.0",
                "budget_total_usd": self.budget_total_usd,
                # Recorded for audit only. Behaviour always comes from config
                # via the constructor -- a stale log must never be able to
                # downgrade cap to warn, or raise the cap, across a restart.
                "budget_mode": self.mode.value,
                "period": self.period,
                "timezone": self.tz_name,
                "overrun_dates": sorted(self._overrun_dates),
                # Today's rollup, for humans reading the file. The authority is
                # always the per-entry budget_date, recomputed on load.
                "budget_date": today,
                "budget_reserved_usd": round(self.reserved_on(today), 4),
                "budget_spent_usd": round(self.spent_on(today), 4),
                "approved_tools": sorted(self._approved_tools),
                "entries": self.entries,
            }
            self.cost_log_path.parent.mkdir(parents=True, exist_ok=True)
            # Unique temp name: two processes must never share one temp file.
            tmp = self.cost_log_path.with_suffix(
                f"{self.cost_log_path.suffix}.{os.getpid()}.tmp"
            )
            with open(tmp, "w") as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.cost_log_path)

    def _load(self) -> None:
        """Rehydrate spend and unresolved reservations from disk.

        Fails closed: an unreadable ledger raises rather than silently
        starting from zero spend, which would defeat the cap.

        budget_total_usd and mode are deliberately NOT restored from the log --
        config.yaml is the sole authority for both.
        """
        try:
            with open(self.cost_log_path) as f:  # type: ignore[arg-type]
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("cost log root is not an object")
            entries = data.get("entries", [])
            if not isinstance(entries, list):
                raise ValueError("cost log 'entries' is not a list")
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            raise CostLogCorruptError(
                f"Cost log at {self.cost_log_path} could not be read ({exc}). "
                f"Refusing to proceed: accumulated spend is unknown, so the "
                f"budget cap cannot be enforced. Inspect or delete the file to "
                f"reset recorded spend."
            ) from exc

        self.entries = entries
        self._approved_tools = set(data.get("approved_tools", []))
        # Sticky: a day marked over budget stays marked across restarts.
        self._overrun_dates = set(data.get("overrun_dates", []))

    # ---- Helpers ----

    def _find(self, entry_id: str) -> dict[str, Any]:
        for entry in self.entries:
            if entry["id"] == entry_id:
                return entry
        raise KeyError(f"Cost entry {entry_id!r} not found")

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex[:12]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
