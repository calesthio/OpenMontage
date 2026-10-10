# Circuit-video: readable burned-in captions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the captions burned into tutorial videos by the ffmpeg runtime smaller, better-looking (a clean sans in a soft box instead of thick-outlined DejaVu), and placed near the bottom edge instead of a sixth of the frame up.

**Architecture:** Today `render_tutorial.py` feeds an SRT to ffmpeg's `subtitles=` filter with `force_style=...`. libass gives an SRT a default script resolution of 384×288 and scales every style value by the real height (1080/288 = 3.75×), so `FontSize=22` becomes ~82 px and `MarginV=48` becomes ~180 px — the exact symptoms reported. The fix converts the SRT into an ASS file whose `[Script Info]` declares `PlayResX: 1920 / PlayResY: 1080` and whose `Style:` line is written in real pixels, then burns that ASS with no `force_style`. Style values come from one `CaptionStyle` dataclass with recipe overrides.

**Tech Stack:** Python stdlib, ffmpeg with libass (present: `ffmpeg -filters` lists `subtitles`), Pillow in `.venv` for the pixel-measuring test, Noto Sans (installed here; `fonts-noto-core` added to the Docker worker).

**Spec:** No separate spec. User's words: "the subtitles we render today are too big, and the font is not nice, also located too high on the frame". Verified on `projects/release-3.5-support-tickets/renders/final.mp4` (ffmpeg runtime, 1920×1080): caption x-height block ≈ 80 px, bottom edge ≈ 180 px above the frame bottom, DejaVu Sans with a 7.5 px black outline.

## Design decisions

- **Scope: ffmpeg runtime only.** That is the configured runtime (`tutorial.config.json: render_runtime=ffmpeg`) and the one the user's renders use. The Remotion runtime's `CaptionOverlay` (42 px Space Grotesk, 80 px bottom padding) is already in the target range and is left untouched; if it ever needs tuning, the knobs are `fontSize` and `paddingBottom` in `remotion-composer/src/components/CaptionOverlay.tsx`.
- **Target look** (1080p): Noto Sans Bold, 46 px, white, on a translucent dark box (libass `BorderStyle=4`, one box per line, 12 px padding), no outline, no shadow, bottom-centre, 64 px above the bottom edge, 160 px side margins (max line ≈ 1600 px). Values scale linearly for other heights via `CaptionStyle.scaled(height)`.
- **Font fallback**: libass resolves fonts through fontconfig and silently falls back to a default sans when a family is missing. To keep output deterministic across machines, the Docker worker installs `fonts-noto-core`; locally `fc-match "Noto Sans:bold"` already resolves. `doctor` gets a `warn` when the caption font is not installed.
- **Recipe override**: an optional `caption_style` object in `<name>.tutorial.json` (keys `font`, `size_px`, `margin_bottom_px`, `margin_side_px`, `box_alpha`, `bold`) is merged over the defaults so a tutorial can adjust without code changes.
- **The SRT stays** (`assets/subtitles.srt` is still produced by `SubtitleGen` and recorded in `edit_decisions.subtitles.source`); the ASS is derived from it at burn time (`assets/captions.ass`). Cue text is plain (no tags) — `highlight_style: "none"` — but the converter strips `<...>` tags defensively.

## Global Constraints

