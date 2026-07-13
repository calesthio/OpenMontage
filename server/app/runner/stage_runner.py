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
    TOOL_SCHEMAS, execute_tool, BudgetExceededError, variant_slug, READ_FILE_CHAR_CAP,
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

# ── Cinematic pipeline stage definitions ─────────────────────────────────────
CINEMATIC_STAGES = [
    {"name": "research",    "skill": "skills/pipelines/cinematic/research-director.md",   "approval": False, "produces": ["research_brief"], "required_artifacts_in": []},
    {"name": "proposal",    "skill": "skills/pipelines/cinematic/proposal-director.md",   "approval": True,  "produces": ["proposal_packet", "decision_log"], "required_artifacts_in": ["research_brief"]},
    {"name": "script",      "skill": "skills/pipelines/cinematic/script-director.md",     "approval": True,  "produces": ["script"], "required_artifacts_in": ["proposal_packet"]},
    # scene_plan/assets/publish must mirror pipeline_defs/cinematic.yaml's
    # human_approval_default exactly — this hardcoded list drifted false for
    # all three (confirmed via a deep code review) while the manifest and
    # every one of these stages' own director skills ("Gate Reminder
    # (Binding)") were updated to require a checkpoint, silently skipping the
    # asset-generation cost gate for every job run through this runner.
    # scene_plan/assets/edit/compose write schema-shaped JSON that downstream
    # stages parse structurally — a lower temperature trades away creative
    # variance (not needed here) for more reliable schema-following and less
    # truncation/format drift, vs. the default 0.7 kept for the genuinely
    # creative stages (research, proposal, script, publish).
    {"name": "scene_plan",  "skill": "skills/pipelines/cinematic/scene-director.md",      "approval": True,  "produces": ["scene_plan"], "required_artifacts_in": ["script"], "temperature": 0.3},
    # max_turns doubled vs. the global default (20) — this stage places one
    # or more generation calls (video/image/tts) per scene across the whole
    # scene_plan, which routinely needs more turns than a single-artifact
    # planning stage.
    {"name": "assets",      "skill": "skills/pipelines/cinematic/asset-director.md",      "approval": True,  "produces": ["asset_manifest"], "required_artifacts_in": ["scene_plan"], "max_turns": 40, "temperature": 0.3},
    {"name": "edit",        "skill": "skills/pipelines/cinematic/edit-director.md",       "approval": False, "produces": ["edit_decisions"], "required_artifacts_in": ["scene_plan", "asset_manifest"], "temperature": 0.3},
    # max_turns doubled vs. the global default (20), same rationale as
    # "assets" above — compose is at least as tool-call-heavy (per-variant
    # render calls, trim/stitch/color-grade/audio-mix passes, etc.) and
    # confirmed live to hit the 20-turn ceiling on a real run.
    {"name": "compose",     "skill": "skills/pipelines/cinematic/compose-director.md",    "approval": False, "produces": ["render_report", "final_review"], "required_artifacts_in": ["edit_decisions", "asset_manifest"], "max_turns": 40, "temperature": 0.3},
    {"name": "publish",     "skill": "skills/pipelines/cinematic/publish-director.md",    "approval": True,  "produces": ["publish_log"], "required_artifacts_in": ["render_report", "final_review"]},
]

# Explicit overrides / aliases. Anything NOT here is resolved dynamically from
# the engine's pipeline_defs/<name>.yaml manifest, so every engine pipeline
# (animated-explainer, screen-demo, podcast-repurpose, …) is runnable via the
# web platform without hardcoding its stages here.
PIPELINE_MAP = {
    "cinematic": CINEMATIC_STAGES,
    "marketing_film": CINEMATIC_STAGES,   # alias → cinematic stages
}


