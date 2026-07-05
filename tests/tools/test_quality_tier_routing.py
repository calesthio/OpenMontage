"""Tests for quality-tier routing in the provider scorer (lib/scoring.py).

The tier changes the *weighting philosophy*, not any hardcoded provider name:
'draft' makes cost+speed dominate (cheap local wins), 'hero' makes quality
dominate (premium API wins). These tests prove the ranking flips accordingly.
"""
from __future__ import annotations

import pytest

from lib.scoring import (
    _TIER_WEIGHTS,
    _normalize_quality_tier,
    normalize_task_context,
    rank_providers,
)


class _Status:
    def __init__(self, value: str):
        self.value = value


class _FakeTool:
    """Minimal stand-in satisfying score_provider's tool contract."""

    def __init__(self, name, provider, runtime, stability, cost):
        self._info = {
            "name": name,
            "provider": provider,
            "runtime": runtime,
            "stability": stability,
            "capability": "music_generation",
            "best_for": ["background music generation"],
            "supports": {},
        }
        self._cost = cost

    def get_info(self):
        return self._info

    def get_status(self):
        return _Status("available")

    def estimate_cost(self, _ctx):
        return self._cost


@pytest.fixture
def providers():
    cheap_local = _FakeTool("acestep_music", "acestep", "local_gpu", "experimental", 0.003)
    premium_api = _FakeTool("suno_music", "suno", "api", "production", 0.30)
    return cheap_local, premium_api


def test_weight_vectors_sum_to_one():
    for tier, weights in _TIER_WEIGHTS.items():
        assert abs(sum(weights.values()) - 1.0) < 1e-9, f"{tier} weights sum to {sum(weights.values())}"


@pytest.mark.parametrize(
    "alias,expected",
    [
        ("hero", "hero"), ("final", "hero"), ("premium", "hero"),
        ("draft", "draft"), ("bulk", "draft"), ("preview", "draft"),
        ("", ""), ("standard", ""), ("nonsense", ""),
    ],
)
def test_tier_alias_normalization(alias, expected):
    assert _normalize_quality_tier(alias) == expected


def test_draft_routes_to_cheap_local(providers):
    cheap, prem = providers
    ctx = {"intent": "background music", "asset_type": "music", "quality_tier": "draft"}
    ranked = rank_providers([cheap, prem], ctx)
    assert ranked[0].provider == "acestep"


def test_hero_routes_to_premium(providers):
    cheap, prem = providers
    ctx = {"intent": "background music", "asset_type": "music", "quality_tier": "hero"}
    ranked = rank_providers([cheap, prem], ctx)
    assert ranked[0].provider == "suno"


def test_tier_survives_double_normalize():
    # Selectors normalize once (via kwarg), then score_provider normalizes again
    # (no kwarg). The tier must survive that second pass unchanged.
    once = normalize_task_context({}, quality_tier="bulk")
    assert once["quality_tier"] == "draft"
    twice = normalize_task_context(once)
    assert twice["quality_tier"] == "draft"


def test_score_carries_tier_for_explainability(providers):
    cheap, _ = providers
    ranked = rank_providers([cheap], {"intent": "x", "quality_tier": "draft"})
    assert ranked[0].quality_tier == "draft"
    assert "tier=draft" in ranked[0].explain()