- Python 3.10+; no new third-party runtime dependencies (Pillow is test-only and already in `.venv`).
- Output frame stays 1920×1080 yuv420p; ffmpeg command shape in `burn_and_mux` (basename-from-cwd trick for the subtitle filter path) must be preserved — paths with `:` or `'` break lavfi quoting.
- `tests/tutorial/test_tutorial_lib.py` and `tests/mcp/test_circuit_video.py` keep passing.
- Run tests with `.venv/bin/python -m pytest`.
- Commit after each task; commit messages end with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`.

## Review Focus

1. A cue containing `{` / `}` or a backslash (ASS override syntax) must render literally, not be interpreted. (Pinned in Task 1, `test_ass_escapes_override_characters`.)
2. A cue longer than the side-margin width must wrap to two lines inside the box, never overflow the frame. (Pinned in Task 2's pixel test: all bright pixels inside x∈[160,1760].)
3. A two-line cue must still sit above the 64 px bottom margin (box grows upward from the anchor, Alignment=2). (Pinned in Task 2, `test_two_line_cue_stays_above_margin`.)
4. A recipe `caption_style` with a bogus key or a non-numeric size must fail loudly at render start, not produce a silent default. (Pinned in Task 1, `test_caption_style_rejects_unknown_keys`.)
5. Timestamps ≥ 1 hour and millisecond rounding: SRT `01:02:03,456` → ASS `1:02:03.46` (centiseconds, no leading zero on hours). (Pinned in Task 1, `test_srt_to_ass_timestamps`.)

---

### Task 1: `lib/captions.py` — `CaptionStyle` and SRT→ASS converter

**Files:**
- Create: `lib/captions.py`
- Test: `tests/tutorial/test_captions.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class CaptionStyle` with fields `font: str = "Noto Sans"`, `size_px: int = 46`, `bold: bool = True`, `margin_bottom_px: int = 64`, `margin_side_px: int = 160`, `box_alpha: float = 0.55`, `box_pad_px: int = 12`, `text_color: str = "FFFFFF"`, `box_color: str = "101418"`; methods `from_recipe(recipe: Mapping) -> CaptionStyle` (merges `recipe.get("caption_style")`, raises `ValueError` on unknown keys / bad types), `scaled(height: int) -> CaptionStyle` (linear scale from 1080), `ass_style_line() -> str`.
  - `srt_to_ass(srt_text: str, *, size: tuple[int, int], style: CaptionStyle) -> str`
  - `parse_srt(srt_text: str) -> list[tuple[float, float, str]]` (start_s, end_s, text with `\n` between lines)
  - `ass_timestamp(seconds: float) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/tutorial/test_captions.py
"""SRT -> ASS caption conversion with real-pixel styling (no ffmpeg needed here)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from lib import captions as C  # noqa: E402

SRT = """1
00:00:00,000 --> 00:00:02,853
New in version 3.5: your support requests

2
00:00:02,853 --> 00:00:05,705
to the Circuit Auction team, right inside
the backoffice.

3
01:02:03,456 --> 01:02:04,999
<b>Tagged</b> text {with} braces \\ and a backslash
"""


def test_parse_srt():
    cues = C.parse_srt(SRT)
    assert len(cues) == 3
    assert cues[0] == (0.0, 2.853, "New in version 3.5: your support requests")
    assert cues[1][2] == "to the Circuit Auction team, right inside\nthe backoffice."


def test_srt_to_ass_timestamps():
    assert C.ass_timestamp(0.0) == "0:00:00.00"
    assert C.ass_timestamp(2.853) == "0:00:02.85"
    assert C.ass_timestamp(3723.456) == "1:02:03.46"
    assert C.ass_timestamp(4.999) == "0:00:05.00"


def test_ass_header_declares_real_resolution_and_pixel_style():
    ass = C.srt_to_ass(SRT, size=(1920, 1080), style=C.CaptionStyle())
    assert "PlayResX: 1920" in ass and "PlayResY: 1080" in ass
    style = next(l for l in ass.splitlines() if l.startswith("Style: Caption,"))
    fields = style[len("Style: "):].split(",")
    # Format: Name, Fontname, Fontsize, Primary, Secondary, Outline, Back, Bold, Italic,
    # Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline,
    # Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
    assert fields[1] == "Noto Sans" and fields[2] == "46" and fields[7] == "-1"
    assert fields[15] == "4" and fields[16] == "12" and fields[17] == "0"  # box, pad, no shadow
    assert fields[18] == "2" and fields[19:22] == ["160", "160", "64"]
    # BackColour alpha: 0.55 opacity -> 0x73 transparency (&HAABBGGRR, alpha = 255*(1-0.55))
    assert fields[6].upper() == "&H73181410"
    assert fields[3].upper() == "&H00FFFFFF"


def test_ass_events_and_line_breaks():
    ass = C.srt_to_ass(SRT, size=(1920, 1080), style=C.CaptionStyle())
    events = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert events[0] == "Dialogue: 0,0:00:00.00,0:00:02.85,Caption,,0,0,0,,New in version 3.5: your support requests"
    assert events[1].endswith(",,to the Circuit Auction team, right inside\\Nthe backoffice.")


def test_ass_escapes_override_characters():
    ass = C.srt_to_ass(SRT, size=(1920, 1080), style=C.CaptionStyle())
    last = [l for l in ass.splitlines() if l.startswith("Dialogue:")][-1]
    text = last.split(",,", 1)[1]
    assert "<b>" not in text and "Tagged text" in text
    assert "{" not in text and "}" not in text  # braces neutralised
    assert "\\" not in text.replace("\\N", "")  # lone backslashes removed


def test_caption_style_from_recipe_and_scaling():
    s = C.CaptionStyle.from_recipe({"caption_style": {"size_px": 40, "font": "Inter", "bold": False}})
    assert (s.size_px, s.font, s.bold, s.margin_bottom_px) == (40, "Inter", False, 64)
    assert C.CaptionStyle.from_recipe({}) == C.CaptionStyle()
    half = C.CaptionStyle().scaled(540)
    assert (half.size_px, half.margin_bottom_px, half.margin_side_px, half.box_pad_px) == (23, 32, 80, 6)


def test_caption_style_rejects_unknown_keys():
    with pytest.raises(ValueError, match="caption_style"):
        C.CaptionStyle.from_recipe({"caption_style": {"fontsize": 40}})
    with pytest.raises(ValueError, match="size_px"):
        C.CaptionStyle.from_recipe({"caption_style": {"size_px": "big"}})
    with pytest.raises(ValueError, match="box_alpha"):
        C.CaptionStyle.from_recipe({"caption_style": {"box_alpha": 1.5}})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/tutorial/test_captions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'lib.captions'`

- [ ] **Step 3: Implement `lib/captions.py`**

```python
"""Burned-in caption styling for the ffmpeg tutorial runtime.

