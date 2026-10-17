# OpenMontage Factory — Session Resume State

**Last Updated:** 2026-10-16
**Git Branch:** `factory/business-documentary-pilot` (working branch; `main` untouched)
**Last Commit:** `40f1910` — feat(business-documentary): 12-stage evidence-first factory pipeline
**Remote:** pushed and confirmed to `origin/factory/business-documentary-pilot`
**Master Plan:** docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md v1.0 (+ v3.1 changelog entry, Milestone A docs only)

---

## Milestone S — 2026-10-16 (tooling audit + minimal skills; observed vs assumed)

- **Observed (from artifacts/CODE):** pilot used piper/piper-tts 1.8.0 voice
  `en_US-lessac-medium` (84.975 s measured), segment-level subtitles (16 cues,
  burned), `render_runtime: ffmpeg` 6.1.1 (d-002; remotion unavailable),
  `direct_clip_search` over Wikimedia Commons (6 CC assets), music silence (d-003).
- **Observed (licenses):** repo AGPL-3.0; voice CC-BY-4.0 exists ONLY as a manifest
  assertion → UNKNOWN; engine/ffmpeg/weights → UNKNOWN from repo files.
- **Observed (skills):** Kilo 7.8.12; project path `.kilo/skills/` per official Kilo
  skills doc. Installed 7 skills (superpowers `bb92a77`, youtube-agent-skill
  `a2feb21`, both MIT; every SKILL.md + script read, no network/secrets found).
  `hookscore.py`/`title.py`/`chapters.py` verified (`py_compile` exit 0 + live runs
  observed). yt-chapters needed vendored `deadair.py` + 4-line import fallback.
- **Assumed (not verified):** Kilo auto-discovery of `.kilo/skills/` in this layout
  (no Kilo session run); voice-license validity for commercial use.

---

## Milestone A — 2026-10-16 (docs only; observed vs assumed)

- **Observed (from CODE):** 16 registered stock adapters in `tools/video/stock_sources/`
  (12 keyless/optional-key, 4 key-gated); NASA + NARA adapters exist
  (`tools/video/stock_sources/nasa.py`, `nara.py`), DVIDS does not (zero hits);
  `Candidate`/`ClipRecord`/`asset_manifest` carry `license` but no
  `storage_policy`, no `archive_id/caption/date`, no `identifiable_persons`,
  no `logo_visible`, no `third_party_copyright`, no `credit_required`;
  `asset_manifest` does have `attribution`, `sha256`, `chosen_interval` (in/out);
  no per-provider storage/rights policy file exists (`storage_policy` zero hits);
  no QA gate measures original-content share; `qa_report` schema exists but the QA
  stage artifact gap stands (no `qa_report.json` written — known gap).
- **Assumed (not verified):** competition, creator-country monetization eligibility,
  RPM (third-party estimates only). Recorded in `docs/openmontage/NICHE_DECISION.md`.
- **Files created:** `docs/openmontage/NICHE_PROFILE_SPEC.md`,
  `docs/openmontage/NICHE_DECISION.md`. No code, installs, model runs, or lock changes.

---

## Current Goal

Implement the **business-documentary pipeline** (12 stages, 13 director skills) declared by
the Master Plan, together with the governance it demands — strict $0 gate, cross-artifact ID
resolution, fail-closed QA — and prove the chain with a real test suite.

---

## Master Plan Stage Status

