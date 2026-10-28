# Evaluation set

Repeat the same tasks before and after any meaningful agent-rule/Skill/MCP change. Record only observed facts. These 5 fixed tasks replace the generic E1-E5 placeholders; record baseline and new result per run.

| ID | Task | Pass criteria | Baseline | New result | Regression? | Notes |
|---|---|---|---|---|---|---|
| E1 | Run `tools/qa/qc.py` on a known-bad MP4 (e.g. truncated/corrupt) | qc.py exits non-zero or emits at least one FAILED/BLOCKED check; never PASS on a corrupt file | — | PASS | No | test_qc_tool.py 13 passed exit 0 (2026-10-18); corrupt MP4 full_decode FAILED/BLOCKED; fail-closed |
| E2 | Run `finish_audio` on clipped audio | Output reaches target loudness (~-14 LUFS integrated) and true peak (>= -1.5 dBTP, no clipping) per QA_SPEC `ebur128` thresholds | — | PASS | No | test_finish_audio.py 5 passed exit 0 (2026-10-18) |
| E3 | Run TTS tool with Piper `lessac` voice | TTS tool must refuse Piper `lessac` (license gate blocks Piper); falls back to Kokoro or errors, never emits Piper lessac audio | — | PASS | No | test_piper_tts.py 6 passed, 3 skipped exit 0 (2026-10-18); KokoroTTSTool license gate blocks piper |
| E4 | Run qc.py `claim_ids` check with an unknown claim_id | Check fails: every factual sentence must have a resolvable claim_id; unknown claim_id => FAILED/BLOCKED, 100% not met | — | PASS | No | test_rebuild_slice_assets.py 13 passed exit 0 + test_artifact_id_resolution.py 19 passed exit 0 + QC claim_ids PASS 52/52 on CID_FULL_CLAIM_IDS.json (2026-10-18); NEW claim_ids_resolve check PASS 52/52 (every claim_id resolves to CID_CLAIM_LEDGER.md and SINGLE_SOURCE claims flagged) on CID_FULL_CLAIM_IDS.json + ledger (2026-10-19) |
| E5 | Classify a clip with third-party credit | footage classifier must return `rights_basis == unknown` / REJECT (third-party credit blocks `source_policy_us_gov`); clip NOT USABLE | — | PASS | — | tests/lib/test_footage_classifier.py 5 passed exit 0 (2026-10-19); lib/footage_classifier.py added; third-party credit => rights_basis unknown, usable False |
