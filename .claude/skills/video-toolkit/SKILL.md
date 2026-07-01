---
name: video-toolkit
description: Create professional videos autonomously using claude-code-video-toolkit — AI voiceovers, image generation, music, talking heads, and Remotion rendering.
metadata:
  openclaw:
    emoji: "🎬"
    skillKey: "video-toolkit"
    os: ["darwin", "linux"]
    requires:
      bins: ["node", "python3", "ffmpeg", "npm"]
---

# Video Toolkit

Create professional explainer videos from a text brief. The toolkit uses open-source AI models on cloud GPUs (Modal or RunPod) for voiceover, image generation, music, and talking head animation. Remotion (React) handles composition and rendering.

## CRITICAL: Toolkit Path

The toolkit lives at a fixed path. **ALWAYS `cd` here before running any tool command.**

```bash
TOOLKIT=~/.openclaw/workspace/claude-code-video-toolkit
cd $TOOLKIT
```

**NEVER run tool commands from inside a project directory.** Tools resolve paths relative to the toolkit root.

## Setup

### Step 1: Check Current State

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/verify_setup.py
```

If everything shows `[x]`, skip to "Quick Test" below. Otherwise continue setup.

### Step 2: Install Python Dependencies

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
pip3 install --break-system-packages -r tools/requirements.txt
```

Note: `--break-system-packages` is needed on Debian/Ubuntu with managed Python (PEP 668). Safe inside containers.

### Step 3: Configure Cloud GPU Endpoints

The toolkit needs cloud GPU endpoint URLs in `.env`. Check if `.env` exists and has Modal endpoints:

```bash
cat ~/.openclaw/workspace/claude-code-video-toolkit/.env | grep MODAL
```

If Modal endpoints are configured, you're ready. If not, **ask the user to provide Modal endpoint URLs** or set up Modal:

```bash
pip3 install --break-system-packages modal
python3 -m modal setup   # Opens browser for authentication

# Deploy each tool — capture the endpoint URL from output
cd ~/.openclaw/workspace/claude-code-video-toolkit
modal deploy docker/modal-qwen3-tts/app.py
modal deploy docker/modal-flux2/app.py
modal deploy docker/modal-music-gen/app.py
modal deploy docker/modal-sadtalker/app.py
modal deploy docker/modal-image-edit/app.py
modal deploy docker/modal-upscale/app.py
modal deploy docker/modal-propainter/app.py
modal deploy docker/modal-ltx2/app.py      # Requires: modal secret create huggingface-token HF_TOKEN=hf_...
```

**LTX-2 prerequisite:** Before deploying LTX-2, create a HuggingFace secret and accept the [Gemma 3 license](https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-unquantized):
```bash
modal secret create huggingface-token HF_TOKEN=hf_your_read_access_token
```

Add each URL to `.env`:
```
MODAL_QWEN3_TTS_ENDPOINT_URL=https://...modal.run
MODAL_FLUX2_ENDPOINT_URL=https://...modal.run
MODAL_MUSIC_GEN_ENDPOINT_URL=https://...modal.run
MODAL_SADTALKER_ENDPOINT_URL=https://...modal.run
MODAL_IMAGE_EDIT_ENDPOINT_URL=https://...modal.run
MODAL_UPSCALE_ENDPOINT_URL=https://...modal.run
MODAL_DEWATERMARK_ENDPOINT_URL=https://...modal.run
MODAL_LTX2_ENDPOINT_URL=https://...modal.run
```

Optional but recommended — Cloudflare R2 for reliable file transfer:
```
R2_ACCOUNT_ID=...
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=video-toolkit
```

### Step 4: Verify and Quick Test

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/verify_setup.py
```

All tools should show `[x]`. Then run a quick test to confirm the GPU pipeline works:

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/qwen3_tts.py --text "Hello, this is a test." --speaker Ryan --tone warm --output /tmp/video-toolkit-test.mp3 --cloud modal
```

