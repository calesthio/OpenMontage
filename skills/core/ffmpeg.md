# FFmpeg Skill

## When to Use

Use FFmpeg-backed tools for any video/audio processing that does not require AI inference:
cutting, trimming, speed adjustment, concatenation, audio extraction, mixing,
subtitle burn-in, overlay compositing, encoding, face enhancement, color grading,
and audio cleanup.

## Tools That Use FFmpeg

### Core Pipeline

| Tool | Capability |
|------|-----------|
| `video_trimmer` | Cut, trim, speed adjust, concat video segments |
| `video_compose` | Full composition: cuts + subtitles + overlays + encode |
| `audio_mixer` | Mix speech/music/SFX, ducking, fades, extract audio |
| `frame_sampler` | Extract representative frames from video |

### Enhancement Layer

| Tool | Capability | Key Presets |
|------|-----------|-------------|
| `face_enhance` | Skin smoothing, sharpening, warm/cool tones | `talking_head_standard`, `soft_skin`, `sharpen` |
| `color_grade` | Cinematic color grading with intensity control | `cinematic_warm`, `cinematic_cool`, `moody_dark` |
| `audio_enhance` | Noise reduction, loudness normalization, EQ | `clean_speech`, `voice_clarity`, `podcast` |

## Key Patterns

### Enhancement Chain Order

Apply enhancements in this order to avoid filter interactions:

1. **Subtitles first** — burn into the base video
2. **Face enhance** — smoothing/sharpening works best on ungraded footage
3. **Color grade** — applies look after face is already enhanced
4. **Audio enhance** — independent of video, apply last

Each step is optional and gracefully skipped if the tool is unavailable.

### Lossless vs Re-encode

- Use `-c copy` (codec copy) when you only need to cut or concat without altering frames. This is instant and lossless.
- Re-encode (`-c:v libx264`) when applying filters (speed change, subtitles, overlays, scaling).
- Default CRF is 23. Use 18-20 for higher quality when the output is the final deliverable.

### Subtitle Burn-in

- Prefer SRT format for simple word subtitles.
- Use `force_style` with full ASS color format: `&H00FFFFFF` (not `&HFFFFFF`).
- Always escape Windows paths (`C\:` not `C:`) in the subtitles filter.
- Vertical video: `font_size: 18`, max 3-4 words/cue (`subtitle_gen` `max_words_per_cue: 4`, `max_chars_per_line: 20`), `margin_v: 50`.
- Horizontal video: `font_size: 22`, max 6-8 words/cue (`subtitle_gen` `max_words_per_cue: 8`, `max_chars_per_line: 42` — the tool defaults), `margin_v: 40`.
- Cue length is set when the SRT is generated, not at burn-in — see `skills/core/subtitle-sync.md`.

### Audio Enhancement Targets

| Platform | Target LUFS | Loudness Range |
|----------|-------------|----------------|
| Social media (TikTok, Reels) | -14 LUFS | 5-7 LU |
| YouTube | -14 to -16 LUFS | 7-11 LU |
| Podcast | -16 LUFS | 7-11 LU |
| Broadcast | -24 LUFS | 7 LU |

The `clean_speech` preset targets -16 LUFS with 11 LU range — good for YouTube/social media.

### Color Grade Intensity

- `intensity: 0.85` — recommended default for cinematic_warm on talking heads
- `intensity: 0.5` — subtle, barely noticeable
- `intensity: 1.0` — full effect, may look over-processed on some footage

### Audio Ducking

- Use `sidechaincompress` with speech as the key signal to lower music volume during dialogue.
- Typical settings: threshold=0.02, ratio=9, attack=200ms, release=500ms.

### Concatenation

- Use the concat demuxer (`-f concat -safe 0`) for same-codec segments.
- For mixed codecs or different resolutions, re-encode all segments first.

## Quality Checklist

- [ ] Output plays without artifacts on desktop and mobile
- [ ] Audio and video remain in sync after processing
- [ ] Subtitles are in the bottom 20% of frame, never covering the face
- [ ] Audio loudness is within target range for the platform
- [ ] Enhancement is visible but natural — skin tones look healthy, not orange
- [ ] No audio clipping or silence gaps at cut points
- [ ] File size is reasonable for the target platform
