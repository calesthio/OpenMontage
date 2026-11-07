#!/usr/bin/env python3
"""scripts/image_review.py - the owner-facing review tools for the episode images.

  queue    build the REVIEW queue (objective flags only) for an episode
  show     print one image's QC result (flags and evidence)
  approve  record an owner approval in the ledger (the image is never
           regenerated afterwards)
  reject   record an owner rejection (the image is re-generated with a new
           seed, up to 4 attempts, then the episode fails closed)

Anatomy, composition and beauty are NOT judged by the tools - the queue
carries objective flags only and the owner decides the rest.

  python scripts/image_review.py queue --episode se_pilot
  python scripts/image_review.py approve --episode se_pilot --render-id r0027
  python scripts/image_review.py reject  --episode se_pilot --render-id r0030 \
      --note "flat, no detail"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from tools.illustration.illustration_qc import qc_image  # noqa: E402
from tools.illustration.owner_review import (  # noqa: E402
    ledger_path,
    read_ledger,
    write_decision,
)
from tools.illustration.review_queue import build_review_queue  # noqa: E402
from tools.illustration.style_kit import load_style  # noqa: E402

DEFAULT_EPISODE = "se_pilot"
DEFAULT_NICHE = "speculative_evolution"


def _episode_root(episode: str) -> Path:
    return REPO / "projects" / episode


def _assets(episode: str) -> Path:
    return _episode_root(episode) / "assets" / "illustrations"


def _episode_images(episode: str) -> List[Path]:
    directory = _assets(episode)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.png") if p.is_file())


def _palette(niche: str) -> Dict[str, str]:
    try:
        return dict(load_style(niche).palette)
    except Exception:  # noqa: BLE001
        return {}


def cmd_queue(args: argparse.Namespace) -> int:
    files = _episode_images(args.episode)
    if not files:
        print(f"BLOCKED: no images in {_assets(args.episode)}")
        return 2
    queue = build_review_queue([str(f) for f in files], args.width, args.height,
                               _palette(args.niche),
                               out_dir=args.out_dir or _assets(args.episode),
                               episode=args.episode)
    print(f"images: {queue['total']} queued for review: {queue['queued']}")
    print(f"flags: {queue['flags']}")
    for item in queue["items"][:20]:
        print(f"  {item['rank']:3d} {item['name']:44s} "
              f"priority={item['priority']:3d} flags={'|'.join(item['flags'])}")
    print(f"queue: {Path(args.out_dir or _assets(args.episode)) / 'review_queue.csv'}")
    print("note: anatomy, composition and beauty stay owner-judged")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    path = Path(args.file)
    if not path.is_file():
        print(f"BLOCKED: no such image: {path}")
        return 2
    result = qc_image(path, args.width, args.height, _palette(args.niche))
    print(json.dumps(result, indent=2))
    return 0


def _decision(args: argparse.Namespace, decision: str) -> int:
    ledger = ledger_path(_episode_root(args.episode))
    sha = args.sha256 or ""
    prompt_sha = args.prompt_sha256 or ""
    if not sha:
        state = _assets(args.episode) / "run_state.json"
        if state.is_file():
            doc = json.loads(state.read_text(encoding="utf-8"))
            entry = (doc.get("renders") or {}).get(args.render_id) or {}
            sha = entry.get("sha256") or sha
            prompt_sha = entry.get("prompt_sha256") or prompt_sha
    row = write_decision(ledger, args.render_id, decision,
                         sha256=sha, prompt_sha256=prompt_sha,
                         reviewer=args.reviewer, note=args.note)
    print(f"{decision}: {row['render_id']} (ledger {ledger})")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    return _decision(args, "approved")


def cmd_reject(args: argparse.Namespace) -> int:
    return _decision(args, "rejected")


def cmd_ledger(args: argparse.Namespace) -> int:
    rows = read_ledger(ledger_path(_episode_root(args.episode)))
    if not rows:
        print("the ledger is empty")
        return 0
    for row in rows:
        print(f"{row['render_id']:10s} {row['decision']:9s} {row['reviewer']:8s} "
              f"{row['reviewed_utc']} {row['note']}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", default=DEFAULT_EPISODE)
    ap.add_argument("--niche", default=DEFAULT_NICHE)
    ap.add_argument("--width", type=int, default=1344)
    ap.add_argument("--height", type=int, default=768)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("queue", help="build the REVIEW queue")
    p.add_argument("--out-dir", default="")
    p.set_defaults(func=cmd_queue)

    p = sub.add_parser("show", help="QC one image")
    p.add_argument("--file", required=True)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("approve", help="owner approval (never regenerated)")
    p.add_argument("--render-id", required=True)
    p.add_argument("--reviewer", default="owner")
    p.add_argument("--note", default="")
    p.add_argument("--sha256", default="")
    p.add_argument("--prompt-sha256", default="")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject", help="owner rejection (re-queued)")
    p.add_argument("--render-id", required=True)
    p.add_argument("--reviewer", default="owner")
    p.add_argument("--note", default="")
    p.add_argument("--sha256", default="")
    p.add_argument("--prompt-sha256", default="")
    p.set_defaults(func=cmd_reject)

    p = sub.add_parser("ledger", help="print the owner ledger")
    p.set_defaults(func=cmd_ledger)

    args = ap.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