def _resolve_stages(pipeline_name: str) -> list[dict]:
    """Return the stage list for a pipeline.

    Precedence: explicit PIPELINE_MAP override → pipeline_defs manifest →
    cinematic fallback. Manifest stages map skill "pipelines/x/y-director" to
    "skills/pipelines/x/y-director.md" and human_approval_default to approval.
    """
    if pipeline_name in PIPELINE_MAP:
        return PIPELINE_MAP[pipeline_name]
    try:
        from app.pipeline_catalog import load_manifest
        manifest = load_manifest(pipeline_name)
        stages = []
        for s in manifest.get("stages", []):
            skill = s.get("skill")
            stages.append({
                "name": s["name"],
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
            })
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
    return CINEMATIC_STAGES

MAX_TURNS  = 20
# How many pause→resume round-trips a single stage run allows for its
# mid-stage sample-preview checkpoint (see SamplePreviewNeeded below) before
# giving up. Mirrors asset-director.md's own "max 3 iterations" policy for a
# rejected sample.
MAX_SAMPLE_ITERATIONS = 3


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
                    emit_event=lambda ev: _emit(job_id, ev),
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
        job_store.update(job_id, status="failed")
        _emit(job_id, {
            "type": "job_failed",
            "message": f"Unhandled pipeline error: {exc}",
            "trace": traceback.format_exc()[-1500:],
        })
    finally:
        _ACTIVE_JOB_IDS.discard(job_id)


