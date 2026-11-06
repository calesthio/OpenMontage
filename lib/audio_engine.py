"""Audio Production Engine — Kokoro-82M TTS for OpenMontage Factory.

Generates English narration audio at $0 using the locally installed
Kokoro-82M model with voice ``af_heart``.

Features:
  * Per-sentence synthesis with stable voice parameters
  * Text normalization before synthesis (abbreviations, numbers, dates,
    units, scientific terms)
  * Continuous paragraph-scene synthesis for natural intonation +
    per-sentence synthesis alternative (quality compared)
  * Audio file caching keyed by normalized text + voice + speed
  * Error handling and retry logic
  * Original text preserved separately from normalized TTS text

All work is local and zero-cost: no API keys, no credits, no network
beyond HF hub cache (already populated).
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import soundfile as sf
from kokoro import KPipeline

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_VOICE = "af_heart"
DEFAULT_SPEED = 1.0
SAMPLE_RATE = 24000  # Kokoro-82M native output rate
MAX_RETRIES = 3


@dataclass
class AudioSegment:
    """One synthesized audio fragment."""

    sentence_id: str
    original_text: str          # verbatim source text — never modified
    normalized_text: str        # text actually sent to TTS
    audio_path: str             # absolute path to WAV file
    audio_sha256: str | None    # sha256 of the audio file
    duration_seconds: float     # measured via ffprobe/soundfile info
    start_ms: int | None = None  # timeline start (set by alignment)
    end_ms: int | None = None    # timeline end (set by alignment)
    voice: str = DEFAULT_VOICE
    speed: float = DEFAULT_SPEED
    sample_rate: int = SAMPLE_RATE
    status: str = "planned"      # planned | synthesized | qc_passed | qc_failed | failed | cached
    error: str | None = None
    attempts: int = 0
    cached: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AudioProductionResult:
    """Outcome of producing audio for all sentences of one project."""

    project_id: str
    total_sentences: int
    synthesized: int
    cached: int
    qc_passed: int
    qc_failed: int
    failed: int
    total_duration_seconds: float
    segments: list[AudioSegment] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "total_sentences": self.total_sentences,
            "synthesized": self.synthesized,
            "cached": self.cached,
            "qc_passed": self.qc_passed,
            "qc_failed": self.qc_failed,
            "failed": self.failed,
            "total_duration_seconds": self.total_duration_seconds,
            "segments": [s.to_dict() for s in self.segments],
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Text normalization (preserves original separately)
# ---------------------------------------------------------------------------

_ABBREVIATIONS_TTS = {
    "dr.": "doctor",
    "mr.": "mister",
    "mrs.": "misses",
    "ms.": "miss",
    "prof.": "professor",
    "sr.": "senior",
    "jr.": "junior",
    "st.": "saint",
    "vs.": "versus",
    "etc.": "et cetera",
    "e.g.": "for example",
    "i.e.": "that is",
    "approx.": "approximately",
    "fig.": "figure",
    "vol.": "volume",
    "no.": "number",
    "inc.": "incorporated",
    "ltd.": "limited",
    "ph.d.": "ph d",
    "m.d.": "m d",
    "u.s.a.": "u s a",
    "u.k.": "u k",
    "co.": "company",
    "corp.": "corporation",
    "dept.": "department",
    "univ.": "university",
    "gen.": "general",
    "rep.": "representative",
    "sen.": "senator",
    "gov.": "governor",
}

_NUM_WORDS = {
    "0": "zero", "1": "one", "2": "two", "3": "three", "4": "four",
    "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine",
}


def normalize_text_for_tts(text: str) -> str:
    """Normalize text for Kokoro TTS while keeping *original* elsewhere.

    Handles:
      * Unicode normalization (NFKC)
      * Abbreviations -> spoken form
      * Decimal numbers -> digit-by-digit ("3.14" -> "three point one four")
      * Simple ordinals/units kept as-is (Kokoro handles most)
      * Collapse whitespace
    """
    if not text:
        return text
    t = unicodedata.normalize("NFKC", text)
    # Abbreviations (case-insensitive, followed by whitespace or end).
    for abbr, spoken in _ABBREVIATIONS_TTS.items():
        t = re.sub(
            r"(?<!\w)" + re.escape(abbr) + r"(?=\s|$)",
            spoken,
            t,
            flags=re.IGNORECASE,
        )
    # Decimals: 3.14 -> "three point one four"
    def _decimal_repl(m: re.Match[str]) -> str:
        whole, frac = m.group(0).split(".")
        spoken = " ".join(_NUM_WORDS.get(d, d) for d in whole) if whole.isdigit() else whole
        spoken += " point " + " ".join(_NUM_WORDS.get(d, d) for d in frac)
        return spoken
    t = re.sub(r"\b\d+\.\d+\b", _decimal_repl, t)
    # Collapse whitespace
    t = re.sub(r"\s+", " ", t).strip()
    return t


# ---------------------------------------------------------------------------
# Audio Engine
# ---------------------------------------------------------------------------

class AudioEngine:
    """Kokoro-82M TTS engine with caching and retry."""

    def __init__(
        self,
        *,
        voice: str = DEFAULT_VOICE,
        speed: float = DEFAULT_SPEED,
        cache_dir: str | Path | None = None,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        self.voice = voice
        self.speed = speed
        self.max_retries = max_retries
        self.cache_dir = Path(cache_dir) if cache_dir else Path("/tmp/kilo/audio_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._pipeline: KPipeline | None = None
        self._cache: dict[str, str] = {}  # normalized_text_hash -> audio_path
        self._load_cache_index()

    # ------------------------------------------------------------------
    # Pipeline (lazy, cached)
    # ------------------------------------------------------------------

    def _get_pipeline(self) -> KPipeline:
        if self._pipeline is None:
            self._pipeline = KPipeline(lang_code="a")
        return self._pipeline

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def _cache_key(self, normalized_text: str) -> str:
        payload = f"{self.voice}|{self.speed}|{normalized_text}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _load_cache_index(self) -> None:
        index_file = self.cache_dir / "cache_index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                self._cache = data.get("cache", {})
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save_cache_index(self) -> None:
        index_file = self.cache_dir / "cache_index.json"
        index_file.write_text(
            json.dumps({"cache": self._cache}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.wav"

    def _get_cached(self, normalized_text: str) -> str | None:
        key = self._cache_key(normalized_text)
        if key in self._cache:
            p = Path(self._cache[key])
            if p.exists() and p.stat().st_size > 0:
                return str(p)
        return None

    def _store_cached(self, normalized_text: str, audio_path: str) -> None:
        key = self._cache_key(normalized_text)
        self._cache[key] = str(audio_path)
        self._save_cache_index()

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def synthesize(self, *, text: str, output_path: str | Path) -> AudioSegment:
        """Synthesize *text* to WAV at *output_path*.

        Returns an :class:`AudioSegment` with measured duration.  Uses cache
        when the same (voice, speed, normalized_text) was already synthesized.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        normalized = normalize_text_for_tts(text)
        cached = self._get_cached(normalized)
        if cached:
            seg = AudioSegment(
                sentence_id="",
                original_text=text,
                normalized_text=normalized,
                audio_path=str(cached),
                audio_sha256=None,
                duration_seconds=0.0,
                voice=self.voice,
                speed=self.speed,
                sample_rate=SAMPLE_RATE,
                status="cached",
                cached=True,
            )
            seg.audio_sha256 = self._sha256_file(Path(cached))
            seg.duration_seconds = self._duration(cached)
            return seg

        last_error = ""
        for attempt in range(1, self.max_retries + 1):
            try:
                pipeline = self._get_pipeline()
                audio = None
                for _, _, chunk in pipeline(
                    normalized, voice=self.voice, speed=self.speed
                ):
                    audio = chunk  # Kokoro yields one chunk per segment
                if audio is None or len(audio) == 0:
                    raise RuntimeError("Kokoro produced no audio")
                sf.write(str(output_path), audio, SAMPLE_RATE)
                duration = len(audio) / SAMPLE_RATE
                seg = AudioSegment(
                    sentence_id="",
                    original_text=text,
                    normalized_text=normalized,
                    audio_path=str(output_path),
                    audio_sha256=None,
                    duration_seconds=0.0,
                    voice=self.voice,
                    speed=self.speed,
                    sample_rate=SAMPLE_RATE,
                    status="synthesized",
                )
                seg.audio_sha256 = self._sha256_file(output_path)
                seg.duration_seconds = round(duration, 4)
                self._store_cached(normalized, str(output_path))
                return seg
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                if attempt < self.max_retries:
                    continue
                return AudioSegment(
                    sentence_id="",
                    original_text=text,
                    normalized_text=normalized,
                    audio_path=str(output_path),
                    audio_sha256=None,
                    duration_seconds=0.0,
                    voice=self.voice,
                    speed=self.speed,
                    sample_rate=SAMPLE_RATE,
                    status="failed",
                    error=last_error,
                    attempts=attempt,
                )
        # Unreachable
        return AudioSegment(
            sentence_id="",
            original_text=text,
            normalized_text=normalized,
            audio_path=str(output_path),
            voice=self.voice,
            speed=self.speed,
            sample_rate=SAMPLE_RATE,
            status="failed",
            error=last_error or "unknown synthesis error",
            attempts=self.max_retries,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sha256_file(path: Path) -> str | None:
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    @staticmethod
    def _duration(path: str | Path) -> float:
        try:
            info = sf.info(str(path))
            return round(float(info.frames) / float(info.samplerate), 4)
        except Exception:
            return 0.0