Why ASS and not `subtitles=x.srt:force_style=...`: libass gives an SRT a
default PlayRes of 384x288 and scales every style value by video_height/288.
At 1080p that turns FontSize=22 into ~82 px and MarginV=48 into ~180 px — the
"too big / too high" captions. Declaring PlayResX/PlayResY = the real frame
size makes every value below a real pixel.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, fields, replace
from typing import Any, Mapping

_SRT_TIME = re.compile(r"(\d+):(\d\d):(\d\d)[,.](\d{1,3})")
_TAG = re.compile(r"<[^>]+>")
_ALLOWED_RECIPE_KEYS = {
    "font": str, "size_px": int, "bold": bool, "margin_bottom_px": int,
    "margin_side_px": int, "box_alpha": float, "box_pad_px": int,
    "text_color": str, "box_color": str,
}


@dataclass(frozen=True)
class CaptionStyle:
    font: str = "Noto Sans"
    size_px: int = 46
    bold: bool = True
    margin_bottom_px: int = 64
    margin_side_px: int = 160
    box_alpha: float = 0.55        # box opacity 0..1
    box_pad_px: int = 12
    text_color: str = "FFFFFF"     # RRGGBB
    box_color: str = "101418"      # RRGGBB

    @classmethod
    def from_recipe(cls, recipe: Mapping[str, Any]) -> "CaptionStyle":
        raw = recipe.get("caption_style") or {}
        if not isinstance(raw, Mapping):
            raise ValueError("recipe caption_style must be an object")
        unknown = set(raw) - set(_ALLOWED_RECIPE_KEYS)
        if unknown:
            raise ValueError(f"unknown caption_style keys: {', '.join(sorted(unknown))}")
        clean: dict[str, Any] = {}
        for key, val in raw.items():
            typ = _ALLOWED_RECIPE_KEYS[key]
            if typ is float and isinstance(val, int) and not isinstance(val, bool):
                val = float(val)
            if typ is int and isinstance(val, bool):
                raise ValueError(f"caption_style.{key} must be an integer")
            if not isinstance(val, typ):
                raise ValueError(f"caption_style.{key} must be {typ.__name__}")
            clean[key] = val
        if "box_alpha" in clean and not 0.0 <= clean["box_alpha"] <= 1.0:
            raise ValueError("caption_style.box_alpha must be between 0 and 1")
        return replace(cls(), **clean)

    def scaled(self, height: int) -> "CaptionStyle":
        f = height / 1080.0
        return replace(
            self,
            size_px=max(1, round(self.size_px * f)),
            margin_bottom_px=round(self.margin_bottom_px * f),
            margin_side_px=round(self.margin_side_px * f),
            box_pad_px=round(self.box_pad_px * f),
        )

    def ass_style_line(self) -> str:
        primary = _ass_color(self.text_color, 0.0)
        back = _ass_color(self.box_color, 1.0 - self.box_alpha)
        return (
            "Style: Caption," f"{self.font},{self.size_px},{primary},&H000000FF,&H00000000,{back},"
            f"{-1 if self.bold else 0},0,0,0,100,100,0,0,"
            f"4,{self.box_pad_px},0,2,{self.margin_side_px},{self.margin_side_px},{self.margin_bottom_px},1"
        )


