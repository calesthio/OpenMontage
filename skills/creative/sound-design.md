# Sound Design for Video Production

> Sources: W3C accessibility standards, BBC audio guidelines, YouTube/TikTok platform specs,
> Sweetwater mastering guides, ElevenLabs documentation, Boris FX, HookSounds, Artlist

## Quick Reference Card

```
DIALOGUE:       -12 dB peak  |  -16 to -14 LUFS integrated
MUSIC BED:      -30 to -20 dB (18-20 dB below dialogue)
SFX:            -18 to -12 dB (6 dB below dialogue minimum)
WHOOSH TIMING:  Start 10-20ms before visual, duration 400-500ms
MUSIC BPM:      Calm 60-80 | Standard 90-110 | Upbeat 120-140
TRUE PEAK:      Never exceed -1.5 dBTP
VOICE EQ:       HPF 80Hz, cut 500Hz, boost 2-5kHz, cut 6-8kHz
VOICE COMP:     3:1 ratio, 1-5ms attack, 10-20ms release
TARGET LUFS:    -14 LUFS (YouTube/TikTok/IG) | -16 LUFS (podcasts)
```

## Audio Ducking Levels

| Element | Peak Level | Notes |
|---------|-----------|-------|
| Dialogue / Narration | -6 dB to -12 dB | Primary element |
| Background music (during speech) | -18 dB to -20 dB | 18-20 dB below dialogue |
| Sound effects | -12 dB to -18 dB | Between dialogue and music |
| Final mix | -10 dB to -20 dB | Never exceed 0 dB |

**Ducking rules:**
- W3C accessibility: music must be **20 dB lower** than foreground speech
- BBC guideline: lower music by an additional **4 dB** from where you think it sounds right
- Duck music **6-12 dB** when narration is active; for complex educational topics, duck up to **22 dB**
- EQ trick: cut **2-4 kHz** on background music to make room for speech clarity
- When testing, adjust in **1 dB increments** from a -20 dB baseline upward

## Music Selection by Content Type

| Content Type | BPM Range | Mood |
|-------------|-----------|------|
| Calm explainer / tutorial | 60-80 | Contemplative, focused, trust-building |
| Corporate / testimonial | 60-100 | Professional, calm, credible |
| Standard explainer / educational | 90-110 | Steady, engaging, not distracting |
| Upbeat explainer / promo | 110-130 | Enthusiastic, approachable |
| High-energy / product demo | 120-140 | Exciting, urgent, dynamic |
| Action / fast-paced | 140-200 | Adrenaline, intensity |

**Genre recommendations for explainers:**
- Lo-fi (steady, non-distracting, modern feel)
- Ambient (atmospheric, stays in background)
- Light acoustic guitar instrumentals (warm, approachable)
- Contemporary pop instrumentals (upbeat, familiar)
- Inspiring soundtrack / cinematic light (builds emotion without overwhelming)

**Key rules:**
- Always use **instrumental** tracks when voiceover is present — lyrics compete with narration
- Choose dynamically **even** tracks — avoid dramatic crescendos or beat drops
- Match energy to the learning context: upbeat for "exciting new concept," gentle for serious topics

## Sound Effects (SFX) Placement

### SFX Categories for Explainer Videos

| SFX Type | Use Case | Duration | Level |
|----------|----------|----------|-------|
| Whoosh / Swish | Scene transitions, slide changes | 400-500ms | -18 to -12 dB |
| Pop / Pluck | Text appearing, bullet points | <200ms | -15 to -12 dB |
| Click / Tap | UI interactions, button presses | <100ms | -20 to -15 dB |
| Riser / Swell | Building to a reveal or key point | 1-3s | -18 to -12 dB |
| Impact / Hit | Key reveal, important stat | <300ms | -12 to -6 dB |
| Subtle whoosh | Element sliding in/out | 200-400ms | -20 to -15 dB |

### Timing rules
- Start whoosh **10-20ms before** the visual transition (brain processes audio faster)
- Peak of whoosh energy should coincide with the **moment of greatest visual change**
- Fine-tune in **1-frame increments** for sync
- When stacking whooshes, keep them in different frequency bands

## Platform Loudness Targets (2025)

| Platform | Integrated LUFS | True Peak | Notes |
|----------|----------------|-----------|-------|
| YouTube | -14 LUFS | -1.5 dBTP | Normalizes down, not up |
| YouTube Shorts | -14 LUFS | -1.5 dBTP | Same as long-form |
| TikTok | -14 LUFS | -1 dBTP | Prioritize 2-4 kHz for phone speakers |
| Instagram Reels | -14 LUFS | -1 dBTP | Same mobile optimization |
| Spotify | -14 LUFS | -2 dBTP | Stricter true peak |
| Apple Podcasts | -16 LUFS | -1 dBTP | More headroom for speech |

### Content-type LUFS

| Content Type | Integrated LUFS | Dynamic Range |
|-------------|----------------|---------------|
| Dialogue-heavy / educational | -16 to -14 LUFS | 6-12 dB |
| Music videos | -14 to -12 LUFS | 6-10 dB |
| Gaming content | -14 to -12 LUFS | 8-12 dB |

### Technical specs
- Sample rate: **48 kHz** preferred
- Bit depth: **24-bit** preferred
- Bitrate: **192 kbps** minimum
- Noise floor: below **-60 dB**
- Headroom: at least **-6 dB** in the final mix

## AI TTS (ElevenLabs) Mixing

### Processing Chain

1. **High-pass filter:** 80-100 Hz (24 dB/oct slope) — removes rumble and low-frequency TTS artifacts
2. **EQ:**
   - Cut ~500 Hz: removes muddiness/boxy quality
   - Boost 2-5 kHz (+2-3 dB): adds presence and clarity
   - Cut 6-8 kHz (gentle): reduces sibilance/harshness common in AI voices
   - Optional: boost 120-250 Hz for thinner AI voices
3. **Compression:**
   - Ratio: **3:1** (range 2:1 to 4:1)
   - Attack: **1-5 ms**
   - Release: **10-20 ms** (increase to 30ms if pumping)
   - Threshold: **-26 dB** (target -4 to -6 dB gain reduction)
   - Output gain: **+6 dB**
4. **De-esser:** target **6-8 kHz** if sibilance remains
5. **Limiter:** ceiling at **-1.5 dBTP**

### AI-specific tips
- AI TTS has inconsistent dynamics — compression is more important than for human speech
- ElevenLabs may have subtle artifacts in 4-6 kHz; use narrow notch cut if detected
- Sidechain background music to voiceover track for automatic ducking
- Cut 2-4 kHz on the music bed to clear the "intelligibility band" for voice
- Always test on phone speakers — if voice disappears, boost 2-4 kHz more aggressively

## Applying to Balamonis Studio

When the **audio_mixer** tool is used in the compose stage:

1. Set narration as primary track, music as secondary
2. Apply ducking: music -18 to -20 dB below narration during speech
3. Select music BPM from the table above based on the playbook mood
4. Place SFX at transition points with 10-20ms audio lead
5. Target -14 LUFS integrated for YouTube output
6. Keep true peak below -1.5 dBTP
7. For AI TTS narration, apply the processing chain above before mixing
8. Test the final mix on phone speakers — most viewers watch on mobile