async def _run_pipeline_impl(job_id: str, data: dict) -> None:
    pipeline_name = data.get("pipeline", "cinematic")
    stages = _resolve_stages(pipeline_name)
    brand_info = data.get("brand_info", {})
    options = data.get("options", {})
    project_name = data.get("project_name", job_id)

    project_dir = OM_ROOT / "projects" / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "artifacts").mkdir(exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)
    (project_dir / "renders").mkdir(exist_ok=True)

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
        job_store.update(job_id, status="awaiting_approval")
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
        _emit(job_id, {
            "type": "awaiting_approval",
            "stage": "budget",
            "gate": "budget",
            "preview": preview,
        })
        _emit(job_id, budget_exceeded_event)
        approval = await job_store.wait_for_approval(job_id, timeout=3600.0)
        if (job_store.get(job_id) or {}).get("cancel_requested"):
            raise JobCancelled()
        if approval["action"] == "reject":
            job_store.update(job_id, status="failed")
            _emit(job_id, {"type": "job_failed", "stage": "budget",
                           "message": f"Budget ¥{budget_cny} exceeded (spent ¥{spent}); aborted by user"})
            return False
        # Re-arm at a new, higher ceiling instead of permanently disabling
        # budget protection for the rest of the job (the previous
        # `budget_overridden` flag did that — approving one small overage
        # early silently waived every later stage's check too, no matter how
        # much more expensive). 20% headroom over the actual current spend
        # lets the stage that triggered this approval proceed without an
        # immediate re-prompt for the exact same overage, while still gating
        # again if a LATER stage blows through this new ceiling.
        #
        # On the force=True pre-call-block path, `spent` does NOT include the
        # blocked call's own cost (it never ran) — re-arming off spent*1.2
        # alone can land BELOW what that call actually needs (or even below
        # the previous ceiling), permanently re-blocking the identical call on
        # every future approval. Use the blocked call's own projected_cny (the
        # spend IF it's admitted) as a floor, together with the previous
        # ceiling, so the new ceiling never drops below either.
        old_budget_cny = budget_cny
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

    async def _sample_preview_gate(stage_name: str, spn: SamplePreviewNeeded) -> list[dict]:
        """Pause for a real approval on a mid-stage sample-preview checkpoint
        and return the resume_messages to feed back into _run_agent_stage.

        Reuses the exact same awaiting_approval/wait_for_approval primitive
        as the stage-boundary and budget gates — this is a genuine pause,
        the SAME conversation resumes afterward, not a fresh one.
        """
        job_store.update(job_id, status="awaiting_approval")
        _emit(job_id, {
            "type": "awaiting_approval",
            "stage": stage_name,
            "gate": "sample_preview",
            "preview": {
                "text": spn.preview_text,
                "iteration": spn.sample_iteration + 1,
                "max_iterations": MAX_SAMPLE_ITERATIONS,
            },
        })
        approval = await job_store.wait_for_approval(job_id, timeout=3600.0)
        if (job_store.get(job_id) or {}).get("cancel_requested"):
            raise JobCancelled()
        job_store.update(job_id, status="running")
        if approval["action"] == "reject":
            fb = approval.get("feedback") or "Not approved as-is — reconsider your approach."
            _emit(job_id, {"type": "stage_rejected", "stage": stage_name, "gate": "sample_preview", "feedback": fb})
            resume_text = f"Rejected: {fb}. Adjust your approach and try again."
        else:
            _emit(job_id, {"type": "stage_approved", "stage": stage_name, "gate": "sample_preview"})
            resume_text = "Approved — proceed to complete the stage."
        return spn.messages + [{"role": "user", "content": resume_text}]

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
                job_store.update(job_id, status="failed", current_stage=stage_name)
                _emit(job_id, {
                    "type": "job_failed",
                    "stage": stage_name,
                    "message": (
                        f"Stage '{stage_name}' requires artifact(s) {missing} "
                        f"which were not found in {project_dir / 'artifacts'}"
                    ),
                })
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

        # Run stage in thread pool (blocking sync LLM calls must not block event loop).
        # A pre-call budget block raises BudgetExceededError out of the thread —
        # pause for the human decision, and on approval re-run the stage at the
        # gate's newly re-armed (raised) ceiling, never with the check fully
        # disabled. A mid-stage SamplePreviewNeeded pauses the same way but
        # resumes the SAME conversation (resume_messages) rather than
        # re-running from scratch — it doesn't consume a retry round.
        success = False
        feedback = ""
        resume_messages: list[dict] | None = None
        sample_iteration = 0
        _round = 0
        while _round <= MAX_ROUNDS:
            try:
                success = await asyncio.to_thread(
                    _run_agent_stage,
                    job_id, stage_name, skill_text, project_dir,
                    brand_info, options, feedback, cost_accumulator, cost_tracker,
                    budget_cny, base_cost,
                    stage_def.get("produces"),
                    resume_messages, sample_iteration,
                    max_turns=stage_def.get("max_turns", MAX_TURNS),
                    temperature=stage_def.get("temperature", 0.7),
                    required_artifacts_in=stage_def.get("required_artifacts_in"),
                )
                resume_messages = None
            except BudgetGateNeeded as bgn:
                _sync_cost(stage_name)
                if not await _budget_gate(force=True, triggering_exc=bgn.budget_exc):
                    return
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
                # Defensive fallback: a raw BudgetExceededError reaching here
                # unwrapped (the normal tool-call path in _run_agent_stage
                # always converts it to BudgetGateNeeded first, preserving
                # `messages`) — fall back to the old restart-from-scratch
                # behavior rather than crash.
                _sync_cost(stage_name)
                if not await _budget_gate(force=True):
                    return
                continue   # approved overspend → re-run this stage at the raised ceiling
            except SamplePreviewNeeded as spn:
                _sync_cost(stage_name)
                resume_messages = await _sample_preview_gate(stage_name, spn)
                sample_iteration = spn.sample_iteration + 1
                continue   # resume the same conversation, doesn't consume a retry round
            _sync_cost(stage_name)
            if success:
                break
            _emit(job_id, {"type": "stage_retry", "stage": stage_name, "round": _round + 1})
            _round += 1
            sample_iteration = 0   # a genuine retry starts a fresh conversation
            # Fold the last failure into feedback so the retry's brand-new
            # conversation at least knows what went wrong last time, instead
            # of reproducing the identical outcome up to MAX_ROUNDS times.
            last_error = _last_failure_message(job_id, stage_name)
            if last_error:
                feedback = f"Your previous attempt at this stage failed: {last_error}"

        if not success:
            job_store.update(job_id, status="failed", current_stage=stage_name)
            # Reuse the same "what actually went wrong" diagnostic the
            # missing-produces failure right below already includes — this
            # emit used to carry no message field at all, leaving operators
            # with nothing actionable for a max-turns/retries-exhausted
            # failure specifically.
            _emit(job_id, {
                "type": "job_failed",
                "stage": stage_name,
                "message": (
                    _last_failure_message(job_id, stage_name)
                    or f"Stage '{stage_name}' failed after exhausting its retries."
                ),
            })
            return

        missing = _missing_produces(project_dir, stage_def)
        if missing is not None:
            job_store.update(job_id, status="failed", current_stage=stage_name)
            _emit(job_id, {
                "type": "job_failed",
                "stage": stage_name,
                "message": (
                    f"Stage '{stage_name}' finished without writing any of its required "
                    f"artifact(s) {missing} — check the event log above; the agent may "
                    f"have stopped to ask for a decision (e.g. a generation provider "
                    f"failure) instead of completing. Retry will re-run this stage."
                ),
            })
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
                job_store.update(job_id, status="failed", current_stage=stage_name)
                _emit(job_id, {"type": "job_failed", "stage": stage_name, "message": runtime_mismatch})
                return

        # The compose stage's render_report/final_review artifacts existing
        # (checked above) is NOT proof a video actually got rendered — a
        # video_compose call can fail, and confirmed live: an agent that hit
        # exactly that failure fabricated a plausible-looking render_report
        # (invented file paths under a DIFFERENT project name, invented file
        # sizes, an invented render duration) instead of retrying or
        # reporting the failure honestly, and the job then showed as
        # "completed" with zero actual deliverable. Require a real file under
        # renders/ (the same glob the preview/final-video UI relies on) —
        # don't trust the artifact's own claims about what it produced.
        if stage_name == "compose":
            _compose_render_path = _discover_render_path(project_dir)
            if _compose_render_path is None:
                job_store.update(job_id, status="failed", current_stage=stage_name)
                _emit(job_id, {
                    "type": "job_failed",
                    "stage": stage_name,
                    "message": (
                        "Stage 'compose' wrote render_report/final_review but no actual "
                        f"render file exists under {project_dir / 'renders'} — the "
                        "report's claimed output isn't backed by a real file. Retry will "
                        "re-run this stage."
                    ),
                })
                return
            # render_report's own claims (output path here; runtime/counts
            # elsewhere) are never cross-validated against reality otherwise
            # — confirmed live: render_report claimed a DIFFERENT output
            # filename than the one actually discovered on disk. A wrong
            # internal path claim while a real file DOES exist is
            # lower-severity than no file at all (handled above) — warn,
            # don't fail the stage.
            _render_report = _load_artifacts(project_dir).get("render_report") or {}
            _claimed_path_mismatch = _render_report_path_diverges(
                project_dir, _render_report, _compose_render_path
            )
            if _claimed_path_mismatch:
                _emit(job_id, {
                    "type": "warning",
                    "stage": stage_name,
                    "message": (
                        f"render_report claims output path '{_claimed_path_mismatch}' but "
                        "the actual discovered render file is "
                        f"'{_compose_render_path.relative_to(project_dir)}' — the report's "
                        "internal path claim doesn't match reality (a real file does "
                        "exist, so the stage still proceeds)."
                    ),
                })

        # The generalized anti-fabrication check above (compose/
        # render_report) has no equivalent for other stages that also
        # declare file-backed exports — confirmed live: a publish_log
        # artifact claimed 5 real export files (teaser cut, platform-specific
        # crops, poster frame) that were never generated (no exports/
        # directory ever created, zero video-processing tool calls in that
        # stage's trace). Key off the completing stage's declared `produces`
        # contract rather than a literal stage-name check, so this holds for
        # any current/future stage whose produces includes a validated
        # artifact name (see _PRODUCES_EXPORT_VALIDATORS).
        for _artifact_name, _validator in _PRODUCES_EXPORT_VALIDATORS.items():
            if _artifact_name not in (stage_def.get("produces") or []):
                continue
            _artifact_value = _load_artifacts(project_dir).get(_artifact_name) or {}
            _missing_exports = _validator(project_dir, _artifact_value)
            if _missing_exports:
                job_store.update(job_id, status="failed", current_stage=stage_name)
                _emit(job_id, {
                    "type": "job_failed",
                    "stage": stage_name,
                    "message": (
                        f"Stage '{stage_name}' wrote {_artifact_name} claiming export(s) "
                        f"{_missing_exports}, but no file exists at that path under "
                        f"{project_dir} — the artifact's claimed output isn't backed by a "
                        "real file. Retry will re-run this stage."
                    ),
                })
                return

        # The check above only requires ANY render file to exist — in a
        # multi-variant A/B job (options.video_model_variants declares more
        # than one model) that passes even when some declared variants never
        # actually rendered (e.g. 2 of 3 succeeded, the 3rd's generation
        # call failed). Silently completing with partial output would hide
        # that a whole variant is missing. Require every declared variant to
        # have its own render file before treating this stage as genuinely
        # complete.
        if stage_name == "compose":
            missing_variants = _missing_variants(project_dir, options)
            if missing_variants:
                job_store.update(job_id, status="failed", current_stage=stage_name)
                total_variants = len(options.get("video_model_variants") or [])
                _emit(job_id, {
                    "type": "job_failed",
                    "stage": stage_name,
                    "message": (
                        f"Stage 'compose' is an A/B variants job ({total_variants} "
                        f"declared), but {len(missing_variants)} variant(s) never "
                        f"produced a render file: {missing_variants}. Refusing to mark "
                        "a multi-variant compose stage complete with partial output. "
                        "Retry will re-run this stage."
                    ),
                })
                return

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
            def _preview() -> Any:
                # The agent's write_artifact call is instructed to use the
                # manifest's real produces name (see the prompt hint above),
                # but fall back to trying the stage name itself first — some
                # skills/older manifests still name the artifact after the
                # stage. Return the first file that actually exists.
                arts = _load_artifacts(project_dir)
                if stage_name in arts:
                    return arts[stage_name]
                for name in stage_def.get("produces") or []:
                    if name in arts:
                        return arts[name]
                return None

            job_store.update(job_id, status="awaiting_approval")
            _emit(job_id, {"type": "awaiting_approval", "stage": stage_name, "preview": _preview()})
            approval = await job_store.wait_for_approval(job_id, timeout=3600.0)
            if (job_store.get(job_id) or {}).get("cancel_requested"):
                raise JobCancelled()

            while approval["action"] == "reject":
                feedback = approval.get("feedback", "")
                job_store.update(job_id, status="running")
                _emit(job_id, {"type": "stage_rejected", "stage": stage_name, "feedback": feedback})
                # Snapshot before regenerating — see _artifact_mtimes' docstring
                # for why file *presence* alone can't detect a no-op round.
                mtimes_before = _artifact_mtimes(project_dir, stage_def.get("produces") or [])
                # Re-run with feedback in a thread (never block the loop) and keep
                # accumulating cost. Same budget gate + produces hint as the
                # first run — previously this call dropped budget_cny/base_cost
                # entirely, letting a reject-regenerate loop bypass the
                # pre-call budget ceiling.
                resume_messages = None
                sample_iteration = 0
                while True:
                    try:
                        success = await asyncio.to_thread(
                            _run_agent_stage,
                            job_id, stage_name, skill_text, project_dir,
                            brand_info, options, feedback, cost_accumulator, cost_tracker,
                            budget_cny, base_cost,
                            stage_def.get("produces"),
                            resume_messages, sample_iteration,
                            max_turns=stage_def.get("max_turns", MAX_TURNS),
                            temperature=stage_def.get("temperature", 0.7),
                            required_artifacts_in=stage_def.get("required_artifacts_in"),
                        )
                        resume_messages = None
                        break
                    except BudgetGateNeeded as bgn:
                        _sync_cost(stage_name)
                        if not await _budget_gate(force=True, triggering_exc=bgn.budget_exc):
                            return
                        # Resume the SAME conversation at the raised ceiling —
                        # see BudgetGateNeeded's docstring.
                        resume_messages = bgn.messages + [{
                            "role": "user",
                            "content": f"Budget approved at new ceiling ¥{budget_cny} — retry the blocked call.",
                        }]
                        continue   # resume, doesn't consume a retry round
                    except BudgetExceededError:
                        # Defensive fallback — see the initial-run loop above
                        # for why this shouldn't normally trigger.
                        _sync_cost(stage_name)
                        if not await _budget_gate(force=True):
                            return
                        continue   # approved overspend → re-present the same approval round
                    except SamplePreviewNeeded as spn:
                        _sync_cost(stage_name)
                        resume_messages = await _sample_preview_gate(stage_name, spn)
                        sample_iteration = spn.sample_iteration + 1
                        continue   # resume the same conversation
                _sync_cost(stage_name)
                if not success:
                    job_store.update(job_id, status="failed")
                    # Same gap as the initial-run failure path above: reuse
                    # the last recorded error as an actionable diagnostic
                    # instead of an emit with no message field.
                    _emit(job_id, {
                        "type": "job_failed",
                        "stage": stage_name,
                        "message": (
                            _last_failure_message(job_id, stage_name)
                            or f"Stage '{stage_name}' failed after exhausting its retries."
                        ),
                    })
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
                    job_store.update(job_id, status="failed", current_stage=stage_name)
                    _emit(job_id, {
                        "type": "job_failed",
                        "stage": stage_name,
                        "message": (
                            f"Stage '{stage_name}' was rejected, but the regenerated run "
                            "finished without actually rewriting its required "
                            f"artifact(s) {still_missing or untouched} — the agent may have "
                            "stopped without acting on your feedback. Retry will re-run this stage."
                        ),
                    })
                    return
                _emit(job_id, {"type": "stage_completed", "stage": stage_name})
                job_store.update(job_id, status="awaiting_approval")
                _emit(job_id, {"type": "awaiting_approval", "stage": stage_name, "preview": _preview()})
                approval = await job_store.wait_for_approval(job_id, timeout=3600.0)
                if (job_store.get(job_id) or {}).get("cancel_requested"):
                    raise JobCancelled()

            job_store.update(job_id, status="running")
            _emit(job_id, {"type": "stage_approved", "stage": stage_name})

        # Mark done so a later retry resumes after this stage.
        completed_stages.add(stage_name)
        job_store.update(job_id, completed_stages=sorted(completed_stages))

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
        job_store.update(job_id, status="failed")
        _emit(job_id, {
            "type": "job_failed",
            "message": (
                "All stages reported complete but no render file was discovered "
                f"under {project_dir / 'renders'}, even though this pipeline "
                "declares a render-producing stage — refusing to mark the job "
                "completed without a real deliverable."
            ),
        })
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


