"""Subtitle generation tool.

Converts word-level timestamps from the transcriber into SRT, VTT,
or caption JSON formats. Pure Python — no external dependencies beyond
the standard library.
"""

from __future__ import annotations

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
    install_instructions = "No external dependencies required."
    agent_skills = ["remotion-best-practices"]

    capabilities = ["generate_srt", "generate_vtt", "generate_caption_json"]

    input_schema = {
        "type": "object",
        "required": ["segments"],
        "properties": {
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
        highlight_style = inputs.get("highlight_style", "none")
        output_path = inputs.get("output_path")
        corrections = inputs.get("corrections")

        start = time.time()

        # Apply word corrections if provided
        if corrections:
            segments = self._apply_corrections(segments, corrections)

        # Build cues from word-level timestamps
        cues = self._build_cues(segments, max_words, max_chars)

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
                seg["text"] = " ".join(w["word"] for w in words)
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

    @staticmethod
    def _display_cells(text: str) -> int:
        """Display width in cells — CJK characters are double-width.

        len() counted a hanzi as 1, so the default 42-char limit allowed 42
        full-width characters per line — 2.6× the Netflix Simplified-Chinese
        limit of 16 chars/line (audit 2026-07-16, Wave 2 item 9). With cell
        counting, max_chars=42 cells ≈ 21 CJK chars; callers targeting strict
        zh-Hans delivery should pass max_chars_per_line=32.
        """
        cells = 0
        for ch in text:
            cells += 2 if (
                "ᄀ" <= ch <= "ᇿ"      # Hangul Jamo
                or "⺀" <= ch <= "鿿"   # CJK radicals … unified ideographs
                or "　" <= ch <= "〿"   # CJK punctuation
                or "가" <= ch <= "힯"   # Hangul syllables
                or "豈" <= ch <= "﫿"   # CJK compatibility
                or "＀" <= ch <= "￯"   # full-width forms
            ) else 1
        return cells

    @staticmethod
    def _split_long_text(text: str, max_cells: int) -> list[str]:
        """Split segment-level text (no word timestamps) into cue-sized
        chunks at punctuation/space boundaries. Previously a timestampless
        segment became ONE unbounded cue however long its text was."""
        import re
        pieces = [p for p in re.split(r"(?<=[，。！？；、,.!?;: ])", text) if p.strip()]
        chunks: list[str] = []
        current = ""
        for piece in pieces:
            candidate = current + piece
            if current and SubtitleGen._display_cells(candidate) > max_cells:
                chunks.append(current.strip())
                current = piece
            else:
                current = candidate
        if current.strip():
            chunks.append(current.strip())
        return chunks or [text]

    def _build_cues(
        self, segments: list[dict], max_words: int, max_chars: int
    ) -> list[dict]:
        """Group words into display cues respecting max_words and max_chars
        (chars measured in display cells — CJK counts double)."""
        # Collect all words with timestamps
        all_words = []
        for seg in segments:
            words = seg.get("words", [])
            if words:
                all_words.extend(words)
            elif "text" in seg:
                # Fallback: segment-level only (no word timestamps) — split
                # oversized text into chunks with linearly distributed time.
                chunks = self._split_long_text(str(seg["text"]), max_chars)
                seg_start, seg_end = float(seg["start"]), float(seg["end"])
                total_cells = sum(self._display_cells(c) for c in chunks) or 1
                t = seg_start
                for chunk in chunks:
                    share = (seg_end - seg_start) * self._display_cells(chunk) / total_cells
                    all_words.append({"word": chunk, "start": t, "end": t + share})
                    t += share

        if not all_words:
            return []

        cues = []
        buf: list[dict] = []
        buf_text = ""

        for w in all_words:
            word_text = w["word"].strip()
            candidate = f"{buf_text} {word_text}".strip() if buf_text else word_text

            if buf and (len(buf) >= max_words or self._display_cells(candidate) > max_chars):
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
            buf_text = f"{buf_text} {word_text}".strip() if buf_text else word_text

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
                    lines.append(" ".join(parts))
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
                    lines.append(" ".join(parts))
                    lines.append("")
        else:
            for cue in cues:
                lines.append(f"{self._ts_vtt(cue['start'])} --> {self._ts_vtt(cue['end'])}")
                lines.append(cue["text"])
                lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _ts_srt(seconds: float) -> str:
        """Format seconds as SRT timestamp: HH:MM:SS,mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds % 1) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _ts_vtt(seconds: float) -> str:
        """Format seconds as VTT timestamp: HH:MM:SS.mmm"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int(round((seconds % 1) * 1000))
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
