"""Remotion caption burn tool — **runtime-specific (Remotion-only)**.

Renders animated word-by-word captions onto a talking-head video using
the Remotion CaptionOverlay component. Falls back to FFmpeg subtitle
burning if Remotion is not available.

The tool:
1. Converts word-level transcript segments to Remotion WordCaption JSON
2. Writes a props file for the TalkingHead composition
3. Renders via ``npx remotion render``
4. Returns the captioned video path

Fallback: if Remotion is unavailable, burns subtitles at the bottom of
the frame using FFmpeg's ``subtitles`` filter with bold styling.

## Runtime scope

This tool is **Remotion-specific** and deliberately has no HyperFrames
counterpart in Phase 1. Word-level caption burn parity on the HyperFrames
runtime is explicitly deferred work (see ``skills/core/hyperframes.md`` →
"What stays Remotion-only in Phase 1").

If a brief requires word-level/karaoke captions, lock
``render_runtime="remotion"`` at proposal even if the rest of the
composition would otherwise be a good fit for HyperFrames. Do NOT attempt
to bolt this tool onto a HyperFrames workspace — the TalkingHead
composition ID and ``WordCaption`` prop shape it emits are tied to the
React scene stack in ``remotion-composer/``.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import time
import os
import tempfile
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


# ---------------------------------------------------------------------- #
#  Thai (scriptio continua) caption support
# ---------------------------------------------------------------------- #
#
# Thai is written without spaces between words. Whisper's word timestamps
# for Thai are byte-level BPE fragments — often a single consonant or a
# detached tone mark ("ร", "ู้", "ไ", "หม") — so passing them straight to
# CaptionOverlay renders "สู ง แล": broken syllables separated by spaces.
# For Thai we re-join the fragments of each segment, segment the text into
# real words (pythainlp newmm when installed), map every word back to the
# timing of the fragments it covers, and render with no word separator.

_THAI_CHAR = re.compile(r"[฀-๿]")
_LATIN_CHAR = re.compile(r"[A-Za-z]")
# A plain trailing " " inside an inline-block caption word collapses to zero
# width in headless Chromium; a non-breaking space survives.
_NBSP = " "


def _is_thai(text: str) -> bool:
    thai = len(_THAI_CHAR.findall(text))
    return thai > 0 and thai >= len(_LATIN_CHAR.findall(text))


def _thai_tokenize(text: str) -> list[str]:
    """Split Thai text into words; whitespace runs are kept as tokens."""
    try:
        from pythainlp.tokenize import word_tokenize
    except ImportError:  # fallback: keep only the spaces the text already has
        return [t for t in re.split(r"(\s+)", text) if t]
    return [t for t in word_tokenize(text, engine="newmm", keep_whitespace=True) if t]


def _apply_text_corrections(
    chars: list[str], times: list[tuple[float, float]], corr: dict[str, str]
) -> tuple[list[str], list[tuple[float, float]]]:
    """Substring corrections on a per-character timeline.

    Replacement characters inherit the time span of the text they replace,
    so the corrected word keeps its original timing even if its length
    changes.
    """
    for wrong in sorted(corr, key=len, reverse=True):
        right = corr[wrong]
        if not wrong or wrong == right:
            continue
        text = "".join(chars)
        out_c: list[str] = []
        out_t: list[tuple[float, float]] = []
        pos = 0
        while True:
            i = text.find(wrong, pos)
            if i < 0:
                break
            out_c.extend(chars[pos:i])
            out_t.extend(times[pos:i])
            span = (times[i][0], times[i + len(wrong) - 1][1])
            out_c.extend(right)
            out_t.extend([span] * len(right))
            pos = i + len(wrong)
        out_c.extend(chars[pos:])
        out_t.extend(times[pos:])
        chars, times = out_c, out_t
    return chars, times


def _thai_timeline_to_captions(
    chars: list[str], times: list[tuple[float, float]]
) -> list[dict]:
    """Tokenize a per-character timeline into caption words (seconds → ms)."""
    text = "".join(chars)
    words: list[dict] = []
    pos = 0
    for tok in _thai_tokenize(text):
        start, end = pos, pos + len(tok) - 1
        pos += len(tok)
        if not tok.strip():
            # Keep real spaces (e.g. around English words or between
            # phrases) visible by attaching them to the previous word.
            if words and not words[-1]["word"].endswith(_NBSP):
                words[-1]["word"] += _NBSP
            continue
        words.append({
            "word": tok,
            "startMs": int(times[start][0] * 1000),
            "endMs": int(times[end][1] * 1000),
        })
    if words:
        words[-1]["word"] = words[-1]["word"].rstrip(_NBSP)
        words[-1]["pageBreakAfter"] = True
    return words


def _even_timeline(text: str, start: float, end: float) -> tuple[list[str], list[tuple[float, float]]]:
    """Spread a phrase evenly over [start, end] one character at a time."""
    text = text.strip()
    n = max(len(text), 1)
    step = (end - start) / n
    return list(text), [(start + i * step, start + (i + 1) * step) for i in range(len(text))]


class RemotionCaptionBurn(BaseTool):
    name = "remotion_caption_burn"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "remotion"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Remotion (optional, preferred): npm install in remotion-composer/\n"
        "FFmpeg (required for fallback): https://ffmpeg.org/download.html"
    )
    agent_skills = ["remotion-best-practices", "ffmpeg"]

    capabilities = [
        "burn_remotion_captions",
        "burn_ffmpeg_captions_fallback",
    ]

    input_schema = {
        "type": "object",
        "required": ["input_path", "output_path"],
        "properties": {
            "input_path": {
                "type": "string",
                "description": "Path to the input video (enhanced talking-head footage).",
            },
            "output_path": {
                "type": "string",
                "description": "Path for the output video with captions burned in.",
            },
            "segments": {
                "type": "array",
                "description": (
                    "Word-level transcript segments from transcriber tool. "
                    "Each segment has 'words' array with {word, start, end}."
                ),
            },
            "srt_path": {
                "type": "string",
                "description": (
                    "Path to an SRT file. Used as an alternative to segments. "
                    "If both provided, segments take priority."
                ),
            },
            "words_per_page": {
                "type": "integer",
                "default": 4,
                "description": (
                    "Words shown at once in the caption overlay. Defaults to 4 "
                    "(6 for Thai, whose captions are segmented into words and "
                    "rendered without spaces automatically)."
                ),
            },
            "font_size": {
                "type": "integer",
                "default": 52,
                "description": "Font size for captions.",
            },
            "highlight_color": {
                "type": "string",
                "default": "#22D3EE",
                "description": "Highlight color for the active word (hex).",
            },
            "corrections": {
                "type": "object",
                "description": (
                    "Dictionary of word corrections for common misrecognitions. "
                    "Keys are the wrong word (case-insensitive), values are the "
                    "correct replacement. Example: {\"cloud\": \"Claude\"}."
                ),
            },
            "overlays": {
                "type": "array",
                "description": (
                    "Array of overlay objects to render on top of the video. "
                    "Each overlay has: type (text_card, stat_card, callout, "
                    "comparison, bar_chart, line_chart, pie_chart, kpi_grid, "
                    "hero_title, section_title, stat_reveal), in_seconds, "
                    "out_seconds, position (lower_third, upper_third, "
                    "left_panel, right_panel, full_overlay), and component-"
                    "specific props (text, stat, chartData, etc.). "
                    "See asset_manifest overlays from the asset-director."
                ),
            },
            "force_ffmpeg": {
                "type": "boolean",
                "default": False,
                "description": "Force FFmpeg fallback even if Remotion is available.",
            },
        },
    }

    resource_profile = ResourceProfile(cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=500)
    idempotency_key_fields = ["input_path", "segments", "srt_path"]
    side_effects = ["writes captioned video to output_path"]
    user_visible_verification = [
        "Play the output video and verify captions appear at the bottom of the frame",
        "Check that the active word is highlighted in the specified color",
        "Verify face is not occluded by caption text",
    ]

    # ------------------------------------------------------------------ #
    #  Remotion detection
    # ------------------------------------------------------------------ #

    def _find_remotion_root(self) -> Path | None:
        """Find the remotion-composer directory relative to the repo."""
        candidates = [
            Path.cwd() / "remotion-composer",
            Path(__file__).resolve().parent.parent.parent / "remotion-composer",
        ]
        for p in candidates:
            if (
                p.is_dir()
                and (p / "package.json").exists()
                and (p / "node_modules").is_dir()
            ):
                return p
        return None

    def _remotion_available(self) -> bool:
        return (
            shutil.which("npx") is not None
            and self._find_remotion_root() is not None
        )

    # ------------------------------------------------------------------ #
    #  Word caption conversion
    # ------------------------------------------------------------------ #

    def _segments_to_word_captions(
        self, segments: list[dict], corrections: dict[str, str] | None = None
    ) -> list[dict]:
        """Convert transcriber segments to [{word, startMs, endMs}, ...]."""
        captions: list[dict] = []
        corr = {k.lower(): v for k, v in (corrections or {}).items()}

        seg_text = " ".join(
            seg.get("text") or "".join(w.get("word", "") for w in seg.get("words", []))
            for seg in segments
        )
        if _is_thai(seg_text):
            return self._thai_segments_to_word_captions(segments, corrections or {})

        for seg in segments:
            words = seg.get("words", [])
            if words:
                for w in words:
                    raw = w["word"].strip()
                    fixed = corr.get(raw.lower().strip(".,!?;:"), raw)
                    # Preserve trailing punctuation from original
                    trailing = ""
                    if raw and raw[-1] in ".,!?;:":
                        trailing = raw[-1]
                    if fixed != raw and not fixed.endswith(trailing):
                        fixed = fixed + trailing
                    captions.append({
                        "word": fixed,
                        "startMs": int(w["start"] * 1000),
                        "endMs": int(w["end"] * 1000),
                    })
            elif "text" in seg:
                text_words = seg["text"].strip().split()
                dur = seg["end"] - seg["start"]
                per_word = dur / max(len(text_words), 1)
                for i, tw in enumerate(text_words):
                    fixed = corr.get(tw.lower().strip(".,!?;:"), tw)
                    captions.append({
                        "word": fixed,
                        "startMs": int((seg["start"] + i * per_word) * 1000),
                        "endMs": int((seg["start"] + (i + 1) * per_word) * 1000),
                    })
        return captions

    def _thai_segments_to_word_captions(
        self, segments: list[dict], corrections: dict[str, str]
    ) -> list[dict]:
        """Thai: merge Whisper fragments into words, one page per segment."""
        captions: list[dict] = []
        for seg in segments:
            chars: list[str] = []
            times: list[tuple[float, float]] = []
            words = seg.get("words") or []
            if words:
                for w in words:
                    frag = w.get("word", "")
                    chars.extend(frag)
                    times.extend([(w["start"], w["end"])] * len(frag))
                # Drop leading/trailing whitespace of the joined segment.
                while chars and not chars[0].strip():
                    chars.pop(0); times.pop(0)
                while chars and not chars[-1].strip():
                    chars.pop(); times.pop()
            elif seg.get("text"):
                chars, times = _even_timeline(seg["text"], seg["start"], seg["end"])
            if not chars:
                continue
            chars, times = _apply_text_corrections(chars, times, corrections)
            captions.extend(_thai_timeline_to_captions(chars, times))
        return captions

    @staticmethod
    def _caption_word_separator(captions: list[dict]) -> str | None:
        """Separator CaptionOverlay should use; None keeps its default."""
        if _is_thai("".join(c["word"] for c in captions)):
            return ""
        return None

    def _srt_to_word_captions(
        self, srt_path: str, corrections: dict[str, str] | None = None
    ) -> list[dict]:
        """Parse SRT file into word captions."""
        content = Path(srt_path).read_text(encoding="utf-8")
        blocks = re.split(r"\n\n+", content.strip())
        corr = {k.lower(): v for k, v in (corrections or {}).items()}
        captions: list[dict] = []
        thai = _is_thai(content)

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) < 3:
                continue
            m = re.match(
                r"(\d{2}):(\d{2}):(\d{2}),(\d{3})\s*-->\s*"
                r"(\d{2}):(\d{2}):(\d{2}),(\d{3})",
                lines[1],
            )
            if not m:
                continue
            start_ms = (
                int(m.group(1)) * 3600000
                + int(m.group(2)) * 60000
                + int(m.group(3)) * 1000
                + int(m.group(4))
            )
            end_ms = (
                int(m.group(5)) * 3600000
                + int(m.group(6)) * 60000
                + int(m.group(7)) * 1000
                + int(m.group(8))
            )
            text = " ".join(lines[2:]).strip()
            if thai:
                chars, times = _even_timeline(text, start_ms / 1000, end_ms / 1000)
                chars, times = _apply_text_corrections(chars, times, corrections or {})
                captions.extend(_thai_timeline_to_captions(chars, times))
                continue
            words = text.split()
            per_word = (end_ms - start_ms) / max(len(words), 1)
            for i, w in enumerate(words):
                fixed = corr.get(w.lower().strip(".,!?;:"), w)
                captions.append({
                    "word": fixed,
                    "startMs": int(start_ms + i * per_word),
                    "endMs": int(start_ms + (i + 1) * per_word),
                })
        return captions

    # ------------------------------------------------------------------ #
    #  Remotion render
    # ------------------------------------------------------------------ #

    def _render_remotion(
        self,
        input_path: str,
        output_path: str,
        captions: list[dict],
        words_per_page: int,
        font_size: int,
        highlight_color: str,
        overlays: list[dict] | None = None,
    ) -> ToolResult:
        root = self._find_remotion_root()
        if root is None:
            return ToolResult(success=False, error="Remotion root not found")

        # Get video duration in frames
        dur_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            input_path,
        ]
        dur_result = self.run_command(dur_cmd)
        dur_out = dur_result.stdout
        duration_s = float(dur_out.strip().split("\n")[0])
        total_frames = math.ceil(duration_s * 30)

        # Detect video dimensions
        dim_cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            input_path,
        ]
        dim_result = self.run_command(dim_cmd)
        dim_parts = dim_result.stdout.strip().split("x")
        width = int(dim_parts[0])
        height = int(dim_parts[1])

        # Copy video to Remotion public folder
        pub_dir = root / "public" / "talking-head"
        pub_dir.mkdir(parents=True, exist_ok=True)
        video_filename = Path(input_path).name
        dest_video = pub_dir / video_filename
        shutil.copy2(input_path, dest_video)

        # Build props JSON
        props = {
            "videoSrc": f"talking-head/{video_filename}",
            "captions": captions,
            "overlays": overlays or [],
            "wordsPerPage": words_per_page,
            "fontSize": font_size,
            "highlightColor": highlight_color,
        }
        separator = self._caption_word_separator(captions)
        if separator is not None:
            props["captionWordSeparator"] = separator
        props_dir = root / "public" / "demo-props"
        props_dir.mkdir(parents=True, exist_ok=True)
        props_file = props_dir / f"caption-burn-{Path(input_path).stem}.json"
        props_file.write_text(json.dumps(props, indent=2), encoding="utf-8")

        # Render (use npx.cmd on Windows for subprocess compatibility)
        import sys
        npx_bin = "npx.cmd" if sys.platform == "win32" else "npx"
        render_cmd = [
            npx_bin, "remotion", "render",
            "TalkingHead",
            f"--props={props_file.relative_to(root)}",
            f"--width={width}", f"--height={height}", "--fps=30",
            f"--frames=0-{total_frames - 1}",
            "--codec=h264", "--crf=18",
            f"--output={str(Path(output_path).resolve())}",
        ]
        self.run_command(render_cmd, cwd=str(root))

        if not Path(output_path).exists():
            return ToolResult(success=False, error="Remotion render produced no output")

        return ToolResult(
            success=True,
            data={
                "method": "remotion",
                "output": output_path,
                "duration_seconds": round(duration_s, 2),
                "total_frames": total_frames,
                "caption_count": len(captions),
                "overlay_count": len(overlays or []),
                "words_per_page": words_per_page,
            },
            artifacts=[output_path],
        )

    # ------------------------------------------------------------------ #
    #  FFmpeg fallback
    # ------------------------------------------------------------------ #

    def _render_ffmpeg(
        self,
        input_path: str,
        output_path: str,
        captions: list[dict],
    ) -> ToolResult:
        """Fall back to FFmpeg subtitle burning at bottom of frame."""
        # Generate temporary SRT from word captions
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        srt_lines = []
        idx = 1
        # Group into pages of ~4 words
        page_size = 4
        separator = self._caption_word_separator(captions)
        joiner = " " if separator is None else separator
        pages: list[list[dict]] = []
        current: list[dict] = []
        for c in captions:
            current.append(c)
            if len(current) >= page_size or c.get("pageBreakAfter"):
                pages.append(current)
                current = []
        if current:
            pages.append(current)
        for page in pages:
            text = joiner.join(c["word"] for c in page).replace(_NBSP, " ")
            start = page[0]["startMs"]
            end = page[-1]["endMs"]
            srt_lines.append(str(idx))
            srt_lines.append(
                f"{self._ms_to_srt(start)} --> {self._ms_to_srt(end)}"
            )
            srt_lines.append(text)
            srt_lines.append("")
            idx += 1

        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix="_tmp_captions_", suffix=".srt", dir=Path(output_path).parent
        )
        tmp_srt = Path(tmp_name)
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
                handle.write("\n".join(srt_lines))
            # Escape path for FFmpeg subtitles filter (Windows colon issue)
            srt_escaped = str(tmp_srt).replace("\\", "/").replace(":", "\\:")

            cmd = [
                "ffmpeg", "-y",
                "-i", input_path,
                "-vf", (
                    f"subtitles='{srt_escaped}'"
                    ":force_style='FontName=Segoe UI,FontSize=24,Bold=1,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                    "Outline=3,Shadow=2,Alignment=2,MarginV=100'"
                ),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                output_path,
            ]
            self.run_command(cmd)

        finally:
            try:
                tmp_srt.unlink()
            except OSError:
                pass

        if not Path(output_path).exists():
            return ToolResult(success=False, error="FFmpeg subtitle burn produced no output")

        return ToolResult(
            success=True,
            data={
                "method": "ffmpeg_fallback",
                "output": output_path,
                "caption_count": len(captions),
                "note": "Used FFmpeg fallback. Install Remotion for animated captions.",
            },
            artifacts=[output_path],
        )

    @staticmethod
    def _ms_to_srt(ms: int) -> str:
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        rem = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{rem:03d}"

    # ------------------------------------------------------------------ #
    #  Main execute
    # ------------------------------------------------------------------ #

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        input_path = inputs["input_path"]
        output_path = inputs["output_path"]
        corrections = inputs.get("corrections")
        force_ffmpeg = inputs.get("force_ffmpeg", False)
        words_per_page = inputs.get("words_per_page")
        font_size = inputs.get("font_size", 52)
        highlight_color = inputs.get("highlight_color", "#22D3EE")

        if not Path(input_path).exists():
            return ToolResult(success=False, error=f"Input video not found: {input_path}")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        start = time.time()

        # Build word captions from segments or SRT
        segments = inputs.get("segments")
        srt_path = inputs.get("srt_path")

        if segments:
            captions = self._segments_to_word_captions(segments, corrections)
        elif srt_path:
            captions = self._srt_to_word_captions(srt_path, corrections)
        else:
            return ToolResult(
                success=False,
                error="Provide either 'segments' (from transcriber) or 'srt_path'.",
            )

        if words_per_page is None:
            # Thai words are short and pages also break at segment ends, so
            # a slightly larger page reads as a natural phrase.
            words_per_page = 6 if self._caption_word_separator(captions) == "" else 4

        if not captions:
            return ToolResult(success=False, error="No caption words extracted.")

        overlays = inputs.get("overlays")

        # Choose render method
        if not force_ffmpeg and self._remotion_available():
            result = self._render_remotion(
                input_path, output_path, captions,
                words_per_page, font_size, highlight_color,
                overlays=overlays,
            )
        else:
            result = self._render_ffmpeg(input_path, output_path, captions)

        result.duration_seconds = round(time.time() - start, 2)
        return result