# Tool names (registry `name`, from tools/tool_registry.py) capable of
# producing the FINAL composed video — the whole-film render, not a per-clip
# editing op. tool_bridge.py names every non-final-compose video_post output
# "{tool_name}{variant_tag}_{unique}.mp4" and writes it under assets/video_post/
# (only a call whose `operation` resolves to "compose" is treated as final and
# routed to renders/ instead — see tool_bridge.py's is_final_compose). A call
# using one of these SAME tool names but a different operation (e.g.
# operation="render"/"remotion_render", which still legitimately produces the
# whole film via Remotion/HyperFrames) also lands in assets/video_post/, so
# this is deliberately a whitelist of compose-capable tool names, not a check
# on the operation string itself.
_COMPOSE_FAMILY_TOOL_PREFIXES = ("video_compose_", "hyperframes_compose_")


def _discover_render_path(project_dir: Path) -> Path | None:
    """Find the final rendered video file on disk, or None if none exists.

    Extracted out of _discover_render_url so a caller that needs the actual
    Path (not just a servable URL) — e.g. cross-validating render_report's
    own claimed output path against reality — doesn't have to re-derive it.
    """
    def _newest(paths: list[Path]) -> Path | None:
        existing = [p for p in paths if p.is_file()]
        if not existing:
            return None
        return max(existing, key=lambda p: p.stat().st_mtime)

    candidate = _newest(list((project_dir / "renders").glob("*.mp4")))
    if candidate is None:
        # Fallback: a compose-family tool (video_compose/hyperframes_compose,
        # capability="video_post") wrote its output under assets/ instead of
        # renders/ — e.g. operation="render"/"remotion_render" is a legitimate
        # final render but isn't routed to renders/ by tool_bridge.py (only
        # operation="compose" is). Scoped to those two tool names specifically
        # — NOT every assets/video_post/*.mp4 — because trim/stitch/etc. calls
        # (video_trimmer, video_stitch, ...) write their INTERMEDIATE,
        # non-final clips to this same folder using the same naming scheme.
        # Without this scoping, a trim/stitch call that ran earlier in this
        # stage's conversation, followed by a final compose call that then
        # FAILED, would leave that intermediate clip sitting here as the
        # newest assets/video_post/*.mp4 — and the old unscoped glob picked
        # exactly that up and presented it as the finished render (the same
        # bug class already fixed once below for assets/video_generation/*.mp4
        # raw scene clips).
        candidate = _newest([
            p for p in project_dir.glob("assets/video_post/*.mp4")
            if p.name.startswith(_COMPOSE_FAMILY_TOOL_PREFIXES)
        ])
    if candidate is None:
        # Last resort: a misnamed compose output (.bin) that is really an mp4
        candidate = _newest(list(project_dir.glob("assets/video_post/*compose*output*")))

    return candidate