def _ass_color(rrggbb: str, transparency: float) -> str:
    """ASS colours are &HAABBGGRR with AA = transparency (00 opaque, FF invisible)."""
    rr, gg, bb = rrggbb[0:2], rrggbb[2:4], rrggbb[4:6]
    aa = max(0, min(255, round(255 * transparency)))
    return f"&H{aa:02X}{bb}{gg}{rr}".upper()


def ass_timestamp(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def parse_srt(srt_text: str) -> list[tuple[float, float, str]]:
    cues: list[tuple[float, float, str]] = []
    for block in re.split(r"\n\s*\n", srt_text.strip().replace("\r\n", "\n")):
        lines = [l for l in block.split("\n")]
        if len(lines) < 2:
            continue
        # Line 0 is the index (may be absent in sloppy SRTs); find the timing line.
        t_idx = 1 if "-->" in lines[1] else (0 if "-->" in lines[0] else -1)
        if t_idx < 0:
            continue
        times = _SRT_TIME.findall(lines[t_idx])
        if len(times) < 2:
            continue
        start, end = (_to_seconds(t) for t in times[:2])
        text = "\n".join(l.rstrip() for l in lines[t_idx + 1:]).strip()
        if text:
            cues.append((start, end, text))
    return cues


def _to_seconds(t: tuple[str, str, str, str]) -> float:
    h, m, s, ms = t
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def _ass_text(text: str) -> str:
    text = _TAG.sub("", text)
    text = text.replace("\\", "")           # a lone backslash starts an override
    text = text.replace("{", "(").replace("}", ")")  # braces delimit override blocks
    return text.replace("\n", "\\N")


def srt_to_ass(srt_text: str, *, size: tuple[int, int], style: CaptionStyle) -> str:
    w, h = size
    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {w}",
        f"PlayResY: {h}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        style.ass_style_line(),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = [
        f"Dialogue: 0,{ass_timestamp(s)},{ass_timestamp(e)},Caption,,0,0,0,,{_ass_text(t)}"
        for s, e, t in parse_srt(srt_text)
    ]
    return "\n".join(head + events) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial/test_captions.py -v`
Expected: all PASS. (If `test_ass_header...` fails on the alpha byte, check: 255 × (1 − 0.55) = 114.75 → rounds to 115 = `0x73`.)

- [ ] **Step 5: Commit**

```bash
git add lib/captions.py tests/tutorial/test_captions.py
git commit -m "feat(tutorial): ASS caption builder with real-pixel styling

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 2: Burn the ASS in `render_tutorial.py` and prove the pixels

**Files:**
- Modify: `render_tutorial.py` — remove `_srt_style` (lines 186-190), change `burn_and_mux` (lines 193-215), add `_build_ass`, call it in `render_ffmpeg_assembly` (line ~443)
- Test: `tests/tutorial/test_caption_burn.py`

**Interfaces:**
- Consumes: `lib.captions.CaptionStyle`, `lib.captions.srt_to_ass` (Task 1).
- Produces: `render_tutorial.build_ass_file(srt: Path, out: Path, *, recipe: dict, target: tuple[int, int]) -> Path`; `burn_and_mux(video, audio, subs: Optional[Path], out, target, recipe)` now expects an `.ass` path (or None).

- [ ] **Step 1: Write the failing test** (pixel-level, uses ffmpeg + Pillow; skipped where missing)

