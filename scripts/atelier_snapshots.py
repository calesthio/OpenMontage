"""Render one review still per scene for an atelier (bespoke) composition.

The Backlot storyboard can't thumbnail a `.tsx` scene, so a bespoke run
populates the assets-gate filmstrip by writing `projects/<slug>/snapshots/
<scene_id>.png` — one Remotion `still` per scene at a representative frame.
Run this AT THE ASSETS GATE (before any draft/compose render):

    python scripts/atelier_snapshots.py <slug>

It reads scene timings from `artifacts/scene_plan.json` and the bespoke render
config from `artifacts/edit_decisions.json` (falling back to conventional
paths: index.tsx / artifacts/props.json / public/). The composition id comes
from edit_decisions.bespoke.composition_id or --composition-id.

See skills/meta/bespoke-composition.md and skills/meta/checkpoint-protocol.md.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

# On Windows npx is npx.cmd — resolve it so subprocess finds it without a shell.
NPX = shutil.which("npx") or "npx"

REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSER_DIR = REPO_ROOT / "remotion-composer"


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", help="project slug under projects/")
    ap.add_argument("--composition-id", help="Remotion composition id (else from edit_decisions)")
    ap.add_argument("--entry", help="entry .tsx (default projects/<slug>/index.tsx)")
    ap.add_argument("--props", help="props JSON (default artifacts/props.json)")
    ap.add_argument("--public-dir", help="public dir (default projects/<slug>/public)")
    ap.add_argument("--fps", type=int, default=None, help="frames per second (default from props or 30)")
    ap.add_argument("--only", nargs="*", help="only these scene ids")
    args = ap.parse_args(argv)

    proj = REPO_ROOT / "projects" / args.slug
    if not proj.is_dir():
        print(f"error: no project at {proj}", file=sys.stderr)
        return 2

    scene_plan = _load(proj / "artifacts" / "scene_plan.json")
    scenes = (scene_plan.get("scenes") or []) if isinstance(scene_plan, dict) else []
    if not scenes:
        print("error: no scenes in artifacts/scene_plan.json", file=sys.stderr)
        return 2

    edit = _load(proj / "artifacts" / "edit_decisions.json")
    bespoke = (edit.get("bespoke") or {}) if isinstance(edit, dict) else {}
    props_path = Path(args.props or bespoke.get("props_path") or (proj / "artifacts" / "props.json"))
    entry = Path(args.entry or bespoke.get("entry") or (proj / "index.tsx"))
    if not entry.is_absolute():
        entry = (REPO_ROOT / entry).resolve()
    public_dir = Path(args.public_dir or bespoke.get("public_dir") or (proj / "public"))
    comp_id = args.composition_id or bespoke.get("composition_id")
    if not comp_id:
        print("error: composition id unknown (pass --composition-id or set edit_decisions.bespoke)", file=sys.stderr)
        return 2

    fps = args.fps
    if fps is None:
        props = _load(props_path)
        fps = int(props.get("fps") or 30)

    # Stage the project into remotion-composer so webpack resolves node_modules.
    sys.path.insert(0, str(REPO_ROOT))
    from tools.video.video_compose import VideoCompose  # noqa: E402
    staged_entry = VideoCompose()._stage_atelier_project(entry, COMPOSER_DIR)

    snap_dir = proj / "snapshots"
    snap_dir.mkdir(exist_ok=True)

    ok, fail = 0, 0
    for sc in scenes:
        sid = str(sc.get("id") or "").strip()
        if not sid:
            continue
        if args.only and sid not in args.only:
            continue
        start = sc.get("start_seconds")
        end = sc.get("end_seconds")
        mid = ((start + end) / 2) if (start is not None and end is not None) else (start or 0)
        frame = max(0, round(mid * fps))
        out = snap_dir / f"{sid}.png"
        cmd = [
            NPX, "remotion", "still", str(staged_entry), str(comp_id), str(out.resolve()),
            f"--frame={frame}",
            f"--props={props_path.resolve()}",
            f"--public-dir={public_dir.resolve()}",
        ]
        try:
            subprocess.run(cmd, cwd=COMPOSER_DIR, check=True, capture_output=True, text=True, timeout=600)
            ok += 1
            print(f"  {sid}: frame {frame} -> {out.relative_to(REPO_ROOT)}")
        except subprocess.CalledProcessError as e:
            fail += 1
            print(f"  {sid}: FAILED — {(e.stderr or e.stdout or '')[-300:]}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  {sid}: FAILED — {e}", file=sys.stderr)

    print(f"snapshots: {ok} ok, {fail} failed -> {snap_dir.relative_to(REPO_ROOT)}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
