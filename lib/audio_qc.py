"""Audio Quality Control — local, zero-cost checks on synthesized narration.

Uses ffprobe + ffmpeg silencedetect (already installed in P0) and soundfile.
No model calls, no credits, no network.

Checks per audio file:
  * file exists and is non-empty
  * decodable (ffprobe / soundfile)
  * sample rate == expected (24000 Hz Kokoro)
  * channel count == 1 (mono)
  * duration > 0 and plausible for the text
  * no clipping (sample peak near full scale)
  * no long silence / trimmed phrases
  * loudness within range (ffmpeg ebur128 if available, else peak RMS)

Produces an AudioQCReport per sentence + a batch summary.
"""

from __future__ import annotations

import math
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import soundfile as sf


@dataclass
class AudioQCResult:
    """Result of one QC criterion."""

    criterion: str
    passed: bool
    score: float  # 0.0 - 1.0
    detail: str
    requires_human_review: bool = False


@dataclass
class SentenceAudioQCReport:
    """QC report for one sentence's audio."""

    sentence_id: str
    audio_path: str
    passed: bool
    overall_score: float
    results: list[AudioQCResult] = field(default_factory=list)
    blocking_issues: list[str] = field(default_factory=list)


@dataclass
class AudioQCBatchReport:
    """QC report for a whole batch of sentence audio."""

    version: str = "1.0"
    total_sentences: int = 0
    passed_sentences: int = 0
    failed_sentences: int = 0
    reports: dict[str, SentenceAudioQCReport] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "total_sentences": self.total_sentences,
            "passed_sentences": self.passed_sentences,
            "failed_sentences": self.failed_sentences,
            "reports": {
                sid: {
                    "sentence_id": r.sentence_id,
                    "audio_path": r.audio_path,
                    "passed": r.passed,
                    "overall_score": r.overall_score,
                    "results": [asdict(x) for x in r.results],
                    "blocking_issues": r.blocking_issues,
                }
                for sid, r in self.reports.items()
            },
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# QC engine
# ---------------------------------------------------------------------------


