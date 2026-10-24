"""Instagram Reels captions as a pixel-exact ASS file.

SRT burned with ``force_style`` is laid out on libass's default 384x288
canvas, so FontSize=28 renders ~190 px tall on a 1920 px frame. This tool
writes ASS with PlayResX/PlayResY equal to the video, so sizes and margins
are real pixels, and keeps captions inside the Instagram safe zone (clear of
the top bar, the bottom caption/CTA area and the right-hand action buttons).

Modes:
  phrase          one or two balanced lines per cue
  word_highlight  same cues, the spoken word recoloured as it is said

Casing follows Azerbaijani rules (i -> İ, ı -> I) via lib.az_text.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from lib import az_text
from lib.reels_profiles import ProfileError, load_lexicon, resolve_style
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)

# Margins in px for a 1080x1920 frame. "organic" keeps clear of the Reels
# overlay (caption, audio row, action buttons); "ads" follows Meta's stricter
# Reels-ads safe zone (bottom ~35%).
SAFE_ZONES = {
    "organic": {"top": 250, "bottom": 480, "left": 90, "right": 160},
    "ads": {"top": 270, "bottom": 680, "left": 65, "right": 160},
}

_SENTENCE_END = (".", "!", "?", "…")
HOLD_BRIDGE_S = 0.4  # gaps up to this keep the previous cue on screen
HOLD_TAIL_S = 0.2


def hex_to_ass(colour: str | None, alpha: float = 0.0, default: str = "#FFFFFF") -> str:
    """'#RRGGBB' -> '&HAABBGGRR' (alpha 0 = opaque, 1 = transparent)."""
    colour = (colour or default).lstrip("#")
    rr, gg, bb = colour[0:2], colour[2:4], colour[4:6]
    aa = max(0, min(255, round(alpha * 255)))
    return f"&H{aa:02X}{bb}{gg}{rr}".upper()


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def _fmt_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_cues(
    words: list[dict],
    *,
    max_chars_per_line: int = 24,
    max_lines: int = 2,
    max_gap_s: float = 0.6,
    max_cue_s: float = 3.5,
) -> list[list[dict]]:
    """Group timed words into caption cues that fit the line budget."""
    budget = max_chars_per_line * max_lines
    cues: list[list[dict]] = []
    current: list[dict] = []
    length = 0
    for w in words:
        token = str(w["word"]).strip()
        if not token:
            continue
        added = len(token) + (1 if current else 0)
        if current and (
            length + added > budget
            or float(w["start"]) - float(current[-1]["end"]) > max_gap_s
            or float(w["end"]) - float(current[0]["start"]) > max_cue_s
        ):
            cues.append(current)
            current, length = [], 0
            added = len(token)
        current.append({**w, "word": token})
        length += added
        if token.endswith(_SENTENCE_END):
            cues.append(current)
            current, length = [], 0
    if current:
        cues.append(current)
    return cues


def split_lines(tokens: list[str], max_chars_per_line: int, max_lines: int) -> list[list[int]]:
    """Balanced line breaks; returns token indices per line."""
    if max_lines <= 1 or len(" ".join(tokens)) <= max_chars_per_line:
        return [list(range(len(tokens)))]
    best = None
    for cut in range(1, len(tokens)):
        a = len(" ".join(tokens[:cut]))
        b = len(" ".join(tokens[cut:]))
        score = max(a, b) + (100 if max(a, b) > max_chars_per_line else 0)
        if best is None or score < best[0]:
            best = (score, cut)
    cut = best[1] if best else len(tokens)
    return [list(range(cut)), list(range(cut, len(tokens)))]


class ReelsCaptions(BaseTool):
    name = "reels_captions"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "subtitle"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = []
    install_instructions = "No external dependencies required (burn-in needs FFmpeg with libass)."
    agent_skills = ["ffmpeg"]

    capabilities = ["generate_ass", "word_highlight", "safe_zone_layout", "brand_caption_style"]

    input_schema = {
        "type": "object",
        "required": ["output_path"],
        "properties": {
            "transcript_path": {"type": "string", "description": "Transcript JSON with words."},
            "words": {"type": "array", "description": "Timed words, used when transcript_path is omitted."},
            "output_path": {"type": "string", "description": "Destination .ass file."},
            "client_id": {"type": "string", "description": "Resolve caption style from this brand profile."},
            "profile_id": {"type": "string", "description": "Editing profile; defaults to the brand's preferred one."},
            "style": {
                "type": "object",
                "description": "Explicit style keys; override the resolved profile/brand style.",
            },
            "emphasis_words": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Approved keywords drawn in the highlight colour (phrase mode).",
            },
            "protected_terms": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Extra brand/name spellings kept in Latin casing when uppercased.",
            },
            "safe_zone": {"type": "string", "enum": list(SAFE_ZONES), "default": "organic"},
            "width": {"type": "integer", "default": 1080},
            "height": {"type": "integer", "default": 1920},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=5)
    idempotency_key_fields = [
        "transcript_path", "words", "client_id", "profile_id", "style",
        "emphasis_words", "safe_zone", "width", "height",
    ]
    side_effects = ["writes ASS subtitle file to output_path"]
    user_visible_verification = [
        "Check a frame per cue: readable, inside the safe zone, correct Azerbaijani letters",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        words = self._load_words(inputs)
        if not words:
            return ToolResult(success=False, error="No timed words (transcript_path or words)")

        warnings: list[str] = []
        style: dict[str, Any] = {}
        if inputs.get("client_id"):
            try:
                resolved = resolve_style(inputs["client_id"], inputs.get("profile_id"))
            except ProfileError as exc:
                return ToolResult(success=False, error=str(exc))
            style.update(resolved["captions"])
            warnings.extend(resolved["warnings"])
        style.update(inputs.get("style") or {})

        font = style.get("font") or "Inter"
        if not self._font_available(font):
            warnings.append(f"Font '{font}' is not installed; falling back to Inter")
            font = "Inter"

        width = int(inputs.get("width", 1080))
        height = int(inputs.get("height", 1920))
        zone = dict(SAFE_ZONES[inputs.get("safe_zone", "organic")])
        scale_x, scale_y = width / 1080, height / 1920
        zone = {
            "top": round(zone["top"] * scale_y), "bottom": round(zone["bottom"] * scale_y),
            "left": round(zone["left"] * scale_x), "right": round(zone["right"] * scale_x),
        }

        position = style.get("position", "lower_safe")
        alignment, margin_v = {
            "lower_safe": (2, zone["bottom"]),
            "center": (5, 0),
            "upper_safe": (8, zone["top"]),
        }.get(position, (2, zone["bottom"]))

        font_size = int(style.get("font_size_px", 64) * scale_y)
        text_c = hex_to_ass(style.get("text_color"), default="#FFFFFF")
        hi_c = hex_to_ass(style.get("highlight_color"), default="#FFD400")
        outline_c = hex_to_ass(style.get("outline_color"), default="#000000")
        if style.get("box_color"):
            box_alpha = 1.0 - float(style.get("box_opacity") or 0.6)
            border_style, outline_px, shadow = 3, max(6, font_size // 6), 0
            outline_c = back_c = hex_to_ass(style["box_color"], alpha=box_alpha)
        else:
            border_style = 1
            outline_px = int(style.get("outline_px", max(3, font_size // 16)))
            shadow = int(style.get("shadow_px", 2))
            back_c = hex_to_ass("#000000", alpha=0.4)

        header = "\n".join([
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {width}",
            f"PlayResY: {height}",
            "WrapStyle: 2",
            "ScaledBorderAndShadow: yes",
            "YCbCr Matrix: TV.709",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
            "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
            "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Reels,{font},{font_size},{text_c},{hi_c},{outline_c},{back_c},"
            f"{-1 if style.get('bold', True) else 0},0,0,0,100,100,0,0,{border_style},"
            f"{outline_px},{shadow},{alignment},{zone['left']},{zone['right']},{margin_v},1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ])

        max_chars = int(style.get("max_chars_per_line", 24))
        max_lines = int(style.get("max_lines", 2))
        uppercase = bool(style.get("uppercase", False))
        if uppercase:
            # Capitals run ~15% wider; keep the same lines inside the safe zone.
            max_chars = max(8, int(max_chars * 0.85))
        mode = style.get("mode", "phrase")
        emphasis = {az_text.match_key(w) for w in inputs.get("emphasis_words") or []}
        try:
            protected = set(load_lexicon(inputs.get("client_id"))["protected_terms"])
        except ProfileError as exc:
            return ToolResult(success=False, error=str(exc))
        protected.update(inputs.get("protected_terms") or [])

        cues = build_cues(words, max_chars_per_line=max_chars, max_lines=max_lines)
        events: list[str] = []
        for idx, cue in enumerate(cues):
            tokens = [az_text.normalize(w["word"]) for w in cue]
            if uppercase:
                tokens = [az_text.upper_token(t, protected) for t in tokens]
            lines = split_lines(tokens, max_chars, max_lines)
            cue_start = float(cue[0]["start"])
            cue_end = float(cue[-1]["end"])
            # Bridge short gaps to the next cue (no flicker at jump cuts) and
            # hold the last words briefly; never overlap the next cue.
            next_start = float(cues[idx + 1][0]["start"]) if idx + 1 < len(cues) else None
            if next_start is not None and next_start - cue_end <= HOLD_BRIDGE_S:
                cue_end = max(cue_end, next_start)
            elif next_start is not None:
                cue_end = min(cue_end + HOLD_TAIL_S, next_start)
            else:
                cue_end += HOLD_TAIL_S

            def render(active: int | None) -> str:
                rendered_lines = []
                for line in lines:
                    parts = []
                    for i in line:
                        tok = _ass_escape(tokens[i])
                        if i == active or (active is None and az_text.match_key(tokens[i]) in emphasis):
                            parts.append(f"{{\\c&H{hi_c[4:]}&}}{tok}{{\\c&H{text_c[4:]}&}}")
                        else:
                            parts.append(tok)
                    rendered_lines.append(" ".join(parts))
                return "\\N".join(rendered_lines)

            if mode == "word_highlight":
                for i, w in enumerate(cue):
                    s = cue_start if i == 0 else float(w["start"])
                    e = float(cue[i + 1]["start"]) if i + 1 < len(cue) else cue_end
                    if e <= s:
                        continue
                    events.append(f"Dialogue: 0,{_fmt_time(s)},{_fmt_time(e)},Reels,,0,0,0,,{render(i)}")
            else:
                events.append(
                    f"Dialogue: 0,{_fmt_time(cue_start)},{_fmt_time(cue_end)},Reels,,0,0,0,,{render(None)}"
                )

        out = Path(inputs["output_path"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(header + "\n" + "\n".join(events) + "\n", encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "output": str(out),
                "cue_count": len(cues),
                "event_count": len(events),
                "mode": mode,
                "font": font,
                "font_size_px": font_size,
                "safe_zone": inputs.get("safe_zone", "organic"),
                "margins": {**zone, "margin_v_used": margin_v},
                "warnings": warnings,
            },
            artifacts=[str(out)],
            duration_seconds=round(time.time() - start, 3),
        )

    @staticmethod
    def _load_words(inputs: dict[str, Any]) -> list[dict]:
        if inputs.get("transcript_path"):
            path = Path(inputs["transcript_path"])
            if not path.is_file():
                return []
            data = json.loads(path.read_text(encoding="utf-8"))
            words = [w for s in data.get("segments", []) for w in s.get("words", [])]
            words = words or data.get("words") or data.get("word_timestamps") or []
        else:
            words = inputs.get("words") or []
        return [w for w in words if w.get("start") is not None and w.get("end") is not None]

    @staticmethod
    def _font_available(font: str) -> bool:
        if not shutil.which("fc-list"):
            return True  # cannot check; let libass resolve it
        try:
            out = subprocess.run(
                ["fc-list", ":", "family"], capture_output=True, text=True, timeout=20
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return True
        families = {f.strip() for line in out.splitlines() for f in line.split(",")}
        return font in families
