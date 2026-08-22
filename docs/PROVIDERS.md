# OpenMontage Provider Guide

Everything you need to know about every provider in OpenMontage — setup instructions, pricing, free tiers, and what each unlocks.

---

## Quick Start: What Should I Set Up?

**Start free, add paid providers as you need them.** Here's the recommended order:

| Step | Cost | What to set up | What it unlocks |
|------|------|----------------|-----------------|
| 1 | **$0** | Pexels + Pixabay | Stock photos and videos — enough to produce basic videos |
| 2 | **$0** | Google API key | TTS with 700+ voices (1M chars/month free) + $300 new account credit |
| 3 | **$0** | ElevenLabs | Premium TTS + music + SFX (10K chars/month free) |
| 4 | **$0** | Piper (local install) | Fully offline TTS — no API key, no cost, no network |
| 5 | **~$0.03/image** | fal.ai | FLUX images + Kling/Veo/MiniMax video + Recraft — broad single-key image + video coverage |
| 6 | **~$0.05/image** | OpenAI | GPT Image 2 images + OpenAI TTS |
| 7 | **~$0.04/image** | Google Imagen | Imagen 4 images (shares the Google API key) |
| 8 | **pay-as-you-go** | Kling Official | Official direct Kling video, image, TTS, avatar, and lip-sync API, separate from fal.ai Kling |
| 9 | **pay-as-you-go** | Volcengine Ark | Official direct Seedance 2.0 Standard/Fast/Mini API |
| 10 | **$12/month** | Runway | Gen-4 video — highest quality AI video |
| 11 | **pay-as-you-go** | Hunyuan cloud video | Chinese-friendly T2V + I2V |
| 12 | **pay-as-you-go** | HeyGen | Avatar videos, multi-model video gateway |
| 13 | **pay-as-you-go** | Suno | Full song generation with vocals and lyrics |
| 14 | **$0 + GPU** | Local video gen | WAN 2.1, Hunyuan, CogVideo, LTX — free, offline |
| 15 | **$0 + GPU** | Local Diffusion | Stable Diffusion images — free, offline |

### Environment Variable Summary

```bash
# .env — add your keys here

# FREE (no cost, ever)
PEXELS_API_KEY=              # Stock photos + videos
PIXABAY_API_KEY=             # Stock photos + videos

# GOOGLE (one key, multiple tools, generous TTS free tier)
GOOGLE_API_KEY=              # Google TTS + Imagen + Lyria music + Gemini Omni/Veo video

# VOICE + MUSIC
ELEVENLABS_API_KEY=          # TTS, music, sound effects (10K chars/month free)
FISH_AUDIO_API_KEY=          # fish.audio TTS (voice cloning via reference_id, inline emotion tags)
OPENAI_API_KEY=              # OpenAI TTS + GPT Image 2 images
XAI_API_KEY=                 # xAI Grok image generation/editing + Grok video generation
DOUBAO_SPEECH_API_KEY=       # Volcengine Doubao Speech TTS (strong Mandarin narration)
DOUBAO_SPEECH_VOICE_TYPE=    # Default Doubao speaker/voice type
DASHSCOPE_API_KEY=           # Alibaba DashScope (Qwen image gen, TTS, ASR with word timestamps)

# AZURE AI SPEECH (optional cloud STT + TTS; one key unlocks both directions)
AZURE_SPEECH_KEY=            # Azure AI Speech — azure_stt (Fast Transcription) + azure_tts (neural narration)
AZURE_SPEECH_REGION=         # Speech resource region, e.g. eastus

# MULTI-MODEL GATEWAY (one key, 6+ tools)
FAL_KEY=                     # FLUX, Recraft, Kling, Veo, MiniMax video
MINIMAX_API_KEY=             # MiniMax first-party image + MiniMax H3 video generation
ATLASCLOUD_API_KEY=          # Atlas Cloud image/video gateway

# KLING OFFICIAL DIRECT API
KLING_API_KEY=               # Official Kling video, image, TTS, avatar, lip sync
KLING_API_BASE_URL=          # Optional; default https://api-singapore.klingai.com

# VOLCENGINE ARK DIRECT SEEDANCE 2.0 / 2.5 API
ARK_API_KEY=                 # API key body only; do not include the "Bearer " prefix

# VIDEO
HEYGEN_API_KEY=              # HeyGen avatar video gateway
RUNWAY_API_KEY=              # Runway native + Seedance 2.5, Gemini Omni, MiniMax H3
SUNO_API_KEY=                # Suno music generation

# TENCLOUD HUNYUAN
TENCENT_TOKENHUB_API_KEY=    # Tencent Hunyuan cloud video + 3D (hy-3d-3.1) via TokenHub API

# LOCAL (no keys needed — just GPU + install)
VIDEO_GEN_LOCAL_ENABLED=     # Set to "true" for local video gen
VIDEO_GEN_LOCAL_MODEL=       # wan2.2-ti2v-5b, wan2.1-1.3b, wan2.1-14b, hunyuan-1.5, ltx2-local, cogvideo-5b

# COMFYUI (optional overrides; localhost:8188 is the default)
COMFYUI_SERVER_URL=          # Local ComfyUI server for shared workflows
COMFYUI_VIDEO_SERVER_URL=    # Optional video-specific ComfyUI server
```

---

## Current Video Model Coverage

The following integrations are based on documented, currently exposed model
identifiers. Provider pages without a public API contract were not given
speculative model strings.

| Model | Direct provider | fal.ai | Runway | ComfyUI Partner Nodes | Local ComfyUI |
|-------|-----------------|--------|--------|-----------------------|---------------|
| **Gemini Omni Flash** | Google `gemini_omni_video` | `gemini_omni_fal` (T2V, I2V, references, editing) | `runway_video` model `gemini_omni_flash` | `GeminiVideoOmni` (hosted, paid credits) | Not available as local weights |
| **Seedance 2.5** | Volcengine `seedance_ark` model variant `2.5` | `seedance_video` model version `2.5` | `runway_video` model `seedance2_5` | `ByteDance2TextToVideoNode` (hosted, paid credits) | Not available as local weights |
| **MiniMax H3** | `minimax_video` model `MiniMax-H3` | `minimax_fal_video` (`hailuo-03`) | `runway_video` model `hailuo3` | `MinimaxHailuo03TextToVideoNode` (hosted, paid credits) | Supported with official open weights and an exported API workflow |

ComfyUI Partner Nodes run inside the ComfyUI graph but call hosted services;
they require network access, a logged-in Comfy account, and prepaid credits.
Only the MiniMax H3 open-weight workflow in this table is a local model path.

Replicate, HeyGen, and Higgsfield were not updated for these exact model
versions because their public API documentation did not expose a current,
stable contract for them at the time of this update.

---

## Cloud Providers

### xAI — Grok Image + Video

> **Best if you want one provider for image edits and reference-conditioned short video.** Grok covers both image generation/editing and video generation under one key.

**Tools unlocked:** `grok_image`, `grok_video`
**Env var:** `XAI_API_KEY`

#### Setup

1. Create an xAI developer account
2. Generate an API key in the xAI developer console
3. Add to `.env`: `XAI_API_KEY=xai-...`

#### What it's best for

- Image editing and style transfer
- Multi-image composites into one generated frame
- Short reference-image videos where a person, garment, or product must carry into motion

#### Pricing

Current xAI docs pricing for the Grok media models:

| Model | Price |
|------|-------|
| `grok-imagine-image` | $0.02 per generated image |
| `grok-imagine-image` input images (edits/composites) | $0.002 per input image |
| `grok-imagine-video` at 480p | $0.05/sec |
| `grok-imagine-video` at 720p | $0.07/sec |
| `grok-imagine-video` input images | $0.002 per input image |

OpenMontage now uses those published rates in the Grok tool estimators.

---

### Volcengine Jimeng — 即梦 AI Video Generation

> **Direct ByteDance API via V4 signing.** Calls the Volcengine visual API (visual.volcengineapi.com) with HMAC-SHA256 request signing using IAM AK/SK credentials. Supports text-to-video and image-to-video via Jimeng 3.0 Pro.

**Tools unlocked:** `jimeng_video`
**Env vars:** `VOLC_ACCESSKEY` (Access Key ID) + `VOLC_SECRETKEY` (Secret Access Key)

#### Setup