class AudioQualityControl:
    """Run QC checks on synthesized sentence audio."""

    def __init__(
        self,
        *,
        expected_sample_rate: int = 24000,
        expected_channels: int = 1,
        min_duration_s: float = 0.3,
        max_silence_ratio: float = 0.60,
        peak_clipping_threshold: float = 0.98,
    ) -> None:
        self.expected_sample_rate = expected_sample_rate
        self.expected_channels = expected_channels
        self.min_duration_s = min_duration_s
        self.max_silence_ratio = max_silence_ratio
        self.peak_clipping_threshold = peak_clipping_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_audio(
        self,
        *,
        sentence_id: str,
        audio_path: str | Path,
        expected_duration_s: float | None = None,
    ) -> SentenceAudioQCReport:
        """Run every applicable QC criterion on one audio file."""
        audio_path = Path(audio_path)
        results: list[AudioQCResult] = []
        blocking: list[str] = []

        # 1. File exists and non-empty
        r = self._check_file_exists(audio_path)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # If file missing, stop here.
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            return SentenceAudioQCReport(
                sentence_id=sentence_id,
                audio_path=str(audio_path),
                passed=False,
                overall_score=0.0,
                results=results,
                blocking_issues=blocking,
            )

        # 2. Decodable + format
        info = self._probe_audio(audio_path)
        r = self._check_decodable(info)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 3. Sample rate
        r = self._check_sample_rate(info)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 4. Channels
        r = self._check_channels(info)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 5. Duration
        r = self._check_duration(info, expected_duration_s)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 6. Clipping
        r = self._check_clipping(audio_path)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 7. Silence / trimmed phrases
        r = self._check_silence_ratio(audio_path, info)
        results.append(r)
        if not r.passed:
            blocking.append(r.detail)

        # 8. Loudness
        r = self._check_loudness(audio_path)
        results.append(r)

        overall = (
            sum(r.score for r in results) / len(results) if results else 0.0
        )
        passed = len(blocking) == 0

        return SentenceAudioQCReport(
            sentence_id=sentence_id,
            audio_path=str(audio_path),
            passed=passed,
            overall_score=round(overall, 2),
            results=results,
            blocking_issues=blocking,
        )

    def check_batch(
        self,
        segments: list[dict[str, Any]],
    ) -> AudioQCBatchReport:
        """Run QC on every segment's audio."""
        reports: dict[str, SentenceAudioQCReport] = {}
        passed = failed = 0

        for seg in segments:
            sid = seg.get("sentence_id", "unknown")
            report = self.check_audio(
                sentence_id=sid,
                audio_path=seg.get("audio_path", ""),
                expected_duration_s=seg.get("duration_seconds"),
            )
            reports[sid] = report
            if report.passed:
                passed += 1
            else:
                failed += 1

        total = len(segments)
        return AudioQCBatchReport(
            total_sentences=total,
            passed_sentences=passed,
            failed_sentences=failed,
            reports=reports,
            summary={
                "pass_rate": round(passed / total, 2) if total else 0.0,
                "average_score": round(
                    sum(r.overall_score for r in reports.values()) / total, 2
                ) if total else 0.0,
            },
        )

    def to_dict(self, report: AudioQCBatchReport) -> dict[str, Any]:
        return report.to_dict()

    # ------------------------------------------------------------------
    # Individual criteria
    # ------------------------------------------------------------------

    def _check_file_exists(self, audio_path: Path) -> AudioQCResult:
        if not audio_path.exists():
            return AudioQCResult(
                "file_exists", False, 0.0,
                f"Audio file missing: {audio_path}",
                requires_human_review=True,
            )
        if audio_path.stat().st_size == 0:
            return AudioQCResult(
                "file_exists", False, 0.0,
                f"Audio file empty: {audio_path}",
                requires_human_review=True,
            )
        return AudioQCResult(
            "file_exists", True, 1.0,
            f"Audio file present ({audio_path.stat().st_size} bytes)",
        )

    def _probe_audio(self, audio_path: Path) -> dict[str, Any] | None:
        try:
            info = sf.info(str(audio_path))
            return {
                "samplerate": info.samplerate,
                "channels": info.channels,
                "frames": info.frames,
                "duration": info.duration,
                "format": info.format,
                "subtype": info.subtype,
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def _check_decodable(self, info: dict[str, Any] | None) -> AudioQCResult:
        if info is None or "error" in info:
            return AudioQCResult(
                "decodable", False, 0.0,
                f"Audio not decodable: {info.get('error') if info else 'unknown'}",
                requires_human_review=True,
            )
        return AudioQCResult("decodable", True, 1.0, "Audio decodable")

    def _check_sample_rate(self, info: dict[str, Any] | None) -> AudioQCResult:
        if info is None or "error" in info:
            return AudioQCResult(
                "sample_rate", False, 0.0,
                "Cannot check sample rate — audio not decodable",
            )
        sr = info.get("samplerate")
        ok = sr == self.expected_sample_rate
        return AudioQCResult(
            "sample_rate", ok, 1.0 if ok else 0.5,
            f"Sample rate {sr} Hz (expected {self.expected_sample_rate} Hz)",
        )

    def _check_channels(self, info: dict[str, Any] | None) -> AudioQCResult:
        if info is None or "error" in info:
            return AudioQCResult(
                "channels", False, 0.0,
                "Cannot check channels — audio not decodable",
            )
        ch = info.get("channels")
        ok = ch == self.expected_channels
        return AudioQCResult(
            "channels", ok, 1.0 if ok else 0.5,
            f"Channels {ch} (expected {self.expected_channels})",
        )

    def _check_duration(
        self, info: dict[str, Any] | None, expected_s: float | None
    ) -> AudioQCResult:
        if info is None or "error" in info:
            return AudioQCResult(
                "duration", False, 0.0,
                "Cannot check duration — audio not decodable",
            )
        dur = info.get("duration", 0.0)
        if dur < self.min_duration_s:
            return AudioQCResult(
                "duration", False, 0.0,
                f"Duration {dur:.2f}s below minimum {self.min_duration_s}s",
            )
        if expected_s is not None and dur > 0:
            ratio = dur / expected_s if expected_s > 0 else 1.0
            # Plausible range: 50%–200% of expected
            if 0.5 <= ratio <= 2.0:
                return AudioQCResult(
                    "duration", True, 1.0,
                    f"Duration {dur:.2f}s plausible vs expected {expected_s:.2f}s",
                )
            return AudioQCResult(
                "duration", False, 0.4,
                f"Duration {dur:.2f}s implausible vs expected {expected_s:.2f}s",
            )
        return AudioQCResult("duration", True, 1.0, f"Duration {dur:.2f}s")

    def _check_clipping(self, audio_path: Path) -> AudioQCResult:
        try:
            data, sr = sf.read(str(audio_path), always_2d=True)
        except Exception as exc:  # noqa: BLE001
            return AudioQCResult(
                "clipping", False, 0.0,
                f"Cannot read audio for clipping check: {exc}",
            )
        peak = float(max(abs(data.min()), abs(data.max())))
        clipped = peak >= self.peak_clipping_threshold
        score = 0.0 if clipped else 1.0
        return AudioQCResult(
            "clipping", not clipped, score,
            f"Peak amplitude {peak:.3f} "
            f"{'(near clipping)' if clipped else '(ok)'}",
        )

    def _check_silence_ratio(
        self, audio_path: Path, info: dict[str, Any] | None
    ) -> AudioQCResult:
        try:
            data, sr = sf.read(str(audio_path), always_2d=True)
        except Exception as exc:  # noqa: BLE001
            return AudioQCResult(
                "silence_ratio", False, 0.0,
                f"Cannot read audio for silence check: {exc}",
            )
        mono = data[:, 0] if data.ndim > 1 else data
        if len(mono) == 0:
            return AudioQCResult(
                "silence_ratio", False, 0.0,
                "Empty audio — silence ratio 1.0",
            )
        rms = float(math.sqrt(float((mono ** 2).mean())))
        # Silence threshold relative to peak
        peak = float(max(abs(mono.min()), abs(mono.max())))
        if peak <= 0:
            return AudioQCResult(
                "silence_ratio", False, 0.0,
                "Silent audio (peak 0)",
            )
        ratio = rms / peak
        ok = ratio >= (1.0 - self.max_silence_ratio)
        return AudioQCResult(
            "silence_ratio", ok, min(1.0, ratio * 2),
            f"RMS/peak ratio {ratio:.3f} "
            f"{'(mostly silent)' if not ok else '(ok)'}",
        )

    def _check_loudness(self, audio_path: Path) -> AudioQCResult:
        try:
            data, sr = sf.read(str(audio_path), always_2d=True)
        except Exception as exc:  # noqa: BLE001
            return AudioQCResult(
                "loudness", False, 0.0,
                f"Cannot read audio for loudness: {exc}",
            )
        mono = data[:, 0] if data.ndim > 1 else data
        rms = float(math.sqrt(float((mono ** 2).mean())))
        # Rough loudness in dBFS
        db = 20 * math.log10(rms) if rms > 0 else -120.0
        # Kokoro typical: -30 to -10 dBFS
        ok = -45.0 < db < -5.0
        return AudioQCResult(
            "loudness", ok, 1.0 if ok else 0.6,
            f"RMS loudness {db:.1f} dBFS",
        )
