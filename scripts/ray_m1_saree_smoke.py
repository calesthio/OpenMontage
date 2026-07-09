#!/usr/bin/env python3
"""Run the M1 hosted director smoke: saree job through scene_plan only."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from hosted_pipeline.director_client import ChatCompletionsDirectorClient
from hosted_pipeline.executor import BudgetCaps, StageExecutor, StageRunRequest, current_git_sha
from lib.checkpoint import init_project
from lib.paths import PROJECTS_DIR


DEFAULT_REFERENCES = [
    "https://cdn.ikawn.in/ikawn-v1/workspaces/24s-vertical-saree-ad-1783373712/uploads/1783373717-ikawn_shoot_20260706_235228.png",
    "https://cdn.ikawn.in/ikawn-v1/workspaces/24s-vertical-saree-ad-1783373712/uploads/1783373718-ikawn_shoot_20260706_235233.png",
    "https://cdn.ikawn.in/ikawn-v1/workspaces/24s-vertical-saree-ad-1783373712/uploads/1783373718-ikawn_shoot_20260706_235237.png",
    "https://cdn.ikawn.in/ikawn-v1/workspaces/24s-vertical-saree-ad-1783373712/uploads/1783373718-ikawn_shoot_20260706_235241.png",
]

DEFAULT_BRIEF = (
    "Create a 30 second 9:16 premium cinematic product ad for a Warli heritage saree. "
    "Use the attached reference stills as product truth: ivory ground, Warli/kantha motifs, "
    "ochre/maroon/charcoal borders, black elbow-sleeve blouse, oxidized silver jewelry, "
    "neutral studio grade. The output should feel like a commercial, not a stitched b-roll reel. "
    "Plan only through research, proposal, script, and scene_plan. Do not run paid media generation."
)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _seed_job_request(project_id: str, title: str, brief: str) -> None:
    project_dir = init_project(project_id, title=title, pipeline_type="cinematic", pipeline_dir=PROJECTS_DIR)
    references = [
        {"id": f"ref-{idx + 1}", "url": url, "kind": "image", "source": "m1_saree_smoke"}
        for idx, url in enumerate(DEFAULT_REFERENCES)
    ]
    _write_json(project_dir / "artifacts" / "job_request.json", {
        "version": "1.0",
        "project_id": project_id,
        "title": title,
        "prompt": brief,
        "aspect_ratio": "9:16",
        "duration_seconds": 30,
        "scene_count": 6,
        "reference_assets": references,
        "reference_asset_count": len(references),
        "created_at": int(time.time()),
        "created_by": "ray_m1_saree_smoke",
        "repo_sha": current_git_sha(),
    })


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=f"warli-heritage-saree-m1-{int(time.time())}")
    parser.add_argument("--title", default="Warli Heritage Saree M1")
    parser.add_argument("--brief", default=DEFAULT_BRIEF)
    parser.add_argument("--base-url", default="https://ikawn-ray.fly.dev")
    parser.add_argument("--no-preapprove", action="store_true")
    args = parser.parse_args()

    _seed_job_request(args.project_id, args.title, args.brief)
    executor = StageExecutor(model_client=ChatCompletionsDirectorClient.from_env())
    caps = BudgetCaps(
        total_budget_cap_usd=1.50,
        llm_budget_cap_usd=1.50,
        media_budget_cap_usd=0.0,
        sample_budget_cap_usd=0.0,
    )
    results = []
    for stage in ("research", "proposal", "script", "scene_plan"):
        result = executor.run_stage(StageRunRequest(
            project_id=args.project_id,
            title=args.title,
            pipeline_type="cinematic",
            stage=stage,
            brief=args.brief,
            budget_caps=caps,
            preapprove_human_gates=not args.no_preapprove,
            approval_note="M1 acceptance smoke preapproved by user: run saree job through scene_plan, no paid generation.",
        ))
        results.append({
            "stage": result.stage,
            "status": result.status,
            "blocker": result.blocker,
            "checkpoint_path": str(result.checkpoint_path) if result.checkpoint_path else None,
            "artifact_name": result.artifact_name,
        })
        if result.status == "blocked":
            print(json.dumps({
                "ok": False,
                "project_id": args.project_id,
                "board_url": f"{args.base_url.rstrip('/')}/p/{args.project_id}",
                "repo_sha": result.repo_sha,
                "results": results,
            }, indent=2))
            return 1

    print(json.dumps({
        "ok": True,
        "project_id": args.project_id,
        "board_url": f"{args.base_url.rstrip('/')}/p/{args.project_id}",
        "repo_sha": current_git_sha(),
        "results": results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