def _discover_render_url(project_dir: Path, project_name: str) -> str | None:
    """Find the final rendered video and return a browser-servable /media URL."""
    candidate = _discover_render_path(project_dir)
    if candidate is None:
        return None
    return _url_for_render(project_dir, project_name, candidate)


def _render_report_path_diverges(
    project_dir: Path, render_report: dict, discovered: Path | None
) -> str | None:
    """Return render_report's own claimed output path if it differs from the
    actually-discovered render file, else None.

    Confirmed live: even in a run that passed the render-file-existence
    check (a real mp4 existed), render_report claimed a DIFFERENT output
    filename than the one actually discovered. A wrong internal path claim
    while a real file DOES exist is lower-severity than no file at all
    (already hard-failed separately) — this only informs, it never fails
    the stage.
    """
    if discovered is None:
        return None
    outputs = (render_report or {}).get("outputs") or []
    if not outputs:
        return None
    claimed = outputs[0].get("path")
    if not claimed:
        return None
    try:
        claimed_resolved = (project_dir / claimed).resolve()
    except OSError:
        return claimed
    if claimed_resolved != discovered.resolve():
        return claimed
    return None


def _validate_publish_log_exports(project_dir: Path, publish_log: dict) -> list[str]:
    """Return the publish_log-claimed export_paths that have NO real file on
    disk, for every entry whose status implies a file was actually produced.

    Confirmed live: a publish_log artifact claimed 5 real export files
    (teaser cut, platform-specific crops, poster frame) that were never
    generated — no exports/ directory ever created, zero video-processing
    tool calls in that stage's trace. Per schemas/artifacts/publish_log.
    schema.json, "exported" and "draft" are the statuses that imply a real
    file was written (as opposed to "published"/a remote upload with no
    local file, "failed", or "pending_review").
    """
    missing: list[str] = []
    for entry in (publish_log or {}).get("entries", []):
        if not isinstance(entry, dict):
            continue
        status = entry.get("status")
        export_path = entry.get("export_path")
        if status in ("exported", "draft") and export_path:
            if not (project_dir / export_path).is_file():
                missing.append(export_path)
    return missing


