# Cinematic Video Pipeline

> Sources: No Film School editorial guides, StudioBinder filmmaking resources, Film Riot
> production tutorials, CinematographyDB shot databases, Walter Murch "In the Blink of an Eye"

> For the universal cinematography vocabulary (camera, lens, motion, focus primitives, plus the 5-aspect Subject / Subject Motion / Scene / Spatial Framing / Camera spec), see `skills/creative/video-gen-prompting.md`. This file layers cinematic-specific conventions on top of those primitives — it does not redefine them.

## Quick Reference Card

```
ASPECT RATIO:     2.39:1 (widescreen cinematic) or 16:9 with letterbox
LETTERBOX:        Black bars at top/bottom — 1920x800 active area in 1920x1080 frame
FRAME RATE:       24fps (cinematic standard)
SHOT DURATION:    4-8 seconds average (longer than explainer, shorter than documentary)
COLOR GRADE:      cinematic_warm or cinematic_cool profile
AUDIO:            Layered: dialogue + ambient + Foley + score
MUSIC:            60-90 BPM, orchestral or ambient, dynamic (not loop-based)
TARGET LUFS:      -14 LUFS integrated, -24 LUFS for quiet moments
```

## Replace Mood Adjectives with Visual Causes

> **"Cinematic" and "epic" don't constrain pixels.** The cinematic look comes from concrete choices: aspect ratio, lens, lighting key, color grade, shot duration, and audio layer count. State those — the rest is decoration.
>
> The CMU/Harvard CHAI study showed subjective phrasing varies wildly across annotators and model interpretations, which means a beat tagged "moody" routes to a different visual every render. Replace the adjective with the lighting + grade + shot-duration combination that produces moodiness. See `skills/creative/storytelling.md` "Anti-Subjective Rule" for the script-side equivalent.
>
> | Mood adjective | Cinematic translation |
> |---|---|
> | "epic" | 2.39:1 letterbox, 24fps, 8s+ shot duration, orchestral score with crescendo |
> | "moody" | `moody_dark` grade at 0.6, key light at 1/8 fill, 6s+ contemplative shots, ambient bed at -28dB |
> | "intimate" | 1.85:1, 40-50mm equivalent, shallow DoF, 2 audio layers (dialogue + room tone), no music under dialogue |
> | "cinematic" | (this word is banned — pick one of the above or describe the actual choices) |

## Aspect Ratios

| Ratio | Resolution (in 1080p frame) | Feel | When to Use |
|-------|---------------------------|------|-------------|
| **2.39:1** (anamorphic) | 1920x803 (138px bars each) | Epic, cinematic, grand | Cinematic explainers, brand films |
| **2.35:1** (scope) | 1920x817 (131px bars each) | Classic film | Similar to 2.39:1, slightly taller |
| **1.85:1** (flat) | 1920x1038 (21px bars each) | Moderate cinematic | Subtle letterbox, less dramatic |
| **16:9** (no letterbox) | 1920x1080 | Standard | Default, no cinematic treatment |

### Implementing Letterbox in FFmpeg

```bash
# Add 2.39:1 letterbox (138px black bars top and bottom)
ffmpeg -i input.mp4 -vf "pad=1920:1080:0:138:black,crop=1920:1080:0:0" output.mp4

# Or render at native ratio and pad:
ffmpeg -i input.mp4 -vf "scale=1920:803,pad=1920:1080:0:138:black" output.mp4
```

**Rule:** Only use letterbox when the content genuinely benefits from cinematic framing. Don't letterbox a screen recording or talking head — it just wastes pixels.

## Shot Duration and Pacing

### Average Shot Length by Style

| Style | Average Shot | Cuts/Minute |
|-------|-------------|-------------|
| Action/intense | 2-4s | 15-30 |
| Standard cinematic | 4-8s | 8-15 |
| Documentary | 6-12s | 5-10 |
| Contemplative | 10-20s | 3-6 |
| Montage sequence | 1-3s | 20-40 |