If you get a valid .mp3 file, setup is complete. If it fails, check:
- `.env` has the correct `MODAL_QWEN3_TTS_ENDPOINT_URL`
- Run `python3 tools/verify_setup.py --json` and check `modal_tools` for which endpoints are missing

**Cost:** Modal includes $30/month free compute. A typical 60s video costs $1-3.

---

## Creating a Video

### Step 1: Create Project

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
cp -r templates/product-demo projects/PROJECT_NAME
cd projects/PROJECT_NAME
npm install
```

Templates: `product-demo` (marketing/explainer), `sprint-review`, `sprint-review-v2` (composable scenes).

### Step 2: Write Config

Edit `projects/PROJECT_NAME/src/config/demo-config.ts`:

```typescript
export const demoConfig: ProductDemoConfig = {
  product: {
    name: 'My Product',
    tagline: 'What it does in one line',
    website: 'example.com',
  },
  scenes: [
    { type: 'title', durationSeconds: 9, content: { headline: '...', subheadline: '...' } },
    { type: 'problem', durationSeconds: 14, content: { headline: '...', problems: ['...', '...'] } },
    { type: 'solution', durationSeconds: 13, content: { headline: '...', highlights: ['...', '...'] } },
    { type: 'stats', durationSeconds: 12, content: { stats: [{value: '99%', label: '...'}, ...] } },
    { type: 'cta', durationSeconds: 10, content: { headline: '...', links: ['...'] } },
  ],
  audio: {
    backgroundMusicFile: 'audio/bg-music.mp3',
    backgroundMusicVolume: 0.12,
  },
};
```

Scene types: `title`, `problem`, `solution`, `demo`, `feature`, `stats`, `cta`.

**Duration rule:** Estimate `durationSeconds` as `ceil(word_count / 2.5) + 2`. You will adjust this after generating audio in Step 4.

### Step 3: Write Voiceover Script

Create `projects/PROJECT_NAME/VOICEOVER-SCRIPT.md`:

```markdown
## Scene 1: Title (9s, ~17 words)
Build videos with AI. The product name toolkit makes it easy.

## Scene 2: Problem (14s, ~30 words)
The problem statement goes here. Keep it punchy and relatable.
```

**Word budget per scene:** `(durationSeconds - 2) * 2.5` words. The -2 accounts for 1s audio delay + 1s padding.

### Step 4: Generate Assets

**CRITICAL: All commands below MUST be run from the toolkit root, not the project directory.**

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
```

#### 4a. Background Music

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/music_gen.py \
  --preset corporate-bg \
  --duration 90 \
  --output projects/PROJECT_NAME/public/audio/bg-music.mp3 \
  --cloud modal
```

Presets: `corporate-bg`, `upbeat-tech`, `ambient`, `dramatic`, `tension`, `hopeful`, `cta`, `lofi`.

#### 4b. Voiceover (per-scene)

Generate ONE .mp3 file PER SCENE. Do NOT generate a single voiceover file.

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit

# Scene 01
python3 tools/qwen3_tts.py \
  --text "The voiceover text for scene one." \
  --speaker Ryan --tone warm \
  --output projects/PROJECT_NAME/public/audio/scenes/01.mp3 \
  --cloud modal

# Scene 02
python3 tools/qwen3_tts.py \
  --text "The voiceover text for scene two." \
  --speaker Ryan --tone warm \
  --output projects/PROJECT_NAME/public/audio/scenes/02.mp3 \
  --cloud modal

# ... repeat for each scene
```

**Speakers:** `Ryan`, `Aiden`, `Vivian`, `Serena`, `Uncle_Fu`, `Dylan`, `Eric`, `Ono_Anna`, `Sohee`
**Tones:** `neutral`, `warm`, `professional`, `excited`, `calm`, `serious`, `storyteller`, `tutorial`

For voice cloning (needs a reference recording):
```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/qwen3_tts.py \
  --text "Text to speak" \
  --ref-audio assets/voices/reference.m4a \
  --ref-text "Exact transcript of the reference audio" \
  --output projects/PROJECT_NAME/public/audio/scenes/01.mp3 \
  --cloud modal
```