1. Go to [console.volcengine.com/iam/keymanage](https://console.volcengine.com/iam/keymanage)
2. Create a Volcengine account if you don't have one
3. Create an Access Key pair (AK + SK)
4. Ensure your account has access to Jimeng AI (即梦) video generation service
5. Add to `.env`: `VOLC_ACCESSKEY=...` and `VOLC_SECRETKEY=...`

#### What it's best for

- Direct ByteDance/Volcengine API quota usage
- Jimeng 3.0 Pro text-to-video and image-to-video
- Chinese-language prompt understanding
- Configurable frame count (121=5s, 241=10s) and aspect ratio

#### API notes

Authentication uses Volcengine IAM V4 signing (HMAC-SHA256), not a Bearer token. The signing process builds a canonical request, derives a signing key from SK → date → region → service, and signs the request.

API flow: `POST ?Action=CVSync2AsyncSubmitTask` → poll `POST ?Action=CVSync2AsyncGetResult` → download `video_url`.

The implementation uses the compatible generic `CVSync2Async*` route (API version `2022-08-31`) rather than the model-specific `2024-06-06` actions presented in the public API explorer. This is intentional — the generic route supports the same Jimeng 3.0 Pro model via `req_key` while remaining stable across model updates.

The `req_key` for video is `jimeng_ti2v_v30_pro`. Success code is `10000`. Task statuses: `in_queue`, `generating`, `done`, `not_found`, `expired`.

**Authoritative API reference:** [Jimeng TI2V V30 Pro SubmitTask](https://api.volcengine.com/api-docs/view?action=JimengTI2VV30PROSubmitTask&serviceCode=cv&version=2024-06-06)

**Schema constraints** (enforced by `input_schema` to prevent paid-call failures):
- `prompt`: max 800 characters
- `frames`: must be exactly `121` (5s) or `241` (10s) at 24fps
- `seed`: `-1` for random, or any non-negative integer

#### Pricing

| Model | Price |
|------|-------|
| Jimeng 3.0 Pro (video) | ~$0.05/sec (check Volcengine console for actual rate) |

---

### Volcengine Ark — Direct Seedance 2.0 and 2.5 Video Generation

> **Official direct Seedance API.** Calls Volcengine Ark without routing through fal.ai or Replicate, while keeping those existing provider paths available as independent fallbacks.

**Tool unlocked:** `seedance_ark`

**Env var:** `ARK_API_KEY`

#### Setup

1. Open the [Volcengine Ark API key console](https://console.volcengine.com/ark/region:cn-beijing/apiKey)
2. Enable the Seedance model family and confirm that the account has balance or a valid resource package
3. Create a long-lived API key
4. Add the key body to `.env`: `ARK_API_KEY=...`

Do not include the `Bearer ` prefix in the environment value. The tool adds the authorization scheme when it sends a request.

Optional overrides:

```bash
ARK_SEEDANCE_MODEL=doubao-seedance-2-0-260128
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_CNY_PER_USD=7.2
```

#### Models and capabilities

| Variant | Default model ID | Output |
|---------|------------------|--------|
| 2.5 | `doubao-seedance-2-5-260628` | 480p or 720p; 4–30 seconds |
| Standard | `doubao-seedance-2-0-260128` | 480p, 720p, 1080p, or 4K |
| Fast | `doubao-seedance-2-0-fast-260128` | 480p or 720p |
| Mini | `doubao-seedance-2-0-mini-260615` | 480p or 720p |

The adapter supports:

- text-to-video, first-frame image-to-video, and multimodal reference-to-video
- local image and audio inputs encoded as validated Data URIs
- remote reference image, video, and audio URLs
- task create, query, cancel, and bounded polling
- synchronized audio, optional last-frame return, web search for text-only requests, and output download
- pre-submit dry-run and token-based cost estimates

Seedance 2.5 accepts up to 30 image, 10 video, and 10 audio references.
Select it with `model: "2.5"` (or its exact model ID). Because the public
documentation does not establish a stable default token price for this model,
OpenMontage requires `custom_price_cny_per_million_tokens` before presenting a
cost estimate; unknown pricing is never reported as free.

Local reference videos are intentionally rejected because the public API does not document video Data URI support. Use a provider-accessible HTTPS URL or an Ark asset reference instead.

#### API and billing notes

The asynchronous API flow is:

`POST /contents/generations/tasks` → `GET /contents/generations/tasks/{id}` → download the successful result URL.

Queued tasks can be cancelled with `DELETE /contents/generations/tasks/{id}`. Task records are retained for a limited period, and successful result URLs are short-lived, so the tool downloads outputs promptly.

Ark bills Seedance by completion tokens. Rates vary by model, resolution, and whether the request includes reference video. OpenMontage estimates cost before submission and reconciles against provider-returned usage when available. Check the Ark console for current rates before a paid run; custom endpoint IDs and Seedance 2.5 require an explicit custom price so unknown pricing is never treated as free.

Official references: [Seedance model list](https://www.volcengine.com/docs/82379/1366799), [create task](https://www.volcengine.com/docs/82379/1520757?lang=zh), [query task](https://www.volcengine.com/docs/82379/1521309?lang=zh).

---

### Alibaba DashScope — Qwen Image + TTS + ASR

> **Best for Chinese-language production.** One key unlocks Qwen-Image generation, Qwen-TTS Mandarin narration, and Qwen-ASR with word-level timestamps — the only DashScope path that provides word-level granularity for subtitle alignment.

**Tools unlocked:** `dashscope_image`, `dashscope_tts`, `dashscope_asr`
**Env var:** `DASHSCOPE_API_KEY`

#### Setup

1. Go to [dashscope.aliyun.com](https://dashscope.aliyun.com/)
2. Create an Alibaba Cloud account if you don't have one
3. Generate an API key in the DashScope console
4. Add to `.env`: `DASHSCOPE_API_KEY=sk-...`

#### What it's best for

- Chinese-language image generation with strong prompt understanding (Qwen-Image)
- Natural Mandarin narration (Qwen-TTS, Cherry voice)
- Word-level timestamp transcription for subtitle alignment (Qwen-ASR filetrans)
- Replacing the broken `whisperx` slot for ASR

#### API notes

DashScope's `/compatible-mode/v1/` only supports `/chat/completions` and `/embeddings`. Image gen, TTS, and ASR all use DashScope-native endpoints with nested `{model, input, parameters}` request shape — not OpenAI-compatible paths.

The ASR tool (`qwen3-asr-flash-filetrans`) uses an async submit-poll pattern. Audio must be at a publicly accessible URL (local files are not supported). Word timestamps are in milliseconds, normalized to seconds by the tool.

#### Pricing

| Model | Price |
|------|-------|
| `qwen-image-2.0-pro` | ~$0.02 per image (check console for current rates) |
| `qwen3-tts-flash` | ~$0.000015 per character |
| `qwen3-asr-flash-filetrans` | Per-minute billing (check console) |

---

### Tencent Hunyuan Cloud — Image Generation

> **Chinese-friendly first-party image generation.** `hunyuan_image` accesses
> Hunyuan Image 3.0 through Tencent TokenHub with Bearer-token authentication.
> It supports seeded text-to-image, up to three reference images, custom
> resolutions, prompt rewriting, and watermark controls.

**Tool unlocked:** `hunyuan_image`

**Env var:** `TENCENT_TOKENHUB_API_KEY`

Generate an API key in the Tencent Cloud TokenHub console and add it to
`.env`. The tool reports approximately $0.08 per generated image based on
TokenHub's credit price. It is available through `image_selector`; shared
reference-image inputs are normalized to the provider's `images` array.

---

### fal.ai — Multi-Model Gateway

> **Broad single-key coverage.** One API key unlocks image and video providers across multiple models.

**Tools unlocked:** `flux_image`, `recraft_image`, `seedream_image`,
`kling_video`, `veo_video`, `seedance_video`, `gemini_omni_fal`,
`minimax_fal_video`, `fal_elevenlabs_tts`, `fal_elevenlabs_music`
**Env var:** `FAL_KEY`

#### Setup

1. Go to [fal.ai](https://fal.ai/) and click **Sign up** (GitHub or Google)
2. Navigate to [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys)
3. Click **Create Key**, copy it
4. Add to `.env`: `FAL_KEY=your-key-here`

#### Pricing

No subscription — pure pay-as-you-go, no minimum spend.

**Image generation:**

| Model | Price | Per $1 |
|-------|-------|--------|
| FLUX Pro v1.1 | $0.05/image | 20 images |
| FLUX Dev | $0.03/image | 33 images |
| Recraft v3 | ~$0.04/image | 25 images |
| Seedream 5 Pro (up to 1536x1536) | $0.0675/image | ~14 images |
| Seedream 5 Pro (up to 2048x2048) | $0.135/image | ~7 images |

**Video generation:**

| Model | Price | Per $1 |
|-------|-------|--------|
| Kling 2.5 Turbo Pro | $0.07/sec | 14 seconds |
| Seedance 2.5 | endpoint-dependent | 4–30 seconds |
| Gemini Omni Flash | endpoint-dependent | 3–10 seconds |
| MiniMax H3 (`hailuo-03`) | endpoint-dependent | 4–15 seconds |
| Veo 3 | $0.40/sec | 2.5 seconds |
| WAN 2.5 | $0.05/sec | 20 seconds |

**Free tier:** None — but $0 to start, you only pay for what you use.

The same key can also access ElevenLabs speech and music through fal.ai. Use
`fal_elevenlabs_tts` when direct ElevenLabs credentials are unavailable, or
select it through `tts_selector` with `preferred_provider: "fal.ai"`.

---

### MiniMax — Official Direct Image and Video API

> **First-party image and video generation.** The direct MiniMax API supports
> seeded image generation plus MiniMax H3 video generation with text, first/last
> frames, image/video/audio references, and global or mainland-China routing.

**Tools unlocked:** `minimax_image`, `minimax_video`

**Env var:** `MINIMAX_API_KEY`

**Optional region:** `MINIMAX_REGION=global` (default) or `cn`

#### Setup

1. Create a MiniMax Open Platform account.
2. Generate an API key in the account's API-key page.
3. Add `MINIMAX_API_KEY=...` to `.env`.
4. For a mainland-China account, also set `MINIMAX_REGION=cn`.

`MINIMAX_BASE_URL` may be used for a documented private/enterprise endpoint
override. The default global and mainland-China hosts are selected from
`MINIMAX_REGION`.

#### MiniMax H3 video

Use `minimax_video` with `model: "MiniMax-H3"`. The tool uses the v2 task
contract (`POST /v2/video_generation`, then
`GET /v2/query/video_generation/{task_id}`) and supports 4–15 second 2K clips.
Older Hailuo models continue to use the v1 API. MiniMax H3 reference generation
can combine images, video, and audio; reference audio requires a visual
reference.

#### Pricing

| Models | Global pay-as-you-go price |
|--------|----------------------------|
| `image-01`, `image-01-live` | $0.0035 per generated image |

MiniMax also offers subscription token plans with included daily image quota.
OpenMontage conservatively reports the standard pay-as-you-go amount in cost
estimates and generation results.

The tools are automatically discoverable through the image and video selectors;
choose them with `preferred_provider: "minimax"`.

---

### Atlas Cloud — Image and Video Gateway

**Tools:** `atlas_image`, `atlas_video`
**Env var:** `ATLASCLOUD_API_KEY` (aliases: `ATLAS_CLOUD_API_KEY`, `ATLAS_API_KEY`)
**Skill:** `.agents/skills/atlas-cloud/SKILL.md`

Atlas Cloud provides one endpoint and key for the following explicitly cataloged
routes. OpenMontage validates each model's real schema instead of treating task
suffixes or parameter names as interchangeable.

| Family | Supported routes | Current Atlas rate |
|---|---|---:|
| Seedance 2.5 | text/image/reference to video | $0.134/sec |
| Seedance 2.0 | text/image/reference to video | $0.112/sec |
| Gemini Omni Flash | text/image/reference to video; video edit; developer text/image/reference | $0.112–0.140/sec |
| MiniMax H3 | text/image/reference to video | $0.100/sec |
| Seedream 5.0 Pro | text to image; edit; layer decomposition | $0.022–0.045/image |
| GPT Image 2 | text to image; edit | $0.009–0.010/image |
| Nano Banana 2 | text to image; edit | $0.080/image |

Inspect `get_info()["model_catalog"]` for exact IDs, operations, media shapes,
durations, and resolutions. Prices are estimates sourced from each model's
machine-readable Atlas page and should be reconfirmed before a paid batch.

---

### Kling Official — Direct API

> **Official Kling path.** This is separate from `kling_video` via fal.ai: it uses Kling's official `Authorization: Bearer <KLING_API_KEY>` API, provider name `kling_official`, and direct Classic/Turbo/Omni task protocols.

**Tools unlocked:** `kling_official_video`, `kling_official_image`, `kling_tts`, `kling_avatar`, `kling_lip_sync`
**Env vars:** `KLING_API_KEY`, optional `KLING_API_BASE_URL`

#### Setup

1. Create or open a Kling AI Open Platform account.
2. Generate an official API key in the Kling API console.
3. Add to `.env`:
   ```bash
   KLING_API_KEY=your-key-here
   # Optional, defaults to Singapore:
   KLING_API_BASE_URL=https://api-singapore.klingai.com
   ```

#### What It Is Best For

- Direct official Kling API provenance rather than fal.ai gateway routing
- Text-to-video, image-to-video, and deep Video Omni reference workflows via `kling_official_video`
- Text-to-image, image edit/reference, and Image Omni multi-reference or series workflows via `kling_official_image`
- Text-to-speech via `kling_tts` when you already know the official Kling `voice_id`
- Cloud avatar presenter clips via `kling_avatar`, without replacing local `talking_head`
- Cloud lip-sync via `kling_lip_sync`, with explicit face selection for multi-person videos
- Accounts that need to use official Kling model permissions, resource packs, or regional endpoints

#### Notes

- `provider="kling_official"` is intentionally different from fal.ai's `provider="kling"`.
- Official Kling is a paid remote API. OpenMontage uses conservative cost estimates and includes high-cost factors such as Omni references, series output, 4k mode, and native sound.
- Local image paths are sent as raw base64 for supported Classic/image-generation fields. Turbo image-to-video requires a URL and will not silently upload through fal.ai.
- Video Omni and Image Omni can pass official `element_id` references through `element_list`; Elements remain an internal Kling Official helper, not a standalone OpenMontage capability.
- Account Usage is available as a low-frequency diagnostic helper under `tools/_kling/account.py`; it is not a selector or pipeline tool.
- `callback_url` is passed through and recorded when supplied, but OpenMontage still polls tasks by default.
- `kling_tts` requires an explicit `voice_id`; OpenMontage does not guess a default official voice.
- `kling_avatar` and `kling_lip_sync` register under the existing `avatar` capability and coexist with local SadTalker/Wav2Lip tools. Current avatar pipelines must opt into them explicitly; registry discovery alone does not replace local tools.
- Official Kling audio effects and video effects are documented but intentionally not registered as OpenMontage tools yet, because current pipelines do not have a stable sound-effects or video-effects capability slot for them.

---

### ElevenLabs — Voice, Music, Sound Effects

> **Premium voice quality.** Best TTS for narration-heavy videos. Also generates music and sound effects.

**Tools unlocked:** `elevenlabs_tts`, `music_gen`
**Env var:** `ELEVENLABS_API_KEY`

#### Setup

1. Go to [elevenlabs.io](https://elevenlabs.io) and click **Sign up**
2. Go to **Profile** (bottom-left) > **API Keys**, or visit [elevenlabs.io/app/settings/api-keys](https://elevenlabs.io/app/settings/api-keys)
3. Click **Create API Key**, name it, copy it
4. Add to `.env`: `ELEVENLABS_API_KEY=xi_your-key-here`

#### Pricing

| Plan | Price | Characters/month | Key features |
|------|-------|-------------------|--------------|
| **Free** | $0 | 10,000 | 3 custom voices, API access, attribution required |
| Starter | $5/mo | 30,000 | No attribution |
| Creator | $22/mo | 100,000 | Professional voice cloning |
| Pro | $99/mo | 500,000 | 96kbps audio, usage analytics |
| Scale | $330/mo | 2,000,000 | Priority support |

**Free tier:** 10,000 characters/month (roughly 2-3 minutes of narration). API access included. Music generation and sound effects also available on free tier with limited credits.

---

### fish.audio — Expressive TTS + Voice Cloning

> **High-emotion narration and reusable cloned voices.** S2-generation models support inline emotion tags (`[laugh]`, `[whispers]`) and 80+ languages. Voices created in the fish.audio playground are reused across runs via `reference_id`.

**Tools unlocked:** `fish_audio_tts`
**Env var:** `FISH_AUDIO_API_KEY`

#### Setup

1. Sign up at [fish.audio](https://fish.audio)
2. Create an API key at [fish.audio/go-api/api-keys](https://fish.audio/go-api/api-keys/)
3. Add to `.env`: `FISH_AUDIO_API_KEY=your-key-here`
4. (Optional) Build or pick a voice model in the fish.audio playground and pass its id as `reference_id` to reuse a cloned voice

#### Backend models

`model` is **required — there is no default**. Pass one of:

| Model | Best for |
|-------|----------|
| `s2.1-pro` | Latest flagship — inline emotion tags, 80+ languages, hero narration |
| `s2.1-pro-free` | Promotional free access to s2.1-pro — drafts, samples, validation runs (see caveats below) |
| `s2-pro` | First S2 generation — stable high quality with emotion-tag support |
| `s1` | Previous flagship, kept for compatibility (no emotion tags) |

**`s2.1-pro-free` caveats — promotional, not a durable free tier.** Per the [fish.audio announcement](https://fish.audio/ko/blog/s2-1-pro-free-api/?articleLocale=en), free API access runs **through August 31, 2026** and is subject to Fair Use limits, carries **no SLA or latency guarantee**, requests **may be retained** by fish.audio, and **commercial use is restricted**. Don't route client work or production narration through it, and don't plan long-term costs at $0 — `fish_audio_tts.estimate_cost()` falls back to the paid `s2.1-pro` rate after the promotional window ends.

The legacy `speech-1.x` tier and `s1-mini` have been removed from the fish.audio API and are not supported.

#### Pricing

Billing is **per UTF-8 byte of input text** (not per character) — CJK text and emoji cost 3-4x an ASCII character of the same visible length. Current list pricing: `s1` / `s2-pro` / `s2.1-pro` = $15 per 1M bytes; `s2.1-pro-free` is $0 only during the promotional window (through August 31, 2026 — see caveats above). Verify current pricing in the [official pricing guide](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits) before large batches.

---

### Doubao Speech — Mandarin TTS

> **Strong Mandarin narration.** Volcengine Doubao Speech is a good choice for Chinese explainer voiceovers and long-form narration that needs subtitle timing metadata.

**Tools unlocked:** `doubao_tts`
**Env vars:** `DOUBAO_SPEECH_API_KEY`, `DOUBAO_SPEECH_VOICE_TYPE`

#### Setup

1. Open the Volcengine Doubao Speech console and enable Speech Synthesis 2.0.
2. Create a new-console API Key.
3. Choose a Speech 2.0 voice type, for example `zh_female_vv_uranus_bigtts`.
4. Add to `.env`:
   ```bash
   DOUBAO_SPEECH_API_KEY=your-api-key
   DOUBAO_SPEECH_VOICE_TYPE=zh_female_vv_uranus_bigtts
   ```

#### API Notes

OpenMontage uses the new-console API key flow:

```text
X-Api-Key: ${DOUBAO_SPEECH_API_KEY}
X-Api-Resource-Id: seed-tts-2.0
```

Do not pass a new-console API Key as `X-Api-App-Id` or `X-Api-Access-Key`. That mismatch can produce `load grant: requested grant not found`.

#### What It Is Best For

- Natural Mandarin narration for Chinese-language explainers
- Async long-form narration via `/api/v3/tts/submit` and `/api/v3/tts/query`
- Character-level timing metadata for subtitle alignment
- Calm educational pacing where the video duration can follow the approved voice rhythm

#### Pacing

Start with `speech_rate: 0` for natural Mandarin delivery. If the approved format needs a tighter runtime, compare short samples at `speech_rate: 25` or `50` before generating the full narration. Do not force Doubao to match another provider's duration unless the user explicitly wants that tradeoff.

#### Pricing

Doubao Speech 2.0 is billed by character package or usage in Volcengine. OpenMontage estimates cost from text length and prefers provider-returned usage metadata when available.

---

### Tencent Hunyuan Cloud — Video Generation

> **Tencent Hunyuan (腾讯混元) cloud video generation via TokenHub API.** Generates
> videos from text or images using Tencent's Hunyuan models through the Tencent
> TokenHub API — an OpenAI-compatible gateway (tokenhub.tencentmaas.com) with
> simple Bearer-token authentication. No TC3-HMAC-SHA256 signing required.

**Tools unlocked:** `hunyuan_cloud_video`
**Env var:** `TENCENT_TOKENHUB_API_KEY`

#### Setup

1. Go to the [Tencent Cloud TokenHub console](https://console.cloud.tencent.com/tokenhub).
2. Create an application or navigate to the **API Key** section.
3. Generate an API key and copy its value.
4. Add to `.env`:
   ```bash
   TENCENT_TOKENHUB_API_KEY=your-tokenhub-api-key
   ```

#### What It's Best For

- **Chinese-friendly prompt understanding** — Hunyuan models natively understand Chinese prompts better than most Western APIs
- **Simple auth** — Bearer token, no complex signing (just an HTTP Authorization header)
- **Direct Tencent Cloud quota** — uses your own Tencent Cloud credits, not a third-party gateway mark-up
- **Both T2V and I2V** — one API key unlocks text-to-video and image-to-video

#### API Notes

TokenHub uses a **submit-then-poll** pattern:

```text
# Submit a generation task
POST https://tokenhub.tencentmaas.com/v1/api/video/submit
Authorization: Bearer ${TENCENT_TOKENHUB_API_KEY}

# Poll for results
POST https://tokenhub.tencentmaas.com/v1/api/video/query
Authorization: Bearer ${TENCENT_TOKENHUB_API_KEY}
```

| Model | Type | Pricing |
|-------|------|---------|
| `hy-video-1.5` | Text-to-video | 1.5 credits (~$0.25) |
| `yt-video-2.0` | Image-to-video | 2–5 credits (~$0.33–0.83) |

Resolution options: **720p** (default) or **1080p**.

A watermark (`logo_add`) is added by default. Set `logo_add: 0` to disable it (requires console approval from Tencent).

**Schema constraints:**
- **Prompt:** max 200 UTF-8 characters
- **Image:** max 10MB, 50–5000 px per side, aspect ratio 1:4 to 4:1
- **Formats:** jpg, png, jpeg, webp, bmp, tiff

#### Fallback Tools

If `hunyuan_cloud_video` returns an error, the agent may retry with: `jimeng_video`, `kling_official_video`, `minimax_video`

#### Pricing

Tencent TokenHub uses a credit-based pricing system (1 credit = 1.2 RMB ≈ $0.167 USD):

| Model | Resolution | Credits | Estimated USD |
|-------|-----------|---------|---------------|
| HY-Video-1.5 | any | 1.5 | ~$0.25 |
| YT-Video-2.0 | 480p | 2 | ~$0.33 |
| YT-Video-2.0 | 720p / 1080p | 5 | ~$0.83 |

> **Free tier:** Tencent occasionally offers new-user credits for TokenHub. Check the [TokenHub console](https://console.cloud.tencent.com/tokenhub) for current promotions.

---

### Tencent Hunyuan Cloud — 3D Generation

> **Tencent Hunyuan (腾讯混元) 3D asset generation via TokenHub API.** Generates
> textured/PBR GLB meshes from text, a single image, or up to eight multi-view
> images using the Tencent TokenHub OpenAI-compatible gateway with Bearer-token
> authentication — the same key as `hunyuan_cloud_video`. No TC3-HMAC-SHA256
> signing required.

**Tools unlocked:** `hunyuan_cloud_3d`
**Env var:** `TENCENT_TOKENHUB_API_KEY`

#### Setup

Same TokenHub key as video/image generation:

1. Go to the [Tencent Cloud TokenHub console](https://console.cloud.tencent.com/tokenhub).
2. Create an application or navigate to the **API Key** section.
3. Generate an API key and copy its value.
4. Add to `.env`:
   ```bash
   TENCENT_TOKENHUB_API_KEY=your-tokenhub-api-key
   ```

#### Model Support

Only the **`hy-3d-3.1`** professional model is supported. Operations:

| Operation | Input | Notes |
|-----------|-------|-------|
| `text_to_3d` | Prompt (max 1024 UTF-8 chars) | Chinese-friendly; prompt and image are mutually exclusive |
| `image_to_3d` | One front-view image (URL or local path), optionally + up to 7 `multi_view_images` | Max 8MB, 128–5000px per side, jpg/png/jpeg/webp; views: `left`, `right`, `back`, `top`, `bottom`, `left_front`, `right_front`; encoded total ≤8MB |

`generate_type`: **Normal** (textured geometry, default) or **Geometry**
(untextured white model). `LowPoly` and `Sketch` are 3.0-only and rejected.
`enable_pbr` adds PBR materials; `face_count` targets 3000–1500000 triangles.
`result_format` may add one of STL/USDZ/FBX — OBJ and GLB are always returned
(GLB only for `Geometry`).

#### API Notes

TokenHub uses a **submit-then-poll** pattern mirroring the native Tencent
Cloud actions `SubmitHunyuanTo3DProJob` / `QueryHunyuanTo3DProJob`
(parameters snake_cased):

```text
# Submit a generation task
POST https://tokenhub.tencentmaas.com/v1/api/3d/submit
Authorization: Bearer ${TENCENT_TOKENHUB_API_KEY}
Body: {"model": "hy-3d-3.1", "prompt": "一只小猫", ...}

# Poll for results
POST https://tokenhub.tencentmaas.com/v1/api/3d/query
Authorization: Bearer ${TENCENT_TOKENHUB_API_KEY}
Body: {"model": "hy-3d-3.1", "id": "<job id>"}
```

Completed jobs return a `data` array of `{type, url, preview_image_url}`
entries (typically `obj` and `glb`). The `obj` entry arrives as a ZIP
package (obj + mtl + textures), which the tool detects by magic bytes and
extracts into `<stem>-pkg/`; the GLB is written to `output_path`. The tool
records preview URLs and the `job_id` in a `.provenance.json` manifest, and
reports the credits the API consumed.

References:
- TokenHub 3D guide: <https://cloud.tencent.com/document/product/1823/130082>
- Submit action: <https://cloud.tencent.com/document/api/1804/123447>
- Query action: <https://cloud.tencent.com/document/api/1804/123448>

#### Fallback Tools

If `hunyuan_cloud_3d` returns an error, the agent may retry with: `fal_3d`, `atlas_3d`

#### Pricing

Per-job credits, per the [混元生3D 计费概述](https://cloud.tencent.com.cn/document/product/1804/123461).
Post-paid price is **1 credit = 0.12 RMB** (settled daily, see
[TokenHub 计费方式](https://cloud.tencent.com.cn/document/product/1823/130054) and
[模型价格](https://cloud.tencent.com.cn/document/product/1823/130055)):

> **3D credits are a separate system from other TokenHub models.** The
> 0.12 RMB credit applies only to the Hunyuan 3D models. HY/YT video models
> use a different credit unit (1.0 RMB/credit), and image models bill by
> tokens (10 RMB per million tokens, settled hourly). Per the
> [模型价格](https://cloud.tencent.com.cn/document/product/1823/130055) doc,
> credits of different model families are calculated and consumed
> independently (不互通) — do not reuse the video tool's credit price when
> estimating 3D costs.

| Feature | Credits | Est. RMB | Est. USD |
|---------|---------|----------|----------|
| Normal (textured) generation | 20 | ¥2.40 | ~$0.33 |
| Geometry (white model) | 15 | ¥1.80 | ~$0.25 |
| Multi-view images | +10 | +¥1.20 | ~$0.17 |
| PBR materials (`enable_pbr`) | +10 | +¥1.20 | ~$0.17 |
| Explicit face count | +10 | +¥1.20 | ~$0.17 |
| Extra result format | +5 | +¥0.60 | ~$0.08 |

Typical jobs: Normal text/image-to-3D ≈ $0.33; with PBR ≈ $0.50; the 3.1
model's full combo (Normal + multi-view + PBR + face count + format) ≈ $0.92.
Failed jobs are never billed, and the API returns the consumed credits per job.

Prepaid credit packs discount the per-credit price to 0.09–0.10 RMB, and new
users can claim a 100-credit free package in the console. Check the
[TokenHub console](https://console.cloud.tencent.com/tokenhub) for current
promotions before quoting a batch.

---

### Azure AI Speech — Speech-to-Text

> **Cloud transcription.** Azure AI Speech Fast Transcription turns local audio into text with word-level timestamps, speaker diarization, and multi-language identification — no GPU required. Optional: the local faster-whisper `transcriber` remains the default offline STT path. When `AZURE_SPEECH_KEY` is set, the agent prefers `azure_stt` for cloud transcription.

**Tools unlocked:** `azure_stt`
**Env vars:** `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` (or `AZURE_SPEECH_ENDPOINT`)

#### Setup

1. In the [Azure portal](https://portal.azure.com), create a **Speech** resource (Azure AI services → Speech service).
2. Open the resource's **Keys and Endpoint** page.
3. Copy **KEY 1** and the **Location/Region** (e.g. `eastus`).
4. Add to `.env`:
   ```bash
   AZURE_SPEECH_KEY=your-speech-resource-key
   AZURE_SPEECH_REGION=eastus
   # AZURE_SPEECH_ENDPOINT=https://<custom>...  # optional, overrides region
   ```

#### API Notes

OpenMontage uses the **Fast Transcription** REST endpoint, which accepts a local
audio file directly (multipart upload) and returns a synchronous result — no
Azure Blob storage, SAS URLs, or async job polling:

```text
POST https://{region}.api.cognitive.microsoft.com/speechtotext/transcriptions:transcribe?api-version=2024-11-15
Ocp-Apim-Subscription-Key: ${AZURE_SPEECH_KEY}
```

For files longer than ~2 hours or bulk jobs, use Azure Batch Transcription instead (not wired into OpenMontage).

#### What It Is Best For

- Cloud transcription with word-level timestamps and no local GPU
- Multi-language auto-detection across a candidate locale set
- Speaker diarization without a HuggingFace token
- Subtitle timing metadata that flows straight into `subtitle_gen`

#### Pricing

Azure AI Speech Standard (S0) bills speech-to-text by audio-hour (roughly
$1.00/audio-hour at time of writing; a free F0 tier includes a limited monthly
allowance). OpenMontage estimates cost from the transcribed audio duration. See
[Azure AI Speech pricing](https://azure.microsoft.com/pricing/details/cognitive-services/speech-services/) for current rates.

---

### Azure AI Speech — Text-to-Speech

> **Cloud neural narration.** Azure neural TTS delivers high-quality multilingual voices with SSML prosody control and express-as styles — same Speech resource as `azure_stt`, so one key/region unlocks both directions. Optional: the local `piper_tts` remains the default offline TTS path. When `AZURE_SPEECH_KEY` is set, the agent may prefer `azure_tts` for cloud narration.

**Tools unlocked:** `azure_tts`
**Env vars:** `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` (or `AZURE_TTS_ENDPOINT`)

#### Setup

Identical to the STT setup above — the same Speech resource key and region work
for both. If you already configured `azure_stt`, `azure_tts` is available now.

```bash
AZURE_SPEECH_KEY=your-speech-resource-key
AZURE_SPEECH_REGION=eastus
# AZURE_TTS_ENDPOINT=https://<region>.tts.speech.microsoft.com  # optional, overrides region
```

Note: the TTS host (`<region>.tts.speech.microsoft.com`) differs from the STT
endpoint, so the optional override var is `AZURE_TTS_ENDPOINT`, not
`AZURE_SPEECH_ENDPOINT`.

#### API Notes

OpenMontage uses the synchronous REST v1 endpoint with an SSML body — no token
exchange, Blob storage, or job polling:

```text
POST https://{region}.tts.speech.microsoft.com/cognitiveservices/v1
Ocp-Apim-Subscription-Key: ${AZURE_SPEECH_KEY}
Content-Type: application/ssml+xml
X-Microsoft-OutputFormat: audio-48khz-192kbitrate-mono-mp3
```

Voice shortlist aliases: `andrew` (default — warm, confident), `brandon`
(deeper), `ava` (bright female), `guy` (authoritative), `jenny` (friendly). Any
Azure voice short name is accepted verbatim. See the `azure-text-to-speech`
skill for SSML `rate`/`pitch`/`style` guidance.

#### What It Is Best For

- High-quality neural narration on existing Azure credentials
- Calm, confident explainer / founder-register delivery
- Multilingual narration via the *Multilingual* voice family
- Deterministic re-renders (fixed voice + SSML → identical audio)

Not for: fully offline production (use `piper_tts`) or voice cloning (use
`elevenlabs_tts`).

#### Pricing

Azure neural TTS Standard (S0) bills roughly **$16 per 1M characters** (a free
F0 tier includes a limited monthly allowance). A 150-word narration segment
costs about $0.015. OpenMontage estimates cost from character count. See
[Azure AI Speech pricing](https://azure.microsoft.com/pricing/details/cognitive-services/speech-services/) for current rates.

---

### Google — TTS + Imagen + Music + Video (Shared Key)

> **One key, five tools.** Google Cloud TTS has 700+ voices in 50+ languages — the strongest localization option. `google_imagen` supports both Imagen 4 and Gemini 2.5 Flash Image, including projects without Imagen catalog access. Google Lyria generates high-quality background music. Gemini Omni Flash supports conversational video editing, and direct Veo generation covers premium short video clips.

**Tools unlocked:** `google_tts`, `google_imagen`, `google_music`, `gemini_omni_video`, `veo_video`
**Env var:** `GOOGLE_API_KEY` (or `GEMINI_API_KEY` — either works; `GEMINI_API_KEY` takes precedence)

#### Setup

1. Go to [Google AI Studio](https://aistudio.google.com/) and sign in
2. Navigate to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
3. Click **Create API Key**, select a Google Cloud project
4. Copy the key
5. Add to `.env`: `GOOGLE_API_KEY=AIza...` (or `GEMINI_API_KEY=AIza...`)

**For TTS specifically**, you also need to enable the Text-to-Speech API:
1. Visit [console.cloud.google.com/apis/library/texttospeech.googleapis.com](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
2. Click **Enable**
3. Make sure your API key's restrictions allow the Text-to-Speech API

**For Imagen, Lyria Music, Gemini Omni video, and direct Veo video**, enable the Generative Language API:
1. Visit [console.cloud.google.com/apis/library/generativelanguage.googleapis.com](https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com)
2. Click **Enable**

#### Google TTS Pricing

| Voice Type | Free tier | Paid (per 1M chars) | Notes |
|-----------|-----------|---------------------|-------|
| **Standard** | 1M chars/month | $4.00 | Basic quality, fast |
| **WaveNet** | 1M chars/month | $16.00 | Natural-sounding |
| **Neural2** | 1M chars/month | $16.00 | Best quality |
| **Studio** | — | $24.00 | Professional studio voices |
| **Chirp** | — | $4.00 | Conversational style |

The free tiers apply *independently* — you get 1M Standard AND 1M WaveNet AND 1M Neural2 characters per month free. That's roughly 250+ minutes of narration per month at zero cost.

#### Google Imagen Pricing

| Model | Price per image |
|-------|----------------|
| Imagen 4 Fast | $0.02 |
| Imagen 4 Standard | $0.04 |
| Imagen 4 Ultra | $0.06 |
| Gemini 2.5 Flash Image (`gemini-2.5-flash-image`) | $0.039 |

**Free tier for Imagen:** None. Paid tier only.

To select the Gemini backend through the governed `image_selector`, pass
`preferred_provider: "google_imagen"` and
`model_name: "gemini-2.5-flash-image"`. The selector maps its neutral
`model_name` field to the provider's `model` input.

#### Gemini Omni Video Pricing

| Model | Price | Notes |
|-------|-------|-------|
| `gemini-omni-flash-preview` | ~$0.10 per second of video | Billed as 5,792 output tokens/sec of 720p video at $17.50/1M tokens |

Generates 3–10 second clips at 720p/24fps with synthesized audio, plus stateful conversational editing (`edit_video` via `previous_interaction_id`). **Paid tier only — no free tier.** A typical 8-second clip costs ~$0.80; each edit turn generates a new clip and bills again.

#### Google Music (Lyria) Pricing

| Model | Price per generation request |
|-------|-----------------------------|
| `lyria-3-pro-preview` | $0.08 (flat rate, up to 184s duration) |

**Free tier for Music:** None. Paid tier only.

**New account bonus:** Google Cloud offers **$300 in free credits** for new accounts (90-day trial), applicable to TTS, Imagen, Music, Gemini Omni video, and direct Veo video.

#### Google TTS Voice Types

Google TTS offers 700+ voices across 50+ languages. Voice names follow the pattern `{language}-{type}-{letter}`:

| Type | Example | Quality | Cost |
|------|---------|---------|------|
| **Chirp 3 HD** | `en-US-Chirp3-HD-Orus` | **Best (2024, most natural)** | **Mid — default** |
| Standard | `en-US-Standard-A` | Good | Cheapest |
| WaveNet | `en-US-WaveNet-D` | Very good | Mid |
| Neural2 | `en-US-Neural2-D` | Excellent | Mid |
| Studio | `en-US-Studio-O` | Professional | Highest |
| Journey | `en-US-Journey-D` | Conversational (long-form) | Mid |

**Recommended voices:** `en-US-Chirp3-HD-Orus` (male, rich/cinematic), `en-US-Chirp3-HD-Aoede` (female, warm). These are Google's newest tier — most natural-sounding, uses the v1beta1 endpoint automatically.

**Languages include:** English (US, UK, AU, IN), Spanish, French, German, Italian, Portuguese, Japanese, Korean, Chinese (Mandarin, Cantonese), Arabic, Hindi, Russian, Dutch, Polish, Turkish, Vietnamese, Thai, Indonesian, and 30+ more.

---

### OpenAI — TTS + Image Generation

> **Solid all-rounder.** GPT Image 2 handles complex multi-element compositions and in-image text well. TTS is fast and affordable.

**Tools unlocked:** `openai_tts`, `openai_image`
**Env var:** `OPENAI_API_KEY`

#### Setup

1. Go to [platform.openai.com/signup](https://platform.openai.com/signup) and create an account
2. Add a payment method at [platform.openai.com/account/billing](https://platform.openai.com/account/billing)
3. Navigate to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
4. Click **Create new secret key**, name it, copy it
5. Add to `.env`: `OPENAI_API_KEY=sk-...`

#### TTS Pricing

| Model | Price per 1M characters |
|-------|------------------------|
| tts-1 | $15.00 |
| tts-1-hd | $30.00 |
| gpt-4o-mini-tts | $12.00 |

#### Image Pricing

| Model | Size | Quality | Price per image |
|-------|------|---------|----------------|
| GPT Image 2 | 1024x1024 | low | $0.006 |
| GPT Image 2 | 1024x1024 | medium | $0.053 |
| GPT Image 2 | 1024x1024 | high | $0.211 |
| GPT Image 2 | 1024x1536 / 1536x1024 | low | $0.005 |
| GPT Image 2 | 1024x1536 / 1536x1024 | medium | $0.041 |
| GPT Image 2 | 1024x1536 / 1536x1024 | high | $0.165 |

> **Note:** DALL-E 2/3 were shut down by OpenAI on 2026-05-12, and the `gpt-image-1` family (`gpt-image-1-mini`, `gpt-image-1.5`) retires 2026-12-01 — `gpt-image-2` is OpenAI's recommended replacement ([deprecations](https://developers.openai.com/api/docs/deprecations)).

**Free tier:** None. Requires prepaid billing. Previously offered $5 in free credits for new accounts (discontinued for most signups).

---

### Runway — Native and Third-Party Video Models

> **Multi-model production API.** OpenMontage supports current Runway-native
> models plus documented third-party Seedance 2.5, Gemini Omni Flash, and
> MiniMax H3/Hailuo 3.0 routes.

**Tools unlocked:** `runway_video`
**Env var:** `RUNWAY_API_KEY`

#### Setup

1. Go to [dev.runwayml.com](https://dev.runwayml.com/) and create a developer account
2. Subscribe to a paid plan (Standard or above — API requires subscription)
3. Generate an API key from the developer portal
4. Add to `.env`: `RUNWAY_API_KEY=key_...`

#### Pricing

| Plan | Price | Credits/month | Video capacity |
|------|-------|---------------|----------------|
| **Free** | $0 | 125 one-time | ~5 seconds Gen-4 |
| Standard | $12/mo | 625 | ~25 seconds Gen-4 |
| Pro | $28/mo | 2,250 | ~90 seconds Gen-4 |
| Unlimited | $76/mo | Unlimited (Explore Mode) | Unlimited Gen-4 Turbo |

**API pricing (Runway credits are $0.01 each):**

| Model | Price per second |
|-------|-----------------|
| Gen-4 Turbo | ~$0.05 |
| Gen-4.5 | ~$0.12 |
| Seedance 2.5 | ~$0.20 at 480p / ~$0.30 at 720p |
| Gemini Omni Flash | ~$0.10 generation / ~$0.11 video editing |
| MiniMax H3 (`hailuo3`) | ~$0.10 at 768P / ~$0.15 at 2K |

Seedance 2.5 supports text, image, and video inputs, 4–30 second outputs, and
up to 30 image, 10 video, and 10 audio references. Gemini Omni Flash supports
3–10 second text/image generation plus video editing with up to five image
references. Hailuo 3.0 is Runway's MiniMax H3 route and supports 5–15 second
outputs at 768P or 2K. The adapter maps each model to its exact request field
names instead of sending a generic payload.

Gen-3 Alpha Turbo and Gen-4 Aleph were removed from the Runway API on
2026-07-30 and are not offered by the tool.

**Free tier:** 125 one-time credits (no monthly renewal). Enough for about 5 seconds of Gen-4 video. API access requires a paid subscription.

---

### Higgsfield — Multi-Model Video Orchestrator

> **Multi-model video platform.** Routes to Kling 3.0, Veo 3.1, Sora 2, WAN 2.5, and proprietary Soul Cinema through a single API. Includes Soul ID for character consistency across clips.

**Tools unlocked:** `higgsfield_video`
**Env vars:** `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET` (or combined `HIGGSFIELD_KEY=key:secret`)

#### Setup

1. Go to [cloud.higgsfield.ai](https://cloud.higgsfield.ai/) and create an account
2. Subscribe to a plan (Starter or above for API access)
3. Navigate to API Keys section at [cloud.higgsfield.ai/api-keys](https://cloud.higgsfield.ai/api-keys)
4. Generate an API key and secret
5. Add to `.env`:
   ```
   HIGGSFIELD_API_KEY=your-api-key
   HIGGSFIELD_API_SECRET=your-api-secret
   ```

#### Pricing

| Plan | Price | Notes |
|------|-------|-------|
| Free | $0 | Limited credits |
| Starter | $15/mo | Basic allocation |
| Plus | $34/mo | Mid-tier, ~33-56 Kling 3.0 clips |
| Ultra | $84/mo | High volume |

**Per-generation costs (approximate, via credits):**

| Model | Cost per clip |
|-------|--------------|
| Kling 3.0 | ~$0.10 (cheapest) |
| WAN 2.5 | ~$0.10 |
| Soul Cinema | ~$0.15 |
| Veo 3.1 | ~$0.50 |
| Sora 2 | ~$0.50 |

**Free tier:** Limited credits on signup. No monthly renewal on free plan.

---

### HeyGen — Avatar Video Gateway

> **Multi-model video gateway.** Access VEO, Sora, Runway, Kling, and Seedance through a single API.

**Tools unlocked:** `heygen_video`
**Env var:** `HEYGEN_API_KEY`

#### Setup

1. Go to [app.heygen.com/register](https://app.heygen.com/register) and create an account
2. Navigate to the API section in settings
3. Generate your API key
4. Add API balance (prepaid, separate from web plan credits)
5. Add to `.env`: `HEYGEN_API_KEY=your-key-here`

#### Pricing

| Service | Price |
|---------|-------|
| Avatar video (Engine III) | $0.017/sec |
| Avatar video (Engine IV) | $0.10/sec |
| Prompt to Video | $0.033/sec |
| Video Translation (Speed) | $0.05/sec |
| Video Translation (Precision) | $0.10/sec |

**Web plans:**

| Plan | Price | Notes |
|------|-------|-------|
| Free | $0 | 1 credit (demo) |
| Creator | $24/mo | Limited credits |
| Business | $72/mo | API access, more credits |

**Free tier:** 1 credit on web platform. API is pay-as-you-go with prepaid balance.

---

### Suno — AI Music Generation

> **Full songs with vocals and lyrics.** Any genre, up to 8 minutes. Instrumentals or vocal tracks.

**Tools unlocked:** `suno_music`
**Env var:** `SUNO_API_KEY`

#### Setup

1. Go to [suno.com](https://suno.com) and create a Suno account
2. For API access, go to [sunoapi.org](https://sunoapi.org) and create an account
3. Navigate to the dashboard and copy your API key
4. Add credits (1 credit = $0.005 USD)
5. Add to `.env`: `SUNO_API_KEY=your-key-here`

#### Pricing

**Suno platform:**

| Plan | Price | Credits | Notes |
|------|-------|---------|-------|
| Free | $0 | 50/day | ~10 songs/day, non-commercial only |
| Pro | $10/mo | 2,500/mo | Commercial license |
| Premier | $30/mo | 10,000/mo | Commercial license |

**API (via sunoapi.org):** Pay-as-you-go, 1 credit = $0.005. Each generation produces 2 tracks.

---

### Pexels — Free Stock Media

> **Completely free.** No cost, no attribution required, commercial use allowed.

**Tools unlocked:** `pexels_image`, `pexels_video`
**Env var:** `PEXELS_API_KEY`

#### Setup

1. Go to [pexels.com/join](https://www.pexels.com/join/) and create a free account
2. Navigate to [pexels.com/api](https://www.pexels.com/api/)
3. Click **Your API Key** or request API access
4. Copy your key from the dashboard
5. Add to `.env`: `PEXELS_API_KEY=your-key-here`

#### Pricing

**Completely free.** No paid tiers. No attribution required. Commercial use allowed.

- 200 requests/hour
- 20,000 requests/month
- Photo and video search + download

---

### Pixabay — Free Stock Media

> **Completely free.** 5M+ royalty-free images and videos.

**Tools unlocked:** `pixabay_image`, `pixabay_video`
**Env var:** `PIXABAY_API_KEY`

#### Setup

1. Go to [pixabay.com/accounts/register](https://pixabay.com/accounts/register/) and create a free account
2. Navigate to [pixabay.com/api/docs](https://pixabay.com/api/docs/)
3. Your API key is displayed at the top of the docs page (after login)
4. Copy the key
5. Add to `.env`: `PIXABAY_API_KEY=your-key-here`

#### Pricing

**Completely free.** No paid tiers. No attribution required. Commercial use allowed.

- ~100 requests/minute
- 5,000 requests/hour
- Photo and video search + download
- Standard API limited to 1280px images (full resolution requires editorial API)

---

## Local Providers (Free, No API Key)

These providers run entirely on your machine. No network, no API key, no cost. Some require a GPU.

### Remotion — Programmatic Video Composition

> **React-based video rendering.** Turns still images into animated video with spring physics, animated text cards, stat cards, charts, and transitions. **This is the key fallback when no video generation providers are configured** — the agent generates images and Remotion animates them into professional-looking video.

**Tool:** `video_compose` (with `operation="render"` — auto-routes to Remotion when needed)
**Runtime:** CPU (Node.js required)
**Env var:** None

#### Setup

```bash
# Included in make setup, or install manually:
cd remotion-composer && npm install && cd ..
```

Requires **Node.js 18+** and `npx`. The `remotion-composer/` project is included in the repo.

#### What Remotion Renders

| Component | What it produces |
|-----------|-----------------|
| **TextCard** | Animated title/body text with spring physics entrance |
| **StatCard** | Animated statistics with count-up animations |
| **ProgressBar** | Animated progress indicators |
| **CalloutBox** | Highlighted callout panels with icon animations |
| **ComparisonCard** | Side-by-side comparison layouts |
| **BarChart / LineChart / PieChart** | Animated data visualizations |
| **KPIGrid** | Multi-metric dashboard cards |
| **Image scenes** | Still images with spring-animated motion (replaces Ken Burns) |

#### When Does Remotion Activate?

The `video_compose` tool's `render` operation auto-detects when Remotion is needed:
- Cuts contain still images (`.png`, `.jpg`, etc.)
- Cuts have `type` set to `text_card`, `stat_card`, `chart`, etc.
- Cuts specify `animation` or `transition_in`/`transition_out`

If Remotion is not installed, compositions fall back to FFmpeg Ken Burns pan-and-zoom — functional but less engaging.

**Cost:** Free. Always local.

---

### HyperFrames - HTML/CSS/GSAP Video Composition

> **GSAP-native local rendering.** HyperFrames is the preferred runtime for motion-graphics-heavy HTML compositions and the `character-animation` pipeline's rigged SVG character acting.

**Tool:** `hyperframes_compose` directly, or `video_compose` with `edit_decisions.render_runtime="hyperframes"`
**Runtime:** CPU (Node.js >= 22, FFmpeg, and `npx` required)
**Env var:** None

#### Setup

```bash
node --version
ffmpeg -version
npx --yes hyperframes doctor
```

The CLI is consumed as `npx hyperframes`. Do not use `npx @hyperframes/cli`; that package name is not the OpenMontage runtime path.

#### What HyperFrames Renders

| Use case | What it produces |
|----------|------------------|
| **Kinetic typography** | HTML/CSS text animation driven by GSAP timelines |
| **Product / launch videos** | Structured HTML scenes, registry blocks, and transitions |
| **Website-to-video** | Browser-captured site compositions with HyperFrames validation |
| **Character animation** | SVG character rigs, pose/action timelines, and GSAP acting beats rendered to `renders/final.mp4` |

HyperFrames workspaces live under `projects/<project-name>/hyperframes/`. Final videos still follow the normal OpenMontage convention: `projects/<project-name>/renders/final.mp4`.

**Cost:** Free. Always local.

---

### Piper TTS — Offline Text-to-Speech

> **Completely free, fully offline TTS.** No network required. Good quality for drafts and budget-constrained projects.

**Tool:** `piper_tts`
**Runtime:** CPU (no GPU needed)
**Env var:** None

#### Setup

```bash
# Install via pip
pip install piper-tts

# Or download the binary from GitHub
# https://github.com/rhasspy/piper/releases

# Download a voice model (first run downloads automatically)
piper --download-dir ~/.piper/models --model en_US-lessac-medium
```

**Available voices:** ~30 English voices plus voices for German, French, Spanish, Italian, and other languages. Lower variety than cloud providers but completely free and offline.

**Quality:** Good for drafts, internal videos, and budget projects. For client-facing narration, use ElevenLabs or Google TTS.

---

### ComfyUI Video — Local Workflows and Hosted Partner Nodes

**Tool:** `comfyui_video`

**Optional env vars:** `COMFYUI_SERVER_URL` (default
`http://localhost:8188`) and `COMFYUI_VIDEO_SERVER_URL` (video-specific
override).

The bundled WAN 2.2 workflows and caller-supplied local workflows execute on
the ComfyUI machine. MiniMax H3 is available as an official open-weight local
workflow; pass the official workflow exported in API format using
`workflow_json` or `workflow_path`, plus its `output_node`.

The MiniMax H3 local stack includes the pruned INT8 diffusion model, Qwen3-VL
text encoder, video VAE, and audio VAE. OpenMontage exposes the official
download URLs and destination folders in tool metadata rather than silently
downloading large weights.

The same tool also supports these ComfyUI Partner Nodes:

| `model_family` | Node | Execution | Approximate cost |
|----------------|------|-----------|------------------|
| `gemini_omni_flash` | `GeminiVideoOmni` | Hosted Partner Node | ~$0.146/sec |
| `seedance_2.5` | `ByteDance2TextToVideoNode` | Hosted Partner Node | ~$0.148/sec 480p; ~$0.333/sec 720p |
| `minimax_h3_api` | `MinimaxHailuo03TextToVideoNode` | Hosted Partner Node | ~$0.129/sec 768P; ~$0.186/sec 2K |
| `minimax_h3_local` | official MiniMax H3 graph | Local GPU | No API charge |

Partner Nodes are not offline: they require current ComfyUI, network access, a
logged-in Comfy account, and prepaid credits. Prices are estimates converted
from Comfy credits (211 credits = $1); actual metered usage is authoritative.

Official references: [Partner Node overview](https://docs.comfy.org/tutorials/partner-nodes/overview),
[pricing](https://docs.comfy.org/tutorials/partner-nodes/pricing), and
[MiniMax H3 local tutorial](https://docs.comfy.org/tutorials/video/minimax/minimax-h3).

---

### Local Video Generation (GPU Required)

> **Free AI video generation.** Requires an NVIDIA GPU with sufficient VRAM.

**Tools:** `wan_video`, `hunyuan_video`, `cogvideo_video`, `ltx_video_local`
**Runtime:** Local GPU (CUDA required)
**Env vars:** `VIDEO_GEN_LOCAL_ENABLED=true`, `VIDEO_GEN_LOCAL_MODEL=<model>`

#### Setup

```bash
# 1. Install the GPU stack
make install-gpu
# Or manually:
pip install diffusers transformers accelerate torch pillow requests

# 2. Enable local generation in .env
VIDEO_GEN_LOCAL_ENABLED=true

# 3. Choose a model based on your GPU VRAM
VIDEO_GEN_LOCAL_MODEL=wan2.2-ti2v-5b   # 12GB+ VRAM (default; 720p @ 24fps, T2V+I2V+V2V)
VIDEO_GEN_LOCAL_MODEL=wan2.1-1.3b      # 6GB+ VRAM (entry-level, text-to-video only)
VIDEO_GEN_LOCAL_MODEL=wan2.1-14b       # 24GB+ VRAM (best Wan 2.1 quality)
VIDEO_GEN_LOCAL_MODEL=hunyuan-1.5      # 12GB+ VRAM
VIDEO_GEN_LOCAL_MODEL=ltx2-local       # 8GB+ VRAM (fastest)
VIDEO_GEN_LOCAL_MODEL=cogvideo-5b      # 10GB+ VRAM
VIDEO_GEN_LOCAL_MODEL=cogvideo-2b      # 6GB+ VRAM (lightest)
```

#### Model Comparison

| Model | VRAM | Quality | Speed | Best for |
|-------|------|---------|-------|----------|
| **WAN 2.2 TI2V (5B)** | 12GB | Excellent | Medium | Default. 720p @ 24fps, one checkpoint for T2V/I2V/V2V |
| **WAN 2.1 (1.3B)** | 6GB | Good | Fast | Entry-level GPU, quick iteration (text-to-video only) |
| **WAN 2.1 (14B)** | 24GB | Excellent | Slow | Best Wan 2.1 quality |
| **Hunyuan 1.5** | 12GB | Very good | Medium | Mid-range GPUs |
| **LTX-2** | 8GB | Good | Fastest | Quick drafts, lowest latency |
| **CogVideo (5B)** | 10GB | Good | Medium | Balanced option |
| **CogVideo (2B)** | 6GB | Fair | Fast | Low-VRAM experimentation |

**All local models support:** text-to-video, offline generation, seeded reproducibility.

#### WAN 2.2 — the full operation matrix

`wan_video` drives one checkpoint across every Wan task. The `operation` input selects
the diffusers pipeline; the tool refuses an operation the chosen variant has no weights for.

| `operation` | What it does | Extra inputs |
|-------------|--------------|--------------|
| `text_to_video` | Prompt to clip | — |
| `image_to_video` | Animate a still | `reference_image_path` / `reference_image_url` |
| `video_to_video` | Restyle an existing clip | `source_video_path`, `strength` |
| `first_last_frame` | Interpolate between two stills | `reference_image_*` + `last_image_*` |
| `text_to_image` | Single frame, saved as PNG | — |

Geometry is snapped to what the VAE can encode, so you can ask for any size: frame counts
land on `4k + 1`, and width/height land on a multiple of 32 for the TI2V line (its 16x VAE
plus 2x patching is why 720p is **1280x704**, not 1280x720) or 16 elsewhere.

#### Clips longer than five seconds

Wan is trained for roughly a five-second pass. Ask for more with `duration_seconds` and the
tool chains segments: each continuation is seeded with the previous segment's last frame,
regenerates it as its own frame 0, and that duplicate is dropped at the seam.

```python
wan_video.execute({
    "prompt": "A red convertible on a coastal road at golden hour",
    "duration_seconds": 30,          # -> 720 frames @ 24fps -> 6 chained segments
    "width": 704, "height": 480,
    "num_inference_steps": 20,
    "offload_mode": "sequential",
    "segment_prompts": [...],        # optional shot list, one entry per segment
})
```

Chaining drifts: every hop conditions on already-generated pixels, so contrast and colour
creep. `correct_drift` (on by default) re-grades each segment to the opening segment's
channel statistics. Pass `segment_prompts` to steer the clip through a shot list instead of
repeating one prompt six times.

#### Fitting a 12GB card

`precision` (`auto`/`bf16`/`int8`/`int4`) and `offload_mode` (`auto`/`model`/`sequential`)
both default to `auto` and are picked from visible VRAM.

A bf16 5B transformer is ~10GB resident. With `offload_mode="model"` that leaves almost
nothing for activations on a 12GB card — measured peak was 10.85GB at just 512x320.
`offload_mode="sequential"` streams one submodule at a time: the same card then peaks at
**1.97GB** and renders 704x480 comfortably, at the cost of ~4s per denoising step of PCIe
traffic. On a 12GB GPU `auto` selects it for you.

> **NVIDIA driver note.** If the loaded kernel module and the installed userspace libraries
> are different versions, `nvmlInit` fails. CUDA compute still runs, but PyTorch calls NVML
> while composing an out-of-memory report — so real OOMs surface as an internal assert, and
> bitsandbytes (`int8`/`int4`) cannot load at all. Compare `cat /proc/driver/nvidia/version`
> with `nvidia-smi`; if they disagree, reboot. `wan_video` detects this and says so.


Image-to-video is *not* universal — Wan 2.1 never shipped 1.3B I2V weights and CogVideo is
text-only. Each variant's real capability list is `operations` in `tools/video/_shared.py`,
and `wan_video` refuses an operation the selected checkpoint cannot do.

---

### Local Diffusion — Offline Image Generation (GPU Required)

> **Free Stable Diffusion image generation.** No API cost, fully offline.

**Tool:** `local_diffusion`
**Runtime:** Local GPU (CUDA required)
**Env var:** None (enable by installing dependencies)

#### Setup

```bash
pip install diffusers transformers accelerate torch
```

First run downloads the model (~4GB). Subsequent runs use the cached model.

**VRAM requirement:** 4GB+ (8GB recommended for 1024x1024 images)

**Supports:** Negative prompts, seeds, custom sizes. Quality is lower than FLUX or GPT Image 2 but completely free and offline.

---

### LTX-2 on Modal — Self-Hosted Cloud GPU

> **Run LTX-2 on Modal's cloud GPUs.** Your own endpoint, your own scale. More consistent than local GPU, cheaper than commercial APIs.

**Tool:** `ltx_video_modal`
**Runtime:** Cloud (self-hosted)
**Env var:** `MODAL_LTX2_ENDPOINT_URL`

#### Setup

1. Create a [Modal](https://modal.com) account
2. Deploy the LTX-2 endpoint (see Modal docs)
3. Set the endpoint URL in `.env`: `MODAL_LTX2_ENDPOINT_URL=https://your-modal-endpoint`

**Modal pricing:** ~$0.99/hour for A100 GPU time. Cost per video depends on generation time.

---

### Other Local Tools (Always Available)

These tools require only FFmpeg or Python packages — no GPU, no API key.

| Tool | Install | What it does |
|------|---------|-------------|
| **FFmpeg tools** (video_compose, video_stitch, video_trimmer, audio_mixer, audio_enhance, color_grade, face_enhance, frame_sampler, scene_detect) | `brew install ffmpeg` / `sudo apt install ffmpeg` / `winget install FFmpeg` | Video editing, audio processing, color grading, analysis |
| **Transcriber** | `pip install faster-whisper` | Speech-to-text with word-level timestamps |
| **Background Remove** | `pip install rembg` (CPU) or `pip install rembg[gpu]` | Remove image/video backgrounds |
| **Upscale** | `pip install realesrgan` (requires PyTorch + CUDA) | Real-ESRGAN image/video upscaling |
| **Face Restore** | `pip install gfpgan` (requires PyTorch) | CodeFormer/GFPGAN face restoration |
| **Code Snippet** | `pip install Pygments Pillow` | Syntax-highlighted code images |
| **Diagram Gen** | `npm install -g @mermaid-js/mermaid-cli` | Mermaid diagram rendering |
| **Math Animate** | `pip install manim` | ManimCE mathematical animations |
| **Subtitle Gen** | No install needed | SRT/VTT subtitle file generation |
| **Video Understand** | `pip install transformers torch` | CLIP/BLIP-2 visual analysis |
| **Talking Head** | Clone [SadTalker](https://github.com/OpenTalker/SadTalker) | Avatar animation from photo + audio |
| **Lip Sync** | Clone [Wav2Lip](https://github.com/Rudrabha/Wav2Lip) | Audio-driven lip synchronization |

---

## Provider-to-Tool Mapping

| Provider | Env Var | Tools Unlocked | Cost |
|----------|---------|---------------|------|
| **Pexels** | `PEXELS_API_KEY` | `pexels_image`, `pexels_video` | Free |
| **Pixabay** | `PIXABAY_API_KEY` | `pixabay_image`, `pixabay_video` | Free |
| **Piper** | — (install only) | `piper_tts` | Free |
| **Azure AI Speech** | `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` | `azure_stt`, `azure_tts` | Free tier + paid |
| **Google** | `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) | `google_tts`, `google_imagen`, `google_music`, `gemini_omni_video`, `veo_video` | Free tier (TTS) + paid |
| **ElevenLabs** | `ELEVENLABS_API_KEY` | `elevenlabs_tts`, `music_gen` | Free tier + paid |
| **fish.audio** | `FISH_AUDIO_API_KEY` | `fish_audio_tts` | Free tier (s2.1-pro-free) + paid |
| **fal.ai** | `FAL_KEY` | `flux_image`, `recraft_image`, `kling_video`, `veo_video`, `seedance_video`, `gemini_omni_fal`, `minimax_fal_video` | Pay-as-you-go |
| **Atlas Cloud** | `ATLASCLOUD_API_KEY` | `atlas_image`, `atlas_video` | Pay-as-you-go |
| **Kling Official** | `KLING_API_KEY` | `kling_official_video`, `kling_official_image`, `kling_tts`, `kling_avatar`, `kling_lip_sync` | Pay-as-you-go |
| **Volcengine Ark** | `ARK_API_KEY` | `seedance_ark` | Pay-as-you-go |
| **MiniMax direct** | `MINIMAX_API_KEY` | `minimax_image`, `minimax_video` | Pay-as-you-go |
| **OpenAI** | `OPENAI_API_KEY` | `openai_tts`, `openai_image` | Paid only |
| **xAI** | `XAI_API_KEY` | `grok_image`, `grok_video` | Paid only |
| **Runway** | `RUNWAY_API_KEY` | `runway_video` | Free trial + paid |
| **Higgsfield** | `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET` | `higgsfield_video` | Subscription ($15-84/mo) |
| **HeyGen** | `HEYGEN_API_KEY` | `heygen_video` | Pay-as-you-go |
| **Suno** | `SUNO_API_KEY` | `suno_music` | Pay-as-you-go |
| **Tencent Hunyuan** | `TENCENT_TOKENHUB_API_KEY` | `hunyuan_cloud_video`, `hunyuan_cloud_3d` | Pay-as-you-go (video ~$0.25–0.83/gen; 3D ~$0.25–0.92/model) |
| **Local GPU** | `VIDEO_GEN_LOCAL_ENABLED` | `wan_video`, `hunyuan_video`, `cogvideo_video`, `ltx_video_local` | Free (GPU required) |
| **Local Diffusion** | — (install only) | `local_diffusion` | Free (GPU required) |
| **Modal** | `MODAL_LTX2_ENDPOINT_URL` | `ltx_video_modal` | Self-hosted cloud |
| **ComfyUI** | optional server URL overrides | `comfyui_video` | Local GPU, or paid Partner Node credits |

---

## Capability Coverage

How many providers cover each capability:

| Capability | Cloud Providers | Local Providers | Free Options |
|-----------|----------------|-----------------|--------------|
| **Image Generation** | FLUX, Kling Official, Grok, Google Imagen, GPT Image 2, Recraft | Local Diffusion | Pexels, Pixabay (stock) |
| **Video Generation** | Grok, Kling Official, fal.ai, Seedance via Volcengine Ark, Runway, Veo, Gemini Omni, Higgsfield, MiniMax, HeyGen, Tencent Hunyuan, ComfyUI Partner Nodes | WAN, Hunyuan, CogVideo, LTX, ComfyUI WAN, ComfyUI MiniMax H3 | Pexels, Pixabay (stock) |
| **Text-to-Speech** | Azure AI Speech, ElevenLabs, fish.audio, Google TTS, Kling Official, OpenAI | Piper | Piper, Google free tier, ElevenLabs free tier, Azure free tier, fish.audio s2.1-pro-free |
| **Music Generation** | ElevenLabs, Suno, Google Lyria | — | ElevenLabs free tier |
| **3D Asset Generation** | Atlas Cloud, fal.ai, Tencent Hunyuan | Blender (assembly) | CC0 catalogs (`threejs_asset_catalog`) |
| **Post-Production** | — | FFmpeg (compose, stitch, trim, mix, enhance, grade) | All free |
| **Analysis** | — | WhisperX, Scene Detect, Frame Sampler, CLIP/BLIP-2 | All free |
| **Enhancement** | — | Upscale, BG Remove, Face Enhance, Face Restore | All free |
| **Avatar** | Kling Official | SadTalker, Wav2Lip | Local tools are free |

---

## FAQ

**Q: What's the absolute minimum I need to produce a video?**
A: FFmpeg + Node.js (both free, local). FFmpeg handles video assembly, audio mixing, and subtitles. With Node.js, Remotion renders still images into animated video — so even without any video generation API, the agent generates images and Remotion turns them into professional-looking video with spring animations, text cards, and transitions. Add Piper TTS for free narration and Pexels/Pixabay for free stock footage.

**Q: I don't have any video generation providers. Can I still make videos?**
A: Yes. The agent generates still images (via any image provider — even free stock from Pexels/Pixabay) and Remotion composes them into animated video with spring physics transitions, text cards, stat cards, and charts. This is the default path for explainer and animation pipelines when no video gen is configured.

**Q: What's one low-friction way to get AI-generated images and video?**
A: fal.ai (`FAL_KEY`) is one pay-as-you-go option with broad single-key coverage. It unlocks FLUX images plus multiple video providers. No subscription — pay only for what you generate.

**Q: I have a GPU. What can I run locally for free?**
A: Set `VIDEO_GEN_LOCAL_ENABLED=true` and install `diffusers`. You get WAN 2.1, Hunyuan, CogVideo, and LTX video generation plus Stable Diffusion image generation — all free, all offline.

**Q: Which TTS provider should I use?**
A: For quality → ElevenLabs. For localization (50+ languages) → Google TTS. For budget → Google free tier (1M chars/month). For offline → Piper.

**Q: Do I need all these providers?**
A: No. Start with what you have. The selector pattern auto-routes to whatever's available. Missing a provider? The system falls through to the next one automatically.
