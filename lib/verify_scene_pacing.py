"""Verify that a TerminalScene `steps` list paces with narration cues.

Use from any build_composition.py or synthetic-UI builder:

    from lib.verify_scene_pacing import trace, assert_alignment

    trace(install_steps, scene_start=50.0)
    assert_alignment(
        install_steps,
        scene_start=50.0,
        scene_end=110.0,
        narration_cues=[
            (57.0,  "seg07 Clone the repo"),
            (65.5,  "seg08 Run make setup"),
            (83.0,  "seg09 Open the folder"),
            (92.0,  "seg10 agent reads guide"),
        ],
        tolerance=1.0,
    )

The tracer mimics the frame math inside TerminalScene.tsx so video-time
estimates are exact to 1/fps. Fails loudly if any narration cue has no
matching command/output within `tolerance` seconds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


def step_duration(step: dict[str, Any], fps: int = 30) -> float:
    """Return the cursor-advancement for a single step (frame-accurate).

    Pills DO NOT advance the cursor — they're non-blocking overlays.
    """
    k = step["kind"]
    if k == "cmd":
        # TerminalScene uses JavaScript text.length (UTF-16 code units).
        text_length = len(step["text"].encode("utf-16-le", errors="surrogatepass")) // 2
        type_frames = math.ceil(text_length * step.get("typeSpeed", 0.035) * fps)
        hold_frames = math.ceil(step.get("holdSeconds", 0.3) * fps)
        return (type_frames + hold_frames) / fps
    if k == "out":
        reveal_frames = max(2, math.ceil(0.08 * fps))
        hold_frames = math.ceil(step.get("holdSeconds", 0.15) * fps)
        return (reveal_frames + hold_frames) / fps
    if k == "pause":
        return math.ceil(step["seconds"] * fps) / fps
    if k == "pill":
        return 0.0
    raise ValueError(f"Unknown step kind: {k!r}")


@dataclass
class Landmark:
    video_time: float
    kind: str
    text: str


def trace(steps: list[dict[str, Any]], scene_start: float = 0.0, fps: int = 30, *, quiet: bool = False) -> list[Landmark]:
    """Walk the step list and print a video-time landmark for each visible event.

    Returns the list of landmarks (useful for alignment checks).
    """
    cursor = 0.0
    out: list[Landmark] = []
    for s in steps:
        k = s["kind"]
        vt = round(cursor + scene_start, 2)
        if k in ("cmd", "out", "pill"):
            text = s.get("text", "")
            out.append(Landmark(video_time=vt, kind=k.upper(), text=text))
            if not quiet:
                prefix = {"CMD": "CMD  ", "OUT": "OUT  ", "PILL": "PILL "}[k.upper()]
                print(f"  {vt:7.2f}s  {prefix}{text[:60]}")
        cursor += step_duration(s, fps)

    end_vt = round(cursor + scene_start, 2)
    if not quiet:
        print(f"  {end_vt:7.2f}s  -- steps end --")
    return out


def assert_alignment(
    steps: list[dict[str, Any]],
    scene_start: float,
    scene_end: float,
    narration_cues: list[tuple[float, str]],
    *,
    tolerance: float = 1.0,
    fps: int = 30,
) -> None:
    """Validate that every narration cue has a visual landmark within tolerance.

    Also checks that total step duration does not overflow scene_end.
    Raises AssertionError on any mismatch.
    """
    landmarks = trace(steps, scene_start, fps, quiet=True)
    errors: list[str] = []

    for cue_time, cue_desc in narration_cues:
        # Find closest landmark by video-time
        if not landmarks:
            errors.append(f"cue {cue_time:.2f}s ({cue_desc}): no landmarks at all")
            continue
        closest = min(landmarks, key=lambda lm: abs(lm.video_time - cue_time))
        delta = closest.video_time - cue_time
        if abs(delta) > tolerance:
            errors.append(
                f"cue {cue_time:.2f}s ({cue_desc}) has no visual within ±{tolerance:.1f}s — "
                f"closest is {closest.kind} at {closest.video_time:.2f}s ({delta:+.2f}s off): {closest.text[:40]}"
            )

    # Overflow check
    cursor = sum(step_duration(s, fps) for s in steps)
    end_vt = scene_start + cursor
    scene_duration = scene_end - scene_start
    if cursor > scene_duration + 0.5:
        errors.append(
            f"steps overflow scene: cursor ends at {end_vt:.2f}s but scene_end is {scene_end:.2f}s "
            f"(overflow {cursor - scene_duration:.2f}s)"
        )
    if cursor < scene_duration - 5.0:
        errors.append(
            f"steps underfill scene by {scene_duration - cursor:.2f}s — last visible step holds "
            f"frozen from {end_vt:.2f}s to {scene_end:.2f}s. Add a closer pause."
        )

    if errors:
        raise AssertionError(
            "Scene pacing check failed:\n  - " + "\n  - ".join(errors)
        )


__all__ = ["step_duration", "trace", "assert_alignment", "Landmark"]
