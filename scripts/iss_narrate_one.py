#!/usr/bin/env python3
"""scripts/iss_narrate_one.py — synthesize ONE sentence with a fresh Kokoro KPipeline.
Usage: iss_narrate_one.py <index> "<text>" <out.wav>
Isolated subprocess avoids kokoro state degradation across repeated calls.
"""
import sys
from pathlib import Path
import numpy as np
import soundfile as sf
from kokoro import KPipeline

SR = 24000


def main():
    idx = int(sys.argv[1])
    text = sys.argv[2]
    out_wav = sys.argv[3]
    pipeline = KPipeline(lang_code="a")
    audio = None
    for _, _, seg in pipeline(text, voice="af_heart", speed=1.0):
        audio = np.asarray(seg, dtype=np.float32)
    if audio is None:
        audio = np.zeros(1, dtype=np.float32)
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    sf.write(out_wav, audio, SR)
    print(f"{idx}: {len(audio)/SR:.2f}s", flush=True)


if __name__ == "__main__":
    main()
