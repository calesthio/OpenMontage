"""Lay a generated Vietnamese voiceover onto a finished cut, line by line.

    python scripts/_voiceover.py projects/duoi-tan-hoa-ngay-6

Reads `assets/subtitles.srt` for where each line belongs, `assets/vo_raw.wav`
plus `assets/vo_segments.json` for the speech itself, and writes the muxed
master and the caption file beside them.

The speech is *placed*, not concatenated. VieNeu returns one continuous wav with
its own gaps, and simply muxing that would drift further from the picture with
every line — 44 seconds of speech under 64 seconds of film means the last line
would land twenty seconds early. So each line is cut out and put back at its own
cue.

Two rules decide the placement, and the second one matters more than it looks:

* a line never starts before its cue, so a line written for a shot cannot be
  heard over the shot before it;
* a line never starts before the previous line has finished. Generated speech
  is not the length the subtitle was written for, and where it overruns, the
  next line slides. That drift is reported rather than absorbed, because a line
  pushed past its own shot is a cut that needs re-timing, not a rounding error.

Captions are then written from where the speech actually landed, not from the
.srt. The .srt is the plan; the voice is what the viewer hears, and when they
disagree the subtitle is the one that is wrong.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

_CAPTION = Path(__file__).resolve().parent / "_caption_ngay8.py"

# Ngày 8's measured delivery level: quiet enough to sit under ambient, loud
# enough on a phone speaker.
LUFS = -15.0
PEAK_DBFS = -1.4
# Smallest gap left between two lines when speech overruns its slot.
MIN_GAP = 0.12


def _caption_module():
    spec = importlib.util.spec_from_file_location("cap", _CAPTION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def place(cues, segments):
    """Where each line starts in the finished cut, and how long it runs."""
    placed, cursor = [], 0.0
    for (cue_start, _, text), seg in zip(cues, segments):
        length = seg["end"] - seg["start"]
        start = max(cue_start, cursor)
        placed.append({"start": start, "length": length, "text": text,
                       "src_start": seg["start"], "late": round(start - cue_start, 2)})
        cursor = start + length + MIN_GAP
    return placed


def build_track(raw: Path, placed, out: Path, total: float) -> None:
    """One input per line, delayed to its slot, mixed onto a silent bed."""
    args = ["ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=mono"]
    for line in placed:
        args += ["-ss", f"{line['src_start']:.3f}", "-t", f"{line['length']:.3f}", "-i", str(raw)]

    chains = []
    for i, line in enumerate(placed, start=1):
        chains.append(f"[{i}:a]aresample=48000,adelay={int(line['start'] * 1000)}|"
                      f"{int(line['start'] * 1000)}[a{i}]")
    mix = "".join(f"[a{i}]" for i in range(1, len(placed) + 1))
    chains.append(f"[0:a]{mix}amix=inputs={len(placed) + 1}:normalize=0:dropout_transition=0[m]")
    # loudnorm resamples to its own internal rate (96 kHz here), which is not a
    # sample rate a phone player should be handed; put it back to 48 kHz.
    chains.append(f"[m]loudnorm=I={LUFS}:TP={PEAK_DBFS}:LRA=11,aresample=48000[out]")

    args += ["-filter_complex", ";".join(chains), "-map", "[out]",
             "-c:a", "pcm_s16le", str(out)]
    subprocess.run(args, check=True)


def main() -> int:
    project = Path(sys.argv[1] if len(sys.argv) > 1 else "projects/duoi-tan-hoa-ngay-6")
    assets = project / "assets"
    cap = _caption_module()

    cues = cap.read_srt(assets / "subtitles.srt")
    segments = json.loads((assets / "vo_segments.json").read_text(encoding="utf-8"))
    if len(cues) != len(segments):
        raise SystemExit(f"{len(cues)} subtitle cues but {len(segments)} spoken lines")

    silent = project / "renders" / "final.mp4"
    total = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(silent)],
        capture_output=True, text=True, check=True).stdout.strip())

    placed = place(cues, segments)
    overrun = [p for p in placed if p["late"] > 0.25]
    end = placed[-1]["start"] + placed[-1]["length"]
    print(f"{len(placed)} lines, speech ends {end:.2f}s of {total:.2f}s")
    for p in overrun:
        print(f"  late {p['late']:+.2f}s  {p['text'][:44]}")
    if end > total:
        raise SystemExit(f"the voice runs {end - total:.2f}s past the picture — re-time the .srt")

    track = assets / "vo_track.wav"
    build_track(assets / "vo_raw.wav", placed, track, total)

    voiced = assets / "_cut_vo.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(track),
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                    # No -shortest: the silent bed is built to the picture's own
                    # length, and -shortest was clipping the last frames off.
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                    str(voiced)], check=True)

    # Captions from where the voice landed, not from the plan.
    spoken = assets / "subtitles_spoken.srt"
    spoken.write_text("".join(
        f"{i}\n{_stamp(p['start'])} --> {_stamp(p['start'] + p['length'])}\n{p['text']}\n\n"
        for i, p in enumerate(placed, start=1)), encoding="utf-8")

    subprocess.run([sys.executable, str(_CAPTION), "--assets", str(assets),
                    "--srt", str(spoken), "--in", "_cut_vo.mp4",
                    "--out", "_cut_cap.mp4"], check=True)

    final = project / "renders" / "final_voice.mp4"
    final.write_bytes((assets / "_cut_cap.mp4").read_bytes())
    print(f"-> {final}")
    return 0


def _stamp(seconds: float) -> str:
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{int(hours):02d}:{int(minutes):02d}:{secs:06.3f}".replace(".", ",")


if __name__ == "__main__":
    raise SystemExit(main())