### Pacing Rhythm

Cinematic pacing follows a **breathing rhythm** — vary shot length deliberately:

```
Long (8s) → Medium (5s) → Short (3s) → Short (2s) → LONG (10s) → Medium (6s)
```

**Never use the same shot length 3 times in a row** — it creates monotony.

### The Murch Rule

Walter Murch's editing priorities (in order of importance):
1. **Emotion** — does the cut serve the emotional arc?
2. **Story** — does the cut advance the narrative?
3. **Rhythm** — does the cut feel right in the pacing?
4. **Eye trace** — where is the viewer looking?
5. **2D plane** — screen geography (180-degree rule)
6. **3D space** — spatial continuity

For OpenMontage explainers using cinematic style: prioritize rhythm and story over spatial concerns (since we're often cutting between generated images, not continuous footage).

## Audio Layering

Cinematic audio has **4 layers** (not just voiceover + music):

| Layer | Level | Content |
|-------|-------|---------|
| **Dialogue/narration** | -12 dB peak | Primary voice |
| **Music/score** | -24 to -18 dB | Orchestral, ambient, dynamic |
| **Ambient/room tone** | -30 to -24 dB | Environmental sound bed |
| **Foley/SFX** | -18 to -12 dB | Specific action sounds |

### Music for Cinematic

| Characteristic | Value |
|---------------|-------|
| BPM | 60-90 (slower than standard explainer) |
| Genre | Orchestral, ambient, piano, cinematic electronic |
| Dynamics | Dynamic (crescendos, swells, quiet moments) — NOT loop-based |
| Key changes | At narrative turning points |
| Silence | Deliberately remove music for 3-5s at key reveals |

### Ambient Sound

Add a subtle ambient layer to fill silence and create depth:
- Room tone / air conditioning hum (very low, -35 dB)
- Environmental sounds matching the topic (city, nature, lab)
- Generates "presence" even during narration pauses

## Color Grading for Cinematic

| Look | Profile | Intensity | Characteristics |
|------|---------|-----------|----------------|
| **Warm cinematic** | `cinematic_warm` | 0.85 | Orange highlights, lifted shadows |
| **Teal & orange** | `cinematic_cool` | 0.7 | Classic Hollywood blockbuster look |
| **Moody dark** | `moody_dark` | 0.6 | Crushed blacks, low saturation |
| **Vintage film** | `vintage_film` | 0.7 | Faded, warm tint, reduced contrast |

**Cinematic grading rules:**
- Shadows should be slightly lifted (never pure black)
- Highlights should be slightly rolled off (never pure white)
- Skin tones must stay on the vectorscope skin tone line
- Consistency across all clips — one LUT/profile for the entire video
- **If a beat is described as "moody," rewrite as the lighting + grade + shot-duration combination that produces moodiness.** Don't pass mood adjectives to the asset/edit stages.

## Applying to OpenMontage

When building cinematic-style content:

1. **Set aspect ratio** — use 2.39:1 letterbox for true cinematic, or 16:9 with `cinematic_warm` grade for subtle
2. **Render at 24fps** if the content is purely generated/animated (set in `video_compose`)
3. **Shot duration 4-8 seconds average** — vary deliberately, never same length 3x
4. **Layer audio** — narration + music + ambient minimum; add Foley SFX at key moments
5. **Music at 60-90 BPM**, dynamic (not looping) — use `music_gen` with "cinematic orchestral" prompt
6. **Remove music for 3-5 seconds** at key reveals — silence is powerful
7. **Color grade with `cinematic_warm` or `cinematic_cool`** at 0.7-0.85 intensity
8. **Image prompts** should include "cinematic lighting, shallow depth of field, film grain" for matching aesthetic
9. **Slower narration** — 140-150 WPM (slower than standard 155 WPM explainer pace)
