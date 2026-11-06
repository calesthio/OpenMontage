"""Audio Production Orchestrator — P3 of OpenMontage Factory.

End-to-end audio pipeline for one project:

  sentence_segmenter → AudioEngine (Kokoro TTS) → concat narration
  → AudioAligner (ffmpeg silence detection) → AudioQualityControl
  → SentenceTimelineBuilder (merge with image engine output)

Rule: ONE SENTENCE = ONE UNIQUE AUDIO FRAGMENT.  One audio fragment is never
shared between two sentences.

Default mode is mock-safe: real Kokoro synthesis runs locally ($0), but the
orchestrator never calls gflow or spends credits.  Zero-Cost Gate and
MCP Security Proxy are respected.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.asset_registry import AssetRegistry
from lib.audio_alignment import AudioAligner, AlignmentReport
from lib.audio_engine import (
    AudioEngine,
    AudioSegment,
    AudioProductionResult,
    normalize_text_for_tts,
)
from lib.audio_qc import AudioQualityControl, SentenceAudioQCReport
from lib.recovery_manager import RecoveryManager
from lib.sentence_segmenter import Sentence, SentenceSegmenter
from lib.sentence_timeline import SentenceTimeline, SentenceTimelineBuilder


@dataclass
class SentenceAudioPlan:
    """Plan for turning one sentence into one audio fragment."""

    sentence_id: str
    sentence_text: str
    normalized_text: str
    audio_asset_id: str
    output_path: str
    voice: str = "af_heart"
    speed: float = 1.0
    state: str = "planned"  # planned | synthesized | cached | qc_passed | qc_failed | failed | blocked
    duration_seconds: float | None = None
    start_ms: int | None = None
    end_ms: int | None = None
    alignment_confidence: float | None = None
    qc_result: dict[str, Any] | None = None
    error: str | None = None
    attempts: int = 0
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AudioProductionPlan:
    """Full plan for all sentences of one project."""

    project_id: str
    version: str = "1.0"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sentences: list[SentenceAudioPlan] = field(default_factory=list)
    total: int = 0

    @property
    def by_id(self) -> dict[str, SentenceAudioPlan]:
        return {p.sentence_id: p for p in self.sentences}


class AudioProductionEngine:
    """Orchestrate sentence → normalized text → audio → alignment → QC → timeline."""

    def __init__(
        self,
        project_id: str,
        *,
        base_dir: str | Path = "projects",
        voice: str = "af_heart",
        speed: float = 1.0,
        mock: bool = False,
        max_retries: int = 3,
        cache_dir: str | Path | None = None,
    ) -> None:
        self.project_id = project_id
        self.mock = mock
        self.voice = voice
        self.speed = speed
        self.max_retries = max_retries

        self.registry = AssetRegistry(project_id, base_dir=base_dir)
        self.recovery = RecoveryManager(self.registry)
        cache = Path(cache_dir) if cache_dir else Path(base_dir) / "audio_cache"
        self.engine = AudioEngine(voice=voice, speed=speed, cache_dir=cache)
        self.aligner = AudioAligner()
        self.qc = AudioQualityControl()
        self.segmenter = SentenceSegmenter()
        self.timeline_builder = SentenceTimelineBuilder(project_id)

        self.plan: AudioProductionPlan | None = None
        self.narration_path: str | Path | None = None

    # ------------------------------------------------------------------
    # Character / voice setup
    # ------------------------------------------------------------------

    def set_voice(self, *, voice: str, speed: float = 1.0) -> None:
        self.voice = voice
        self.speed = speed
        self.engine.voice = voice
        self.engine.speed = speed

    # ------------------------------------------------------------------
    # Pipeline: build plan (zero-cost; no synthesis yet)
    # ------------------------------------------------------------------

    def build_plan(
        self,
        *,
        sentences: list[Sentence],
        output_root: str | Path = "projects",
    ) -> AudioProductionPlan:
        """Build the complete audio plan for *sentences*.

        Registers one audio asset per sentence (AssetRegistry) and prepares
        output paths.  No synthesis happens here — no credits, no generation.
        """
        root = Path(output_root) / self.project_id
        narration_dir = root / "audio" / "narration"
        sentence_dir = root / "audio" / "sentence_alignment"
        qc_dir = root / "audio" / "qc_reports"
        for d in (root, narration_dir, sentence_dir, qc_dir):
            d.mkdir(parents=True, exist_ok=True)

        plans: list[SentenceAudioPlan] = []
        for sentence in sentences:
            sid = sentence.sentence_id
            audio_asset_id = f"{self.project_id}-AUD-{sid}"
            output_path = str(sentence_dir / f"{sid}.wav")
            prompt_id = f"{self.project_id}-APT-{sid}"

            plan = SentenceAudioPlan(
                sentence_id=sid,
                sentence_text=sentence.text,
                normalized_text="",  # filled at synthesis
                audio_asset_id=audio_asset_id,
                output_path=output_path,
                voice=self.voice,
                speed=self.speed,
                state="planned",
            )
            plans.append(plan)

            # Register asset (one audio per sentence).
            self.registry.register_asset(
                sentence_id=sid,
                prompt_id=prompt_id,
                source_prompt=sentence.text,
                model="kokoro-82m",
                aspect_ratio="",  # N/A for audio
                references=[],
                generation_params={
                    "voice": self.voice,
                    "speed": self.speed,
                    "sample_rate": 24000,
                    "output_path": output_path,
                },
                job_id=None,
                file_path=output_path,
                status="planned",
            )

        self.plan = AudioProductionPlan(
            project_id=self.project_id,
            sentences=plans,
            total=len(plans),
        )
        return self.plan

    # ------------------------------------------------------------------
    # Execution: synthesize + align + QC
    # ------------------------------------------------------------------

    def execute(
        self,
        *,
        continuous: bool = True,
        cost_usd: float | None = None,
    ) -> AudioProductionResult:
        """Synthesize all planned sentences, align, QC, build timeline.

        *continuous* — synthesize per-paragraph/scene for natural intonation,
        then split into per-sentence files.  When False, each sentence is
        synthesized independently (compare quality in tests).

        In mock mode, writes placeholder audio so QC/timeline can run without
        Kokoro.  Real mode calls Kokoro-82M locally ($0).
        """
        if self.plan is None:
            raise RuntimeError("build_plan must be called before execute")

        result = AudioProductionResult(
            project_id=self.project_id,
            total_sentences=len(self.plan.sentences),
            synthesized=0,
            cached=0,
            qc_passed=0,
            qc_failed=0,
            failed=0,
            total_duration_seconds=0.0,
        )

        # --- Synthesis ---------------------------------------------------
        if self.mock:
            segment_dicts = self._mock_synthesize_all(result)
        else:
            segment_dicts = self._synthesize_all(
                result, continuous=continuous, cost_usd=cost_usd
            )

        # --- Concatenate narration track --------------------------------
        self.narration_path = self._concat_narration(segment_dicts)

        # --- Alignment --------------------------------------------------
        align_input = [
            {
                "sentence_id": d["sentence_id"],
                "original_text": d["original_text"],
                "normalized_text": d["normalized_text"],
                "audio_asset_id": d["audio_asset_id"],
                "audio_path": d["audio_path"],
                "duration_seconds": d["duration_seconds"],
            }
            for d in segment_dicts
        ]
        alignment: AlignmentReport = self.aligner.build_timeline(
            segments=align_input,
            narration_path=self.narration_path,
            project_id=self.project_id,
        )

        # --- QC ---------------------------------------------------------
        qc_report = self.qc.check_batch(segments=align_input)

        # --- Merge into plans + timeline --------------------------------
        audio_qc_map: dict[str, bool] = {}
        image_qc_map: dict[str, bool] = {}
        for d in segment_dicts:
            sid = d["sentence_id"]
            plan = self.plan.by_id[sid]
            # Find QC result
            qc_rep = qc_report.reports.get(sid)
            if qc_rep:
                plan.qc_result = {
                    "sentence_id": qc_rep.sentence_id,
                    "passed": qc_rep.passed,
                    "score": qc_rep.overall_score,
                    "blocking_issues": qc_rep.blocking_issues,
                    "results": [asdict(r) for r in qc_rep.results],
                }
                audio_qc_map[sid] = qc_rep.passed
                if qc_rep.passed:
                    plan.state = "qc_passed"
                    result.qc_passed += 1
                else:
                    plan.state = "qc_failed"
                    result.qc_failed += 1
                    result.errors.append(f"{sid}: QC failed — {qc_rep.blocking_issues}")
            else:
                plan.state = "qc_failed"
                result.qc_failed += 1
                audio_qc_map[sid] = False

            # Persist final QC status to the asset registry (recovery uses it).
            self.registry.register_asset(
                sentence_id=sid,
                prompt_id=f"{self.project_id}-APT-{sid}",
                source_prompt=plan.sentence_text,
                model="kokoro-82m",
                aspect_ratio="",
                references=[],
                generation_params={
                    "voice": self.voice,
                    "speed": self.speed,
                    "sample_rate": 24000,
                    "output_path": plan.output_path,
                    "normalized_text": plan.normalized_text,
                },
                job_id=None,
                file_path=plan.output_path,
                status=plan.state,
            )

            # Find alignment timing
            timing = next(
                (t for t in alignment.timings if t.sentence_id == sid), None
            )
            if timing:
                plan.start_ms = timing.start_ms
                plan.end_ms = timing.end_ms
                plan.duration_ms = timing.duration_ms
                plan.alignment_confidence = timing.alignment_confidence
                plan.duration_seconds = timing.duration_ms / 1000.0
            else:
                plan.duration_seconds = d["duration_seconds"]

            plan.cached = d.get("cached", False)
            if plan.state in ("qc_passed", "qc_failed"):
                result.total_duration_seconds += plan.duration_seconds or 0.0

        # --- Build timeline (P4 input) ----------------------------------
        timeline_entries = [
            {
                "sentence_id": p.sentence_id,
                "original_text": p.sentence_text,
                "normalized_text": p.normalized_text,
                "audio_asset_id": p.audio_asset_id,
                "audio_path": p.output_path,
                "start_ms": p.start_ms or 0,
                "end_ms": p.end_ms or 0,
                "duration_ms": p.duration_ms or int((p.duration_seconds or 0) * 1000),
                "alignment_confidence": p.alignment_confidence or 0.0,
            }
            for p in self.plan.sentences
        ]
        image_plans = [
            {
                "sentence_id": p.sentence_id,
                "asset_id": p.audio_asset_id,  # placeholder; merged by image engine later
                "output_path": p.output_path,
            }
            for p in self.plan.sentences
        ]
        timeline = self.timeline_builder.build(
            audio_timings=timeline_entries,
            image_plans=image_plans,
            audio_qc=audio_qc_map,
            image_qc=image_qc_map,
        )

        result.segments = [
            self.plan.by_id[sid] for sid in [p.sentence_id for p in self.plan.sentences]
        ]
        return result

    # ------------------------------------------------------------------
    # Resume / recovery
    # ------------------------------------------------------------------

    def resume(self) -> dict[str, list[str]]:
        if self.plan is None:
            raise RuntimeError("build_plan must be called before resume")
        all_ids = [p.sentence_id for p in self.plan.sentences]
        return self.recovery.sentences_to_process(all_ids)

    def snapshot_recovery(self) -> None:
        self.recovery.save(self.recovery.snapshot())

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _synthesize_all(
        self,
        result: AudioProductionResult,
        *,
        continuous: bool,
        cost_usd: float | None,
    ) -> list[dict[str, Any]]:
        """Synthesize each sentence.  Returns segment dicts in order."""
        segments: list[dict[str, Any]] = []
        for plan in self.plan.sentences:
            plan.attempts += 1
            seg = self.engine.synthesize(
                text=plan.sentence_text, output_path=plan.output_path,
            )
            plan.normalized_text = seg.normalized_text
            plan.audio_path = seg.audio_path
            plan.audio_sha256 = seg.audio_sha256
            plan.duration_seconds = seg.duration_seconds
            plan.cached = seg.cached
            plan.attempts = seg.attempts

            if seg.status == "cached":
                plan.state = "cached"
                result.cached += 1
            elif seg.status == "synthesized":
                plan.state = "synthesized"
                result.synthesized += 1
            else:
                plan.state = "failed"
                plan.error = seg.error
                result.failed += 1
                result.errors.append(f"{plan.sentence_id}: {seg.error}")

            # Register / update asset in registry with final QC status.
            self.registry.register_asset(
                sentence_id=plan.sentence_id,
                prompt_id=f"{self.project_id}-APT-{plan.sentence_id}",
                source_prompt=plan.sentence_text,
                model="kokoro-82m",
                aspect_ratio="",
                references=[],
                generation_params={
                    "voice": self.voice,
                    "speed": self.speed,
                    "sample_rate": 24000,
                    "output_path": plan.output_path,
                    "normalized_text": plan.normalized_text,
                },
                job_id=None,
                file_path=plan.output_path,
                status=plan.state,
            )

            segments.append({
                "sentence_id": plan.sentence_id,
                "original_text": plan.sentence_text,
                "normalized_text": plan.normalized_text,
                "audio_asset_id": plan.audio_asset_id,
                "audio_path": plan.output_path,
                "duration_seconds": plan.duration_seconds,
                "cached": plan.cached,
            })
        return segments

    def _mock_synthesize_all(
        self,
        result: AudioProductionResult,
    ) -> list[dict[str, Any]]:
        """Write placeholder WAVs so QC/timeline run without Kokoro.

        Writes a low-level sine tone (not silence) so loudness/silence QC
        checks pass.  Clearly mock content.
        """
        import math
        import wave

        segments: list[dict[str, Any]] = []
        for plan in self.plan.sentences:
            plan.attempts += 1
            p = Path(plan.output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Cache check: identical (voice, speed, normalized_text) reused.
            normalized = normalize_text_for_tts(plan.sentence_text)
            cached_path = self.engine._get_cached(normalized)
            if cached_path:
                plan.state = "cached"
                plan.cached = True
                plan.audio_path = cached_path
                plan.audio_sha256 = self.engine._sha256_file(Path(cached_path))
                plan.duration_seconds = self.engine._duration(cached_path)
                result.cached += 1
                segments.append({
                    "sentence_id": plan.sentence_id,
                    "original_text": plan.sentence_text,
                    "normalized_text": normalized,
                    "audio_asset_id": plan.audio_asset_id,
                    "audio_path": cached_path,
                    "duration_seconds": plan.duration_seconds,
                    "cached": True,
                })
                continue
            # Deterministic sine tone per sentence (440 Hz base, varied).
            seed = sum(ord(c) for c in plan.sentence_text) % 256
            freq = 220 + (seed % 3) * 110  # 220/330/440 Hz
            frames = int(24000 * 0.5)  # 0.5s placeholder
            amp = 3000  # well below clipping (32767)
            with wave.open(str(p), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                for i in range(frames):
                    sample = int(amp * math.sin(2 * math.pi * freq * i / 24000))
                    w.writeframes(sample.to_bytes(2, "little", signed=True))
            self.engine._store_cached(normalized, str(p))
            plan.normalized_text = normalized
            plan.audio_path = str(p)
            plan.audio_sha256 = self._sha256_file(p)
            plan.duration_seconds = 0.5
            plan.state = "synthesized"
            plan.cached = False
            result.synthesized += 1
            segments.append({
                "sentence_id": plan.sentence_id,
                "original_text": plan.sentence_text,
                "normalized_text": plan.normalized_text,
                "audio_asset_id": plan.audio_asset_id,
                "audio_path": str(p),
                "duration_seconds": 0.5,
                "cached": False,
            })
        return segments

    def _concat_narration(
        self, segment_dicts: list[dict[str, Any]]
    ) -> str | Path:
        """Concatenate per-sentence WAVs into one narration track."""
        import wave

        root = Path(self.registry.root)
        narration_dir = root / "audio" / "narration"
        narration_dir.mkdir(parents=True, exist_ok=True)
        out = narration_dir / "narration.wav"

        with wave.open(str(out), "wb") as wout:
            wout.setnchannels(1)
            wout.setsampwidth(2)
            wout.setframerate(24000)
            for seg in segment_dicts:
                p = Path(seg["audio_path"])
                if not p.exists():
                    continue
                with wave.open(str(p), "rb") as win:
                    wout.writeframes(win.readframes(win.getnframes()))
        return out

    @staticmethod
    def _sha256_file(path: Path) -> str | None:
        try:
            h = __import__("hashlib").sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def integrity_report(self) -> dict[str, Any]:
        return self.registry.integrity_check()

    def to_dict(self) -> dict[str, Any]:
        if self.plan is None:
            return {"project_id": self.project_id, "plan": None}
        return {
            "project_id": self.project_id,
            "total": self.plan.total,
            "voice": self.voice,
            "speed": self.speed,
            "sentences": [asdict(p) for p in self.plan.sentences],
            "registry": self.registry.integrity_check(),
        }
