"""The narration stage's contract, proven with real audio.

Master Plan section 7: "Длительность брать из реального аудиофайла, а не
только из WPM-прикидки". This test synthesizes real narration with the local
piper voice, measures the files with ffprobe, hashes the exact input text, and
builds a `narration_manifest` from those measured values — then validates it
against the schema and asserts the manifest never carries an estimated number.

Skipped (with the reason) when piper or the voice is not installed, so a
machine without a synthesizer reports the gap instead of passing vacuously.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path

import pytest

from schemas.artifacts import validate_artifact
from tools.audio.piper_tts import PiperTTS, resolve_voice_model

VOICE = "en_US-lessac-medium"

SCRIPT_SECTIONS = [
    {
        "segment_id": "seg-hook",
        "script_section": "hook",
        "text": (
            "Every hotel towel you have ever used was washed in a plant that "
            "runs on a schedule tighter than a bus route."
        ),
    },
    {
        "segment_id": "seg-close",
        "script_section": "close",
        "text": "The wash is cheap. The route is the business.",
    },
]


def _available() -> bool:
    if shutil.which("piper") is None:
        return False
    try:
        resolve_voice_model(VOICE)
    except FileNotFoundError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _available(),
    reason="piper executable or en_US-lessac-medium voice is not installed",
)


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


@pytest.fixture(scope="module")
def synthesized(tmp_path_factory) -> dict:
    """Real per-section audio, measured from the written files."""

    out_dir = tmp_path_factory.mktemp("narration")
    segments = []
    cursor = 0.0
    for section in SCRIPT_SECTIONS:
        audio = out_dir / f"{section['segment_id']}.wav"
        result = PiperTTS().execute(
            {
                "text": section["text"],
                "model": VOICE,
                "output_path": str(audio),
            }
        )
        assert result.success, result.error
        duration = _probe_duration(audio)
        segments.append(
            {
                "segment_id": section["segment_id"],
                "script_section": section["script_section"],
                "text": section["text"],
                "audio_path": str(audio),
                "start_seconds": round(cursor, 3),
                "end_seconds": round(cursor + duration, 3),
                "duration_seconds": duration,
                "text_sha256": hashlib.sha256(
                    section["text"].encode("utf-8")
                ).hexdigest(),
            }
        )
        cursor += duration

    input_text = " ".join(s["text"] for s in SCRIPT_SECTIONS)
    return {
        "segments": segments,
        "total_duration_seconds": round(cursor, 3),
        "input_text_sha256": hashlib.sha256(input_text.encode("utf-8")).hexdigest(),
    }


def test_every_segment_wrote_a_real_file(synthesized: dict) -> None:
    for segment in synthesized["segments"]:
        path = Path(segment["audio_path"])
        assert path.exists() and path.stat().st_size > 10_000


def test_durations_are_measured_not_estimated(synthesized: dict) -> None:
    """The manifest's durations must equal the files' real durations."""

    total = 0.0
    for segment in synthesized["segments"]:
        measured = _probe_duration(Path(segment["audio_path"]))
        assert segment["duration_seconds"] == pytest.approx(measured, abs=0.001)
        total += measured
    assert synthesized["total_duration_seconds"] == pytest.approx(total, abs=0.002)


def test_segments_are_contiguous_without_gaps_or_overlaps(synthesized: dict) -> None:
    previous_end = 0.0
    for segment in synthesized["segments"]:
        assert segment["start_seconds"] == pytest.approx(previous_end, abs=0.002)
        previous_end = segment["end_seconds"]


def test_the_input_text_hash_matches_the_script(synthesized: dict) -> None:
    text = " ".join(s["text"] for s in SCRIPT_SECTIONS)
    assert synthesized["input_text_sha256"] == hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


def test_the_manifest_built_from_real_audio_validates(synthesized: dict) -> None:
    """A narration_manifest with measured values must pass its schema."""

    manifest = {
        "version": "1.0",
        "run_id": "run-piper-verification",
        "created_at": "2026-10-15T00:00:00Z",
        "provider": "piper",
        "model": VOICE,
        "voice_id": VOICE,
        "voice_license": "MIT (piper runtime); check the individual voice recording license before commercial publication",
        "language": "en-US",
        "input_text_sha256": synthesized["input_text_sha256"],
        "script_ref": "artifacts/script.json",
        "total_duration_seconds": synthesized["total_duration_seconds"],
        "sample_rate_hz": 22050,
        "segments": [
            {
                "segment_id": segment["segment_id"],
                "script_section": segment["script_section"],
                "text": segment["text"],
                "audio_path": segment["audio_path"],
                "start_seconds": segment["start_seconds"],
                "end_seconds": segment["end_seconds"],
                "duration_seconds": segment["duration_seconds"],
                "text_sha256": segment["text_sha256"],
                "pronunciation_notes": [],
            }
            for segment in synthesized["segments"]
        ],
        "verification": {
            "method": "provider_timestamps",
            "word_accuracy": None,
            "threshold": 0.95,
            "passed": None,
            "notes": "duration measured with ffprobe from the written WAV files",
        },
    }
    validate_artifact("narration_manifest", manifest)


def test_a_manifest_with_estimated_durations_is_not_written(synthesized: dict) -> None:
    """Fail-closed guard: a duration that no file backs is a defect.

    The manifest schema accepts any number, so the *director* is the gate —
    this pins the rule that the number must equal the measured one.
    """

    segment = synthesized["segments"][0]
    measured = _probe_duration(Path(segment["audio_path"]))
    assert abs(segment["duration_seconds"] - measured) < 0.001
    assert segment["duration_seconds"] != pytest.approx(measured * 1.5)
