# 2026-06-30 — Thiền Đạo standard video production pipeline

**Type:** feature / process codification · **Branch:** `feat/thien-dao-standard-video-pipeline` · **Commit:** 8305145

## What

Codified the de-facto video pipeline (distilled from 3 prior channel videos + memory files) into reusable artifacts, via a chained `/brainstorm → /ck-plan → /ck-predict → /ck-scenario → /cook` workflow. Three phases, all complete:

1. **SOP doc** — `docs/video-production-pipeline.md`: 9-stage pipeline (0–8), locked-defaults table, fallback decision tree, core-vs-meditation split, machine-specific env conditions.
2. **Recipe library** — `scripts/video/montage_lib.py`: 6 pure FFmpeg recipes (`slow_loop_scene`, `make_card`, `concat_segments`, `build_narration_track`, `duck_mux`, `remux_audio`) + `narration_offsets_from_durations` helper.
3. **Validation & wiring** — `_qa.py` (Stage-8 gates) + `_validate_bonmua.py` + `_validate_longform.py`; cross-links across SOP ↔ README ↔ calendar plan ↔ ARCHITECTURE.md.

## Key decisions

- **Library over monolith.** `/ck-predict --chain reason` flipped the artifact from a config-driven `build_video.py` to a recipe library + per-video thin drivers. Three past videos differ too much for one config schema to fit without over-fitting; the real reuse value is DRY-ing the proven FFmpeg recipes, not a driver framework.
- **Security by construction.** All on-screen text routes through drawtext `textfile=` and subprocess runs as arg-lists (never `shell=True`), closing the injection vector in the original `shell=True` + f-string script.
- **Hardened from `/ck-scenario`.** Five gaps patched into the lib: batched amix (scale), idempotent skip-existing renders (crash-resume), `remux_audio` double-music guard, fail-fast missing-asset, and a **hard blocking copyright gate** (`format_tags` scan for Content-ID/CC-BY markers).

## Verification

Ran both validators on real bon-mua assets (output to scratchpad — published renders untouched):
- bon-mua rebuild: 247.5s reduced master (orig published 692s), 1920×1080 h264, voice + copyright gates pass, remux guard accepts silent / refuses non-silent.
- long-form: **240 cues → 8 amix batches, no OOM** + 132s long build path, all QA gates pass.

## Friction / notes

- **1M-context subagent credits unavailable on this machine** — `code-reviewer`, `docs-manager`, `git-manager`, and `journal-writer` subagents all died with a terminal "Usage credits required for 1M context" API error (0 tokens). Performed code review, docs sync, and this journal entry inline against the same checklists. Worth enabling usage credits (or a standard-context subagent model) to restore the delegated `/cook` gates.
- The `narration_dry`/`wet` offset bug from a prior video is now structurally prevented by the offset helper (computes absolute offsets from clip durations).

## Follow-ups

- Long-form sleep format (main growth lane): build path is skeleton-proven but still has no real end-to-end video (needs real Veo/narration assets).
- Philosophy-essay variant: decide whether it's a parameter flag in the same pipeline or a separate one (bilingual karaoke subs, faster pacing).
