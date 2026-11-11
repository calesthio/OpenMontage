# Quality Validation Plan

## Purpose

Run tools on real media, inspect the outputs (look at frames, listen to audio, watch video), find gaps, fix them.

## Test Scripts

`test_04`–`test_08` are standalone scripts, not pytest tests: run each with `python`. They write to `tests/qa/output/` (gitignored), print what they produced, and **exit 1 when any step fails** (0 otherwise), so a CI step or shell `&&` chain notices a failure. `tests/qa/conftest.py` keeps pytest from importing them, which used to run every script during collection of the main suite and hide its failures.

`test_09` is a pytest module (HyperFrames scaffold, lint/validate, full render); it skips when the HyperFrames runtime is missing.

| Script | Tools Tested | API Keys Used | Est. Cost |
|--------|-------------|---------------|-----------|
| `test_04_audio_mix.py` | `audio_mixer` | None (ffmpeg only) | $0 |
| `test_05_video_compose.py` | `video_compose` (incl. subtitle burn-in) | None (ffmpeg only) | $0 |
| `test_06_video_stitch.py` | `video_stitch` | None (ffmpeg only) | $0 |
| `test_07_playbook_intelligence.py` | `styles/playbook_loader.py` functions | None (pure Python) | $0 |
| `test_08_end_to_end.py` | animated-explainer flow on ffmpeg fixtures | None (ffmpeg fixtures) | $0 |
| `test_09_hyperframes_compose.py` | `hyperframes_compose` | None (Node + HyperFrames CLI) | $0 |

Paid-provider checks (TTS, image and music generation) have no scripts here; exercise those tools through a pipeline run with the user's approval.

FFmpeg features: the subtitle burn-in steps in `test_05` need the `subtitles` filter (libass). Check with `.venv/bin/python -c "from tools.ffmpeg_capabilities import has_filter; print(has_filter('subtitles'))"`; on a build without it those steps fail, and the script exits 1.

## Inspection Protocol

For each output:
1. **Audio files**: Use `ffprobe` for format/duration/channels, then LISTEN (play in media player or use Whisper to verify content matches prompt)
2. **Image files**: Use `ffprobe` for dimensions, then VIEW (open image, check composition, text readability, style match)
3. **Video files**: Use `ffprobe` for resolution/fps/duration/codec, then WATCH (check A/V sync, transitions, subtitle timing)
4. **Design intelligence**: Run against all 3 playbooks, verify contrast ratios match manual calculation, check CVD warnings are accurate

## Known Risk Areas

| Area | Risk | How to Validate |
|------|------|-----------------|
| Music duration alignment | Music may not match narration duration | Compare durations; use `audio_mixer` track `loop` / `offset_seconds` |
| Audio ducking timing | Ducking may cut music too aggressively | Inspect waveform: music should duck under speech, recover smoothly |
| Video stitch transitions | Crossfade may flicker with mismatched codecs | Test with both matching and mismatched clips, check `auto_normalize` |
| Subtitle burn-in | Font size/position may clip on mobile formats | Test with 9:16 (TikTok) and 16:9 (YouTube) profiles |
| Remotion render | Components may fail with real data | `make demo`, then a composition with every component |
| Playbook contrast | Edge cases in dark-on-dark or light-on-light themes | Test with all 3 playbooks + a deliberately low-contrast custom one |

## Run Order

From the repository root:

```bash
# Composition
.venv/bin/python tests/qa/test_04_audio_mix.py
.venv/bin/python tests/qa/test_05_video_compose.py
.venv/bin/python tests/qa/test_06_video_stitch.py

# Intelligence validation (no media)
.venv/bin/python tests/qa/test_07_playbook_intelligence.py

# Full flow
.venv/bin/python tests/qa/test_08_end_to_end.py

# HyperFrames (pytest)
.venv/bin/python -m pytest tests/qa/test_09_hyperframes_compose.py -q
```

## Success Criteria

- [ ] Every script exits 0
- [ ] Audio mix: speech clearly above music, ducking smooth, no clipping
- [ ] Video compose: A/V sync within 50ms, correct resolution, playable in VLC
- [ ] Video stitch: smooth transitions, no frame drops, PIP correctly positioned
- [ ] Playbook intelligence: all 3 playbooks pass a11y, contrast ratios within 0.1 of manual calc
- [ ] End-to-end: renders without errors, all stages checkpoint correctly
