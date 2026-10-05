"""Hermes Creative Intelligence Layer.

Public API — import from here so callers don't depend on module layout.

    from tools.intelligence import (
        Embedding, ConceptGraph, NoveltyEngine, OpportunityEngine,
        RetentionPredictor, SeedMiner,
    )
"""
from .embedding import Embedding, embed, cosine
from .knowledge_graph import ConceptGraph, Concept, Edge
from .novelty_engine import NoveltyEngine
from .opportunity import OpportunityEngine, IdeaSpace
from .retention import RetentionPredictor, RetentionModel, RetentionFeatureSet, RETENTION_FEATURES
from .features import extract_features, predict_retention
from .seed_miner import SeedMiner
from .sources import (
    Signal, SignalSource, YouTubeTranscriptSource, RedditSource,
    GoogleTrendsSource, HackerNewsSource, SignalIngestor,
)

__all__ = [
    "Embedding", "embed", "cosine",
    "ConceptGraph", "Concept", "Edge",
    "NoveltyEngine",
    "OpportunityEngine", "IdeaSpace",
    "RetentionPredictor", "RetentionModel", "RETENTION_FEATURES",
    "extract_features", "predict_retention",
    "SeedMiner",
    "Signal", "SignalSource", "YouTubeTranscriptSource", "RedditSource",
    "GoogleTrendsSource", "HackerNewsSource", "SignalIngestor",
]
