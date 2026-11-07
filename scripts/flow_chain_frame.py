"""Pull the last frame out of a clip, to use as the next shot's start frame.

Flow's `flow_video` only accepts a *start* frame, so a multi-shot scene keeps
its cast, wardrobe and set consistent by chaining: each shot begins on the frame
the previous one ended. That is the only continuity guarantee available through
the start-frame input — same faces, same room, same light, because it is
literally the same image.

The trade-off is worth stating when you use it: the shots read as one continuous
take rather than separate camera setups. For a short dramatic beat that is
usually what you want; for a scene that needs real coverage it is not.

    python scripts/flow_chain_frame.py clip.mp4 next_start.png
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def last_frame(video: Path, out: Path, back_off_seconds: float = 0.15) -> Path:
    """Write the final frame of `video` to `out`.

    Seeks slightly before the end rather than to the very last frame: the last
    frame of an encoded clip is often a low-quality P-frame, and on some clips
    seeking exactly to the duration lands past the end and writes nothing.
    """
    if not video.is_file():
        raise SystemExit(f"no such clip: {video}")

    duration = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True).stdout.strip())

    seek = max(0.0, duration - back_off_seconds)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-ss", f"{seek:.3f}", "-i", str(video),
         "-frames:v", "1", str(out)],
        check=True)

    if not out.is_file() or out.stat().st_size < 1024:
        raise SystemExit(f"ffmpeg produced no usable frame at {seek:.2f}s of {video}")
    return out


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    written = last_frame(Path(sys.argv[1]), Path(sys.argv[2]))
    print(f"{written}  ({written.stat().st_size} bytes)")
