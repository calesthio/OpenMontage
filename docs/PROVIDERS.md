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
| 8 | **$12/month** | Runway | Gen-4 video — highest quality AI video |
| 9 | **pay-as-you-go** | HeyGen | Avatar videos, multi-model video gateway |
| 10 | **pay-as-you-go** | Suno | Full song generation with vocals and lyrics |
| 11 | **$0 + GPU** | Local video gen | WAN 2.1, Hunyuan, CogVideo, LTX — free, offline |
| 12 | **$0 + GPU** | Local Diffusion | Stable Diffusion images — free, offline |

### Environment Variable Summary

```bash
# .env — add your keys here

# FREE (no cost, ever)
PEXELS_API_KEY=              # Stock photos + videos
PIXABAY_API_KEY=             # Stock photos + videos

# GOOGLE (one key, two tools, generous free tier)
GOOGLE_API_KEY=              # Google TTS + Google Imagen

# VOICE + MUSIC
ELEVENLABS_API_KEY=          # TTS, music, sound effects (10K chars/month free)
OPENAI_API_KEY=              # OpenAI TTS + GPT Image 2 images
XAI_API_KEY=                 # xAI Grok image generation/editing + Grok video generation
DOUBAO_SPEECH_API_KEY=       # Volcengine Doubao Speech TTS (strong Mandarin narration)
DOUBAO_SPEECH_VOICE_TYPE=    # Default Doubao speaker/voice type
DOUBAO_VISION_API_KEY=       # Volcengine Ark/Doubao vision understanding for prompt reverse
DOUBAO_VISION_MODEL=         # Doubao vision endpoint/model id configured in Ark
DOUBAO_VISION_BASE_URL=      # Optional; default https://ark.cn-beijing.volces.com/api/v3

# MULTI-MODEL GATEWAY (one key, 6+ tools)
FAL_KEY=                     # FLUX, Recraft, Seedance 2.0, Kling, Veo, MiniMax video

# VIDEO
RUNNINGHUB_API_KEY=          # RunningHub standard model API key for runninghub_seedance_video
HEYGEN_API_KEY=              # HeyGen avatar video gateway
RUNWAY_API_KEY=              # Runway Gen-4 video (direct)
REPLICATE_API_TOKEN=         # Replicate-hosted Seedance 2.0 fallback
SUNO_API_KEY=                # Suno music generation

# LOCAL (no keys needed — just GPU + install)
VIDEO_GEN_LOCAL_ENABLED=     # Set to "true" for local video gen
VIDEO_GEN_LOCAL_MODEL=       # wan2.1-1.3b, wan2.1-14b, hunyuan-1.5, ltx2-local, cogvideo-5b
```

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

### fal.ai — Multi-Model Gateway

> **Broad single-key coverage.** One API key unlocks image and video providers across multiple models.

**Tools unlocked:** `flux_image`, `recraft_image`, `seedance_video`, `kling_video`, `veo_video`, `minimax_video`
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

**Video generation:**

| Model | Price | Per $1 |
|-------|-------|--------|
| Kling 2.5 Turbo Pro | $0.07/sec | 14 seconds |
| MiniMax | ~$0.05/sec | 20 seconds |
| Veo 3 | $0.40/sec | 2.5 seconds |
| WAN 2.5 | $0.05/sec | 20 seconds |

**Free tier:** None — but $0 to start, you only pay for what you use.

---

### Seedance 2.0 — Creator Video Generation

> **Preferred premium path for creator-video scenes.** Seedance 2.0 is best when the approved scene needs real generated motion, camera direction, reference-conditioned continuity, or model-generated synced audio.

**Tools unlocked:** `runninghub_seedance_video`, `seedance_video`, `seedance_replicate`
**Env vars:** `RUNNINGHUB_API_KEY` for RunningHub, `FAL_KEY` for fal.ai, or `REPLICATE_API_TOKEN` for Replicate

#### Setup

For RunningHub:

