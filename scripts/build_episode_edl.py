#!/usr/bin/env python3
"""scripts/build_episode_edl.py — one command: cards + EDL + render manifest.

Reads the labelled illustration manifest for an episode, draws one own-graphics
chapter card per script section, builds the EDL (sentences -> images, motion
rotation, labels, claim_ids) and writes the render manifest that cmd_render
consumes. Deterministic and offline: no network, no model calls.

    python scripts/build_episode_edl.py --episode se_pilot \
        [--images projects/se_pilot/assets/illustrations/illustration_manifest.json] \
        [--script projects/se_pilot/script.md] \
        [--duration 299.775] [--resolution 1280x720] [--fps 30]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.illustration.cards import make_section_cards  # noqa: E402
from tools.illustration.pilot_edl import (  # noqa: E402
    build_illustration_edl,
    images_from_manifest,
    script_sections,
)
from tools.packaging.rights_records import (  # noqa: E402
    build_rights_records,
    credits_lines,
    write_rights_records,
)


def narration_duration(episode_dir: Path, override: float | None = None) -> float | None:
    """Finished-narration duration from the manifest or ffprobe; None = BLOCKED."""
    if override:
        return float(override)
    manifest = episode_dir / "artifacts" / "narration_manifest.json"
    if manifest.is_file():
        dur = json.loads(manifest.read_text(encoding="utf-8")).get("expected_duration")
        if dur:
            return float(dur)
    wav = episode_dir / "narration_finished.wav"
    if wav.is_file():
        import subprocess

        res = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(wav)], capture_output=True, text=True)
        try:
            return float(res.stdout.strip())
        except ValueError:
            pass
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--episode", required=True)
    ap.add_argument("--episode-dir", default="")
    ap.add_argument("--images", default="")
    ap.add_argument("--script", default="")
    ap.add_argument("--cards-dir", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--duration", type=float, default=None)
    ap.add_argument("--card-duration", type=float, default=3.0)
    ap.add_argument("--resolution", default="1280x720")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--model", default="klein",
                    help="illustration model used for the rights/credit block")
    args = ap.parse_args(argv)

    ep = Path(args.episode_dir) if args.episode_dir else (
        ROOT / "projects" / args.episode)
    script = Path(args.script) if args.script else ep / "script.md"
    images_manifest = Path(args.images) if args.images else (
        ep / "assets" / "illustrations" / "illustration_manifest.json")
    cards_dir = Path(args.cards_dir) if args.cards_dir else ep / "assets" / "cards"
    out = Path(args.out) if args.out else ep / "edit_decisions.json"

    if not script.is_file():
        print(f"BLOCKED: script not found: {script}")
        return 2
    if not images_manifest.is_file():
        print(f"BLOCKED: illustration manifest not found: {images_manifest}")
        return 2

    images = images_from_manifest(images_manifest)
    sections = script_sections(script)
    if not images:
        print("BLOCKED: illustration manifest has no images")
        return 2
    if not sections:
        print("BLOCKED: script has no narration sections")
        return 2

    dur = narration_duration(ep, args.duration)
    if not dur:
        print("BLOCKED: no narration duration (run narration first)")
        return 2

    cards = make_section_cards(sections, cards_dir)
    edl = build_illustration_edl(
        images, None, total_duration=dur, topic=args.episode,
        episode=args.episode, sections=sections, card_paths=cards,
        card_duration=args.card_duration, out_path=out)
    edl["resolution"] = args.resolution
    edl["fps"] = args.fps
    out.write_text(json.dumps(edl, indent=2), encoding="utf-8")

    assets = {}
    for cut in edl["cuts"]:
        assets[cut["asset_id"]] = {"kind": cut["kind"], "path": cut["source"]}
    manifest = {
        "resolution": args.resolution,
        "fps": args.fps,
        "assets": assets,
    }
    manifest_path = out.parent / "render_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Rights records + credits are derived from the EDL, never hand-written.
    illust_manifest = json.loads(images_manifest.read_text(encoding="utf-8"))
    records = build_rights_records(edl, illust_manifest, model=args.model)
    art = ep / "artifacts"
    rights_path = write_rights_records(art / "rights_records.json", records)
    credits_path = art / "credits.txt"
    credits_path.write_text("\n".join(credits_lines(records)) + "\n",
                            encoding="utf-8")

    cards_n = sum(1 for c in edl["cuts"] if c["role"] == "graphics_card")
    print(f"episode={args.episode} duration={dur:.3f}s cuts={len(edl['cuts'])} "
          f"cards={cards_n} illustrations={len(images)}")
    print(f"edl={out}")
    print(f"render_manifest={manifest_path} assets={len(assets)}")
    print(f"rights_records={rights_path} records={len(records)}")
    print(f"credits={credits_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
