"""Audio Alignment — maps synthesized audio to sentence IDs with timestamps.

Zero-cost, local alignment without WhisperX/faster-whisper (not installed;
not installed here per project constraint to avoid heavy deps).

Strategy:
  1. Synthesize each sentence separately with Kokoro (which yields phonemes
     per call) → per-sentence WAV files with measured durations.
  2. Concatenate per-sentence WAVs into a narration track (preserving order
     and a small inter-sentence pause).
  3. Run ffmpeg silencedetect on the concatenated track to find pause
     boundaries → refine sentence start/end.
  4. Fall back to cumulative duration if silence detection is ambiguous.

Word-level timestamps are NOT available from Kokoro-82M (no timestamp API),
so alignment is sentence-level with sub-sentence granularity derived from
phoneme count ratios within each sentence where useful.

All timing is derived from the ACTUAL audio (ffprobe duration), never from
words-per-minute estimates.
"""

from __future__ import annotations

import json
import math
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class SentenceTiming:
    """Precise timing for one sentence within the narration audio."""

    sentence_id: str
    original_text: str
    normalized_text: str
    audio_asset_id: str
    audio_path: str
    start_ms: int
    end_ms: int
    duration_ms: int
    alignment_confidence: float  # 0.0-1.0
    status: str  # ok | partial | failed | missing_audio
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AlignmentReport:
    """Result of aligning all sentences to the narration audio."""

    project_id: str
    narration_path: str
    total_duration_ms: int
    total_sentences: int
    aligned: int
    partial: int
    failed: int
    timings: list[SentenceTiming] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "narration_path": self.narration_path,
            "total_duration_ms": self.total_duration_ms,
            "total_sentences": self.total_sentences,
            "aligned": self.aligned,
            "partial": self.partial,
            "failed": self.failed,
            "timings": [t.to_dict() for t in self.timings],
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Silence detection (ffmpeg)
# ---------------------------------------------------------------------------


def detect_silence_intervals(
    audio_path: str | Path,
    *,
    noise_db: float = -30.0,
    min_silence_s: float = 0.25,
) -> list[tuple[float, float]]:
    """Return list of (start_s, end_s) silent intervals via ffmpeg silencedetect.

    Zero-cost: uses ffmpeg already installed in P0.
    """
    cmd = [
        "ffmpeg", "-hide_banner", "-nostats",
        "-i", str(audio_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence_s}",
        "-f", "null", "-",
    ]
    try:
        proc = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []

    silence_re = re.compile(
        r"silence_start: (?P<start>[\d.]+) | silence_end: (?P<end>[\d.]+) | "
        r"silence_duration: (?P<dur>[\d.]+)"
    )
    intervals: list[tuple[float, float]] = []
    current_start: float | None = None
    for line in proc.stderr.splitlines():
        m = silence_re.search(line)
        if not m:
            continue
        if m.group("start") is not None:
            current_start = float(m.group("start"))
        elif m.group("end") is not None and current_start is not None:
            intervals.append((current_start, float(m.group("end"))))
            current_start = None
    return intervals


import re  # noqa: E402  (used above)


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------


