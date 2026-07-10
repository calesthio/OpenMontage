---
name: ltx2
description: AI video generation with LTX-2.3 22B — text-to-video, image-to-video clips for video production. Use when generating video clips, animating images, creating b-roll, animated backgrounds, or motion content. Triggers include video generation, animate image, b-roll, motion, video clip, text-to-video, image-to-video.
---

# LTX-2.3 Video Generation

Generate ~5 second video clips from text prompts or images using the LTX-2.3 22B DiT model.
Runs on Modal (A100-80GB). Requires `MODAL_LTX2_ENDPOINT_URL` in `.env`.

### MaaS Gateway Route

The same LTX-2.3 22B model is also reachable via `tools/video/maas_video.py` as
model `leapfast/ltx-2.3` (billed in CNY through the internal MaaS gateway,
`best_for` lists it as "LTX-2.3 via self-hosted H100 GPU cluster"). Calling it
that way uses `MaasVideo.execute({...})`, not the `tools/ltx2.py` CLI shown
below — but the model behavior does carry over: the **Prompting Guide**,
**Known Limitations**, and CJK note further down all apply regardless of
which path you're calling through. `image_to_video` **is** supported through
this route (confirmed live 2026-07-10 — submit → succeeded, output correctly
conditioned on the reference frame; `MaasVideo.MODELS["leapfast/ltx-2.3"]
["ops"]` includes `"i2v"`) — pass `image_url`/`image_base64` plus
`image_strength` as usual. `maas_video.execute()` still validates operation
against each model's declared `ops` before spending money on any model where
that assumption doesn't hold — don't route around that check by guessing a
model secretly supports more than it declares; if you find another gap, fix
the declaration once you've confirmed it live, the way this one was.

## Quick Reference

```bash
# Text-to-video
python3 tools/ltx2.py --prompt "A sunset over the ocean, golden light on waves, cinematic" --output sunset.mp4

# Image-to-video (animate a still image)
python3 tools/ltx2.py --prompt "Gentle camera drift, soft ambient motion" --input photo.jpg --output animated.mp4

# Custom resolution and duration
python3 tools/ltx2.py --prompt "..." --width 1024 --height 576 --num-frames 161 --output wide.mp4

# Fast mode (fewer steps, quicker)
python3 tools/ltx2.py --prompt "..." --quality fast --output quick.mp4

# Reproducible output
python3 tools/ltx2.py --prompt "..." --seed 42 --output reproducible.mp4
```

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--prompt` | (required) | Text description of the video |
| `--input` | - | Input image for image-to-video |
| `--width` | 768 | Video width (divisible by 64) |
| `--height` | 512 | Video height (divisible by 64) |
| `--num-frames` | 121 | Frame count, must satisfy `(n-1) % 8 == 0` |
| `--fps` | 24 | Frames per second |
| `--quality` | standard | `standard` (30 steps) or `fast` (15 steps) |
| `--steps` | 30 | Override inference steps directly |
| `--seed` | random | Seed for reproducibility |
| `--output` | auto | Output file path |
| `--negative-prompt` | sensible default | What to avoid |

## Valid Frame Counts

`(n - 1) % 8 == 0`: 25 (~1s), 49 (~2s), 73 (~3s), 97 (~4s), **121 (~5s default)**, 161 (~6.7s), 193 (~8s max practical).

## Common Resolutions

| Resolution | Ratio | Notes |
|------------|-------|-------|
| 768x512 | 3:2 | Default, good balance |
| 512x512 | 1:1 | Square, fastest |
| 1024x576 | 16:9 | Widescreen |
| 576x1024 | 9:16 | Portrait/vertical |

## Prompting Guide

LTX-2 responds well to cinematographic descriptions. Layer these dimensions:

- **Camera:** "Slow dolly forward", "Aerial drone shot", "Tracking shot", "Static wide angle"
- **Lighting:** "Golden hour", "Cinematic lighting", "Neon-lit", "Soft diffused light"
- **Motion:** "Timelapse of...", "Slow motion", "Gentle camera drift", "Gradually transitions"
- **Style:** "Shot on 35mm film", "Documentary style", "Clean minimal aesthetic"
- **Negative:** Always implicitly avoids "worst quality, blurry, jittery, watermark, text, logo"

Keep prompts under 200 words. Be specific about the scene.

### Good Prompts

```
# Atmospheric b-roll
"Aerial drone shot slowly flying over turquoise ocean waves breaking on white sand, golden hour sunlight, cinematic"

# Product/tech scene
"Close-up of hands typing on a mechanical keyboard, shallow depth of field, soft desk lamp lighting, cozy atmosphere"

# Abstract background
"Dark moody abstract background with flowing blue light streaks, subtle geometric grid, bokeh particles floating, cinematic tech atmosphere"

