---
name: acestep
description: AI music generation with ACE-Step 1.5 — background music, vocal tracks, covers, stem extraction for video production. Use when generating music, soundtracks, jingles, or working with audio stems. Triggers include background music, soundtrack, jingle, music generation, stem extraction, cover, style transfer, or musical composition tasks.
---

# ACE-Step 1.5 Music Generation

Open-source music generation (MIT license) via the `acestep_music` tool
(`tools/audio/acestep_music.py`), a BaseTool with `capability="music_generation"`.
Route to it for **bulk / background / instrumental** music — it is near-free versus
the paid music APIs (ElevenLabs `music_gen`, Suno `suno_music`), which you reserve
for hero tracks. Runs on a RunPod serverless ACE-Step endpoint.
Requires `RUNPOD_API_KEY` and `RUNPOD_ACESTEP_ENDPOINT_ID` in `.env`.

> The tool is invoked through the registry
> (`registry.get_by_capability("music_generation")` → `.execute({...})`), not a CLI.
> The `python tools/music_gen.py --flag …` snippets below are kept as a **parameter
> reference**: `--prompt`→`prompt`, `--duration`→`duration_seconds`, `--bpm`→`bpm`,
> `--key`→`key`, `--lyrics`→`lyrics`, `--seed`→`seed`. Preset rows map to prompt+bpm+key
> values you pass directly.

## Quick Reference

```bash
# Basic generation
python tools/music_gen.py --prompt "Upbeat tech corporate" --duration 60 --output bg.mp3

# With musical control
python tools/music_gen.py --prompt "Calm ambient piano" --duration 30 --bpm 72 --key "D Major" --output ambient.mp3

# Scene presets (video production)
python tools/music_gen.py --preset corporate-bg --duration 60 --output bg.mp3
python tools/music_gen.py --preset tension --duration 20 --output problem.mp3
python tools/music_gen.py --preset cta --brand digital-samba --duration 15 --output cta.mp3

# Vocals with lyrics
python tools/music_gen.py --prompt "Indie pop jingle" --lyrics "[verse]\nBuild it better\nShip it faster" --duration 30 --output jingle.mp3

# Cover / style transfer
python tools/music_gen.py --cover --reference theme.mp3 --prompt "Jazz piano version" --duration 60 --output jazz_cover.mp3

# Stem extraction
python tools/music_gen.py --extract vocals --input mixed.mp3 --output vocals.mp3

# List presets
python tools/music_gen.py --list-presets
```

## Creating a Song (Step by Step)

### 1. Instrumental background track (simplest)
```bash
python tools/music_gen.py --prompt "Upbeat indie rock, driving drums, jangly guitar" --duration 60 --bpm 120 --key "G Major" --output track.mp3
```

### 2. Song with vocals and lyrics
Write lyrics in a temp file or pass inline. Use structure tags to control song sections.

```bash
# Write lyrics to a file first (recommended for longer songs)
cat > /tmp/lyrics.txt << 'LYRICS'
[Verse 1]
Walking through the morning light
Coffee in my hand feels right
Another day to build and dream
Nothing's ever what it seems

[Chorus - anthemic]
WE KEEP MOVING FORWARD
Through the noise and doubt
We keep moving forward
That's what it's about

[Verse 2]
Screens are glowing late at night
Shipping code until it's right
The deadline's close but so are we
Almost there, just wait and see

[Chorus - bigger]
WE KEEP MOVING FORWARD
Through the noise and doubt
We keep moving forward
That's what it's about

[Outro - fade]
(Moving forward...)
LYRICS

# Generate the song
python tools/music_gen.py \
  --prompt "Upbeat indie rock anthem, male vocal, driving drums, electric guitar, studio polish" \
  --lyrics "$(cat /tmp/lyrics.txt)" \
  --duration 60 \
  --bpm 128 \
  --key "G Major" \
  --output my_song.mp3
```

### 3. Using a preset for video background
```bash
python tools/music_gen.py --preset tension --duration 20 --output problem_scene.mp3
```

### Key tips for good results
- **Caption = overall style** (genre, instruments, mood, production quality)
- **Lyrics = temporal structure** (verse/chorus flow, vocal delivery)
- **UPPERCASE in lyrics** = high vocal intensity
- **Parentheses** = background vocals: "We rise (together)"
- **Keep 6-10 syllables per line** for natural rhythm
- **Don't describe the melody in the caption** — describe the *sound* and *feeling*
- **Use `--seed`** to lock randomness when iterating on prompt/lyrics

## Scene Presets

| Preset | BPM | Key | Use Case |
|--------|-----|-----|----------|
| `corporate-bg` | 110 | C Major | Professional background, presentations |
| `upbeat-tech` | 128 | G Major | Product launches, tech demos |
| `ambient` | 72 | D Major | Overview slides, reflective content |
| `dramatic` | 90 | D Minor | Reveals, announcements |
| `tension` | 85 | A Minor | Problem statements, challenges |
| `hopeful` | 120 | C Major | Solution reveals, resolutions |
| `cta` | 135 | E Major | Call to action, closing energy |
| `lofi` | 85 | F Major | Screen recordings, coding demos |

## Task Types

### text2music (default)
Generate music from text prompt + optional lyrics.

