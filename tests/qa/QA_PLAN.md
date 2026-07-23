# Quality Validation Plan — Phase 3.5 + G3.11

## Purpose

Run every tool with real API keys, inspect outputs (see images, listen to audio, watch video), find gaps, fix them. This is the gate before calling Phase 3.5 "Verified."

## Test Scripts (all ready to run)

| Script | Tools Tested | API Keys Used | Est. Cost |
|--------|-------------|---------------|-----------|
| `test_01_tts.py` | `elevenlabs_tts` (ElevenLabs) | ELEVENLABS_API_KEY | ~$0.02 |
| `test_02_image_gen.py` | `image_gen` (GPT Image 2 + FLUX) | OPENAI_API_KEY, FAL_AI_API_KEY | ~$0.15 |
| `test_03_music.py` | `music_gen` (ElevenLabs) | ELEVENLABS_API_KEY | ~$0.10 |
| `test_04_audio_mix.py` | `audio_mixer` | None (ffmpeg only) | $0 |
| `test_05_video_compose.py` | `video_compose` | None (ffmpeg only) | $0 |
| `test_06_video_stitch.py` | `video_stitch` | None (ffmpeg only) | $0 |
| `test_07_playbook_intelligence.py` | `playbook_loader.py` functions | None (pure Python) | $0 |
| `test_08_end_to_end.py` | Full animated-explainer pipeline | None (ffmpeg fixtures) | $0 |

## Inspection Protocol

For each output:
1. **Audio files**: Use `ffprobe` for format/duration/channels, then LISTEN (play in media player or use Whisper to verify content matches prompt)
2. **Image files**: Use `ffprobe` for dimensions, then VIEW (open image, check composition, text readability, style match)
3. **Video files**: Use `ffprobe` for resolution/fps/duration/codec, then WATCH (check A/V sync, transitions, subtitle timing)
4. **Design intelligence**: Run against all 3 playbooks, verify contrast ratios match manual calculation, check CVD warnings are accurate

## Known Risk Areas

| Area | Risk | How to Validate |
|------|------|-----------------|
| TTS voice selection | Default voice may not match playbook mood | Test with multiple voice IDs, compare against playbook `voice_style` |
| Image gen consistency | GPT Image/FLUX outputs vary wildly per prompt | Test with playbook `image_prompt_prefix` prepended |
| Music duration alignment | Music may not match narration duration | Compare `music.duration` vs `tts.duration`, check padding/looping |
| Audio ducking timing | Ducking may cut music too aggressively | Inspect waveform: music should duck ~6dB under speech, recover smoothly |
| Video stitch transitions | Crossfade may flicker with mismatched codecs | Test with both matching and mismatched clips, check `auto_normalize` |
| Subtitle burn-in | Font size/position may clip on mobile formats | Test with 9:16 (TikTok) and 16:9 (YouTube) profiles |
| Remotion render | Components may fail with real data | Build a test composition with all 8 components, render at 1080p |
| Playbook contrast | Edge cases in dark-on-dark or light-on-light themes | Test with all 3 playbooks + a deliberately low-contrast custom one |

## Run Order

```bash
cd C:/Users/ishan/Documents/OpenMontage

# Phase 1: Individual tools (can run in parallel)
python tests/qa/test_01_tts.py
python tests/qa/test_02_image_gen.py
python tests/qa/test_03_music.py

# Phase 2: Composition (depends on Phase 1 outputs)
python tests/qa/test_04_audio_mix.py
python tests/qa/test_05_video_compose.py
python tests/qa/test_06_video_stitch.py

# Phase 3: Intelligence validation (no API calls)
python tests/qa/test_07_playbook_intelligence.py

# Phase 4: Full pipeline
python tests/qa/test_08_end_to_end.py
```

## Success Criteria

- [ ] All 3 TTS samples: clear speech, correct content, no artifacts, ≥44.1kHz
- [ ] All 4 images: match prompt intent, correct dimensions, no watermarks, good composition
- [ ] Both music tracks: match mood prompt, correct duration (±2s), no abrupt cuts
- [ ] Audio mix: speech clearly above music, ducking smooth, no clipping
- [ ] Video compose: A/V sync within 50ms, correct resolution, playable in VLC
- [ ] Video stitch: smooth transitions, no frame drops, PIP correctly positioned
- [ ] Playbook intelligence: all 3 playbooks pass a11y, contrast ratios within 0.1 of manual calc
- [ ] End-to-end: 60-second explainer renders without errors, all stages checkpoint correctly
