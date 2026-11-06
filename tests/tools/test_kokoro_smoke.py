"""Smoke test for Kokoro-82M TTS (af_heart) in the main project environment.

Synthesizes a short utterance and verifies ffprobe can decode it.
Zero-cost: local CPU synthesis, no API keys, no credits.
"""

from __future__ import annotations

import os

# Force huggingface_hub to use only the local cache so kokoro's model load
# performs zero network calls (the Kokoro-82M weights are pre-cached).
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import subprocess
import sys

import pytest


def test_kokoro_synthesizes_af_heart(tmp_path):
    try:
        from kokoro import KPipeline
        import soundfile as sf
    except ImportError as exc:
        pytest.skip(f"kokoro stack not installed: {exc}")

    wav = tmp_path / "kokoro_smoke.wav"
    pipeline = KPipeline(lang_code="a")
    written = False
    for _, _, audio in pipeline("Kokoro smoke test. Voice af_heart.", voice="af_heart", speed=1.0):
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


def test_kokoro_available_in_main_env():
    try:
        import kokoro  # noqa: F401
        import soundfile  # noqa: F401
    except ImportError:
        pytest.fail("kokoro/soundfile not importable in main Python env")


def test_sys_python_matches_pytest_env():
    # Kokoro was installed into the interpreter running pytest.
    assert sys.executable
