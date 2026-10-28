#!/usr/bin/env python3
"""Технический QC финального видео пилота.

Проверяет: существование файла, непустоту, duración, разрешение, FPS,
кодек, наличие аудио, loudness/TP через ebur128, чёрные кадры через blackdetect,
тишину через silencedetect. Выходит с кодом 0 только если все проверки PASS.

Используется после финальной сборки (категория A1).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

TARGET_W, TARGET_H = 1280, 720
TARGET_FPS = 30
TARGET_DUR_S = 1099.775
DUR_TOLERANCE_S = 6.0


def ffprobe_json(path: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(r.stdout)


def run_ffmpeg_filter(path: Path, vf: str) -> str:
    r = subprocess.run(
        ["ffmpeg", "-v", "info", "-i", str(path),
         "-vf", vf, "-f", "null", "-"],
        capture_output=True, text=True,
    )
    return r.stderr


def parse_duration(text: str) -> float | None:
    for line in text.splitlines():
        m = re.search(r"duration:\s*([\d.]+)", line)
        if m:
            return float(m.group(1))
    return None


import re  # noqa: E402


def check(condition: bool, msg: str, results: list[str]) -> None:
    status = "PASS" if condition else "FAIL"
    results.append(f"[{status}] {msg}")
    print(f"  [{status}] {msg}")


def main() -> int:
    parser = argparse.ArgumentParser(description="QC финального видео пилота")
    parser.add_argument("video", type=Path, help="путь к MP4 для проверки")
    args = parser.parse_args()

    video = args.video
    results: list[str] = []

    if not video.exists():
        print(f"[FAIL] Файл не существует: {video}")
        return 1
    if video.stat().st_size == 0:
        print(f"[FAIL] Файл пустой: {video}")
        return 1
    print(f"[PASS] Файл существует, не пуст ({video.stat().st_size / 1024 / 1024:.1f} MB)")

    info = ffprobe_json(video)

    # --- Видео поток ---
    v_streams = [s for s in info["streams"] if s["codec_type"] == "video"]
    a_streams = [s for s in info["streams"] if s["codec_type"] == "audio"]
    check(len(v_streams) == 1, "ровно один видеопоток", results)
    check(len(a_streams) >= 1, "есть хотя бы один аудиопоток", results)

    vs = v_streams[0]
    w = int(vs.get("width", 0))
    h = int(vs.get("height", 0))
    check(w == TARGET_W and h == TARGET_H,
          f"разрешение {w}x{h} (цель {TARGET_W}x{TARGET_H})", results)

    # FPS
    fps_str = vs.get("avg_frame_rate", "0/1")
    num, den = fps_str.split("/")
    fps = float(num) / float(den) if float(den) != 0 else 0
    check(abs(fps - TARGET_FPS) < 0.5,
          f"FPS {fps:.2f} (цель {TARGET_FPS})", results)

    codec = vs.get("codec_name", "")
    check(codec in ("h264", "hevc", "av1"), f"видеокодек {codec}", results)

    # --- Длительность ---
    dur = float(info.get("format", {}).get("duration", 0))
    check(abs(dur - TARGET_DUR_S) <= DUR_TOLERANCE_S,
          f"длительность {dur:.1f}s (цель {TARGET_DUR_S}±{DUR_TOLERANCE_S}s)", results)

    # --- Аудио ---
    as_ = a_streams[0]
    acodec = as_.get("codec_name", "")
    check(acodec in ("aac", "mp3", "opus"), f"аудиокодек {acodec}", results)

    # --- Full decode ---
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video),
                        "-f", "null", "-"], capture_output=True, text=True)
    check(r.returncode == 0, "полный декод без ошибок", results)
    if r.returncode != 0:
        print(f"  stderr: {r.stderr[:500]}")

    # --- Black detect ---
    black_txt = run_ffmpeg_filter(video, "blackdetect=d=0.5:pix_th=0.10")
    black_count = len(re.findall(r"black_start:", black_txt))
    check(black_count == 0, f"чёрных кадров: {black_count} (цель 0)", results)

    # --- Silence detect ---
    sil_txt = run_ffmpeg_filter(video, "silencedetect=n=-30dB:d=2.0")
    sil_count = len(re.findall(r"silence_start:", sil_txt))
    check(sil_count == 0, f"длительных тишины (>2s, -30dB): {sil_count} (цель 0)", results)

    # --- Loudness (ebur128) ---
    loud_txt = run_ffmpeg_filter(video, "ebur128=peak=true")
    i_match = re.search(r"I:\s*([\d.-]+)\s*LUFS", loud_txt)
    tp_match = re.search(r"TP:\s*([\d.-]+)\s*dBTP", loud_txt)
    loudness = float(i_match.group(1)) if i_match else None
    true_peak = float(tp_match.group(1)) if tp_match else None
    if loudness is not None:
        check(-20 <= loudness <= -10, f" loudness I={loudness:.1f} LUFS (цель -20..-10)", results)
    else:
        results.append("[FAIL] не удалось измерить loudness")
    if true_peak is not None:
        check(true_peak <= -1.0, f" true peak={true_peak:.1f} dBTP (цель ≤-1.0)", results)
    else:
        results.append("[FAIL] не удалось измерить true peak")

    # --- Итог ---
    print("\n" + "=" * 40)
    failed = [r for r in results if r.startswith("[FAIL]")]
    if failed:
        print(f"РЕЗУЛЬТАТ: FAIL — {len(failed)} проверок не пройдено")
        for f in failed:
            print(f"  {f}")
        return 1
    print(f"РЕЗУЛЬТАТ: PASS — все {len(results)} проверок пройдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
