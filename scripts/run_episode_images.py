#!/usr/bin/env python3
"""scripts/run_episode_images.py - the episode-scale image driver (P3).

  brief    derive the image brief from the script + claim ledger
  plan     budget, batches, seeds, state (resumable)
  submit   push ONE batch (one Kaggle kernel), no polling
  status   ONE kernel status call
  fetch    download the batch output -> verify (sha256) -> QC -> state
  finalize hard fail when images < prompts, write the manifest
  approve  mark an image as owner-approved (never regenerated again)

Zero-cost: the Kaggle CLI reads KAGGLE_API_TOKEN from the environment; the
token is never printed. Media stays in the gitignored episode assets or /tmp.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.illustration.episode_run import (  # noqa: E402
    BATCH_SIZE_DEFAULT,
    EpisodeImages,
    FakeBridge,
    RunError,
)
from tools.illustration.image_brief import ImageBriefError  # noqa: E402
from tools.illustration.model_registry import (  # noqa: E402
    EngineConfigError,
    active_adapter,
    adapter_for,
    load_engine,
)
from tools.illustration.style_kit import load_style  # noqa: E402

DEFAULT_EPISODE = "se_pilot"
DEFAULT_NICHE = "speculative_evolution"


def _episode_root(episode: str) -> Path:
    return REPO / "projects" / episode


def _style_and_adapter(niche: str, model: str):
    style = load_style(niche)
    engine = load_engine()
    adapter = adapter_for(engine, model) if model else active_adapter(engine)
    return style, adapter


def _write_json(path: Path, data: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _run(args: argparse.Namespace, bridge=None) -> EpisodeImages:
    style, adapter = _style_and_adapter(args.niche, args.model)
    episode = Path(args.episode_root) if args.episode_root else \
        _episode_root(args.episode)
    return EpisodeImages(
        episode, adapter, style, bridge=bridge,
        images_per_minute=args.images_per_minute,
        narration_minutes=args.minutes,
        script_path=args.script or (episode / "script.md"),
        ledger_path=args.ledger or (episode / "claim_ledger.md"),
        spec_dir=args.spec_dir or (REPO / "docs/openmontage/niches" /
                                   args.niche / "creatures"),
    )


# --------------------------------------------------------------------- brief
def cmd_brief(args: argparse.Namespace) -> int:
    try:
        run = _run(args)
        brief = run.build_brief(max_images=args.max_images or None,
                                required_beats=tuple(args.beat or ()))
    except (ImageBriefError, EngineConfigError, RunError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    out = Path(args.out) if args.out else \
        run.asset_dir / "image_brief.json"
    _write_json(out, brief)
    print(f"brief: {len(brief['entries'])} visual beats, "
          f"{len(brief['skipped'])} skipped")
    print(f"tags: {brief['tags']}")
    for entry in brief["entries"][:5]:
        print(f"  {entry['render_id']} {entry['beat_id']} {entry['tag']:12s} "
              f"{entry['subject']:24s} {entry['view']:14s} seed={entry['seed']}")
    if len(brief["entries"]) > 5:
        print(f"  ... {len(brief['entries']) - 5} more")
    print(f"brief_json={out}")
    return 0


# ---------------------------------------------------------------------- plan
def cmd_plan(args: argparse.Namespace) -> int:
    try:
        run = _run(args)
        brief = run.build_brief(max_images=args.max_images or None,
                                required_beats=tuple(args.beat or ()))
        plan = run.plan(brief, batch_size=args.batch_size,
                        max_images=args.max_images or None,
                        select=tuple(args.select or ()))
    except (ImageBriefError, EngineConfigError, RunError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"budget: {plan['budget']}")
    print(f"renders: {len(plan['renders'])} "
          f"(truncated={plan['truncated']}, dropped={len(plan['dropped_beats'])})")
    for batch in plan["batches"]:
        print(f"  batch {batch['batch_id']}: {len(batch['render_ids'])} prompts")
    print(f"pending: {len(run.pending())}")
    print(f"seed_log={run.seed_log_path}")
    print(f"state={run.state_path}")
    return 0


# -------------------------------------------------------------------- submit
def cmd_submit(args: argparse.Namespace) -> int:
    from tools.illustration.kaggle_episode_bridge import KaggleEpisodeBridge

    try:
        run = _run(args, bridge=KaggleEpisodeBridge())
        state = run.load_state()
        batches = state.get("batches") or {}
        if not batches:
            print("BLOCKED: no batch planned (run `plan` first)")
            return 2
        planned = [batches[k] for k in sorted(batches, key=int)
                   if batches[k].get("status") == "planned"]
        if not planned:
            print("BLOCKED: no batch is waiting for a submission")
            return 2
        batch = planned[0]
        result = run.submit(batch)
    except (EngineConfigError, RunError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"SUBMITTED {result['job_id']} ({result['renders']} renders). "
          "No polling: call `status` once between phases.")
    return 0


# --------------------------------------------------------------------- status
def cmd_status(args: argparse.Namespace) -> int:
    from tools.illustration.kaggle_episode_bridge import KaggleEpisodeBridge
    print(f"status={KaggleEpisodeBridge().status()}")
    return 0


# ---------------------------------------------------------------------- fetch
def cmd_fetch(args: argparse.Namespace) -> int:
    from tools.illustration.kaggle_episode_bridge import KaggleEpisodeBridge

    try:
        run = _run(args, bridge=KaggleEpisodeBridge())
        state = run.load_state()
        batches = state.get("batches") or {}
        submitted = [batches[k] for k in sorted(batches, key=int)
                     if batches[k].get("status") in {"submitted", "fetched"}]
        if not submitted:
            print("BLOCKED: no batch was submitted")
            return 2
        batch = submitted[-1]
        result = run.fetch(batch, qc=not args.no_qc)
    except (EngineConfigError, RunError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"batch {batch['batch_id']}: verified={len(result['verified'])} "
          f"failed={len(result['failed'])}")
    if result["failed"]:
        print(f"failed: {result['failed']}")
        print(f"errors: {result['errors']}")
    print(f"kernel: {json.dumps(result['manifest'])}")
    return 0 if not result["failed"] else 1


# ------------------------------------------------------------------- finalize
def cmd_finalize(args: argparse.Namespace) -> int:
    try:
        run = _run(args)
        manifest = run.finalize()
    except (EngineConfigError, RunError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"images: {len(manifest['images'])} "
          f"model={manifest['model']} tags={manifest['tags']}")
    print(f"manifest={run.manifest_path}")
    return 0


# -------------------------------------------------------------------- approve
def cmd_approve(args: argparse.Namespace) -> int:
    try:
        run = _run(args)
        record = run.approve(args.render_id, approved_by=args.approved_by)
    except (EngineConfigError, RunError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"approved {record['render_id']} (sha256={record['sha256']})")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", default=DEFAULT_EPISODE)
    ap.add_argument("--episode-root", default="")
    ap.add_argument("--niche", default=DEFAULT_NICHE)
    ap.add_argument("--model", default="", help="default: the locked model")
    ap.add_argument("--script", default="")
    ap.add_argument("--ledger", default="")
    ap.add_argument("--spec-dir", default="")
    ap.add_argument("--images-per-minute", type=int, default=7)
    ap.add_argument("--minutes", type=float, default=None,
                    help="narration minutes (default: from the narration manifest)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("brief", help="derive the image brief")
    p.add_argument("--max-images", type=int, default=0)
    p.add_argument("--beat", action="append", help="require this beat id")
    p.add_argument("--out", default="")
    p.set_defaults(func=cmd_brief)

    p = sub.add_parser("plan", help="budget + batches + seeds")
    p.add_argument("--max-images", type=int, default=0)
    p.add_argument("--beat", action="append")
    p.add_argument("--batch-size", type=int, default=BATCH_SIZE_DEFAULT)
    p.add_argument("--select", action="append",
                   help="keep only this render id (repeatable)")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("submit", help="push ONE batch (one kernel)")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("status", help="ONE kernel status call")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("fetch", help="download + verify + QC one batch")
    p.add_argument("--no-qc", action="store_true")
    p.set_defaults(func=cmd_fetch)

    p = sub.add_parser("finalize", help="hard fail if images < prompts")
    p.set_defaults(func=cmd_finalize)

    p = sub.add_parser("approve", help="owner-approve an image")
    p.add_argument("--render-id", required=True)
    p.add_argument("--approved-by", default="owner")
    p.set_defaults(func=cmd_approve)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
