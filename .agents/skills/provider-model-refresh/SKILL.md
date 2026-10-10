---
name: provider-model-refresh
description: Use the September 2026 image, video, speech and Avatar V adapters with explicit model/host contracts.
---

# Provider model refresh

For media production, first follow AGENT_GUIDE.md and the selected pipeline.
These adapters are discoverable through the normal BaseTool registry. Inspect
their input schema and status before making a request. An API credential indicates
configuration, not verified account entitlement. No paid live test is implied.

## Routing

Use `preferred_tool` to require an exact adapter and `hosting_provider` to require
an API host. `preferred_provider` remains a legacy ranking preference. Select an
exact `model` for images/video or `model_id` for speech. An unavailable exact
model must fail rather than silently substitute a different model.

| Model | Direct tool | Aggregator tools |
| --- | --- | --- |
| GPT Image 2.5 Flare / Sunburst | openai_image | openai_fal_image, atlas_refresh_image |
| Gemini 3 Pro Image / Nano Banana Pro | google_imagen | gemini_fal_image, gemini_replicate_image, atlas_refresh_image |
| Ideogram 4.5 / Precise Edit | ideogram_image | ideogram_fal_image |
| Wan 3.0 | — | wan_fal_video, wan_atlas_video, wan_replicate_video |
| H3 Max | — | h3_max_video (fal) |
| LTX-2.5 Fast / Pro | ltx_api_video | — |
| Eleven v4 / v4 Turbo | elevenlabs_tts | fal_elevenlabs_tts (v4 only) |
| Gemini 3.8 Flash / Flash-Lite TTS | gemini_tts | — |
| Lyria 3.5 | google_music | — |
| Sonic 3.6 | cartesia_tts | — |
| Inworld TTS-2 / Flash | inworld_tts | — |
| Qwen Image 2.1 | qwen_image_21 (local) | — |
| HeyGen Avatar V | heygen_avatar | — |

## Image requests

GPT Image 2.5 uses separate `gpt-image-2.5-flare` and
`gpt-image-2.5-sunburst` IDs. Use Flare for speed and Sunburst for demanding
edits. Describe what changes and what must remain. Direct edits use local
`image_path`/`image_paths` and optional `mask_path`. Keep alpha output in PNG or
WebP. The old GPT Image 2 default remains available for compatibility.

Google Pro's exact ID is `gemini-3-pro-image`; it is distinct from
`gemini-3.1-flash-image` (Nano Banana 2). Use up to 14 reference images, and
1K/2K/4K on supported routes. Replicate fallback is disabled.

Ideogram direct `generation_mode=precise_edit` preserves unaffected pixels;
use `image_path` followed by up to four references in `image_paths`. With a
mask, only three references are allowed. Black edits, white preserves. Precise
Edit cannot specify output size. `dry_run=true` validates and prices the exact
request without generating. On fal, `precise_edit` sets `edit_precision=high`.

Qwen Image 2.1 requires the actual local model directory and compatible
Diffusers. It never downloads weights implicitly. Check the Qwen Research
License for the intended use. Transparent generation validates the returned
alpha channel rather than adding an opaque alpha channel.

## Video and jobs

`operation` selects text_to_video, image_to_video or reference_to_video.
Replicate Wan supports text and first-frame image only. Wan on Atlas uses
`refers` objects and `duration=-1` for automatic length; fal uses reference URL
arrays and nullable duration. Do not transfer native parameters between hosts.
Pass route-specific controls in `provider_params`; checked-in schemas under
tools/provider_contracts validate the complete request before submission.

LTX-2.5 supports text/image/audio generation, not retake or extend. Frame rates
are 24, 25, 48, 50; long durations require Fast at 720p/1080p and 24/25 FPS.
`duration=null` lets the model choose length, but cannot combine with a last
frame. H3 Max is separate from the older H3 endpoint.

Set `job_path` to persist a checkpoint. On timeout, pass the returned
`resume_job` to the same tool; this polls the existing job without a second
paid submission. A submission timeout without an ID is ambiguous: check the
provider dashboard before submitting again. Preserve provenance and outputs.
Unknown pricing is reported explicitly, never treated as a free service.

## Speech and music

Direct Eleven IDs are `eleven_v4` / `eleven_v4_turbo`; fal uses `eleven-v4`.
fal v4 accepts at most 5,000 characters and has no speed/style control.
Direct v4 accepts up to 10,000. Voice catalogs and rights differ by host.
Gemini TTS uses Interactions with speech annotations; configure each dialogue
speaker's voice and turn text separately. Its current adapter outputs WAV.
Cartesia uses API version 2026-08-14 and WAV. Inworld uses a portal-issued
Base64 credential with Basic auth, MP3, and at most 2,000 UTF-16 code units.
Lyria duration is a prompt target, not guaranteed exact timing.

## Avatar V

Use `heygen_avatar` in the avatar-spokesperson pipeline. First `list_looks` or
`inspect_look`; generation checks `avatar_type=digital_twin` and
`supported_api_engines` before POST. Avatar V is explicitly requested with
`engine=avatar_v`; it never falls back to IV. Provide exactly one of
`script` (+ `voice_id`), `audio_url`, or `audio_asset_id`. A reference look must
be a digital twin in the same verified group. Use an authorized existing
presenter and preserve HeyGen's consent/account requirements.

## Evidence and limitations

Contracts were inspected 2026-10-03; each schema records its official source.
See docs/provider-update-plan-2026-10-03.md for release research. Public Kling 4
generation endpoints remain unverified, so do not invent a model ID. Live voice
agents require a separate streaming/session integration beyond batch narration.
