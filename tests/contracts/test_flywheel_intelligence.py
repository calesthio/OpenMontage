"""Contract tests for the Hermes Creative Intelligence layer.

Offline + deterministic (no numpy/sklearn). Verifies the v2 behaviours:
- Novelty gate rejects imitations (cosine > 0.9) and accepts novel combos.
- Opportunity Engine is multiplicative and surfaces low-saturation spaces.
- Retention predictor is transparent (priors) and refuses to fake-learn.
- SeedMiner emits ranked, NOVEL idea spaces (not copied videos).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.intelligence import (  # noqa: E402
    ConceptGraph, Concept, NoveltyEngine, OpportunityEngine, IdeaSpace,
    RetentionPredictor, SeedMiner, Embedding,
)
from tools.intelligence.retention import RetentionFeatureSet  # noqa: E402


# ---------------------------------------------------------------------------
# embedding
# ---------------------------------------------------------------------------
def test_embedding_deterministic_and_cosine():
    a = Embedding.embed("Claude + Productivity strategy")
    b = Embedding.embed("Claude + Productivity strategy")
    assert a == b
    # near-identical text => high cosine
    c = Embedding.embed("Claude and Productivity strategy")
    assert Embedding.cosine(a, c) > 0.8
    # unrelated text => low cosine
    d = Embedding.embed("banana smoothie recipe beach")
    assert Embedding.cosine(a, d) < 0.5


# ---------------------------------------------------------------------------
# knowledge graph
# ---------------------------------------------------------------------------
def test_graph_synthesizes_combinations():
    g = ConceptGraph()
    g.add(Concept(label="Claude", velocity=0.7, novelty=0.4, saturation=0.6))
    g.add(Concept(label="Productivity", velocity=0.4, novelty=0.1, saturation=0.7))
    g.add(Concept(label="Military Strategy", velocity=0.3, novelty=0.4, saturation=0.4))
    combos = g.synthesize("Claude", "Productivity", "Military Strategy", max_depth=3)
    assert "Claude + Productivity" in combos
    assert "Claude + Productivity + Military Strategy" in combos
    # round-trips through dict
    g2 = ConceptGraph.from_dict(g.to_dict())
    assert set(g2.nodes) == set(g.nodes)


def test_graph_emerging_ranks_velocity_over_saturation():
    g = ConceptGraph()
    g.add(Concept(label="HotLowSat", velocity=0.9, novelty=0.8, saturation=0.1))
    g.add(Concept(label="HotHighSat", velocity=0.9, novelty=0.8, saturation=0.9))
    emerging = g.emerging(top=1)
    assert emerging[0].label == "HotLowSat"


# ---------------------------------------------------------------------------
# novelty engine — the "don't imitate" gate
# ---------------------------------------------------------------------------
def test_novelty_rejects_imitation_and_accepts_novel():
    n = NoveltyEngine(threshold=0.9)
    published = "7 Military Strategies Claude Uses Better Than Humans"
    n.register_published("v1", published)
    # exact duplicate => rejected (cosine ~1.0 > 0.9)
    novel, score, nearest = n.check(published)
    assert novel is False
    assert nearest and "Military" in nearest
    # genuinely different combo => accepted
    novel2, score2, _ = n.check("Open-source MCP servers for everyday workflows")
    assert novel2 is True
    assert score2 > (1 - 0.9)
    # NOTE: a pure synonym swap (Humans->People) scores ~0.88 under the
    # lexical stand-in embedding and is NOT caught at 0.9 — that fidelity
    # requires swapping Embedding.embed for a real sentence model.


# ---------------------------------------------------------------------------
# opportunity engine — multiplicative, low-saturation wins
# ---------------------------------------------------------------------------
def test_opportunity_is_multiplicative_and_zeroes_weak_factor():
    e = OpportunityEngine()
    # strong on every axis
    good = IdeaSpace(label="A", novelty=0.8, demand=0.9, retention_potential=0.8,
                     creator_gap=0.9, monetization=0.7, evergreen=0.8)
    e.add(good)
    # novel & demanded but saturated (creator_gap ~ 0) => score ~ 0
    saturated = IdeaSpace(label="B", novelty=0.8, demand=0.9,
                          retention_potential=0.8, creator_gap=0.0,
                          monetization=0.7, evergreen=0.8)
    e.add(saturated)
    assert good.score() > 0.0
    assert saturated.score() == 0.0
    ranked = e.rank()
    assert ranked[0].label == "A"


# ---------------------------------------------------------------------------
# retention — transparent heuristic, refuses to fake-learn
# ---------------------------------------------------------------------------
def test_retention_predictor_transparent_and_no_fakelern():
    p = RetentionPredictor()
    feats = RetentionFeatureSet(
        hook_strength=0.9, curiosity_gap=0.8, pacing=0.8, loop_quality=0.7,
        payoff_timing=0.7, pattern_interrupt=0.6, emotional_variance=0.5,
        scene_cadence=0.5, information_density=0.5, visual_entropy=0.4,
        narration_speed=0.4, subtitle_density=0.4, broll_frequency=0.4,
    )
    out = p.predict(feats)
    assert 0.0 < out["retention_score"] <= 1.0
    assert out["predicted_completion"] >= out["retention_score"]
    # fit() must NOT silently learn on fabricated data
    with pytest.raises(NotImplementedError):
        p.model.fit([feats])


# ---------------------------------------------------------------------------
# seed miner — produces novel, ranked idea SPACES
# ---------------------------------------------------------------------------
def test_seed_miner_emits_novel_ranked_spaces():
    m = SeedMiner(novelty_threshold=0.9, opportunity_floor=0.05)
    seeds = m.mine(top=5)
    assert 0 < len(seeds) <= 5
    labels = [s.label for s in seeds]
    # no duplicate seeds
    assert len(labels) == len(set(labels))
    # every seed is a real opportunity (non-zero) and ordered descending
    scores = [s.score() for s in seeds]
    assert all(s > 0 for s in scores)
    assert scores == sorted(scores, reverse=True)
    # every seed is a COMBINATION (idea space), not a single copied video
    for s in seeds:
        assert "+" in s.label or s.novelty > 0.3


def test_seed_miner_persists_json(tmp_path):
    m = SeedMiner()
    m.mine(top=3)
    out = tmp_path / "intel.json"
    m.write(out)
    data = json.loads(out.read_text())
    assert "graph" in data and "opportunity" in data
    assert data["opportunity"]["count"] > 0