# Stage-produces artifact name -> validator that checks its file-backed
# claims against reality. Generalizes the compose/render_report
# anti-fabrication check above to any stage whose `produces` declares one of
# these artifacts, rather than keying off a literal stage name — starting
# with the concrete publish_log case (see _validate_publish_log_exports).
_PRODUCES_EXPORT_VALIDATORS = {
    "publish_log": _validate_publish_log_exports,
}


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


def _missing_variants(project_dir: Path, options: dict) -> list[str] | None:
    """For a multi-variant compose job, return the declared A/B model strings
    that have NO corresponding rendered file — or None if this isn't a
    multi-variant job, or every declared variant rendered.

    The compose anti-fabrication check (in _run_pipeline_impl, right after
    _discover_render_url) only requires ANY render file to exist. In a
    3-variant job where 2 variants render and the 3rd fails, that check alone
    still passes (a render DID happen) and the stage proceeds as genuinely
    complete with no signal that a whole variant never rendered. Each
    variant is expected to land at renders/final_<variant_slug(model)>.mp4 per
    tool_bridge.py's per-call output-path tagging — the "A/B Variants" prompt
    section in _run_agent_stage instructs the agent to pass `inputs.variant`
    as the exact declared model string on every compose call.
    """
    variants = [m for m in (options.get("video_model_variants") or []) if m]
    if len(variants) <= 1:
        return None
    renders_dir = project_dir / "renders"
    missing = [m for m in variants if not (renders_dir / f"final_{variant_slug(m)}.mp4").is_file()]
    return missing or None


