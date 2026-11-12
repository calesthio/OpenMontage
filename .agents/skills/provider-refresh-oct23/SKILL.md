---
name: provider-refresh-oct23
description: API contracts and production routing for the October 23, 2026 provider refresh.
---

# October 23 provider integrations

Read the tool's current input schema before use. Announce tool, host, exact model,
operation and quoted cost before production. No automatic host/model fallback.
Use explicit output paths under the production project. Account access is not
established merely by having a credential configured. Most new prices require a
fresh account quote; do not use expired promotions as permanent prices.

## Google and ElevenLabs migrations

- `gemini_omni_video`: direct Gemini Interactions API model is
  `gemini-omni-1.1-flash`. Old preview retired October 22. Continue editing with
  `previous_interaction_id`; do not substitute it inside a Veo request.
- `veo_video`: Google backend requires Vertex; fal retains its own contracts.
  Gemini API Veo has retired. Select Omni explicitly for the replacement workflow.
- `google_imagen`: new default `gemini-nano-banana-2.1`; Imagen models require
  Vertex. Native Gemini image models use generate_content, not Imagen predict.
- `elevenlabs_tts`: `eleven_v4` uses HTTP Text to Dialogue with `inputs` and
  `settings`. Keep each narration request <=2,000 characters. `next_text` maps to
  `future_text`; context strings <=100 characters. Style/speed/speaker boost are
  not dialogue settings. `eleven_v4_turbo` uses the dialogue WebSocket; this file
  adapter does not support timestamps or continuity controls on Turbo. It waits
  for global `is_final`, not the per-turn marker. The current official realtime
  tutorial documents Turbo although the older WebSocket reference says v3-only.

## Narration and conversion

- `heygen_tts`: model_id `heygen-voice-1`, `heygen-voice-1-turbo`, or
  `heygen-voice-1-turbo-free`. Pass an ACTIVE native public/workspace voice ID;
  `operation=list_voices` discovers native voices. Professional clones only work
  with the non-Turbo model. `voice_type` can prevalidate the category; the service
  validates actual ownership/status. Completed speech and SSE both write WAV.
  SSE parts are individual WAV containers, decoded before assembly. Timestamps
  become an alignment sidecar and word_timestamps. Free access ends November 30,
  2026; failures never switch to paid. Rate rejection retries are bounded and honor
  short Retry-After delays; larger delays surface to the caller.
- `heygen_catalog_tts`: separate catalog IDs, `/v3/voices/speech`; explicitly choose
  `engine` (starfish, heygen_voice, elevenlabs). Native professional clone IDs do
  not belong here. Catalog output can be MP3 or WAV. Supply either suffix; the returned artifact
  path uses the actual response codec suffix and preserves the audio.
- `heygen_voice_convert`: ACTIVE instant workspace voice only, at most300 seconds.
  Exactly one audio_path (<=16 MB), audio_url or asset_id. Output WAV. Supply a
  stable idempotency_key if resuming after an ambiguous timeout; no automatic retry.
- `grok_tts`: xAI narration `/v1/tts`, not Grok Voice realtime. `language=auto` by
  default, voice_id defaults to eve; list_voices discovers voices. output_format
  is an object, e.g. {"codec":"wav","sample_rate":24000}; this file adapter exposes
  MP3/WAV, not headerless telephony codecs. Optional character alignment is saved.
- `mistral_tts`: model_id `voxtral-mini-tts-3-0`; exactly one voice_id or local
  reference_audio_path. mp3/wav/flac/opus. Inline emotion/pace tags and expressiveness;
  free-form style instructions are not available at launch. No realtime TTS claim.
- `mai_tts`: Azure Speech key/region, model_id MAI-Voice-2.1 or MAI-Voice-2.1-Flash.
  voice_id is a managed voice base such as en-US-Harper (the model suffix is added).
  The TTS selector translates speed and pitch through the Azure SSML adapter.
  This adapter does not provision personal voice clones or grant gated access.
- `mistral_stt`: Voxtral Mini/Small Transcribe3, local audio files; timestamps are
  segments, not words. Diarization implies segment timestamps. Raw transcript JSON
  is persisted, including speaker and usage metadata.
