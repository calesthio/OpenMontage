# AUDIT_3_PIPELINE — Audio/video assembly pipeline

Read-only audit. No code changes, no generation, no network/GPU spend.
Date: 2026-11-06. Active branch: `kilo/mega-100`.

## 1. Kokoro TTS integration

- Code: `tools/audio/kokoro_tts.py` (211 lines) + `scripts/z3_kokoro_narrate.py` (64 lines).
- Voice: `af_heart` (American English, female), 24 kHz native, Kokoro-82M weights Apache-2.0.
- Route: HF xet/CDN blocked; working route is `kokoro-onnx` 0.6.1 + ONNX weights from GitHub Releases (`kokoro-v1.0.onnx` 310MB + voices 27MB) into `/tmp/kilo/kokoro_onnx_weights` (gitignored).
- Venv: `/tmp/kilo/z1_venv` — ABSENT in current environment (wiped per Z_STATE). Requirements: `docs/openmontage/z1_voice_venv.requirements.txt`.
- Last successful synthesis: Z1-Z4 (2026-10-19, Artemis draft 3:05) and R2 (2026-10-18, CID slice 52.8s). Smoke artifact: `docs/openmontage/smoke/kokoro_test.mp3` (~22s, 24kHz mono).
- Status: code present and previously working; environment not currently runnable (venv/weights removed). License residual risk: training-data provenance (synthetic data) UNKNOWN.

## 2. Audio modules

| File | Lines | Status | Tests |
|---|---|---|---|
| `lib/sentence_segmenter.py` | 252 | Real code | `tests/lib/test_sentence_segmenter.py` |
| `lib/audio_alignment.py` | 299 | Real code | none direct (used by audio tests) |
| `lib/audio_engine.py` | 362 | Real code | indirect |
| `lib/audio_qc.py` | 399 | Real code | indirect |
| `lib/sentence_timeline.py` | 184 | Real code | none direct |
| `lib/audio_production_engine.py` | 556 | Real code | `tests/lib/test_audio_production_engine.py` |
| `lib/audio_mixing.py` | 376 | Real code (one `pass` in exception handler) | indirect |

All six requested modules exist and contain substantive implementations (no stubs). `audio_production_engine.py` is the main orchestrator; `audio_alignment.py` and `sentence_timeline.py` support sync/timing; `audio_qc.py` QC checks; `audio_mixing.py` mixing.

## 3. Stickman SVG rig and compositing

- Rig: `lib/stickman_rig.py` (pure-Python SVG emitter: RigProfile, Pose/Expression/Prop, FK, SVG emission, keyframe validation, content-addressed cache key). Zero-cost. Tests: `tests/lib/test_stickman_rig.py`.
- Pose library: `lib/stickman_pose_library.py`, continuity: `lib/stickman_continuity.py`.
- Compositing claim (Playwright SVG->PNG + PIL alpha-composite): verified in V2/V3 creative reviews. V2: 11 scenes composited, 26k+ teal pixels verified. V3: 11 scenes, 29,404 teal pixels at frame @2s. Both final videos QC PASS.
- Within-scene limb animation: NOT implemented (static overlay per scene; pose changes between scenes only). Full keyframe animation requires Remotion compositing (deferred). So: compositing works; animation is partial.

## 4. Remotion project

- Path: `remotion-composer/`. `package.json` valid (Remotion 4.0.484, React 18, TS 5.3). `node_modules` present (136 entries). Build script: `npx remotion render src/index.tsx Explainer out/video.mp4`.
- Compositions registered in `Root.tsx`: Explainer, CinematicRenderer, SignalFromTomorrowWithMusic, TalkingHead, TitledVideo, PilotScene1, PilotDraft, HeroTitle, ProductReveal, ProductRevealVertical, CaptionOverlayOnly, CollageBurst, LyricOverlay, EndTag, EndTagOverlay.
- Not run here (would require Chrome/render time); project structure and Root.tsx are valid. TypeScript entry `src/index.tsx` exists.

## 5. Video/render modules

| File | Lines | Status | Tests |
|---|---|---|---|
| `lib/render_engine.py` | 587 | Real code (4 `pass` in exception handlers) | indirect (final_qc, p4_render) |
| `lib/edit_decision_engine.py` | 486 | Real code | indirect |
| `lib/production_timeline.py` | 288 | Real code | indirect |
| `lib/preview_system.py` | 329 | Real code | none direct |
| `lib/audio_mixing.py` | 376 | Real code | indirect |

No stubs. `render_engine.py` handles rendering; `edit_decision_engine.py` EDL; `production_timeline.py` timeline; `preview_system.py` preview; `audio_mixing.py` mixing.

## 6. Pilot V1/V2/V3 reports and QC

- V1: 174.37s, 1920x1080, 37.7 MB, QC PASS (21 checks). Issues: 15 static scenes, no stickman in render (metadata only), no music bed, black bars in 6 segments, image resolution 1376x768 upscaled.
- V2: 174.37s, 36.6 MB, QC PASS (21 checks). Added stickman (11 scenes, verified pixels), motion on all scenes (pan_zoom), ambient music bed, normalized audio. Issues: static override bug (move_type vs motion_type) left 15 scenes static in practice, black bars remained, SFX not timed, stickman static pose only.
- V3: 174.37s, 52.2 MB, QC PASS (25 checks). Fixed black bars (0/58 frames), fixed static override (0 static), stickman present (29,404 teal pixels). Issues: SFX still not timed, no infographic overlays, image resolution still upscaled, Remotion stickman animation not done, some comic-panel compositions remain.

## Reproduce commands
```
wc -l lib/sentence_segmenter.py lib/audio_alignment.py lib/audio_engine.py lib/audio_qc.py lib/sentence_timeline.py lib/audio_production_engine.py lib/audio_mixing.py lib/render_engine.py lib/edit_decision_engine.py lib/production_timeline.py lib/preview_system.py
cat tools/audio/kokoro_tts.py
ls remotion-composer/src && cat remotion-composer/package.json
cat projects/pilot/first_video/qc/final_v2_qc.json | head -20
cat projects/pilot/first_video/qc/final_v3_qc.json | head -20
```
