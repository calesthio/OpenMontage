# Hermes Creative Intelligence Layer

The bottleneck in the content flywheel was never automation — it runs
end-to-end. It was **discovery of genuinely novel, high-retention ideas**.
This layer addresses that: instead of optimizing throughput of a fixed loop,
it *mines opportunity* before the flywheel breeds anything.

## Modules (`tools/intelligence/`)

| Module | Role | v2 mapping |
|---|---|---|
| `embedding.py` | Deterministic token+char-ngram embedding + cosine. **Stand-in** for a real sentence model — single swap point (`Embedding.embed`). | similarity for novelty gate |
| `knowledge_graph.py` | Stores **ideas** (not videos). 8 signals/node (popularity, velocity, sentiment, controversy, novelty, saturation, viewer_overlap, historical_retention) + viewer-overlap edges + combination synthesis. | Semantic Knowledge Graph |
| `novelty_engine.py` | Rejects candidates with cosine > `threshold` (0.9) to any published idea. Forces exploration, not imitation. | Novelty Engine |
| `opportunity.py` | Multiplicative `Opportunity Score = Novelty × Demand × Retention × CreatorGap × Monetization × Evergreen` over **idea spaces**. | Opportunity Engine |
| `retention.py` | 12-feature retention predictor. **Transparent priors**; `fit()` is `NotImplementedError` so it never fakes learning on synthetic data. | Retention Intelligence |
| `features.py` | Extracts the 12 retention features from a render artifact (pre-render, structural). | Retention before rendering |
| `seed_miner.py` | Synthesizes novel spaces → opportunity-scores → novelty-gates → ranks seeds for the flywheel. | Concept Evolution front |
| `sources.py` | Signal-source plugin seam. YouTube/Reddit/Trends/HN stubs, key-gated. Inert offline; real values only with credentials. | Trend Intelligence Layer |

## Honest boundaries

- **Embedding** is lexical (token unigrams + 3-char n-grams). It catches
  exact duplicates and near-phrasing, but a pure synonym swap (Humans→People)
  scores ~0.88 and is *not* caught at 0.9. That fidelity requires a real
  sentence-embedding model — swap only `Embedding.embed`.
- **Signal sources** are inert without API keys. They never fabricate values;
  offline they return `[]`. The ingestion contract (`SignalSource`,
  `SignalIngestor`) is stable; only the adapters (or their keys) change.
- **Retention `fit()`** raises `NotImplementedError`. Training needs real
  backtesting outcomes (AVD, completion %, loop %, shares) — wire your
  analytics export to enable learned weights.

## Usage

```bash
# mine novel idea SPACES to seed generation 0 (vs random seeds)
env -u PYTHONPATH ./.venv_clean/bin/python scripts/flywheel_run.py \
  --project my-run --generations 6 --intelligence

# live board (Discovery / Opportunity-Mining panel appears when --intelligence ran)
env -u PYTHONPATH ./.venv_clean/bin/python -m backlot open my-run
```

### Wiring a live signal source
```python
import os
os.environ["YOUTUBE_API_KEY"] = "..."   # or set in shell
from tools.intelligence import ConceptGraph, SignalIngestor, YouTubeTranscriptSource
g = ConceptGraph()
n = SignalIngestor().ingest([YouTubeTranscriptSource("AI agents")], g)
# g now has concept nodes seeded from real weak signals
```

## Tests
`tests/contracts/test_flywheel_intelligence*.py` — 16 offline, deterministic
tests (ranking, novelty gate, retention heuristic, feature extraction,
source inertness, ingestion). Full suite: 490 passed.
