# Talking Head Generation Usage for Balamonis Studio

> Sources: SadTalker paper (Zhang et al. 2023), MuseTalk documentation, existing Layer 2 skills
> at `skills/creative/face-restore-usage.md` and `skills/creative/enhancement-strategy.md`

## Quick Reference Card

```
DEFAULT MODEL:    sadtalker
INPUT:            One face photo + one audio file → animated talking video
EXPRESSION:       expression_scale=1.0 (0.5 = subtle, 1.5 = expressive)
STILL MODE:       false (true = mouth-only animation, head stays fixed)
PREPROCESS:       crop (default — crops face, animates, pastes back)
KEY RULE:         Generate audio FIRST, then pass to talking_head
```

## When to Use the talking_head Tool

| Scenario | Use talking_head? |
|----------|-------------------|
| Avatar spokesperson video from a single photo | Yes |
| Personalized message — animate a headshot with custom narration | Yes |
| No video footage exists but a photo is available | Yes |
| Multi-language avatar — same face, different audio tracks | Yes |
| Existing video footage needs processing | No — use the talking-head pipeline |
| Lip-syncing existing video to new audio | No — use the `lip_sync` tool |

## Input Requirements

### Photo

- Clear, front-facing face with good lighting
- Minimum resolution: 256x256px
- Best results: 512x512 or larger
- Neutral expression, direct eye contact
- Avoid: extreme angles, accessories covering the face (large sunglasses, masks), multiple faces in the image

### Audio

- Clean speech audio — WAV or MP3
- Sample rate: 16kHz or higher
- Audio duration determines output video duration
- Remove background noise before feeding into talking_head — clean audio produces cleaner lip sync

## Model Selection

| Model | Strengths | Weaknesses |
|-------|----------|------------|
| sadtalker | Natural head motion, good expression range, well-tested | Can struggle with extreme expressions |
| musetalk | Higher quality lip sync, sharper mouth region | More constrained head motion |

**Default to `sadtalker`** unless lip sync precision is the top priority.

## Settings Reference

### Preprocess Modes

| Mode | What It Does | When to Use |
|------|-------------|-------------|
| `crop` | Crops face region, animates, pastes back into original frame | Default — best for headshots and portraits |
| `resize` | Resizes full input to model dimensions | When you want full-frame output at model resolution |
| `full` | No preprocessing — input passed directly | Advanced — input must already be correctly sized for the model |

### expression_scale Tuning

| Value | Effect | Use Case |
|-------|--------|----------|
| 0.5 | Subtle, minimal head movement | Corporate, formal, conservative |
| 0.7 | Calm, professional | Business presentations, news-style |
| 1.0 | Natural conversational (default) | General-purpose, explainers |
| 1.5 | Expressive, energetic | Social media, engaging content |
| >1.5 | Risk of artifacts | Avoid unless intentionally stylized |

### still_mode

| Value | Effect | Use Case |
|-------|--------|----------|
| `false` (default) | Head moves naturally while speaking | More realistic, conversational feel |
| `true` | Only mouth animates, head stays fixed | Formal/corporate look, or when head motion causes artifacts |

## Common Workflows

### 1. Avatar Spokesperson

```
photo + elevenlabs_tts → talking_head → face_enhance → compose
```

Standard avatar video: generate speech from script, animate the photo, polish the face, compose into final video.

### 2. Multi-Language Avatar

```
photo + tts per language → talking_head per language → compose variants
```

Same face photo, different audio tracks per language. Each produces a separate talking-head video for localized content.

### 3. Quick Social Content

```
headshot + script → piper_tts → talking_head → subtitle_gen → compose
```

Fast turnaround social video: generate speech locally, animate, add subtitles, compose.

### 4. Photo-to-Explainer

```
talking_head output → compose with diagram overlays
```

Use the talking-head video as a presenter layer, then overlay diagrams, charts, or screen recordings during composition.

## Quality Checklist

Before accepting talking_head output, verify:

- [ ] Lip movements match the audio naturally
- [ ] Head motion looks organic, not robotic
- [ ] No visual artifacts around face edges or jaw
- [ ] Eyes blink naturally (not frozen or blinking too fast)
- [ ] Output resolution is acceptable for the target platform
- [ ] Expression intensity matches the tone of the narration

## Applying to Balamonis Studio

When using the `talking_head` tool:

1. **Generate audio FIRST** (via `tts_selector`, `elevenlabs_tts`, `openai_tts`, or `piper_tts`), then pass to talking_head
2. **Use `expression_scale=1.0` as baseline** — only increase for high-energy content
3. **Always apply `face_enhance` AFTER talking_head** to polish the output
4. **For corporate/professional content**, use `still_mode=true` and `expression_scale=0.7`
5. **Source photo quality directly impacts output quality** — use the best available photo
6. **Crop mode is the safest default** — only use `resize` or `full` if crop produces bad framing
7. **Preview a 5-second clip before generating the full video** — catch artifacts early
8. **Fallback strategy:** if SadTalker is unavailable but Wav2Lip is, record a simple static video from the photo and lip-sync it with the `lip_sync` tool instead
