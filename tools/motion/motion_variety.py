#!/usr/bin/env python3
"""tools/motion/motion_variety.py — motion variety for still images (M5).

Builds ffmpeg filter strings for slow pan/zoom (multiple easings), detail
crops, parallax on stills, animated map/timeline cards, chapter cards, and
subtitle styles. Also lints per-segment variation: no two consecutive
identical moves. No network, no paid routes, no AI upscaling.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def ease_curve(name: str = "linear") -> Callable[[float], float]:
    name = (name or "linear").lower()
    if name == "linear":
        return lambda t: t
    if name == "easein":
        return lambda t: t * t
    if name == "easeout":
        return lambda t: 1 - (1 - t) * (1 - t)
    if name == "easeinout":
        return lambda t: 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2
    # unknown -> linear (fail-safe deterministic default)
    return lambda t: t


def build_pan_zoom(duration_s: float, easing: str = "easeinout",
                   direction: str = "in", start_scale: float = 1.0,
                   end_scale: float = 1.15, fps: int = 30) -> str:
    """ffmpeg zoompan filter for a slow pan/zoom over a still image.

    direction: "in" (zoom in) or "out" (zoom out). start/end scale define the
    range; easing interpolates the zoom over duration.
    """
    easing = (easing or "linear").lower()
    if direction == "out":
        start_scale, end_scale = end_scale, start_scale
    f = ease_curve(easing)
    frames = max(1, int(duration_s * 25))
    # progress fraction over the duration, clamped to [0,1]
    prog = f"clamp(onframe/{frames},0,1)"
    # z(t) = start_scale + (end_scale-start_scale)*ease(progress)
    # Express ease via sampled ease_curve into a small lookup is not possible
    # in a single ffmpeg expr; use linear-interp of the ease function name is
    # out of scope. We implement zoom as ease-in/out via polynomial expr:
    if easing == "easein":
        zexpr = f"{start_scale}+({end_scale}-{start_scale})*pow({prog},2)"
    elif easing == "easeout":
        zexpr = f"{start_scale}+({end_scale}-{start_scale})*(1-pow(1-{prog},2))"
    elif easing == "easeinout":
        zexpr = (f"{start_scale}+({end_scale}-{start_scale})*"
                 f"(if(lt({prog},0.5),2*pow({prog},2),1-pow(2-2*{prog},2)/2))")
    else:
        zexpr = f"{start_scale}+({end_scale}-{start_scale})*{prog}"
    # slow pan across the frame proportional to progress
    xexpr = f"(iw-iw/{zexpr})*{prog}/2"
    yexpr = f"(ih-ih/{zexpr})*{prog}/2"
    d = int(duration_s * 25)  # zoompan duration in frames (25fps base)
    return (f"zoompan=z='{zexpr}':x='{xexpr}':y='{yexpr}':d={d}:s=1280x720:fps={fps}")


def build_detail_crop(duration_s: float, crop_box: tuple,
                      fps: int = 30) -> str:
    """Crop to a sub-box of a still (detail crop). crop_box = (x0,y0,x1,y1) in 0..1."""
    x0, y0, x1, y1 = crop_box
    return (f"crop=iw*{x1-x0}:ih*{y1-y0}:iw*{x0}:ih*{y0},"
            f"scale=1280:720,fps={fps}")


def build_parallax(duration_s: float, layers: int = 2, drift: float = 0.04,
                   fps: int = 30) -> str:
    """Simple parallax: multiple scaled copies drifting at different rates."""
    filters = []
    for i in range(layers):
        scale = 1.0 + i * 0.12
        dx = drift * (i + 1)
        filters.append(
            f"[0:v]scale=iw*{scale}:ih*{scale}[base{i}];"
            f"[base{i}]crop=iw:ih:({dx}*onframe)%(iw*{scale}-iw):0[m{i}]"
        )
    return ";".join(filters) + f";[m{layers-1}]fps={fps}[v]"


def build_chapter_card(title: str, subtitle: str, duration_s: float) -> Dict[str, Any]:
    """Chapter card spec (rendered by the composer; here a declarative spec)."""
    return {
        "kind": "chapter_card",
        "title": title,
        "subtitle": subtitle,
        "duration": float(duration_s),
        "layout": "centered_title_card",
        "style": "minimal",
    }


def build_subtitle_style(name: str = "default") -> Dict[str, Any]:
    styles = {
        "default": {"font": "DejaVuSans", "size": 24, "color": "ffffff",
                    "align": "bottom", "margin_v": 60, "outline": 1},
        "chapter": {"font": "DejaVuSans-Bold", "size": 36, "color": "ffffff",
                    "align": "center", "margin_v": 120, "outline": 2},
    }
    return dict(styles.get(name, styles["default"]))


def lint_variation(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flag two consecutive segments with identical move (type+easing+direction).

    Returns a list of problem dicts {index, segment, reason}.
    """
    problems: List[Dict[str, Any]] = []
    prev_key = None
    for i, seg in enumerate(segments):
        move = seg.get("move")
        key = (move, seg.get("easing"), seg.get("direction"))
        if prev_key is not None and key == prev_key and move is not None:
            problems.append({
                "index": i,
                "segment": seg,
                "reason": f"consecutive identical move: {move} {seg.get('easing')} {seg.get('direction')}",
            })
        prev_key = key
    return problems
