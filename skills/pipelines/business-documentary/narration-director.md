# Narration Director - Business Documentary Pipeline

## When To Use

Stage 7 of 12. You synthesize the English narration from the verified
`script`, measure the real duration from the audio files, and record the
timestamps captions will be built from.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact in | `script` (validated) | Text to synthesize |
| Schema | `schemas/artifacts/narration_manifest.schema.json` | Output validation |
| Registry | `piper_tts`, `tts_selector` | Available TTS |

## Process

### 1. Check what can actually synthesize

```bash
python -c "
from tools.tool_registry import registry
registry.discover()
for name in ('piper_tts', 'tts_selector'):
    t = registry._tools.get(name)
    print(name, t.get_info()['status'] if t else 'missing')
"
```

`piper_tts` is the offline path (voice `en_US-lessac-medium`) and depends on
the `piper` binary plus a downloaded voice model. If no TTS tool is
`available`, **this stage fails closed**: write `status="failed"` with
`no_tts_provider_available`, run the setup-offer protocol so the operator can
install a local voice, and do not fabricate audio, durations or timestamps.

A film with no narration is allowed only when the brief recorded that decision
— never as a silent workaround for a missing synthesizer.

### 2. Zero-cost check before any call

Every synthesis call goes through the gate:

```python
from lib.zero_cost_gate import facts_from_registry, evaluate_call
print(evaluate_call(facts_from_registry('piper_tts', 'synthesize',
                                        cost_usd=0.0, route='local:piper')))
```

A cloud TTS route with unknown pricing is BLOCKED in strict zero-cost mode.
Offer it to the human with its cost; do not call it unilaterally.

### 3. Synthesize per section, cache by hash

One file per script section, named with the section id. Cache key = hash of
the exact text + voice + model + parameters, so a rerun that changed nothing
reuses the audio.

### 4. Measure, do not estimate

`duration_seconds` per segment comes from probing the written file
(`ffprobe`), not from a words-per-minute calculation. `total_duration_seconds`
is the sum of measured segment durations.

### 5. Timestamps for captions

Record `word_timestamps` (or the provider's segment timestamps). Subtitles are
generated from these — never re-estimated later.

### 6. Hash the input text

`input_text_sha256` is the SHA-256 of the exact narration text synthesized.
This is what lets QA prove the audio matches the script.

### 7. Verify the voice license and pronunciation

- Record the voice model's license and permitted use before commercial
  publication.
- Apply the script's `pronunciation` notes for brands, acronyms and units;
  verify the ones that are easy to get wrong (ticker symbols, metric units,
  non-English names).

### 8. Optional self-transcription check

If a local STT transcriber is available, transcribe the final audio and
compare it with the intended text. Record `verification.method`,
`word_accuracy`, `threshold` and `passed`. A divergence above threshold blocks
or triggers review — never silently accepted.

### 9. Quality gate

- Schema-valid `narration_manifest`.
- Every segment's `audio_path` exists with its measured duration.
- `input_text_sha256` matches the script text.
- `metadata.tts_provider`, `metadata.tts_model` and voice license recorded.
- No segment duration was estimated.

## Common Pitfalls

- Trusting a "wpm × words" duration for the timeline.
- Skipping word timestamps and then inventing captions.
- Synthesizing the hook with one long clip so it cannot be re-timed in edit.
- Using a cloud voice without recording its license.

---

## Checkpoint Note

`narration` is auto-approved (`human_approval_default: false`): write the
checkpoint, self-review, continue. A *failed* narration stage still stops the
run — it does not get skipped by auto-approval.
