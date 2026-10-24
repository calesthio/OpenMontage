# Footage Director - Business Documentary Pipeline

## When To Use

Stage 8 of 12. You find, download and clear the real footage the scene plan
asks for, producing an `asset_manifest` where every asset carries provider,
original URL, author, license and attribution — and every failed search is
classified instead of hidden.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact in | `scene_plan` (validated) | Scenes + queries |
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Output validation |
| Registry | `direct_clip_search` (required), `corpus_builder`, `clip_search` (optional) | Retrieval |
| Lib | `lib/zero_cost_gate`, `lib/artifact_ids` | Cost gate + scene resolution |

## Process

### 1. Route every search through the zero-cost gate

```python
from lib.zero_cost_gate import facts_from_registry, evaluate_call
decision = evaluate_call(facts_from_registry('direct_clip_search', 'search',
                                             cost_usd=0.0,
                                             route='no-key archives'))
```

No-key archive sources (Archive.org, Wikimedia Commons, NASA, and similar)
are the default path. A key-gated or metered route with unknown pricing is
BLOCKED in strict zero-cost mode — surface it to the human with its cost
instead of calling it.

### 2. Run the scene's 2–4 queries

Use the queries the storyboard director wrote, in order. Do not substitute a
looser query for a strict one that returned nothing — record the miss.

### 3. Classify every result — never collapse to an empty list

| Class | Meaning |
|-------|---------|
| `no_results` | The query genuinely matched nothing |
| `transport_error` | Network/timeout/5xx |
| `auth_error` | Missing or rejected credentials |
| `rate_limited` | 429 |
| `license_rejected` | Found, but terms do not allow this use |
| `download_error` | Could not fetch the file |
| `invalid_media` | Fetched, but fails MIME/duration/resolution/decode |

`lib.zero_cost_gate.classify_failure()` maps a failure onto the taxonomy.
`no_results` is a fact to record; `transport_error` is a retry on the **same**
route with backoff. `reroute_allowed()` is always `False` — an auth, billing
or rate-limit failure stops and reports, it never silently switches vendor.

### 4. Validate the file before it enters the manifest

Check the container/MIME, real duration, resolution, and a full decode of the
first seconds. A file that fails any of these is `invalid_media`, not an asset.

### 5. License and provenance per asset

Record for every asset: provider, original URL, file title/ID, author, license
type, required attribution text, commercial-use permission, modification and
redistribution limits, download date, and the proof of terms.

**Do not assume** that everything on Archive.org, Wikimedia Commons or NASA is
public domain — status depends on the individual item and on third-party
rights. "Royalty-free" is not "CC0". If the rights are unclear, the asset is
not used.

### 6. Block empty scenes, do not fill them

A scene with no valid asset is `BLOCKED`. The run stops at that scene rather
than rendering a black or reused clip to keep the timeline full.

### 7. Score and keep the trail

For each scene record the candidates considered, their scores, the pick and
why, plus the passes you rejected. These feed stage 9 and the golden-set
regression tests.

### 8. Quality gate

- Schema-valid `asset_manifest`.
- Every asset: provider, original URL, author, license, attribution, hash,
  duration, scene_id, search query, score, selection reason, QA verdict.
- `metadata.search_stats` carries per-query result-class counts.
- Every `scene_id` resolves against the scene plan
  (`lib.artifact_ids.check_asset_manifest`).
- No scene is reported as filled when its search class was not `no_results`
  but `license_rejected` or `invalid_media`.

## Common Pitfalls

- Treating a key-gated API's 401 as "no results".
- Downloading a clip whose license forbids commercial use, then crediting it
  anyway.
- Using the same strong clip for four scenes to hide weak searches.
- Trusting a filename as evidence of content.

---

## Gate Reminder (Binding)

`footage` gates on human approval. Present the manifest scene by scene (the
Backlot filmstrip is the review surface). After approval: checkpoint
`status="awaiting_human"` and **END YOUR TURN**.
