"""Real Kokoro-82M TTS smoke test (local, zero-cost).

Synthesizes a short utterance with the installed Kokoro-82M model (voice
af_heart) and verifies ffprobe can decode it. No API keys, no credits,
no network beyond the already-cached HF weights.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Force huggingface_hub offline so kokoro uses the pre-cached weights only.
import os  # noqa: E402

os.environ.setdefault("HF_HUB_OFFLINE", "1")


def test_real_kokoro_synthesizes_af_heart(tmp_path):
    try:
        from kokoro import KPipeline
        import soundfile as sf
    except ImportError as exc:
        pytest.skip(f"kokoro stack not installed: {exc}")

    wav = tmp_path / "kokoro_real.wav"
    pipeline = KPipeline(lang_code="a")
    written = False
    for _, _, audio in pipeline(
        "Real Kokoro smoke test. Voice af heart, speaking clearly.",
        voice="af_heart",
        speed=1.0,
    ):
        sf.write(str(wav), audio, 24000)
        written = True
        break
    assert written, "kokoro produced no audio"
    assert wav.exists() and wav.stat().st_size > 0

    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(wav)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        timeout=30,
    )
    assert out.returncode == 0, out.stderr
    duration = float(out.stdout.strip())
    assert duration > 0


def test_real_kokoro_available_in_main_env():
    try:
        import kokoro  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        pytest.fail("kokoro/soundfile not importable in main Python env")


def test_normalize_scientific_terms():
    from lib.audio_engine import normalize_text_for_tts
    out = normalize_text_for_tts(
        "Dr. Smith measured 3.14 mRNA in the U.S.A. lab at 5 p.m."
    )
    low = out.lower()
    assert "doctor" in low
    assert "three point one four" in low
    assert "mrna" in low
    assert "u s a" in low
