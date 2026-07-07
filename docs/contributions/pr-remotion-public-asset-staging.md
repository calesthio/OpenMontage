# Pull Request: fix(remotion): stage local assets into public/ before Explainer render

> Copy the sections below into GitHub when opening the PR.
> Branch: `fix/remotion-public-asset-staging` · Commit: `42a4214`

---

## Summary

Fixes a production bug in the Remotion render path: **local narration and music files fail to load** when passed as absolute filesystem paths. This blocked hybrid / real-photo workflows (user JPGs + local TTS audio) unless contributors manually copied assets into `remotion-composer/public/`.

This PR adds automatic asset staging — the same class of fix HyperFrames compose already does via `_resolve_and_stage_assets`, but missing from the Remotion `Explainer` path.

---

## Related issue

<!-- If no issue exists yet, open one first or use: -->
Refs # _(optional — link a bug report for "Remotion render fails on local audio paths")_

---

## Background: what existed before

| Area | Prior behavior |
|------|----------------|
| **`video_compose._remotion_render`** | Rewrote local image `cuts[].source` paths to `file://` URIs |
| **`Explainer.tsx` `resolveAsset()`** | Absolute paths → `file://`; relative paths → `staticFile()` under `public/` |
| **`hyperframes_compose`** | Already copies assets into workspace before render |
| **Compose-director skills** | Mentioned `public/` staging for agents but **no tool implemented it** for Remotion |
| **Real-photo / hybrid pipelines** | Expect `source_media_review` + passthrough assets; compose step had no mechanical staging |

**Observed failure** (reproduced on a hybrid real-photo story reel):

```
Not allowed to load local resource: file:///.../narration.mp3
Could not play audio with src file://...
```

Headless Chromium **blocks `file://` for `<Audio>`**. Images sometimes appeared to work; audio always failed. The workaround was manual copy into `remotion-composer/public/<project>/` — undocumented and easy to miss.

---

## Gap

1. **No Remotion asset staging** — unlike HyperFrames, Remotion path assumed agents would hand-place files in `public/`.
2. **Wrong path strategy for audio** — `file://` rewrite is incompatible with Remotion's headless audio loader.
3. **Undocumented contract** — compose-director skills referenced `public/` but tooling did not enforce or automate it.
4. **Silent agent burden** — Rule Zero pipelines expect tools to handle mechanical steps; this was left to ad-hoc scripts.

---

## What we created

### 1. `lib/remotion_asset_staging.py` (new)

Mechanical helper (no creative orchestration):

- `derive_staging_slug()` — from `projects/<slug>/renders/` output path or `metadata.project_id`
- `stage_local_assets_for_remotion()` — copies local media into `remotion-composer/public/<slug>/`
- Rewrites props to `staticFile()`-compatible paths: `<slug>/narration.mp3`
- Handles: absolute paths, `file://` URIs, dedupe when narration + music share one file, basename collision disambiguation
- Skips: `https://` remote assets, already-public-relative paths
- Returns staging report → `metadata.remotion_asset_staging`

### 2. `tools/video/video_compose.py` (modified)

- Calls staging **before** writing `.remotion_props.json`
- **Removes** the `file://` rewrite loop for cut sources
- Attaches staging report to render props metadata for debugging

### 3. Tests (new)

- `tests/lib/test_remotion_asset_staging.py` — 7 unit tests (paths, remote skip, dedupe, collisions)
- `tests/tools/test_video_compose_remotion_staging.py` — integration test with mocked `npx remotion render`

### 4. Skills (docs)

- `skills/pipelines/hybrid/compose-director.md` — Remotion local asset staging section
- `skills/pipelines/explainer/compose-director.md` — automatic staging note under Step 4

---

## Changes

- Add `lib/remotion_asset_staging.py` — stage local cut/audio assets into `public/<slug>/`
- Update `video_compose._remotion_render` to use staging; remove `file://` rewrite
- Add unit + integration tests (8 total)
- Document contract in hybrid and explainer compose-director skills
- **Not included:** unrelated `package-lock.json` peer-metadata churn

---

## Testing

```bash
python -m pytest tests/lib/test_remotion_asset_staging.py -q
python -m pytest tests/tools/test_video_compose_remotion_staging.py -q
```

| Result | Count |
|--------|-------|
| Unit tests | 7 passed |
| Integration (mocked Remotion CLI) | 1 passed |

**Manual verification (recommended by reviewer):**

1. Create a hybrid project with local JPG cuts + local `narration.mp3`
2. Run `video_compose` with `operation: "remotion_render"` and `output_path` under `projects/<slug>/renders/`
3. Confirm render succeeds without manual `public/` copy
4. Confirm `remotion-composer/public/<slug>/` contains staged files

**Platform:** macOS (primary dev); logic is pathlib/shutil — cross-platform.

---

## Architecture alignment

Per [`docs/PR_REVIEW_GUIDE.md`](../PR_REVIEW_GUIDE.md):

| Check | Status |
|-------|--------|
| Agent-first (Python = tools, not orchestration) | ✅ Mechanical staging only |
| No silent runtime swap | ✅ Remotion path unchanged |
| No schema changes | ✅ Uses existing props shape + optional `metadata` |
| Focused scope | ✅ Single concern; no lockfile churn |
| Tests at right level | ✅ Mocked unit + integration |
| Docs match behavior | ✅ Compose-director skills updated |

---

## Checklist

- [x] The change is focused on a single logical concern.
- [x] I ran the relevant tests locally (`pytest` on new test modules — 8/8 passed).
- [x] I updated docs/skills where behavior changed (hybrid + explainer compose-director).
- [x] No unrelated files (build artifacts, local config, lockfile noise) are included in the diff.

---

## Reviewer notes

**Scenario:** Render runtime change (Remotion path only).

**Risk:** Low — additive staging before existing render; remote `https://` assets untouched; already-staged relative paths skipped.

**Follow-up (out of scope):** HEIC support in `source_media_review` (iPhone photo folders) — separate PR.
