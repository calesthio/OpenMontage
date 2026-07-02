# Lip Sync Usage for Balamonis Studio

> Sources: Wav2Lip paper (Prajwal et al. 2020), Wav2Lip-GAN documentation, Balamonis Studio
> `tools/lip_sync.py` implementation

## Quick Reference Card

```
DEFAULT MODEL:    wav2lip (faster, good sync accuracy)
HIGHER QUALITY:   wav2lip_gan (better visual quality, slower)
FACE PADDING:     [0, 10, 0, 0] (top, bottom, left, right)
INPUT:            Video with visible face + audio to sync to
RESIZE FACTOR:    1 = full res (best), 2 = half res (recommended for drafts)
KEY RULE:         Use lip_sync for VIDEO input; use talking_head for PHOTO input
```

## When to Use lip_sync

Lip sync is a **post-production** step. Use it after generating replacement audio.

- **Dubbing / localization** -- replace original speech with translated audio and match lips
- **Audio replacement** -- re-record narration and sync to existing video
- **Voice-over correction** -- fix mismatched audio/video timing
- **NOT for photo-to-video** -- use the `talking_head` tool instead

## CRITICAL DISTINCTION -- lip_sync vs talking_head

| | `lip_sync` | `talking_head` |
|---|---|---|
| **Input** | Existing VIDEO + new audio | Still PHOTO + audio |
| **Output** | Video with synced lips | New video from photo |
| **Use Case** | Dubbing, audio replacement | Avatar generation, spokesperson |

**Decision rule:** If you already have video footage of the person speaking, use `lip_sync`. If you only have a photograph and want to make it talk, use `talking_head`.

## Model Selection Guide

| Model | Quality | Speed | Best For |
|-------|---------|-------|----------|
| `wav2lip` | Good lip sync, may blur chin | Faster | Quick dubbing, drafts |
| `wav2lip_gan` | Better visual quality around mouth | Slower | Final renders, close-ups |

**Decision rule:** Use `wav2lip` for iteration and drafts. Switch to `wav2lip_gan` for final renders or any shot where the face is prominent (close-ups, medium shots). The quality difference is most visible in the mouth and chin region.

## Input Requirements

- Video must contain a clearly visible face throughout
- Face should be front-facing or at most 30-degree angle
- Minimum face size: ~100px across
- Audio should be clean speech (not music or noise)
- Audio length should roughly match video length (within 10%)

## Face Padding

Face padding controls how much area around the detected face is included in the sync region. Format: `[top, bottom, left, right]`.

| Scenario | Padding | Reason |
|----------|---------|--------|
| Default talking-head shot | `[0, 10, 0, 0]` | Works for 90% of footage |
| Chin being cut off | Increase index 1 (bottom) | Extends the mask below the chin |
| Forehead getting cropped | Increase index 0 (top) | Extends the mask above the forehead |
| Face off-center in frame | Adjust indices 2, 3 (left, right) | Compensates for lateral offset |

Keep left/right at 0 unless the face is noticeably off-center in the frame.

## Resize Factor

| Value | Resolution | Quality | Speed | Use Case |
|-------|-----------|---------|-------|----------|
| 1 | Full | Best | Slowest | Final renders |
| 2 | Half | Good | Faster | Drafts, iteration |
| 3+ | Reduced | Degraded | Fastest | Quick previews only |

**Recommendation:** Use `resize_factor=2` during iteration, `resize_factor=1` for final output.

## Common Workflows

### 1. Localization Dubbing

Translate a video into another language with matched lip movements.

```
transcriber(video) --> transcript
  --> translate script to target language
--> tts_selector(translated_script, target_language_voice)
  --> lip_sync(original_video, translated_audio)
```

### 2. Audio Re-Record

Replace narration audio and re-sync the speaker's lips.

```
new_audio_recording
  --> lip_sync(original_video, new_audio)
  --> face_enhance (post-sync cleanup)
  --> compose
```

### 3. Multi-Language Output

Produce multiple language versions from a single source video.

```
source_video
  --> lip_sync(source_video, english_audio)   --> english_output
  --> lip_sync(source_video, spanish_audio)   --> spanish_output
  --> lip_sync(source_video, french_audio)    --> french_output
```

Keep the original video as the source for each language -- do not chain lip_sync outputs.

## Quality Checklist

Before moving to the compose stage, verify each lip_sync output:

- [ ] **Lip movements match the new audio naturally** -- no desync or lag
- [ ] **No visual artifacts around the mouth/chin area** -- no blurring, smearing, or color mismatch
- [ ] **Face region blends seamlessly with the rest of the frame** -- no visible boundary
- [ ] **No temporal flickering between frames** -- smooth frame-to-frame transitions
- [ ] **Audio-visual sync is tight** -- no perceptible delay between mouth movement and sound

## Applying to Balamonis Studio

When using the `lip_sync` tool in post-production:

1. **Generate the replacement audio FIRST** (`tts_selector`, `elevenlabs_tts`, `openai_tts`, or `piper_tts`), then lip sync -- lip_sync requires finished audio as input
2. **Use `wav2lip` for drafts and iteration, `wav2lip_gan` for final renders** -- save processing time during the creative loop
3. **Apply `face_enhance` AFTER lip_sync, not before** -- lip_sync modifies the face region, so enhancing before sync is wasted work
4. **For localization workflows, keep the original video as source** and sync each language separately -- never chain lip_sync outputs
5. **Check that audio length matches video length before syncing** -- trim or pad audio if needed to stay within 10% of video duration
6. **Face padding `[0, 10, 0, 0]` works for 90% of talking-head footage** -- only adjust if you see cropping artifacts
7. **For close-up shots, always use `wav2lip_gan`** -- the quality difference is visible at this framing
