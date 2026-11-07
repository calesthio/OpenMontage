#!/usr/bin/env python3
"""S4 push: pre-render prompts via tools/prompting.builder (OpenCode-owned, read
only) and push one model's bakeoff job to Kaggle.

Reads KAGGLE_API_TOKEN via the kaggle CLI only; never prints/logs/commits it.
Builds the job folder under /tmp/kilo (not committed), pushes to
forts845/openmontage-runner (enable_gpu + enable_internet), records SUBMITTED in
docs/openmontage/S4_STATE.md.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402
from tools.prompting.builder import (  # noqa: E402 - OpenCode-owned, read only
    CreatureSpec,
    PromptBuilder,
)

REPO = Path(__file__).resolve().parent.parent
MATRIX_PATH = REPO / "docs" / "openmontage" / "image_gen" / "prompt_test_matrix.json"
KERNEL_SLUG = "forts845/openmontage-runner"
RUN_PY = REPO / "tools" / "kaggle_bridge" / "s4_bakeoff_run.py"

MODEL_CONFIG = {
    "zimage": {
        "model_id": "Tongyi-MAI/Z-Image-Turbo",
        "pipeline_class": "ZImagePipeline",
        "revision": "main",
        "vae_model_id": None,
        "target": "zimage",
    },
    "sdxl": {
        "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "pipeline_class": "StableDiffusionXLPipeline",
        "revision": "main",
        "vae_model_id": "madebyollin/sdxl-vae-fp16-fix",
        "target": "sdxl",
    },
    "klein": {
        "model_id": "black-forest-labs/FLUX.2-klein-4B",
        "pipeline_class": "FluxPipeline",
        "revision": "main",
        "vae_model_id": None,
        "target": "klein",
    },
}


def _embed_job(run_text: str, job: dict) -> str:
    marker = "JOB_EMBEDDED = None"
    injection = f"JOB_EMBEDDED = {json.dumps(job)}\n"
    if marker not in run_text:
        raise RuntimeError("JOB_EMBEDDED marker missing in runner")
    return run_text.replace(marker, injection, 1)


def build_model_job(model: str) -> dict:
    cfg = MODEL_CONFIG[model]
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    jobs = [j for j in matrix["jobs"] if j["model"] == model]

    builder = PromptBuilder()
    render_jobs = []
    for j in jobs:
        spec = CreatureSpec.from_mapping(j["spec"])
        rendered = builder.build(
            target=cfg["target"],
            variant=j["variant"],
            spec=spec,
            negation_style=False,
        )
        render_jobs.append({
            "render_id": j["render_id"],
            "scene_id": j["scene_id"],
            "variant": j["variant"],
            "seed": j["seed"],
            "prompt": rendered["prompt"],
            "negative_prompt": rendered["negative_prompt"],
            "guidance_scale": rendered["guidance_scale"],
            "steps": rendered["steps"],
        })

    return {
        "job_id": f"s4-{model}-1",
        "model": model,
        "model_id": cfg["model_id"],
        "pipeline_class": cfg["pipeline_class"],
        "revision": cfg["revision"],
        "vae_model_id": cfg["vae_model_id"],
        "width": matrix.get("resolution", [1280, 720])[0],
        "height": matrix.get("resolution", [1280, 720])[1],
        "images": render_jobs,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", choices=list(MODEL_CONFIG.keys()))
    args = ap.parse_args()

    model = args.model
    job = build_model_job(model)
    work = Path("/tmp/kilo/s4_jobs") / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)

    bridge = KaggleBridgeTool()

    bj = bridge.execute({
        "command": "build_job_folder",
        "job_folder": str(work),
        "job_id": job["job_id"],
        "kernel_slug": KERNEL_SLUG,
        "job": job,
        "run_py": _embed_job(RUN_PY.read_text(encoding="utf-8"), job),
        "enable_gpu": True,
        "enable_internet": True,
        "kaggle_cmd": "kaggle",
    })
    if not bj.success:
        print(f"BUILD FAILED ({model}): {bj.error}"); sys.exit(1)
    print(f"job folder built: {bj.data['job_folder']} ({len(job['images'])} images)")

    ps = bridge.execute({
        "command": "push",
        "job_folder": str(work),
        "kernel_slug": KERNEL_SLUG,
        "timeout": 3600,
        "accelerator": "gpu",
        "kaggle_cmd": "kaggle",
    })
    if not ps.success:
        print(f"PUSH FAILED ({model}): {ps.error}"); sys.exit(1)
    print(f"PUSH OK ({model}): {ps.data['push']}")

    (work / "submitted.json").write_text(
        json.dumps({"job_id": job["job_id"], "model": model,
                    "kernel_slug": KERNEL_SLUG,
                    "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "num_images": len(job["images"])}, indent=2),
        encoding="utf-8")
    print(f"SUBMITTED job_id={job['job_id']} model={model} images={len(job['images'])}")


if __name__ == "__main__":
    main()
