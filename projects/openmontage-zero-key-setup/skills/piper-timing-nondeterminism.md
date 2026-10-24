# Piper narration timings are not reproducible — measure the shipped WAVs

**Learned:** 2026-08-31, during `openmontage-zero-key-setup` (screen-demo, synthetic_terminal).

## What happened

The script stage measured each narration line by synthesizing it with `piper_tts` and probing
with `ffprobe`, then laid the terminal choreography out against those numbers. When the asset
stage regenerated the same six lines with the same text, model, `length_scale`, and
`sentence_silence`, five of six came back a different length — up to **-0.43s** on a 6.4s line.

Direct check, same line three times:

```
4.831429
4.610839
4.599229
```

## Why

`en_US-lessac-medium.onnx.json` sets `noise_scale: 0.667`, `noise_w: 0.8`. Piper's duration
predictor is stochastic and the CLI exposes no seed flag, so utterance length varies run to run
(observed spread ~5%). `length_scale` scales the mean; it does not make synthesis deterministic.

## Rule

1. **Never** lay a timeline out against a probe WAV you are going to throw away. Generate the
   narration you will ship, then measure those exact files.
2. Once timings are locked, treat the WAVs as immutable inputs. Regenerating narration after
   the scene plan is approved silently invalidates every cue, pause, and pill time.
3. If narration must be regenerated, re-run the layout and
   `lib.verify_scene_pacing.assert_alignment` before rendering.
4. Budget for this in any pipeline that syncs visuals to local TTS. Cloud providers with fixed
   seeds do not have this property; Piper does.

## Cost of ignoring it

Commands drift out of sync with the lines that announce them — the exact failure
`.agents/skills/synthetic-screen-recording/SKILL.md` calls the #1 failure mode, arriving through
a back door that skill does not mention.
