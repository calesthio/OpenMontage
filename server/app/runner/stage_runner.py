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
LLM_MODEL = "anthropic/claude-sonnet-4.6"

llm = OpenAI(api_key=MAAS_KEY, base_url=f"{MAAS_BASE}/v1")

# ── Cinematic pipeline stage definitions ─────────────────────────────────────
CINEMATIC_STAGES = [
    {"name": "research",    "skill": "skills/pipelines/cinematic/research-director.md",   "approval": False, "produces": ["research_brief"], "required_artifacts_in": []},
    {"name": "proposal",    "skill": "skills/pipelines/cinematic/proposal-director.md",   "approval": True,  "produces": ["proposal_packet", "decision_log"], "required_artifacts_in": ["research_brief"]},
    {"name": "script",      "skill": "skills/pipelines/cinematic/script-director.md",     "approval": True,  "produces": ["script"], "required_artifacts_in": ["proposal_packet"]},
    {"name": "scene_plan",  "skill": "skills/pipelines/cinematic/scene-director.md",      "approval": False, "produces": ["scene_plan"], "required_artifacts_in": ["script"]},
    {"name": "assets",      "skill": "skills/pipelines/cinematic/asset-director.md",      "approval": False, "produces": ["asset_manifest"], "required_artifacts_in": ["scene_plan"]},
    {"name": "edit",        "skill": "skills/pipelines/cinematic/edit-director.md",       "approval": False, "produces": ["edit_decisions"], "required_artifacts_in": ["scene_plan", "asset_manifest"]},
    {"name": "compose",     "skill": "skills/pipelines/cinematic/compose-director.md",    "approval": False, "produces": ["render_report", "final_review"], "required_artifacts_in": ["edit_decisions", "asset_manifest"]},
    {"name": "publish",     "skill": "skills/pipelines/cinematic/publish-director.md",    "approval": False, "produces": ["publish_log"], "required_artifacts_in": ["render_report", "final_review"]},
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
) -> bool:
    """Run a single stage. Returns True on success, False on failure.

    May raise BudgetExceededError if a paid tool call would cross budget_cny —
    the caller catches it to drive the human budget gate.
    """

    artifacts = _load_artifacts(project_dir)
    artifacts_summary = json.dumps(
        {k: "(present)" for k in artifacts}, ensure_ascii=False
    )

    # Brand Kit injection — if a kit_id is in options, load and merge
    brand_kit = _load_brand_kit(options.get("brand_kit_id"))
    brand_section = ""
    if brand_kit:
        brand_section = f"""
## Brand Kit (use these to ensure visual/tonal consistency)
{json.dumps(brand_kit, ensure_ascii=False, indent=2)[:2000]}
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

    messages = [{"role": "user", "content": user_msg}]

    for turn in range(MAX_TURNS):
        try:
            response = llm.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOL_SCHEMAS,
                tool_choice="auto",
                max_tokens=8192,
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
            # No tools to run → the agent is done with this stage. Do NOT gate
            # on finish_reason: OpenAI-compatible gateways (aiapbot proxies
            # Anthropic/DashScope/etc.) may report finish_reason=="stop" even
            # when the message carries tool_calls; gating on "stop" would drop
            # those calls and mark the stage complete without running them.
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
                # Arguments were truncated — tell the model exactly what happened
                _emit(job_id, {
                    "type": "error",
                    "stage": stage_name,
                    "message": f"Tool {tool_name}: arguments JSON truncated ({len(raw_args)} chars). "
                               "Agent must retry with a shorter/simpler content.",
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": (
                        f"ERROR: Your function call arguments were truncated and could not be parsed "
                        f"({len(raw_args)} chars received, likely hit max_tokens). "
                        "Please retry write_artifact with a more concise 'content' object — "
                        "keep each field value under 500 characters, omit verbose descriptions."
                    ),
                })
                continue

            _emit(job_id, {
                "type": "tool_call",
                "stage": stage_name,
                "tool": tool_name,
                "summary": f"{tool_name}({list(tool_args.keys())})",
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
                )
            except BudgetExceededError:
                # Hard budget stop — unwind the stage so the runner's event loop
                # can pause for the human budget decision.
                raise
            except Exception as exc:
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


async def run_pipeline_job(job_id: str, data: dict) -> None:
    """Async entry point called by FastAPI BackgroundTasks.

    Wrapped in a last-resort guard so any unhandled error marks the job failed
    and surfaces via SSE, instead of leaving it silently stuck at 'running'.
    """
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
        # pre-call check is disabled once overridden).
        success = False
        feedback = ""
        _round = 0
        while _round <= MAX_ROUNDS:
            try:
                success = await asyncio.to_thread(
                    _run_agent_stage,
                    job_id, stage_name, skill_text, project_dir,
                    brand_info, options, feedback, cost_accumulator, cost_tracker,
                    (None if budget_overridden else budget_cny), base_cost,
                    stage_def.get("produces"),
                )
            except BudgetExceededError:
                _sync_cost(stage_name)
                if not await _budget_gate(force=True):
                    return
                continue   # approved overspend → re-run this stage, gate disabled
            _sync_cost(stage_name)
            if success:
                break
            _emit(job_id, {"type": "stage_retry", "stage": stage_name, "round": _round + 1})
            _round += 1

        if not success:
            job_store.update(job_id, status="failed", current_stage=stage_name)
            _emit(job_id, {"type": "job_failed", "stage": stage_name})
            return

        _emit(job_id, {"type": "stage_completed", "stage": stage_name})

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
                # Re-run with feedback in a thread (never block the loop) and keep
                # accumulating cost. Same budget gate + produces hint as the
                # first run — previously this call dropped budget_cny/base_cost
                # entirely, letting a reject-regenerate loop bypass the
                # pre-call budget ceiling.
                try:
                    success = await asyncio.to_thread(
                        _run_agent_stage,
                        job_id, stage_name, skill_text, project_dir,
                        brand_info, options, feedback, cost_accumulator, cost_tracker,
                        (None if budget_overridden else budget_cny), base_cost,
                        stage_def.get("produces"),
                    )
                except BudgetExceededError:
                    _sync_cost(stage_name)
                    if not await _budget_gate(force=True):
                        return
                    continue   # approved overspend → re-present the same approval round
                _sync_cost(stage_name)
                if not success:
                    job_store.update(job_id, status="failed")
                    _emit(job_id, {"type": "job_failed", "stage": stage_name})
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

    job_store.update(job_id, status="completed", render_url=render_url)
    _emit(job_id, {"type": "job_completed", "render_url": render_url})


def _discover_render_url(project_dir: Path, project_name: str) -> str | None:
    """Find the final rendered video and return a browser-servable /media URL."""
    def _newest(paths: list[Path]) -> Path | None:
        existing = [p for p in paths if p.is_file()]
        if not existing:
            return None
        return max(existing, key=lambda p: p.stat().st_mtime)

    candidate = _newest(list((project_dir / "renders").glob("*.mp4")))
    if candidate is None:
        # Fallback: any mp4 the compose stage may have written under assets/
        candidate = _newest(list(project_dir.glob("assets/**/*.mp4")))
    if candidate is None:
        # Last resort: a misnamed compose output (.bin) that is really an mp4
        candidate = _newest(list(project_dir.glob("assets/**/*compose*output*")))

    if candidate is None:
        return None
    rel = candidate.relative_to(project_dir).as_posix()
    # Route through the storage seam so swapping to object storage later yields
    # signed URLs without touching this call site.
    try:
        from app.interfaces import get_storage
        return get_storage().url_for(project_name, rel)
    except Exception:
        return f"/media/{project_name}/{rel}"
