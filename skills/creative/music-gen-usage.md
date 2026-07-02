# Music Generation Usage for Balamonis Studio

> Sources: ElevenLabs Music API documentation, ElevenLabs best practices guide, Artlist BPM
> guide, existing Layer 3 skills at `.agents/skills/music/` and `.agents/skills/elevenlabs/`

## Quick Reference Card

```
API MODEL:        music_v1
MIN DURATION:     3,000ms (3s)
MAX DURATION:     600,000ms (10 min)
INSTRUMENTAL:     Always set force_instrumental=true for video background
COST:             ~$0.05 per 30 seconds
KEY RULE:         Music must be 18-20 dB below narration (see sound-design.md)
```

## BPM Selection by Video Type

| Video Type | BPM Range | Prompt Fragment |
|-----------|-----------|-----------------|
| Educational explainer | 80-100 | "gentle ambient electronic, 90 BPM" |
| Corporate / tech | 100-120 | "upbeat corporate pop, 110 BPM, positive" |
| Epic / dramatic reveal | 60-80 | "cinematic orchestral, 70 BPM, building tension" |
| Fast-paced montage | 120-140 | "energetic electronic, 130 BPM, driving beat" |
| Meditation / calm | 50-70 | "ambient drone, 60 BPM, peaceful" |
| Comedy / lighthearted | 100-130 | "playful ukulele pop, 120 BPM, whimsical" |
| Sad / reflective | 60-80 | "melancholic piano, 65 BPM, minor key" |
| Action / hype | 140-170 | "high-intensity drum and bass, 160 BPM" |

## Key and Mood Mapping

| Mood | Key | Musical Characteristics |
|------|-----|----------------------|
| Happy / upbeat | C major, G major | Bright, resolved, energetic |
| Serious / professional | D minor, A minor | Grounded, authoritative |
| Mysterious / curious | E minor, B minor | Tension, anticipation |
| Triumphant / inspiring | D major, Bb major | Expansive, climactic |
| Melancholic / thoughtful | F minor, C minor | Reflective, emotional |
| Neutral / ambient | C major, Am (no strong key) | Unobtrusive, background |

## Prompt Engineering

### Structure

```
[GENRE/STYLE], [BPM], [KEY/MOOD], [INSTRUMENTS], [ENERGY LEVEL], [PURPOSE]
```

### Examples

**Educational explainer:**
```
Gentle lo-fi ambient electronic, 90 BPM, C major, soft synth pads and light
percussion, calm and steady energy, background music for narration
```

**Corporate product demo:**
```
Modern upbeat corporate pop, 110 BPM, G major, acoustic guitar and light drums,
positive energy building gradually, underscore for product walkthrough
```

**Technical deep-dive:**
```
Minimal ambient electronic, 80 BPM, A minor, soft Rhodes piano and subtle
bass, contemplative and focused, background music for technical explanation
```

### Key Prompting Rules

1. **Always include "background" or "underscore"** — tells the model to stay dynamically even
2. **Always use `force_instrumental=true`** — lyrics compete with narration
3. **Specify BPM explicitly** — don't rely on genre to set tempo
4. **Avoid "bright hi-hats" or "prominent vocals"** — high-frequency busy elements compete with speech in the 2-4 kHz intelligibility band
5. **Include energy direction** — "steady energy" for explainers, "building gradually" for reveals

## Duration Matching

### Exact Duration

```python
result = music_gen.execute({
    "prompt": "Gentle ambient, 90 BPM, background underscore",
    "duration_seconds": 150,  # Match video length
    "output_path": "assets/music/background.mp3"
})
```

### Section-Mapped (Advanced)

For videos with distinct acts, generate sections separately:

| Video Section | Duration | Music Style |
|--------------|----------|-------------|
| Intro / hook | 8-10s | Soft, building |
| Main explanation | 90-120s | Steady, neutral |
| Key reveal | 20-30s | Intensified, fuller |
| Outro | 10-15s | Fading, gentle |

Generate each as a separate track and crossfade in the `audio_mixer`.

## Looping for Long Videos

For videos longer than the generated track:

1. Generate a track 30-60% of video length
2. Use FFmpeg to create a seamless loop:
   ```bash
   ffmpeg -stream_loop 2 -i music.mp3 -c copy music_looped.mp3
   ```
3. Add a 2-3 second crossfade at loop points in `audio_mixer`

**Better approach:** Generate at the exact video duration. ElevenLabs supports up to 10 minutes per generation.

## Stem Isolation

For cleaner ducking control, generate isolated stems:

- `"solo electric guitar in E minor, 90 BPM"` — guitar-only track
- `"soft ambient pad in C major, 80 BPM"` — synth pad only
- Layer stems in FFmpeg during composition for precise ducking control

## Applying to Balamonis Studio

When using the `music_gen` tool:

1. **Match BPM to content type** using the table above — don't default to a generic prompt
2. **Always set `force_instrumental=true`** — no lyrics under narration
3. **Include "background" or "underscore"** in every prompt
4. **Set duration to match video length** — avoid looping when possible
5. **Budget check** — at $0.05/30s, a 3-minute video costs ~$0.30 for music
6. **Duck music 18-20 dB below narration** — see `skills/creative/sound-design.md` for ducking rules
7. **Cut 2-4 kHz on the music bed** in `audio_mixer` to clear the speech intelligibility band
8. **Test on phone speakers** — if narration disappears behind music, duck more aggressively
9. **One track per video** — avoid switching music styles mid-video unless there's a clear narrative shift