1. Use a RunningHub enterprise/shared standard-model API key.
2. Add to `.env.local` (recommended, gitignored) or `.env`: `RUNNINGHUB_API_KEY=your-key-here`
3. The tool submits to RunningHub's `sparkvideo-2.0-mini/multimodal-video` endpoint, polls `/openapi/v2/query`, and immediately downloads the returned video URL because RunningHub result links expire.

OpenMontage limits Seedance-compatible generation to at most `15` seconds per generated clip. Users can choose any supported duration from `4` to `15` seconds. Resolution is selectable between `480p` and `720p`, with `480p` as the default. Batch planners must cap a single Seedance batch at `5` generated clips.

For fal.ai:

1. Create a fal.ai API key at [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys)
2. Add to `.env`: `FAL_KEY=your-key-here`

For Replicate:

1. Create a Replicate API token at [replicate.com/account/api-tokens](https://replicate.com/account/api-tokens)
2. Add to `.env`: `REPLICATE_API_TOKEN=your-token-here`

#### What it is best for

- Seedance-led scenes in the `creator-video` pipeline
- RunningHub-hosted creator workflows where the user has non-official Seedance-compatible access
- Text-to-video, image-to-video, and reference-conditioned video through the fal.ai path
- Cinematic creator clips where camera movement and subject continuity matter
- Dialogue-style prompts when the model should generate synchronized audio

#### Pricing

OpenMontage estimates Seedance cost from the selected gateway, variant, and selected clip duration at runtime. The current tool estimates are roughly `$0.24/sec` for fast mode and `$0.30/sec` for standard mode; check the provider dashboard before large batch runs.

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

### Doubao Vision — Reference Prompt Reverse

> **Best for Chinese short-video reference analysis.** Doubao Vision reads extracted keyframes plus transcript text and reverses each scene into editable Seedance prompts.

**Tools unlocked:** `doubao_vision_understand`, `reference_prompt_reverse`
**Env vars:** `DOUBAO_VISION_API_KEY` or `ARK_API_KEY`, plus `DOUBAO_VISION_MODEL`

#### Setup

1. Enable a Doubao visual understanding model or endpoint in Volcengine Ark.
2. Add credentials to `.env.local`:
   ```bash
   DOUBAO_VISION_API_KEY=your-api-key
   DOUBAO_VISION_MODEL=your-doubao-vision-endpoint-or-model-id
   # Optional if not using the default Ark-compatible endpoint:
   DOUBAO_VISION_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
   ```

OpenMontage calls the configured endpoint through Volcengine Ark's `/responses` API with local keyframes encoded as image data URIs. The response is required to be JSON so the package can update `visual_summary`, `camera_motion`, `pacing`, and `production_inputs.seedance_prompt`.

This is an analysis step, not production approval. Review and edit the reversed prompts before Seedance generation.

---

### Google — TTS + Imagen (Shared Key)

> **One key, two tools.** Google Cloud TTS has 700+ voices in 50+ languages — the strongest localization option. Imagen 4 generates high-quality images.

**Tools unlocked:** `google_tts`, `google_imagen`
**Env var:** `GOOGLE_API_KEY`

#### Setup

1. Go to [Google AI Studio](https://aistudio.google.com/) and sign in
2. Navigate to [aistudio.google.com/apikey](https://aistudio.google.com/apikey)
3. Click **Create API Key**, select a Google Cloud project
4. Copy the key
5. Add to `.env`: `GOOGLE_API_KEY=AIza...`

**For TTS specifically**, you also need to enable the Text-to-Speech API:
1. Visit [console.cloud.google.com/apis/library/texttospeech.googleapis.com](https://console.cloud.google.com/apis/library/texttospeech.googleapis.com)
2. Click **Enable**
3. Make sure your API key's restrictions allow the Text-to-Speech API

**For Imagen**, enable the Generative Language API:
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

**Free tier for Imagen:** None. Paid tier only.

**New account bonus:** Google Cloud offers **$300 in free credits** for new accounts (90-day trial), applicable to both TTS and Imagen.

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

### Runway — Gen-3/Gen-4 Video

> **Highest-rated AI video quality.** #1 on Elo rankings. Professional-grade video generation with Gen-3 Alpha Turbo, Gen-4 Turbo, and Gen-4 Aleph models.

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

**API pricing (approximate):**

| Model | Price per second |
|-------|-----------------|
| Gen-3 Alpha Turbo | ~$0.05 |
| Gen-4 Turbo | ~$0.05 |
| Gen-4 Aleph | ~$0.15 |

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
VIDEO_GEN_LOCAL_MODEL=wan2.1-1.3b      # 6GB+ VRAM (entry-level)
VIDEO_GEN_LOCAL_MODEL=wan2.1-14b       # 24GB+ VRAM (best local quality)
VIDEO_GEN_LOCAL_MODEL=hunyuan-1.5      # 12GB+ VRAM
VIDEO_GEN_LOCAL_MODEL=ltx2-local       # 8GB+ VRAM (fastest)
VIDEO_GEN_LOCAL_MODEL=cogvideo-5b      # 10GB+ VRAM
VIDEO_GEN_LOCAL_MODEL=cogvideo-2b      # 6GB+ VRAM (lightest)
```

#### Model Comparison

| Model | VRAM | Quality | Speed | Best for |
|-------|------|---------|-------|----------|
| **WAN 2.1 (1.3B)** | 6GB | Good | Fast | Entry-level GPU, quick iteration |
| **WAN 2.1 (14B)** | 24GB | Excellent | Slow | Best quality-to-VRAM ratio |
| **Hunyuan 1.5** | 12GB | Very good | Medium | Mid-range GPUs |
| **LTX-2** | 8GB | Good | Fastest | Quick drafts, lowest latency |
| **CogVideo (5B)** | 10GB | Good | Medium | Balanced option |
| **CogVideo (2B)** | 6GB | Fair | Fast | Low-VRAM experimentation |

**All local models support:** Image-to-video, text-to-video, offline generation, seeded reproducibility.

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

`faster-whisper` also needs the selected Whisper model cached locally on first real run. If the machine is offline before that cache exists, OpenMontage now keeps the reference-analysis pipeline running and marks the transcript as `pending_transcription` with reason `transcriber_model_download_required`.

### Reference Video Analysis Package

**Tools:** `reference_video_package`, `reference_prompt_reverse`, `reference_text_edit`, `reference_asset_binding`, `reference_review_approval`, `reference_production_plan`, `seedance_batch`, `video_stitch`
**Pipeline:** `reference-video-analysis`
**Runtime:** Local, analysis-only

Use this workflow when a creator provides a Douyin link or local video as a reference. The MVP produces a human-editable replication package with transcript, rewrite draft, scene table, keyframes, pacing notes, and a Seedance-only v1 downstream mode. Each scene also exposes editable production inputs for script text, Seedance prompt drafts, and user-uploaded asset slots.

The pipeline tries URL ingestion first when a supported downloader can access the link. If Douyin blocks download because of login, region, watermark handling, or platform protection, it stops cleanly and asks for a local file path. It must not bypass platform access controls.

Start by analyzing either a video URL or a local video file:

```bash
.venv/bin/python scripts/analyze_reference_video.py \
  "https://v.douyin.com/<share-id>/" \
  --project-dir projects/<project>
```

```bash
.venv/bin/python scripts/analyze_reference_video.py \
  /path/to/reference-video.mp4 \
  --project-dir projects/<project>
```

If URL ingestion is blocked, the command exits with code `3` and prints a structured fallback payload with `fallback_required: "local_video_file"`. Download the team-authorized video manually, then rerun the local-file command above.

For the safest one-command preview, use the wrapper below. By default it analyzes the source, writes the editable package, prints the next commands, and stops before any paid or downstream generation:

```bash
.venv/bin/python scripts/reference_preview_pipeline.py \
  "https://v.douyin.com/<share-id>/" \
  --project-dir projects/<project>
```

Add `--reverse-prompts` only when you explicitly want to call the configured vision provider, such as Doubao, to enrich Seedance prompts from keyframes:

```bash
.venv/bin/python scripts/reference_preview_pipeline.py \
  /path/to/reference-video.mp4 \
  --project-dir projects/<project> \
  --reverse-prompts \
  --provider doubao
```

For an end-to-end local demo handoff, use the one-command runner. It runs reference analysis, optionally reverses prompts, writes the guided demo report, and stops at the human-edit gate. By default it does not call Doubao or any paid video-generation provider:

```bash
.venv/bin/python scripts/run_reference_local_demo.py \
  /path/to/reference-video.mp4 \
  --project-dir projects/<project>
```

Before a live demo or first real sample, you can run the same readiness check by itself. It validates the local source path, output directory, FFmpeg/FFprobe, and whether optional Doubao/Seedance keys are configured. It reports only env var names and never prints secret values:

```bash
.venv/bin/python scripts/reference_demo_preflight.py \
  /path/to/reference-video.mp4 \
  --project-dir projects/<project>
```

Use `--reverse-prompts --provider doubao` only when you want the configured Doubao Vision API to enrich editable Seedance prompts. The runner still does not approve production, call Seedance, or export a final video:

```bash
.venv/bin/python scripts/run_reference_local_demo.py \
  /path/to/reference-video.mp4 \
  --project-dir projects/<project> \
  --reverse-prompts \
  --provider doubao
```

To resume a half-finished reference project, inspect the project directory. This command is local-only and prints the current artifact, approval state, and safest next command:

```bash
.venv/bin/python scripts/reference_project_status.py \
  projects/<project>
```

For a web dashboard or desktop client, use the snapshot command instead of parsing individual artifact files. It returns a stable JSON envelope with phase, status, latest artifact paths, media paths, delivery info, next actions, UI action metadata, and safety flags. It never prints API key values:

```bash
.venv/bin/python scripts/reference_project_snapshot.py \
  projects/<project>
```

The local console exposes the same safe contract over HTTP. It can create a reference project and import an existing local video file before analysis:

- `POST /api/reference/projects/create` with `project_name`
- `POST /api/reference/projects/import-source` with `project_dir` and `source_path`
- `GET /api/reference/state?project_dir=...` for the current phase and safe UI actions
- `POST /api/reference/actions/prepare` for confirmation-gated command preparation
- `POST /api/reference/actions/execute` for safe local-only actions such as analysis or dry-run preparation
- `GET /api/reference/jobs/status?project_dir=...&job_id=...` for tracked job status and log paths
- `GET /api/reference/jobs/list?project_dir=...` for recent project jobs; the console refreshes this list and polls running jobs after execution

Use `ui_actions[]` to render buttons safely. Each action includes `risk`, `paid_generation`, `requires_confirmation`, `can_execute`, `execution_mode`, `disabled_reason`, `execution_note`, `operator_guidance`, and `confirmation_phrase`; frontends should render `operator_guidance.summary`, `operator_guidance.next_step`, and the provided button labels instead of inferring copy from raw risk names. Require the exact phrase before enabling paid generation, approval, or delivery export actions. A successful prepare response may include a raw shell `command`; show it only after confirmation and offer copy/download helpers for manual terminal execution. The execute endpoint refuses paid generation, final delivery export, production approval, and manual-review actions with a machine-readable `blocked_reason`; those remain prepare-only or manual-review only.

To smoke-test that contract locally without opening a browser or calling paid providers, run:

```bash
.venv/bin/python scripts/reference_console_smoke.py \
  /path/to/reference-video.mp4 \
  --project-name reference-console-smoke
```

The smoke script calls the same local API router for health, console HTML loading, project creation, source import, safe action execution, job polling, and job listing. It checks that the console page includes the guidance renderer plus copy/download helpers for prepared commands, only executes `can_execute` local actions, and strips raw shell commands from its JSON output. The result includes machine-readable `steps[]`, `failure_stage`, and `recommended_action` fields so CI or a web client can show exactly where setup failed.

To exercise the real loopback HTTP server instead of the in-process router, add `--server-mode http`; this binds a local port and may require local-network permission on locked-down systems:

```bash
.venv/bin/python scripts/reference_console_smoke.py \
  /path/to/reference-video.mp4 \
  --project-name reference-console-smoke \
  --server-mode http \
  --port 0
```

When a package has edited copy/prompts or bound team assets, the status command recommends `preview_reference_approval.py` before `approve_reference_package.py`. This keeps the final review local-only until the package has valid script text, Seedance prompts, authorized selected assets, at least one selected team-authorized face/presenter reference when likeness replacement is required, and locked Seedance defaults (`15s`, `480p`, batch size `1`). Once a final-edit plan is `ready_for_compose`, the status command recommends a dry-run first, then a formal compose command with `--burn-subtitles`; it also adds `--mix-audio` automatically when the plan declares valid local `compose_handoff.audio_tracks`. After a rendered report and final MP4 exist, the status becomes `final_render_ready` and prompts human playback review before distribution.

For a guided local review loop, use the wizard. Without an edit sheet it exports the current package's editable JSON template; with `--edit-sheet` it validates the sheet, applies local text/asset edits, and previews approval readiness. It never writes an approved package and never calls paid generation:

```bash
.venv/bin/python scripts/reference_review_wizard.py \
  projects/<project>
```

```bash
.venv/bin/python scripts/reference_review_wizard.py \
  projects/<project> \
  --edit-sheet projects/<project>/artifacts/reference-edit-sheets/<reference>-edit-sheet.json \
  --duration 15 \
  --resolution 480p \
  --batch-size 1
```

For stakeholder demos, generate a readable local report from the current project state. If the package is not approved, the report exports/links the edit sheet and marks Seedance dry-run as blocked until approval. If the package is approved, it also writes a local Seedance production plan, dry-run task list, and final-edit missing-clip report. It still never calls paid providers:

```bash
.venv/bin/python scripts/reference_demo_report.py \
  projects/<project> \
  --duration 15 \
  --resolution 480p \
  --batch-size 1 \
  --provider runninghub
```

For batch human edits, export a local JSON edit-sheet template from the current pending package:

```bash
.venv/bin/python scripts/export_reference_edit_sheet.py \
  projects/<project>/artifacts/reference-prompts/<reference>-prompts-reversed-package.json \
  --project-dir projects/<project>
```

The exported sheet includes current global copy, per-scene script/prompt fields, and asset placeholders. Your team can edit that JSON directly. The editable format accepts any combination of global copy, per-scene script/prompt edits, and team-authorized assets:

```json
{
  "rewrite_text": "人工确认后的复刻文案",
  "scene_edits": [
    {
      "scene_id": "s1",
      "script_text": "前三秒提出痛点，然后给出解决方案。",
      "seedance_prompt": "竖屏近景口播，干净背景，轻微推近。"
    }
  ],
  "assets": [
    {
      "path": "/path/to/team-face.png",
      "scene_id": "s1",
      "id": "face-ref",
      "role": "subject_or_face_reference",
      "authorized": true
    }
  ]
}
```

After editing, validate the sheet before applying it. This local preflight checks scene IDs, asset paths, and `authorized: true` without writing artifacts:

```bash
.venv/bin/python scripts/apply_reference_edit_sheet.py \
  projects/<project>/artifacts/reference-prompts/<reference>-prompts-reversed-package.json \
  --project-dir projects/<project> \
  --edit-sheet /path/to/edit-sheet.json \
  --validate-only
```

Then apply the edit sheet in one local command. This still does not approve production or call paid providers:

```bash
.venv/bin/python scripts/apply_reference_edit_sheet.py \
  projects/<project>/artifacts/reference-prompts/<reference>-prompts-reversed-package.json \
  --project-dir projects/<project> \
  --edit-sheet /path/to/edit-sheet.json
```

If Doubao Vision is configured, reverse-engineer editable Seedance prompts from keyframes before manual edits:

```bash
.venv/bin/python scripts/reverse_reference_prompts.py \
  projects/<project>/artifacts/<reference>-replication-package.json \
  --project-dir projects/<project> \
  --provider doubao
```

Before approval, edit replicated copy and generated Seedance prompts without manually changing JSON. Repeat `--scene-edit` for multiple scenes; the tuple is `SCENE_ID SCRIPT_TEXT SEEDANCE_PROMPT`:

```bash
.venv/bin/python scripts/edit_reference_package.py \
  projects/<project>/artifacts/reference-prompts/<reference>-prompts-reversed-package.json \
  --project-dir projects/<project> \
  --rewrite-text "人工修改后的复刻文案" \
  --scene-edit s1 "人工确认后的场景脚本" "竖屏产品口播，人物面向镜头，干净背景"
```

Then bind any team-owned reference images or product assets into the edited package. Repeat `--asset` for multiple files; the tuple is `PATH SCENE_ID ROLE ASSET_ID`:

```bash
.venv/bin/python scripts/bind_reference_assets.py \
  projects/<project>/artifacts/reference-edits/<reference>-text-edited-package.json \
  --project-dir projects/<project> \
  --asset /path/to/team-face.png s1 subject_or_face_reference face-ref \
  --authorized
```

Before approval, preview the approval readiness summary. This is local-only and does not write an approved package:

```bash
.venv/bin/python scripts/preview_reference_approval.py \
  projects/<project>/artifacts/reference-assets/<reference>-assets-bound-package.json \
  --project-dir projects/<project> \
  --target-mode seedance \
  --duration 15 \
  --resolution 480p \
  --batch-size 1
```

After a human edits the JSON package and binds any needed assets, approve a copied handoff package with an explicit review phrase. This does not start paid generation:

```bash
.venv/bin/python scripts/approve_reference_package.py \
  projects/<project>/artifacts/reference-assets/<reference>-assets-bound-package.json \
  --project-dir projects/<project> \
  --target-mode seedance \
  --reviewer operator \
  --approval-phrase "APPROVE REFERENCE PACKAGE"
```

Then prepare a local production handoff from the approved package:

```bash
.venv/bin/python scripts/prepare_reference_production.py \
  projects/<project>/artifacts/reference-review/<reference>-seedance-approved-package.json \
  --project-dir projects/<project> \
  --duration 15 \
  --resolution 480p \
  --batch-size 1
```

This workflow does not replace faces, call digital-human APIs, run paid Seedance generation, or publish outputs during analysis/review. Reference-video v1 downstream production is Seedance-only, requires human review, and requires at least one selected team-authorized face/presenter asset when the package declares `requires_team_authorized_face_or_avatar: true`. The production handoff enforces Seedance constraints: `4`-`15` seconds per clip, `480p` or `720p`, and maximum batch size `5`.

To prepare both the production handoff and Seedance dry-run preview in one local step:

```bash
.venv/bin/python scripts/preview_reference_seedance.py \
  projects/<project>/artifacts/reference-review/<reference>-seedance-approved-package.json \
  --project-dir projects/<project> \
  --duration 15 \
  --resolution 480p \
  --batch-size 1 \
  --provider runninghub
```

This preview command still does not call any paid provider. It only writes a production plan JSON and a Seedance dry-run task-list JSON.

If the production handoff already exists, generate only the dry-run Seedance task list:

```bash
.venv/bin/python scripts/plan_seedance_batch.py \
  projects/<project>/artifacts/<reference>-seedance-production-plan.json \
  --project-dir projects/<project> \
  --provider runninghub
```

The dry-run task list records provider tool, prompt, duration, resolution, reference image paths, and output paths for the first batch only. It does not call RunningHub, fal.ai, Replicate, or any paid video-generation API.

Before spending on generation, preview the final-edit readiness plan from the dry-run task list. This writes a timeline, expected clip paths, subtitle text handoff, and a missing-clip checklist. It does not render the final video:

```bash
.venv/bin/python scripts/preview_reference_final_edit.py \
  projects/<project>/artifacts/<reference>-seedance-batch-dry-run.json \
  --project-dir projects/<project>
```

Before burning subtitles, optionally create a reviewable subtitle-polish plan. The default path is a dry run: it uses the local口播字幕 planner, writes `artifacts/reference-subtitles/<reference>-subtitle-polish-plan.json`, includes the exact Doubao prompt that would be sent, and does not call Doubao or any paid API:

```bash
.venv/bin/python scripts/polish_reference_subtitles.py \
  projects/<project>/artifacts/reference-final-edit/<reference>-final-edit-plan.json \
  --project-dir projects/<project>
```

Only after explicitly approving a paid Doubao/Ark subtitle-polish call, run live mode with both switches. Doubao returns cue text only; OpenMontage still allocates timestamps locally before SRT/render:

```bash
.venv/bin/python scripts/polish_reference_subtitles.py \
  projects/<project>/artifacts/reference-final-edit/<reference>-final-edit-plan.json \
  --project-dir projects/<project> \
  --live \
  --allow-paid-api
```

Once the final-edit plan status is `ready_for_compose`, run a local compose dry-run first. This writes a render report under `artifacts/reference-render/`, creates an SRT sidecar from `timeline[].subtitle_text`, validates any declared `compose_handoff.audio_tracks`, records the encoding quality profile, and does not create the final MP4. The default quality is `high` (`CRF 18`) so subtitle burn-in and mux steps keep more upload headroom than the legacy `standard` profile (`CRF 23`):

```bash
.venv/bin/python scripts/compose_reference_final.py \
  projects/<project>/artifacts/reference-final-edit/<reference>-final-edit-plan.json \
  --project-dir projects/<project> \
  --dry-run
```

If a subtitle-polish plan has been reviewed, pass it into compose so the SRT uses the polished cue list instead of raw `timeline[].subtitle_text`:

```bash
.venv/bin/python scripts/compose_reference_final.py \
  projects/<project>/artifacts/reference-final-edit/<reference>-final-edit-plan.json \
  --project-dir projects/<project> \
  --subtitle-polish-plan artifacts/reference-subtitles/<reference>-subtitle-polish-plan.json \
  --dry-run
```

After confirming the report, compose the ready clips locally with FFmpeg-backed `video_stitch`. Add `--burn-subtitles` to burn the generated SRT into the final MP4. Add `--mix-audio` when `compose_handoff.audio_tracks` contains validated narration/music/SFX paths; OpenMontage will run `audio_mixer` first, then mux the mixed audio into the final video:

```bash
.venv/bin/python scripts/compose_reference_final.py \
  projects/<project>/artifacts/reference-final-edit/<reference>-final-edit-plan.json \
  --project-dir projects/<project> \
  --burn-subtitles
```

Use `--quality standard` only for small draft files. Use `--quality master` (`CRF 16`) for archival exports when larger files are acceptable:

```bash
.venv/bin/python scripts/compose_reference_final.py \
  projects/<project>/artifacts/reference-final-edit/<reference>-final-edit-plan.json \
  --project-dir projects/<project> \
  --burn-subtitles \
  --quality master
```

```bash
.venv/bin/python scripts/compose_reference_final.py \
  projects/<project>/artifacts/reference-final-edit/<reference>-final-edit-plan.json \
  --project-dir projects/<project> \
  --burn-subtitles \
  --mix-audio
```

After playing the final MP4 and confirming business approval, export a local delivery package. This copies the final video, render report, final-edit plan, subtitles, and optional mixed audio into `deliveries/<final-video-name>/`, then writes `delivery-manifest.json` and `README.md` for upload/archive handoff:

```bash
.venv/bin/python scripts/export_reference_delivery.py \
  projects/<project> \
  --render-report projects/<project>/artifacts/reference-render/<reference>-render-report.json \
  --reviewer operator \
  --approval-phrase "APPROVE FINAL DELIVERY"
```

The delivery export is local-only and does not call paid providers. The explicit approval phrase is required so a rendered draft is not accidentally treated as distributable.

To run exactly one paid sample after reviewing the dry-run task list, use both approval flags and the confirmation phrase:

```bash
.venv/bin/python scripts/plan_seedance_batch.py \
  projects/<project>/artifacts/<reference>-seedance-production-plan.json \
  --project-dir projects/<project> \
  --provider runninghub \
  --execute \
  --allow-paid-generation \
  --approval-phrase "RUN SEEDANCE SAMPLE"
```

This sample path executes only the first planned Seedance task. Review the generated clip before approving any remaining batch items.

---

## Provider-to-Tool Mapping

| Provider | Env Var | Tools Unlocked | Cost |
|----------|---------|---------------|------|
| **Pexels** | `PEXELS_API_KEY` | `pexels_image`, `pexels_video` | Free |
| **Pixabay** | `PIXABAY_API_KEY` | `pixabay_image`, `pixabay_video` | Free |
| **Piper** | — (install only) | `piper_tts` | Free |
| **Google** | `GOOGLE_API_KEY` | `google_tts`, `google_imagen` | Free tier + paid |
| **ElevenLabs** | `ELEVENLABS_API_KEY` | `elevenlabs_tts`, `music_gen` | Free tier + paid |
| **fal.ai** | `FAL_KEY` | `flux_image`, `recraft_image`, `kling_video`, `veo_video`, `minimax_video` | Pay-as-you-go |
| **OpenAI** | `OPENAI_API_KEY` | `openai_tts`, `openai_image` | Paid only |
| **xAI** | `XAI_API_KEY` | `grok_image`, `grok_video` | Paid only |
| **Runway** | `RUNWAY_API_KEY` | `runway_video` | Free trial + paid |
| **Higgsfield** | `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET` | `higgsfield_video` | Subscription ($15-84/mo) |
| **HeyGen** | `HEYGEN_API_KEY` | `heygen_video` | Pay-as-you-go |
| **Suno** | `SUNO_API_KEY` | `suno_music` | Pay-as-you-go |
| **Local GPU** | `VIDEO_GEN_LOCAL_ENABLED` | `wan_video`, `hunyuan_video`, `cogvideo_video`, `ltx_video_local` | Free (GPU required) |
| **Local Diffusion** | — (install only) | `local_diffusion` | Free (GPU required) |
| **Modal** | `MODAL_LTX2_ENDPOINT_URL` | `ltx_video_modal` | Self-hosted cloud |

---

## Capability Coverage

How many providers cover each capability:

| Capability | Cloud Providers | Local Providers | Free Options |
|-----------|----------------|-----------------|--------------|
| **Image Generation** | FLUX, Grok, Google Imagen, GPT Image 2, Recraft | Local Diffusion | Pexels, Pixabay (stock) |
| **Video Generation** | Grok, Kling, Runway, Veo, Higgsfield, MiniMax, HeyGen | WAN, Hunyuan, CogVideo, LTX | Pexels, Pixabay (stock) |
| **Text-to-Speech** | ElevenLabs, Google TTS, OpenAI | Piper | Piper, Google free tier, ElevenLabs free tier |
| **Music Generation** | ElevenLabs, Suno | — | ElevenLabs free tier |
| **Post-Production** | — | FFmpeg (compose, stitch, trim, mix, enhance, grade) | All free |
| **Analysis** | — | WhisperX, Scene Detect, Frame Sampler, CLIP/BLIP-2 | All free |
| **Enhancement** | — | Upscale, BG Remove, Face Enhance, Face Restore | All free |
| **Avatar** | — | SadTalker, Wav2Lip | All free |

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
