# TTS Segment Lab

## When to Use

Use `tts_segment_lab` after the narration script is approved and before final
narration assets are generated.

It is for voiceover auditioning, not objective model benchmarking. Use it when
a script has high-risk delivery lines:

- opening hooks;
- emotional turns;
- product reveals;
- pronunciation-sensitive names or acronyms;
- ending handoffs and calls to action.

## Tool

| Tool | Capability |
|------|------------|
| `tts_segment_lab` | Generate and record TTS audition variants |
| `tts_selector` | Route generated variants to available TTS providers |

## Workflow

1. Mark high-risk sections in the script.
2. Create a manifest with `script_path`, `output_dir`, `segments`, and variants.
3. Add `reference` audio when a current approved version exists.
4. Run `dry_run` to inspect the review structure without API calls.
5. Run `generate` to create audition samples.
6. Listen to `review.md`.
7. Run `select` to write `selection.json`.
8. Reuse selected audio in final asset generation.

## Minimal Manifest

```json
{
  "project": "my-explainer",
  "run_id": "opening-audition-v1",
  "script_path": "projects/my-explainer/artifacts/script.json",
  "output_dir": "projects/my-explainer/assets/tts-lab/opening-audition-v1",
  "defaults": {
    "preferred_provider": "auto"
  },
  "segments": [
    {
      "id": "opening",
      "section_id": "s1",
      "label": "Opening hook",
      "reference": {
        "id": "reference-current",
        "audio": "projects/my-explainer/assets/audio/current-opening.mp3",
        "duration_seconds": 8.2,
        "note": "Current approved narration."
      },
      "variants": [
        {
          "id": "auto",
          "note": "Let tts_selector choose the best available provider."
        },
        {
          "id": "doubao-rate8",
          "provider": "doubao",
          "note": "Mandarin baseline with timestamp support.",
          "provider_options": {
            "voice_id": "zh_female_vv_uranus_bigtts",
            "resource_id": "seed-tts-2.0",
            "enable_timestamp": true
          },
          "overrides": {
            "speech_rate": 8
          }
        }
      ]
    }
  ]
}
```

## Selection

After listening, write a selection:

```json
{
  "operation": "select",
  "results_path": "projects/my-explainer/assets/tts-lab/opening-audition-v1/results.json",
  "selections": {
    "opening": "reference-current"
  }
}
```

Choose `reference-current` when no new candidate is clearly better. This avoids
unnecessary subtitle and visual-timing rework.
