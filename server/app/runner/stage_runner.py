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
from app.runner.tool_bridge import TOOL_SCHEMAS, execute_tool

# ── MaaS LLM client ───────────────────────────────────────────────────────────
MAAS_KEY  = os.environ.get("MAAS_API_KEY", "")
MAAS_BASE = os.environ.get("MAAS_API_BASE", "https://api.aiapbot.com")
LLM_MODEL = "anthropic/claude-sonnet-4.6"

llm = OpenAI(api_key=MAAS_KEY, base_url=f"{MAAS_BASE}/v1")

# ── Cinematic pipeline stage definitions ─────────────────────────────────────
CINEMATIC_STAGES = [
    {"name": "research",    "skill": "skills/pipelines/cinematic/research-director.md",   "approval": False},
    {"name": "proposal",    "skill": "skills/pipelines/cinematic/proposal-director.md",   "approval": True},
    {"name": "script",      "skill": "skills/pipelines/cinematic/script-director.md",     "approval": True},
    {"name": "scene_plan",  "skill": "skills/pipelines/cinematic/scene-director.md",      "approval": False},
    {"name": "assets",      "skill": "skills/pipelines/cinematic/asset-director.md",      "approval": False},
    {"name": "edit",        "skill": "skills/pipelines/cinematic/edit-director.md",       "approval": False},
    {"name": "compose",     "skill": "skills/pipelines/cinematic/compose-director.md",    "approval": False},
    {"name": "publish",     "skill": "skills/pipelines/cinematic/publish-director.md",    "approval": False},
]

PIPELINE_MAP = {
    "cinematic": CINEMATIC_STAGES,
    "marketing_film": CINEMATIC_STAGES,
}

MAX_TURNS  = 20
MAX_ROUNDS = 2   # reviewer sends back at most twice per stage


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
) -> bool:
    """Run a single stage. Returns True on success, False on failure."""

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

        if not msg.tool_calls or finish == "stop":
            # Agent finished this stage
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
                )
            except Exception as exc:
                result = f"ERROR: Tool execution failed: {exc}"
                _emit(job_id, {
                    "type": "error",
                    "stage": stage_name,
                    "message": f"Tool {tool_name} error: {exc}",
                })

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
    """Async entry point called by FastAPI BackgroundTasks."""

    pipeline_name = data.get("pipeline", "cinematic")
    stages = PIPELINE_MAP.get(pipeline_name, CINEMATIC_STAGES)
    brand_info = data.get("brand_info", {})
    options = data.get("options", {})
    project_name = data.get("project_name", job_id)

    project_dir = OM_ROOT / "projects" / project_name
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "artifacts").mkdir(exist_ok=True)
    (project_dir / "assets").mkdir(exist_ok=True)
    (project_dir / "renders").mkdir(exist_ok=True)

    # USD→CNY exchange rate (approximate, good enough for cost display)
    USD_TO_CNY = 7.25
    cost_accumulator: list[float] = []  # list of cost_usd floats from tool calls

    job_store.update(job_id, status="running", project_dir=str(project_dir))
    _emit(job_id, {"type": "job_started", "pipeline": pipeline_name, "stages": [s["name"] for s in stages]})

    for stage_def in stages:
        stage_name = stage_def["name"]
        skill_path = OM_ROOT / stage_def["skill"]
        needs_approval = stage_def["approval"]

        job_store.update(job_id, current_stage=stage_name, status="running")
        _emit(job_id, {"type": "stage_started", "stage": stage_name})

        # Load director skill
        skill_text = skill_path.read_text(encoding="utf-8") if skill_path.exists() else f"# {stage_name} director\nExecute the {stage_name} stage."

        # Run stage in thread pool (blocking sync LLM calls must not block event loop)
        success = False
        feedback = ""
        for _round in range(MAX_ROUNDS + 1):
            success = await asyncio.to_thread(
                _run_agent_stage,
                job_id, stage_name, skill_text, project_dir,
                brand_info, options, feedback, cost_accumulator,
            )
            # Update cost after each stage
            cost_cny = round(sum(cost_accumulator) * USD_TO_CNY, 4)
            job_store.update(job_id, cost_cny=cost_cny)
            _emit(job_id, {"type": "cost_updated", "cost_cny": cost_cny, "stage": stage_name})
            if success:
                break
            _emit(job_id, {"type": "stage_retry", "stage": stage_name, "round": _round + 1})

        if not success:
            job_store.update(job_id, status="failed", current_stage=stage_name)
            _emit(job_id, {"type": "job_failed", "stage": stage_name})
            return

        _emit(job_id, {"type": "stage_completed", "stage": stage_name})

        # Human approval gate
        if needs_approval:
            artifacts = _load_artifacts(project_dir)
            preview = artifacts.get(stage_name) or artifacts.get(
                {"proposal": "proposal_packet"}.get(stage_name, stage_name)
            )
            job_store.update(job_id, status="awaiting_approval")
            _emit(job_id, {
                "type": "awaiting_approval",
                "stage": stage_name,
                "preview": preview,
            })

            approval = await job_store.wait_for_approval(job_id, timeout=3600.0)
            if approval["action"] == "reject":
                feedback = approval.get("feedback", "")
                job_store.update(job_id, status="running")
                _emit(job_id, {"type": "stage_rejected", "stage": stage_name, "feedback": feedback})
                # Re-run the stage with feedback
                success = _run_agent_stage(
                    job_id, stage_name, skill_text, project_dir,
                    brand_info, options, feedback
                )
                if not success:
                    job_store.update(job_id, status="failed")
                    _emit(job_id, {"type": "job_failed", "stage": stage_name})
                    return
                _emit(job_id, {"type": "stage_completed", "stage": stage_name})
            else:
                job_store.update(job_id, status="running")
                _emit(job_id, {"type": "stage_approved", "stage": stage_name})

    # All stages complete
    renders = list((project_dir / "renders").glob("*.mp4"))
    render_url = f"/media/{project_name}/renders/{renders[0].name}" if renders else None

    job_store.update(job_id, status="completed", render_url=render_url)
    _emit(job_id, {"type": "job_completed", "render_url": render_url})