```python
# tests/tutorial/test_caption_burn.py
"""Burn a caption onto a synthetic 1080p frame and measure where the text lands."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import render_tutorial as RT  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg required")
Image = pytest.importorskip("PIL.Image")


def _burn_frame(tmp_path: Path, srt_text: str, recipe: dict) -> "Image.Image":
    srt = tmp_path / "subs.srt"
    srt.write_text(srt_text)
    ass = RT.build_ass_file(srt, tmp_path / "captions.ass", recipe=recipe, target=(1920, 1080))
    png = tmp_path / "frame.png"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x2b3a4a:s=1920x1080:d=1",
         "-vf", f"subtitles={ass.name}", "-frames:v", "1", str(png)],
        cwd=str(tmp_path), check=True,
    )
    return Image.open(png).convert("L")


def _bright_bbox(im) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of pixels brighter than 200 (the white glyphs)."""
    w, h = im.size
    px = im.load()
    xs, ys = [], []
    for y in range(h):
        for x in range(0, w, 2):
            if px[x, y] > 200:
                xs.append(x)
                ys.append(y)
    assert xs, "no caption pixels found"
    return min(xs), min(ys), max(xs), max(ys)


ONE_LINE = "1\n00:00:00,000 --> 00:00:05,000\nOpen the Sales area and pick the auction\n"
LONG = ("1\n00:00:00,000 --> 00:00:05,000\n"
        "Each row is a ticket with its status and description. Click it to read the full conversation now\n")


def test_single_line_caption_size_and_position(tmp_path):
    left, top, right, bottom = _bright_bbox(_burn_frame(tmp_path, ONE_LINE, {}))
    text_h = bottom - top
    assert 30 <= text_h <= 60, f"glyph block {text_h}px tall; want ~46px font"  # was ~80
    assert 1080 - bottom <= 110, f"text bottom is {1080 - bottom}px above the edge; want < 110"  # was ~180
    assert 1080 - bottom >= 60
    assert left >= 160 and right <= 1760
    assert abs((left + right) / 2 - 960) < 40  # centred


def test_two_line_cue_stays_above_margin(tmp_path):
    left, top, right, bottom = _bright_bbox(_burn_frame(tmp_path, LONG, {}))
    assert left >= 160 and right <= 1760
    assert bottom <= 1080 - 60
    assert 90 <= bottom - top <= 140  # two lines of ~46px with leading


def test_recipe_override_changes_size(tmp_path):
    _, top, _, bottom = _bright_bbox(_burn_frame(tmp_path, ONE_LINE, {"caption_style": {"size_px": 60}}))
    assert bottom - top > 45
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/tutorial/test_caption_burn.py -v`
Expected: FAIL with `AttributeError: module 'render_tutorial' has no attribute 'build_ass_file'`

- [ ] **Step 3: Modify `render_tutorial.py`**

Add import: `from lib.captions import CaptionStyle, srt_to_ass  # noqa: E402`.

Delete `_srt_style`. Add:

```python
def build_ass_file(srt: Path, out: Path, *, recipe: dict, target: tuple[int, int]) -> Path:
    """Derive the burn-in ASS (real-pixel style, PlayRes = frame) from the SRT."""
    style = CaptionStyle.from_recipe(recipe).scaled(target[1])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(srt_to_ass(srt.read_text(), size=target, style=style))
    return out
```

Change `burn_and_mux` so the parameter is `subs: Optional[Path]` and the filter is:

```python
    if subs and subs.exists():
        cwd = str(subs.parent)
        vf += f",subtitles={subs.name}"
```

(The ASS carries its own style; no `force_style`.) In `render_ffmpeg_assembly`, right after `srt = _build_srt(steps, project_dir)`:

```python
    ass = build_ass_file(srt, assets / "captions.ass", recipe=recipe, target=target) if srt else None
```

and pass `ass` (not `srt`) to `burn_and_mux`. Keep returning `srt` for `edit_decisions`.

Validate the recipe style early so a typo fails before the capture: in `main()`, right after `lang = recipe.get("lang", "en")`, add:

```python
    try:
        CaptionStyle.from_recipe(recipe)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/tutorial/test_caption_burn.py tests/tutorial/test_captions.py -v`
Expected: all PASS. If `test_single_line_caption_size_and_position` fails on `text_h`, open `frame.png` from the tmp dir (`pytest --basetemp=/tmp/claude-1000/.../scratchpad/burn`) and look before touching the thresholds.

- [ ] **Step 5: Visual check on a real render (no Cypress)**

Run (reuse the existing capture + manifest of the support-tickets render):

```bash
ls projects/release-3.5-support-tickets/assets/video/ projects/release-3.5-support-tickets/assets/*.json
.venv/bin/python render_tutorial.py --tutorial support-tickets \
  --client-dir ../circuitauction-backoffice/client --project-id caption-check \
  --offline-narration --capture projects/release-3.5-support-tickets/assets/video/capture.mp4 \
  --manifest <manifest json printed above>
ffmpeg -y -v error -ss 18 -i projects/caption-check/renders/final.mp4 -frames:v 1 /tmp/claude-1000/-media-bl-Disk2-htdocs-OpenMontage/6919352c-af15-4053-8d22-b2cc48f2cdcc/scratchpad/after18.png
```

