"""Subtitle generation tool.

Converts word-level timestamps from the transcriber into SRT, VTT,
or caption JSON formats. Pure Python — no external dependencies beyond
the standard library.
"""

from __future__ import annotations

import difflib
import re

import json
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)


# --- CJK-aware joining -------------------------------------------------------
# Latin scripts separate words with spaces; CJK scripts do not. Joining CJK
# tokens with a space inserts a visible gap between every character and breaks
# the renderer's line wrapping (see remotion-composer CaptionOverlay
# `wordSeparator`, which expects "" for CJK).
_CJK_RANGES = (
    (0x3040, 0x30FF),   # Hiragana + Katakana
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0xAC00, 0xD7AF),   # Hangul syllables
    (0xFF00, 0xFFEF),   # Halfwidth and Fullwidth Forms
)
_TAG_RE = re.compile(r"<[^>]+>")


def _is_cjk_char(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def _is_cjk_edge(text: str, first: bool) -> bool:
    """True when the first/last visible character is CJK (ignores <b> tags)."""
    plain = _TAG_RE.sub("", text)
    if not plain:
        return False
    return _is_cjk_char(plain[0] if first else plain[-1])


def _visible_edge(text: str, first: bool) -> str:
    """First/last visible character, ignoring <b> markup. "" when empty."""
    plain = _TAG_RE.sub("", text)
    if not plain:
        return ""
    return plain[0] if first else plain[-1]


# Punctuation that binds two tokens into one written word ("skip-tts", "GPT-4",
# "l'heure"). A space around these would tear a single word apart.
_INTRATOKEN_PUNCT = set("-‐‑'’/")


_HARD_BREAK = "。！？!?…"          # sentence enders: always end a cue
_SOFT_BREAK = "，、；：,;:"          # clause separators: end a cue when it is half full


def _break_weight(token: str) -> int:
    """0 = no break, 1 = soft break (clause), 2 = hard break (sentence end)."""
    plain = _TAG_RE.sub("", token).rstrip('"\')' + "）】》")
    if not plain:
        return 0
    if plain[-1] in _HARD_BREAK:
        return 2
    if plain[-1] in _SOFT_BREAK:
        return 1
    return 0


_CJK_PUNCT = set("。！？!?…，、；：,;:") | set("「」『』（）()《》〈〉【】\"'“”‘’")


def _jieba_split(text: str) -> list[str] | None:
    """CJK word segmentation, when the optional `jieba` package is present.

    Returns None when unavailable so callers can fall back to clause-level
    tokens rather than cutting inside a word.
    """
    try:
        import jieba  # type: ignore
    except Exception:
        return None
    try:
        words = [w for w in jieba.lcut(text) if w.strip()]
    except Exception:
        return None
    return words or None


def _flatten_char_timeline(segments: list[dict]) -> list[tuple[str, float, float]]:
    """Spread each word's span evenly across its characters."""
    timeline: list[tuple[str, float, float]] = []
    for seg in segments:
        for w in seg.get("words") or []:
            token = w.get("word") or ""
            n = len(token)
            if n == 0:
                continue
            start, end = float(w["start"]), float(w["end"])
            span = end - start
            for i, ch in enumerate(token):
                timeline.append((ch, start + span * i / n, start + span * (i + 1) / n))
    return timeline


def align_script_to_words(
    script_text: str, segments: list[dict], tokenize: bool = True
) -> list[dict]:
    """Map the authoritative narration script onto ASR-derived timings.

    Subtitles built straight from speech-to-text inherit its homophone errors,
    and CJK recognisers emit per-character tokens with no word boundaries — so
    any length-based cue splitter cuts words in half. When the narration script
    is known (always true for generated TTS) the script is the authoritative
    text and only the timings need to come from ASR.

    Returns word-level tokens carrying the original characters, the original
    punctuation (which supplies clause boundaries), and aligned timings.
    """
    timeline = _flatten_char_timeline(segments)
    if not timeline or not script_text:
        return []

    heard = "".join(ch for ch, _, _ in timeline)
    matcher = difflib.SequenceMatcher(None, heard, script_text, autojunk=False)

    # One (char, start, end) per script character, in script order.
    aligned: list[tuple[str, float, float]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for k in range(j2 - j1):
                _, start, end = timeline[i1 + k]
                aligned.append((script_text[j1 + k], start, end))
            continue
        if tag == "delete":
            continue  # recognised but absent from the script — nothing to place
        # replace / insert: borrow the surrounding time window and spread it.
        if i1 < len(timeline):
            window_start = timeline[i1][1]
        elif aligned:
            window_start = aligned[-1][2]
        else:
            window_start = timeline[-1][2]
        if tag == "replace" and i2 > i1:
            window_end = timeline[i2 - 1][2]
        else:
            window_end = window_start
        count = j2 - j1
        span = window_end - window_start
        for k in range(count):
            aligned.append(
                (script_text[j1 + k], window_start + span * k / count,
                 window_start + span * (k + 1) / count)
            )

    # Group into tokens: end a token after punctuation, and (when segmentation
    # is available) after each word so cue splitters never cut inside a word.
    tokens: list[dict] = []
    buf: list[tuple[str, float, float]] = []

    def flush() -> None:
        if not buf:
            return
        tokens.append({
            "word": "".join(c for c, _, _ in buf),
            "start": round(buf[0][1], 3),
            "end": round(buf[-1][2], 3),
        })
        buf.clear()

    for ch, start, end in aligned:
        buf.append((ch, start, end))
        if ch in _CJK_PUNCT:
            flush()
            continue
        if tokenize:
            # Split only when the buffered run clearly spans several words, so a
            # single word is never emitted as two cues.
            run = "".join(c for c, _, _ in buf)
            words = _jieba_split(run)
            if words and len(words) > 1 and len(run) >= 6:
                # Emit every word except the trailing one, which stays buffered
                # so the next character can still extend it.
                consumed = 0
                for w in words[:-1]:
                    consumed += len(w)
                if consumed > 0:
                    head = buf[:consumed]
                    tail = buf[consumed:]
                    buf[:] = tail
                    tokens.append({
                        "word": "".join(c for c, _, _ in head),
                        "start": round(head[0][1], 3),
                        "end": round(head[-1][2], 3),
                    })
    flush()
    return tokens


def _enforce_min_cue_duration(cues: list[dict], minimum: float) -> list[dict]:
    """Stretch cues shorter than `minimum`, never past the next cue's start.

    Speech-to-text timing can hand a one-word interjection a fraction of a
    second. subtitle-sync.md specifies a 0.5s floor; without it such a cue is
    unreadable. Overlap is avoided by borrowing only the gap that exists, and a
    cue is never shortened below its own start.
    """
    for i, cue in enumerate(cues):
        start = float(cue["start"])
        end = float(cue["end"])
        if end - start >= minimum:
            continue
        ceiling = float(cues[i + 1]["start"]) if i + 1 < len(cues) else float("inf")
        # Leave a hair of breathing room so cues never appear to touch.
        target = min(start + minimum, ceiling - 0.001) if ceiling != float("inf") else start + minimum
        if target > end:
            cue["end"] = round(target, 3)
    return cues


def _join_tokens(parts: list[str]) -> str:
    """Join subtitle tokens, omitting the separator between CJK characters.

    A space is also suppressed around intra-word punctuation, so a hyphenated
    Latin token sitting inside CJK text ("skip-tts", "GPT-4") is not torn apart
    into ``skip- tts``.
    """
    out = ""
    for part in parts:
        if not part:
            continue
        if not out:
            out = part
            continue
        if _is_cjk_edge(out, first=False) or _is_cjk_edge(part, first=True):
            out += part
        elif (
            _visible_edge(out, first=False) in _INTRATOKEN_PUNCT
            or _visible_edge(part, first=True) in _INTRATOKEN_PUNCT
        ):
            out += part
        else:
            out += " " + part
    return out


class SubtitleGen(BaseTool):
    name = "subtitle_gen"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = []  # pure Python
    # jieba is optional: when present, CJK cues also break between words inside
    # long unpunctuated clauses. Without it, CJK cues break at punctuation only,
    # which is always correct but occasionally produces a longer cue.
    install_instructions = (
        "No external dependencies required. "
        "Optional: `pip install jieba` for finer CJK cue boundaries."
    )
    agent_skills = ["remotion-best-practices"]

    capabilities = ["generate_srt", "generate_vtt", "generate_caption_json"]

    input_schema = {
        "type": "object",
        "required": ["segments"],
        "properties": {
            "script_text": {
                "type": "string",
                "description": (
                    "Authoritative narration script, when known (it always is for "
                    "TTS-generated audio). Aligns the script onto ASR timings so "
                    "cues carry the correct characters and punctuation instead of "
                    "speech-to-text errors, and so CJK cues break between words "
                    "rather than mid-word. Strongly recommended for CJK."
                ),
            },
            "segments": {
                "type": "array",
                "description": "Transcript segments from transcriber (with words and timestamps)",
            },
            "format": {
                "type": "string",
                "enum": ["srt", "vtt", "json"],
                "default": "srt",
            },
            "output_path": {"type": "string"},
            "max_chars_per_line": {"type": "integer", "default": 42},
            "min_cue_seconds": {
                "type": "number",
                "default": 0.5,
                "description": (
                    "Minimum display time per cue. subtitle-sync.md specifies 0.5s; "
                    "short interjections otherwise flash by (a 0.24s cue is unreadable). "
                    "Set 0 to disable."
                ),
            },
            "max_words_per_cue": {"type": "integer", "default": 8},
            "highlight_style": {
                "type": "string",
                "enum": ["none", "word_by_word", "karaoke"],
                "default": "none",
            },
            "corrections": {
                "type": "object",
                "description": (
                    "Dictionary of word corrections for common ASR misrecognitions. "
                    "Keys are the wrong word (case-insensitive), values are the "
                    "correct replacement. Applied before generating subtitles. "
                    "Example: {\"cloud\": \"Claude\", \"co-pilot\": \"Copilot\"}."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)
    idempotency_key_fields = ["segments", "format", "max_words_per_cue"]
    side_effects = ["writes subtitle file to output_path"]
    user_visible_verification = [
        "Play video with generated subtitles and verify timing",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        segments = inputs["segments"]
        fmt = inputs.get("format", "srt")
        max_words = inputs.get("max_words_per_cue", 8)
        max_chars = inputs.get("max_chars_per_line", 42)
        min_cue = float(inputs.get("min_cue_seconds", 0.5) or 0.0)
        highlight_style = inputs.get("highlight_style", "none")
        output_path = inputs.get("output_path")
        corrections = inputs.get("corrections")

        start = time.time()

        # Apply word corrections if provided
        if corrections:
            segments = self._apply_corrections(segments, corrections)

        # Build cues from word-level timestamps
        script_text = inputs.get("script_text")
        if script_text:
            aligned_words = align_script_to_words(
                script_text, segments, tokenize=not bool(corrections)
            )
            if aligned_words:
                segments = [{
                    "text": script_text,
                    "start": aligned_words[0]["start"],
                    "end": aligned_words[-1]["end"],
                    "words": aligned_words,
                }]

        cues = self._build_cues(segments, max_words, max_chars)
        if min_cue > 0:
            cues = _enforce_min_cue_duration(cues, min_cue)

        if fmt == "srt":
            content = self._render_srt(cues, highlight_style)
            ext = ".srt"
        elif fmt == "vtt":
            content = self._render_vtt(cues, highlight_style)
            ext = ".vtt"
        elif fmt == "json":
            content = json.dumps({"cues": cues, "highlight_style": highlight_style}, indent=2)
            ext = ".caption.json"
        else:
            return ToolResult(success=False, error=f"Unknown format: {fmt}")

        if output_path is None:
            output_path = f"subtitles{ext}"
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")

        elapsed = time.time() - start

        return ToolResult(
            success=True,
            data={
                "format": fmt,
                "cue_count": len(cues),
                "output": str(out),
            },
            artifacts=[str(out)],
            duration_seconds=round(elapsed, 2),
        )

    @staticmethod
    def _apply_corrections(
        segments: list[dict], corrections: dict[str, str]
    ) -> list[dict]:
        """Apply word-level corrections to transcript segments.

        Handles case-insensitive matching and preserves punctuation.
        """
        import copy

        corr = {k.lower(): v for k, v in corrections.items()}
        result = copy.deepcopy(segments)

        for seg in result:
            words = seg.get("words", [])
            for w in words:
                raw = w.get("word", "").strip()
                # Strip punctuation for lookup, preserve it
                stripped = raw.lower().rstrip(".,!?;:'\"")
                if stripped in corr:
                    trailing = raw[len(stripped):]
                    w["word"] = corr[stripped] + trailing
            # Also fix segment-level text
            if "text" in seg and words:
                seg["text"] = _join_tokens([w["word"] for w in words])
            elif "text" in seg:
                for wrong, right in corr.items():
                    import re as _re
                    seg["text"] = _re.sub(
                        r"\b" + _re.escape(wrong) + r"\b",
                        right,
                        seg["text"],
                        flags=_re.IGNORECASE,
                    )

        return result

    def _build_cues(
        self, segments: list[dict], max_words: int, max_chars: int
    ) -> list[dict]:
        """Group words into display cues respecting max_words and max_chars."""
        # Collect all words with timestamps
        all_words = []
        for seg in segments:
            words = seg.get("words", [])
            if words:
                all_words.extend(words)
            elif "text" in seg:
                # Fallback: segment-level only (no word timestamps)
                all_words.append({
                    "word": seg["text"],
                    "start": seg["start"],
                    "end": seg["end"],
                })

        if not all_words:
            return []

        cues = []
        buf: list[dict] = []
        buf_text = ""

        for w in all_words:
            word_text = w["word"].strip()
            candidate = _join_tokens([buf_text, word_text])

            weight = _break_weight(buf[-1]["word"]) if buf else 0
            # CJK speech-to-text without an initial_prompt yields no punctuation
            # and no word boundaries, so a length cut is the only option there.
            # With punctuation available, prefer clause and sentence boundaries:
            # a hard break always cuts, a soft break cuts once the cue is half full.
            pun_break = weight == 2 or (weight == 1 and len(buf_text) >= max_chars // 2)
            len_break = len(buf) >= max_words or len(candidate) > max_chars
            if buf and (pun_break or len_break):
                cues.append({
                    "index": len(cues) + 1,
                    "start": buf[0]["start"],
                    "end": buf[-1]["end"],
                    "text": buf_text,
                    "words": [
                        {"word": b["word"].strip(), "start": b["start"], "end": b["end"]}
                        for b in buf
                    ],
                })
                buf = []
                buf_text = ""

            buf.append(w)
            buf_text = _join_tokens([buf_text, word_text])

        # Flush remaining
        if buf:
            cues.append({
                "index": len(cues) + 1,
                "start": buf[0]["start"],
                "end": buf[-1]["end"],
                "text": buf_text,
                "words": [
                    {"word": b["word"].strip(), "start": b["start"], "end": b["end"]}
                    for b in buf
                ],
            })

        return cues

    def _render_srt(self, cues: list[dict], highlight_style: str = "none") -> str:
        lines = []
        if highlight_style == "word_by_word":
            # Emit one cue per word for word-by-word reveal
            idx = 1
            for cue in cues:
                for word_info in cue.get("words", []):
                    lines.append(str(idx))
                    lines.append(
                        f"{self._ts_srt(word_info['start'])} --> {self._ts_srt(word_info['end'])}"
                    )
                    lines.append(word_info["word"])
                    lines.append("")
                    idx += 1
        elif highlight_style == "karaoke":
            # Show full cue text but bold the active word using SRT HTML tags
            for cue in cues:
                words = cue.get("words", [])
                if not words:
                    lines.append(str(cue["index"]))
                    lines.append(f"{self._ts_srt(cue['start'])} --> {self._ts_srt(cue['end'])}")
                    lines.append(cue["text"])
                    lines.append("")
                    continue
                for wi, word_info in enumerate(words):
                    lines.append(str(cue["index"] * 100 + wi))
                    lines.append(
                        f"{self._ts_srt(word_info['start'])} --> {self._ts_srt(word_info['end'])}"
                    )
                    parts = []
                    for wj, w in enumerate(words):
                        if wj == wi:
                            parts.append(f"<b>{w['word']}</b>")
                        else:
                            parts.append(w["word"])
                    lines.append(_join_tokens(parts))
                    lines.append("")
        else:
            for cue in cues:
                lines.append(str(cue["index"]))
                lines.append(f"{self._ts_srt(cue['start'])} --> {self._ts_srt(cue['end'])}")
                lines.append(cue["text"])
                lines.append("")
        return "\n".join(lines)

    def _render_vtt(self, cues: list[dict], highlight_style: str = "none") -> str:
        lines = ["WEBVTT", ""]
        if highlight_style == "word_by_word":
            for cue in cues:
                for word_info in cue.get("words", []):
                    lines.append(
                        f"{self._ts_vtt(word_info['start'])} --> {self._ts_vtt(word_info['end'])}"
                    )
                    lines.append(word_info["word"])
                    lines.append("")
        elif highlight_style == "karaoke":
            for cue in cues:
                words = cue.get("words", [])
                if not words:
                    lines.append(f"{self._ts_vtt(cue['start'])} --> {self._ts_vtt(cue['end'])}")
                    lines.append(cue["text"])
                    lines.append("")
                    continue
                for wi, word_info in enumerate(words):
                    lines.append(
                        f"{self._ts_vtt(word_info['start'])} --> {self._ts_vtt(word_info['end'])}"
                    )
                    parts = []
                    for wj, w in enumerate(words):
                        if wj == wi:
                            parts.append(f"<b>{w['word']}</b>")
                        else:
                            parts.append(w["word"])
                    lines.append(_join_tokens(parts))
                    lines.append("")
        else:
            for cue in cues:
                lines.append(f"{self._ts_vtt(cue['start'])} --> {self._ts_vtt(cue['end'])}")
                lines.append(cue["text"])
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _hmsms(seconds: float) -> tuple[int, int, int, int]:
        """Decompose seconds into (h, m, s, ms), rounding to whole ms first.

        Rounding to total milliseconds before splitting the fields lets the
        carry propagate: 0.9995s+ must become the next second (…,000), not a
        malformed 4-digit …,1000 with the seconds field left unincremented.
        """
        total_ms = int(round(max(0.0, seconds) * 1000))
        h, rem = divmod(total_ms, 3_600_000)
        m, rem = divmod(rem, 60_000)
        s, ms = divmod(rem, 1_000)
        return h, m, s, ms

    @classmethod
    def _ts_srt(cls, seconds: float) -> str:
        """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
        h, m, s, ms = cls._hmsms(seconds)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @classmethod
    def _ts_vtt(cls, seconds: float) -> str:
        """Format seconds as VTT timestamp: HH:MM:SS.mmm"""
        h, m, s, ms = cls._hmsms(seconds)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
