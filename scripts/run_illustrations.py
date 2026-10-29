#!/usr/bin/env python3
"""Episode-scale AI illustration engine driver (G3).

One Kaggle job per episode+model, no polling loops:

  plan    specs -> per-model prompt plan (budget-checked, cache-aware)
  submit  embed the plan into the proven S7 kernel runner and push ONCE
  status  one `kaggle kernels status` call (never a wait loop)
  fetch   download output -> verify (fail-closed) -> label + image QC

Zero-cost: the Kaggle CLI reads KAGGLE_API_TOKEN from the environment; the
token is never printed. Media stays in /tmp (never committed).

Usage
  python scripts/run_illustrations.py plan --episode se_pilot \\
      --minutes 10.5 --per-spec 14
  python scripts/run_illustrations.py submit --job-json projects/se_pilot/jobs/ill-se_pilot-klein-1.json
  python scripts/run_illustrations.py status
  python scripts/run_illustrations.py fetch --job-json projects/se_pilot/jobs/ill-se_pilot-klein-1.json
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

from tools.illustration.episode_batch import (  # noqa: E402
    build_job,
    check_budget,
    estimate_wall_seconds,
    get_engine,
    images_for_minutes,
    label_and_qc,
    load_specs,
    plan_renders,
    resolve_adapter,
    split_cached,
    verify_fetched,
)
from tools.illustration.model_registry import EngineConfigError  # noqa: E402

KERNEL_SLUG = "forts845/openmontage-runner"
RUN_PY = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
SPEC_DIR = REPO / "docs/openmontage/niches/speculative_evolution/creatures"
OUT_ROOT = Path("/tmp/kilo/ill_out")
KAGGLE_CMD = "kaggle"
IMAGE_CAP = 120


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _episode_root(episode: str) -> Path:
    return REPO / "projects" / episode


def _write_json(path: Path, data: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _read_job(path: str | Path) -> Dict[str, Any]:
    p = Path(path)
    if not p.is_file():
        raise SystemExit(f"BLOCKED: job json not found: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _embed_job(run_text: str, job: Dict[str, Any]) -> str:
    """Embed the job as a JSON *string* (JSON null/true are not Python)."""
    marker = "JOB_EMBEDDED = None"
    if marker not in run_text:
        raise SystemExit("BLOCKED: JOB_EMBEDDED marker missing in kernel runner")
    literal = json.dumps(json.dumps(job, ensure_ascii=False))
    return run_text.replace(marker, f"JOB_EMBEDDED = json.loads({literal})\n", 1)


def _ladder_for(model: str, attempt: int) -> List[str]:
    """Attempt N skips rungs already tried (no identical retry)."""
    try:
        adapter = resolve_adapter(model)
        full = list(adapter.install_ladder)
    except ValueError:
        full = []
    return full[max(0, attempt - 1):] or full


def _model_choices() -> List[str]:
    try:
        return sorted(get_engine().models)
    except EngineConfigError:
        return []


def _locked_model() -> str:
    """The model the config locks (config/image_engine.json)."""
    try:
        return get_engine().model
    except EngineConfigError as exc:
        raise SystemExit(f"BLOCKED: {exc}")


# --------------------------------------------------------------------- plan
def cmd_plan(args: argparse.Namespace) -> int:
    ep = args.episode
    model = args.model or _locked_model()
    specs = load_specs(args.spec_dir or SPEC_DIR)
    count = (args.per_spec * len(specs)) if args.per_spec else images_for_minutes(
        args.minutes, args.per_minute)
    try:
        check_budget(count, args.cap)
    except Exception as exc:  # BudgetError
        print(f"BLOCKED: {exc}")
        return 2

    per_spec = args.per_spec or max(1, round(count / len(specs)))
    variants = [v.strip().upper() for v in args.variants.split(",") if v.strip()]
    renders = plan_renders(specs, model, per_spec=per_spec,
                           seed_base=args.seed_base, variants=variants)
    try:
        check_budget(len(renders), args.cap)
    except Exception as exc:  # BudgetError
        print(f"BLOCKED: {exc}")
        return 2

    cache = Path(args.cache) if args.cache else _episode_root(ep) / "assets" / "illustrations"
    todo, reused = split_cached(renders, cache)
    job = build_job(ep, model, todo, width=args.width, height=args.height,
                    ladder=_ladder_for(model, 1), attempt=1,
                    max_wall_seconds=args.max_wall)
    job["plan"] = {
        "spec_dir": str(Path(args.spec_dir or SPEC_DIR).resolve()),
        "specs": len(specs),
        "per_spec": per_spec,
        "variants": variants,
        "planned_total": len(renders),
        "reused": len(reused),
        "to_generate": len(todo),
        "est_wall_seconds": estimate_wall_seconds(model, len(todo)),
    }
    out = Path(args.job_json) if args.job_json else (
        _episode_root(ep) / "jobs" / f"{job['job_id']}.json")
    _write_json(out, job)

    print(f"episode={ep} model={model} specs={len(specs)} per_spec={per_spec}")
    print(f"planned={len(renders)} reused={len(reused)} to_generate={len(todo)} "
          f"cap={args.cap}")
    est = job["plan"]["est_wall_seconds"]
    print(f"est_wall={'unmeasured (BLOCKED for timing claims)' if est is None else f'{est:.0f}s'}")
    print(f"job_id={job['job_id']} ladder={job['install_ladder']}")
    print(f"job_json={out}")
    return 0


# ------------------------------------------------------------------- submit
def cmd_submit(args: argparse.Namespace) -> int:
    from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool

    prev = _read_job(args.job_json)
    if not prev.get("renders"):
        print("BLOCKED: nothing to generate (plan is empty; everything cached)")
        return 2
    attempt = args.attempt
    renders = list(prev["renders"])
    limit = int(getattr(args, "limit", 0) or 0)
    if limit:
        if limit > len(renders):
            print(f"BLOCKED: --limit {limit} exceeds the planned "
                  f"{len(renders)} renders")
            return 2
        renders = renders[:limit]
    ladder = (_ladder_for(prev["model"], attempt)
              if not getattr(args, "keep_ladder", False)
              else list(prev.get("install_ladder") or
                        resolve_adapter(prev["model"]).install_ladder))
    job = build_job(prev.get("episode_id", "ep"), prev["model"], renders,
                    width=prev.get("width", 1344), height=prev.get("height", 768),
                    ladder=ladder, attempt=attempt,
                    max_wall_seconds=prev.get("max_wall_seconds", 5400))
    if limit:
        job["changed_from_previous"] += (
            f"; smoke: first {limit}/{len(prev['renders'])} renders only")
    override_id = getattr(args, "job_id", "") or ""
    if override_id:
        job["job_id"] = override_id
    job["plan"] = prev.get("plan", {})

    work = _episode_root(prev.get("episode_id", "ep")) / "jobs" / job["job_id"]
    work.mkdir(parents=True, exist_ok=True)
    run_text = _embed_job(RUN_PY.read_text(encoding="utf-8"), job)

    bridge = KaggleBridgeTool()
    bj = bridge.execute({
        "command": "build_job_folder", "job_folder": str(work),
        "job_id": job["job_id"], "kernel_slug": KERNEL_SLUG, "job": job,
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
        "job_id": job["job_id"], "model": job["model"], "attempt": attempt,
        "kernel_slug": KERNEL_SLUG, "num_renders": len(job["renders"]),
        "install_ladder": job["install_ladder"],
        "changed_from_previous": job["changed_from_previous"],
        "job_json": str(Path(args.job_json)),
        "submitted_utc": _now(),
    })
    print(f"SUBMITTED {job['job_id']} ({len(job['renders'])} renders). "
          f"No polling: call `status` once between phases.")
    return 0


# ------------------------------------------------------------------- status
def cmd_status(args: argparse.Namespace) -> int:
    slug = args.kernel_slug
    try:
        res = subprocess.run([KAGGLE_CMD, "kernels", "status", slug],
                             capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"NOT_RUN: status call failed: {exc}")
        return 3
    raw = (res.stdout or res.stderr or "").strip()
    # Never print anything token-shaped.
    raw = re.sub(r"[0-9a-f]{32,}", "<redacted>", raw)
    m = re.search(r"KernelWorkerStatus\.([A-Za-z_]+)", raw)
    print(f"status={m.group(1) if m else (raw or 'UNKNOWN')}")
    print(f"exit={res.returncode}")
    return 0


# -------------------------------------------------------------------- fetch
def cmd_fetch(args: argparse.Namespace) -> int:
    from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool

    job = _read_job(args.job_json)
    ep = job.get("episode_id", "ep")
    dest = Path(args.dest) if args.dest else OUT_ROOT / job["job_id"]
    if dest.exists():
        import shutil
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    bridge = KaggleBridgeTool()
    fo = bridge.execute({"command": "fetch_output", "kernel_slug": KERNEL_SLUG,
                         "dest": str(dest), "file_pattern": "*",
                         "kaggle_cmd": KAGGLE_CMD})
    if not fo.success:
        print(f"FETCH FAILED: {fo.error}")
        return 3

    folder = dest / job["output_dir"]
    root = folder if folder.is_dir() else dest
    res = verify_fetched(root, job)
    _write_json(dest / "verification.json", {
        "ok": res["ok"], "error": res.get("error"), "verified_utc": _now(),
        "job_id": job["job_id"],
    })
    if not res["ok"]:
        print(f"REJECT: {res['error']}")
        return 2

    out = Path(args.out) if args.out else _episode_root(ep) / "assets" / "illustrations"
    manifest = label_and_qc(Path(res["manifest_path"]).parent, job, out,
                            speculative=args.speculative)
    qc = manifest["qc"]
    print(f"verified={len(manifest['images'])}/{len(job['renders'])} "
          f"qc_passed={qc['passed']} qc_failed={qc['failed']} "
          f"duplicates={len(qc['duplicates'])}")
    print(f"label={manifest['label']} rights_basis={manifest['rights_basis']}")
    print(f"out={out}")
    print(f"manifest={out / 'illustration_manifest.json'}")
    return 0 if qc["batch_ok"] else 1


# --------------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("plan", help="plan one model's episode batch")
    p.add_argument("--episode", required=True)
    p.add_argument("--model", default="", choices=_model_choices(),
                   help="model key from config/image_engine.json "
                        "(default: the locked model)")
    p.add_argument("--spec-dir", default="")
    p.add_argument("--minutes", type=float, default=10.5)
    p.add_argument("--per-minute", type=float, default=8.0)
    p.add_argument("--per-spec", type=int, default=0,
                   help="images per spec (overrides --minutes budget)")
    p.add_argument("--variants", default="A,B,C")
    p.add_argument("--seed-base", type=int, default=7000)
    p.add_argument("--width", type=int, default=1344)
    p.add_argument("--height", type=int, default=768)
    p.add_argument("--cap", type=int, default=IMAGE_CAP)
    p.add_argument("--max-wall", type=int, default=5400)
    p.add_argument("--cache", default="")
    p.add_argument("--job-json", default="")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("submit", help="push ONE Kaggle job (no polling)")
    p.add_argument("--job-json", required=True)
    p.add_argument("--attempt", type=int, default=1)
    p.add_argument("--limit", type=int, default=0,
                   help="submit only the first N planned renders (smoke retry)")
    p.add_argument("--job-id", default="",
                   help="override the derived job id (keeps failed folder intact)")
    p.add_argument("--keep-ladder", action="store_true",
                   help="start at the proven install rung instead of skipping it")
    p.add_argument("--no-push", action="store_true")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("status", help="one status call")
    p.add_argument("--kernel-slug", default=KERNEL_SLUG)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("fetch", help="fetch + verify + label + QC")
    p.add_argument("--job-json", required=True)
    p.add_argument("--dest", default="")
    p.add_argument("--out", default="")
    p.add_argument("--speculative", action="store_true", default=True)
    p.add_argument("--no-speculative", dest="speculative", action="store_false")
    p.set_defaults(func=cmd_fetch)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
