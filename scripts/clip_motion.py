"""Measure how much a clip actually moves, and compare it against a reference.

Ngày 8 shipped three shots that were technically correct and visibly dead: their
prompts said "locked-off", Flow obliged, and next to the published episodes they
looked like stills with a breeze. Nobody caught it by watching, because a still
shot does not look broken on its own — only beside a moving one.

So it gets measured. Mean absolute difference between consecutive frames, at
10fps on a 96x170 greyscale downscale: high enough to see a slow push-in, small
enough that grain and compression do not swamp it. The number has no physical
unit; it is only meaningful against another clip measured the same way.

The 'Dưới tán hoa' reference band, measured off the published episode:

    footage         1.9 - 8.7      every shot carries a slow continuous move
    text card       0.5            the only near-still frame in the piece

Under about 1.5 a shot reads as a still. Over about 12 it is faster than
anything the series has published, and on Ngày 8 that meant a descent three
times too quick to follow.

A number outside the band is a signal, not a debate. Ngày 8's descent measured
13.4 and the first reading of that was "a travelling shot turns the whole frame
over, so the band does not apply here" — written from an eight-frame contact
strip. Looked at properly the clip was broken twice over: the seedling ended up
buried inside the earth with no soil line anywhere, and the render had drifted
to photoreal against seven cel-shaded neighbours. The measurement was right and
the excuse was wrong.

So: out of band means open the clip and look at full size, at several points,
before deciding anything. If the reading still seems inapplicable, say why in
terms of what is visible on screen — never in terms of where the threshold came
from.

Look at every clip at its peak timestamp before accepting it. A number inside
the band only says the clip does not sit still and does not race; it says
nothing about whether the world stayed the same while the camera moved.

    python scripts/clip_motion.py <clip-or-dir> [more...]
    python scripts/clip_motion.py <dir> --cuts       # also flag mid-clip cuts
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

LOW, HIGH = 1.5, 12.0        # the reference band, rounded outward
CUT = 20.0                   # a jump this big between frames is a cut, not a move


def frame_deltas(clip: Path, fps: int = 10, w: int = 96, h: int = 170) -> np.ndarray:
    """Per-frame mean absolute difference over a small greyscale version."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(clip),
         "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
        capture_output=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)
    if len(frames) < 3:
        return np.zeros(0, np.float32)
    return np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))


def report(clip: Path, fps: int, find_cuts: bool) -> bool:
    deltas = frame_deltas(clip, fps)
    if not len(deltas):
        print(f"  {clip.stem:22} too short to measure")
        return True

    mean = float(deltas.mean())
    note = ""
    ok = True
    if mean < LOW:
        note, ok = f"  <- STILL (under {LOW}); reads as a photograph", False
    elif mean > HIGH:
        note, ok = f"  <- TOO FAST (over {HIGH}); faster than the series has published", False

    # Where the peak is matters as much as how big it is. Ngày 8's shot 3 peaked
    # at 16.0 — under the cut threshold, so it was passed over — and that peak was
    # Veo dissolving the background and replacing the room behind the seedling.
    # A first-and-last-frame review cannot see that; it happens in the middle. So
    # the peak's timestamp is printed always, as somewhere to go and look.
    peak = int(np.argmax(deltas))
    print(f"  {clip.stem:22} mean {mean:5.2f}   p90 {np.percentile(deltas, 90):5.2f}   "
          f"max {deltas.max():5.2f} @ {peak / fps:4.1f}s{note}")

    # A clip is meant to be one continuous shot. A single frame pair that jumps
    # this hard is Veo having inserted a cut of its own, which no amount of
    # prompt tuning fixes after the fact — the clip has to be made again.
    if find_cuts:
        for i, value in enumerate(deltas):
            if value > CUT:
                print(f"      cut inside the clip at t={i / fps:.1f}s (delta {value:.1f})")
                ok = False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="clips, or directories of clips")
    parser.add_argument("--fps", type=int, default=10)
    parser.add_argument("--cuts", action="store_true",
                        help="also flag hard cuts inside a clip")
    args = parser.parse_args()

    clips: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        clips.extend(sorted(path.glob("*.mp4")) if path.is_dir() else [path])
    if not clips:
        raise SystemExit("no clips found")

    print(f"reference band: footage {LOW}-{HIGH}")
    ok = all([report(clip, args.fps, args.cuts) for clip in clips])
    print("\nall clips inside the band" if ok else "\nsome clips are outside the band")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
