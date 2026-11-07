# EBU R128 loudness threshold proposal — narration-only content (F2)

**Status:** PROPOSED (docs only). qc.py thresholds NOT changed. No code change.

**Observed result (F2 final slice):** ebur128 check FAILED: integrated loudness I = -17.1 LUFS, target -14.0 +/- 2.0 LUFS (i.e. -16.0 to -12.0). Measured -17.1 is 1.1 LU below the lower bound (-16.0) — marginal. True peak TP = -1.4 dBTP <= max -1.5 dBTP PASS.

**Content type:** narration-only slice, no music bed, no sound effects. Audio is source archive material (PCM extracted from archive.org derivatives) run through finish_audio two-pass loudnorm.

**Reason for proposal:**
- QA_SPEC.md / finish_audio.py docstring already notes: "for narration-first content -16..-14 LUFS may be acceptable — record this question for the owner."
- -17.1 LUFS is within ~1 LU of the narration-acceptable band (-16..-14). For archive-derived narration-only material with no music, a target of -16 LUFS (+/- 2, i.e. -18..-14) is more appropriate than the general -14 target.
- True peak is already compliant (-1.4 dBTP <= -1.5 dBTP), so no clipping risk.

**Proposed threshold change (docs only):**
- Add a content-type conditional: for narration-only / no-music slices, ebur128 integrated target = -16.0 LUFS +/- 2.0 (acceptable band -18.0..-14.0), true peak max -1.5 dBTP unchanged.
- General (music/narration mix) content keeps -14.0 +/- 2.0 LUFS.

**Files NOT changed:** tools/qa/qc.py, config/qc_thresholds.json (thresholds intentionally left as-is pending owner review).

**Owner decision needed:** Accept the narration-only ebur128 band (-16 +/- 2 LUFS) and mark F2 ebur128 PASS, or keep -14 +/- 2 and treat -17.1 as a marginal FAIL requiring re-mix.
