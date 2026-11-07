#!/usr/bin/env python3
"""Инвентаризация артефактов пилота перед финальной сборкой.

Проверяет наличие всех 78 кадров Klein, 10 аудиофайлов, SRT-субтитров,
контакт-листов и мастеринг-аудио. Выходит с кодом 0 только если всё на месте.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRAME_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/frames_klein"
AUDIO_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/audio"
CONTACT_DIR = ROOT / "tools/kaggle_bridge/jobs/pilot-render/contact_sheets_klein"
SHOT_LIST = ROOT / "tools/kaggle_bridge/jobs/pilot-render/shot_list.json"
MASTER_AUDIO = Path("/tmp/master/mastered_full.wav")

errors: list[str] = []
warnings: list[str] = []


def check(condition: bool, msg: str) -> None:
    if condition:
        print(f"  [OK] {msg}")
    else:
        print(f"  [FAIL] {msg}")
        errors.append(msg)


def main() -> int:
    print("=== Аудит артефактов пилота ===\n")

    # --- shot_list.json ---
    if not SHOT_LIST.exists():
        print(f"[FAIL] shot_list.json не найден: {SHOT_LIST}")
        return 1
    data = json.loads(SHOT_LIST.read_text(encoding="utf-8"))
    shots = data["shots"]
    print(f"shot_list.json: {len(shots)} бит, секции: {sorted({s['section'] for s in shots})}")
    print(f"  total_audio_s: {data.get('total_audio_s')}, total_frames: {data.get('total_frames')}")

    # --- Кадры ---
    expected_frames = [f"s{sec:02d}_{bit['bit_id']}.png" for sec in range(1, 11) for bit in shots if bit["section"] == sec]
    print(f"\nОжидается кадров: {len(expected_frames)}")
    present = sorted(p.name for p in FRAME_DIR.glob("*.png")) if FRAME_DIR.exists() else []
    missing = [f for f in expected_frames if f not in present]
    extra = [f for f in present if f not in expected_frames]
    check(len(missing) == 0, f"все {len(expected_frames)} кадров на месте")
    if missing:
        print(f"  Отсутствуют: {missing[:10]}{'...' if len(missing) > 10 else ''}")
    if extra:
        warnings.append(f"лишние файлы в frames_klein: {extra[:5]}")
        print(f"  [WARN] лишние: {extra[:5]}")

    # --- Аудио ---
    print("\nАудио файлы:")
    audio_files = sorted(AUDIO_DIR.glob("section_*.wav")) if AUDIO_DIR.exists() else []
    check(len(audio_files) == 10, f"найдено {len(audio_files)} из 10 аудиофайлов")
    total_dur = 0.0
    for af in audio_files:
        total_dur += float(af.stat().st_size)  # placeholder, реальная длительность через ffprobe
    print(f"  всего файлов: {len(audio_files)}")

    # --- Субтитры ---
    srt_bits = AUDIO_DIR / "subtitles_bits.srt"
    srt_old = AUDIO_DIR / "subtitles.srt"
    check(srt_bits.exists(), f"subtitles_bits.str существует: {srt_bits}")
    if srt_bits.exists():
        blocks = sum(1 for line in srt_bits.read_text(encoding="utf-8").splitlines() if line.strip().isdigit())
        print(f"  блоков субтитров (bits): {blocks}")
    check(srt_old.exists(), f"subtitles.srt существует (старая версия): {srt_old}")

    # --- Контакт-листы ---
    print("\nКонтакт-листы:")
    contacts = sorted(CONTACT_DIR.glob("contact_sheet_klein_*.jpg")) if CONTACT_DIR.exists() else []
    check(len(contacts) == 7, f"найдено {len(contacts)} из 7 контакт-листов")

    # --- Мастеринг-аудио ---
    print("\nМастеринг-аудио:")
    check(MASTER_AUDIO.exists(), f"mastered_full.wav существует: {MASTER_AUDIO} ({MASTER_AUDIO.stat().st_size / 1024 / 1024:.1f} MB)")

    # --- Итог ---
    print("\n" + "=" * 40)
    if errors:
        print(f"РЕЗУЛЬТАТ: FAIL — {len(errors)} ошибок, {len(warnings)} предупреждений")
        for e in errors:
            print(f"  - {e}")
        for w in warnings:
            print(f"  - [WARN] {w}")
        return 1
    print(f"РЕЗУЛЬТАТ: PASS — все артефакты на месте ({len(warnings)} предупреждений)")
    for w in warnings:
        print(f"  - [WARN] {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