### cover
Style transfer from reference audio. Control blend with `--cover-strength` (0.0-1.0):
- **0.2** — Loose style inspiration (more creative freedom)
- **0.5** — Balanced style transfer
- **0.7** — Close to original structure (default)
- **1.0** — Maximum fidelity to source

### extract
Stem separation — isolate individual tracks from mixed audio.
Tracks: `vocals`, `drums`, `bass`, `guitar`, `piano`, `keyboard`, `strings`, `brass`, `woodwinds`, `other`

### repaint (future)
Regenerate a specific time segment within existing audio while preserving the rest.

### lego (future, requires base model)
Generate individual instrument tracks within an existing audio context.

### complete (future, requires base model)
Extend partial compositions by adding specified instruments.

## Prompt Engineering

### Caption Writing — Layer Dimensions

Write captions by layering multiple descriptive dimensions rather than single-word descriptions.

**Dimensions to include:**
- **Genre/Style**: pop, rock, jazz, electronic, lo-fi, synthwave, orchestral
- **Emotion/Mood**: melancholic, euphoric, dreamy, nostalgic, intimate, tense
- **Instruments**: acoustic guitar, synth pads, 808 drums, strings, brass, piano
- **Timbre**: warm, crisp, airy, punchy, lush, polished, raw
- **Era**: "80s synth-pop", "modern indie", "classical romantic"
- **Production**: lo-fi, studio-polished, live recording, cinematic
- **Vocal**: breathy, powerful, falsetto, raspy, spoken word (or "instrumental")

**Good**: "Slow melancholic piano ballad with intimate female vocal, warm strings building to powerful chorus, studio-polished production"
**Bad**: "Sad song"

### Key Principles

1. **Specificity over vagueness** — describe instruments, mood, production style
2. **Avoid contradictions** — don't request "classical strings" and "hardcore metal" simultaneously
3. **Repetition reinforces priority** — repeat important elements for emphasis
4. **Sparse captions = more creative freedom** — detailed captions constrain the model
5. **Use metadata params for BPM/key** — don't write "120 BPM" in the caption, use `--bpm 120`

### Lyrics Formatting

**Structure tags** (use in lyrics, not caption):
```
[Intro]
[Verse]
[Chorus]
[Bridge]
[Outro]
[Instrumental]
[Guitar Solo]
[Build]
[Drop]
[Breakdown]
```

**Vocal control** (prefix lines or sections):
```
[raspy vocal]
[whispered]
[falsetto]
[powerful belting]
[harmonies]
[ad-lib]
```

**Energy indicators:**
- UPPERCASE = high intensity ("WE RISE ABOVE")
- Parentheses = background vocals ("We rise (together)")
- Keep 6-10 syllables per line within sections for natural rhythm

**Example — Tech Product Jingle:**
```
[Verse]
Build it better, ship it faster
Every feature tells a story

[Chorus - anthemic]
THIS IS YOUR PLATFORM
Your vision, your stage
Digital Samba, every page

[Outro - fade]
(Build it better...)
```

## Video Production Integration

### Music for Scene Types

| Scene | Preset | Duration | Notes |
|-------|--------|----------|-------|
| Title | `dramatic` or `ambient` | 3-5s | Short, mood-setting |
| Problem | `tension` | 10-15s | Dark, unsettling |
| Solution | `hopeful` | 10-15s | Relief, optimism |
| Demo | `lofi` or `corporate-bg` | 30-120s | Non-distracting, matches demo length |
| Stats | `upbeat-tech` | 8-12s | Building credibility |
| CTA | `cta` | 5-10s | Maximum energy, punchy |
| Credits | `ambient` | 5-10s | Gentle fade-out |

### Timing Workflow

1. Plan scene durations first (from voiceover script)
2. Generate music to match: `--duration <scene_seconds>`
3. Music duration is precise (within 0.1s of requested)
4. For background music spanning multiple scenes: generate one long track

### Combining with Voiceover

Background music should be mixed at 10-20% volume in Remotion:
```tsx
<Audio src={staticFile('voiceover.mp3')} volume={1} />
<Audio src={staticFile('bg-music.mp3')} volume={0.15} />
```

For music under narration: use instrumental presets (`corporate-bg`, `ambient`, `lofi`).
For music-forward scenes (title, CTA): can use higher volume or vocal tracks.

### Brand Consistency

Use `--brand <name>` to load hints from `brands/<name>/brand.json`.
Use `--cover --reference brand_theme.mp3` to create variations of a brand's sonic identity.
For consistent sound across a project: fix the seed (`--seed 42`) and vary only duration/prompt.

## Technical Details

- **Output**: 48kHz MP3/WAV/FLAC
- **Duration range**: 10-600 seconds
- **BPM range**: 30-300
- **Inference**: ~2-3s on GPU (turbo, 8 steps), ~40-60s on Mac MPS
- **Turbo model**: 8 steps, no CFG needed, fast and good quality
- **Shift parameter**: 3.0 recommended for turbo (improves quality)

### When NOT to use ACE-Step
- **Voice cloning** — use Qwen3-TTS or ElevenLabs instead
- **Sound effects** — use ElevenLabs SFX (`tools/sfx.py`)
- **Speech/narration** — use voiceover tools, not music gen
- **Stem extraction from video** — extract audio first with FFmpeg, then use `--extract`