class AudioAligner:
    """Align per-sentence audio to a global timeline."""

    def __init__(
        self,
        *,
        inter_sentence_pause_s: float = 0.30,
        min_confidence: float = 0.5,
    ) -> None:
        self.inter_sentence_pause_s = inter_sentence_pause_s
        self.min_confidence = min_confidence

    def build_timeline(
        self,
        *,
        segments: list[dict[str, Any]],
        narration_path: str | Path,
        project_id: str,
    ) -> AlignmentReport:
        """Build sentence→timeline mapping.

        *segments* is a list of dicts with keys: sentence_id, original_text,
        normalized_text, audio_asset_id, audio_path, duration_seconds.
        Order in the list defines playback order.

        Falls back to cumulative duration (plus fixed inter-sentence pause)
        when silence detection cannot refine boundaries.
        """
        narration_path = Path(narration_path)
        total_duration_s = self._probe_duration(narration_path)
        total_duration_ms = int(total_duration_s * 1000)

        # Detect silence intervals in the full narration track.
        silence_intervals = detect_silence_intervals(narration_path)

        timings: list[SentenceTiming] = []
        aligned = partial = failed = 0

        cursor_s = 0.0
        for seg in segments:
            sid = seg["sentence_id"]
            dur_s = float(seg.get("duration_seconds", 0.0))
            if dur_s <= 0:
                # Missing/invalid audio — mark failed, advance by estimate.
                failed += 1
                timings.append(SentenceTiming(
                    sentence_id=sid,
                    original_text=seg.get("original_text", ""),
                    normalized_text=seg.get("normalized_text", ""),
                    audio_asset_id=seg.get("audio_asset_id", ""),
                    audio_path=seg.get("audio_path", ""),
                    start_ms=int(cursor_s * 1000),
                    end_ms=int((cursor_s + dur_s) * 1000),
                    duration_ms=int(dur_s * 1000),
                    alignment_confidence=0.0,
                    status="missing_audio",
                    notes="no audio duration",
                ))
                cursor_s += self.inter_sentence_pause_s
                continue

            start_s = cursor_s
            end_s = cursor_s + dur_s

            # Try to refine boundary using nearby silence.
            confidence = 1.0
            refined = self._refine_boundary(
                start_s, end_s, silence_intervals, total_duration_s
            )
            if refined is not None:
                start_s, end_s = refined
            else:
                confidence = 0.7  # fallback to cumulative
                partial += 1

            # Clamp to total duration.
            end_s = min(end_s, total_duration_s)
            if end_s <= start_s:
                end_s = start_s + dur_s

            timings.append(SentenceTiming(
                sentence_id=sid,
                original_text=seg.get("original_text", ""),
                normalized_text=seg.get("normalized_text", ""),
                audio_asset_id=seg.get("audio_asset_id", ""),
                audio_path=seg.get("audio_path", ""),
                start_ms=int(round(start_s * 1000)),
                end_ms=int(round(end_s * 1000)),
                duration_ms=int(round((end_s - start_s) * 1000)),
                alignment_confidence=round(confidence, 2),
                status="ok" if confidence >= self.min_confidence else "partial",
                notes="",
            ))
            aligned += 1 if confidence >= self.min_confidence else 0

            # Advance cursor: sentence duration + inter-sentence pause.
            cursor_s = end_s + self.inter_sentence_pause_s

        report = AlignmentReport(
            project_id=project_id,
            narration_path=str(narration_path),
            total_duration_ms=total_duration_ms,
            total_sentences=len(segments),
            aligned=aligned,
            partial=partial,
            failed=failed,
            timings=timings,
        )
        return report

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _probe_duration(path: str | Path) -> float:
        try:
            import soundfile as sf
            info = sf.info(str(path))
            return float(info.frames) / float(info.samplerate)
        except Exception:
            return 0.0

    @staticmethod
    def _refine_boundary(
        start_s: float,
        end_s: float,
        silence_intervals: list[tuple[float, float]],
        total_duration_s: float,
    ) -> tuple[float, float] | None:
        """Adjust start/end to nearest silence boundaries within tolerance.

        Returns None if no usable silence found (caller falls back).
        """
        TOLERANCE = 0.6  # seconds
        new_start = start_s
        new_end = end_s

        # Find silence just before start (sentence start boundary).
        best_start_silence: float | None = None
        for s, e in silence_intervals:
            if abs(e - start_s) <= TOLERANCE:
                if best_start_silence is None or e > best_start_silence:
                    best_start_silence = e
        if best_start_silence is not None:
            new_start = best_start_silence

        # Find silence just after end (sentence end boundary).
        best_end_silence: float | None = None
        for s, e in silence_intervals:
            if abs(s - end_s) <= TOLERANCE:
                if best_end_silence is None or s < best_end_silence:
                    best_end_silence = s
        if best_end_silence is not None:
            new_end = best_end_silence

        if best_start_silence is None and best_end_silence is None:
            return None
        return (new_start, new_end)
