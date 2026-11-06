# AUDIT_4_QC_AND_RECONCILE — QC, end-to-end, reconcile, scoring

Read-only audit. No code changes.
Date: 2026-11-06. Active branch: `kilo/mega-100`.

## 1. QC modules — concrete checks

### `tools/qa/qc.py` (1341 lines) — main technical QC (ffprobe/ffmpeg-based)
Checks (each returns PASS/FAILED/BLOCKED/NOT_RUN):
1. thresholds_config (config load, fail-closed)
2. ffprobe_streams (streams readable)
3. full_decode (ffmpeg full decode no errors)
4. blackdetect (black frame ratio)
5. freezedetect (max freeze, static_by_design exemption)
6. silencedetect (silence ratio)
7. ebur128 (LUFS/TP)
8. duration_vs_script (narration manifest drift)
9. subtitle_sync (SRT end times vs audio)
10. credits_complete (credits.txt present)
11. claim_ids (every sentence has claim_id)
12. claim_ids_resolve (every id resolves to ledger; SINGLE/UNVERIFIED flagged)
13. rights_basis (rights records per clip)
14. added_value (graphics/stills share vs archive)
15. motion_variety (no consecutive identical moves)
16. speculative_label (only for speculative niches; AI cuts labelled)
Verdict logic: FAILED if any FAILED/BLOCKED; NOT_RUN if any NOT_RUN; else PASS.
Inputs via CLI/file paths: video, narration_manifest, subtitle_path, credits_path, claim_ids_path, rights_records_path, edit_decisions_path, ledger. Called per episode (run_episode cmd_qc).

### `tools/qa/qc_pilot_final.py` (163 lines) — pilot-final simple QC
Checks: file exists/non-empty, exactly one video stream, >=1 audio stream, resolution 1280x720, FPS ~30, video codec h264/hevc/av1, duration 1099.775±6s, audio codec aac/mp3/opus, full decode, blackdetect 0, silencedetect 0 (>2s -30dB), ebur128 loudness -20..-10 LUFS, true peak <=-1.0 dBTP. Exit 0 only if all PASS.

### `tools/qa/release_gate.py` (113 lines) — publication blocker computation
Checks: QC report present and no FAILED/BLOCKED/NOT_RUN; single-source/unknown claim ids per sentence; owner sign-offs (voice, image_model, rights_flags, disclosure) all true. Returns publishable bool + reasons list. Fail-closed (missing input = blocker). Read-only.

### `tools/illustration/illustration_qc.py` (323 lines) — AI illustration QC
Checks: blur (Laplacian variance), exact size + aspect, text-like artifacts (connected components), palette drift vs niche style (coverage/off-palette share), near-duplicates (aHash+dHash Hamming). Thresholds from config/qc_thresholds.json illustration_qc. No beauty/anatomy scoring.

Invocation: qc.py and release_gate are invoked by run_episode pipeline; illustration_qc via tests/tools and image pipelines; qc_pilot_final standalone CLI. Not a single unified command across all four.

## 2. End-to-end single command?

Closest: `python scripts/run_episode.py <topic_id>` (Z3/Z4) chains claim_ledger_check -> script_validation -> footage_manifest_rights -> narration -> subtitles -> edl -> render -> finish_audio -> qc -> release_gate -> package_draft, with checkpoint/resume/idempotency.
But it is NOT fully automatic from arbitrary text: requires pre-prepared topic (claim ledger, script, footage manifest, assets), and narration needs `/tmp/kilo/z1_venv` (currently absent). Image generation is separate (`run_illustrations.py` / `run_episode_images.py`). So: no one-command "script text -> mp4" from scratch; pipeline breaks at topic prep + image gen + environment (Kokoro venv/weights).

## 3. Reuse vs factory-specific (from AUDIT_1)

Worth reusing for educational/animation direction:
- `docs/openmontage/SERIES_PLAN.md` (topic ranking method).
- Claim-ledger approach (`CID_CLAIM_LEDGER.md`, `_parse_claim_ledger`, claim_ids_resolve) for fact-checking scripts.
- Generic EDL (`cmd_edl`), chapter mode (`--chapters`), QC thresholds config approach (SCR-05).
- `release_gate.py` publication blockers, zero-cost gate, rights registry pattern, review pack harness, EVALS.md tasks.
- `tools/illustration/*` (style kit, creature sheets, image QC v2), motion_variety, packaging, analytics import, museum adapters.

Factory/NASA-footage-specific (low value for new niche):
- CID slice artifacts, `FOOTAGE_QUALITY.md`, K2 footage probe (NASA CID), S12 bakeoff reports, stick4 IP-Adapter jobs, kaggle jobs under pilot-render/frames_klein, contact sheets.
- `docs/openmontage/image_gen/BAKEOFF_S5/S7/S8` are model-comparison records (reusable methodology, but data is niche-agnostic enough; keep methodology, discard media).

## 4. Readiness percentages (agent estimate)

- Image generation pipeline: ~70%. Real engine, style kit, seed locking, QC, batch/recovery; blocked models (Z-Image, SANA), LoRA not implemented, G2 failed, reference image only for klein.
- Audio pipeline: ~85%. Kokoro route proven, modules real, alignment/QC; environment currently broken (venv/weights wiped), license residual risk.
- Video assembly: ~75%. Render/EDL/timeline/preview real, V1-V3 composited; within-scene animation missing, Remotion integration partial, image resolution upscaled.
- QC: ~90%. qc.py 16 checks, final_qc, release_gate, illustration_qc, fail-closed thresholds; tests present; not all checks run in every invocation.

## Reproduce commands
```
python scripts/run_episode.py --help
sed -n '1,120p' scripts/run_episode.py
cat tools/qa/qc.py | grep -n "entry("
cat tools/qa/release_gate.py
```