#### 4c. Scene Images

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/flux2.py \
  --prompt "Dark tech background with blue geometric grid, cinematic lighting" \
  --width 1920 --height 1080 \
  --output projects/PROJECT_NAME/public/images/title-bg.png \
  --cloud modal
```

Image presets (use `--preset` instead of `--prompt --width --height`):
`title-bg`, `problem`, `solution`, `demo-bg`, `stats-bg`, `cta`, `thumbnail`, `portrait-bg`

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/flux2.py \
  --preset title-bg \
  --output projects/PROJECT_NAME/public/images/title-bg.png \
  --cloud modal
```

#### 4d. Video Clips — B-Roll & Animated Backgrounds (optional)

Generate AI video clips for b-roll cutaways, animated slide backgrounds, or intro/outro sequences:

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit

# B-roll clip from text
python3 tools/ltx2.py \
  --prompt "Aerial drone shot over a European city at golden hour, cinematic wide angle" \
  --output projects/PROJECT_NAME/public/videos/broll-europe.mp4 \
  --cloud modal

# Animate a slide/screenshot (image-to-video)
python3 tools/ltx2.py \
  --prompt "Gentle particle effects, soft ambient light shifts, very slight camera drift" \
  --input projects/PROJECT_NAME/public/images/title-bg.png \
  --output projects/PROJECT_NAME/public/videos/animated-title.mp4 \
  --cloud modal

# Abstract intro/outro background
python3 tools/ltx2.py \
  --prompt "Dark moody abstract background with flowing blue light streaks, bokeh particles, cinematic" \
  --output projects/PROJECT_NAME/public/videos/intro-bg.mp4 \
  --cloud modal
```

Use in Remotion compositions with `<OffthreadVideo>`:
```tsx
<OffthreadVideo src={staticFile('videos/broll-europe.mp4')} />
```

**LTX-2 rules:**
- Max ~8 seconds per clip (193 frames at 24fps). Default is ~5s (121 frames).
- Width/height must be divisible by 64. Default: 768x512.
- ~$0.20-0.25 per clip, ~2.5 min generation time.
- Cold start ~60-90s. Subsequent clips on warm GPU are faster.
- Generated audio is ambient only — use voiceover/music tools for speech and music.
- ~30% of generations may have training data artifacts (logos/text). Re-run with `--seed` to vary.

#### 4e. Talking Head Narrator (optional)

Generate a presenter portrait, then animate per-scene clips:

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit

# 1. Generate portrait
python3 tools/flux2.py \
  --prompt "Professional presenter portrait, clean style, dark background, facing camera, upper body" \
  --width 1024 --height 576 \
  --output projects/PROJECT_NAME/public/images/presenter.png \
  --cloud modal

# 2. Generate per-scene narrator clips (one per scene, NOT one long video)
python3 tools/sadtalker.py \
  --image projects/PROJECT_NAME/public/images/presenter.png \
  --audio projects/PROJECT_NAME/public/audio/scenes/01.mp3 \
  --preprocess full --still --expression-scale 0.8 \
  --output projects/PROJECT_NAME/public/narrator-01.mp4 \
  --cloud modal

# Repeat for each scene that needs a narrator
```

**SadTalker rules — follow these exactly:**
- **ALWAYS** use `--preprocess full` (default `crop` outputs a square, wrong aspect ratio)
- **ALWAYS** use `--still` (reduces head movement, looks professional)
- **ALWAYS** generate per-scene clips (6-15s each), NEVER one long video
- Processing: ~3-4 min per 10s of audio on Modal A10G
- `--expression-scale 0.8` keeps expressions subtle (range 0.0-1.5)

#### 4e. Image Editing (optional)

Create scene variants from existing images:

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/image_edit.py \
  --input projects/PROJECT_NAME/public/images/title-bg.png \
  --prompt "Make it darker with red tones, more ominous" \
  --output projects/PROJECT_NAME/public/images/problem-bg.png \
  --cloud modal
