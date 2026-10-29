"""Smart Trim — AI-powered <60s video trimmer at sentence boundaries.

Cuts long-form documentary footage to under 60 seconds for Shorts without
breaking voice mid-sentence. Uses Whisper word-level timestamps to find
sentence boundaries, then scores candidate windows to select the best
~55s narrative segment.

Designed specifically for BBC/documentary clips at risk of Content ID blocks
when they exceed ~58s.

Usage (standalone):
    python -m tools.video.smart_trim \\
        --input projects/cape-gannets-torpedo-divers/source.mp4 \\
        --output projects/cape-gannets-torpedo-divers/renders/trimmed_55s.mp4

Usage (from pipeline):
    from tools.video.smart_trim import SmartTrimmer
    trimmer = SmartTrimmer()
    result = trimmer.execute({
        "input_path": "path/to/source.mp4",
        "output_path": "path/to/trimmed.mp4",
        "target_seconds": 55,
        "max_seconds": 59,
    })
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ResumeSupport,
    ToolResult,
    ToolStability,
    ToolTier,
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Word:
    """A single word with precise timestamps."""
    text: str
    start: float
    end: float


@dataclass
class Sentence:
    """A sentence composed of words, with aggregate timing."""
    words: list[Word]
    text: str = ""
    start: float = 0.0
    end: float = 0.0
    duration: float = 0.0
    index: int = 0

    def __post_init__(self):
        if self.words:
            self.text = " ".join(w.text for w in self.words)
            self.start = self.words[0].start
            self.end = self.words[-1].end
            self.duration = self.end - self.start


@dataclass
class TrimWindow:
    """A candidate trim window: a contiguous slice of sentences."""
    sentences: list[Sentence]
    start: float = 0.0
    end: float = 0.0
    duration: float = 0.0
    score: float = 0.0
    text_preview: str = ""

    def __post_init__(self):
        if self.sentences:
            self.start = self.sentences[0].start
            self.end = self.sentences[-1].end
            self.duration = self.end - self.start
            self.text_preview = " ".join(s.text for s in self.sentences[:3]) + "..."


# ---------------------------------------------------------------------------
# Sentence boundary detection from Whisper words
# ---------------------------------------------------------------------------

# Sentence-ending punctuation
_SENTENCE_END_RE = re.compile(r'[.!?]+$')

# Minimum pause between words to force a sentence break even without punctuation
_PAUSE_THRESHOLD = 0.8  # seconds


def words_to_sentences(words: list[Word]) -> list[Sentence]:
    """Group words into sentences using punctuation and pause detection.

    Rules:
    1. If a word ends with sentence-ending punctuation (.!?), break here.
    2. If the gap between two words is > _PAUSE_THRESHOLD, break between them.
    3. Don't create sentences shorter than 2 words (merge short fragments forward).
    """
    if not words:
        return []

    sentences: list[Sentence] = []
    current_words: list[Word] = []

    for i, word in enumerate(words):
        current_words.append(word)

        is_sentence_end = bool(_SENTENCE_END_RE.search(word.text.strip()))
        has_long_pause = (
            i + 1 < len(words)
            and (words[i + 1].start - word.end) > _PAUSE_THRESHOLD
        )

        if is_sentence_end or has_long_pause:
            # Only break if we have at least 2 words (avoid single-word "sentences")
            if len(current_words) >= 2:
                sentences.append(Sentence(words=list(current_words)))
                current_words = []
            # else: keep accumulating

    # Flush remaining words
    if current_words:
        if sentences:
            # Merge short trailing fragment into the last sentence
            sentences[-1].words.extend(current_words)
            sentences[-1].__post_init__()
        else:
            sentences.append(Sentence(words=current_words))

    # Re-index
    for i, s in enumerate(sentences):
        s.index = i

    return sentences


# ---------------------------------------------------------------------------
# Window scoring
# ---------------------------------------------------------------------------

# Keywords that indicate high-value narrative moments in wildlife footage
_DRAMATIC_KEYWORDS = {
    "hunt", "hunting", "attack", "attacks", "strike", "strikes",
    "predator", "predators", "prey", "survive", "survival",
    "escape", "escapes", "chase", "chasing", "catch", "catches",
    "dive", "dives", "diving", "plunge", "torpedo",
    "speed", "fast", "fastest", "incredible", "amazing",
    "danger", "dangerous", "deadly", "kill", "killing",
    "fight", "fighting", "battle", "struggle",
    "suddenly", "moment", "crucial", "critical", "vital",
    "must", "only", "chance", "impossible", "extraordinary",
    "spectacular", "remarkable", "astonishing",
}

# Words that indicate story setup / context
_SETUP_KEYWORDS = {
    "here", "every", "each", "year", "day", "morning", "dawn",
    "ocean", "sea", "waters", "deep", "surface",
    "thousands", "millions", "hundred", "colony", "group", "flock",
    "gather", "gathers", "arrive", "arrives", "begin", "begins",
}

# Words that indicate resolution / conclusion
_RESOLUTION_KEYWORDS = {
    "finally", "survive", "survived", "escape", "escaped",
    "success", "successful", "safe", "safely", "enough",
    "but", "however", "yet", "still", "against",
    "triumph", "return", "returns", "complete",
}


def score_sentence(sentence: Sentence) -> float:
    """Score a sentence for narrative importance (0.0 – 10.0)."""
    words_lower = {w.text.strip().lower().rstrip(".,!?;:") for w in sentence.words}
    score = 1.0  # base score

    # Dramatic content bonus
    dramatic_hits = words_lower & _DRAMATIC_KEYWORDS
    score += len(dramatic_hits) * 1.5

    # Length bonus (longer sentences tend to carry more narrative weight)
    word_count = len(sentence.words)
    if word_count >= 8:
        score += 1.0
    elif word_count >= 5:
        score += 0.5

    # Duration penalty for very short sentences (likely incomplete)
    if sentence.duration < 1.0:
        score *= 0.5

    return min(score, 10.0)


def score_window(window: TrimWindow, all_sentences: list[Sentence]) -> float:
    """Score a candidate trim window for narrative quality.

    Rewards:
    - High aggregate sentence importance
    - Presence of setup (beginning) + climax (middle) + resolution (end)
    - Clean opening (starts at or near a natural break)
    - Duration close to target

    Penalties:
    - Starting mid-action (first sentence has no setup keywords)
    - Ending abruptly (last sentence has no resolution feel)
    """
    if not window.sentences:
        return 0.0

    # Sum individual sentence scores
    total = sum(score_sentence(s) for s in window.sentences)

    # Normalize by sentence count to prevent bias toward many short sentences
    avg = total / len(window.sentences)
    score = total * 0.6 + avg * 4.0  # weighted blend

    # Arc bonus: does the window have a beginning, middle, and end?
    first_words = {w.text.strip().lower().rstrip(".,!?") for w in window.sentences[0].words}
    last_words = {w.text.strip().lower().rstrip(".,!?") for w in window.sentences[-1].words}

    has_setup = bool(first_words & _SETUP_KEYWORDS)
    has_resolution = bool(last_words & _RESOLUTION_KEYWORDS)

    if has_setup:
        score *= 1.2
    if has_resolution:
        score *= 1.15

    # Position bonus: starting from the very beginning of the video is often best
    if window.sentences[0].index == 0:
        score *= 1.1

    # Penalty: if the first sentence is short / incomplete, it's a weak opener
    if len(window.sentences[0].words) < 3:
        score *= 0.8

    return round(score, 2)


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------

class SmartTrimmer(BaseTool):
    """AI-powered video trimmer that cuts at sentence boundaries.

    Uses Whisper for word-level transcription, scores narrative windows,
    and FFmpeg for the actual cut. Designed for BBC documentary clips
    that trigger Content ID blocks when they exceed ~58 seconds.
    """

    name = "smart_trim"
    version = "1.0.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "whisper+ffmpeg"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "pip:openai-whisper"]
    install_instructions = (
        "Install FFmpeg: https://ffmpeg.org/download.html\n"
        "Install Whisper: pip install openai-whisper"
    )
    agent_skills = ["ffmpeg", "video-edit"]

    capabilities = [
        "sentence_boundary_trim",
        "narrative_scoring",
        "smart_cut",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to source video file.",
            },
            "output_path": {
                "type": "string",
                "description": "Path for trimmed output. Defaults to <input>_trimmed.mp4.",
            },
            "target_seconds": {
                "type": "number",
                "default": 55,
                "description": "Target duration in seconds. Slightly under 60 to be safe.",
            },
            "max_seconds": {
                "type": "number",
                "default": 59,
                "description": "Absolute maximum duration. Must not exceed this.",
            },
            "whisper_model": {
                "type": "string",
                "default": "base",
                "description": "Whisper model size: tiny, base, small, medium, large.",
            },
            "prefer_start": {
                "type": "boolean",
                "default": True,
                "description": "If true, prefer windows that start from the beginning.",
            },
            "transcript_path": {
                "type": "string",
                "description": "Optional pre-existing transcript JSON (skip Whisper).",
            },
            "candidates_count": {
                "type": "integer",
                "default": 5,
                "description": "Number of top candidate windows to report.",
            },
            "codec": {
                "type": "string",
                "default": "libx264",
                "description": "Output codec. Use 'copy' for fast lossless cut (may have keyframe drift).",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=1000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["Whisper error"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["input_path", "target_seconds", "max_seconds", "whisper_model"]
    side_effects = ["writes video file to output_path", "writes transcript JSON"]
    user_visible_verification = [
        "Play trimmed output — verify no mid-sentence cuts",
        "Check duration is under max_seconds",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start_time = time.time()
        input_path = Path(inputs["input_path"])
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        target_s = inputs.get("target_seconds", 55)
        max_s = inputs.get("max_seconds", 59)
        whisper_model = inputs.get("whisper_model", "base")
        prefer_start = inputs.get("prefer_start", True)
        candidates_count = inputs.get("candidates_count", 5)
        codec = inputs.get("codec", "libx264")

        output_path = Path(
            inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_trimmed")))
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------------------------
        # Step 1: Get source video duration
        # ------------------------------------------------------------------
        source_duration = self._get_duration(input_path)
        if source_duration is None:
            return ToolResult(success=False, error="Could not determine source video duration")

        # If already under max, no trimming needed
        if source_duration <= max_s:
            return ToolResult(
                success=True,
                data={
                    "action": "no_trim_needed",
                    "source_duration": round(source_duration, 2),
                    "message": f"Source is already {source_duration:.1f}s (under {max_s}s limit).",
                },
                artifacts=[str(input_path)],
                duration_seconds=round(time.time() - start_time, 2),
            )

        # ------------------------------------------------------------------
        # Step 2: Transcribe with word-level timestamps
        # ------------------------------------------------------------------
        transcript_path_str = inputs.get("transcript_path")
        if transcript_path_str and Path(transcript_path_str).exists():
            print(f"[SmartTrim] Loading existing transcript: {transcript_path_str}")
            words = self._load_transcript(Path(transcript_path_str))
        else:
            print(f"[SmartTrim] Transcribing with Whisper ({whisper_model})...")
            words, raw_result = self._transcribe(input_path, whisper_model)

            # Save transcript for reuse
            transcript_out = input_path.with_suffix(".smart_trim_transcript.json")
            self._save_transcript(words, raw_result, transcript_out)
            print(f"[SmartTrim] Transcript saved: {transcript_out}")

        if not words:
            return ToolResult(
                success=False,
                error="Whisper returned no words. Is there narration in this video?",
            )

        print(f"[SmartTrim] Got {len(words)} words spanning "
              f"{words[0].start:.1f}s – {words[-1].end:.1f}s")

        # ------------------------------------------------------------------
        # Step 3: Build sentences
        # ------------------------------------------------------------------
        sentences = words_to_sentences(words)
        print(f"[SmartTrim] Detected {len(sentences)} sentences:")
        for s in sentences:
            print(f"  [{s.start:.1f}s – {s.end:.1f}s] ({s.duration:.1f}s) {s.text[:80]}")

        # ------------------------------------------------------------------
        # Step 4: Find candidate windows
        # ------------------------------------------------------------------
        candidates = self._find_candidate_windows(
            sentences, target_s, max_s, prefer_start
        )

        if not candidates:
            return ToolResult(
                success=False,
                error=(
                    f"No valid trim window found under {max_s}s. "
                    f"All sentences may be too long, or the narration is too sparse."
                ),
            )

        # Score and rank
        for w in candidates:
            w.score = score_window(w, sentences)

        candidates.sort(key=lambda w: w.score, reverse=True)
        top = candidates[:candidates_count]

        best = top[0]
        print(f"\n[SmartTrim] Best window: {best.start:.2f}s – {best.end:.2f}s "
              f"({best.duration:.1f}s, score={best.score})")
        print(f"  Preview: {best.text_preview}")

        # ------------------------------------------------------------------
        # Step 5: FFmpeg cut at sentence boundaries
        # ------------------------------------------------------------------
        print(f"[SmartTrim] Cutting with FFmpeg ({codec})...")
        self._ffmpeg_cut(input_path, output_path, best.start, best.end, codec)

        # Verify output
        out_duration = self._get_duration(output_path)
        if out_duration is None or out_duration > max_s + 0.5:
            return ToolResult(
                success=False,
                error=(
                    f"Output duration {out_duration}s exceeds limit {max_s}s. "
                    "Keyframe alignment may have caused drift."
                ),
            )

        file_size_mb = round(output_path.stat().st_size / (1024 * 1024), 2)

        # Build candidate report
        candidate_report = []
        for i, c in enumerate(top):
            candidate_report.append({
                "rank": i + 1,
                "start": round(c.start, 2),
                "end": round(c.end, 2),
                "duration": round(c.duration, 1),
                "score": c.score,
                "sentences": len(c.sentences),
                "preview": c.text_preview[:120],
            })

        result = ToolResult(
            success=True,
            data={
                "action": "trimmed",
                "source_duration": round(source_duration, 2),
                "output_duration": round(out_duration, 2),
                "output_path": str(output_path),
                "output_size_mb": file_size_mb,
                "trim_start": round(best.start, 2),
                "trim_end": round(best.end, 2),
                "sentences_kept": len(best.sentences),
                "sentences_total": len(sentences),
                "words_total": len(words),
                "best_score": best.score,
                "candidates": candidate_report,
                "full_text": " ".join(s.text for s in best.sentences),
            },
            artifacts=[str(output_path)],
            duration_seconds=round(time.time() - start_time, 2),
        )

        print(f"\n[SmartTrim] SUCCESS")
        print(f"  Output: {output_path}")
        print(f"  Duration: {out_duration:.1f}s (target: {target_s}s, max: {max_s}s)")
        print(f"  Size: {file_size_mb} MB")
        print(f"  Sentences: {len(best.sentences)}/{len(sentences)}")

        return result

    # ------------------------------------------------------------------
    # Internal methods
    # ------------------------------------------------------------------

    def _get_duration(self, path: Path) -> Optional[float]:
        """Get video duration in seconds using ffprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    str(path),
                ],
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception as e:
            print(f"[SmartTrim] ffprobe error: {e}")
            return None

    def _transcribe(self, video_path: Path, model_name: str) -> tuple[list[Word], dict]:
        """Run Whisper transcription with word-level timestamps."""
        import whisper

        model = whisper.load_model(model_name)
        result = model.transcribe(
            str(video_path),
            word_timestamps=True,
            language="en",
        )

        words: list[Word] = []
        for segment in result.get("segments", []):
            for w in segment.get("words", []):
                text = w.get("word", "").strip()
                if text:
                    words.append(Word(
                        text=text,
                        start=w["start"],
                        end=w["end"],
                    ))

        return words, result

    def _load_transcript(self, path: Path) -> list[Word]:
        """Load words from a previously saved transcript JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        words: list[Word] = []
        for w in data.get("words", []):
            words.append(Word(text=w["text"], start=w["start"], end=w["end"]))
        return words

    def _save_transcript(self, words: list[Word], raw_result: dict, path: Path):
        """Save transcript for reuse."""
        out = {
            "words": [{"text": w.text, "start": w.start, "end": w.end} for w in words],
            "full_text": raw_result.get("text", ""),
            "segments": [
                {
                    "start": s["start"],
                    "end": s["end"],
                    "text": s["text"],
                }
                for s in raw_result.get("segments", [])
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)

    def _find_candidate_windows(
        self,
        sentences: list[Sentence],
        target_s: float,
        max_s: float,
        prefer_start: bool,
    ) -> list[TrimWindow]:
        """Find all valid trim windows using a sliding window approach.

        A valid window:
        - Consists of contiguous sentences
        - Total duration <= max_s
        - Total duration >= target_s * 0.7 (at least 70% of target)
        """
        candidates: list[TrimWindow] = []
        min_duration = target_s * 0.7  # Don't go too short

        for i in range(len(sentences)):
            window_sentences: list[Sentence] = []
            # Compute window duration from the first sentence's start to the last
            # sentence's end (accounts for gaps between sentences too)
            for j in range(i, len(sentences)):
                window_sentences.append(sentences[j])
                window_duration = sentences[j].end - sentences[i].start

                if window_duration > max_s:
                    break  # This window is too long, stop adding sentences

                if window_duration >= min_duration:
                    window = TrimWindow(sentences=list(window_sentences))
                    candidates.append(window)

        # Apply prefer_start boost (already handled in score_window but we can
        # also pre-filter to avoid a huge candidate list)
        if prefer_start and candidates:
            # Keep top 30 overall + all windows that start at index 0
            start_candidates = [c for c in candidates if c.sentences[0].index == 0]
            other_candidates = [c for c in candidates if c.sentences[0].index != 0]
            # Sort others by rough duration closeness to target
            other_candidates.sort(
                key=lambda w: abs(w.duration - target_s)
            )
            candidates = start_candidates + other_candidates[:30]

        return candidates

    def _ffmpeg_cut(
        self,
        input_path: Path,
        output_path: Path,
        start: float,
        end: float,
        codec: str,
    ):
        """Execute FFmpeg cut at precise timestamps.

        Uses re-encoding by default for frame-accurate cuts (not keyframe-bound).
        """
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{start:.3f}",
            "-i", str(input_path),
            "-t", f"{end - start:.3f}",
        ]

        if codec == "copy":
            cmd.extend(["-c", "copy", "-avoid_negative_ts", "make_zero"])
        else:
            cmd.extend([
                "-c:v", codec,
                "-crf", "18",
                "-preset", "medium",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
            ])

        cmd.append(str(output_path))

        print(f"  CMD: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {result.stderr[-500:]}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Smart Trim: Cut video to <60s at sentence boundaries"
    )
    parser.add_argument("--input", "-i", required=True, help="Source video path")
    parser.add_argument("--output", "-o", help="Output video path")
    parser.add_argument("--target", type=float, default=55, help="Target duration (default: 55s)")
    parser.add_argument("--max", type=float, default=59, help="Max duration (default: 59s)")
    parser.add_argument("--model", default="base", help="Whisper model (default: base)")
    parser.add_argument("--codec", default="libx264", help="Codec (default: libx264, use 'copy' for fast)")
    parser.add_argument("--transcript", help="Pre-existing transcript JSON path")
    parser.add_argument("--candidates", type=int, default=5, help="Number of candidates to show")

    args = parser.parse_args()

    trimmer = SmartTrimmer()
    result = trimmer.execute({
        "input_path": args.input,
        "output_path": args.output,
        "target_seconds": args.target,
        "max_seconds": args.max,
        "whisper_model": args.model,
        "codec": args.codec,
        "transcript_path": args.transcript,
        "candidates_count": args.candidates,
    })

    if result.success:
        print(f"\n{'='*60}")
        print(f"SMART TRIM COMPLETE")
        print(f"{'='*60}")
        if result.data.get("action") == "no_trim_needed":
            print(result.data["message"])
        else:
            print(f"Output:     {result.data['output_path']}")
            print(f"Duration:   {result.data['output_duration']}s")
            print(f"Size:       {result.data['output_size_mb']} MB")
            print(f"Sentences:  {result.data['sentences_kept']}/{result.data['sentences_total']}")
            print(f"\nKept text:")
            print(f"  {result.data['full_text']}")
            print(f"\nTop candidates:")
            for c in result.data.get("candidates", []):
                print(f"  #{c['rank']}: {c['start']}s–{c['end']}s "
                      f"({c['duration']}s, score={c['score']}) "
                      f"[{c['sentences']} sentences]")
    else:
        print(f"\nFAILED: {result.error}")

    return 0 if result.success else 1


if __name__ == "__main__":
    exit(main())
