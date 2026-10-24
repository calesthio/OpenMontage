#!/usr/bin/env python3
"""S5-2: push ONE model's bake-off job to Kaggle (fp16, GPU, internet on).

Reads the fixed test set (docs/openmontage/image_gen/S5_TEST_SET.json), keeps
only this model's renders, and embeds them into tools/kaggle_bridge/s5_bakeoff_run.py.
The KAGGLE_API_TOKEN is used by the kaggle CLI only and is never printed.

Usage: python scripts/s5_push_bakeoff.py {sdxl|klein|zimage}
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

TEST_SET = REPO / "docs/openmontage/image_gen/S5_TEST_SET.json"
# S5 runs on its OWN kernel so a parallel session cannot overwrite its output
# (S5's klein job was overwritten on the shared runner slug on 2026-10-21).
KERNEL_SLUG = "forts845/openmontage-s5-runner"
RUN_PY = REPO / "tools/kaggle_bridge/s5_bakeoff_run.py"
JOBS_DIR = Path("/tmp/kilo/s5_jobs")

MODEL_CONFIG = {
    "sdxl": {
        "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "pipeline_class": "StableDiffusionXLPipeline",
        "vae_model_id": "madebyollin/sdxl-vae-fp16-fix",
    },
    "klein": {
        "model_id": "black-forest-labs/FLUX.2-klein-4B",
        "pipeline_class": "Flux2Pipeline",
        "vae_model_id": None,
    },
    "zimage": {
        "model_id": "Tongyi-MAI/Z-Image-Turbo",
        "pipeline_class": "ZImagePipeline",
        "vae_model_id": None,
    },
}


def embed_job(run_text: str, job: dict) -> str:
    """Embed the job as a JSON *string* parsed at runtime.

    json.dumps() alone writes JSON null/true/false, which are not Python
    literals -- that killed the first two S5 SDXL runs with
    `NameError: name 'null' is not defined`.
    """
    marker = "JOB_EMBEDDED = None"
    if marker not in run_text:
        raise SystemExit("JOB_EMBEDDED marker missing in runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    return run_text.replace(
        marker, f"JOB_EMBEDDED = json.loads({literal})\n", 1)


def build_job(model: str) -> dict:
    cfg = MODEL_CONFIG[model]
    ts = json.loads(TEST_SET.read_text(encoding="utf-8"))
    renders = [r for r in ts["renders"] if r["model"] == model]
    if not renders:
        raise SystemExit(f"no renders for model {model} in {TEST_SET.name}")
    return {
        "job_id": f"s5-{model}-1",
        "model": model,
        "model_id": cfg["model_id"],
        "pipeline_class": cfg["pipeline_class"],
        "revision": "main",
        "vae_model_id": cfg["vae_model_id"],
        "width": ts["resolution"][0],
        "height": ts["resolution"][1],
        "renders": renders,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", choices=list(MODEL_CONFIG))
    args = ap.parse_args()

    job = build_job(args.model)
    work = JOBS_DIR / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)

    run_text = embed_job(RUN_PY.read_text(encoding="utf-8"), job)

    bridge = KaggleBridgeTool()
    bj = bridge.execute({
        "command": "build_job_folder",
        "job_folder": str(work),
        "job_id": job["job_id"],
        "kernel_slug": KERNEL_SLUG,
        "job": job,
        "run_py": run_text,
        "enable_gpu": True,
        "enable_internet": True,
        "kaggle_cmd": "kaggle",
    })
    if not bj.success:
        raise SystemExit(f"BUILD FAILED ({args.model}): {bj.error}")
    # Kaggle requires a unique kernel title per account; the shared runner
    # already owns "OpenMontage runner" (409 Conflict otherwise).
    meta_path = work / "kernel-metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["title"] = "OpenMontage S5 runner"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"job folder: {bj.data['job_folder']} ({len(job['renders'])} renders)")

    ps = bridge.execute({
        "command": "push",
        "job_folder": str(work),
        "kernel_slug": KERNEL_SLUG,
        "timeout": 5400,
        "accelerator": "gpu",
        "kaggle_cmd": "kaggle",
    })
    if not ps.success:
        raise SystemExit(f"PUSH FAILED ({args.model}): {ps.error}")

    (work / "submitted.json").write_text(json.dumps({
        "job_id": job["job_id"], "model": args.model, "kernel_slug": KERNEL_SLUG,
        "num_renders": len(job["renders"]),
        "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2), encoding="utf-8")
    print(f"SUBMITTED {job['job_id']} ({len(job['renders'])} renders)")


if __name__ == "__main__":
    main()
