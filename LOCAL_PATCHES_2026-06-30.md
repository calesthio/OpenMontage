# Local patches — 2026-06-30

Bug fixes applied on top of upstream `299dd4f` (Merge PR #236).
Both are independent of, and complementary to, the already-applied **PR #238**
(local zero-key asset staging → `public/_om_assets`). They make the
`documentary-montage` (CinematicRenderer) Remotion render path actually produce
visible footage from a schema-compliant `edit_decisions`.

Verified: full test suite **426 passed / 8 skipped**; end-to-end render of a
schema `cuts` edit_decisions (no hand-authored `scenes`) with `music:{source:"none"}`
produces a non-black 1080p MP4 (frame inspected).

---

## Fix 1 — CinematicRenderer crashes on a music/soundtrack object without `src`

**File:** `remotion-composer/src/CinematicRenderer.tsx`

**Symptom:** Whole render aborts with
`TypeError: Cannot read properties of undefined (reading 'startsWith')`
at `resolveAsset` ← `Soundtrack`. Triggered by a music opt-out that passes a
truthy-but-srcless object, e.g. `music: {"source": "none"}`.

**Root cause:** the render sites guarded the *object* (`{music ? …}` /
`{soundtrack ? …}`) but then passed `music.src` / `soundtrack.src` (which is
`undefined`) into `<Soundtrack>` → `resolveAsset(undefined).startsWith(...)`.

**Fix:**
- `resolveAsset()`: `if (!src) return "";` (fail soft instead of throwing).
- Render sites: guard on `.src` — `{music?.src ? …}` and `{soundtrack?.src ? …}`.

---

## Fix 2 — documentary-montage renders a black video (cuts never mapped to scenes)

**File:** `tools/video/video_compose.py` (`_remotion_render`)

**Symptom:** `operation="render"` with a schema-valid `edit_decisions` (which
carries `cuts`, per `schemas/artifacts/edit_decisions.schema.json`) and
`renderer_family="documentary-montage"` "succeeds" but the output is a 30s black
video. This is the core "local rendering broken" symptom.

**Root cause:** `documentary-montage` / `cinematic-trailer` route to the
`CinematicRenderer` composition, which consumes a `scenes[]` array
(`{id, kind, src, startSeconds, durationSeconds}`). `_render` →
`_remotion_render` passes `edit_decisions` through (staging `cuts[].source` to
`public/`) but never builds `scenes`. The composition falls back to its empty
default `scenes` → black render, 30s default duration.

**Fix:** in `_remotion_render`, after asset staging, when the target composition
is `CinematicRenderer` and no `scenes` are present, build video `scenes` from the
staged `cuts` (cumulative `startSeconds`, `durationSeconds = out − in`, falling
back to `duration_seconds`). Gated so non-cinematic compositions (Explainer etc.)
are untouched.

---

## Not changed / out of scope
- Music generation still requires a provider key (ElevenLabs `music_gen`
  unavailable without one); the fixes above make the *no-music* path valid.
- `corpus_builder` (degraded) / `clip_search` (unavailable) — standard CLIP
  retrieval path; the fast path (`direct_clip_search`) works zero-key.
