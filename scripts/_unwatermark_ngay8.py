"""Take the Flow sparkle off a series episode without cropping the frame.

    python scripts/_unwatermark_ngay8.py [projects/duoi-tan-hoa-ngay-7]

Four methods were tried against real footage. Only one survives.

`crop` works everywhere and was rejected: it throws away the bottom 12% and
re-frames every shot.

`delogo` interpolates a *rectangle* from its own edges. On dark tilled soil that
is undetectable. Anywhere with structure it is worse than the mark it removes —
a 72x72 smear across a diagonal beam of wood, or a smooth streak inside fine
speckle, is far louder than the sparkle. Shrinking the box only shrinks the
streak.

`unblend` inverted an alpha composite: observed = (1-a)*background + a*C, fitted
at C=225 with a peak alpha of 0.45. It was right for the footage it was fitted
on and it is **wrong for anything Flow makes now**, which is why no code here
calls it any more. The platform rewrite of 2026-09 changed the mark, and the
measurement says so plainly: the same sparkle sits +39 above a background of 62
and +91 above a background of 131. An alpha blend toward a fixed colour lifts a
*dark* background more than a bright one, so the lift must fall as the
background brightens. This one rises. Scaling alpha down from 1.0 to 0.55 never
removed the star, and clamping the divisor harder never removed it either --
which is what says the error is in the subtraction, not the division.

The trap in that finding is how it hides. Inverting a wrong model leaves a dark
star, and a dark star is invisible on bright cloth and pale tile. Two crops
chosen from the brightest shots in the episode said "clean" while four of six
clips carried an obvious artifact.

`removelogo` is `delogo` done on the mark's own shape: given a mask it
interpolates only those pixels, so a beam of wood runs straight through where
the star used to be instead of dissolving into a block. It needs no model of how
the mark was composited, which is exactly why it survived the platform changing
underneath it. It is used for every clip: there is no brightness split any more,
and one method for all six shots is also one less thing to be wrong about.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# The mark's own silhouette: the old alpha profile thresholded and dilated three
# pixels. Without the dilation, removelogo interpolates from pixels that still
# carry the mark's soft edge and leaves a faint halo.
MASK = Path("projects/_brand/flow-watermark-mask.png")

# The episode is an argument because the mark is a property of Flow, not of one
# day's story.
PROJECT = Path(sys.argv[1] if len(sys.argv) > 1 else "projects/duoi-tan-hoa-ngay-8")
SRC = PROJECT / "assets" / "video"
DST = PROJECT / "assets" / "video_clean"


def removelogo(src: Path, dst: Path) -> None:
    """Interpolate the mark's own pixels away, using its shape as a mask.

    The mask path is passed relative to the working directory on purpose: a
    filter argument splits on ":", so an absolute Windows path turns
    `removelogo=C:/...` into a parse error that names the whole filterchain and
    not the colon.
    """
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                    "-vf", f"removelogo={MASK.as_posix()}",
                    "-c:v", "libx264", "-crf", "17", "-preset", "slow",
                    "-pix_fmt", "yuv420p", "-c:a", "copy", str(dst)], check=True)


def main() -> int:
    if not MASK.is_file():
        raise SystemExit(f"missing the mark's mask at {MASK}")
    DST.mkdir(parents=True, exist_ok=True)

    clips = sorted(SRC.glob("0*.mp4"))
    if not clips:
        raise SystemExit(f"no numbered clips in {SRC}")
    for clip in clips:
        out = DST / clip.name
        removelogo(clip, out)
        print(f"{clip.stem:20} -> removelogo  {out.stat().st_size / 1e6:.1f} MB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
