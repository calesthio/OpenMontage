#!/usr/bin/env python3
"""S1 speculative-illustration gate.

Adapts the AI_IMAGE_POLICY illustration gate to the speculative-evolution
niche (AI share 100%): every AI cut requires a persistent "Speculative
illustration" label at start + description, and a motion-variety lint (no two
identical moves in a row). Other gates are not weakened.
"""
from __future__ import annotations

from typing import Any, Dict, List

SPECULATIVE_LABEL = "Speculative illustration"


def check_speculative_label(
    cuts: List[Dict[str, Any]], duration: float
) -> List[Dict[str, Any]]:
    """Require every AI cut to carry the Speculative illustration label +
    a description. Returns problem dicts."""
    problems: List[Dict[str, Any]] = []
    ai_total = 0
    ai_labeled = 0
    ai_share = 0.0
    for c in cuts:
        if c.get("generator") != "AI":
            continue
        ai_total += 1
        label_ok = c.get("label") == SPECULATIVE_LABEL
        desc_ok = bool(str(c.get("description", "")).strip())
        if label_ok and desc_ok:
            ai_labeled += 1
        else:
            problems.append({
                "cut_id": c.get("id", "?"),
                "reason": (
                    f"AI cut lacks '{SPECULATIVE_LABEL}' label or description "
                    f"(label={c.get('label')!r}, description={c.get('description')!r})"
                ),
            })
        try:
            dur = float(c.get("duration", 0))
        except (TypeError, ValueError):
            dur = 0.0
        ai_share += (dur / duration) if duration > 0 else 0.0
    if ai_total and ai_share > 1.0 + 1e-9:
        problems.append({
            "cut_id": "aggregate",
            "reason": f"AI share {ai_share:.2f} > 1.0 (100%)",
        })
    return {
        "problems": problems,
        "ai_total": ai_total,
        "ai_labeled": ai_labeled,
        "ai_share": round(ai_share, 4),
        "ok": not problems,
    }


def check_motion_variety(
    segments: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """No two consecutive segments with identical move (type+easing+direction).

    Reuses the motion_variety.lint_variation rule.
    """
    from tools.motion.motion_variety import lint_variation  # noqa: E402

    problems = lint_variation(segments)
    return {
        "problems": problems,
        "ok": not problems,
    }
