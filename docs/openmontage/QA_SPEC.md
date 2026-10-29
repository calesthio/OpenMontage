# QA Spec — OpenMontage Milestone Q (spec only)

**Status:** spec only. No application code, no installs, no tests. Implementation is a LATER milestone (tests first). Thresholds marked INITIAL GUESSES — tune after human review.

**Threshold source (SCR-05):** `tools/qa/qc.py` loads `config/qc_thresholds.json`
by default (the pipeline passes it explicitly). A missing, unreadable or
malformed config is **BLOCKED**, never a silent fallback to the code defaults;
the code defaults below are the documented INITIAL GUESSES only.

## 1. Hard checks

Each check is deterministic and fail-closed: a missing tool output or unresolvable reference -> BLOCKED, never PASS.

| check_id | ffmpeg filter / tool | What it verifies | Threshold (INITIAL GUESS) |
|---|---|---|---|
| `ffprobe_streams` | ffprobe | expected streams present (video + audio), codec, resolution, fps, duration | streams resolve; no empty fields |
| `full_decode` | `ffmpeg -i file -f null -` | full decode without errors | exit 0, no decode errors |
| `blackdetect` | `blackdetect` | black ratio of final video | black ratio <= INITIAL GUESS 0.05 |
| `freezedetect` | `freezedetect` | frozen-frame duration | freeze duration <= INITIAL GUESS 2.0 s |
| `silencedetect` | `silencedetect` | silence ratio | silence ratio <= INITIAL GUESS 0.10 |
| `ebur128` | `ebur128` | integrated LUFS + true peak | I=-14 LUFS (target), TP=-1.5 dBTP (target) |
| `duration_vs_script` | ffprobe duration vs narration_manifest | final duration matches script | within INITIAL GUESS ±1.0 s |
| `subtitle_sync` | ffprobe subtitle stream vs audio | subtitle drift | drift <= INITIAL GUESS 0.5 s |
| `credits_complete` | read credits.txt | credits.txt completeness | all required fields present |
| `claim_ids` | read script + evidence_ledger | every factual sentence has resolvable claim_id | 100% of factual sentences |
| `rights_basis` | read asset_manifest | rights_basis known for every clip | 100% of clips have explicit rights_basis |
| `added_value` | read edit_decisions + final file | added-value metrics (§3) | per-gate thresholds below |

Tools: ffprobe, ffmpeg (analysis-only, e.g. `-f null`), python -m json.tool, pytest read-only.

## 2. qa_report.json schema

```json
{
  "job_id": "string",
  "check_id": "string",
  "status": "PASS|REVIEW|BLOCKED|FAILED",
  "evidence": "string",
  "measured_value": "string | number | null",
  "threshold": "string | number | null",
  "tool_version": "string",
  "timestamp": "ISO-8601"
}
```

- `status` is PASS|REVIEW|BLOCKED|FAILED; fail closed (unable to run -> BLOCKED).
- `tool_version` records the actual tool/ffmpeg version observed.
- `timestamp` is ISO-8601 UTC.

## 3. Added-value metrics

- narration coverage >= 90% of runtime (INITIAL GUESS)
- >= 1 original diagram/chart per 90 s (INITIAL GUESS)
- no unannotated archive clip > 20 s (INITIAL GUESS)
- still-image-only sequence <= 15 s (INITIAL GUESS)
- every claim has an on-screen source card or credits entry

## 4. Gate mapping

| QA check | Master-plan gate it enforces |
|---|---|
| `rights_basis`, `claim_ids` | topic viability gate: >=10 usable licensed clips, >=3 primary docs |
| `blackdetect`, `freezedetect`, `silencedetect`, `ebur128`, `full_decode` | technical QC gate (fail-closed) |
| `duration_vs_script`, `subtitle_sync` | editorial / narration alignment gate |
| `credits_complete` | credits & attribution gate |
| `added_value` | added-value gate |
| `ffprobe_streams` | container/stream integrity gate |