| Stage | Status | Evidence |
|-------|--------|----------|
| **P0.1 Re-verify git state / `--db-path`** | ✅ Complete | `git status --short` clean; no `--db-path` file exists in the repo; the modified files listed in the Kilo screenshot are not present. Nothing was deleted or reset. |
| **P0.2 Diagnose the pytest timeout** | ✅ Complete | Root cause: **pytest was not installed** in this environment (`No module named pytest`) and `tests/factory/` did not exist. Installed `pytest 9.1.1` + `pytest-asyncio` (dev deps from `requirements-dev.txt`, $0). Test groups then run **separately with exit codes** — see the table below. |
| **P0.3 Verify 12 stages + 13 skills** | ✅ Implemented | They did **not** exist. Now created: `pipeline_defs/business-documentary.yaml` (12 stages) + `skills/pipelines/business-documentary/` (13 skills) + 7 new artifact schemas. Contract tests assert stage order, gates, tool names and skill files. |
| **P0.4 Verify TTS / diagram / stock render** | 🟢 Mostly verified | **Diagram: verified with a real artifact** (Pillow render writes an 8.5 KB PNG). **TTS: verified with real audio** — `piper-tts` 1.8.0 installed, `en_US-lessac-medium` voice downloaded, real WAV synthesized (5.27 s for the test sentence, pcm_s16le 22 050 Hz mono, clean full decode). **Stock adapters: error taxonomy verified** with fakes; live no-key archive search not yet run. |
| **P0.5 Verify $0 gate + stock adapter errors** | ✅ Implemented | New `lib/zero_cost_gate.py`: unknown cost / unknown route / unapproved paid call / unavailable tool → **BLOCKED**. Failure taxonomy (auth / billing / rate_limit / transport / no_results) kept distinct; `reroute_allowed()` is always `False`. |
| **P1 First E2E pilot (60–90s)** | ✅ Complete | `projects/pallets-hidden-business/`: all 11 stages (topic → compose) completed and checkpointed. Rendered MP4 at `renders/pallets-hidden-business.mp4` — h264 1920×1080 30fps, aac 22050Hz mono, 84.975s, 32.16 MB, full `ffprobe` decode clean. Music: silence (recorded decision d-003). Publish excluded by user directive. |

---

## What's Completed

- ✅ `pipeline_defs/business-documentary.yaml` — 12 stages (`topic → research → evidence →
  script → fact_check → storyboard → narration → footage → editorial → compose → qa →
  publish`), `budget_default_usd: 0.0`, gated stages per Master Plan.
- ✅ 13 director skills in `skills/pipelines/business-documentary/` (executive-producer +
  one director per stage).
- ✅ 7 new artifact schemas: `topic_brief`, `evidence_ledger`, `fact_check_report`,
  `narration_manifest`, `alignment_report`, `qa_report`, `publish_package` — registered in
  `schemas/artifacts/__init__.py`.
- ✅ Additive schema extensions the pipeline needs: `script.sections[].evidence_ids`,
  `scene_plan.scenes[]` (`search_queries`, `visual_class`, `diagram_spec`, …),
  `asset_manifest.assets[]` (`author`, `attribution`, `license_url`, `sha256`,
  `search_query`, `selection_reason`, `qa_verdict`, …), `research_brief.sources[]`
  (`source_id`, `publisher`, `source_type`, …), and optional `run_id`/`created_at` on the
  six artifacts the pipeline produces.
- ✅ `lib/zero_cost_gate.py` — strict $0 gate, failure taxonomy, search-stats summary,
  run ledger.
- ✅ `lib/artifact_ids.py` — cross-artifact ID resolution (evidence / source / scene /
  asset / QA gate) with precise dangling-reference reporting.
- ✅ `tools/audio/piper_tts.py` — bare voice name now resolves through `PIPER_VOICES_DIR`,
  `~/.local/share/piper/voices` and cwd, and fails with an actionable message.
- ✅ `tests/factory/` — 150 tests, all passing.
- ✅ P1 pilot **all 11 stages** for *“Why Pallets Matter to Global Shipping”*
  (`projects/pallets-hidden-business/artifacts/`), validated and checkpointed through
  `compose`. Rendered MP4: h264 1920×1080 30fps, aac 22050Hz mono, 84.975s, 32.16 MB,
  full `ffprobe` decode clean.
- ✅ Environment fix (free, no repo change): installed **ffmpeg 6.1.1** via apt. This
  flipped `video_post` 0/10 → 9/10, `audio_processing` 0/2 → 2/2 and cleared two
  pre-existing environment-caused test failures.

---

## What's NOT Completed

- ❌ **Publish** — excluded by user directive ("Do not publish videos"); the Master Plan also
  gates publish on primary-source retrieval, which is still outstanding.
- ❌ Remotion runtime: `remotion-composer/node_modules` is empty (`npx hyperframes` 0.8.159
  **is** available; ffmpeg is available; Remotion is not).
- ❌ No web-search tool exists in the registry — the research stage depends on
  human-supplied sources or `video_downloader` / `transcript_fetcher` (both `unavailable`
  without `yt_dlp` / `youtube_transcript_api`).