```

#### 4f. Upscaling (optional)

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
python3 tools/upscale.py \
  --input projects/PROJECT_NAME/public/images/some-image.png \
  --output projects/PROJECT_NAME/public/images/some-image-4x.png \
  --scale 4 --cloud modal
```

### Step 5: Sync Timing

**ALWAYS do this after generating voiceover.** Audio duration differs from estimates.

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit
for f in projects/PROJECT_NAME/public/audio/scenes/*.mp3; do
  echo "$(basename $f): $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")s"
done
```

Update each scene's `durationSeconds` in `demo-config.ts` to: `ceil(actual_audio_duration + 2)`.

Example: if `01.mp3` is 6.8s, set scene 1 `durationSeconds` to `9` (ceil(6.8 + 2) = 9).

### Step 6: Review Still Frames

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit/projects/PROJECT_NAME
npx remotion still src/index.ts ProductDemo --frame=100 --output=/tmp/review-scene1.png
npx remotion still src/index.ts ProductDemo --frame=400 --output=/tmp/review-scene2.png
```

Check: text truncation, animation timing, narrator PiP positioning, background contrast.

### Step 7: Render

```bash
cd ~/.openclaw/workspace/claude-code-video-toolkit/projects/PROJECT_NAME
npm run render
```

**Output:** `out/ProductDemo.mp4`

---

## Composition Patterns

### Per-Scene Audio

Use per-scene audio with a 1-second delay (`from={30}` = 30 frames = 1s at 30fps):

```tsx
<Sequence from={30}>
  <Audio src={staticFile('audio/scenes/01.mp3')} volume={1} />
</Sequence>
```

### Per-Scene Narrator PiP

```tsx
<Sequence from={30}>
  <OffthreadVideo
    src={staticFile('narrator-01.mp4')}
    style={{ width: 320, height: 180, objectFit: 'cover' }}
    muted
  />
</Sequence>
```

**ALWAYS use `<OffthreadVideo>`, NEVER `<video>`.** Remotion requires its own component for frame-accurate rendering.

### Transitions

```tsx
import { TransitionSeries, linearTiming } from '@remotion/transitions';
import { fade } from '@remotion/transitions/fade';
import { glitch } from '../../../lib/transitions/presentations/glitch';
import { lightLeak } from '../../../lib/transitions/presentations/light-leak';
```

**NEVER import from `lib/transitions` barrel** — import custom transitions from `lib/transitions/presentations/` directly.

---

## Error Recovery

| Problem | Solution |
|---------|----------|
| Tool command fails with "No module named..." | Run `pip3 install --break-system-packages -r tools/requirements.txt` from toolkit root |
| "MODAL_*_ENDPOINT_URL not configured" | Check `.env` has the endpoint URL. Run `python3 tools/verify_setup.py` |
| SadTalker output is square/cropped | You forgot `--preprocess full`. Re-run with that flag |
| Audio too short/long for scene | Re-run Step 5 (sync timing) and update config |
| `npm run render` fails | Make sure you're in the project dir, not toolkit root. Run `npm install` first |
| "Cannot find module" in Remotion | Check import paths. Custom components use `../../../lib/` relative paths |
| Cold start timeout on Modal | First call after idle takes 30-120s. Retry once — second call uses warm GPU |

---

## Cost Estimates (Modal)

| Tool | Typical Cost | Notes |
|------|-------------|-------|
| Qwen3-TTS | ~$0.01/scene | ~20s per scene on warm GPU |
| FLUX.2 | ~$0.01/image | ~3s warm, ~30s cold |
| ACE-Step | ~$0.02-0.05 | Depends on duration |
| SadTalker | ~$0.05-0.20/scene | ~3-4 min per 10s audio |
| Qwen-Edit | ~$0.03-0.15 | ~8 min cold start (25GB model) |
| RealESRGAN | ~$0.005/image | Very fast |
| LTX-2.3 | ~$0.20-0.25/clip | ~2.5 min per 5s clip, A100-80GB |

**Total for a 60s video:** ~$1-3 depending on scenes and narrator clips.

Modal Starter plan: $30/month free compute. Apps scale to zero when idle.
