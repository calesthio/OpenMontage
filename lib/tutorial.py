"""Shared helpers for the Cypress → tutorial-video pipeline.

Used by author_tutorial.py and render_tutorial.py. Everything here is pure and
deterministic (no browser, no ttsd, no ffmpeg) except make_title_card (Pillow),
so the risky logic — caption timing, narration placement, edit_decisions
shape — is unit-testable in isolation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Step:
    """One narratable beat, recorded by cy.tutorialStep into the manifest."""

    index: int
    narration: str
    t_ms: int = 0
    action: str = "note"
    target: Optional[str] = None
    region: Optional[dict] = None
    importance: str = "normal"
    suggested_treatment: str = "realtime"
    marker: Optional[dict] = None
    # Filled during render once the capture is measured/normalized:
    video_start_s: float = 0.0
    duration_s: float = 0.0

    @property
    def video_end_s(self) -> float:
        return self.video_start_s + self.duration_s


def steps_from_manifest(manifest: dict) -> list[Step]:
    """Build ordered Step objects from a Cypress tutorial manifest sidecar."""
    out: list[Step] = []
    for s in sorted(manifest.get("steps", []), key=lambda x: x.get("index", 0)):
        out.append(
            Step(
                index=int(s.get("index", 0)),
                narration=(s.get("narration") or "").strip(),
                t_ms=int(s.get("t_ms", 0)),
                action=s.get("action", "note"),
                target=s.get("target"),
                region=s.get("region"),
                importance=s.get("importance", "normal"),
                suggested_treatment=s.get("suggested_treatment", "realtime"),
                marker=s.get("marker"),
            )
        )
    return out


def apply_durations(steps: list[Step], durations_ms: list[int]) -> None:
    """Attach per-step narration durations (ms) to steps, in index order."""
    for st in steps:
        if 0 <= st.index < len(durations_ms):
            st.duration_s = max(0.0, durations_ms[st.index] / 1000.0)


def assign_start_times(
    steps: list[Step],
    marker_times_s: Optional[list[float]] = None,
    lead_offset_s: float = 0.0,
) -> None:
    """Set each step's start time within the (normalized) body video.

    Primary path: marker_times_s — the true per-step times recovered from the
    drift markers by normalize_capture (already relative to the trimmed start).
    Fallback: derive from the manifest wall-clock t_ms plus a fixed lead offset
    (less accurate over long specs; see the drift note in the plan).
    """
    if marker_times_s and len(marker_times_s) == len(steps):
        for st, t in zip(steps, marker_times_s):
            st.video_start_s = max(0.0, float(t))
        return
    for st in steps:
        st.video_start_s = max(0.0, st.t_ms / 1000.0 + lead_offset_s)


def split_words(text: str) -> list[str]:
    return re.findall(r"\S+", text or "")


def build_subtitle_segments(steps: list[Step]) -> list[dict]:
    """Synthesize word-level caption segments from authored narration + timing.

    No transcriber / Whisper / torch: the words are spread evenly across each
    step's [video_start, video_start+duration] window. subtitle_gen consumes
    these exactly like real transcriber output.
    """
    segments: list[dict] = []
    for st in steps:
        words = split_words(st.narration)
        if not words or st.duration_s <= 0:
            continue
        n = len(words)
        start = st.video_start_s
        dur = st.duration_s
        wlist = []
        for i, w in enumerate(words):
            wlist.append(
                {
                    "word": w,
                    "start": round(start + dur * i / n, 3),
                    "end": round(start + dur * (i + 1) / n, 3),
                }
            )
        segments.append(
            {
                "text": st.narration,
                "start": round(start, 3),
                "end": round(start + dur, 3),
                "words": wlist,
            }
        )
    return segments


def build_edit_decisions(
    steps: list[Step],
    capture_path: str,
    body_duration_s: float,
    *,
    intro_s: float,
    outro_s: float,
    recipe: dict,
    narration_audio_path: Optional[str] = None,
    subtitles_path: Optional[str] = None,
    music_path: Optional[str] = None,
    render_runtime: str = "ffmpeg",
) -> dict:
    """Build an edit_decisions artifact.

    v1 renders via the self-contained ffmpeg assembly in render_tutorial.py, but
    we persist a valid edit_decisions so the run is legible on the Backlot board
    and the richer Remotion "Explainer" path (renderer_family="screen-demo") is a
    drop-in later. Times are on the FINAL timeline (intro offsets the body).
    """
    body_offset = intro_s
    # Scene-type hints (hero_title for intro/outro) live in metadata; the schema's
    # cut object does not allow a `type` field — the Remotion path maps these when
    # it consumes edit_decisions.
    cuts = [
        {
            "id": "intro",
            "source": "intro_card",
            "in_seconds": 0.0,
            "out_seconds": intro_s,
            "layer": "primary",
            "reason": "Title card (hero_title)",
        },
        {
            "id": "body",
            "source": capture_path,
            "in_seconds": 0.0,
            "out_seconds": body_duration_s,
            "layer": "primary",
            "reason": "Recorded app walkthrough",
        },
        {
            "id": "outro",
            "source": "outro_card",
            "in_seconds": 0.0,
            "out_seconds": outro_s,
            "layer": "primary",
            "reason": "End card (hero_title)",
        },
    ]

    overlays = []
    for st in steps:
        if not st.narration:
            continue
        overlays.append(
            {
                "asset_id": f"section_title_{st.index}",
                "start_seconds": round(body_offset + st.video_start_s, 3),
                "end_seconds": round(body_offset + st.video_end_s, 3),
                "position": {"x": 0.5, "y": 0.86, "width": 0.9, "height": 0.1},
                "opacity": 1.0,
            }
        )

    narration_segments = [
        {
            "asset_id": f"narration_{st.index}",
            "start_seconds": round(body_offset + st.video_start_s, 3),
            "end_seconds": round(body_offset + st.video_end_s, 3),
        }
        for st in steps
        if st.narration and st.duration_s > 0
    ]

    audio: dict[str, Any] = {"narration": {"segments": narration_segments}}
    if narration_audio_path:
        audio["narration"]["src"] = narration_audio_path
    if music_path:
        audio["music"] = {
            "asset_id": "music",
            "src": music_path,
            "volume": 0.18,
            "fade_in_seconds": 1.0,
            "fade_out_seconds": 1.5,
            "ducking": True,
        }

    return {
        "version": "1.0",
        "renderer_family": "screen-demo",
        "render_runtime": render_runtime,
        "composition_mode": "templated",
        "cuts": cuts,
        "overlays": overlays,
        "audio": audio,
        "subtitles": {
            "enabled": True,
            "style": recipe.get("subtitle_style", "word_by_word"),
            "source": subtitles_path or "",
            "position": "bottom-center",
        },
        "metadata": {
            "origin": "cypress-tutorial",
            "proposal_render_runtime": render_runtime,
            "intro_seconds": intro_s,
            "outro_seconds": outro_s,
            "body_duration_seconds": round(body_duration_s, 3),
            "scene_types": {"intro": "hero_title", "outro": "hero_title"},
        },
    }


# --- v2: Remotion ScreencastScene (animated callouts/zoom over the capture) ---

def build_screencast_scene(
    steps: list[Step],
    capture_path: str,
    source_in_seconds: float = 0.0,
    size: tuple[int, int] = (1920, 1080),
    zoom_scale: float = 1.5,
    accent: str = "#F59E0B",
) -> dict:
    """Build the ScreencastScene cut payload from tutorial steps.

    Overlay/zoom/cursor times are **body-relative** (0 at the capture start),
    which is what a Remotion Sequence expects for a scene. Uses each step's real
    normalized bounding box (`region`) so callouts land on the actual element:
      - highlight / zoom / click steps -> a pulsing highlight_box for the window
      - zoom steps -> a zoom-to-highlight window on the region
      - click steps -> a click_pulse
      - every step with a region -> a cursor waypoint at its start
    """
    overlays: list[dict] = []
    cursor: list[dict] = []
    zoom: list[dict] = []
    for st in steps:
        if not st.region:
            continue
        r = st.region
        region = {"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"]}
        cx = round(r["x"] + r["w"] / 2, 4)
        cy = round(r["y"] + r["h"] / 2, 4)
        start = round(st.video_start_s, 3)
        end = round(st.video_end_s if st.duration_s > 0 else st.video_start_s + 2.0, 3)
        cursor.append({"atSeconds": start, "to": [cx, cy]})
        treat = st.suggested_treatment
        if treat in ("highlight", "zoom") or st.action == "click":
            overlays.append({"kind": "highlight_box", "atSeconds": start, "untilSeconds": end, "region": region})
        if treat == "zoom":
            zoom.append({"atSeconds": start, "untilSeconds": end, "region": region, "scale": zoom_scale})
        if st.action == "click":
            overlays.append({"kind": "click_pulse", "atSeconds": start, "untilSeconds": round(start + 0.5, 3), "at": [cx, cy]})
    return {
        "type": "screencast_scene",
        "source": capture_path,
        "source_in_seconds": source_in_seconds,
        "screencastSize": {"width": size[0], "height": size[1]},
        "screencastOverlays": overlays,
        "screencastCursor": cursor,
        "screencastZoom": zoom,
        "accentColor": accent,
    }


def build_remotion_props(
    steps: list[Step],
    capture_path: str,
    body_duration_s: float,
    recipe: dict,
    *,
    intro_s: float,
    outro_s: float,
    narration_audio_path: Optional[str] = None,
    music_path: Optional[str] = None,
    size: tuple[int, int] = (1920, 1080),
    with_callouts: bool = True,
    zoom_scale: float = 1.5,
) -> dict:
    """Full Explainer composition props for the v2 (Remotion) render path.

    cuts = [hero_title intro] + [screencast_scene body w/ callouts] + [hero_title outro];
    captions are word-level on the FINAL timeline (offset by the intro); narration
    + music go on the audio track (the capture itself is muted). Render with:
        cd remotion-composer && npx remotion render src/index.tsx Explainer out.mp4 --props props.json
    """
    body_offset = intro_s
    body_end = round(body_offset + body_duration_s, 3)

    body_cut: dict[str, Any] = {
        "id": "body",
        "in_seconds": body_offset,
        "out_seconds": body_end,
        "source": capture_path,
        "source_in_seconds": 0,
    }
    if with_callouts:
        scene = build_screencast_scene(steps, capture_path, size=size, zoom_scale=zoom_scale)
        body_cut["type"] = "screencast_scene"
        for k in ("screencastSize", "screencastOverlays", "screencastCursor", "screencastZoom", "accentColor"):
            body_cut[k] = scene[k]

    cuts = [
        {
            "id": "intro", "type": "hero_title", "in_seconds": 0.0, "out_seconds": intro_s,
            "text": recipe.get("intro_text", recipe.get("title", "")),
            "heroSubtitle": recipe.get("intro_subtitle", ""),
        },
        body_cut,
        {
            "id": "outro", "type": "hero_title", "in_seconds": body_end,
            "out_seconds": round(body_end + outro_s, 3),
            "text": recipe.get("outro_text", "Thanks for watching"),
            "heroSubtitle": recipe.get("outro_subtitle", ""),
        },
    ]

    captions = []
    for st in steps:
        words = split_words(st.narration)
        if not words or st.duration_s <= 0:
            continue
        n = len(words)
        start = body_offset + st.video_start_s
        for i, w in enumerate(words):
            captions.append({
                "word": w,
                "startMs": int(round((start + st.duration_s * i / n) * 1000)),
                "endMs": int(round((start + st.duration_s * (i + 1) / n) * 1000)),
            })

    props: dict[str, Any] = {"cuts": cuts, "captions": captions}
    audio: dict[str, Any] = {}
    if narration_audio_path:
        audio["narration"] = {"src": narration_audio_path, "volume": 1.0}
    if music_path:
        audio["music"] = {
            "src": music_path, "volume": 0.18,
            "fadeInSeconds": 1.0, "fadeOutSeconds": 1.5,
        }
    if audio:
        props["audio"] = audio
    return props


# --- Title cards (Pillow) --------------------------------------------------

_FONT_REGULAR = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial.ttf",
]
_FONT_BOLD = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def _font(size: int, bold: bool = False):
    from PIL import ImageFont

    for p in _FONT_BOLD if bold else _FONT_REGULAR:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_centered(draw, text, font, cx, y, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)
    return bbox[3] - bbox[1]


def make_title_card(
    path: str,
    title: str,
    subtitle: str = "",
    size: tuple[int, int] = (1920, 1080),
    bg: tuple[int, int, int] = (15, 18, 22),
    fg: tuple[int, int, int] = (245, 247, 250),
    accent: tuple[int, int, int] = (120, 170, 255),
) -> str:
    """Render a simple centered title/subtitle card PNG. Returns the path."""
    from PIL import Image, ImageDraw

    W, H = size
    img = Image.new("RGB", size, bg)
    d = ImageDraw.Draw(img)
    cx = W / 2

    title_font = _font(int(H * 0.09), bold=True)
    sub_font = _font(int(H * 0.042))

    th = _draw_centered(d, title, title_font, cx, H * 0.40, fg)
    # accent rule under the title
    rule_w = int(W * 0.12)
    ry = int(H * 0.40 + th + H * 0.03)
    d.rectangle([cx - rule_w / 2, ry, cx + rule_w / 2, ry + 4], fill=accent)
    if subtitle:
        _draw_centered(d, subtitle, sub_font, cx, ry + H * 0.04, (190, 198, 210))

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
