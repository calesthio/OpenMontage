"""Capture Backlot board screenshots whenever watched project state changes.

This is the Half-B dogfood watcher from internal/evals/BACKLOT_EVAL_PLAN.md.
It polls the Backlot API, fingerprints board-relevant state, and captures the
library plus the changed project board through Playwright.

Example:
    python scripts/backlot_watch_captures.py --projects why-cities-glow rain-on-glass
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASE_URL = "http://127.0.0.1:4750"
DEFAULT_CAPTURE_ROOT = REPO_ROOT / "internal" / "evals" / "captures"


def capture_slug(project_id: str, stage: str | None, status: str | None) -> str:
    """Stable, filesystem-safe screenshot name stem."""
    raw = "-".join(part for part in (project_id, stage or "unknown", status or "unknown") if part)
    raw = raw.replace("\\", "-").replace("/", "-").replace("..", "")
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip(".-")
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or "capture"


def state_fingerprint(state: dict[str, Any]) -> str:
    """Hashable representation of board-visible state.

    Intentionally ignores mtime-ish noise such as last_activity while keeping
    the pieces that should trigger a capture: stage transitions, generating
    flags, scene visual changes, costs, renders, and event count/tail.
    """
    scenes = []
    storyboard = state.get("storyboard") or {}
    for card in storyboard.get("scenes") or []:
        visual = card.get("visual") or {}
        scenes.append({
            "id": card.get("id"),
            "generating": bool(card.get("generating")),
            "generating_tool": card.get("generating_tool"),
            "visual": {
                "path": visual.get("path"),
                "exists": visual.get("exists"),
                "type": visual.get("type"),
            },
            "takes": [take.get("path") for take in (card.get("takes") or [])],
            "audio": [asset.get("path") for asset in (card.get("audio") or [])],
        })

    media = state.get("media") or {}
    events = state.get("events") or []
    visible = {
        "stages": [
            {
                "name": stage.get("name"),
                "status": stage.get("status"),
                "gate_skipped": stage.get("gate_skipped"),
                "versions": stage.get("versions"),
                "partial_progress": stage.get("partial_progress"),
            }
            for stage in state.get("stages") or []
        ],
        "scenes": scenes,
        "cost": state.get("cost"),
        "renders": [r.get("path") for r in media.get("renders") or []],
        "snapshots": [s.get("path") for s in media.get("snapshots") or []],
        "event_count": len(events),
        "event_tail": events[-3:],
    }
    return json.dumps(visible, sort_keys=True, default=str, separators=(",", ":"))


def active_stage(state: dict[str, Any]) -> tuple[str | None, str | None]:
    for stage in state.get("stages") or []:
        if stage.get("status") in {"in_progress", "awaiting_human", "failed", "blocked"}:
            return stage.get("name"), stage.get("status")
    for stage in reversed(state.get("stages") or []):
        if stage.get("status") == "completed":
            return stage.get("name"), stage.get("status")
    return None, None


def fetch_json(base_url: str, path: str) -> dict[str, Any] | list[Any]:
    with urllib.request.urlopen(f"{base_url.rstrip('/')}{path}", timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def capture_url(url: str, output: Path, *, width: int = 1560, height: int = 1150, wait_ms: int = 1200) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "npx",
            "playwright",
            "screenshot",
            "--viewport-size",
            f"{width},{height}",
            "--wait-for-timeout",
            str(wait_ms),
            url,
            str(output),
        ],
        cwd=REPO_ROOT,
        check=True,
        timeout=120,
        shell=(os.name == "nt"),
    )


def capture_project(base_url: str, capture_dir: Path, project_id: str, seq: int, state: dict[str, Any]) -> None:
    stage, status = active_stage(state)
    stem = f"{seq:03d}-{capture_slug(project_id, stage, status)}"
    capture_url(f"{base_url.rstrip('/')}/?static=1", capture_dir / "library" / f"{stem}.png", height=620)
    capture_url(
        f"{base_url.rstrip('/')}/p/{project_id}?static=1",
        capture_dir / project_id / f"{stem}.png",
    )


def watch(
    projects: list[str],
    *,
    base_url: str,
    capture_dir: Path,
    interval_s: float,
    once: bool = False,
    no_screenshots: bool = False,
) -> int:
    fingerprints: dict[str, str] = {}
    seq = 0
    capture_dir.mkdir(parents=True, exist_ok=True)
    print(f"[watch] base={base_url} captures={capture_dir}")
    while True:
        changed = False
        for project_id in projects:
            try:
                state = fetch_json(base_url, f"/api/project/{project_id}/state")
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"[watch] {project_id}: state fetch failed: {exc}", file=sys.stderr)
                continue
            fp = state_fingerprint(state)
            if fingerprints.get(project_id) == fp:
                continue
            fingerprints[project_id] = fp
            changed = True
            seq += 1
            stage, status = active_stage(state)
            print(f"[watch] change {project_id}: {stage or 'unknown'} -> {status or 'unknown'}")
            if not no_screenshots:
                capture_project(base_url, capture_dir, project_id, seq, state)
        if once:
            return 0
        if not changed:
            time.sleep(interval_s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", nargs="+", required=True, help="Project ids to watch")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--interval", type=float, default=20.0, help="Polling interval in seconds")
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument("--once", action="store_true", help="Poll once and exit")
    parser.add_argument("--no-screenshots", action="store_true", help="Exercise polling without Playwright")
    args = parser.parse_args(argv)

    out_dir = args.out_dir
    if out_dir is None:
        stamp = datetime.now().strftime("dogfood-%Y%m%d-%H%M%S")
        out_dir = DEFAULT_CAPTURE_ROOT / stamp
    return watch(
        args.projects,
        base_url=args.base_url,
        capture_dir=out_dir,
        interval_s=args.interval,
        once=args.once,
        no_screenshots=args.no_screenshots,
    )


if __name__ == "__main__":
    raise SystemExit(main())
