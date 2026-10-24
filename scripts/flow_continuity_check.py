"""Build the evidence a continuity pass needs: seams and shot cards.

AI shots are generated independently, so they break continuity in ways a single
clip never reveals — a tool changes shape between shots, soil that was turned is
smooth again, a sign planted in shot 8 is a different sign, the light jumps from
morning to noon. None of that is visible while watching one clip; all of it is
obvious the moment you put the last frame of shot N beside the first frame of
shot N+1.

So this writes two kinds of sheet:

  seam_N_to_M.jpg   last frame of one shot | first frame of the next
  shot_N.jpg        first | middle | last of a single shot

The seam sheets are the ones that matter. Reviewing them is a judgement call —
this script only makes the judgement cheap to perform.

    python scripts/flow_continuity_check.py <clip-dir> [--out <dir>]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

FRAME_H = 420          # tall enough to judge a face or a hand, small enough to scan


def duration(clip: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def frame(clip: Path, at: float, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{max(at, 0):.3f}", "-i", str(clip),
         "-frames:v", "1", "-vf", f"scale=-2:{FRAME_H}", str(dest)],
        check=True)
    if not dest.is_file():
        raise SystemExit(f"ffmpeg wrote no frame at {at:.2f}s of {clip.name}")
    return dest


def hstack(images: list[Path], dest: Path, labels: list[str]) -> Path:
    """Lay frames side by side with a caption strip under each."""
    inputs: list[str] = []
    for image in images:
        inputs += ["-i", str(image)]

    filters = []
    for i, label in enumerate(labels):
        safe = label.replace(":", r"\:").replace("'", "")
        filters.append(
            f"[{i}:v]pad=iw:ih+34:0:0:color=black,"
            f"drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='{safe}':"
            # y=h-25, not ih-25: inside drawtext `h` is the frame height and
            # `ih` is undefined, which ffmpeg rejects as an expression error.
            f"fontcolor=white:fontsize=17:x=10:y=h-25[v{i}]"
        )
    chain = "".join(f"[v{i}]" for i in range(len(images)))
    filters.append(f"{chain}hstack=inputs={len(images)}[out]")

    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", *inputs,
         "-filter_complex", ";".join(filters), "-map", "[out]", str(dest)],
        check=True)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("clip_dir")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    clip_dir = Path(args.clip_dir)
    clips = sorted(c for c in clip_dir.glob("*.mp4") if not c.name.startswith("_"))
    # A stitched master sitting beside its parts would be reviewed as if it were
    # another shot, and its "seams" are meaningless.
    clips = [c for c in clips if len(c.stem) > 2 and c.stem[:2].isdigit()]
    if len(clips) < 2:
        raise SystemExit(f"need at least two numbered clips in {clip_dir}")

    out = Path(args.out or (clip_dir.parent / "continuity"))
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / ".frames"

    print(f"{len(clips)} clips -> {out}\n")

    for clip in clips:
        span = duration(clip)
        marks = [(0.05, "first"), (span / 2, "middle"), (span - 0.15, "last")]
        frames = [frame(clip, at, tmp / f"{clip.stem}_{tag}.jpg") for at, tag in marks]
        hstack(frames, out / f"shot_{clip.stem}.jpg",
               [f"{clip.stem}  {tag}  {at:.1f}s" for at, tag in marks])
        print(f"shot_{clip.stem}.jpg")

    print()
    for earlier, later in zip(clips, clips[1:]):
        end = frame(earlier, duration(earlier) - 0.15, tmp / f"seam_{earlier.stem}_end.jpg")
        start = frame(later, 0.05, tmp / f"seam_{later.stem}_start.jpg")
        name = f"seam_{earlier.stem[:2]}_to_{later.stem[:2]}.jpg"
        hstack([end, start], out / name,
               [f"{earlier.stem}  LAST", f"{later.stem}  FIRST"])
        print(name)

    for leftover in tmp.glob("*.jpg"):
        leftover.unlink()
    tmp.rmdir()

    print(f"\nReview the seam sheets first — that is where continuity breaks show.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
