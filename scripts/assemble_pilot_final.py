#!/usr/bin/env python3
"""Final pilot assembly via ffmpeg (no Remotion). Two passes.

Pass A: xfade video (zoompan 3-5%, alternating pan, 0.5s fade) + concat audio
        -> temp_assembled.mp4
        clip_duration_i = audio_dur_i + 0.5 (0.5s pad = xfade overlap zone).
        xfade offsets: T_{i+1} = T_i + audio_dur_i, so video section boundaries
        match audio section boundaries exactly (no cumulative A/V drift;
        only a 0.5s crossfade lead-in per join).
Pass B: burn subtitles.srt (large sans-serif font, lower third)
        -> remotion-composer/out/pilot-final.mp4

No music file in assets/music/ -> final without music.
"""

import subprocess
import tempfile
from pathlib import Path

ROOT = Path("/workspaces/OpenMontage")
IMG_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/images_sdxl"
AUDIO_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/audio"
SRT = ROOT / "tools/kaggle_bridge/jobs/pilot-render/audio/subtitles.srt"
OUT_DIR = ROOT / "remotion-composer/out"
OUT = OUT_DIR / "pilot-final.mp4"

FPS = 30
OUT_W, OUT_H = 1280, 720
XFADE_DUR = 0.5
ZOOM_PCT = 0.04  # 4% zoom per clip (within 3-5%)

NUM_SECTIONS = 10


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def run(cmd, label):
    print(f"[{label}] ffmpeg ...")
    subprocess.run(cmd, check=True)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    audio_durs = [probe_duration(AUDIO_DIR / f"section_{i:02d}.wav")
                  for i in range(1, NUM_SECTIONS + 1)]
    clip_durs = [d + 0.5 for d in audio_durs]  # 0.5s pad = xfade overlap zone

    # Timeline offsets: T_i = sum of audio_dur of sections before i.
    offsets = [0.0]
    acc = 0.0
    for d in audio_durs[:-1]:
        acc += d
        offsets.append(acc)
    total_dur = sum(audio_durs)  # video (sum+0.5) truncated to sum via -t

    print(f"Audio durations: {[round(d, 3) for d in audio_durs]}")
    print(f"Timeline offsets:  {[round(o, 3) for o in offsets]}")
    print(f"Total duration: {total_dur:.3f}s")

    tmp = Path(tempfile.mkdtemp(prefix="pilot_final_"))
    assembled = tmp / "assembled.mp4"

    # ---- Per-section video-only clips (zoompan) ----
    clips = []
    for i in range(1, NUM_SECTIONS + 1):
        img = IMG_DIR / f"section_{i:02d}.png"
        if not img.exists():
            raise SystemExit(f"Missing {img}")
        clip = tmp / f"sec_{i:02d}.mp4"
        cd = clip_durs[i - 1]
        frames = int(cd * FPS)
        pan = 1 if i % 2 == 1 else -1  # alternate pan direction
        vf = (
            f"scale=1536:1536,"
            f"zoompan=z='1+{ZOOM_PCT}*on/{frames}':"
            f"x='iw/2-(iw/zoom)/2+{pan}*20*on/{frames}':"
            f"y='ih/2-(ih/zoom)/2':"
            f"d={frames}:s={OUT_W}x{OUT_H}:fps={FPS}"
        )
        run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img),
            "-vf", vf, "-t", str(cd),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-an",
            str(clip),
        ], f"section {i} video")
        clips.append(clip)

    # ---- Pass A: xfade video chain + concat audio ----
    inputs = []
    for c in clips:               # inputs 0..9 : video
        inputs += ["-i", str(c)]
    for i in range(1, NUM_SECTIONS + 1):  # inputs 10..19 : wav audio
        inputs += ["-i", str(AUDIO_DIR / f"section_{i:02d}.wav")]

    # Video xfade chain
    v_parts = []
    v_label = "0:v"
    for i in range(1, NUM_SECTIONS):
        out_v = f"v{i}"
        v_parts.append(
            f"[{v_label}][{i}:v]xfade=transition=fade:duration={XFADE_DUR}:"
            f"offset={offsets[i]}[{out_v}]"
        )
        v_label = out_v
    final_v = v_label  # [v9]

    # Audio concat chain (all 10 wavs back-to-back)
    a_labels = "".join(f"[{10+i}:a]" for i in range(NUM_SECTIONS))
    a_filter = f"{a_labels}concat=n={NUM_SECTIONS}:v=0:a=1[final_a]"

    filter_complex = "; ".join(v_parts) + "; " + a_filter

    run([
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filter_complex,
        "-map", f"[{final_v}]", "-map", "[final_a]",
        "-t", str(total_dur),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        str(assembled),
    ], "pass A xfade+concat")

    # ---- Pass B: burn subtitles ----
    subs_filter = (
        f"subtitles=filename={str(SRT)}:"
        f"force_style='FontName=DejaVu Sans,FontSize=24,"
        f"PrimaryColour=&H00FFFFFF,BackColour=&H80000000,"
        f"Bold=1,Alignment=2,MarginV=60,MarginL=40,MarginR=40'"
    )
    run([
        "ffmpeg", "-y", "-i", str(assembled),
        "-vf", subs_filter,
        "-c:a", "copy",
        str(OUT),
    ], "pass B subtitles")

    print(f"\nOUTPUT: {OUT}")
    print(f"Size: {OUT.stat().st_size / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