def _url_for_render(project_dir: Path, project_name: str, candidate: Path) -> str:
    rel = candidate.relative_to(project_dir).as_posix()
    # Route through the storage seam so swapping to object storage later yields
    # signed URLs without touching this call site.
    try:
        from app.interfaces import get_storage
    except ImportError:
        # The storage seam module itself isn't importable in this process —
        # genuinely "no real storage backend available" (e.g. a stripped
        # module path), not a bug in a configured backend.
        return f"/media/{project_name}/{rel}"
    try:
        return get_storage().url_for(project_name, rel)
    except Exception as exc:
        # A genuinely configured (non-local) storage backend raising here is a
        # real bug (bad credentials, unreachable bucket, ...) that silently
        # falling back to the local /media/ path would mask — the returned
        # URL would just 404 with no diagnostic anywhere. Log it so it's
        # visible, but still fall back so render discovery doesn't hard-fail
        # the whole job over a URL-formatting problem.
        logger.warning(
            "get_storage().url_for(%r, %r) raised %r; falling back to local media path",
            project_name, rel, exc,
        )
        return f"/media/{project_name}/{rel}"


def _discover_render_urls(project_dir: Path, project_name: str) -> dict[str, str] | None:
    """Variant-aware sibling of _discover_render_url.

    An A/B job's compose stage produces renders/final_<slug>.mp4 per variant
    (tool_bridge.py's `variant` output-path tagging) instead of a single
    renders/final.mp4. Returns {variant_slug: url} for every renders/final*.mp4
    found, or None for a normal (non-variant) job where only final.mp4 exists —
    callers should keep using the singular render_url/preview_render_url in
    that case, so a non-variant job's behavior is untouched.
    """
    renders = sorted((project_dir / "renders").glob("final*.mp4"))
    if len(renders) <= 1:
        return None  # 0 or 1 file: not a multi-variant job, nothing plural to report
    urls: dict[str, str] = {}
    for path in renders:
        stem = path.stem  # "final_ltx2-3" -> "ltx2-3"; bare "final" -> ""
        slug = stem[len("final"):].lstrip("_") or "default"
        urls[slug] = _url_for_render(project_dir, project_name, path)
    return urls