- ❌ `music_library/` does not exist yet; music decision is recorded as silence (d-003).
- ✅ TTS unblocked this session: `piper-tts` 1.8.0 + `en_US-lessac-medium` voice installed
  locally (`~/.local/share/piper/voices/`); `piper_tts` now reports `available`
  (tts capability 0/13 → 1/13).
- ✅ `piper_tts` bare-voice resolution fixed: `PIPER_VOICES_DIR` →
  `~/.local/share/piper/voices` → cwd, with an error naming the download command.

---

## Changed Files (This Session)

New:
- `pipeline_defs/business-documentary.yaml`
- `skills/pipelines/business-documentary/{executive-producer,topic,research,evidence,script,
  factcheck,storyboard,narration,footage,editorial,compose,qa,publish}-director.md` (13)
- `schemas/artifacts/{topic_brief,evidence_ledger,fact_check_report,narration_manifest,
  alignment_report,qa_report,publish_package}.schema.json`
- `lib/zero_cost_gate.py`, `lib/artifact_ids.py`
- `tests/factory/{__init__,test_pipeline_contract,test_artifact_schemas,
  test_artifact_id_resolution,test_zero_cost_gate,test_dry_run_chain,
  test_factory_environment,test_narration_real_audio,test_pilot_artifacts}.py`
- `tests/tools/test_piper_tts.py`
- `docs/OPENMONTAGE_RESUME.md`, `docs/OPENMONTAGE_WORK_LOG.md`

Run-local (gitignored by design — `projects/` is in `.gitignore`):
- `projects/pallets-hidden-business/` — full pilot: 11 stage artifacts, 11 checkpoints,
  6 footage clips/stills, 1 diagram, narration WAV, subtitles SRT, and the rendered
  `renders/pallets-hidden-business.mp4` (h264 1920×1080 30fps, aac, 84.975s, 32.16 MB).
- `projects/pallets-hidden-business/pallets-hidden-business/` — canonical nested checkpoint
  directory (`lib.checkpoint._checkpoint_path` resolves here); the top-level copies are
  preserved for backward compatibility with any tool that reads `projects/<id>/`.

Because the pilot directory is gitignored, `tests/factory/test_pilot_artifacts.py` skips when it
is absent. If the Codespace is lost, the pilot artifacts must be regenerated from the two
source URLs recorded in `research_brief.json` (both were read in full, quotes are verbatim).

Modified (additive only):
- `schemas/artifacts/__init__.py` (7 new artifact names)
- `schemas/artifacts/{script,scene_plan,asset_manifest,research_brief,render_report,
  publish_log}.schema.json` (new optional/provenance fields, tertiary tier in the
  research-brief reliability/credibility enums)
