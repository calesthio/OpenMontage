# Audio Finishing — OpenMontage Milestone D2 (proposed integration point)

**Status:** docs + prototype only. Tool implemented at `tools/audio/finish_audio.py` (stdlib + ffmpeg/ffprobe only, no network, no model downloads, no new dependencies). **NOT wired into the render pipeline yet** — this file documents the proposed integration point for the next milestone. No process/lock changes.

**Smoke test (internal, not a publishability claim):** re-processed only the audio of the local pilot MP4 (`projects/pallets-hidden-business/renders/pallets-hidden-business.mp4`, 44100 Hz mono, 84.99 s) into `/tmp` (original untouched), then ran the QC tool (`tools/qa/qc.py`) on the result:

| measure | before | after | target |
|---|---|---|---|
| integrated loudness | -17.2 LUFS | -15.3 LUFS | -14.0 +/- 2.0 LUFS |
| true peak | -0.0 dBFS (clipping) | -4.5 dBFS | <= -1.5 dBTP |
| QC ebur128 check | — | PASS | PASS |
| QC full_decode check | — | PASS | PASS |

Finishing brought loudness into tolerance and removed true-peak clipping. Original file was NOT overwritten.

---

## What the tool does

`FinishAudioTool` (`tools/audio/finish_audio.py`, capability `audio_finishing`):

1. **Pass 1 (measure):** runs `loudnorm=print_format=json` to measure `input_i`, `input_lra`, `input_tp`, `input_thresh`. If unparsable → `BLOCKED` (fail-closed, never silent success).
2. **Pass 2 (apply):** applies `loudnorm` with the measured values plus the delivery targets from `config/qc_thresholds.json` (`target_i`, `target_tp`, `target_lra`), then `aresample=44100`.
3. **True-peak limiter:** `alimiter=limit=1:level=1` engages only above 0 dBFS (unity gain otherwise; `level=0` would mute).
4. **Optional sidechain ducking:** when `music_path` is given, compresses the music bed under the narration via `sidechaincompress` + `amix` (EDITING_DOCTRINE §3.2), then passes the mix through pass 2 + limiter.

Output: `pcm_s16le` 44100 Hz wav at `output_path` (pcm_f32le→aac and s16→aac-after-limiter are broken in this ffmpeg build; the render pipeline can re-encode to aac later).

Thresholds (INITIAL GUESSES from QA_SPEC.md / config/qc_thresholds.json):
- `target_i` = -14.0 LUFS (±2.0 tolerance)
- `target_tp` = -1.5 dBTP
- `target_lra` = 11.0 LU

**Owner question (recorded, not decided):** for narration-first content, -16..-14 LUFS may be acceptable instead of -14. Confirm the target before using in a render.

---

## Proposed integration point (next milestone)

Per EDITING_DOCTRINE §3 "Universal order of operations", audio finishing sits at **step 5 (audio — normalize, music bed)**, after content cuts/rhythm/structure/reframe and before overlays/captions (step 6) and the single final encode (step 7).

**Proposed wiring:**
- Call `FinishAudioTool.execute(...)` from the render/audio stage, with:
  - `input_path`: the mixed narration (+music) audio rendered by the audio stage
  - `output_path`: the finished audio fed into the final mux/encode
  - `music_path` + `ducking`: only when `edit_decisions.audio.music` is present AND a MUSIC_POLICY.md-compliant license record exists (pilot uses NO music, decision d-003)
- After finishing, verify by re-running the QC tool (`tools/qa/qc.py`, `ebur128` + `full_decode` checks) on the finished audio; treat `BLOCKED`/`FAILED` as not-passed.
- Do NOT wire into the pipeline in this milestone; this file + the tool are the proposal.

**Inputs (`tools/audio/finish_audio.py` input_schema):**
- `input_path` (required), `output_path` (required)
- `music_path` (optional), `ducking` {enabled, reduction_db, attack_ms, release_ms} (optional)

**Dependencies:** `cmd:ffmpeg`, `cmd:ffprobe` (both present in this environment, ffmpeg 6.1.1). No API keys, no network, no model downloads.

---

## Voice license blocker (from TOOLING_DECISIONS.md §12.2)

Commercial publication is **blocked** until the voice license is confirmed:
- Piper engine: GPL-3.0-or-later (commercial permitted).
- Piper voice `en_US-lessac-medium` (the locally-installed TTS used in the P1 pilot): license **UNKNOWN** — sidecar has `"dataset": "lessac"` but no license field; pilot manifest asserts `CC-BY-4.0` but no license text exists in the repo.
- Kokoro: **UNKNOWN** (not installed).

The "voice license known" Go/No-Go gate (plan v3.2) cannot pass until this is resolved or a licensed alternative is selected. Audio finishing is technical only and is NOT a commercial-use approval.
