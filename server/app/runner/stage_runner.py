"""Stage Runner: drives the OpenMontage cinematic pipeline stage by stage.

Each stage:
  1. Loads the stage director skill (markdown) + upstream artifacts
  2. Launches a headless agent (MaaS / claude-sonnet-4.6) with Tool Bridge
  3. Runs the agent loop until artifact written or error
  4. If human_approval_default=true → pauses, emits awaiting_approval event
  5. Resumes after user approves via POST /jobs/{id}/approve
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

OM_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(OM_ROOT))

from dotenv import load_dotenv
load_dotenv(OM_ROOT / ".env")

from openai import OpenAI

from app.store import job_store
from app.runner.tool_bridge import (
    TOOL_SCHEMAS, execute_tool, BudgetExceededError, READ_FILE_CHAR_CAP,
)
# Render discovery + produces-vs-reality validators: split out into
# render_checks.py (stateless leaf functions, no orchestration
# dependencies — see that module's docstring) and re-imported here so every
# call site below, and every existing
# `from app.runner.stage_runner import _discover_render_url, ...` in the test
# suite, keeps working unchanged. Pure code motion, not a behavior change.
from app.runner.render_checks import (
    _PRODUCES_EXPORT_VALIDATORS,
    _discover_render_path,
    _discover_render_url,
    _discover_render_urls,
    _missing_variants,
    _render_report_path_diverges,
    _url_for_render,
    _validate_publish_log_exports,
)

logger = logging.getLogger(__name__)

try:
    from tools.cost_tracker import CostTracker
    from lib.config_model import BudgetMode
    _COST_TRACKER_AVAILABLE = True
except Exception:  # pragma: no cover - cost ledger is optional
    CostTracker = None  # type: ignore
    BudgetMode = None   # type: ignore
    _COST_TRACKER_AVAILABLE = False

# ── MaaS LLM client ───────────────────────────────────────────────────────────
MAAS_KEY  = os.environ.get("MAAS_API_KEY", "")
MAAS_BASE = os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com")
# Overridable so alternative gateway models (e.g. bailian/deepseek-v4-pro,
# OpenAI-compatible per docs/multimodal-call-guide-v4.md) can be evaluated
# without a code change — this is the model driving every pipeline stage's
# reasoning, so swapping it is a deliberate, explicit choice (env var), never
# a silent default change.
LLM_MODEL = os.environ.get("MAAS_LLM_MODEL", "anthropic/claude-sonnet-4.6")

# Explicit request timeout for every call this client makes. The openai-python
# default (no timeout set here previously) left a hung gateway free to block
# the asyncio.to_thread worker running a stage indefinitely — no error event,
# no stage_retry, the job just sits at "running" forever with no user-visible
# failure. 120s comfortably covers a normal completion (even one filling the
# max_tokens=16384 cap below) while still bounding a genuine hang.
LLM_REQUEST_TIMEOUT_SECONDS = 120.0

llm = OpenAI(api_key=MAAS_KEY, base_url=f"{MAAS_BASE}/v1", timeout=LLM_REQUEST_TIMEOUT_SECONDS)

# ── Cinematic pipeline stage tuning ──────────────────────────────────────────
# Runner-side per-stage overrides, overlaid onto the manifest-derived stage
# dict inside _resolve_stages below. These values (max_turns / temperature)
# deliberately do NOT live in pipeline_defs/cinematic.yaml — the manifest
# schema (schemas/pipelines/pipeline_manifest.schema.json) sets
# additionalProperties: false on stage items with no max_turns/temperature
# keys, and tuning is engine-runtime behavior, not a declarative pipeline
# property. Keyed by (pipeline_name, stage_name) so a future pipeline can get
# its own tuning without touching another's; "marketing_film" needs no entry
# of its own since it resolves via cinematic (see PIPELINE_MAP below).
_STAGE_TUNING: dict[tuple[str, str], dict] = {
    # scene_plan/assets/edit/compose write schema-shaped JSON that downstream
    # stages parse structurally — a lower temperature trades away creative
    # variance (not needed here) for more reliable schema-following and less
    # truncation/format drift, vs. the default 0.7 kept for the genuinely
    # creative stages (research, proposal, script, publish).
    ("cinematic", "scene_plan"): {"temperature": 0.3},
    # max_turns doubled vs. the global default (20) — this stage places one
    # or more generation calls (video/image/tts) per scene across the whole
    # scene_plan, which routinely needs more turns than a single-artifact
    # planning stage.
    ("cinematic", "assets"): {"max_turns": 40, "temperature": 0.3},
    ("cinematic", "edit"): {"temperature": 0.3},
    # max_turns doubled vs. the global default (20), same rationale as
    # "assets" above — compose is at least as tool-call-heavy (per-variant
    # render calls, trim/stitch/color-grade/audio-mix passes, etc.) and
    # confirmed live to hit the 20-turn ceiling on a real run.
    ("cinematic", "compose"): {"max_turns": 40, "temperature": 0.3},
}

# Pure alias table: "marketing_film" has no pipeline_defs/*.yaml manifest of
# its own and instead reuses cinematic's manifest-derived stages verbatim.
# cinematic itself is NOT listed here — it resolves through the exact same
# pipeline_defs/<name>.yaml manifest path as every other engine pipeline (see
# _resolve_stages below) instead of a second, hand-maintained Python stage
# list that could (and, confirmed via a deep code review, did) silently drift
# out of sync with the manifest's human_approval_default/produces/
# required_artifacts_in. Anything NOT in this table is resolved dynamically
# from the manifest, so every engine pipeline (animated-explainer,
# screen-demo, podcast-repurpose, …) is runnable via the web platform without
# hardcoding its stages here.
PIPELINE_MAP: dict[str, Any] = {
    "marketing_film": "cinematic",   # alias → cinematic's manifest-derived stages
}


def _resolve_stages(pipeline_name: str) -> list[dict]:
    """Return the stage list for a pipeline.

    Precedence: PIPELINE_MAP entry → pipeline_defs manifest (with
    _STAGE_TUNING overlaid on top, see its docstring) → cinematic fallback.
    Manifest stages map skill "pipelines/x/y-director" to
    "skills/pipelines/x/y-director.md" and human_approval_default to approval.

    A PIPELINE_MAP entry can be either a string (an alias — re-resolved under
    the aliased name, so it goes through the exact same manifest + tuning
    path as the pipeline it aliases) or a literal list of stage dicts (a raw
    override, returned as-is with no manifest involved at all — used by tests
    that need precise control over stage behavior).
    """
    override = PIPELINE_MAP.get(pipeline_name)
    if isinstance(override, str):
        return _resolve_stages(override)
    if override is not None:
        return override
    try:
        from app.pipeline_catalog import load_manifest
        manifest = load_manifest(pipeline_name)
        stages = []
        for s in manifest.get("stages", []):
            skill = s.get("skill")
            stage_name = s["name"]
            stage = {
                "name": stage_name,
                # None (not "") for skill-less stages — Path(OM_ROOT) / "" is
                # OM_ROOT itself (a directory that .exists()), which would
                # defeat the missing-skill fallback below and crash on
                # read_text(). None makes "no skill" unambiguous.
                "skill": f"skills/{skill}.md" if skill else None,
                "approval": bool(s.get("human_approval_default", False)),
                # The manifest's real output artifact name(s) — most pipelines
                # name their stage differently from what it produces (stage
                # "idea" produces "brief"; stage "publish" produces
                # "publish_log"). Used to tell the agent what to write_artifact
                # as, and to find the right file for the approval preview.
                "produces": s.get("produces") or [],
                # Upstream artifacts (by produces-name) this stage needs before
                # it can run meaningfully — checked as a preflight so a broken
                # resume/retry or a naming drift fails fast with a clear
                # message instead of silently prompting the agent on an
                # incomplete "Available artifacts" summary.
                "required_artifacts_in": s.get("required_artifacts_in") or [],
            }
            tuning = _STAGE_TUNING.get((pipeline_name, stage_name))
            if tuning:
                stage.update(tuning)
            stages.append(stage)
        if stages:
            return stages
    except Exception:
        # Falling back to cinematic's stages here means the job RUNS, just
        # not the pipeline the caller asked for — a corrupted/malformed
        # manifest must at least be diagnosable from the logs. (The
        # unknown-name case never reaches here; jobs.py validates the
        # pipeline name at creation time.)
        logger.warning(
            "Failed to load pipeline manifest %r; falling back to cinematic stages",
            pipeline_name, exc_info=True,
        )
    if pipeline_name == "cinematic":
        # cinematic's own manifest failed to load or declared zero stages —
        # nothing left to fall back to without recursing forever. In
        # practice this never triggers (pipeline_defs/cinematic.yaml is
        # well-formed); an empty list here just means "no stages resolved",
        # same as the manifest-returned-no-stages case above.
        return []
    return _resolve_stages("cinematic")


def _resolve_max_revisions(pipeline_name: str) -> int:
    """The manifest's orchestration.max_revisions_per_stage for this pipeline.

    Every pipeline_defs/*.yaml declares it (universally 3), but until this
    resolver nothing read ANY of the manifests' orchestration keys — the
    human reject→regenerate loop was unbounded, each round a fresh paid LLM
    conversation. Follows PIPELINE_MAP string aliases the same way
    _resolve_stages does; a raw stage-list override (tests) has no manifest,
    so it gets the default. Of the other orchestration keys, only this one
    is enforced by this runner — see the schema
    (schemas/pipelines/pipeline_manifest.schema.json) for each key's
    enforcement status.
    """
    override = PIPELINE_MAP.get(pipeline_name)
    if isinstance(override, str):
        return _resolve_max_revisions(override)
    if override is not None:
        return DEFAULT_MAX_REVISIONS_PER_STAGE
    try:
        from app.pipeline_catalog import load_manifest
        manifest = load_manifest(pipeline_name)
        value = int((manifest.get("orchestration") or {})["max_revisions_per_stage"])
        if value > 0:
            return value
    except Exception:
        pass
    return DEFAULT_MAX_REVISIONS_PER_STAGE

MAX_TURNS  = 20
# How many pause→resume round-trips a single stage run allows for its
# mid-stage sample-preview checkpoint (see SamplePreviewNeeded below) before
# giving up. Mirrors asset-director.md's own "max 3 iterations" policy for a
# rejected sample.
MAX_SAMPLE_ITERATIONS = 3

# ── Approval-wait ladder (remind → escalate → expire; NEVER auto-decide) ─────
# The original behavior was a single wait_for_approval(timeout=3600) whose
# timeout was silently reported as a REJECT — a user who stepped away for an
# hour came back to a job that had been auto-rejected (stage gates: a paid
# regenerate they never asked for; budget gate: the job killed) with no
# countdown and no notification. The ladder instead: emit an
# "approval_reminder" SSE event every APPROVAL_REMINDER_SECONDS (the UI turns
# these into toasts / escalating notices), and only after
# APPROVAL_EXPIRY_SECONDS with no decision at all does the job fail — loudly,
# with an explicit "approval window expired" message, retryable, and NEVER by
# fabricating an approve/reject the human didn't make. (Ladder shape follows
# Cloudflare's approval pattern: remind → escalate → 7-day hard expiry.)
APPROVAL_REMINDER_SECONDS = float(os.environ.get("OM_APPROVAL_REMINDER_SECONDS", 1800.0))
APPROVAL_EXPIRY_SECONDS = float(os.environ.get("OM_APPROVAL_EXPIRY_SECONDS", 7 * 24 * 3600.0))

# Bounded human reject→regenerate rounds per stage gate. Every
# pipeline_defs/*.yaml manifest declares orchestration.max_revisions_per_stage
# (universally 3) but nothing ever read it — the reject loop was unbounded,
# each round a fresh paid LLM conversation. This is the fallback when a
# manifest doesn't declare one; see _resolve_max_revisions.
DEFAULT_MAX_REVISIONS_PER_STAGE = 3


class SamplePreviewNeeded(Exception):
    """Raised out of _run_agent_stage when the agent stops mid-stage (a
    text-only turn, no tool_calls) before its declared artifact exists —
    e.g. asset-director.md's "Sample Preview (Prevents Wasted Spend)" step,
    which explicitly requires generating one sample and waiting for the
    user to confirm before batch-generating the rest.

    This used to be handled by silently injecting a "no human is available,
    proceed autonomously" message and continuing the same turn loop. That
    made the pipeline resilient (a stage could never get permanently stuck),
    but it also meant the skill's own "prevents wasted spend" checkpoint was
    unconditionally defeated — paid generation always proceeded on the
    agent's own unconfirmed judgment, even when a real user was watching
    live via SSE. This tool is used by a single local operator (not a
    synchronous multi-second wait — they may check back minutes later), so a
    real async pause is the right fit: unwind out of the thread, surface the
    agent's message as a genuine approval gate (reusing the exact same
    awaiting_approval/wait_for_approval primitive as the stage-boundary and
    budget gates), and resume the SAME conversation — not a fresh one — once
    the user responds.
    """

    def __init__(self, messages: list[dict], preview_text: str, sample_iteration: int):
        super().__init__(preview_text)
        self.messages = messages
        self.preview_text = preview_text
        self.sample_iteration = sample_iteration


class BudgetGateNeeded(Exception):
    """Raised out of _run_agent_stage when a paid tool call is blocked by the
    pre-call budget ceiling (a BudgetExceededError raised from
    tool_bridge.py BEFORE the blocking call executes) — mirrors
    SamplePreviewNeeded's resume-not-restart pattern above.

    The previous behavior let the bare BudgetExceededError propagate straight
    out of _run_agent_stage, discarding the local `messages` list entirely —
    on approval the caller had no choice but to restart the whole stage
    conversation from scratch (resume_messages stayed None), orphaning any
    assets already generated earlier in that same stage's conversation.
    `messages` here carries the conversation so far, INCLUDING a placeholder
    tool-role response backfilled for the blocked tool_call_id and for every
    sibling tool_call in that same assistant turn that was never reached —
    OpenAI-style chat completions APIs require every tool_call in an
    assistant turn to have a matching tool-role response before the next
    turn is sent, so a conversation resumed without those would be rejected
    as malformed on the very next completion call. `budget_exc` is the
    original BudgetExceededError (carrying .tool_name/.est_cost/
    .projected_cny per tool_bridge.py's contract) so the runner's budget
    gate can show/re-arm using the actual blocked call, not just whatever
    `cost_accumulator` already reflects (which does NOT include this call's
    cost, since it never ran).
    """

    def __init__(self, messages: list[dict], preview_text: str, budget_exc: Exception):
        super().__init__(preview_text)
        self.messages = messages
        self.preview_text = preview_text
        self.budget_exc = budget_exc


class JobCancelled(Exception):
    """Raised the moment a user-requested cancellation (job.cancel_requested,
    set by POST /jobs/{id}/cancel) is observed — from the per-turn loop in
    _run_agent_stage, the per-stage loop in _run_pipeline_impl, or right after
    any of the four wait_for_approval() calls (budget gate, sample-preview
    gate, stage-boundary gate x2).

    A generic "reject" action from wait_for_approval means something
    different at every gate (budget: abort the job; sample-preview: try a
    different approach and keep going; stage-boundary: regenerate with
    feedback and keep going) — cancel_requested must be checked and handled
    BEFORE any gate-specific reject logic runs, or a cancel routed through
    set_approval(..., "reject", ...) would be silently reinterpreted as
    "keep going" by the sample-preview and stage-boundary gates instead of
    actually stopping the job. Always caught in run_pipeline_job, which is
    the single place that marks the job cancelled and emits job_cancelled —
    every raise site below just signals "stop", it never sets status itself.
    """
MAX_ROUNDS = 2   # bounded auto-retry when _run_agent_stage returns False (not the human reject loop, a separate mechanism below)
# Cap each tool result appended to history. Derived from tool_bridge's own
# read_file cap so the strictly-greater relationship can't silently drift:
# if this cap were <= READ_FILE_CHAR_CAP, a file near that size would get
# truncated twice — once by read_file with a clean "[truncated — N total
# chars]" marker, then re-sliced here mid-marker, producing a garbled nested
# truncation notice instead of one clean one.
TOOL_RESULT_CHAR_CAP = READ_FILE_CHAR_CAP + 1000


def _emit(job_id: str, event: dict) -> None:
    job_store.push_event(job_id, {"ts": time.time(), **event})


def _fail_job(
    job_id: str,
    stage: str | None = None,
    message: str | None = None,
    *,
    set_current_stage: bool = True,
    **extra_event_fields: Any,
) -> None:
    """Mark the job failed AND emit the matching job_failed event in one call.

    The invariant "a status change must be accompanied by its matching event"
    used to be maintained by hand at every failure site — one update() +
    one _emit() pair each — which is exactly the kind of duplication where a
    site eventually drifts (e.g. the retries-exhausted emit that shipped with
    no message field at all). `stage`, when given, is stamped on the event
    and (unless set_current_stage=False) recorded as the job's current_stage.
    set_current_stage=False is for sites whose event `stage` names a gate
    rather than a real pipeline stage (e.g. "budget") — clobbering the job
    record's current_stage there would misreport where the pipeline actually
    was. extra_event_fields (e.g. trace) pass through to the event verbatim.
    """
    update_kwargs: dict[str, Any] = {"status": "failed"}
    if stage is not None and set_current_stage:
        update_kwargs["current_stage"] = stage
    job_store.update(job_id, **update_kwargs)
    event: dict[str, Any] = {"type": "job_failed"}
    if stage is not None:
        event["stage"] = stage
    if message is not None:
        event["message"] = message
    event.update(extra_event_fields)
    _emit(job_id, event)


def _pause_for_approval(
    job_id: str,
    stage: str,
    gate: str | None = None,
    preview: Any = None,
    preview_artifact: str | None = None,
) -> float:
    """Set status=awaiting_approval AND emit the matching awaiting_approval
    event in one call — same status-change-plus-event invariant as _fail_job.

    `gate` distinguishes the mid-run gates (budget / sample_preview /
    revisions_exhausted) from the ordinary stage-boundary approval, which
    emits no gate key at all — the key is omitted (not None) there so
    consumers' event shape is unchanged. `preview` is always included, even
    when None, matching the historical stage-boundary emit shape.

    Returns the gate's hard expiry timestamp (also stamped on the event as
    `expires_at` and on the job record as `approval_expires_at`, so both a
    live SSE consumer and a fresh page load can render a countdown) — pass
    it to _wait_for_decision so the deadline the user sees and the deadline
    the runner enforces are the same number.
    """
    # Clear any stale decision/event left by a previous gate's timeout race
    # BEFORE the status flip makes new decisions acceptable (see
    # JobStore.begin_approval_gate).
    job_store.begin_approval_gate(job_id)
    expires_at = time.time() + APPROVAL_EXPIRY_SECONDS
    job_store.update(job_id, status="awaiting_approval", approval_expires_at=expires_at)
    event: dict[str, Any] = {"type": "awaiting_approval", "stage": stage}
    if gate is not None:
        event["gate"] = gate
    event["preview"] = preview
    if preview_artifact is not None:
        # The produces-name of the artifact `preview` holds — lets the UI
        # pick the matching structured renderer (script / scene_plan /
        # asset_manifest / …) instead of a raw JSON box (roadmap 1.2).
        event["preview_artifact"] = preview_artifact
    event["expires_at"] = expires_at
    event["reminder_seconds"] = APPROVAL_REMINDER_SECONDS
    _emit(job_id, event)
    return expires_at


async def _wait_for_decision(
    job_id: str,
    stage: str,
    gate: str | None = None,
    expires_at: float | None = None,
) -> dict:
    """wait_for_approval with the reminder→escalate→expire ladder on top.

    Waits in APPROVAL_REMINDER_SECONDS slices; each slice that elapses with
    no decision emits an "approval_reminder" SSE event (the UI surfaces
    these as toasts/notifications) and keeps waiting. Only when `expires_at`
    (default: now + APPROVAL_EXPIRY_SECONDS; normally the value returned by
    _pause_for_approval) passes with no decision does this return
    {"action": "timeout"} — the caller must then fail the job EXPLICITLY.
    Approve/reject are never fabricated on the human's behalf.
    """
    started = time.time()
    deadline = expires_at if expires_at is not None else started + APPROVAL_EXPIRY_SECONDS
    reminder_index = 0
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return {"action": "timeout", "feedback": ""}
        decision = await job_store.wait_for_approval(
            job_id, timeout=min(APPROVAL_REMINDER_SECONDS, remaining)
        )
        if decision.get("action") != "timeout":
            return decision
        # A cancel can arrive while the gate is open — surface it promptly
        # instead of only after the full expiry window.
        if (job_store.get(job_id) or {}).get("cancel_requested"):
            raise JobCancelled()
        if deadline - time.time() <= 0:
            return {"action": "timeout", "feedback": ""}
        reminder_index += 1
        event: dict[str, Any] = {
            "type": "approval_reminder",
            "stage": stage,
            "reminder_index": reminder_index,
            "waited_seconds": round(time.time() - started),
            "expires_at": deadline,
        }
        if gate is not None:
            event["gate"] = gate
        _emit(job_id, event)


def _approval_expired_message(stage: str) -> str:
    days = APPROVAL_EXPIRY_SECONDS / 86400
    return (
        f"Approval for stage '{stage}' received no decision within the "
        f"{days:.0f}-day approval window — the job was stopped without "
        "auto-approving or auto-rejecting anything. Retry the job to re-open "
        "this stage."
    )


def _truncate_json_for_prompt(text: str, cap: int) -> str:
    """Slice a JSON dump for prompt inclusion, with a visible marker when cut.

    A naive [:cap] slice with no marker (the previous behavior for both
    brand-kit and prior-artifacts injection) gives the agent no signal that
    what it's reading is incomplete, unlike every other truncation point in
    this file/tool_bridge.py, which all append a "[truncated — N total
    chars]" note. Note this doesn't fully solve a cut landing mid-object
    (still syntactically invalid JSON) — that would need truncating whole
    artifacts rather than a raw string slice, a bigger change than this
    fixes.
    """
    if len(text) <= cap:
        return text
    return text[:cap] + f"\n... [truncated — {len(text)} total chars]"


# Prior-artifacts prompt budget (see _build_prior_artifacts_text below): a
# stage's OWN required_artifacts_in list is what it actually needs to do its
# job — each of those gets a generous, independent cap; everything else
# shares one small combined budget placed after them. Confirmed live: by the
# time "compose" runs, the combined artifact dump was >100,000 chars, and the
# OLD flat 6000-char cap on the whole concatenated JSON blob (truncated
# positionally — whatever sorted/iterated first) meant compose's own
# required edit_decisions/asset_manifest never survived into the visible
# window, crowded out by whatever came first (e.g. research_brief).
_REQUIRED_ARTIFACT_PROMPT_CAP = 15000       # per required artifact, not combined
_OTHER_ARTIFACTS_PROMPT_CAP_TOTAL = 2000    # shared budget for everything NOT required


def _build_prior_artifacts_text(artifacts: dict[str, Any], required_names: list[str] | None) -> str:
    """Build the '## Prior Artifacts' prompt section.

    Required artifacts (this stage's own required_artifacts_in) are placed
    first, each capped generously and independently; everything else shares
    one small combined budget placed after them — so a stage's own required
    input can never be crowded out by an unrelated artifact that merely
    happens to iterate first, the way a single flat cap on the concatenated
    JSON blob was.
    """
    required = set(required_names or [])
    sections: list[str] = []

    for name, value in artifacts.items():
        if name not in required:
            continue
        dumped = json.dumps(value, ensure_ascii=False, indent=2)
        sections.append(
            f"### {name} (required by this stage)\n"
            f"{_truncate_json_for_prompt(dumped, _REQUIRED_ARTIFACT_PROMPT_CAP)}"
        )

    remaining_budget = _OTHER_ARTIFACTS_PROMPT_CAP_TOTAL
    for name, value in artifacts.items():
        if name in required:
            continue
        if remaining_budget <= 0:
            sections.append(f"### {name}\n[omitted — non-required-artifact budget exhausted]")
            continue
        dumped = json.dumps(value, ensure_ascii=False, indent=2)
        capped = _truncate_json_for_prompt(dumped, remaining_budget)
        sections.append(f"### {name}\n{capped}")
        remaining_budget -= len(capped)

    return "\n\n".join(sections) if sections else "(none)"


def _last_failure_message(job_id: str, stage_name: str) -> str:
    """Most recent "error" event's message for this stage, or "" if none.

    The automatic stage-retry loop used to call _run_agent_stage again with
    feedback="" every time — a brand-new conversation with identical inputs
    to the one that just failed, so a deterministic failure (e.g. the same
    malformed tool call) had no way to change on retry. _run_agent_stage
    only returns True/False, not a reason, but every failure path already
    _emits an "error" event before returning False — reuse that instead of
    growing the function's already-large parameter list further.
    """
    for ev in reversed(job_store.get_events(job_id, after_seq=-1)):
        if ev.get("type") == "error" and ev.get("stage") == stage_name:
            return ev.get("message", "")
    return ""


def _load_artifacts(project_dir: Path) -> dict[str, Any]:
    artifacts = {}
    artifacts_dir = project_dir / "artifacts"
    if artifacts_dir.exists():
        for f in artifacts_dir.glob("*.json"):
            try:
                artifacts[f.stem] = json.loads(f.read_text())
            except Exception:
                pass
    return artifacts


def _missing_produces(project_dir: Path, stage_def: dict) -> list[str] | None:
    """Return the stage's declared `produces` names that were NOT actually
    written, else None (every declared artifact exists).

    _run_agent_stage returning True only means the agent's LLM loop ended
    without further tool calls — e.g. it decided to stop and ask a human
    instead of silently substituting a fallback provider (the correct
    behavior per the tool-provider skill contract), or it wrote its primary
    artifact but skipped a secondary one. Without this check "no more tool
    calls" was being treated as unconditional success: the stage got recorded
    in completed_stages, permanently skipped on every future retry, and the
    job died one or more stages later — at the first stage whose
    required_artifacts_in happens to reference the specific missing name — a
    confusing message pointing at the wrong stage, and a dead-end retry loop
    (retry can never re-run the stage that actually needs it). Require ALL
    declared names, not just one: a downstream stage's required_artifacts_in
    can name any of them (e.g. compose declares
    produces=[render_report, final_review] and publish requires
    final_review specifically — partial completion must still fail here,
    at compose, not silently cascade to publish).
    """
    produces = stage_def.get("produces") or []
    if not produces:
        return None
    have = set(_load_artifacts(project_dir))
    missing = [name for name in produces if name not in have]
    return missing or None


def _artifact_mtimes(project_dir: Path, names: list[str]) -> dict[str, float]:
    """mtime (or -1.0 if absent) of each declared artifact — used to detect a
    reject-regenerate round that didn't actually rewrite anything. File
    *presence* alone (what _missing_produces checks) can't tell "freshly
    written this round" apart from "leftover from the just-rejected round":
    by construction, every declared artifact already exists on disk before a
    regenerate call even starts (reaching the approval gate at all requires
    having passed _missing_produces once already), so a text-only first turn
    after rejection — a real, previously-confirmed occurrence, not just a
    hypothetical — would otherwise be silently treated as "nothing missing"
    and the stale, rejected content would be re-presented as if regenerated."""
    artifacts_dir = project_dir / "artifacts"
    result = {}
    for name in names:
        p = artifacts_dir / f"{name}.json"
        result[name] = p.stat().st_mtime if p.exists() else -1.0
    return result


def _canonical_pipeline_type(pipeline_name: str) -> str:
    """Follow PIPELINE_MAP string aliases to the real manifest name
    (marketing_film → cinematic). A raw stage-list override (tests) has no
    manifest — return the name unchanged; checkpoint writes will then fail
    validation and be skipped (they're best-effort)."""
    seen: set[str] = set()
    name = pipeline_name
    while isinstance(PIPELINE_MAP.get(name), str) and name not in seen:
        seen.add(name)
        name = PIPELINE_MAP[name]   # type: ignore[assignment]
    return name


def _write_stage_checkpoint(
    project_dir: Path,
    project_name: str,
    pipeline_type: str,
    stage_def: dict,
    status: str,
    *,
    approved: bool = False,
    cost_cny: float | None = None,
) -> None:
    """Dual persistence (roadmap 2.5): mirror the web runner's stage state
    into lib/checkpoint's on-disk protocol — the same files the Backlot
    board watches. Until this, the web path never imported lib.checkpoint,
    so 11 of 12 real projects had no checkpoints and the board's entire
    mechanism (version history, time-scrub replay, gate audit, stall
    detection) served exactly one hand-run project.

    Strictly best-effort: the board is an observer, never a blocker — any
    validation failure (e.g. an agent-written artifact that doesn't satisfy
    its schema, which write_artifact deliberately tolerates) skips the
    checkpoint with a debug log and the pipeline continues.
    """
    try:
        from lib.checkpoint import write_checkpoint
        artifacts: dict[str, Any] = {}
        if status in ("completed", "awaiting_human"):
            have = _load_artifacts(project_dir)
            for name in stage_def.get("produces") or []:
                if name in have:
                    artifacts[name] = have[name]
        write_checkpoint(
            project_dir.parent,
            project_name,
            stage_def["name"],
            status,
            artifacts,
            pipeline_type=pipeline_type,
            human_approval_required=bool(stage_def.get("approval")),
            human_approved=approved,
            cost_snapshot={"total_cny": cost_cny} if cost_cny is not None else None,
        )
    except Exception:
        logger.debug(
            "checkpoint write skipped for %s/%s (%s)",
            project_name, stage_def.get("name"), status, exc_info=True,
        )


def _run_asset_consistency_check(job_id: str, project_dir: Path) -> None:
    """Multi-shot subject consistency (roadmap 3.3): lib/asset_consistency
    was written after a real incident (four generated shots of "the same"
    robot vacuum, four visibly different designs) and then never called.
    This is its production call site: after the assets stage completes,
    every group of manifest assets sharing a `subject` tag is checked for
    pairwise visual similarity; below-threshold pairs surface as a warning
    event. Advisory — CLIP being uninstalled or a check error never blocks
    the stage."""
    try:
        manifest = _load_artifacts(project_dir).get("asset_manifest") or {}
        groups: dict[str, list[str]] = {}
        for a in manifest.get("assets", []) or []:
            if not isinstance(a, dict):
                continue
            subject = a.get("subject") or a.get("subject_tag")
            path = a.get("path")
            if not subject or not path or "image" not in str(a.get("type", "")):
                continue
            p = Path(path)
            if not p.is_absolute():
                p = project_dir / path
            groups.setdefault(str(subject), []).append(str(p))
        groups = {s: ps for s, ps in groups.items() if len(ps) >= 2}
        if not groups:
            return
        from lib.asset_consistency import check_asset_consistency
        result = check_asset_consistency(groups)
        if result.get("critical"):
            pairs = "; ".join(
                f"{f['subject']}: {Path(f['asset_a']).name} vs {Path(f['asset_b']).name} "
                f"(similarity {f['similarity']})"
                for f in result.get("findings", [])[:5]
            )
            _emit(job_id, {
                "type": "warning",
                "stage": "assets",
                "message": (
                    "Asset consistency check: the same subject appears as visibly "
                    f"different designs across shots — {pairs}. Review the assets "
                    "before compose locks them in (per-scene 换一版 can reroll the "
                    "outliers)."
                ),
            })
        elif not result.get("ran"):
            logger.debug("asset consistency check skipped: %s", result.get("reason"))
    except Exception:
        logger.debug("asset consistency check errored", exc_info=True)


def _load_brand_kit(kit_id: str | None) -> dict:
    """Load a brand kit from brand_kits/<kit_id>/kit.json, or empty dict."""
    if not kit_id:
        return {}
    p = OM_ROOT / "brand_kits" / kit_id / "kit.json"
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


# The full data URI has to be replayed in EVERY turn's message history for
# the rest of the stage (the agent has no other way to obtain it — read_file
# reads text and would corrupt/fail on binary image bytes), so an
# unbounded-size reference image would silently balloon token cost across up
# to MAX_TURNS calls. The upload endpoint (routers/brands.py) resizes on
# save specifically to stay well under this; this is a backstop for a kit.json
# hand-edited or seeded outside that path.
_MAX_REFERENCE_DATA_URI_CHARS = 400_000  # ~300KB image, comfortably below any turn budget


def _brand_reference_image_data_uri(kit_id: str | None, kit: dict) -> str | None:
    """Base64-encode the brand kit's reference image (if any) as a data URI.

    Deliberately NOT a URL: MAAS_API_BASE is a remote gateway (api.aiapbot.com)
    that cannot reach back into this box's localhost/LAN to fetch a
    /brand-media/... path, even though the web UI can display that same URL
    fine in the user's own browser. A data: URI is embedded directly in the
    request body, so it works regardless of network reachability — this is
    the same reason maas_video/maas_image's own image_to_video paths accept
    image_base64 as an alternative to image_url.
    """
    rel = (kit or {}).get("reference_image_path")
    if not kit_id or not rel:
        return None
    path = OM_ROOT / "brand_kits" / kit_id / rel
    if not path.is_file():
        return None
    try:
        import base64
        ext = path.suffix.lstrip(".").lower() or "png"
        mime = "jpeg" if ext in ("jpg", "jpeg") else ext
        data = base64.b64encode(path.read_bytes()).decode()
        uri = f"data:image/{mime};base64,{data}"
    except OSError:
        return None
    if len(uri) > _MAX_REFERENCE_DATA_URI_CHARS:
        # A truncated data URI isn't a smaller reference image, it's a
        # corrupt one — silently returning it would have the agent copy
        # broken base64 into a paid generation call. Skip it entirely
        # instead; the brand kit's other fields still make it into the
        # prompt as descriptive text.
        return None
    return uri


def _run_agent_stage(
    job_id: str,
    stage_name: str,
    skill_text: str,
    project_dir: Path,
    brand_info: dict,
    options: dict,
    *,
    feedback: str = "",
    cost_accumulator: list | None = None,
    cost_tracker: Any = None,
    budget_cny: float | None = None,
    base_cost: float = 0.0,
    produces: list[str] | None = None,
    resume_messages: list[dict] | None = None,
    sample_iteration: int = 0,
    max_turns: int = MAX_TURNS,
    temperature: float = 0.7,
    required_artifacts_in: list[str] | None = None,
) -> bool:
    """Run a single stage. Returns True on success, False on failure.

    Everything after `options` is keyword-only — the parameter list is long
    enough that threading it positionally was an error magnet (callers and
    test fakes had to count out a[6]/a[9]/a[12] to know what they received).

    resume_messages/sample_iteration resume a conversation that previously
    paused via SamplePreviewNeeded — when given, the stage's initial prompt
    is NOT rebuilt; the agent picks up exactly where it left off.

    May raise BudgetGateNeeded if a paid tool call would cross budget_cny —
    the caller catches it to drive the human budget gate and resume the same
    conversation afterward (see BudgetGateNeeded's docstring).
    """

    artifacts = _load_artifacts(project_dir)
    artifacts_summary = json.dumps(
        {k: "(present)" for k in artifacts}, ensure_ascii=False
    )

    # Brand Kit injection — if a kit_id is in options, load and merge
    kit_id = options.get("brand_kit_id")
    brand_kit = _load_brand_kit(kit_id)
    brand_section = ""
    if brand_kit:
        brand_section = f"""
## Brand Kit (use these to ensure visual/tonal consistency)
{_truncate_json_for_prompt(json.dumps(brand_kit, ensure_ascii=False, indent=2), 2000)}
"""
        ref_data_uri = _brand_reference_image_data_uri(kit_id, brand_kit)
        if ref_data_uri and stage_name == "assets":
            # Only at "assets" (not every stage) — this is the one stage that
            # actually calls image/video generation tools, and the full data
            # URI is expensive enough (replayed in every turn's history for
            # the rest of the stage) that it shouldn't be paid for at stages
            # that can't use it. Called out as its own labeled section,
            # separate from the JSON dump above, so it isn't easy to miss
            # the way a field buried in a 2000-char blob would be.
            brand_section += f"""
## Brand Reference Image (for character/product consistency)
This brand kit has a reference image. To keep a recurring character or
product looking the same across every generated shot, pass EXACTLY the
following data URI as `image_base64` (maas_video image_to_video/
reference_to_video) or `input_image` (maas_image flux2 image-to-image) on
every relevant call — do not describe the same subject freshly in text each
time and hope for visual consistency; reuse this reference image instead.
Copy the string below verbatim, in full — do not shorten or paraphrase it:

{ref_data_uri}
"""

    # A/B variants — when options declares more than one model for a
    # capability, the assets/compose stages must fan out across ALL of them
    # (not just whichever one the agent would have picked on its own).
    video_variants = [m for m in (options.get("video_model_variants") or []) if m]
    variant_section = ""
    if len(video_variants) > 1 and stage_name in ("assets", "compose"):
        variant_list = ", ".join(f'"{m}"' for m in video_variants)
        if stage_name == "assets":
            variant_section = f"""
## A/B Variants (REQUIRED — this job compares {len(video_variants)} video models)
This job must produce EVERY generated video shot once per model below, not
once total:
{variant_list}
For EACH shot in scene_plan, call `run_openmontage_tool` (maas_video) once
per model in that list, passing that exact model string as `inputs.model`
(calls with any other model will be rejected before they cost anything).
Reuse the SAME reference image / prompt across a shot's variants — only the
`model` should differ — so the comparison is apples-to-apples. Record each
asset's `model` field accurately in asset_manifest so the compose stage can
group them back into per-model cuts.
"""
        else:  # compose
            variant_section = f"""
## A/B Variants (REQUIRED — this job compares {len(video_variants)} video models)
asset_manifest contains assets for {len(video_variants)} model variants
({variant_list}), each tagged via its `model` field. Produce ONE fully
composed render PER variant — do not merge them into a single cut. For each
variant's `run_openmontage_tool` (video_compose, operation="compose" or
"remotion_render") call:
  - Use ONLY that variant's assets (filter asset_manifest by `model`).
  - Pass `inputs.variant` set to that exact model string — this is what
    keeps each variant's output file from overwriting the others (it maps
    to a distinct renders/final_<slug>.mp4); omitting it on a multi-variant
    job means only one variant's render survives.
"""

    # Tell the agent the manifest's real output name(s) explicitly, rather than
    # letting it guess from the stage name — many pipelines name a stage
    # differently from what it produces (stage "idea" produces "brief"; stage
    # "publish" produces "publish_log"). The approval-preview lookup below
    # checks these same names, so a mismatch here would show an empty preview
    # even though the agent's artifact wrote successfully.
    if produces:
        primary = produces[0]
        artifact_hint = (
            f"## Expected Artifact Name\n"
            f"Call `write_artifact` with artifact_name=\"{primary}\"."
            + (f" (Additional artifacts this stage may also produce: {', '.join(produces[1:])}.)" if len(produces) > 1 else "")
        )
    else:
        artifact_hint = (
            f"## Expected Artifact Name\n"
            f"No specific name is mandated for this stage — use \"{stage_name}\" for artifact_name."
        )

    user_msg = f"""You are the {stage_name}-director for an OpenMontage cinematic pipeline run.

## Director Skill
{skill_text}

## Project Info
- Brand: {json.dumps(brand_info, ensure_ascii=False)}
- Options: {json.dumps(options, ensure_ascii=False)}
- Available artifacts from previous stages: {artifacts_summary}
{brand_section}
## Prior Artifacts (content)
{_build_prior_artifacts_text(artifacts, required_artifacts_in)}

## User Feedback (if any)
{feedback or "None — proceed normally."}

{artifact_hint}

## Your job
Execute the {stage_name} stage now. Prior-stage artifacts you need are already
fully inlined above under "## Prior Artifacts (content)" — do NOT use `read_file`
to re-fetch artifacts/*.json, that data is already here. Use `read_file` only for
skill docs or schemas you don't already have; pipeline-specific stage-director
skills live at the literal path template `skills/pipelines/{{pipeline}}/{{stage}}-director.md`
(substitute the real pipeline/stage names), never under `skills/core/...`.
Use `run_openmontage_tool` to call generation tools (video, image, TTS, music).
Use `write_artifact` to persist your output artifact when the stage is complete.
After writing the artifact, confirm briefly what you produced.
"""

    # Resuming a paused sample-preview conversation: the agent already has
    # the full context (skill, prior artifacts, etc.) from before the pause —
    # rebuilding user_msg and starting over would throw away everything it
    # already did (including any samples it already generated) and re-ask
    # the same opening question.
    # A shallow copy, not an alias — this function appends to `messages` on
    # every turn, and mutating the caller's own resume_messages list in place
    # would be a surprising side effect for any caller still holding a
    # reference to it.
    messages = list(resume_messages) if resume_messages is not None else [{"role": "user", "content": user_msg}]

    for turn in range(max_turns):
        # Checked once per turn (not just between stages) since a single
        # stage can run for minutes across many turns — job_store.get() is
        # lock-guarded and safe to call from this thread (_run_agent_stage
        # runs inside asyncio.to_thread, not the event loop itself).
        if (job_store.get(job_id) or {}).get("cancel_requested"):
            raise JobCancelled()
        try:
            response = llm.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                # Shared budget for this turn's free-text narration AND its
                # tool-call JSON. A content-heavy stage (e.g. a scene_plan
                # covering several clips) writing a large write_artifact
                # payload could exhaust an 8192 cap before the JSON even
                # finished, producing a tiny, syntactically-truncated
                # arguments string (a handful of chars, not a large partial
                # payload) — confirmed live. Doubled for headroom.
                max_tokens=16384,
                temperature=temperature,
            )
        except Exception as e:
            _emit(job_id, {"type": "error", "stage": stage_name, "message": str(e)})
            return False

        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        if msg.content:
            _emit(job_id, {
                "type": "agent_text",
                "stage": stage_name,
                "text": msg.content[:500],
            })

        if not msg.tool_calls:
            # A text-only turn with the declared artifact(s) already written
            # is genuine completion — the prompt itself asks for exactly this
            # ("After writing the artifact, confirm briefly what you
            # produced."). But a text-only turn BEFORE the artifact exists
            # usually means the agent stopped mid-task to ask for a decision
            # (confirmed live: asset-director's own "Sample Preview" step
            # explicitly tells it to generate one sample of each asset type
            # and confirm with the user before batch-generating the rest).
            # Pause for a real approval instead of silently forcing it
            # forward — bounded so a genuinely stuck agent still fails within
            # a small, predictable number of pause/resume round-trips.
            if produces and _missing_produces(project_dir, {"produces": produces}):
                if sample_iteration < MAX_SAMPLE_ITERATIONS:
                    messages.append({"role": "assistant", "content": msg.content or ""})
                    raise SamplePreviewNeeded(
                        messages=messages,
                        preview_text=msg.content or "",
                        sample_iteration=sample_iteration,
                    )
                # Iteration budget exhausted — fall through to `return True`;
                # the caller's own _missing_produces check (run right after
                # this function returns) will catch the still-missing
                # artifact and fail the stage with a clear message.
            # No tools to run and either the artifact exists, there's no
            # produces to check, or the sample-iteration budget is spent →
            # the agent is done with this stage (or as done as it's going to
            # get). Do NOT gate on finish_reason: OpenAI-compatible gateways
            # (aiapbot proxies Anthropic/DashScope/etc.) may report
            # finish_reason=="stop" even when the message carries tool_calls;
            # gating on "stop" would drop those calls and mark the stage
            # complete without running them.
            return True

        # Append assistant message
        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                }
                for tc in msg.tool_calls
            ]
        })

        # Execute each tool call
        for tc_index, tc in enumerate(msg.tool_calls):
            tool_name = tc.function.name
            raw_args = tc.function.arguments or ""
            try:
                tool_args = json.loads(raw_args)
                if not isinstance(tool_args, dict):
                    tool_args = {}
            except json.JSONDecodeError:
                # Arguments were cut off mid-JSON — tell the model exactly what
                # happened. finish_reason distinguishes a real max_tokens hit
                # ("length") from a merely malformed call the model could
                # otherwise retry unchanged; a small raw_args count does NOT by
                # itself mean the intended content was small — a turn's shared
                # budget can be spent on narration/reasoning before the tool
                # call even starts, cutting it off just a few characters in.
                hit_length_limit = finish == "length"
                _emit(job_id, {
                    "type": "error",
                    "stage": stage_name,
                    "message": (
                        f"Tool {tool_name}: arguments JSON truncated "
                        f"({len(raw_args)} chars, finish_reason={finish}). "
                        "Agent must retry."
                    ),
                })
                if hit_length_limit:
                    retry_hint = (
                        "Please retry write_artifact with a more concise 'content' object — "
                        "keep each field value under 500 characters, omit verbose descriptions, "
                        "and skip restating your reasoning in free text before calling the tool."
                    )
                else:
                    retry_hint = (
                        "This wasn't a length limit — the call was simply malformed. "
                        "Retry the same tool call with valid JSON arguments."
                    )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": (
                        f"ERROR: Your function call arguments were truncated and could not be parsed "
                        f"({len(raw_args)} chars received, finish_reason={finish}). {retry_hint}"
                    ),
                })
                continue

            # Show the call's actual identifying argument, not its parameter
            # names — list(tool_args.keys()) rendered the exact same
            # "read_file(['path'])" for every read_file call regardless of
            # which file was read, so a whole stage's log looked identical
            # line after line.
            if tool_name == "read_file":
                arg_preview = tool_args.get("path", "")
            elif tool_name == "write_artifact":
                arg_preview = tool_args.get("artifact_name", "")
            elif tool_name == "run_openmontage_tool":
                arg_preview = tool_args.get("tool_name", "")
            else:
                arg_preview = ""
            _emit(job_id, {
                "type": "tool_call",
                "stage": stage_name,
                "tool": tool_name,
                "summary": f"{tool_name}({arg_preview})" if arg_preview else tool_name,
            })

            try:
                result = execute_tool(
                    tool_name,
                    tool_args,
                    project_dir,
                    # Stamp the current stage onto every bridge-emitted event
                    # (asset_ready/tool_call/artifact_written/...) — the
                    # filmstrip and the two-tier event log group by stage,
                    # and tool_bridge itself doesn't know which stage is
                    # running. An event that sets its own stage still wins.
                    emit_event=lambda ev: _emit(job_id, {"stage": stage_name, **ev}),
                    cost_accumulator=cost_accumulator,
                    cost_tracker=cost_tracker,
                    budget_cny=budget_cny,
                    base_cost=base_cost,
                    options=options,
                )
            except BudgetExceededError as exc:
                # Hard budget stop — unwind the stage so the runner's event loop
                # can pause for the human budget decision. Restarting the whole
                # conversation on approval (the old behavior: letting this
                # propagate as a bare BudgetExceededError) would orphan any
                # assets already generated earlier in this same stage's
                # conversation — carry `messages` forward instead via
                # BudgetGateNeeded (see its docstring) so the SAME conversation
                # can resume. Backfill a placeholder tool-role response for
                # THIS blocked tool_call_id, and for every sibling tool_call in
                # this same assistant turn that was never reached (OpenAI-style
                # chat completions APIs require every tool_call in an assistant
                # turn to have a matching tool-role response before the next
                # turn is sent, or the resumed conversation is malformed).
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": "BLOCKED: awaiting budget approval",
                })
                for remaining_tc in msg.tool_calls[tc_index + 1:]:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": remaining_tc.id,
                        "content": "SKIPPED: stage paused for budget approval",
                    })
                raise BudgetGateNeeded(messages=messages, preview_text=str(exc), budget_exc=exc)
            except Exception as exc:
                # A bare KeyError (e.g. a tool indexing inputs["some_field"]
                # with no .get() fallback) stringifies to just "'some_field'"
                # — cryptic enough that the agent can't tell what to fix and
                # ends up repeating the exact same broken call until the stage
                # burns through MAX_TURNS. Name the parameter explicitly so
                # the agent can self-correct on the next turn instead of
                # looping on an error it can't interpret.
                if isinstance(exc, KeyError):
                    result = f"ERROR: Tool execution failed — missing required parameter: {exc}"
                else:
                    result = f"ERROR: Tool execution failed: {exc}"
                _emit(job_id, {
                    "type": "error",
                    "stage": stage_name,
                    "message": f"Tool {tool_name} error: {exc}",
                })

            # Cap each tool result before it enters the running history — over
            # MAX_TURNS turns, uncapped read_file/tool outputs can otherwise
            # exceed the model context window and fail the next completion call.
            if len(result) > TOOL_RESULT_CHAR_CAP:
                result = result[:TOOL_RESULT_CHAR_CAP] + f"\n\n[truncated — {len(result)} total chars]"

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    _emit(job_id, {
        "type": "error",
        "stage": stage_name,
        "message": f"Stage {stage_name} reached max turns ({max_turns}) without completing",
    })
    return False


# In-process re-entrancy guard: job_ids with a run_pipeline_job currently
# in flight. The /retry endpoint already rejects retrying a non-"failed" job,
# but that check and the enqueue aren't atomic — two near-simultaneous retry
# calls (or a retry racing a job's own natural completion) could both pass the
# status check before either updates it. A second concurrent run for the same
# job_id would race the first: two LLM sessions writing artifacts for the same
# project, each clobbering whatever the other just wrote. This set makes a
# duplicate invocation a fast no-op instead of a silent data race.
_ACTIVE_JOB_IDS: set[str] = set()


async def run_pipeline_job(job_id: str, data: dict) -> None:
    """Async entry point called by FastAPI BackgroundTasks.

    Wrapped in a last-resort guard so any unhandled error marks the job failed
    and surfaces via SSE, instead of leaving it silently stuck at 'running'.
    """
    if job_id in _ACTIVE_JOB_IDS:
        _emit(job_id, {
            "type": "error",
            "message": "Ignored a duplicate run_pipeline_job call — this job is already running.",
        })
        return
    _ACTIVE_JOB_IDS.add(job_id)
    try:
        await _run_pipeline_impl(job_id, data)
    except JobCancelled:
        # Single point of handling for every cancellation path (per-turn,
        # per-stage, and all four approval-gate wait_for_approval sites) —
        # see JobCancelled's docstring for why cancel_requested must be
        # checked before any gate-specific reject logic runs.
        job_store.update(job_id, status="cancelled")
        _emit(job_id, {"type": "job_cancelled"})
    except Exception as exc:  # noqa: BLE001 — deliberate catch-all backstop
        import traceback
        _fail_job(
            job_id,
            message=f"Unhandled pipeline error: {exc}",
            trace=traceback.format_exc()[-1500:],
        )
    finally:
        _ACTIVE_JOB_IDS.discard(job_id)


async def _run_pipeline_impl(job_id: str, data: dict) -> None:
    pipeline_name = data.get("pipeline", "cinematic")
    stages = _resolve_stages(pipeline_name)
    brand_info = data.get("brand_info", {})
    options = data.get("options", {})
    project_name = data.get("project_name", job_id)

    # Brand voice (roadmap 3.2): a kit's voice_id becomes the default TTS
    # voice for every narration call of this job (tool_bridge fills it when
    # the agent didn't explicitly choose one) — two videos of one brand now
    # share a narrator by mechanism, not by luck.
    _kit = _load_brand_kit(options.get("brand_kit_id"))
    if _kit.get("voice_id"):
        options = {**options, "brand_voice_id": _kit["voice_id"]}

    project_dir = OM_ROOT / "projects" / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "artifacts").mkdir(exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)
    (project_dir / "renders").mkdir(exist_ok=True)

    # Dual persistence (roadmap 2.5): initialize the checkpoint-protocol
    # workspace marker so the Backlot board can identify this run. Best-effort
    # — the board is an observer, never a blocker.
    pipeline_type = _canonical_pipeline_type(pipeline_name)
    try:
        from lib.checkpoint import init_project
        init_project(
            project_name, title=project_name, pipeline_type=pipeline_type,
            pipeline_dir=project_dir.parent,
        )
    except Exception:
        logger.debug("init_project skipped for %s", project_name, exc_info=True)

    # MaaS tools bill in CNY (the user owns the gateway) and their cost_usd field
    # already carries CNY amounts, so accumulate directly — no FX conversion.
    cost_accumulator: list[float] = []
    job = job_store.get(job_id) or {}
    base_cost = float(job.get("cost_cny", 0.0) or 0.0)          # preserve across retries
    completed_stages: set[str] = set(job.get("completed_stages", []))

    # Optional CNY budget ceiling (opt-in via options.budget_cny). When set, the
    # pipeline pauses for human approval once cumulative cost crosses it.
    try:
        budget_cny = float(options["budget_cny"]) if options.get("budget_cny") not in (None, "") else None
    except (TypeError, ValueError):
        budget_cny = None

    # CostTracker as the itemized ledger (persists projects/<name>/cost_log.json).
    # Values are CNY here; we run it in OBSERVE mode and own the human gate in
    # this runner, so its USD-oriented thresholds are neutralized.
    cost_tracker = None
    if _COST_TRACKER_AVAILABLE:
        try:
            cost_tracker = CostTracker(
                budget_total_usd=(budget_cny if budget_cny else 1e12),
                reserve_pct=0.0,
                single_action_approval_usd=1e12,
                require_approval_for_new_paid_tool=False,
                mode=BudgetMode.OBSERVE,
                cost_log_path=project_dir / "cost_log.json",
            )
        except Exception:
            cost_tracker = None

    def _sync_cost(stage_name: str) -> None:
        cost_cny = round(base_cost + sum(cost_accumulator), 4)
        job_store.update(job_id, cost_cny=cost_cny)
        _emit(job_id, {
            "type": "cost_updated",
            "cost_cny": cost_cny,
            "budget_cny": budget_cny,
            "stage": stage_name,
        })

    async def _budget_gate(force: bool = False, triggering_exc: Any = None) -> bool:
        """Pause for approval if over budget. Returns True to continue, False to abort.

        force=True pauses even when spent is still within budget — used when a
        pre-call check blocked the *next* paid call that would have crossed it.
        triggering_exc, when given, is the BudgetExceededError (e.g. a
        BudgetGateNeeded's .budget_exc) that caused a force=True pre-call
        block — its .tool_name/.est_cost/.projected_cny attributes (per
        tool_bridge.py's cross-file contract) drive both the approval preview
        below and the re-arm ceiling, since `spent` at this point does NOT
        include the cost of whatever call is currently blocked (it never ran).
        """
        nonlocal budget_cny
        if not budget_cny:
            return True
        spent = round(base_cost + sum(cost_accumulator), 4)
        if spent <= budget_cny and not force:
            return True
        blocked_tool_name = getattr(triggering_exc, "tool_name", None) if triggering_exc is not None else None
        blocked_est_cost = getattr(triggering_exc, "est_cost", None) if triggering_exc is not None else None
        projected_cny = getattr(triggering_exc, "projected_cny", None) if triggering_exc is not None else None
        preview: dict[str, Any] = {
            "spent_cny": spent, "budget_cny": budget_cny,
            "over_by_cny": round(spent - budget_cny, 4),
        }
        budget_exceeded_event: dict[str, Any] = {
            "type": "budget_exceeded", "spent_cny": spent, "budget_cny": budget_cny,
        }
        if force and (blocked_tool_name is not None or blocked_est_cost is not None):
            # A pre-call block can fire while spent <= budget_cny (the
            # blocking call hasn't executed yet, so it isn't in `spent` at
            # all) — over_by_cny above would then be negative, showing "job
            # is under budget" while asking the user to approve an apparent
            # overspend, with no visibility into which call actually
            # triggered it. Name the blocking call explicitly instead of
            # relying on the generic spent/budget_cny/over_by_cny shape alone.
            preview["blocked_tool_name"] = blocked_tool_name
            preview["blocked_est_cost_cny"] = blocked_est_cost
            preview["projected_cny"] = projected_cny
            budget_exceeded_event["blocked_tool_name"] = blocked_tool_name
            budget_exceeded_event["blocked_est_cost_cny"] = blocked_est_cost
            budget_exceeded_event["projected_cny"] = projected_cny
        expires_at = _pause_for_approval(job_id, "budget", gate="budget", preview=preview)
        _emit(job_id, budget_exceeded_event)
        approval = await _wait_for_decision(job_id, "budget", gate="budget", expires_at=expires_at)
        if (job_store.get(job_id) or {}).get("cancel_requested"):
            raise JobCancelled()
        if approval["action"] == "timeout":
            _fail_job(
                job_id, stage="budget",
                message=_approval_expired_message("budget"),
                set_current_stage=False,
            )
            return False
        if approval["action"] == "reject":
            # set_current_stage=False: "budget" names the gate in the event,
            # not a pipeline stage — the job record's current_stage must keep
            # pointing at the real stage that was running when the gate fired.
            _fail_job(
                job_id, stage="budget",
                message=f"Budget ¥{budget_cny} exceeded (spent ¥{spent}); aborted by user",
                set_current_stage=False,
            )
            return False
        # Re-arm at a new, higher ceiling instead of permanently disabling
        # budget protection for the rest of the job (the previous
        # `budget_overridden` flag did that — approving one small overage
        # early silently waived every later stage's check too, no matter how
        # much more expensive).
        #
        # The ceiling the user CHOSE wins (roadmap 1.3): the approve request
        # can carry new_budget_cny, an absolute cap in CNY. Without it, fall
        # back to the old 20% headroom heuristic — which was an unbounded
        # ratchet the user never picked (approve, spend to the new ceiling,
        # be asked again, ×1.2 forever).
        #
        # Either way the new ceiling is floored so the just-approved
        # continuation isn't immediately re-blocked: on the force=True
        # pre-call-block path `spent` does NOT include the blocked call's own
        # cost (it never ran) — the blocked call's projected_cny (the spend
        # IF it's admitted) is the real floor there.
        old_budget_cny = budget_cny
        floor = projected_cny if (force and projected_cny is not None) else spent
        user_budget = approval.get("new_budget_cny")
        if user_budget is not None:
            try:
                budget_cny = round(max(float(user_budget), floor), 4)
            except (TypeError, ValueError):
                user_budget = None
        if user_budget is None:
            if force and projected_cny is not None:
                budget_cny = round(max(budget_cny, projected_cny) * 1.2, 4)
            else:
                budget_cny = round(spent * 1.2, 4)
        if cost_tracker is not None:
            # Keep the ledger's recorded ceiling in sync for anything
            # inspecting cost_log.json. A direct in-memory attribute bump —
            # not a new CostTracker method or any other change to
            # tools/cost_tracker.py — to stay clear of that file entirely.
            # Safe only because this assignment always runs on the event
            # loop after the stage's asyncio.to_thread call has fully
            # returned — i.e. nothing else is concurrently calling
            # cost_tracker.reserve() (which reads this same attribute while
            # holding cost_tracker._lock) at this moment. A future change
            # that lets a stage's thread keep running past this point (e.g.
            # concurrent stages) must not bypass that lock here.
            cost_tracker.budget_total_usd = budget_cny
        job_store.update(job_id, status="running")
        _emit(job_id, {
            "type": "stage_approved", "stage": "budget",
            "budget_cny": budget_cny, "previous_budget_cny": old_budget_cny,
        })
        return True

    async def _sample_preview_gate(stage_name: str, spn: SamplePreviewNeeded) -> list[dict] | None:
        """Pause for a real approval on a mid-stage sample-preview checkpoint
        and return the resume_messages to feed back into _run_agent_stage —
        or None when the approval window expired (the job is already marked
        failed here; the caller just unwinds).

        Reuses the exact same awaiting_approval/wait_for_approval primitive
        as the stage-boundary and budget gates — this is a genuine pause,
        the SAME conversation resumes afterward, not a fresh one.
        """
        expires_at = _pause_for_approval(job_id, stage_name, gate="sample_preview", preview={
            "text": spn.preview_text,
            "iteration": spn.sample_iteration + 1,
            "max_iterations": MAX_SAMPLE_ITERATIONS,
        })
        approval = await _wait_for_decision(
            job_id, stage_name, gate="sample_preview", expires_at=expires_at
        )
        if (job_store.get(job_id) or {}).get("cancel_requested"):
            raise JobCancelled()
        if approval["action"] == "timeout":
            _fail_job(job_id, stage=stage_name, message=_approval_expired_message(stage_name))
            return None
        job_store.update(job_id, status="running")
        if approval["action"] == "reject":
            fb = approval.get("feedback") or "Not approved as-is — reconsider your approach."
            _emit(job_id, {"type": "stage_rejected", "stage": stage_name, "gate": "sample_preview", "feedback": fb,
                            **({"actor": approval["actor"]} if approval.get("actor") else {})})
            resume_text = f"Rejected: {fb}. Adjust your approach and try again."
        else:
            _emit(job_id, {"type": "stage_approved", "stage": stage_name, "gate": "sample_preview",
                            **({"actor": approval["actor"]} if approval.get("actor") else {})})
            resume_text = "Approved — proceed to complete the stage."
        return spn.messages + [{"role": "user", "content": resume_text}]

    async def _call_stage(
        stage_def: dict, stage_name: str, skill_text: str, feedback: str
    ) -> bool | None:
        """Run one _run_agent_stage attempt, owning the gate-handling loop
        around it (previously duplicated verbatim at the initial-run and
        reject-regenerate call sites). Returns the stage's genuine outcome
        (True/False), or None when the job is already marked failed by a
        gate (user rejected at the budget gate, or an approval window
        expired) — the caller just returns.

        The stage runs in a thread pool (blocking sync LLM calls must not
        block the event loop). A pre-call budget block raises BudgetGateNeeded
        out of the thread — pause for the human decision, and on approval
        re-run at the gate's newly re-armed (raised) ceiling, never with the
        check fully disabled. A mid-stage SamplePreviewNeeded pauses the same
        way but resumes the SAME conversation (resume_messages) rather than
        re-running from scratch. Neither pause consumes one of the caller's
        retry rounds — this helper loops internally on the resume cases and
        returns only on a genuine outcome. Resume state (resume_messages/
        sample_iteration) is local to a single call, so every fresh call
        naturally starts a fresh conversation.
        """
        resume_messages: list[dict] | None = None
        sample_iteration = 0
        while True:
            try:
                # _run_agent_stage is deliberately looked up as a module
                # global at call time (a bare name, never captured/aliased)
                # so tests monkeypatching stage_runner._run_agent_stage keep
                # intercepting this call.
                return await asyncio.to_thread(
                    _run_agent_stage,
                    job_id, stage_name, skill_text, project_dir,
                    brand_info, options,
                    feedback=feedback,
                    cost_accumulator=cost_accumulator,
                    cost_tracker=cost_tracker,
                    budget_cny=budget_cny,
                    base_cost=base_cost,
                    produces=stage_def.get("produces"),
                    resume_messages=resume_messages,
                    sample_iteration=sample_iteration,
                    max_turns=stage_def.get("max_turns", MAX_TURNS),
                    temperature=stage_def.get("temperature", 0.7),
                    required_artifacts_in=stage_def.get("required_artifacts_in"),
                )
            except BudgetGateNeeded as bgn:
                _sync_cost(stage_name)
                if not await _budget_gate(force=True, triggering_exc=bgn.budget_exc):
                    return None
                # Resume the SAME conversation (not a fresh one) at the newly
                # re-armed ceiling — restarting from scratch would orphan any
                # assets already generated earlier in this stage's
                # conversation (see BudgetGateNeeded's docstring).
                resume_messages = bgn.messages + [{
                    "role": "user",
                    "content": f"Budget approved at new ceiling ¥{budget_cny} — retry the blocked call.",
                }]
                continue   # resume, doesn't consume a retry round
            except BudgetExceededError:
                # Defensive fallback that shouldn't normally trigger: a raw
                # BudgetExceededError reaching here unwrapped (the normal
                # tool-call path in _run_agent_stage always converts it to
                # BudgetGateNeeded first, preserving `messages`) — fall back
                # to the old restart-from-scratch behavior rather than crash.
                _sync_cost(stage_name)
                if not await _budget_gate(force=True):
                    return None
                continue   # approved overspend → re-run at the raised ceiling
            except SamplePreviewNeeded as spn:
                _sync_cost(stage_name)
                resume_messages = await _sample_preview_gate(stage_name, spn)
                if resume_messages is None:
                    return None   # approval window expired — job already marked failed
                sample_iteration = spn.sample_iteration + 1
                continue   # resume the same conversation, doesn't consume a retry round

    job_store.update(job_id, status="running", project_dir=str(project_dir))
    _emit(job_id, {
        "type": "job_started",
        "pipeline": pipeline_name,
        "stages": [s["name"] for s in stages],
        "resumed": bool(completed_stages),
    })

    for stage_def in stages:
        stage_name = stage_def["name"]
        skill_rel = stage_def.get("skill")
        needs_approval = stage_def["approval"]

        # Catches a job cancelled while queued (never got as far as a single
        # stage) and one cancelled between stages while running — the
        # per-turn check inside _run_agent_stage handles cancellation
        # mid-stage.
        if (job_store.get(job_id) or {}).get("cancel_requested"):
            raise JobCancelled()

        # Resume support: a retry must NOT re-run or overwrite stages that already
        # finished (and, for approval stages, were already approved).
        if stage_name in completed_stages:
            _emit(job_id, {"type": "stage_skipped", "stage": stage_name})
            continue

        job_store.update(job_id, current_stage=stage_name, status="running")
        _emit(job_id, {"type": "stage_started", "stage": stage_name})
        _write_stage_checkpoint(project_dir, project_name, pipeline_type, stage_def, "in_progress")

        # Preflight: fail fast with a clear diagnostic if an upstream artifact
        # this stage requires is missing, rather than silently launching the
        # LLM call on an incomplete "Available artifacts" summary (it would
        # likely improvise something plausible-looking instead of surfacing
        # the real problem — e.g. a broken resume, a naming mismatch, or a
        # skipped stage from a hand-edited job).
        required = stage_def.get("required_artifacts_in") or []
        if required:
            have = set(_load_artifacts(project_dir))
            missing = [name for name in required if name not in have]
            if missing:
                _fail_job(job_id, stage=stage_name, message=(
                    f"Stage '{stage_name}' requires artifact(s) {missing} "
                    f"which were not found in {project_dir / 'artifacts'}"
                ))
                return

        # Load director skill. Some manifest stages (e.g. sub_stages-only or
        # deliberately instruction-free stages) declare no skill at all —
        # skill_rel is None there, not "" (Path(OM_ROOT) / "" is OM_ROOT
        # itself, a directory, which would defeat this fallback).
        skill_path = (OM_ROOT / skill_rel) if skill_rel else None
        skill_text = (
            skill_path.read_text(encoding="utf-8")
            if skill_path and skill_path.exists()
            else f"# {stage_name} director\nExecute the {stage_name} stage."
        )

        # Each attempt goes through _call_stage (the shared gate-handling
        # loop around asyncio.to_thread(_run_agent_stage, ...) — budget gate,
        # sample-preview gate, and their resume state, none of which consume
        # a retry round; see _call_stage's docstring). This outer loop owns
        # only the bounded auto-retry bookkeeping (MAX_ROUNDS) for genuine
        # failures.
        success = False
        # A revise clone (POST /jobs/{id}/revise, roadmap 2.2) carries the
        # user's feedback for the stage being re-entered — thread it into
        # the stage's very first conversation instead of losing it.
        _revise = (job_store.get(job_id) or {}).get("revise_feedback") or {}
        feedback = _revise.get("feedback", "") if _revise.get("stage") == stage_name else ""
        _round = 0
        while _round <= MAX_ROUNDS:
            outcome = await _call_stage(stage_def, stage_name, skill_text, feedback)
            if outcome is None:
                return   # user rejected at the budget gate — job already marked failed
            success = outcome
            _sync_cost(stage_name)
            if success:
                break
            _emit(job_id, {"type": "stage_retry", "stage": stage_name, "round": _round + 1})
            _round += 1
            # Fold the last failure into feedback so the retry's brand-new
            # conversation at least knows what went wrong last time, instead
            # of reproducing the identical outcome up to MAX_ROUNDS times.
            # (A genuine retry starts a fresh conversation — _call_stage's
            # resume state is per-call, so there's nothing to reset here.)
            last_error = _last_failure_message(job_id, stage_name)
            if last_error:
                feedback = f"Your previous attempt at this stage failed: {last_error}"

        if not success:
            # Reuse the same "what actually went wrong" diagnostic the
            # missing-produces failure right below already includes — this
            # emit used to carry no message field at all, leaving operators
            # with nothing actionable for a max-turns/retries-exhausted
            # failure specifically.
            _fail_job(job_id, stage=stage_name, message=(
                _last_failure_message(job_id, stage_name)
                or f"Stage '{stage_name}' failed after exhausting its retries."
            ))
            return

        missing = _missing_produces(project_dir, stage_def)
        if missing is not None:
            _fail_job(job_id, stage=stage_name, message=(
                f"Stage '{stage_name}' finished without writing any of its required "
                f"artifact(s) {missing} — check the event log above; the agent may "
                f"have stopped to ask for a decision (e.g. a generation provider "
                f"failure) instead of completing. Retry will re-run this stage."
            ))
            return

        # Nothing else validates that edit_decisions.render_runtime matches
        # what was actually locked at proposal — confirmed live: proposal
        # locked a render_runtime with an explicit decision_log entry
        # demanding "no silent fallback to FFmpeg", yet edit_decisions
        # silently switched to 'ffmpeg' with no new decision_log entry and no
        # escalation, and the edit stage has no human approval gate to catch
        # it. See _check_render_runtime_consistency's docstring.
        if stage_name == "edit":
            runtime_mismatch = _check_render_runtime_consistency(project_dir)
            if runtime_mismatch:
                _fail_job(job_id, stage=stage_name, message=runtime_mismatch)
                return

        # Every completing stage's claims about what it actually produced are
        # checked against reality by ONE produces-keyed table,
        # _PRODUCES_EXPORT_VALIDATORS — this used to be four separate
        # mechanisms, bolted on one at a time as each fabrication incident was
        # found live:
        #   1. A literal `stage_name == "compose"` check that a real file
        #      exists under renders/ (the same glob the preview/final-video
        #      UI relies on) — confirmed live: an agent that hit a
        #      video_compose failure fabricated a plausible-looking
        #      render_report (invented file paths under a DIFFERENT project
        #      name, invented file sizes, an invented render duration)
        #      instead of retrying or reporting the failure honestly, and the
        #      job then showed as "completed" with zero actual deliverable.
        #      render_report/final_review existing is not proof a video
        #      actually got rendered — don't trust the artifact's own claims.
        #   2. A separate _render_report_path_diverges() warning check —
        #      render_report's own claims (output path here; runtime/counts
        #      elsewhere) are never cross-validated against reality
        #      otherwise — confirmed live: render_report claimed a DIFFERENT
        #      output filename than the one actually discovered on disk. A
        #      wrong internal path claim while a real file DOES exist is
        #      lower-severity than no file at all — warn, don't fail.
        #   3. A separate _missing_variants() call — the file-exists check
        #      alone only requires ANY render file to exist; in a
        #      multi-variant A/B job (options.video_model_variants declares
        #      more than one model) that passes even when some declared
        #      variants never actually rendered (e.g. 2 of 3 succeeded, the
        #      3rd's generation call failed). Silently completing with
        #      partial output would hide that a whole variant is missing —
        #      require every declared variant to have its own render file.
        #   4. This same produces-keyed loop, previously carrying only the
        #      publish_log case — confirmed live: a publish_log artifact
        #      claimed 5 real export files (teaser cut, platform-specific
        #      crops, poster frame) that were never generated (no exports/
        #      directory ever created, zero video-processing tool calls in
        #      that stage's trace).
        # (1)-(3) are now folded into a "render_report" table entry (see
        # _validate_render_report_produces in render_checks.py) so any
        # current/future stage whose produces declares a validated artifact
        # name gets the same anti-fabrication treatment through one
        # mechanism, instead of each new incident growing its own bespoke
        # wiring here. Each validator returns a ProducesValidation
        # (hard_failures + warnings) so every entry — file-existence,
        # path-divergence, variant-completeness, export-existence — is
        # handled uniformly at this single call site.
        #
        # "render_report"'s activation is gated on the literal stage name
        # "compose", NOT on a declared produces list — this mirrors the
        # ORIGINAL behavior exactly (the render-file check used to be a bare
        # `stage_name == "compose"` check with no produces involvement at
        # all), and is exactly why a stage genuinely renamed away from
        # "compose" (but still declaring produces=["render_report"]) does NOT
        # get this per-stage check and instead relies solely on the SEPARATE
        # job-completion-level `expects_render` fallback near the end of this
        # function (see
        # test_job_completion_refuses_without_render_file_even_if_stage_not_named_compose,
        # which asserts exactly that gap). Every OTHER entry (e.g.
        # publish_log) keeps the produces-keyed activation it always had.
        _produces_to_validate = set(stage_def.get("produces") or [])
        if stage_name == "compose":
            _produces_to_validate.add("render_report")
        else:
            _produces_to_validate.discard("render_report")
        for _artifact_name, _validator in _PRODUCES_EXPORT_VALIDATORS.items():
            if _artifact_name not in _produces_to_validate:
                continue
            _artifact_value = _load_artifacts(project_dir).get(_artifact_name) or {}
            _validation = _validator(project_dir, _artifact_value, options)
            for _warning_msg in _validation.warnings:
                _emit(job_id, {"type": "warning", "stage": stage_name, "message": _warning_msg})
            if _validation.hard_failures:
                _fail_job(job_id, stage=stage_name, message=(
                    f"Stage '{stage_name}': " + " ".join(_validation.hard_failures)
                ))
                return

        # Multi-shot subject consistency (roadmap 3.3) — advisory warning
        # BEFORE the approval gate, so the filmstrip review sees it.
        if "asset_manifest" in (stage_def.get("produces") or []):
            _run_asset_consistency_check(job_id, project_dir)

        _emit(job_id, {"type": "stage_completed", "stage": stage_name})

        # Interim preview: the compose stage produces the actual rendered
        # video, but publish (packaging/distribution metadata) still has to
        # run before the job is "completed" — that's several more turns the
        # user would otherwise wait through with no way to see the render
        # they're actually waiting on. Surface it as soon as it exists.
        if stage_name == "compose":
            preview_url = _discover_render_url(project_dir, project_name)
            preview_urls = _discover_render_urls(project_dir, project_name)
            if preview_url:
                update_kwargs: dict[str, Any] = {"preview_render_url": preview_url}
                if preview_urls:
                    update_kwargs["preview_render_urls"] = preview_urls
                job_store.update(job_id, **update_kwargs)
                _emit(job_id, {
                    "type": "preview_ready",
                    "render_url": preview_url,
                    **({"render_urls": preview_urls} if preview_urls else {}),
                })

        # Human approval gate — loop so repeated rejections each regenerate AND
        # re-present for approval (previously a rejected artifact silently passed).
        if needs_approval:
            def _preview() -> tuple[Any, str | None]:
                # The agent's write_artifact call is instructed to use the
                # manifest's real produces name (see the prompt hint above),
                # but fall back to trying the stage name itself first — some
                # skills/older manifests still name the artifact after the
                # stage. Return (value, artifact_name) for the first file
                # that actually exists — the name drives the UI's structured
                # renderer choice.
                arts = _load_artifacts(project_dir)
                if stage_name in arts:
                    return arts[stage_name], stage_name
                for name in stage_def.get("produces") or []:
                    if name in arts:
                        return arts[name], name
                return None, None

            preview_value, preview_name = _preview()
            _write_stage_checkpoint(
                project_dir, project_name, pipeline_type, stage_def, "awaiting_human",
                cost_cny=round(base_cost + sum(cost_accumulator), 4),
            )
            expires_at = _pause_for_approval(
                job_id, stage_name, preview=preview_value, preview_artifact=preview_name
            )
            approval = await _wait_for_decision(job_id, stage_name, expires_at=expires_at)
            if (job_store.get(job_id) or {}).get("cancel_requested"):
                raise JobCancelled()
            if approval["action"] == "timeout":
                _fail_job(job_id, stage=stage_name, message=_approval_expired_message(stage_name))
                return

            # Bounded reject→regenerate loop: each round is a fresh paid LLM
            # conversation, and the loop used to be unbounded even though
            # every manifest declares orchestration.max_revisions_per_stage.
            # When the budget is spent, pause on a final explicit gate
            # (gate="revisions_exhausted") instead of regenerating again:
            # approve = accept the latest artifact as-is and continue; reject
            # = stop the job. Never auto-approve.
            max_revisions = _resolve_max_revisions(pipeline_name)
            revisions_used = 0
            while approval["action"] == "reject":
                if revisions_used >= max_revisions:
                    expires_at = _pause_for_approval(
                        job_id, stage_name, gate="revisions_exhausted", preview={
                            "revisions_used": revisions_used,
                            "max_revisions": max_revisions,
                            "text": (
                                f"Stage '{stage_name}' has used all {max_revisions} "
                                "revision rounds. Approve to accept the current "
                                "artifact as-is and continue, or reject to stop "
                                "the job."
                            ),
                        })
                    approval = await _wait_for_decision(
                        job_id, stage_name, gate="revisions_exhausted", expires_at=expires_at
                    )
                    if (job_store.get(job_id) or {}).get("cancel_requested"):
                        raise JobCancelled()
                    if approval["action"] == "approve":
                        break   # accept the latest artifact as-is
                    if approval["action"] == "timeout":
                        _fail_job(job_id, stage=stage_name,
                                  message=_approval_expired_message(stage_name))
                        return
                    _fail_job(job_id, stage=stage_name, message=(
                        f"Stage '{stage_name}' exhausted its "
                        f"{max_revisions} revision rounds and the user chose "
                        "to stop rather than accept the latest artifact."
                    ))
                    return
                revisions_used += 1
                feedback = approval.get("feedback", "")
                # Per-scene keep/reroll (roadmap 2.3): the reject carried the
                # SPECIFIC manifest asset ids to redo. Everything else is
                # kept — and re-issuing an identical generation call reuses
                # the content-addressed file at zero cost, so "选择免费、
                # 生成计费" holds mechanically, not just as instruction.
                rejected_ids = approval.get("rejected_asset_ids") or []
                if rejected_ids:
                    reroll_instruction = (
                        "Per-asset reroll request: regenerate ONLY the assets with "
                        f"these ids from asset_manifest: {rejected_ids}. For each, call "
                        "the generation tool again with inputs.force_regenerate=true "
                        "(bypasses the asset cache — without it an identical prompt "
                        "returns the very file the user just rejected), adjusting the "
                        "prompt per the user's feedback if any. Keep every OTHER asset "
                        "exactly as-is: re-issue the identical call WITHOUT "
                        "force_regenerate and the existing file is reused at zero cost. "
                        "Rewrite asset_manifest so rerolled entries point at their NEW "
                        "file paths; keep kept entries byte-identical."
                    )
                    feedback = f"{feedback}\n\n{reroll_instruction}" if feedback else reroll_instruction
                job_store.update(job_id, status="running")
                _emit(job_id, {"type": "stage_rejected", "stage": stage_name, "feedback": feedback,
                                **({"actor": approval["actor"]} if approval.get("actor") else {})})
                # Snapshot before regenerating — see _artifact_mtimes' docstring
                # for why file *presence* alone can't detect a no-op round.
                mtimes_before = _artifact_mtimes(project_dir, stage_def.get("produces") or [])
                # Re-run with feedback through the same shared gate-handling
                # loop as the initial run (never block the event loop) and
                # keep accumulating cost. Same budget gate + produces hint as
                # the first run — previously this call dropped budget_cny/
                # base_cost entirely, letting a reject-regenerate loop bypass
                # the pre-call budget ceiling.
                outcome = await _call_stage(stage_def, stage_name, skill_text, feedback)
                if outcome is None:
                    return   # user rejected at the budget gate — job already marked failed
                success = outcome
                _sync_cost(stage_name)
                if not success:
                    # Same gap as the initial-run failure path above: reuse
                    # the last recorded error as an actionable diagnostic
                    # instead of an emit with no message field.
                    # set_current_stage=False only to keep the update payload
                    # identical to what this site always sent — current_stage
                    # was already set to this stage when it started.
                    _fail_job(job_id, stage=stage_name, message=(
                        _last_failure_message(job_id, stage_name)
                        or f"Stage '{stage_name}' failed after exhausting its retries."
                    ), set_current_stage=False)
                    return
                # A regenerate round can go the same way the very first run
                # can (line ~857 above): the agent's turn loop can end
                # (success=True) without ever calling write_artifact again —
                # e.g. a text-only first turn after rejection. Checking mere
                # file *presence* isn't enough here: by construction, every
                # declared artifact already exists on disk (left over from
                # the just-rejected round) before this call even starts, so
                # _missing_produces alone would report "nothing missing"
                # regardless of whether anything was actually rewritten.
                # Compare mtimes against the pre-regenerate snapshot instead —
                # if nothing changed, the round was a no-op and the user's
                # feedback was silently ignored rather than acted on.
                still_missing = _missing_produces(project_dir, stage_def)
                mtimes_after = _artifact_mtimes(project_dir, stage_def.get("produces") or [])
                untouched = [n for n in mtimes_before if mtimes_after.get(n) == mtimes_before[n]]
                if still_missing is not None or untouched:
                    _fail_job(job_id, stage=stage_name, message=(
                        f"Stage '{stage_name}' was rejected, but the regenerated run "
                        "finished without actually rewriting its required "
                        f"artifact(s) {still_missing or untouched} — the agent may have "
                        "stopped without acting on your feedback. Retry will re-run this stage."
                    ))
                    return
                _emit(job_id, {"type": "stage_completed", "stage": stage_name})
                preview_value, preview_name = _preview()
                _write_stage_checkpoint(
                    project_dir, project_name, pipeline_type, stage_def, "awaiting_human",
                    cost_cny=round(base_cost + sum(cost_accumulator), 4),
                )
                expires_at = _pause_for_approval(
                    job_id, stage_name, preview=preview_value, preview_artifact=preview_name
                )
                approval = await _wait_for_decision(job_id, stage_name, expires_at=expires_at)
                if (job_store.get(job_id) or {}).get("cancel_requested"):
                    raise JobCancelled()
                if approval["action"] == "timeout":
                    _fail_job(job_id, stage=stage_name,
                              message=_approval_expired_message(stage_name))
                    return

            job_store.update(job_id, status="running")
            _emit(job_id, {"type": "stage_approved", "stage": stage_name,
                           **({"actor": approval["actor"]} if approval.get("actor") else {})})

        # Mark done so a later retry resumes after this stage.
        completed_stages.add(stage_name)
        job_store.update(job_id, completed_stages=sorted(completed_stages))
        _write_stage_checkpoint(
            project_dir, project_name, pipeline_type, stage_def, "completed",
            approved=needs_approval,   # gated stages reach here only after approval
            cost_cny=round(base_cost + sum(cost_accumulator), 4),
        )

        # Budget gate — pause for approval if cumulative cost crossed the ceiling.
        if not await _budget_gate():
            return

    # All stages complete — locate the final deliverable robustly.
    # Prefer renders/, but fall back to any mp4 under assets/ (or a misnamed
    # .bin the compose tool may have produced) so the player still works.
    render_url = _discover_render_url(project_dir, project_name)
    render_urls = _discover_render_urls(project_dir, project_name)

    # Second line of defense against the same fabrication scenario the
    # per-stage `stage_name == "compose"` check above already guards
    # against, but independent of that literal stage name. Every current
    # pipeline_defs/*.yaml manifest happens to name its render-producing
    # stage "compose" (declaring produces=["render_report", ...]) — but
    # that's a convention this runner doesn't enforce anywhere else. If a
    # future manifest names that stage something else, the per-stage guard
    # above silently never fires, and without this check the job would still
    # complete right here with a None render_url. Key off the stage's
    # declared `produces` contract (the canonical compose output per
    # AGENT_GUIDE.md's Stage Agents table is "render_report"), not its name,
    # so this holds regardless of what the stage is called. A pipeline that
    # genuinely never declares a render-producing stage (e.g. the
    # framework-smoke test pipeline) is unaffected — expects_render is False
    # for it, matching its actual, non-video deliverable.
    expects_render = any("render_report" in (s.get("produces") or []) for s in stages)
    if expects_render and not render_url:
        _fail_job(job_id, message=(
            "All stages reported complete but no render file was discovered "
            f"under {project_dir / 'renders'}, even though this pipeline "
            "declares a render-producing stage — refusing to mark the job "
            "completed without a real deliverable."
        ))
        return

    update_kwargs: dict[str, Any] = {"status": "completed", "render_url": render_url}
    if render_urls:
        update_kwargs["render_urls"] = render_urls
    job_store.update(job_id, **update_kwargs)
    _emit(job_id, {
        "type": "job_completed",
        "render_url": render_url,
        **({"render_urls": render_urls} if render_urls else {}),
    })


def _check_render_runtime_consistency(project_dir: Path) -> str | None:
    """Return a failure message if edit_decisions.render_runtime silently
    diverges from the render_runtime locked at proposal
    (proposal_packet.production_plan.render_runtime) with no decision_log
    entry justifying the change — else None.

    Confirmed live: proposal locked a Remotion-vs-HyperFrames decision with
    an explicit decision_log entry saying "must use selected render_runtime
    without silent fallback to FFmpeg ... if unavailable, surface blocker to
    user", yet edit_decisions silently set render_runtime='ffmpeg' with no
    new decision_log entry and no escalation — the edit stage has no human
    approval gate to catch this on its own. A justifying entry must be
    logged with stage="edit" specifically (not just the original
    proposal-stage render_runtime_selection entry that locked the value in
    the first place) — otherwise every divergence would trivially "pass"
    just because a render_runtime_selection entry exists somewhere from
    proposal.
    """
    artifacts = _load_artifacts(project_dir)
    edit_decisions = artifacts.get("edit_decisions") or {}
    proposal_packet = artifacts.get("proposal_packet") or {}
    edit_runtime = edit_decisions.get("render_runtime")
    locked_runtime = (proposal_packet.get("production_plan") or {}).get("render_runtime")
    if not edit_runtime or not locked_runtime or edit_runtime == locked_runtime:
        return None
    decision_log = artifacts.get("decision_log") or {}
    justified = any(
        isinstance(d, dict)
        and d.get("category") == "render_runtime_selection"
        and d.get("stage") == "edit"
        for d in (decision_log.get("decisions") or [])
    )
    if justified:
        return None
    return (
        f"Stage 'edit' set edit_decisions.render_runtime='{edit_runtime}', which "
        f"diverges from the render_runtime locked at proposal "
        f"('{locked_runtime}', proposal_packet.production_plan.render_runtime), with "
        "no decision_log entry (category='render_runtime_selection', stage='edit') "
        f"justifying the change. Either match the locked runtime ('{locked_runtime}') "
        "or log a proper decision_log entry explaining the override."
    )
