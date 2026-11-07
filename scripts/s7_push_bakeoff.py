#!/usr/bin/env python3
"""S7-2: push ONE model's bake-off job to Kaggle (fp16, GPU, internet on).

Reads the fixed test set (docs/openmontage/image_gen/S7_TEST_SET.json), keeps
only this model's renders, and embeds them into
tools/kaggle_bridge/s7_bakeoff_run.py. The KAGGLE_API_TOKEN is used by the
kaggle CLI only and is never printed.

Attempts (S7 persistence rule): attempt N keeps only the install-ladder rungs
that were NOT tried before, so no attempt repeats an identical stack. The
change is recorded in the job payload and in the kernel manifest.

Usage: python scripts/s7_push_bakeoff.py {sdxl|klein|zimage} [--attempt N]
                                                  [--width W] [--height H]
                                                  [--change "what changed"]
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

TEST_SET = REPO / "docs/openmontage/image_gen/S7_TEST_SET.json"
KERNEL_SLUG = "forts845/openmontage-runner"
RUN_PY = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
JOBS_DIR = Path("/tmp/kilo/s7_jobs")

MODEL_CONFIG = {
    "sdxl": {
        "model_id": "stabilityai/stable-diffusion-xl-base-1.0",
        "pipeline_class": "StableDiffusionXLPipeline",
        "vae_model_id": "madebyollin/sdxl-vae-fp16-fix",
    },
    "klein": {
        "model_id": "black-forest-labs/FLUX.2-klein-4B",
        # vendor card class for this repo (HF page is tagged Flux2KleinPipeline)
        "pipeline_class": "Flux2KleinPipeline",
        "vae_model_id": None,
    },
    "zimage": {
        "model_id": "Tongyi-MAI/Z-Image-Turbo",
        "pipeline_class": "ZImagePipeline",
        "vae_model_id": None,
    },
}


def embed_job(run_text: str, job: Dict[str, Any]) -> str:
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


def ladder_for(model: str, attempt: int) -> List[str]:
    """Attempt N skips the rungs already tried (no identical attempt)."""
    sys.path.insert(0, str(REPO))
    from tools.kaggle_bridge.s7_bakeoff_run import DEFAULT_LADDERS
    full = list(DEFAULT_LADDERS[model])
    return full[max(0, attempt - 1):] or full


def build_job(model: str, attempt: int, width: int, height: int,
              change: str, load_config: Optional[Dict[str, Any]] = None,
              ladder_override: Optional[List[str]] = None) -> Dict[str, Any]:
    cfg = MODEL_CONFIG[model]
    ts = json.loads(TEST_SET.read_text(encoding="utf-8"))
    renders = [r for r in ts["renders"] if r["model"] == model]
    if not renders:
        raise SystemExit(f"no renders for model {model} in {TEST_SET.name}")
    ladder = list(ladder_override) if ladder_override else ladder_for(model, attempt)
    job: Dict[str, Any] = {
        "job_id": f"s7-{model}-{attempt}",
        "attempt": attempt,
        "model": model,
        "model_id": cfg["model_id"],
        "pipeline_class": cfg["pipeline_class"],
        "revision": "main",
        "vae_model_id": cfg["vae_model_id"],
        "width": width,
        "height": height,
        "install_ladder": ladder,
        "changed_from_previous": change or f"attempt {attempt}: install ladder rungs {ladder}",
        "renders": renders,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if load_config:
        job["load_config"] = load_config
    return job


def parse_json_option(raw: Optional[str], what: str) -> Optional[Any]:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"BLOCKED: {what} is not valid JSON: {exc}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", choices=list(MODEL_CONFIG))
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--change", default="")
    ap.add_argument("--load-config", default="",
                    help='JSON merged over the runner LOAD_CONFIG, e.g. '
                         '\'{"offload": true, "low_cpu_mem_usage": true}\'')
    ap.add_argument("--ladder", default="",
                    help="comma-separated install-ladder rungs (overrides the "
                         "default per-attempt ladder)")
    args = ap.parse_args()

    ts = json.loads(TEST_SET.read_text(encoding="utf-8"))
    width = args.width or ts["resolution"][0]
    height = args.height or ts["resolution"][1]
    load_config = parse_json_option(args.load_config, "--load-config")
    ladder_override = ([r.strip() for r in args.ladder.split(",") if r.strip()]
                       if args.ladder else None)
    if ladder_override:
        from tools.kaggle_bridge.s7_bakeoff_run import RELEASED_STACKS
        unknown = [r for r in ladder_override if r not in RELEASED_STACKS]
        if unknown:
            raise SystemExit(f"BLOCKED: unknown ladder rungs: {unknown}")

    job = build_job(args.model, args.attempt, width, height, args.change,
                    load_config=load_config, ladder_override=ladder_override)
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
    print(f"job folder: {bj.data['job_folder']} ({len(job['renders'])} renders)")
    print(f"install ladder: {job['install_ladder']}")
    print(f"change: {job['changed_from_previous']}")

    ps = bridge.execute({
        "command": "push",
        "job_folder": str(work),
        "kernel_slug": KERNEL_SLUG,
        "timeout": 6600,          # kernel cap above the in-job 90 min model cap
        "accelerator": "gpu",
        "max_retries": 1,         # never double-submit the same job
        "kaggle_cmd": "kaggle",
    })
    if not ps.success:
        raise SystemExit(f"PUSH FAILED ({args.model}): {ps.error}")

    (work / "submitted.json").write_text(json.dumps({
        "job_id": job["job_id"], "model": args.model, "attempt": args.attempt,
        "kernel_slug": KERNEL_SLUG, "num_renders": len(job["renders"]),
        "install_ladder": job["install_ladder"],
        "changed_from_previous": job["changed_from_previous"],
        "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2), encoding="utf-8")
    print(f"SUBMITTED {job['job_id']} ({len(job['renders'])} renders)")


if __name__ == "__main__":
    main()
