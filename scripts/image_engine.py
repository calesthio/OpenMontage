#!/usr/bin/env python3
"""scripts/image_engine.py - inspect and re-lock the image model (P1).

The image model lives in config/image_engine.json. This CLI shows what is
locked, projects the GPU cost and re-locks the model from the owner's blind
scores when they exist.

  python scripts/image_engine.py status
  python scripts/image_engine.py project --count 100
  python scripts/image_engine.py select            # read-only: print the decision
  python scripts/image_engine.py select --write    # write the decision into the config

`select` reads the owner's CSV in projects/s8_blind/results.csv (4 panels) or
projects/s7_blind/results.csv (2 panels). If a CSV is fully filled, the
owner's winner is locked with status OWNER_CONFIRMED. If no CSV is filled,
the agent advisory pick stays with status OWNER_GATED. A TIE is never
resolved by the agent: the config is left untouched.

No secrets, no network, no Kaggle call, no paid route.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.illustration.model_registry import (  # noqa: E402
    DEFAULT_CONFIG_PATH,
    EngineConfigError,
    ImageEngine,
    ModelAdapter,
    active_adapter,
    load_engine,
    owner_decision,
    project_gpu_minutes,
)


def _print_lock(engine: ImageEngine) -> None:
    adapter = active_adapter(engine)
    print(f"config      : {engine.path}")
    print(f"model       : {engine.model}  ({adapter.display_name})")
    print(f"status      : {engine.status}")
    print(f"scheduler   : {engine.scheduler}")
    print(f"steps       : {engine.steps}")
    print(f"guidance    : {engine.guidance}")
    print(f"dtype       : {engine.dtype}")
    print(f"prompt      : target={adapter.prompt_target} variant={engine.prompt_variant}")
    print(f"seed policy : {engine.seed_policy}")
    if engine.fallback:
        print(f"fallback    : {engine.fallback.get('model')} "
              f"({engine.fallback.get('role')}, {engine.fallback.get('status')})")
    if engine.selection:
        print(f"basis       : {engine.selection.get('basis')}")
        print(f"owner action: {engine.selection.get('next_owner_action')}")


def _print_models(engine: ImageEngine) -> None:
    print("")
    print("| model | status | s/image | img/min | peak VRAM MB | measured job |")
    print("|---|---|---|---|---|---|")
    for key, adapter in engine.models.items():
        print(f"| {key} | {adapter.status} | "
              f"{adapter.sec_per_image if adapter.usable else 'n/a (no usable images)'} | "
              f"{adapter.measured.get('usable_images_per_minute')} | "
              f"{adapter.measured.get('peak_vram_mb')} | "
              f"{adapter.measured.get('job_id')} |")


def cmd_status(args: argparse.Namespace) -> int:
    try:
        engine = load_engine(args.config)
    except EngineConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    _print_lock(engine)
    _print_models(engine)
    return 0


def cmd_project(args: argparse.Namespace) -> int:
    try:
        engine = load_engine(args.config)
    except EngineConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(f"projected GPU minutes for {args.count} images "
          f"(measured speed + one model load):")
    print("")
    print("| model | s/image | render min | load s | total min | peak VRAM MB |")
    print("|---|---|---|---|---|---|")
    for key, adapter in engine.models.items():
        try:
            proj = project_gpu_minutes(adapter, args.count)
        except EngineConfigError as exc:
            print(f"| {key} | BLOCKED | - | - | - | - |  ({exc})")
            continue
        print(f"| {key} | {proj['sec_per_image']} | {proj['render_minutes']} | "
              f"{proj['load_seconds']} | {proj['total_minutes']} | "
              f"{proj['peak_vram_mb']} |")
    return 0


def _write_lock(engine: ImageEngine, model: str, status: str,
                basis: str) -> None:
    path = Path(engine.path)
    doc: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    adapter = engine.models[model]
    doc["model"] = model
    doc["status"] = status
    doc["scheduler"] = dict(adapter.scheduler)
    doc["steps"] = adapter.steps
    doc["guidance"] = adapter.guidance
    doc["dtype"] = adapter.dtype
    doc["prompt_variant"] = adapter.prompt_variant
    doc["updated_utc"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  __import__("time").gmtime())
    selection = doc.setdefault("selection", {})
    selection["decision"] = model
    selection["basis"] = basis
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"written: {path} (model={model}, status={status})")


def cmd_select(args: argparse.Namespace) -> int:
    try:
        engine = load_engine(args.config)
    except EngineConfigError as exc:
        print(f"BLOCKED: {exc}")
        return 2

    decision = owner_decision(repo_root=getattr(args, "repo_root", REPO),
                              config_path=args.config)
    print(f"status  : {decision['status']}")
    print(f"model   : {decision['model']}")
    print(f"basis   : {decision['basis']}")
    if decision.get("pack"):
        print(f"pack    : projects/{decision['pack']}/results.csv")
    result = decision.get("owner_result")
    if result and result.get("stats"):
        print("")
        print("| model | wins | 2nd places | losses | anatomy ok |")
        print("|---|---|---|---|---|")
        for model, stats in result["stats"].items():
            print(f"| {model} | {stats['wins']} | {stats.get('seconds', 0)} | "
                  f"{stats['losses']} | {stats['anatomy_ok']}/{stats['anatomy_out_of']} |")

    if decision["status"] != "OWNER_CONFIRMED":
        if decision.get("owner_result") and decision["owner_result"].get("tie"):
            print("")
            print("TIE - the agent does not resolve it. The config is left as it is.")
        else:
            print("")
            print("The owner's blind CSV is not filled: the advisory pick stays "
                  f"({decision['model']}), status OWNER_GATED.")
        return 0

    if decision["model"] not in engine.models:
        print(f"BLOCKED: the owner's winner {decision['model']!r} is not a "
              "registered model entry in the config")
        return 2
    if args.write:
        _write_lock(engine, decision["model"], decision["status"], decision["basis"])
    else:
        print("")
        print("dry run: re-run with --write to lock this model in the config")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    ap.add_argument("--repo-root", default=str(REPO),
                    help="where the owner's blind packs live "
                         "(default: the repository root)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("status", help="print the locked model and the registry")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("project", help="project the GPU minutes per model")
    p.add_argument("--count", type=int, default=100)
    p.set_defaults(func=cmd_project)

    p = sub.add_parser("select", help="lock the model from the owner's scores")
    p.add_argument("--write", action="store_true",
                   help="write the decision into the config")
    p.set_defaults(func=cmd_select)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
