#!/usr/bin/env python3
"""S10-2: push the 54-render style test to Kaggle in ONE kernel run.

The model is not named here: it comes from `config/image_engine.json` through
`tools/illustration/model_registry.py` (the CONFIG lock). The kernel receives
one self-contained `run.py`: the S7 engine (generic install / probe / measure /
manifest machine) with the S10 job embedded.

Rules: fp16 only, no bitsandbytes, no CPU fallback (model CPU offload allowed
and recorded), released library versions from the config's install ladder,
90-minute in-job wall cap, one push (no polling loop).

The KAGGLE_API_TOKEN is used by the kaggle CLI only and is never printed.

Usage:
  python scripts/s10_push_style_test.py [--attempt N] [--change "what changed"]
                                        [--timeout SECONDS]
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

TEST_SET = REPO / "docs/openmontage/image_gen/S10_TEST_SET.json"
CONFIG = REPO / "config/image_engine.json"
KERNEL_SLUG = "forts845/openmontage-runner"
ENGINE_PY = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
JOBS_DIR = Path("/tmp/kilo/s10_jobs")

# Fields the kernel runner reads from each render (kept explicit so an extra
# field in the test set can never bloat the embedded job).
RENDER_FIELDS = ("render_id", "scene_id", "style", "seed", "prompt",
                 "negative_prompt", "steps", "guidance_scale")

# The runner records `variant` per image; for S10 it is the style key.
VARIANT_FIELD = "style"


def locked_adapter():
    """The active (LOCKED) model adapter from config/image_engine.json."""
    from tools.illustration.model_registry import active_adapter, load_engine
    adapter = active_adapter(load_engine(CONFIG))
    if adapter.dtype != "float16":
        raise SystemExit(f"BLOCKED: {adapter.key} dtype is {adapter.dtype!r}; "
                         "S10 is fp16 only")
    return adapter


def embed_job(run_text: str, job: Dict[str, Any]) -> str:
    """Embed the job as a JSON *string* parsed at runtime (S5/S7 lesson)."""
    marker = "JOB_EMBEDDED = None"
    if marker not in run_text:
        raise SystemExit("BLOCKED: JOB_EMBEDDED marker missing in the runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    return run_text.replace(marker, f"JOB_EMBEDDED = json.loads({literal})\n", 1)


def build_job(test_set: Dict[str, Any], adapter, attempt: int = 1,
              width: int = 1024, height: int = 1024,
              change: str = "") -> Dict[str, Any]:
    renders: List[Dict[str, Any]] = []
    for r in test_set["renders"]:
        render = {k: r[k] for k in RENDER_FIELDS if k in r}
        render["variant"] = r[VARIANT_FIELD]
        renders.append(render)
    if len(renders) != 54:
        raise SystemExit(f"BLOCKED: test set has {len(renders)} renders, "
                         "expected 54")
    # S10 runs RELEASED stacks only: the config ladder may carry a git-main
    # rung for unblocking a model; it is dropped here so the run is
    # reproducible from pinned versions alone.
    ladder = [rung for rung in adapter.install_ladder
              if not rung.lower().startswith("git")]
    if not ladder:
        raise SystemExit(f"BLOCKED: no released install rung for {adapter.key}")
    job: Dict[str, Any] = {
        "job_id": f"s10-style-test-{attempt}",
        "attempt": attempt,
        "model": adapter.key,
        "model_id": adapter.model_id,
        "output_dir": f"s10_bakeoff_{adapter.key}",
        "width": int(width),
        "height": int(height),
        "dtype": adapter.dtype,
        "bitsandbytes": False,
        "cpu_fallback": False,
        "install_ladder": ladder,
        "model_config": adapter.job_model_config(),
        "renders": renders,
        "max_wall_seconds": 5400,
        "changed_from_previous": change or (
            f"attempt {attempt}: 54 renders, ladder "
            f"{list(adapter.install_ladder)}"),
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "kind": "visual_style_test",
        "styles": list(test_set["styles"]),
    }
    return job


def build_runner(job: Dict[str, Any]) -> str:
    """One self-contained run.py: the engine with the job embedded."""
    engine = ENGINE_PY.read_text(encoding="utf-8")
    text = embed_job(engine, job)
    if text.count('if __name__ == "__main__":') != 1:
        raise SystemExit("BLOCKED: the composed runner must keep exactly one "
                         "__main__ guard")
    return text


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--attempt", type=int, default=1)
    ap.add_argument("--width", type=int, default=1024)
    ap.add_argument("--height", type=int, default=1024)
    ap.add_argument("--change", default="")
    ap.add_argument("--timeout", type=int, default=3600,
                    help="kaggle push -t (seconds to wait for completion)")
    args = ap.parse_args(argv)

    test_set = json.loads(TEST_SET.read_text(encoding="utf-8"))
    adapter = locked_adapter()
    job = build_job(test_set, adapter, args.attempt, args.width, args.height,
                    args.change)
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
        raise SystemExit(f"BUILD FAILED: {bj.error}")
    print(f"job folder   : {bj.data['job_folder']}")
    print(f"model        : {job['model']} ({job['model_id']})")
    print(f"renders      : {len(job['renders'])} ({job['width']}x{job['height']})")
    print(f"install ladder: {job['install_ladder']}")

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

    (work / "submitted.json").write_text(json.dumps({
        "job_id": job["job_id"],
        "model": job["model"],
        "kernel_slug": KERNEL_SLUG,
        "num_renders": len(job["renders"]),
        "install_ladder": job["install_ladder"],
        "push": ps.data.get("push"),
        "submitted_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }, indent=2), encoding="utf-8")
    print(f"SUBMITTED {job['job_id']} ({len(job['renders'])} renders)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
