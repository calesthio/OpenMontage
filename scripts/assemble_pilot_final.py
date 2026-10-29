#!/usr/bin/env python3
"""Canonical final pilot assembly via ffmpeg.

78 Klein frames (1280x720), one per bit, hard-cut concatenation.
Each clip = bit duration with zoompan 3-5%.
Audio: mastered_full.wav (I=-16 LUFS).
Subtitles: subtitles_bits.srt burned (font 38px, lower third, outline 2px).

Usage:
    python3 scripts/assemble_pilot_final.py \
        --shot-list tools/kaggle_bridge/jobs/pilot-render/shot_list.json \
        --frame-dir tools/kaggle_bridge/jobs/pilot-render/frames_klein \
        --audio /tmp/master/mastered_full.wav \
        --subs tools/kaggle_bridge/jobs/pilot-render/audio/subtitles_bits.srt \
        --out remotion-composer/out/pilot-final.mp4

Все пути можно переопределить через аргументы; нет hardcoded /tmp/ путей.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

FPS = 30
OUT_W, OUT_H = 1280, 720
ZOOM_PCT = 0.04


def build_args() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Сборка финального пилота через ffmpeg")
    p.add_argument("--shot-list", required=True, type=Path,
                   help="shot_list.json с битами и таймингами")
    p.add_argument("--frame-dir", required=True, type=Path,
                   help="папка с кадрами sNN_BNNN.png")
    p.add_argument("--audio", required=True, type=Path,
                   help="мастеринг-аудио WAV (full)")
    p.add_argument("--subs", required=True, type=Path,
                   help="SRT с зажжёнными субтитрами")
    p.add_argument("--out", required=True, type=Path,
                   help="путь к выходному MP4")
    p.add_argument("--fps", type=int, default=FPS, help="кадров в секунду")
    p.add_argument("--zoom", type=float, default=ZOOM_PCT,
                   help="увеличение zoompan (доля от размера кадра)")
    return p


def section_durations(shots: list[dict]) -> dict[int, float]:
    """Считает длительность каждой секции как сумму её битов."""
    durs: dict[int, float] = {}
    for s in shots:
        durs[s["section"]] = durs.get(s["section"], 0.0) + (s["end"] - s["start"])
    return durs


def make_clip(ffmpeg: list[str], frame: Path, out_clip: Path, dur: float,
              fps: int, zoom: float, idx: int) -> None:
    frames = int(dur * fps)
    pan = 1 if idx % 2 == 0 else -1
    vf = (
        f"scale=1536:1536,"
        f"zoompan=z='1+{zoom}*on/{frames}':"
        f"x='iw/2-(iw/zoom)/2+{pan}*20*on/{frames}':"
        f"y='ih/2-(ih/zoom)/2':"
        f"d={frames}:s={OUT_W}x{OUT_H}:fps={fps}"
    )
    subprocess.run(
        ffmpeg + [
            "-y", "-loop", "1", "-i", str(frame),
            "-vf", vf, "-t", str(dur),
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20",
            "-pix_fmt", "yuv420p", "-an", str(out_clip),
        ],
        check=True, capture_output=True,
    )


def main() -> int:
    args = build_args().parse_args()

    for path, label in [(args.shot_list, "shot-list"), (args.frame_dir, "frame-dir"),
                        (args.audio, "audio"), (args.subs, "subs")]:
        if not path.exists():
            print(f"[FAIL] {label} не найден: {path}", file=sys.stderr)
            return 1

    data = json.loads(args.shot_list.read_text(encoding="utf-8"))
    shots = sorted(data["shots"], key=lambda s: (s["section"], int(s["bit_id"][1:])))

    # Абсолютные тайминги: смещаем каждый бит на начало своей секции
    sec_durs = section_durations(shots)
    sec_offset: dict[int, float] = {}
    acc = 0.0
    for sec in sorted(sec_durs):
        sec_offset[sec] = acc
        acc += sec_durs[sec]
    total_dur = acc

    abs_shots = []
    for shot in shots:
        off = sec_offset[shot["section"]]
        abs_shots.append({**shot, "abs_start": shot["start"] + off,
                          "abs_end": shot["end"] + off})

    tmp = Path(tempfile.mkdtemp(prefix="pilot_final_"))
    print(f"Temp: {tmp} | bits: {len(abs_shots)} | total: {total_dur:.2f}s")

    # --- Per-bit clips ---
    ffmpeg = ["ffmpeg"]
    clips: list[Path] = []
    for idx, shot in enumerate(abs_shots):
        fpath = args.frame_dir / f"s{shot['section']:02d}_{shot['bit_id']}.png"
        if not fpath.exists():
            print(f"[FAIL] Кадр не найден: {fpath}", file=sys.stderr)
            return 1
        clip = tmp / f"bit_{idx:03d}.mp4"
        dur = shot["abs_end"] - shot["abs_start"]
        make_clip(ffmpeg, fpath, clip, dur, args.fps, args.zoom, idx)
        clips.append(clip)

    # --- Concat ---
    concat_list = tmp / "concat.txt"
    with open(concat_list, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")

    interm = tmp / "interm.mp4"
    subprocess.run(
        ffmpeg + ["-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
                  "-i", str(args.audio),
                  "-c:v", "copy",
                  "-af", "alimiter",
                  "-c:a", "aac", "-b:a", "128k",
                  "-t", str(total_dur), str(interm)],
        check=True, capture_output=True,
    )
    print(f"Concat done: {interm} ({interm.stat().st_size / 1024 / 1024:.1f} MB)")

    # --- Burn subtitles ---
    subs_filter = (
        f"subtitles=filename={str(args.subs)}:"
        f"force_style='FontName=DejaVu Sans,FontSize=38,"
        f"PrimaryColour=&H00FFFFFF,BackColour=&H80000000,"
        f"Bold=1,Outline=2,Alignment=2,MarginV=70,MarginL=60,MarginR=60'"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ffmpeg + ["-y", "-i", str(interm), "-vf", subs_filter,
                  "-c:a", "copy", str(args.out)],
        check=True, capture_output=True,
    )
    print(f"\nOUTPUT: {args.out}")
    print(f"Size: {args.out.stat().st_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
