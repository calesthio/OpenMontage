"""Simulate a pipeline run on disk to exercise the Backlot live board.

Drives a fake production through the REAL contract — init_project,
in_progress checkpoints, gated awaiting_human states, tool events,
progressively-written artifacts — so the board can be watched updating live.
Also useful as a demo driver.

    python scripts/backlot_simulate_run.py [--project backlot-demo-run]
        [--fast] [--cleanup]

--fast     compresses waits to ~0.3s (for automated verification)
--cleanup  removes the project directory at the end
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.checkpoint import PROJECTS_DIR, init_project, write_checkpoint
from lib.events import emit_event

SCENES = [
    ("sc1", "Opening — a lighthouse at dusk", 0, 4, "The coast holds its breath."),
    ("sc2", "The beam sweeps the water", 4, 9, "Every night, the same promise."),
    ("sc3", "A storm builds offshore", 9, 15, "Until the night the light went out."),
    ("sc4", "The keeper climbs the stairs", 15, 21, "Someone still has to climb."),
]


def artifacts_for(project_id: str) -> dict:
    script = {
        "version": "1.0",
        "title": "The Last Lighthouse",
        "total_duration_seconds": 21,
        "sections": [
            {"id": f"s{i+1}", "label": desc.split("—")[0].strip(), "text": narration,
             "start_seconds": s0, "end_seconds": s1}
            for i, (sid, desc, s0, s1, narration) in enumerate(SCENES)
        ],
    }
    scene_plan = {
        "version": "1.0",
        "scenes": [
            {"id": sid, "type": "generated", "description": desc,
             "start_seconds": s0, "end_seconds": s1,
             "script_section_id": f"s{i+1}",
             "hero_moment": sid == "sc3",
             "required_assets": [{"type": "image", "description": desc, "source": "generate"}]}
            for i, (sid, desc, s0, s1, _n) in enumerate(SCENES)
        ],
    }
    return {"script": script, "scene_plan": scene_plan}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default="backlot-demo-run")
    parser.add_argument("--fast", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    wait = 0.3 if args.fast else 2.5
    pid = args.project
    pdir = PROJECTS_DIR / pid
    if pdir.exists():
        shutil.rmtree(pdir)

    print(f"[sim] init_project {pid}")
    init_project(pid, title="The Last Lighthouse", pipeline_type="cinematic",
                 style_playbook="clean-professional")
    art = artifacts_for(pid)

    def save_artifact(name: str, data: dict) -> None:
        path = pdir / "artifacts" / f"{name}.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def cp(stage: str, status: str, artifacts: dict, **kw) -> None:
        write_checkpoint(PROJECTS_DIR, pid, stage, status, artifacts,
                         pipeline_type="cinematic", **kw)
        print(f"[sim] checkpoint {stage} -> {status}")
        time.sleep(wait)

    # research auto-proceeds (schema-valid fixture from the contract tests)
    cp("research", "in_progress", {})
    from tests.contracts.test_phase0_contracts import sample_artifact
    brief = sample_artifact("research_brief")
    brief["topic"] = "The Last Lighthouse"
    cp("research", "completed", {"research_brief": brief})

    # script gates: awaiting_human -> approved
    cp("script", "in_progress", {})
    save_artifact("script", art["script"])
    cp("script", "awaiting_human", {"script": art["script"]},
       review={"round": 1, "decision": "pass", "critical": 0, "suggestions": 1,
               "nitpicks": 0, "summary": "Hook is strong; tightened s3."})
    time.sleep(wait)  # "user reads the script on the board"
    cp("script", "completed", {"script": art["script"]}, human_approved=True)

    # scene_plan gates too
    cp("scene_plan", "in_progress", {})
    save_artifact("scene_plan", art["scene_plan"])
    cp("scene_plan", "awaiting_human", {"scene_plan": art["scene_plan"]})
    time.sleep(wait)
    cp("scene_plan", "completed", {"scene_plan": art["scene_plan"]}, human_approved=True)

    # assets: per-scene tool events + growing manifest + partial progress
    cp("assets", "in_progress", {})
    manifest = {"version": "1.0", "assets": [], "total_cost_usd": 0.0}
    done_ids = []
    from PIL import Image, ImageDraw
    palette = [(24, 32, 48), (40, 30, 60), (60, 24, 24), (20, 48, 40)]
    for i, (sid, desc, _s0, _s1, _n) in enumerate(SCENES):
        emit_event(pdir, {"tool": "flux_image", "event": "start", "scene_id": sid})
        print(f"[sim] generating {sid}…")
        time.sleep(wait * 1.5)
        rel = f"assets/images/{sid}.png"
        img = Image.new("RGB", (640, 360), palette[i % 4])
        draw = ImageDraw.Draw(img)
        draw.text((20, 160), f"{sid} — {desc[:40]}", fill=(230, 225, 210))
        img.save(pdir / rel)
        emit_event(pdir, {"tool": "flux_image", "event": "finish", "scene_id": sid,
                          "success": True, "cost_usd": 0.05, "duration_s": wait * 1.5,
                          "output_path": rel})
        manifest["assets"].append({
            "id": f"img_{sid}", "type": "image", "path": rel, "scene_id": sid,
            "source_tool": "flux_image", "model": "flux-sim", "cost_usd": 0.05,
            "prompt": desc, "quality_score": 0.88,
        })
        manifest["total_cost_usd"] = round(manifest["total_cost_usd"] + 0.05, 2)
        save_artifact("asset_manifest", manifest)
        done_ids.append(sid)
        write_checkpoint(PROJECTS_DIR, pid, "assets", "in_progress", {},
                         pipeline_type="cinematic",
                         metadata={"partial_progress": {"completed_scene_ids": done_ids}},
                         cost_snapshot={"total_spent_usd": manifest["total_cost_usd"],
                                        "total_reserved_usd": 0.0,
                                        "budget_remaining_usd": 5 - manifest["total_cost_usd"]})
    # assets gate (the storyboard review)
    cp("assets", "awaiting_human", {"asset_manifest": manifest},
       cost_snapshot={"total_spent_usd": manifest["total_cost_usd"],
                      "total_reserved_usd": 0.0,
                      "budget_remaining_usd": 5 - manifest["total_cost_usd"]})
    time.sleep(wait)
    cp("assets", "completed", {"asset_manifest": manifest}, human_approved=True)

    print(f"[sim] done — board at http://127.0.0.1:4750/p/{pid}")
    if args.cleanup:
        shutil.rmtree(pdir)
        print("[sim] cleaned up")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