# Animate a portrait
"Professional headshot, subtle natural head movement, confident warm expression, studio lighting, shallow depth of field"

# Animate a slide/screenshot
"Gentle subtle particle effects floating across a presentation slide, soft ambient light shifts, very slight camera drift"
```

### Bad Prompts

```
# Too vague
"A cool video"

# Too many competing ideas
"A cat riding a skateboard while juggling fire on the moon during a thunderstorm"

# Describing text/UI (model can't render text reliably)
"A website showing the text 'Welcome to our platform'"

# Non-Latin script is worse, not just "also unreliable"
"A shop sign reading 懒得动？交给小猫" — do not do this. Same failure mode as
image-generation models baking in text (see flux-best-practices): the model
won't render tofu boxes, it renders plausible-looking but wrong characters,
which is easy to miss on a quick review and harder to catch than a Latin
typo. Never prompt for on-screen text in any script; composite real text
afterward in Remotion (which has a bundled CJK font fallback — see
remotion-composer/src/fonts.ts) or via ffmpeg drawtext with a real font file.
```

## Video Production Use Cases

### B-Roll Clips
Generate atmospheric 5s shots for cutaways between narrated scenes:
```bash
python3 tools/ltx2.py --prompt "Futuristic holographic interface, glowing data visualizations, clean workspace, cinematic" --output broll_tech.mp4
python3 tools/ltx2.py --prompt "Aerial view of European city at golden hour, modern architecture" --output broll_europe.mp4
```

### Animated Slide Backgrounds
Feed a slide screenshot and add subtle motion:
```bash
python3 tools/ltx2.py --prompt "Gentle particle effects, soft ambient light shifts, very slight camera drift" --input slide.png --output animated_slide.mp4
```

### Animated Portraits
Bring still headshots to life:
```bash
python3 tools/ltx2.py --prompt "Subtle natural head movement, warm expression, professional lighting" --input headshot.png --output animated_portrait.mp4
```

### Branded Intro/Outro
Generate abstract motion backgrounds for title cards:
```bash
python3 tools/ltx2.py --prompt "Dark moody background with flowing blue and coral light streaks, bokeh particles, cinematic tech atmosphere, no text" --output intro_bg.mp4
```

### Combining with Other Tools

LTX-2 generates raw clips. Combine with the rest of the toolkit:

| Workflow | Tools |
|----------|-------|
| Generate clip → upscale | `ltx2.py` → `upscale.py` |
| Generate clip → add to Remotion | `ltx2.py` → use as `<OffthreadVideo>` in composition |
| Generate image → animate | `flux2.py` → `ltx2.py --input` |
| Generate clip → extract audio | `ltx2.py` → `ffmpeg -i clip.mp4 -vn audio.wav` |
| Generate clip → add voiceover | `ltx2.py` → mix with `qwen3_tts.py` output |

## Technical Details

- **Model:** LTX-2.3 22B DiT (Lightricks), bf16
- **GPU:** A100-80GB on Modal (~$4.68/hr)
- **Inference:** ~2.5 min per clip (768x512, 121 frames, 30 steps)
- **Cost:** ~$0.20-0.25 per 5s clip
- **Cold start:** ~60-90s (loading ~55GB weights)
- **Output:** H.264 MP4 with synchronized ambient audio (24fps)
- **Max duration:** ~8s (193 frames) per clip

### Known Limitations

- **Training data artifacts:** ~30% of generations may have unwanted logos/text from training data. Re-run with different `--seed`.
- **Text rendering:** Cannot reliably generate readable text in video. Use Remotion overlays instead. This is worse for CJK/non-Latin scripts — expect confidently-wrong characters, not tofu boxes, so a quick glance won't catch it.
- **Max duration:** ~8s per clip. Longer content needs stitching.
- **Audio:** Generated audio is ambient/environmental only. Use voiceover/music tools for speech and music.
- **License:** Community License — free under $10M revenue, commercial license needed above that.

## Setup

```bash
# 1. Create Modal secret for HuggingFace (one-time)
modal secret create huggingface-token HF_TOKEN=hf_your_token

# 2. Deploy (downloads ~55GB of weights, takes ~10 min)
modal deploy docker/modal-ltx2/app.py

# 3. Save endpoint URL to .env
echo "MODAL_LTX2_ENDPOINT_URL=https://yourname--video-toolkit-ltx2-ltx2-generate.modal.run" >> .env

# 4. Test
python3 tools/ltx2.py --prompt "A candle flickering on a dark table, cinematic" --output test.mp4
```

**Important:** HuggingFace token needs read-access scope. Accept the [Gemma 3 license](https://huggingface.co/google/gemma-3-12b-it-qat-q4_0-unquantized) before deploying. Unauthenticated downloads are severely rate-limited.
