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
from app.runner.tool_bridge import TOOL_SCHEMAS, execute_tool, BudgetExceededError

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

llm = OpenAI(api_key=MAAS_KEY, base_url=f"{MAAS_BASE}/v1")

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
    {"name": "scene_plan",  "skill": "skills/pipelines/cinematic/scene-director.md",      "approval": True,  "produces": ["scene_plan"], "required_artifacts_in": ["script"]},
    {"name": "assets",      "skill": "skills/pipelines/cinematic/asset-director.md",      "approval": True,  "produces": ["asset_manifest"], "required_artifacts_in": ["scene_plan"]},
    {"name": "edit",        "skill": "skills/pipelines/cinematic/edit-director.md",       "approval": False, "produces": ["edit_decisions"], "required_artifacts_in": ["scene_plan", "asset_manifest"]},
    {"name": "compose",     "skill": "skills/pipelines/cinematic/compose-director.md",    "approval": False, "produces": ["render_report", "final_review"], "required_artifacts_in": ["edit_decisions", "asset_manifest"]},
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
        pass
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
MAX_ROUNDS = 2   # reviewer sends back at most twice per stage
TOOL_RESULT_CHAR_CAP = 8000   # cap each tool result appended to history


def _emit(job_id: str, event: dict) -> None:
    job_store.push_event(job_id, {"ts": time.time(), **event})


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
) -> bool:
    """Run a single stage. Returns True on success, False on failure.

    resume_messages/sample_iteration resume a conversation that previously
    paused via SamplePreviewNeeded — when given, the stage's initial prompt
    is NOT rebuilt; the agent picks up exactly where it left off.

    May raise BudgetExceededError if a paid tool call would cross budget_cny —
    the caller catches it to drive the human budget gate.
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
{json.dumps(brand_kit, ensure_ascii=False, indent=2)[:2000]}
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
{json.dumps(artifacts, ensure_ascii=False, indent=2)[:6000]}

## User Feedback (if any)
{feedback or "None — proceed normally."}

{artifact_hint}

## Your job
Execute the {stage_name} stage now. Use `read_file` to load additional skills or schemas as needed.
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

    for turn in range(MAX_TURNS):
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
                temperature=0.7,
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
        for tc in msg.tool_calls:
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
            except BudgetExceededError:
                # Hard budget stop — unwind the stage so the runner's event loop
                # can pause for the human budget decision.
                raise
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
        "message": f"Stage {stage_name} reached max turns ({MAX_TURNS}) without completing",
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
    budget_overridden = False

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

    async def _budget_gate(force: bool = False) -> bool:
        """Pause for approval if over budget. Returns True to continue, False to abort.

        force=True pauses even when spent is still within budget — used when a
        pre-call check blocked the *next* paid call that would have crossed it.
        """
        nonlocal budget_overridden
        if not budget_cny or budget_overridden:
            return True
        spent = round(base_cost + sum(cost_accumulator), 4)
        if spent <= budget_cny and not force:
            return True
        job_store.update(job_id, status="awaiting_approval")
        _emit(job_id, {
            "type": "awaiting_approval",
            "stage": "budget",
            "gate": "budget",
            "preview": {"spent_cny": spent, "budget_cny": budget_cny,
                        "over_by_cny": round(spent - budget_cny, 4)},
        })
        _emit(job_id, {"type": "budget_exceeded", "spent_cny": spent, "budget_cny": budget_cny})
        approval = await job_store.wait_for_approval(job_id, timeout=3600.0)
        if approval["action"] == "reject":
            job_store.update(job_id, status="failed")
            _emit(job_id, {"type": "job_failed", "stage": "budget",
                           "message": f"Budget ¥{budget_cny} exceeded (spent ¥{spent}); aborted by user"})
            return False
        budget_overridden = True   # user approved overspend — don't re-prompt this run
        job_store.update(job_id, status="running")
        _emit(job_id, {"type": "stage_approved", "stage": "budget"})
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
        # pause for the human decision, and on approval re-run the stage (the
        # pre-call check is disabled once overridden). A mid-stage
        # SamplePreviewNeeded pauses the same way but resumes the SAME
        # conversation (resume_messages) rather than re-running from scratch —
        # it doesn't consume a retry round.
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
                    (None if budget_overridden else budget_cny), base_cost,
                    stage_def.get("produces"),
                    resume_messages, sample_iteration,
                )
                resume_messages = None
            except BudgetExceededError:
                _sync_cost(stage_name)
                if not await _budget_gate(force=True):
                    return
                continue   # approved overspend → re-run this stage, gate disabled
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

        if not success:
            job_store.update(job_id, status="failed", current_stage=stage_name)
            _emit(job_id, {"type": "job_failed", "stage": stage_name})
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
        if stage_name == "compose" and not _discover_render_url(project_dir, project_name):
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
                            (None if budget_overridden else budget_cny), base_cost,
                            stage_def.get("produces"),
                            resume_messages, sample_iteration,
                        )
                        resume_messages = None
                        break
                    except BudgetExceededError:
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
                    _emit(job_id, {"type": "job_failed", "stage": stage_name})
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

    update_kwargs: dict[str, Any] = {"status": "completed", "render_url": render_url}
    if render_urls:
        update_kwargs["render_urls"] = render_urls
    job_store.update(job_id, **update_kwargs)
    _emit(job_id, {
        "type": "job_completed",
        "render_url": render_url,
        **({"render_urls": render_urls} if render_urls else {}),
    })


def _discover_render_url(project_dir: Path, project_name: str) -> str | None:
    """Find the final rendered video and return a browser-servable /media URL."""
    def _newest(paths: list[Path]) -> Path | None:
        existing = [p for p in paths if p.is_file()]
        if not existing:
            return None
        return max(existing, key=lambda p: p.stat().st_mtime)

    candidate = _newest(list((project_dir / "renders").glob("*.mp4")))
    if candidate is None:
        # Fallback: a compose-family tool (video_compose/trimmer/stitch, all
        # capability="video_post") wrote its output under assets/ instead of
        # renders/. Scoped to video_post specifically — NOT assets/**/*.mp4 —
        # because that glob also matches assets/video_generation/*.mp4, the
        # RAW per-scene clips from maas_video. Confirmed live: a compose stage
        # that never actually composed anything (all generation blocked,
        # render_report honestly documented the failure) still left raw scene
        # clips sitting in assets/video_generation/ from an earlier stage —
        # the broad glob picked the newest one and presented a random 3s clip
        # as if it were the finished film.
        candidate = _newest(list(project_dir.glob("assets/video_post/*.mp4")))
    if candidate is None:
        # Last resort: a misnamed compose output (.bin) that is really an mp4
        candidate = _newest(list(project_dir.glob("assets/video_post/*compose*output*")))

    if candidate is None:
        return None
    return _url_for_render(project_dir, project_name, candidate)


def _url_for_render(project_dir: Path, project_name: str, candidate: Path) -> str:
    rel = candidate.relative_to(project_dir).as_posix()
    # Route through the storage seam so swapping to object storage later yields
    # signed URLs without touching this call site.
    try:
        from app.interfaces import get_storage
        return get_storage().url_for(project_name, rel)
    except Exception:
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
