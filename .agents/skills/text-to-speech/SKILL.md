---
name: text-to-speech
description: HeyGen native Voice1 and catalog speech, voice discovery, timestamps, and streaming.
---

# HeyGen speech

Use the registered tools, not the retired /v1/audio speech endpoints.

- `heygen_tts`: native HeyGen Voice1 / Turbo / Turbo Free. Native ACTIVE public,
  instant or professional voices from `/v3/models/audio/voices`. Professional
  voices require Voice1 (not Turbo). Output is44.1kHz WAV; text limit5,000 chars.
- `heygen_catalog_tts`: catalog voices from `/v3/voices`; explicit engine selection
  on `/v3/voices/speech` (Starfish, HeyGen Voice, or ElevenLabs). These voice IDs
  are not interchangeable with native clone IDs.
- `heygen_voice_convert`: timing-preserving conversion with an ACTIVE instant
  workspace voice via `/v3/models/audio/sts`.

Read [the October23 provider guide](../provider-refresh-oct23/SKILL.md) for current
request fields, output paths, timestamp/SSE handling, pricing, and retry behavior.
Do not silently fall back between native models, catalog engines, or hosts.
Turbo Free is promotional through November30,2026 and has shared capacity limits.

Official documentation:
https://developers.heygen.com/docs/voices/heygen-voice-speech
https://developers.heygen.com/reference/generate-speech
https://developers.heygen.com/docs/voices/speech-to-speech
