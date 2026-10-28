#!/usr/bin/env python3
"""scripts/iss_kokoro_narrate.py — re-narrate the ISS script (v1) with Kokoro-82M.

Parses ISS_FULL_SCRIPT_v0.md sentences, synthesizes each with kokoro KPipeline
(af_heart, cached PyTorch weights), concatenates with pauses, runs finish_audio
(loudnorm to I=-14, TP=-1.5), writes subtitles.srt + narration_manifest.json.

Outputs (docs/openmontage/slice/iss/audio/):
  narration_raw.wav, narration_spoken.txt, narration_finished.wav,
  subtitles.srt, narration_manifest.json
"""

import json
import re
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro import KPipeline

SRC = "docs/openmontage/slice/iss/ISS_FULL_SCRIPT_v0.md"
AUDIO_DIR = Path("docs/openmontage/slice/iss/audio")
SR = 24000
INTRO_S, PAUSE_S, TRAIL_S = 1.0, 0.5, 1.3


def parse_sentences(path):
    sents = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        if not re.fullmatch(r"B\d+", cells[0]):
            continue
        sents.append(cells[1])
    return sents


def hmsms(sec):
    td = timedelta(seconds=sec)
    total_ms = int(td.total_seconds() * 1000)
    h = total_ms // 3_600_000
    m = (total_ms % 3_600_000) // 60_000
    s = (total_ms % 60_000) // 1000
    ms = total_ms % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    sentences = parse_sentences(SRC)
    print(f"{len(sentences)} sentences to narrate")

    pipeline = KPipeline(lang_code="a")
    silence = lambda sec: np.zeros(int(sec * SR), dtype=np.float32)
    parts = [silence(INTRO_S)]
    spoken = []
    cues = []  # (start, end, text)
    t = INTRO_S
    for text in sentences:
        gen = pipeline(text, voice="af_heart", speed=1.0)
        audio = None
        for _, _, seg in gen:
            audio = np.asarray(seg, dtype=np.float32)
        if audio is None:
            audio = np.zeros(1, dtype=np.float32)
        start = t
        parts.append(audio)
        t += len(audio) / SR
        parts.append(silence(PAUSE_S))
        t += PAUSE_S
        end = t
        cues.append((start, end, text))
        spoken.append(text)
    parts[-1] = silence(TRAIL_S)
    narration = np.concatenate(parts)
    raw_wav = AUDIO_DIR / "narration_raw.wav"
    sf.write(raw_wav, narration, SR)
    dur = len(narration) / SR
    Path(AUDIO_DIR / "narration_spoken.txt").write_text(" ".join(spoken), encoding="utf-8")
    print(f"raw duration {dur:.2f}s, {len(sentences)} sentences")

    # subtitles
    srt_lines = []
    for i, (start, end, text) in enumerate(cues, 1):
        srt_lines.append(str(i))
        srt_lines.append(f"{hmsms(start)} --> {hmsms(end)}")
        srt_lines.append(text)
        srt_lines.append("")
    (AUDIO_DIR / "subtitles.srt").write_text("\n".join(srt_lines), encoding="utf-8")

    # finish_audio
    sys.path.insert(0, ".")
    from tools.audio.finish_audio import FinishAudioTool
    fin = FinishAudioTool()
    res = fin.execute({
        "input_path": str(raw_wav),
        "output_path": str(AUDIO_DIR / "narration_finished.wav"),
    })
    print("finish_audio:", res.success, res.error, res.data.get("measured_loudness") if res.data else None)

    manifest = {
        "sentences": len(sentences),
        "duration_s": round(dur, 6),
        "finished_duration_s": None,
        "sample_rate": SR,
        "beats": [f"B{i}" for i in range(1, 9)],
        "engine": "kokoro_82m_cpu",
        "voice": "af_heart",
        "script": SRC,
    }
    (AUDIO_DIR / "narration_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("wrote narration_manifest.json")


if __name__ == "__main__":
    main()
