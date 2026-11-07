#!/usr/bin/env python3
"""S1-5 EDL builder: per-cut rationale EDL for the speculative evolution pilot.

Builds an Edit Decision List JSON from a shot list. Each cut carries rationale,
motion spec (pan/zoom/detail_crop/parallax + easing + direction), claim_ids, and
duration. Enforces motion-variety lint (no two identical moves in a row).
Stdlib only; no media committed.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.motion.motion_variety import lint_variation  # noqa: E402


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def build_edl(
    shots: List[Dict[str, Any]],
    output_path: Path,
    width: int = 1280,
    height: int = 720,
    fps: int = 30,
) -> Dict[str, Any]:
    """Build EDL with per-cut rationale. Returns {edl_path, cuts[], motion_problems[]}."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    cuts: List[Dict[str, Any]] = []
    t_cursor = 0.0
    for i, s in enumerate(shots):
        dur = float(s.get("duration", 5.0))
        move = s.get("move", {})
        cut = {
            "cut_id": f"cut_{i+1:03d}",
            "start": round(t_cursor, 4),
            "end": round(t_cursor + dur, 4),
            "duration": round(dur, 4),
            "source": s.get("source"),
            "source_sha256": s.get("source_sha256"),
            "claim_ids": s.get("claim_ids", []),
            "rationale": s.get("rationale", ""),
            "motion": {
                "type": move.get("type", "pan"),
                "easing": move.get("easing", "easeinout"),
                "direction": move.get("direction", "in"),
            },
            "width": width,
            "height": height,
            "fps": fps,
            "label": "Speculative illustration" if s.get("generator", "AI") == "AI" else None,
        }
        cuts.append(cut)
        t_cursor += dur

    # motion variety lint: no two identical consecutive moves
    segments = [{"move": c["motion"]["type"], "easing": c["motion"]["easing"],
                 "direction": c["motion"]["direction"]} for c in cuts]
    problems = lint_variation(segments)

    edl = {
        "version": "1.0",
        "topic": "How could life survive beneath a frozen alien ocean?",
        "width": width,
        "height": height,
        "fps": fps,
        "total_duration": round(t_cursor, 4),
        "num_cuts": len(cuts),
        "cuts": cuts,
        "motion_problems": problems,
    }
    output_path.write_text(json.dumps(edl, indent=2), encoding="utf-8")
    return {
        "edl_path": str(output_path),
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
        "bytes": output_path.stat().st_size,
        "cuts": cuts,
        "motion_problems": problems,
        "ok": not problems,
    }