- `elevenlabs_soundtrack`: video_paths (<=10, combined <=200 MB / 600seconds),
  optional description/tags, add_sfx/use_audio_as_reference/separate_tracks. Separate
  tracks return playable files in a sibling *_tracks directory; never treat a ZIP
  as an audio file. The adapter rejects unsafe archive paths and oversized archives.

## Images and video

| Model | Explicit tools / hosts |
|---|---|
| Nano Banana2.1 | google_imagen, gemini_fal_image, gemini_replicate_image |
| FLUX3 Image | bfl_image, flux3_fal_image, flux3_replicate_image |
| FLUX3 Max video | flux3_video (fal) |
| Vidu Q4 | vidu_video (fal), image_to_video or reference_to_video; no text-only route |
| Fibo2 | bria_image direct or bria_fal_image |
| MAI Image2.6 / Flash | mai_image, deployed Foundry models |
| Grok Imagine1.5 / Lite | grok_video direct xAI |

fal and Replicate have checked-in endpoint schemas under tools/provider_contracts.
Pass provider_params only when documented by that host. Do not copy fal fields to
Replicate or direct APIs. Existing Pro image model defaults remain unchanged on
aggregators; select the new model explicitly.

BFL bounding-box layouts are encoded in the prompt per BFL docs, not a fabricated
`boxes` endpoint field. BFL supports up to10 reference images; width/height must be
provided together. Its API reference is authoritative over older narrative examples.
Bria persists structured metadata for later editing. Its shared endpoint can route
some legacy combinations to older Fibo models; the direct tool rejects those
combinations when advertising Fibo2. MAI requires model identity to match the
configured deployment; PNG output and <=2,359,296 pixels with each side >=768.

Grok1.5 references are limited to720p. Lite has no reference audio, reference images,
last_frame or keyframes. Full1.5 supports preset voice references; custom audio
references remain partner gated. Mid-video pins must be inside duration and occupy
different1/3-second slots. No model substitution on failure. fal/Replicate/BFL/Grok
jobs expose resume metadata; save job_path before polling and resume pending jobs
instead of submitting duplicate paid generations.

## Realtime is separate from narration

`realtime_audio` is a bounded one-response file runner for Grok Voice3,
Eleven Realtime Mini/Max and MAI-Transcribe-2-Streaming. Input is text or mono PCM16
WAV (16/24kHz; Eleven requires24kHz). Voice output is WAV; MAI output is event JSON.
Input sending and event receiving run concurrently. MAI commits explicitly and
waits for final transcription, not a commit acknowledgment. Eleven uses ephemeral
session credentials and bursty input pacing for recorded files.

For live audio, VAD, interruptions, multiple turns, or function calls, use the
context-managed `tools.audio._realtime_session.RealtimeAudioSession` transport:
`append_audio`, `commit`, `receive`, `request_response`, `cancel`, and
`submit_tool_result`. The caller owns the session lifecycle and tool approvals.
Received tool calls are never executed automatically. The finite file runner
rejects tools because it cannot continue them after closing the socket. No microphone
UI, browser app, or voice-agent orchestration is implied by this transport layer.
Secrets remain in memory. No realtime translation or Kling4 support was added.

## Primary references

- https://ai.google.dev/gemini-api/docs/deprecations
- https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert
- https://elevenlabs.io/docs/eleven-api/guides/how-to/websockets/realtime-tdd
- https://elevenlabs.io/docs/api-reference/music/video-to-music
- https://developers.heygen.com/docs/voices/heygen-voice-speech
- https://developers.heygen.com/docs/voices/speech-to-speech
- https://developers.heygen.com/reference/generate-speech
- https://docs.x.ai/developers/model-capabilities/audio/text-to-speech
- https://docs.x.ai/developers/model-capabilities/video/overview
- https://docs.mistral.ai/studio/audio/overview
- https://docs.bfl.ml/api-reference/utility/generate-an-image-with-flux-3
- https://docs.bria.ai/whats-new/fibo-2
- https://learn.microsoft.com/azure/ai-services/speech-service/mai-voices
- https://learn.microsoft.com/azure/foundry/foundry-models/how-to/use-foundry-models-mai-image
- https://learn.microsoft.com/azure/ai-services/speech-service/mai-transcribe-2-streaming-realtime
- https://elevenlabs.io/docs/eleven-agents/guides/openai-realtime-compatibility
- https://docs.x.ai/developers/rest-api-reference/inference/voice
