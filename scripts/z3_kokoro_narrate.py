#!/usr/bin/env python3
"""scripts/z3_kokoro_narrate.py — synthesize a script's sentences with Kokoro-82M ONNX CPU.

Uses kokoro-onnx (PyPI) + Kokoro-82M ONNX weights from GitHub Releases
(thewh1teagle/kokoro-onnx release model-files-v1.1). Weights live in
/tmp/kilo/kokoro_onnx_weights/ (gitignored, outside the repo).
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from kokoro_onnx import Kokoro

MODEL = "/tmp/kilo/kokoro_onnx_weights/kokoro-v1.0.onnx"
VOICES = "/tmp/kilo/kokoro_onnx_weights/voices-v1.0.bin"
INTRO_S = 1.0
PAUSE_S = 0.5
TRAIL_S = 1.3
SR = 24000


def parse_script(path):
    sentences = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("| B"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 4 and cells[0][0] == "B" and cells[0][1:].isdigit():
            sentences.append(cells[1])
    return sentences


def main():
    script_path, out_wav = sys.argv[1], sys.argv[2]
    sentences = parse_script(script_path)
    kokoro = Kokoro(MODEL, VOICES)
    silence = lambda sec: np.zeros(int(sec * SR), dtype=np.float32)
    parts = [silence(INTRO_S)]
    full = []
    for text in sentences:
        audio, _ = kokoro.create(text, voice="af_heart", speed=1.0, lang="en-us")
        seg = np.asarray(audio, dtype=np.float32)
        parts.append(seg)
        parts.append(silence(PAUSE_S))
        full.append(text)
    parts[-1] = silence(TRAIL_S)
    narration = np.concatenate(parts)
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    sf.write(out_wav, narration, SR)
    print(json.dumps({
        "sentences": len(sentences),
        "duration_s": round(len(narration) / SR, 6),
        "sample_rate": SR,
        "wav": out_wav,
        "full_text": " ".join(full),
        "engine": "kokoro_onnx_82m_cpu",
        "voice": "af_heart",
    }))


if __name__ == "__main__":
    main()
