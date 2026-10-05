"""Contract tests for signal sources + retention feature extraction.

Offline + deterministic. Verifies v2 behaviours:
- Signal sources are inert without credentials (never fabricate).
- YouTube parsers are correct on fixtures.
- SignalIngestor folds weak signals into the ConceptGraph deterministically.
- Retention extractor maps an artifact -> 12 bounded features, and a
  structurally stronger Short scores higher retention.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.intelligence import (  # noqa: E402
    ConceptGraph, SignalSource, Signal, SignalIngestor,
    YouTubeTranscriptSource, RetentionFeatureSet,
)
from tools.intelligence.features import extract_features, predict_retention  # noqa: E402
from tools.intelligence.sources import _extract_concepts  # noqa: E402


# ---------------------------------------------------------------------------
# signal sources — inert offline, correct parsers
# ---------------------------------------------------------------------------
def test_youtube_inert_without_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    src = YouTubeTranscriptSource()
    assert src.is_live() is False
    assert src.fetch() == []


def test_youtube_parse_search_fixture():
    payload = {
        "items": [
            {"id": {"videoId": "abc123"}},
            {"id": {"videoId": "def456"}},
            {"id": {"playlistId": "nope"}},
        ]
    }
    ids = YouTubeTranscriptSource._parse_search(payload)
    assert ids == ["abc123", "def456"]


def test_youtube_parse_captions_fixture():
    payload = {
        "items": [
            {"snippet": {"text": "Claude beats humans at strategy"}},
            {"snippet": {"name": "caption track"}},
        ]
    }
    sigs = YouTubeTranscriptSource._parse_captions(payload, "vid9")
    assert len(sigs) == 2
    assert sigs[0].source == "youtube"
    assert "Claude" in sigs[0].text
    assert sigs[0].url.endswith("vid9")


def test_ingestor_folds_signals_into_graph():
    g = ConceptGraph()
    # a fake live source (bypass key gating for the unit)
    class FakeSrc(SignalSource):
        name = "fake"
        def is_live(self):
            return True
        def fetch(self):
            return [
                Signal(source="fake", text="Claude productivity military strategy",
                       weight=1.0, recency=0.8),
                Signal(source="fake", text="Open source MCP servers", weight=1.0, recency=0.6),
            ]
    n = SignalIngestor().ingest([FakeSrc()], g)
    assert n == 2
    assert g.get("Claude") is not None
    assert g.get("Mcp") is not None
    # signals raised popularity/velocity deterministically
    assert g.get("Claude").popularity > 0.0
    assert g.get("Claude").velocity > 0.0


def test_extract_concepts_skips_stopwords():
    concepts = _extract_concepts("the CLAUDE and your productivity strategy")
    assert "The" not in concepts and "And" not in concepts
    assert "Claude" in concepts and "Productivity" in concepts


# ---------------------------------------------------------------------------
# retention feature extractor
# ---------------------------------------------------------------------------
def _artifact(hook=True, payoff=True, cues_per_section=1, words=140, dur=60.0, anchors=3):
    secs = []
    labels = (["Hook"] if hook else ["Intro"]) + ["Build"] + (["Climax"] if payoff else ["Body"])
    for i, lab in enumerate(labels):
        secs.append({
            "label": lab,
            "text": f"section {i} " + ("why does this work?" if i == 0 else "detail here"),
            "enhancement_cues": [{"type": "diagram"}] * cues_per_section,
        })
    return {
        "topic": "test", "duration_seconds": dur, "target_duration_seconds": dur,
        "word_count": words, "retention_anchors": anchors,
        "sections": secs,
    }


def test_extract_features_bounded_0_1():
    feats = extract_features(_artifact())
    d = feats.as_dict()
    for k, v in d.items():
        if k in ("observed_avd", "observed_completion", "observed_loop_pct"):
            continue
        assert 0.0 <= v <= 1.0, f"{k}={v} out of range"


def test_extract_features_good_beats_flat():
    good = _artifact(hook=True, payoff=True, cues_per_section=2, words=140, anchors=3)
    flat = _artifact(hook=False, payoff=False, cues_per_section=0, words=60, anchors=0)
    g = predict_retention(good)["retention_score"]
    f = predict_retention(flat)["retention_score"]
    assert g > f
    # the good artifact should have a strong immediate hook
    assert extract_features(good).hook_strength >= 0.9


def test_extract_features_uses_payoff_timing():
    with_payoff = extract_features(_artifact(payoff=True))
    without = extract_features(_artifact(payoff=False))
    assert with_payoff.payoff_timing > without.payoff_timing


# keep `json` imported for potential fixtures without lint complaints
_ = json