Expected: the frame shows a single-line caption ~46 px tall in a dark translucent box ~64 px above the bottom, Noto Sans Bold. Compare with the "before" frame at `scratchpad/real18.png`.

- [ ] **Step 6: Commit**

```bash
git add render_tutorial.py tests/tutorial/test_caption_burn.py
git commit -m "fix(tutorial): burn captions from a real-pixel ASS (smaller, boxed, lower)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 3: Font availability — Docker worker and `doctor`

**Files:**
- Modify: `deploy/Dockerfile` line 28 (apt list)
- Modify: `mcp_servers/circuit_video/service.py` `doctor` (after the ffmpeg/ffprobe checks)
- Modify: `tutorialctl.py` `cmd_doctor` (same check)
- Test: `tests/mcp/test_circuit_video.py` (append)

**Interfaces:**
- Produces: `service.caption_font_installed(family: str) -> Optional[bool]` (None when `fc-list` is unavailable).

- [ ] **Step 1: Write the failing test**

```python
from circuit_video.service import caption_font_installed  # noqa: E402


def test_caption_font_check(monkeypatch):
    import subprocess as sp

    class R:
        returncode = 0
        stdout = "Noto Sans\nDejaVu Sans\n"

    monkeypatch.setattr(sp, "run", lambda *a, **k: R())
    assert caption_font_installed("Noto Sans") is True
    assert caption_font_installed("Inter") is False
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert caption_font_installed("Noto Sans") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/mcp/test_circuit_video.py -v -k caption_font`
Expected: FAIL with `ImportError: cannot import name 'caption_font_installed'`

- [ ] **Step 3: Implement**

In `service.py`:

```python
def caption_font_installed(family: str) -> Optional[bool]:
    """True/False via fontconfig; None when fc-list is not available."""
    if not shutil.which("fc-list"):
        return None
    try:
        r = subprocess.run(["fc-list", ":", "family"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    families = {part.strip() for line in r.stdout.splitlines() for part in line.split(",")}
    return family in families
```

In `doctor`, after the node/npx loop:

```python
    font = "Noto Sans"
    have_font = caption_font_installed(font)
    if have_font is None:
        add("caption font", "warn", f"fc-list not available; cannot verify {font!r}")
    else:
        add("caption font", "ok" if have_font else "warn",
            f"{font!r} {'installed' if have_font else 'missing — captions fall back to the default sans (install fonts-noto-core)'}")
```

`tutorialctl.py` `cmd_doctor`: same three lines, inline (it does not import the MCP package), using `subprocess.run(["fc-list", ":", "family"], ...)`.

`deploy/Dockerfile` line 28: add `fonts-noto-core` after `fonts-dejavu-core`.

- [ ] **Step 4: Run tests and verify**

Run: `.venv/bin/python -m pytest tests/mcp/test_circuit_video.py -v`
Expected: all PASS.
Run: `.venv/bin/python tutorialctl.py doctor | grep -i "caption font"` → `ok`.

- [ ] **Step 5: Commit**

```bash
git add deploy/Dockerfile mcp_servers/circuit_video/service.py tutorialctl.py tests/mcp/test_circuit_video.py
git commit -m "chore(tutorial): check/install the caption font (Noto Sans)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task 4: Docs

**Files:**
- Modify: `mcp_servers/circuit_video/README.md`, `.agents/skills/circuit-video/SKILL.md`

- [ ] **Step 1:** Add to the README:

```markdown
## Captions (ffmpeg runtime)

Burned-in captions use `lib/captions.py`: Noto Sans Bold 46 px on a translucent
box, 64 px above the bottom edge at 1080p. Override per tutorial in
`<name>.tutorial.json`:

```json
"caption_style": {"size_px": 42, "margin_bottom_px": 72, "font": "Noto Sans", "box_alpha": 0.5}
```

Keys: `font`, `size_px`, `bold`, `margin_bottom_px`, `margin_side_px`,
`box_alpha` (0–1), `box_pad_px`, `text_color`, `box_color` (RRGGBB).
```

Add one line to `SKILL.md` under the pipeline list: `Captions: SRT from subtitle_gen → ASS with real-pixel style (lib/captions.py); recipe caption_style overrides.`

- [ ] **Step 2: Commit**

```bash
git add mcp_servers/circuit_video/README.md .agents/skills/circuit-video/SKILL.md
git commit -m "docs(tutorial): caption style and recipe overrides

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```
