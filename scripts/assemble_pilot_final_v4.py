#!/usr/bin/env python3
"""Final pilot assembly v4 via ffmpeg — concat demuxer + subtitles.

78 Klein frames (1280x720), one per bit, hard-cut concatenation.
Each clip = bit duration with zoompan 3-5%.
Audio: mastered.wav (I=-16 LUFS).
Subtitles: subtitles_bits.srt burned (font 38px, lower third, outline 2px).
"""

import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path("/workspaces/OpenMontage")
FRAME_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/frames_klein"
SL = ROOT / "tools/kaggle_bridge/jobs/pilot-render/shot_list.json"
SRT = ROOT / "tools/kaggle_bridge/jobs/pilot-render/audio/subtitles_bits.srt"
MASTER_AUDIO = Path("/tmp/master/mastered_full.wav")
OUT_DIR = ROOT / "remotion-composer/out"
OUT = OUT_DIR / "pilot-final.mp4"

FPS = 30
OUT_W, OUT_H = 1280, 720
ZOOM_PCT = 0.04


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = json.loads(SL.read_text())
    shots = sorted(data["shots"], key=lambda s: (s["section"], int(s["bit_id"][1:])))

    section_durs = {1: 83.025, 2: 129.400, 3: 148.600, 4: 135.500, 5: 132.875,
                    6: 137.750, 7: 99.875, 8: 101.375, 9: 83.575, 10: 47.800}
    section_offset = {}
    acc = 0.0
    for sec in range(1, 11):
        section_offset[sec] = acc
        acc += section_durs[sec]
    total_dur = acc

    abs_shots = []
    for shot in shots:
        off = section_offset[shot["section"]]
        abs_shots.append({**shot, "abs_start": shot["start"] + off, "abs_end": shot["end"] + off})
    shots = abs_shots

    tmp = Path(tempfile.mkdtemp(prefix="pilot_final_v4_"))
    print(f"Temp: {tmp} | bits: {len(shots)} | total: {total_dur:.2f}s")

    # ---- Per-bit clips ----
    clips = []
    for idx, shot in enumerate(shots):
        fpath = FRAME_DIR / f"s{shot['section']:02d}_{shot['bit_id']}.png"
        if not fpath.exists():
            raise SystemExit(f"Missing frame {fpath}")
        clip = tmp / f"bit_{idx:03d}.mp4"
        dur = shot["abs_end"] - shot["abs_start"]
        frames = int(dur * FPS)
        pan = 1 if idx % 2 == 0 else -1
        vf = (
            f"scale=1536:1536,"
            f"zoompan=z='1+{ZOOM_PCT}*on/{frames}':"
            f"x='iw/2-(iw/zoom)/2+{pan}*20*on/{frames}':"
            f"y='ih/2-(ih/zoom)/2':"
            f"d={frames}:s={OUT_W}x{OUT_H}:fps={FPS}"
        )
        subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(fpath),
            "-vf", vf, "-t", str(dur),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-an", str(clip),
        ], check=True, capture_output=True)
        clips.append(clip)

    # ---- Concat list ----
    concat_list = tmp / "concat.txt"
    with open(concat_list, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")

    interm = tmp / "interm.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-i", str(MASTER_AUDIO),
        "-c:v", "copy",
        "-af", "alimiter",
        "-c:a", "aac", "-b:a", "128k",
        "-t", str(total_dur),
        str(interm),
    ], check=True)
    print(f"Concat done: {interm} ({interm.stat().st_size/1024/1024:.1f} MB)")

    # ---- Burn subtitles ----
    subs_filter = (
        f"subtitles=filename={str(SRT)}:"
        f"force_style='FontName=DejaVu Sans,FontSize=38,"
        f"PrimaryColour=&H00FFFFFF,BackColour=&H80000000,"
        f"Bold=1,Outline=2,Alignment=2,MarginV=70,MarginL=60,MarginR=60'"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(interm),
        "-vf", subs_filter,
        "-c:a", "copy",
        str(OUT),
    ], check=True)
    print(f"\nOUTPUT: {OUT}")
    print(f"Size: {OUT.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
