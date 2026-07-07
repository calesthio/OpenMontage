---
name: fish-audio-tts
description: Generate expressive, multilingual narration with fish.audio (S1 / S2-generation models) and reuse cloned voices via reference_id. Use when the user prefers fish.audio/Fish Audio TTS, wants a specific playground voice model, or needs high-emotion voice-clone narration.
---

# fish.audio TTS

Requires `FISH_AUDIO_API_KEY` in `.env` (create one at https://fish.audio/go-api/api-keys/).
Create voice models in the fish.audio playground and pass their id as `reference_id` to reuse a cloned voice.

## Current API

Single synchronous call returning raw audio bytes:

```text
POST https://api.fish.audio/v1/tts
Authorization: Bearer ${FISH_AUDIO_API_KEY}
Content-Type: application/json
model: <backend model>     # HTTP header selects the backend, e.g. s1
```

The backend model is chosen with the `model` **HTTP header**, not a body field. In OpenMontage this maps to the tool's `model` input.

## Backend models

`model` is **required — there is no default**. Pass one of:

- `s2.1-pro` — latest generation. Best quality: inline emotion tags, 80+ languages, multi-speaker. Hero narration.
- `s2.1-pro-free` — free tier of s2.1-pro. Drafts, samples, and validation runs at $0.
- `s2-pro` — first S2 generation. Stable high quality with emotion-tag support.
- `s1` — previous flagship. Kept for compatibility with existing integrations.

Billing is **per UTF-8 byte of input text** (not per character). CJK text and emoji cost 3-4x an ASCII character of the same visible length. Approximate: `s1` / `s2-pro` / `s2.1-pro` ≈ $15 per 1M bytes, `s2.1-pro-free` = $0. Verify current pricing at https://fish.audio before large batches.

## Inline emotion tags (S2 models only)

`s2-pro` / `s2.1-pro` / `s2.1-pro-free` interpret inline emotion tags embedded in the text:

- Tags like `[laugh]`, `[whispers]` change the delivery mid-sentence.
- Example: `"That's hilarious [laugh] but let me explain seriously."`
- `s1` does not interpret emotion tags — they may be read out as plain text, so strip them when targeting s1.

## Voice selection (reference_id)

- Build or pick a voice in the fish.audio playground, then copy its model id.
- Pass it as `reference_id`. The selector's generic `voice_id` is accepted as an alias when `reference_id` is absent.
- Without a `reference_id`, fish.audio uses its default voice for the chosen model.

Inline on-the-fly cloning (uploading reference audio + text per request) is **not** supported by this tool — create a voice model in the playground first.

## OpenMontage Usage

Generate with the TTS selector:

```python
from tools.audio.tts_selector import TTSSelector

result = TTSSelector().execute({
    "preferred_provider": "fish_audio",
    "text": "Here's why compound interest quietly beats every get-rich-quick scheme.",
    "model": "s1",
    "reference_id": "<playground voice model id>",
    "output_path": "projects/my-video/assets/audio/narration.mp3",
})
```

Or call the provider directly:

```python
from tools.audio.fish_audio_tts import FishAudioTTS

result = FishAudioTTS().execute({
    "text": "Short sample line for approval.",
    "model": "s1",
    "reference_id": "<playground voice model id>",
    "output_path": "projects/my-video/assets/audio/fish_sample.mp3",
})
```

The provider writes the audio to `output_path` and returns `data.output` plus the resolved `model` and `reference_id`.

## Quality & latency tuning

- `latency`: `normal` (default, best quality), `balanced` (a little faster), or `low` (fastest, slight quality cost).
- `normalize`: default `true`; keep it on so numbers, dates, and currency read naturally.
- `prosody`: optional `{ "speed": 1.0, "volume": 0 }` to nudge pace/loudness.
- `mp3_bitrate`: `128` is a good default; raise to `192` for music-bed-heavy mixes.
- `temperature`: default `0.7`. Raise toward `0.9` for more expressive reads (recommended when leaning on emotion tags); lower for a steadier, more predictable delivery.
- `top_p` / `repetition_penalty`: usually leave at the defaults (`0.7` / `1.2`).

## Recommended Workflow

1. Generate a 10-15 second sample with the chosen `model` + `reference_id` before a full paid narration.
2. Ask the user to approve voice naturalness, emotion, and pace.
3. Generate the full narration only after approval.
4. For batch/localization variants where cost matters, prototype on `s2.1-pro-free` ($0) and upgrade the final to `s2.1-pro`.

## Troubleshooting

- `401 Unauthorized`: wrong or missing `FISH_AUDIO_API_KEY`.
- `402` / payment errors: account credit exhausted.
- `404` / bad voice: the `reference_id` is wrong or not owned by this account.
- Empty/short audio: check that `text` is non-empty and `normalize` is not stripping the whole input.

## Safety

Never print or write the API key to logs, metadata, patches, or project artifacts. `.env.example` should contain only empty variable names.
