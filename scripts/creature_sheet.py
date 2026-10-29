#!/usr/bin/env python3
"""scripts/creature_sheet.py - the consistency kit driver (P2).

  plan    build the canonical creature sheet job file (deterministic)
  submit  push the sheet job through the Kaggle bridge ONCE (no polling)
  status  one `kaggle kernels status` call (never a wait loop)
  fetch   download the output -> verify (fail-closed) -> label + image QC

The sheet job holds one creature in the front, side and three-quarter view.
The locked model (config/image_engine.json) generates the front view; the
other two views are generated from it as a reference image when the model's
official card documents reference-image editing, otherwise seed + prompt
anchoring is used.

Zero-cost: the Kaggle CLI reads KAGGLE_API_TOKEN from the environment; the
token is never printed. Media stays in /tmp (never committed).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.illustration.creature_sheet import (  # noqa: E402
    build_creature_sheet,
    build_sheet_job,
    load_creature_specs,
)
from tools.illustration.illustration_qc import qc_batch  # noqa: E402
from tools.illustration.model_registry import (  # noqa: E402
    EngineConfigError,
    active_adapter,
    adapter_for,
    load_engine,
)
from tools.illustration.style_kit import load_style  # noqa: E402

KERNEL_SLUG = "forts845/openmontage-runner"
RUN_PY = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
OUT_ROOT = Path("/tmp/kilo/sheet_out")
KAGGLE_CMD = "kaggle"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _write_json(path: Path, data: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _read_json(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"BLOCKED: job json not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _embed_job(run_text: str, job: Dict[str, Any]) -> str:
    marker = "JOB_EMBEDDED = None"
    if marker not in run_text:
        raise SystemExit("BLOCKED: JOB_EMBEDDED marker missing in kernel runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    return run_text.replace(marker, f"JOB_EMBEDDED = json.loads({literal})\n", 1)


def _adapter(model: str):
    engine = load_engine()
    if model:
        return adapter_for(engine, model)
    return active_adapter(engine)


# --------------------------------------------------------------------- plan
def cmd_plan(args: argparse.Namespace) -> int:
    try:
        style = load_style(args.niche)
    except EngineConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    adapter = _adapter(args.model)
    spec_dir = Path(args.spec_dir) if args.spec_dir else \
        REPO / "docs/openmontage/niches" / args.niche / "creatures"
    try:
        creatures = load_creature_specs(spec_dir)
    except (ValueError, RuntimeError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    if args.creature:
        creatures = [c for c in creatures if c["name"] == args.creature]
        if not creatures:
            print(f"BLOCKED: unknown creature {args.creature!r}")
            return 2

    jobs: List[Dict[str, Any]] = []
    for creature in creatures:
        renders = build_creature_sheet(creature, style, adapter)
        if args.limit:
            renders = renders[:args.limit]
        job = build_sheet_job(args.niche, creature, renders, adapter,
                              width=args.width, height=args.height)
        jobs.append(job)

    out_dir = Path(args.out_dir) if args.out_dir else \
        REPO / "projects" / "sheets" / args.niche
    written = []
    for job in jobs:
        path = out_dir / f"{job['job_id']}.json"
        _write_json(path, job)
        written.append(path)
        print(f"job_id={job['job_id']} renders={len(job['renders'])} "
              f"model={job['model']} views={[r['view'] for r in job['renders']]}")
        print(f"  seeds={[r['seed'] for r in job['renders']]} "
              f"reference={job['reference_policy']['workflow']}")
        print(f"  job_json={path}")
    print(f"jobs written: {len(written)}")
    return 0


# ------------------------------------------------------------------- submit
def cmd_submit(args: argparse.Namespace) -> int:
    from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool

    job = _read_json(args.job_json)
    if not job.get("renders"):
        print("BLOCKED: nothing to generate (the job has no renders)")
        return 2
    if args.limit:
        job = dict(job)
        job["renders"] = job["renders"][:args.limit]
        job["changed_from_previous"] += f"; smoke: first {args.limit} renders only"
    job_id = job["job_id"]
    work = REPO / "projects" / "sheets" / "work" / job_id
    work.mkdir(parents=True, exist_ok=True)
    run_text = _embed_job(RUN_PY.read_text(encoding="utf-8"), job)

    bridge = KaggleBridgeTool()
    bj = bridge.execute({
        "command": "build_job_folder", "job_folder": str(work),
        "job_id": job_id, "kernel_slug": KERNEL_SLUG, "job": job,
        "run_py": run_text, "enable_gpu": True, "enable_internet": True,
        "kaggle_cmd": KAGGLE_CMD,
    })
    if not bj.success:
        print(f"BUILD FAILED: {bj.error}")
        return 2
    _write_json(work / "job.json", job)
    print(f"job folder: {bj.data['job_folder']} ({len(job['renders'])} renders)")
    print(f"install ladder: {job['install_ladder']}")
    if args.no_push:
        print("DRY RUN: not pushed (--no-push)")
        return 0

    ps = bridge.execute({
        "command": "push", "job_folder": str(work), "kernel_slug": KERNEL_SLUG,
        "timeout": 6600, "accelerator": "gpu", "max_retries": 1,
        "kaggle_cmd": KAGGLE_CMD,
    })
    if not ps.success:
        print(f"PUSH FAILED: {ps.error}")
        return 2
    _write_json(work / "submitted.json", {
        "job_id": job_id, "model": job["model"],
        "num_renders": len(job["renders"]),
        "kernel_slug": KERNEL_SLUG,
        "install_ladder": job["install_ladder"],
        "reference_workflow": job.get("reference_policy", {}).get("workflow"),
        "submitted_utc": _now(),
    })
    print(f"SUBMITTED {job_id} ({len(job['renders'])} renders). "
          "No polling: call `status` once between phases.")
    return 0


# ------------------------------------------------------------------- status
def cmd_status(args: argparse.Namespace) -> int:
    """ONE status call. Never a wait loop (RUN_RULES)."""
    proc = subprocess.run([KAGGLE_CMD, "kernels", "status", KERNEL_SLUG],
                          capture_output=True, text=True, timeout=120)
    print((proc.stdout or proc.stderr or "").strip())
    return proc.returncode


# -------------------------------------------------------------------- fetch
def cmd_fetch(args: argparse.Namespace) -> int:
    job = _read_json(args.job_json)
    job_id = job["job_id"]
    out_dir = OUT_ROOT / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [KAGGLE_CMD, "kernels", "output", KERNEL_SLUG, "-p", str(out_dir), "-o"],
        capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        print(f"FETCH FAILED: {(proc.stderr or proc.stdout or '')[-400:]}")
        return 2

    from tools.illustration.episode_batch import label_and_qc, verify_fetched
    fetched = out_dir / job_id
    if not fetched.is_dir():
        fetched = out_dir
    res = verify_fetched(fetched, job)
    if not res.get("ok"):
        print(f"BLOCKED: fetch verification failed: {res.get('error')}")
        return 2
    speculative = bool(job.get("style", {}).get("speculative"))
    manifest = label_and_qc(fetched, job, out_dir / "labeled", speculative=speculative)
    print(f"verified {len(manifest['images'])} images "
          f"label={manifest.get('label')} qc={manifest.get('qc', {}).get('total')} "
          f"-> {out_dir / 'labeled'}")
    print(json.dumps(manifest.get("qc", {}), indent=1)[:800])
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="build the deterministic sheet job file")
    p.add_argument("--niche", default="speculative_evolution")
    p.add_argument("--creature", default="")
    p.add_argument("--model", default="", help="default: the locked model")
    p.add_argument("--spec-dir", default="")
    p.add_argument("--out-dir", default="")
    p.add_argument("--width", type=int, default=1024)
    p.add_argument("--height", type=int, default=1024)
    p.add_argument("--limit", type=int, default=0,
                   help="only the first N views (smoke job)")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("submit", help="push the sheet job through the bridge")
    p.add_argument("--job-json", required=True)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--no-push", action="store_true")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("status", help="ONE kernel status call")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("fetch", help="download + verify + label the output")
    p.add_argument("--job-json", required=True)
    p.set_defaults(func=cmd_fetch)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
