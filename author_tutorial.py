#!/usr/bin/env python3
"""Tutorial authoring pass (Workflow A, step 2).

Runs the tutorial spec in fast collect-only mode (video off) to gather the
ordered narration steps, synthesizes each line once via the narration backend
(ttsd sidecar or ElevenLabs direct, --narration-backend) to measure its duration, and writes the committed *.timings.json next to
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
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
# Repo-local virtualenv fallback: when this script runs under an interpreter that
# lacks the requirements (e.g. the system python3 that hosts the MCP server), use
# the packages installed in ./.venv (`uv venv .venv && uv pip install -r requirements.txt`).
try:
    import jsonschema  # noqa: F401
except ImportError:
    import sysconfig as _sc
    _venv_sp = REPO_ROOT / ".venv" / "lib" / f"python{_sc.get_python_version()}" / "site-packages"
    if _venv_sp.is_dir():
        sys.path.append(str(_venv_sp))

from lib import tutorial as T  # noqa: E402
from lib.envfile import parse_env_file  # noqa: E402
from tools.audio.narration_client import NarrationError  # noqa: E402
from tools.capture import cypress_bridge as bridge  # noqa: E402
from render_tutorial import resolve_tutorial  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate a tutorial's narration timings.json.")
    ap.add_argument("--tutorial", required=True)
    ap.add_argument("--client-dir", required=True)
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--narration-url", default="http://127.0.0.1:5557")
    ap.add_argument("--narration-backend", choices=list(T.NARRATION_BACKENDS), default=None)
    ap.add_argument("--voice-id", default=None)
    ap.add_argument("--lang", default=None)
    ap.add_argument("--manifest", default=None,
                    help="reuse an existing collect manifest instead of running Cypress")
    args = ap.parse_args()

    client_dir = Path(args.client_dir).resolve()
    tut = resolve_tutorial(client_dir, args.tutorial)
    lang = args.lang or tut["recipe"].get("lang", "en")

    env = {**parse_env_file(REPO_ROOT / ".env"), **os.environ}
    try:
        backend, voice_id = T.resolve_narration_choice(
            cli_backend=args.narration_backend, cli_voice_id=args.voice_id,
            recipe=tut["recipe"], env=env,
        )
        client = T.narration_client_for(
            backend, narration_url=args.narration_url, voice_id=voice_id, env=env,
        )
        client.health()
    except (ValueError, NarrationError) as e:
        print(f"ERROR: narration backend not ready: {e}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001  (ttsd unreachable)
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

    timings = {
        "spec": tut["spec_rel"],
        "lang": lang,
        "narration": {"backend": backend, "voice_id": voice_id},
        "steps": out_steps,
    }
    tut["timings_path"].write_text(json.dumps(timings, indent=2))
    print(f"OK wrote {tut['timings_path']} ({len(out_steps)} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
