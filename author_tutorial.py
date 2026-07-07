#!/usr/bin/env python3
"""Tutorial authoring pass (Workflow A, step 2).

Runs the tutorial spec in fast collect-only mode (video off) to gather the
ordered narration steps, synthesizes each line once via the `ttsd` narration
sidecar to measure its duration, and writes the committed *.timings.json next to
the spec. The capture (Workflow B) then holds each step long enough for its
narration, and — because the narration cache is content-addressed — the render
reuses the exact same audio/durations.

Re-run whenever narration text or the voice changes.

Usage:
  python author_tutorial.py --tutorial sales-tour \
      --client-dir /path/to/circuitauction-backoffice/client \
      --base-url https://<demo-host>
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from tools.audio.narration_client import NarrationClient  # noqa: E402
from tools.capture import cypress_bridge as bridge  # noqa: E402
from render_tutorial import resolve_tutorial  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a tutorial's narration timings.json.")
    ap.add_argument("--tutorial", required=True)
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--narration-url", default="http://127.0.0.1:5557")
    ap.add_argument("--lang", default=None)
    ap.add_argument("--manifest", default=None,
                    help="reuse an existing collect manifest instead of running Cypress")
    args = ap.parse_args()

    client_dir = Path(args.client_dir).resolve()
    tut = resolve_tutorial(client_dir, args.tutorial)
    lang = args.lang or tut["recipe"].get("lang", "en")

    client = NarrationClient(args.narration_url)
    try:
        client.health()
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: ttsd not reachable at {args.narration_url}: {e}", file=sys.stderr)
        return 2

    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text())
    else:
        manifest = bridge.run_tutorial_spec(
            str(client_dir), tut["spec_rel"], base_url=args.base_url, collect_only=True
        )

    steps = sorted(manifest.get("steps", []), key=lambda s: s.get("index", 0))
    out_steps = []
    with tempfile.TemporaryDirectory() as tmp:
        for s in steps:
            text = (s.get("narration") or "").strip()
            if not text:
                continue
            idx = int(s.get("index", 0))
            dur = client.render(lang, text, str(Path(tmp) / f"step_{idx}.wav"))
            out_steps.append({"index": idx, "narration": text, "duration_ms": dur})

    timings = {"spec": tut["spec_rel"], "lang": lang, "steps": out_steps}
    tut["timings_path"].write_text(json.dumps(timings, indent=2))
    print(f"OK wrote {tut['timings_path']} ({len(out_steps)} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
