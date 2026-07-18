"""System capabilities: live view of the active evolution-seam backends,
plus cost transparency (roadmap 3.1): decision-point estimates and the
usage rollup."""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from app.interfaces import active_backends
from app.runner.stage_runner import LLM_MODEL
from app.store import job_store

OM_ROOT = Path(__file__).parent.parent.parent.parent

router = APIRouter()

# The curated set of models the wizard offers for each generation capability.
# Single source of truth — the wizard (web/app/dashboard/new/page.tsx) and the
# settings page (web/app/dashboard/settings/page.tsx) used to each hardcode
# their own independent copy of this same list, which could silently drift
# (confirmed by the deep quality review). Both now fetch this from
# /system/capabilities instead. Kept as a small curated list rather than the
# MaaS gateway's full live catalog (133+ models) since the wizard
# deliberately only surfaces a handful of vetted options, not every model
# the gateway happens to support.
MODEL_CATALOG = {
    "video_models": ["leapfast/ltx-2.3", "leapfast/wan2.2", "volcengine/doubao-seedance-2.0"],
    "image_models": ["leapfast/flux2", "gemini-3.1-flash-image-preview"],
    "tts_models": ["qwen3-tts-flash", "leapfast/indextts"],
}


@router.get("/capabilities")
async def capabilities():
    """Which storage/queue/auth adapter is live, plus the planned roadmap.

    Backs the settings page so it reports real state instead of static text.
    `llm_model` reflects MAAS_LLM_MODEL if set, so the settings page can't
    drift out of sync with the model actually driving the pipeline the way
    a hardcoded display string would. `model_catalog` serves the same
    purpose for the wizard's video/image/TTS model pickers.
    """
    return {"backends": active_backends(), "llm_model": LLM_MODEL, "model_catalog": MODEL_CATALOG}


class EstimateRequest(BaseModel):
    pipeline: str = "cinematic"
    # Reference-driven path (wires CostTracker.estimate_from_reference —
    # 220 lines of quoting engine that previously had zero call sites):
    reference_brief: dict[str, Any] | None = None
    target_duration_seconds: int | None = None
    tool_plan: dict[str, Any] | None = None


@router.post("/estimate")
async def estimate_cost(req: EstimateRequest):
    """Decision-point cost estimate (roadmap 3.1) — shown BEFORE the user
    commits, not discovered after the money is spent.

    Two paths:
    - reference-driven: reference_brief + target_duration + tool_plan →
      CostTracker.estimate_from_reference's itemized quote (assumptions
      included — that's the confidence interval's basis).
    - history-driven (default): the empirical spread of this pipeline's
      completed jobs (min/median/max of cost_cny) — an honest range with
      its sample size attached, no model fiction.
    """
    if req.reference_brief is not None and req.target_duration_seconds:
        try:
            from tools.cost_tracker import CostTracker
            quote = CostTracker(cost_log_path=None).estimate_from_reference(
                req.reference_brief,
                req.target_duration_seconds,
                req.tool_plan or {},
            )
            return {"mode": "reference", "quote": quote}
        except Exception as exc:
            return {"mode": "reference", "error": str(exc)}

    costs = sorted(
        float(j.get("cost_cny", 0.0) or 0.0)
        for j in job_store.all().values()
        if j.get("pipeline") == req.pipeline and j.get("status") == "completed"
        and float(j.get("cost_cny", 0.0) or 0.0) > 0
    )
    if not costs:
        return {"mode": "history", "pipeline": req.pipeline, "sample_count": 0,
                "low_cny": None, "typical_cny": None, "high_cny": None}
    return {
        "mode": "history",
        "pipeline": req.pipeline,
        "sample_count": len(costs),
        "low_cny": round(costs[0], 2),
        "typical_cny": round(statistics.median(costs), 2),
        "high_cny": round(costs[-1], 2),
    }


@router.get("/usage")
async def usage():
    """Spend rollup (roadmap 3.1): by pipeline, by project, and by tool.

    Job-level totals come from the job store (cost_cny); per-tool detail
    from each project's cost_log.json (the CostTracker itemized ledger the
    runner already writes).
    """
    jobs = list(job_store.all().values())
    by_pipeline: dict[str, dict[str, Any]] = {}
    by_project: dict[str, dict[str, Any]] = {}
    total = 0.0
    for j in jobs:
        cost = float(j.get("cost_cny", 0.0) or 0.0)
        total += cost
        for key, bucket in ((j.get("pipeline", "?"), by_pipeline),
                            (j.get("project_name", "?"), by_project)):
            b = bucket.setdefault(key, {"jobs": 0, "cost_cny": 0.0})
            b["jobs"] += 1
            b["cost_cny"] = round(b["cost_cny"] + cost, 4)

    by_tool: dict[str, dict[str, Any]] = {}
    projects_dir = OM_ROOT / "projects"
    if projects_dir.is_dir():
        for log_path in projects_dir.glob("*/cost_log.json"):
            try:
                log = json.loads(log_path.read_text())
            except (OSError, json.JSONDecodeError):
                continue
            for entry in log.get("entries", []) or []:
                if not isinstance(entry, dict):
                    continue
                tool = entry.get("tool") or entry.get("tool_name") or "?"
                # Ledger values are CNY despite the field name — see
                # stage_runner's CostTracker setup comment.
                cost = float(entry.get("actual_usd") or entry.get("estimated_usd") or 0.0)
                b = by_tool.setdefault(tool, {"calls": 0, "cost_cny": 0.0})
                b["calls"] += 1
                b["cost_cny"] = round(b["cost_cny"] + cost, 4)

    return {
        "total_cny": round(total, 4),
        "by_pipeline": by_pipeline,
        "by_project": by_project,
        "by_tool": by_tool,
    }
