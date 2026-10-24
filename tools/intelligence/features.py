"""Retention feature extractor.

Turns a rendered Short's artifact payload (the dict the render stage
produces — sections, word_count, duration, enhancement cues, retention
anchors, novelty flag) into the 12-feature vector the RetentionPredictor
consumes.

Why before rendering matters: the v2 design wants retention predicted
*before* spending render budget. These features are STRUCTURAL and
DETERMINISTIC (immediate hook, pacing, cuts-per-10s, visual entropy,
loop tightness) — they're computable from the script/artifact plan alone,
so the engine can prune weak variants pre-render.

Honest scope: no learning, no network. Swap `extract_features` for a
trained extractor later; the RetentionFeatureSet contract is stable.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Dict, List

from .retention import RetentionFeatureSet, RetentionPredictor

_HOOK_LABELS = {"hook", "open", "intro", "cold-open", "cold open"}
_PAYOFF_LABELS = {"climax", "payoff", "reveal", "twist", "conclusion", "finish", "reveal"}
_CURIOSITY_CUES = {"curiosity", "gap", "question", "mystery", "secret", "why", "hook"}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _sections(artifact: dict) -> List[dict]:
    return artifact.get("sections") or []


def _words_per_sec(artifact: dict) -> float:
    dur = float(artifact.get("duration_seconds") or artifact.get("target_duration_seconds") or 1.0)
    wc = float(artifact.get("word_count") or 0)
    return wc / dur if dur > 0 else 0.0


def extract_features(artifact: dict) -> RetentionFeatureSet:
    """Map a render artifact to the 12 retention features (each 0..1)."""
    secs = _sections(artifact)
    n = max(1, len(secs))
    dur = float(artifact.get("duration_seconds") or artifact.get("target_duration_seconds") or 60.0)
    wps = _words_per_sec(artifact)

    # immediate hook: first section labelled a hook + carries a visual/curiosity cue
    first = secs[0] if secs else {}
    first_cues = {c.get("type", "") for c in (first.get("enhancement_cues") or [])}
    hook = (1.0 if first.get("label", "").lower() in _HOOK_LABELS else 0.4) + (0.3 if first_cues else 0.0)
    hook_strength = _clamp(hook)

    # curiosity gap: a curiosity cue anywhere, or a "?" in the narration
    all_text = " ".join(s.get("text", "") for s in secs).lower()
    has_q = "?" in all_text
    has_cue = any(
        _CURIOSITY_CUES & {c.get("type", "").lower()}
        for s in secs for c in (s.get("enhancement_cues") or [])
    )
    curiosity_gap = _clamp(0.3 + 0.4 * has_cue + 0.3 * has_q)

    # information density: words/sec vs a "dense" 2.5 wps ceiling
    information_density = _clamp(wps / 2.5)

    # pacing: peaks around 2.3 wps (too slow = dead, too fast = overwhelming)
    pacing = _clamp(1.0 - abs(wps - 2.3) / 2.3)

    # scene cadence: cuts per 10s (pattern interrupts)
    cuts_per_10s = n / (dur / 10.0) if dur > 0 else 0.0
    scene_cadence = _clamp(cuts_per_10s / 3.0)  # ~3 cuts/10s is brisk

    # emotional variance: rhythm change across sections (std of text length)
    lengths = [len(s.get("text", "")) for s in secs]
    if len(lengths) > 1:
        mean = sum(lengths) / len(lengths)
        var = sum((l - mean) ** 2 for l in lengths) / len(lengths)
        emotional_variance = _clamp((var ** 0.5) / max(1.0, mean))
    else:
        emotional_variance = 0.0

    # payoff timing: a payoff section exists in the latter half (~0.7)
    payoff_idx = next((i for i, s in enumerate(secs) if s.get("label", "").lower() in _PAYOFF_LABELS), -1)
    if payoff_idx >= 0 and n > 1:
        payoff_timing = _clamp(1.0 - abs((payoff_idx / (n - 1)) - 0.7) / 0.7)
    else:
        payoff_timing = 0.3

    # loop quality: retention anchors + tight duration match
    anchors = float(artifact.get("retention_anchors") or 0)
    target = float(artifact.get("target_duration_seconds") or dur or 1.0)
    dur_match = 1.0 - min(1.0, abs(dur - target) / max(1.0, target))
    loop_quality = _clamp(0.5 * _clamp(anchors / 3.0) + 0.5 * dur_match)

    # narration speed: wps relative to a calm 2.0 target
    narration_speed = _clamp(1.0 - abs(wps - 2.0) / 2.0)

    # subtitle density: caption load (words per section)
    subtitle_density = _clamp((float(artifact.get("word_count") or 0) / n) / 40.0)

    # visual entropy: diversity of distinct cue types across sections
    cue_types = {c.get("type", "") for s in secs for c in (s.get("enhancement_cues") or []) if c.get("type")}
    visual_entropy = _clamp(len(cue_types) / 5.0)

    # b-roll frequency: fraction of sections carrying a visual cue
    with_cue = sum(1 for s in secs if (s.get("enhancement_cues") or []))
    broll_frequency = _clamp(with_cue / n)

    # pattern interrupt (derived): brisk cadence + rhythm variance
    pattern_interrupt = _clamp(0.6 * scene_cadence + 0.4 * emotional_variance)

    return RetentionFeatureSet(
        hook_strength=hook_strength,
        curiosity_gap=curiosity_gap,
        information_density=information_density,
        pacing=pacing,
        scene_cadence=scene_cadence,
        emotional_variance=emotional_variance,
        payoff_timing=payoff_timing,
        loop_quality=loop_quality,
        narration_speed=narration_speed,
        subtitle_density=subtitle_density,
        visual_entropy=visual_entropy,
        broll_frequency=broll_frequency,
        pattern_interrupt=pattern_interrupt,
    )


def predict_retention(artifact: dict, model=None) -> Dict[str, float]:
    """Convenience: artifact -> retention prediction dict."""
    feats = extract_features(artifact)
    return RetentionPredictor(model).predict(feats)