- `tools/audio/piper_tts.py` (voice resolution + install instructions)
- `tests/contracts/test_runtime_presentation_contract.py` (planning-stage lookup falls back
  to a pipeline's first stage)
- `AGENTS.md` (Factory session reading order)

---

## Commands Run & Results

```bash
# P0.2 — test infrastructure
pip install "pytest>=8.0" "pytest-asyncio>=0.23"     # pytest 9.1.1

# P0.2 — per-group runs (no tail, exit codes collected; after ffmpeg install)
python -m pytest tests/contracts -q   # 1244 passed, 7 skipped, exit 0
python -m pytest tests/lib -q         #   58 passed,             exit 0
python -m pytest tests/qa -q         #    2 skipped,           exit 0
python -m pytest tests/styles -q     #   15 passed,           exit 0
python -m pytest tests/backlot -q    #   37 passed, 1 skipped, exit 0
python -m pytest tests/tools -q      #  687 passed, 3 xfailed, exit 0
python -m pytest tests/factory -q    #  135 passed,           exit 0
# tests/pipelines and tests/eval collect no tests (exit 5) — pre-existing:
# both directories hold harness code/fixtures only.

# Environment fix (free)
sudo apt-get install -y ffmpeg          # ffmpeg 6.1.1, exit 0

# Registry preflight after ffmpeg
registry.provider_menu_summary()
# composition_runtimes: {'ffmpeg': True, 'remotion': False, 'hyperframes': True}
# tts 0/13, video_generation 0/31, image_generation 0/23, video_post 9/10

# P0.4 — real diagram artifact
DiagramGen().execute({'diagram_type':'boxes', ..., 'output_path': tmp})
# success=True, 8590-byte PNG written, PNG magic bytes verified
```

P0.4 — real narration artifact (local, free):

```bash
pip install piper-tts                                # 1.8.0 + onnxruntime
python -m piper.download_voices en_US-lessac-medium  # voice model
ffprobe /tmp/opencode/piper_smoke.wav
# codec_name=pcm_s16le, sample_rate=22050, channels=1, duration=5.270930
ffmpeg -v error -i .../piper_smoke.wav -f null -     # decode exit 0
```

---

## Stop Point & Next Action

**Stop Point:** The P1 pilot is **complete** through stage 11 (`compose`). All 11 stages are
checkpointed as `completed` with `human_approved=True` (topic gate approved 2026-10-15 via
decision d-001, "Then execute Phase 1 only"). The rendered MP4
(`projects/pallets-hidden-business/renders/pallets-hidden-business.mp4`) passes `ffprobe`
full decode: h264 1920×1080 30fps, aac 22050Hz mono, 84.975s, 32.16 MB. Stage 12 (`publish`)
is **excluded** by the user directive and by the Master Plan's primary-source gate.

**Milestone D1 (2026-10-16) — complete:** audio + editing toolchain audited; docs + skills
only (no paid routes, no keys, no process/lock changes). See
`docs/openmontage/TOOLING_DECISIONS.md` §12, `docs/openmontage/EDITING_DOCTRINE.md`,
`docs/openmontage/MUSIC_POLICY.md`, and `.kilo/skills/{cutting-rhythm,edl-edit,audio-edit}/`.

**Next Action (exact):** resume P2 scope:
- Retrieve primary sources (IPPC ISPM 15 text, NWPCA/USDA statistics, pooler filings) before
  any publish package — currently blocked by the Master Plan's primary-source gate.
- Populate `music_library/` with hand-verified licensed tracks for future renders (see
  MUSIC_POLICY.md required record fields).
- Add a registered web-search tool so `research` does not depend on human-supplied URLs.

---

## Blockers & Risks

1. **No TTS synthesizer** — ✅ RESOLVED this session: `piper-tts` 1.8.0 installed with the
   `en_US-lessac-medium` voice; `piper_tts` reports `available`. Cloud TTS remains blocked by
   strict $0 mode (unknown pricing → BLOCKED).
2. **No video_generation / image_generation** (0/31, 0/23 configured) — the pipeline is
   designed around real footage, so this is acceptable, but it leaves no fallback B-roll.
3. **`clip_retrieval` (CLIP) and `corpus_population` unavailable** — only `direct_clip_search`
   is usable, so visual alignment relies on frame inspection rather than embedding ranking.
4. **Remotion runtime missing** (`node_modules` empty) — `render_runtime` must be chosen from
   ffmpeg + hyperframes only, with both recorded in the `render_runtime_selection` decision.
5. **Research has no registered web tool** — sources came from the agent's own fetch tooling
   (two articles read in full, quotes verbatim). The pilot's evidence is therefore
   **tertiary**, and the primary-source gaps are recorded in `research_brief.metadata.gaps`.
   This is a hard gate before any publish package.
6. **No force-push / destructive commands used.** All work is on a working branch.

P1 pilot commands run:

```bash
# stage 1..3 built, validated, checkpointed at the human topic gate
python -c "... validate_artifact + artifact_ids.resolve_all + write_checkpoint('topic','awaiting_human')"
# → topic_brief / research_brief / evidence_ledger schema OK, 0 dangling refs,
#   projects/pallets-hidden-business/checkpoint_topic.json = awaiting_human

# regression check after the research_brief enum change
python -m pytest tests/contracts tests/tools tests/lib -q   # 2000 passed, 7 skipped, 3 xfailed
python -m pytest tests/factory -q                          # 150 passed
```

---

## Budget / $0 Mode Verification

- **Mode:** strict_zero_cost=true (Master Plan); `orchestration.budget_default_usd: 0.0`.
- **Gate:** `lib/zero_cost_gate.evaluate_call()` — `cost_usd=None` → BLOCKED; `route=None` →
  BLOCKED; non-zero cost → BLOCKED without explicit user approval; tool not `available` →
  BLOCKED (surface as setup request, never reroute).
- **Calls made this session:** ffmpeg install (apt, free), pip install of dev dependencies
  and `piper-tts` (free), voice-model download (free), local diagram render and local
  narration synthesis (local CPU, free). **No paid API call, no video generation, no upload,
  no YouTube publish.**
