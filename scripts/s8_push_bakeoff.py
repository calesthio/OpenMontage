#!/usr/bin/env python3
"""S8-2b: push ONE of the three new S8 models to Kaggle (fp16, GPU, internet).

The kernel receives ONE self-contained run.py: the S7 engine (the generic
install/probe/measure/manifest machine) with the job embedded, followed by the
S8 additions (model registry + the SDXL-Lightning UNet swap + the vendor-card
scheduler overrides).

Persistence rule (S8): attempt N keeps only the install-ladder rungs that were
NOT tried before, so no attempt repeats an identical stack; the change is
recorded in the job payload and in the kernel manifest. The ladder holds
RELEASED versions only - no git main.

The KAGGLE_API_TOKEN is used by the kaggle CLI only and is never printed.

Usage:
  python scripts/s8_push_bakeoff.py {sdxl-lightning|dreamshaper-xl|sana-sprint-1.6b}
                               [--attempt N] [--change "what changed"]
                               [--load-config JSON] [--ladder r1,r2]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool  # noqa: E402

TEST_SET = REPO / "docs/openmontage/image_gen/S8_TEST_SET.json"
KERNEL_SLUG = "forts845/openmontage-runner"
ENGINE_PY = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
S8_ADDITIONS_PY = REPO / "tools/kaggle_bridge/s8_bakeoff_run.py"
JOBS_DIR = Path("/tmp/kilo/s8_jobs")

MODEL_ORDER = ["sdxl-lightning", "dreamshaper-xl", "sana-sprint-1.6b"]


def embed_job(run_text: str, job: Dict[str, Any]) -> str:
    """Embed the job as a JSON *string* parsed at runtime.

    json.dumps() alone writes JSON null/true/false, which are not Python
    literals -- that killed the first two S5 SDXL runs.
    """
    marker = "JOB_EMBEDDED = None"
    if marker not in run_text:
        raise SystemExit("JOB_EMBEDDED marker missing in runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    return run_text.replace(
        marker, f"JOB_EMBEDDED = json.loads({literal})\n", 1)


def strip_main_guard(run_text: str) -> str:
    """Remove the engine's `if __name__ == "__main__":` block.

    The S8 additions end with their own guard, so the engine's must go or
    main() would run before the S8 model registry is installed.
    """
    marker = 'if __name__ == "__main__":'
    idx = run_text.find(marker)
    if idx == -1:
        return run_text
    return run_text[:idx].rstrip() + "\n"


def build_runner(job: Dict[str, Any]) -> str:
    """One self-contained run.py: engine (job embedded) + S8 additions."""
    engine = strip_main_guard(ENGINE_PY.read_text(encoding="utf-8"))
    engine = embed_job(engine, job)
    additions = S8_ADDITIONS_PY.read_text(encoding="utf-8")
    return engine + "\n\n# --- S8 additions ---\n" + additions


def ladder_for(model: str, attempt: int) -> List[str]:
    """Attempt N skips the rungs already tried (no identical attempt)."""
    sys.path.insert(0, str(REPO))
    from tools.kaggle_bridge.s8_bakeoff_run import S8_LADDER
    full = list(S8_LADDER)
    return full[max(0, attempt - 1):] or full


def build_job(model: str, attempt: int, width: int, height: int,
              change: str, load_config: Optional[Dict[str, Any]] = None,
              ladder_override: Optional[List[str]] = None,
              steps: Optional[int] = None,
              guidance_scale: Optional[float] = None) -> Dict[str, Any]:
    ts = json.loads(TEST_SET.read_text(encoding="utf-8"))
    spec = ts["model_spec"][model]
    renders = [dict(r) for r in ts["renders"] if r["model"] == model]
    if not renders:
        raise SystemExit(f"no renders for model {model} in {TEST_SET.name}")
    if steps:
        for r in renders:
            r["steps"] = int(steps)
    if guidance_scale is not None:
        for r in renders:
            r["guidance_scale"] = float(guidance_scale)
    ladder = list(ladder_override) if ladder_override else ladder_for(model, attempt)
    job: Dict[str, Any] = {
        "job_id": f"s8-{model}-{attempt}",
        "attempt": attempt,
        "model": model,
        "model_id": spec["model_id"],
        "pipeline_class": spec["pipeline_class"],
        "revision": "main",
        "vae_model_id": spec.get("vae_model_id"),
        "unet_checkpoint": spec.get("unet_checkpoint"),
        "output_dir": f"s8_bakeoff_{model}",
        "width": width,
        "height": height,
        "install_ladder": ladder,
        "changed_from_previous": change or f"attempt {attempt}: ladder rungs {ladder}",
        "renders": renders,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "card": spec.get("card"),
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("model", choices=MODEL_ORDER)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--width", type=int, default=None)
    ap.add_argument("--height", type=int, default=None)
    ap.add_argument("--change", default="")
    ap.add_argument("--load-config", default="")
    ap.add_argument("--ladder", default="")
    ap.add_argument("--steps", type=int, default=None,
                    help="override the step count of every render (card range)")
    ap.add_argument("--guidance-scale", type=float, default=None,
                    help="override the guidance scale of every render")
    args = ap.parse_args()

    ts = json.loads(TEST_SET.read_text(encoding="utf-8"))
    width = args.width or ts["resolution"][0]
    height = args.height or ts["resolution"][1]
    load_config = parse_json_option(args.load_config, "--load-config")
    ladder_override = ([r.strip() for r in args.ladder.split(",") if r.strip()]
                       if args.ladder else None)
    if ladder_override:
        from tools.kaggle_bridge.s8_bakeoff_run import S8_LADDER
        unknown = [r for r in ladder_override if r not in S8_LADDER]
        if unknown:
            raise SystemExit(f"BLOCKED: unknown ladder rungs: {unknown} "
                             f"(S8 allows released stacks only: {S8_LADDER})")

    job = build_job(args.model, args.attempt, width, height, args.change,
                    load_config=load_config, ladder_override=ladder_override,
                    steps=args.steps, guidance_scale=args.guidance_scale)
    work = JOBS_DIR / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)

    run_text = build_runner(job)

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
        "timeout": 6600,
        "accelerator": "gpu",
        "max_retries": 1,
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
