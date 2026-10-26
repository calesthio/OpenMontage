#!/usr/bin/env python3
"""S14: push ONE smoke-test model to a fresh Kaggle kernel.

One model per kernel, never several dependency stacks in one kernel.
Order: MiniT2I B/16, MiniT2I L/16, Tongyi-MAI/Z-Image (Base).
512x512, 3 seeds (101, 202, 303), single simple prompt.
Checkpoint's own default scheduler/steps.

Usage:
  python scripts/s14_push_smoke.py --model minit2i-b-16
  python scripts/s14_push_smoke.py --model minit2i-l-16
  python scripts/s14_push_smoke.py --model zimage-base
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

KERNEL_SLUG = "forts845/of-bridge-runner"
JOBS_DIR = Path("/tmp/kilo/s14_jobs")
WIDTH = 512
HEIGHT = 512
SEEDS = [101, 202, 303]
PROMPT = ("flat vector illustration of an alien deep-sea creature, exactly six "
          "separate tendrils, two pairs of fins, plain light background, "
          "empty lower fifth, no text")

MODELS: Dict[str, Dict[str, Any]] = {
    "minit2i-b-16": {
        "model": "minit2i-b-16",
        "model_id": "MiniT2I/MiniT2I-B-16",
        "license_id": "MiniT2I/MiniT2I-B-16",
        "pipeline_candidates": ["FluxPipeline", "AutoPipelineForText2Image",
                                "Flux2Pipeline", "FluxPipeline"],
        "note": "MIT; PyTorch/diffusers repo not found publicly -> expect HARDWARE FAIL",
    },
    "minit2i-l-16": {
        "model": "minit2i-l-16",
        "model_id": "MiniT2I/MiniT2I-L-16",
        "license_id": "MiniT2I/MiniT2I-L-16",
        "pipeline_candidates": ["FluxPipeline", "AutoPipelineForText2Image",
                                "Flux2Pipeline", "FluxPipeline"],
        "note": "MIT; PyTorch/diffusers repo not found publicly -> expect HARDWARE FAIL",
    },
    "zimage-base": {
        "model": "zimage-base",
        "model_id": "Tongyi-MAI/Z-Image",
        "license_id": "Tongyi-MAI/Z-Image",
        "pipeline_candidates": ["ZImagePipeline"],
        "steps": 50,
        "guidance_scale": None,
        "note": "Apache-2.0; ZImagePipeline in diffusers 0.37.0",
    },
}

RENDER_PROMPT = PROMPT


def build_job(model_key: str, attempt: int = 1) -> Dict[str, Any]:
    if model_key not in MODELS:
        raise SystemExit(f"BLOCKED: unknown model {model_key!r}; "
                         f"registered: {sorted(MODELS)}")
    m = MODELS[model_key]
    job: Dict[str, Any] = {
        "job_id": f"s14-{model_key}-{attempt}",
        "attempt": attempt,
        "model": m["model"],
        "model_id": m["model_id"],
        "license_id": m["license_id"],
        "output_dir": f"s14_smoke_{m['model']}",
        "prompt": RENDER_PROMPT,
        "width": WIDTH,
        "height": HEIGHT,
        "seeds": list(SEEDS),
        "pipeline_candidates": list(m["pipeline_candidates"]),
        "steps": m.get("steps"),
        "guidance_scale": m.get("guidance_scale"),
        "max_wall_seconds": MAX_WALL_SECONDS,
        "changed_from_previous": f"attempt {attempt}: S14 smoke test {model_key}",
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "smoke_test_s14",
        "note": m["note"],
    }
    return job


MAX_WALL_SECONDS = 3600


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=sorted(MODELS))
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--timeout", type=int, default=3600)
    args = ap.parse_args(argv)

    job = build_job(args.model, args.attempt)
    work = JOBS_DIR / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)

    engine_py = REPO / "tools/kaggle_bridge/s14_smoke_run.py"
    engine_text = engine_py.read_text(encoding="utf-8")
    marker = "JOB_EMBEDDED = None"
    if marker not in engine_text:
        raise SystemExit("BLOCKED: JOB_EMBEDDED marker missing in the runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    run_text = engine_text.replace(marker,
                                   f"JOB_EMBEDDED = json.loads({literal})\n", 1)
    if run_text.count('if __name__ == "__main__":') != 1:
        raise SystemExit("BLOCKED: the composed runner must keep exactly one "
                         "__main__ guard")
    (work / "run.py").write_text(run_text, encoding="utf-8")

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
        raise SystemExit(f"BUILD FAILED: {bj.error}")

    ps = bridge.execute({
        "command": "push",
        "job_folder": str(work),
        "kernel_slug": KERNEL_SLUG,
        "timeout": int(args.timeout),
        "accelerator": "gpu",
        "max_retries": 1,
        "kaggle_cmd": "kaggle",
    })
    if not ps.success:
        raise SystemExit(f"PUSH FAILED: {ps.error}")

    submitted = {
        "job_id": job["job_id"],
        "model": job["model"],
        "model_id": job["model_id"],
        "kernel_slug": KERNEL_SLUG,
        "num_seeds": len(job["seeds"]),
        "width": job["width"],
        "height": job["height"],
        "push": ps.data.get("push"),
        "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": job["note"],
    }
    (work / "submitted.json").write_text(
        json.dumps(submitted, indent=2), encoding="utf-8")
    print(json.dumps(submitted, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
