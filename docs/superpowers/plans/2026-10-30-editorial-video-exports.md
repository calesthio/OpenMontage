# Editorial Video Exports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add a selectable 9:16 social and 16:9 1080p desktop export workflow plus a restrained editorial-data visual playbook.

**Architecture:** Register one platform-neutral `social_vertical` media profile; store one or both chosen output profiles in the proposal artifact; let the existing composer render the approved edit once per selected profile and report each output. Add a new YAML playbook without changing existing styles or the read-only Backlot.

**Tech Stack:** Python `MediaProfile`, JSON Schema, YAML style playbooks, pipeline Markdown, pytest, FFmpeg/ffprobe.

**Spec:** `docs/superpowers/specs/2026-10-30-editorial-video-exports-design.md`

## Global Constraints

- New proposal checkboxes default to both formats selected; at least one output is required.
- Profiles: `social_vertical` = 1080×1920, 30 fps; `youtube_landscape` = 1920×1080, 30 fps.
- Each selected format is rendered as a separate aspect-specific output, not derived by cropping the other output.
- Existing proposals without `production_plan.output_profiles` keep their legacy single-target behavior.
- Backlot remains read-only; no TTS provider, model download, or API key is added.
- Playbooks without an explicit background effect retain ambient defaults; only the new editorial playbook opts into a flat background.
- Preserve the user's existing `remotion-composer/package-lock.json` modification.

## Review Focus

1. Empty, duplicate, or unknown output-profile selections must be rejected by the proposal schema.
2. A legacy proposal with no output profile list must remain valid and use the previous single-target route.
3. Social profile must not inherit one platform's duration/file-size cap as a universal limit.
4. Each format must encode the requested dimensions, frame rate and codec, with distinct file paths.
5. Dark-playbook text, caption and chart colors must remain legible in both aspect ratios.
6. The flat-background option affects only the new playbook; existing playbooks remain ambient.

---

### Task 1: Add profile selection and dual output workflow

**Files:**
- Modify: `lib/media_profiles.py`
- Modify: `schemas/artifacts/proposal_packet.schema.json`
- Modify: `skills/pipelines/explainer/proposal-director.md`
- Modify: `skills/pipelines/explainer/compose-director.md`
- Test: `tests/contracts/test_output_profiles.py`
- Test: `tests/contracts/test_phase0_contracts.py`
- Test: `tests/tools/test_video_compose_vertical.py`

**Interfaces:**
- Proposal field: optional `production_plan.output_profiles: string[]`; when present, non-empty, unique, and limited to `social_vertical` and `youtube_landscape`.
- The compose stage reads that approved list and calls `video_compose` once per profile with a distinct output path; the existing `render_report.outputs` array records the results.

- [x] **Step 1: Write failing profile and proposal-schema tests**
  - Assert `get_profile("social_vertical")` is 1080×1920 at 30 fps and has no platform-specific duration/file-size cap.
  - Assert a valid proposal accepts either profile or both, rejects empty/duplicate/unknown profile arrays, and still accepts a legacy proposal without the field.
- [x] **Step 2: Run focused tests and confirm the new-profile/schema assertions fail for the expected missing behavior.**
- [x] **Step 3: Add `SOCIAL_VERTICAL` to the media profile registry; add the optional validated `output_profiles` schema property.**
- [x] **Step 4: Update proposal instructions to show both `[x]` output choices by default and persist the user's chosen non-empty list.**
- [x] **Step 5: Update compose instructions to render each selected profile separately, use profile-specific filenames, preserve the existing single-target path for older proposals, and record one report output per file.**
- [x] **Step 6: Add/adjust FFmpeg-backed tests that render a small fixture for both profiles and assert the actual output dimensions and distinct paths.**
- [x] **Step 7: Run focused tests (12 passed); attempt the full suite and record the unrelated failure/timeout in the ledger.**

### Task 2: Add the editorial-data explainer playbook and renderer support

**Files:**
- Create: `styles/editorial-data-explainer.yaml`
- Modify: `schemas/styles/playbook.schema.json`
- Modify: `pipeline_defs/animated-explainer.yaml`
- Modify: `tools/video/video_compose.py`
- Modify: `remotion-composer/src/Root.tsx`
- Modify: `remotion-composer/src/Explainer.tsx`
- Modify: `lib/hyperframes_style_bridge.py`
- Test: `tests/contracts/test_phase3_contracts.py`
- Test: `tests/contracts/test_remotion_theme_playbook_keys.py`
- Test: `tests/tools/test_hyperframes_compose.py`

- [x] **Step 1: Write failing tests** for the playbook's schema/manifest registration, chart-palette mapping, flat-background theme mapping, and HyperFrames style-token output. Update the HyperFrames fixture to use canonical playbook schema keys.
- [x] **Step 2: Run those tests and confirm the expected missing-style/mapping failures.**
- [x] **Step 3: Add the editorial playbook and recommend it for animated explainers.**
- [x] **Step 4: Add an optional `visual_language.background_effect` (`ambient` or `flat`) and route `chart_palette` and the background effect into Remotion themes; keep ambient as the default for existing playbooks.**
- [x] **Step 5: Let Remotion suppress ambient gradients/orbs only when a theme requests `flat`; expose the same flat effect, canonical typography/muted colors, and chart palette in HyperFrames style tokens/design notes.**
- [x] **Step 6: Run scoped validation and both profile/style smoke renders (116 tests passed, TypeScript clean); the full-suite attempts and failure are recorded in the ledger.**

## Completion checks

- Confirm the new proposal choices select either/both outputs without changing old proposal behavior.
- Confirm the style is discoverable, valid, and leaves existing playbooks unchanged.
- Report only tests, renders, and voice-provider facts actually verified; no production video or TTS audio is generated in this change.
