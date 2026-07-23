"""Retention Intelligence — predicts retention BEFORE rendering.

v2 spec lists 12 features; Reddit/creator analysis ([1]) consistently points to
immediate hooks, rapid pacing, pattern interrupts and seamless loops as strong
retention drivers, with exact thresholds varying by niche.

HONEST STATUS: this is a *heuristic* predictor. It is transparent and
deterministic, but the weights are priors, NOT learned. The v2 design calls
for updating feature weights from backtesting (Hook retention, AVD, loop %,
completion %, shares …). This module is structured so a trained model can
replace `_predict` without touching callers: implement `RetentionModel.fit`
and pass it in. Until then, weights are explicit and editable.

[1] r/shortsAlgorithm — 53-Shorts scrape, 6 retention patterns
    (community analysis; thresholds niche-dependent).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

# The 12 retention features from the v2 spec (0..1 each).
RETENTION_FEATURES = [
    "hook_strength", "curiosity_gap", "information_density", "pacing",
    "scene_cadence", "emotional_variance", "payoff_timing", "loop_quality",
    "narration_speed", "subtitle_density", "visual_entropy", "broll_frequency",
]

# Prior weights (sum normalised at predict time). These are EDITABLE PRIORS,
# not learned values. Replace via RetentionModel subclass + fit().
_PRIOR_WEIGHTS: Dict[str, float] = {
    "hook_strength": 1.6,        # immediate hook — strongest driver
    "curiosity_gap": 1.4,        # curiosity gap sustains watch
    "pacing": 1.3,              # rapid pacing
    "loop_quality": 1.2,         # seamless loop = rewatches
    "payoff_timing": 1.1,        # payoff before drop-off
    "pattern_interrupt": 1.0,     # (derived) pattern interrupts
    "emotional_variance": 0.9,
    "scene_cadence": 0.8,
    "information_density": 0.7,
    "visual_entropy": 0.6,
    "narration_speed": 0.5,
    "subtitle_density": 0.4,
    "broll_frequency": 0.4,
}


@dataclass
class RetentionFeatureSet:
    hook_strength: float = 0.0
    curiosity_gap: float = 0.0
    information_density: float = 0.0
    pacing: float = 0.0
    scene_cadence: float = 0.0
    emotional_variance: float = 0.0
    payoff_timing: float = 0.0
    loop_quality: float = 0.0
    narration_speed: float = 0.0
    subtitle_density: float = 0.0
    visual_entropy: float = 0.0
    broll_frequency: float = 0.0
    # optional derived signal
    pattern_interrupt: float = 0.0
    # observed outcomes (filled by backtesting; empty => prediction only)
    observed_avd: float = 0.0
    observed_completion: float = 0.0
    observed_loop_pct: float = 0.0

    def as_dict(self) -> dict:
        import dataclasses as _dc
        return {f.name: getattr(self, f.name) for f in _dc.fields(self)}


class RetentionModel:
    """Swappable predictor. Default = transparent priors."""

    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = dict(_PRIOR_WEIGHTS)
        if weights:
            self.weights.update(weights)

    def predict(self, feats: RetentionFeatureSet) -> Dict[str, float]:
        d = feats.as_dict()
        num = 0.0
        den = 0.0
        for k, w in self.weights.items():
            v = float(d.get(k, 0.0))
            v = max(0.0, min(1.0, v))
            num += w * v
            den += w
        score = num / den if den > 0 else 0.0
        # Derived headline metrics (illustrative mapping, transparent).
        return {
            "retention_score": round(score, 4),
            "predicted_completion": round(min(1.0, score * 1.05), 4),
            "predicted_rewatches": round(score * feats.loop_quality, 4),
            "hook_score": round(max(0.0, min(1.0, feats.hook_strength)), 4),
        }

    def fit(self, samples: List[RetentionFeatureSet]) -> None:
        """Placeholder for learned weights.

        A production implementation regresses observed outcomes
        (avd/completion/loop_pct) onto features to set self.weights.
        Kept unimplemented so the heuristic stays the default and nothing
        silently 'learns' on fabricated data.
        """
        raise NotImplementedError(
            "fit() requires real backtesting outcomes; not synthesised. "
            "Wire this to your analytics export to enable learned weights."
        )


class RetentionPredictor:
    def __init__(self, model: Optional[RetentionModel] = None) -> None:
        self.model = model or RetentionModel()

    def predict(self, feats: RetentionFeatureSet) -> Dict[str, float]:
        return self.model.predict(feats)
