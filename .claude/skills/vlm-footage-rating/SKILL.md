---
name: vlm-footage-rating
description: Semantic video understanding for footage selection. Use when a clip library needs to be rated by behavior, camera stability, subject visibility, composition, or temporal structure; when clips must be selected for a montage by semantics instead of filename; when the editor needs frame-accurate timestamps of interesting moments; or when two candidate clips need a relative comparison with reasoning. Works fully local with an Ollama vision model (e.g. Gemma 4 12B, Gemma 3n, Qwen-VL). No API keys required.
license: MIT
metadata:
  requires:
    env: []
    ollama: true
---

# VLM Footage Rating (Semantic Video Understanding)

Rate a folder of video clips with a local vision-language model and get an
editorial database: behavior, camera quality, composition, subject (product)
visibility, timestamped segments, highlights, rankings, and match-cut
continuity. This is the layer static CLIP retrieval cannot provide:
temporal and behavioral semantics.

## Pipeline Overview

```
vlm_clip_rating        -> clip_tags.jsonl      (coarse: behavior/camera/shot/subject/segments)
vlm_zoom_rating        -> clip_zooms.jsonl     (frame-accurate timestamps + deep-dive descriptions)
vlm_editorial_ranking  -> editorial_rankings.json (composite scores, leaderboards, match cuts)
vlm_comparative_rank   -> comparative_rankings.jsonl (optional: relative ranking with reasoning)
```

Each stage is idempotent (skips already-processed clips), so re-running after
adding footage only processes the new clips.

## Prerequisites

- ffmpeg/ffprobe on PATH
- Ollama running with a vision model.

The tools accept only `localhost` or loopback-IP Ollama URLs. Video frames
are base64-encoded in requests, so remote endpoints are rejected to preserve
the advertised local-only privacy boundary.

**Recommended and tested: `gemma4:12b`** (this is the model the tools were
built and validated against: ~8GB VRAM, best quality for behavior nuance).
The behavior taxonomy, JSON schema, and prompts were tuned on it.

```bash
ollama pull gemma4:12b
```

Other vision models may work (the tools are model-agnostic over Ollama's
API), but they are NOT tested:

| Model | VRAM (approx) | Fits | Status |
|---|---|---|---|
| `gemma3n:e4b` | ~3.5GB | 4GB GPUs | Untested, smaller/faster |
| `gemma3n:e2b` | ~1.5GB | any GPU | Untested, fastest/lightest |
| `qwen2.5vl:3b` | ~3GB | 4GB GPUs | Untested |
| `qwen2.5vl:7b` | ~6GB | 8GB GPUs | Untested |
| `gemma4:12b` | ~8GB | 12GB+ GPUs | **TESTED, recommended** |

If you try a smaller model, expect possible differences in JSON
conformance and rating quality; the defensive parsing handles most drift.
For 4b-class models, passing `frame_scale: 384` speeds up inference.

## Usage

### 1. Coarse rating

```python
from tools.video.vlm_clip_rating import VlmClipRating
tool = VlmClipRating()
tool.execute({
    "input_dir": "/path/to/clips",
    "output_path": "/path/to/clip_tags.jsonl",
    "focus_prompt": "a black collar (the product being advertised)",
    "model": "gemma4:12b",
})
```

`focus_prompt` is optional: set it to whatever subject the edit cares about
(a product, an animal behavior, a person) and the model rates its visibility
in every clip. Leave empty for generic footage rating.

### 2. Zoom pass (frame-accurate timestamps)

```python
from tools.video.vlm_zoom_rating import VlmZoomRating
VlmZoomRating().execute({
    "ratings_path": "/path/to/clip_tags.jsonl",
    "output_path": "/path/to/clip_zooms.jsonl",
})
```

Re-examines each flagged highlight/segment at 4 fps, producing sub-beats with
precise start/end times, camera angle, subject facing direction (for match
cuts), deep-dive descriptions, and vibe.

### 3. Editorial ranking

```python
from tools.video.vlm_editorial_ranking import VlmEditorialRanking
VlmEditorialRanking().execute({
    "ratings_path": "/path/to/clip_tags.jsonl",
    "zooms_path": "/path/to/clip_zooms.jsonl",   # optional
    "output_path": "/path/to/editorial_rankings.json",
    "weights": {"stability": 0.25, "quality": 0.25, "subject": 0.25,
                "composition": 0.15, "vibe": 0.10},
})
```

Weights must sum to 1.0 and are campaign-tunable (bias toward product shots,
stability, or energy).

### 4. Comparative ranking (optional tiebreaker)

```python
from tools.video.vlm_comparative_rank import VlmComparativeRank
VlmComparativeRank().execute({
    "rankings_path": "/path/to/editorial_rankings.json",
    "output_path": "/path/to/comparative_rankings.jsonl",
    "purpose": "subject_hero",
})
```

Shows 4 candidate clips in one context, asks for a relative ranking,
calibrated scores, and reasons for best/worst. Use when two clips score
close and you want the model to argue about which wins.

## Output Schema Highlights

| Field | Meaning |
|---|---|
| `overall.behavior` | walking_calm, pulling, sniffing, trotting, sitting, lying, greeting, playing, expression, other |
| `overall.energy` | calm, neutral, excited, hyper |
| `camera.stability_score` | 0-1 camera shake quality |
| `shot.type` | extreme_wide ... extreme_close_up |
| `shot.rule_of_thirds_score` | 0-1 composition |
| `product.subject_visibility` | not_visible, partial, clear, featured |
| `product.subject_quality_score` | 0-1 how well the subject of interest is shown |
| `segments[].start_s/end_s` | coarse timestamped beats |
| `highlights[].start_s/end_s` | keeper moments (coarse) |
| zoom `sub_beats[]` | frame-accurate beats: start_s/end_s, camera_angle, subject_facing, deep_dive, vibe, use |

## Editing Recipes

- **Subject hero shots**: filter `product.subject_visibility` in
  ("featured", "clear"), rank by `subject_quality_score`.
- **Stability gate**: only use clips with `camera.stability_score >= 0.9`.
- **Match cuts**: `editorial_rankings.json` -> `match_cuts` -> chains by
  subject facing direction (left/right). Cut same-direction shots together.
- **Story beats**: pick behavior buckets (open wide, calm walk, action,
  subject close-up) and use zoom timestamps for precise cut points.

## Pitfalls

- The VLM occasionally emits malformed JSON (string entries in arrays,
  non-numeric timestamps). The tools guard this; if you hand-parse the
  JSONL, filter `isinstance(x, dict)` and use safe float conversion.
- Zoom sub-beat timestamps are window-relative: real clip time is
  `window_start_s + sub_beat.start_s`.
- First clip per run is slower (model load). Subsequent clips are ~5-15s.
- Runtime scales with clip count: ~8-15s per clip for coarse, ~30s per
  zoom window. Budget accordingly for large libraries.
