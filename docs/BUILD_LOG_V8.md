# BUILD_LOG_V8

OpenMontage Factory — V8 implementation log.
V8 source of truth: `FACTORY_RESEARCH_AND_ARCHITECTURE_AUDIT_V8.md`.
Budget: $0 strict zero-cost. No auto-publish. Human approval required for release.

## Format

Each entry: date, P0/wave item, files changed, status, notes.

Committed after every completed P0 item (8.1–8.6) and after every wave item.

---

## Log

### 2026-11-07 — Session start

- Extracted `FACTORY_RESEARCH_AND_ARCHITECTURE_AUDIT_V8.md` from git commit `944c0de` (was absent from working tree).
- Audited current code: `lib/checkpoint.py` (atomic tmp+os.replace checkpoint writes), `lib/budget_guard.py` ($0 guard with free fallbacks), `lib/zero_cost_gate.py` (fail-closed gate, `reroute_allowed=False`), `lib/motion_director.py` (`STATIC_LIMIT_SEC=15.0` hard-coded as law), `scripts/release_checklist.py` (`STATIC_MAX_SEC=15.0` hard pass/fail), `lib/final_qc.py` (blocking/non-blocking check split), `lib/tts_engine.py` (Kokoro+Piper per-sentence), `lib/scene_router.py` (archival vs ai_generated binary).
- No code changes yet. Starting P0.

### 2026-11-07 — P0 8.1 (DONE)

- `lib/checkpoint.py`: added `COMPLETED_REQUIRED_ARTIFACT_KEYS = {"checksums", "qc_passed"}`. `write_checkpoint` now rejects `status="completed"` unless artifacts carry a non-empty `checksums` map and `qc_passed == True`. Atomic tmp+os.replace rename retained. Moved completed-validation after `_enforce_stage_prerequisites` so prerequisite violations surface first.
- `tests/lib/test_checkpoint_resume_identity.py`: updated all three `write_checkpoint(..., "completed", ...)` calls to include `checksums` and `qc_passed: True`.
- Status: all 16 checkpoint tests pass.

### 2026-11-07 — P0 8.2 (DONE)

- Created `lib/state_store.py`: SQLite-backed durable runtime state store.
  - Table `stage_state`: project_id, stage, pipeline_type, status, failure_class, input_fingerprint, output_artifacts, checksums, qc_passed, retry_count, reason_code, warning, requires_approval, timestamps.
  - Table `events`: append-only event log.
  - Statuses: PENDING, RUNNING, PASSED, DEGRADED, BLOCKED, FAILED, NEEDS_REVIEW, SKIPPED.
  - Failure classes: REQUIRED, OPTIONAL, DEGRADABLE, MANUAL_REVIEW.
  - `transition()` for atomic status changes; `complete()` enforces V8 §8.1 (checksums + qc_passed); `fail()` records failure class.
  - WAL journal mode, single transaction per write, explicit commit.
- Verified with smoke test: transition→complete→fail round-trip works.
- Status: new module, no existing tests broken.

### 2026-11-07 — P0 8.3 (DONE)

- `lib/scene_router.py`: added `failure_class` field to `RouteDecision` (default OPTIONAL). Archival-missing → AI fallback = OPTIONAL; budget guard refusal = REQUIRED.
- `lib/motion_director.py`: added `failure_class` field to `MotionPlan` (default DEGRADABLE). zoompan failure → fallback_used = DEGRADABLE (continue with warning, static frame accepted).
- `lib/tts_engine.py`: added `failure_class` field to `TtsResult` (default OPTIONAL). Piper fallback = OPTIONAL; both engines failed = REQUIRED (cannot assemble without voice).
- Field order fixed in dataclasses (`reason` before `failure_class` with defaults).
- Verified: all three modules import and produce correct failure_class defaults.

### 2026-11-07 — P0 8.4 (DONE)

- `lib/budget_guard.py`: V8 §8.4 — fallback never uses Google Flow. `_fallback_for` now explicitly says "Never Google Flow — no credits, no hidden generation" for image/video generation, and adds a `flow_generation` entry that returns "BLOCKED — Google Flow never used as fallback. Retry must not spend credits." Existing assets are never renamed to newly_generated.
- Verified: guard returns fallback_used for paid ops, success for $0, fallback text contains anti-Flow language.
- Existing tests: 3 passed (test_zero_cost_gate + budget/guard tests in tests/lib/).

### 2026-11-07 — P0 8.5 (DONE)

- `lib/motion_director.py`: `STATIC_LIMIT_SEC` re-documented as "warning threshold, not an absolute quality law" (V8 §8.5). `MotionPlan` gains `motion_advisory: bool` — set True when hold > limit and motion could not be applied (static hold is advisory, not blocking).
- `scripts/release_checklist.py`: `max_static_segment_sec` and `avg_visual_change_interval_sec` now return WARNING (passed=None, non-blocking) when > 15s, instead of hard FAIL. Overall verdict still requires all blocking checks to pass; advisory warnings don't block.
- `FACTORY_100_SPEC.md` line 74 ("still-only <= 15 s unless motion-lint passes") left untouched per file header instruction — change proposed via SPEC_CHANGE_REQUESTS.md instead.

### 2026-11-07 — P0 8.6 (DONE)

- `lib/render_integration.py`: V8 §8.6 — rejected "strictly not worse on every metric". `ready_for_render` now requires only blocking (critical technical guardrails) checks to pass. Non-blocking checks (severity "low") are advisory — they don't block render. `all_passed` still computed for info but doesn't gate render. Removed unused `blocking_passed` variable.
- Verified: 19 existing render_integration tests pass.
- All 6 P0 items (8.1–8.6) complete.

### 2026-11-07 — Волна 1.1: A/V sync по audio master (DONE)

- Created `lib/audio_master.py`: V8 §3.4 audio-as-single-source-of-time.
  - `VoiceBlock`: per-block WAV with sample_count, sample_rate, duration_seconds, pause_after, crossfade, engine.
  - `NarrationMaster`: concatenated master WAV, duration measured from actual samples (soundfile/ffprobe), never from ASR/WPM.
  - `TimelineManifest`: single manifest driving Remotion + FFmpeg; scene timings derived from rational timebase (fps_num/fps_den), no per-frame independent rounding.
  - `probe_wav_duration()`: sample_count/sample_rate/duration from actual WAV samples.
  - `build_narration_master()`: ffmpeg concat of blocks with pauses/crossfades.
  - `build_timeline_manifest()`: manifest anchored to narration master.
- Updated `lib/tts_engine.py`: added `synthesize_blocks()` — synthesizes semantic voice blocks (paragraphs), preserves each block WAV with parameters (V8 §8.11).
