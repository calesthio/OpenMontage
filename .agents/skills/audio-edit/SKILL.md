---
name: audio-edit
description: Use for audio editing operations with FFmpeg: trimming, concatenation, normalization, loudness measurement, true-peak limiting, sample rate/channel conversion, and audio mixing.
---

# Audio Edit — Layer 3 (FFmpeg)

## Scope
FFmpeg-based audio processing: loudnorm (EBU R128 two-pass), alimiter, aresample, amix, sidechaincompress, atrim, asetpts, ebur128. No API keys, no network, no model downloads.

## Key filters
- `loudnorm=print_format=json` — measure integrated loudness, LRA, true peak
- `loudnorm=I=...:TP=...:LRA=...:measured_I=...` — apply normalization with measured values
- `alimiter=limit=1:level=1` — true-peak safety limiter
- `aresample=44100` — sample rate conversion
- `amix=inputs=2:duration=first` — mix multiple audio streams
- `sidechaincompress=threshold=...:ratio=...` — ducking music under narration
- `ebur128` — loudness analysis (EBU R128)

## Safety rules
- Always probe input with ffprobe before processing (sample rate, channels, duration)
- Use argument arrays, never shell-concatenated untrusted paths
- Write to temp path, validate output, then atomically rename
- Preserve source media; do not overwrite originals
- Handle missing audio streams, variable sample rates, odd channel layouts
- Fail-closed: if loudnorm measurement is unparsable or filter missing, return BLOCKED
- Record command, tool version, input/output hashes, exit code in job report

## Typical two-pass workflow
1. Measure: `ffmpeg -i input -af loudnorm=print_format=json -f null -`
2. Apply: `ffmpeg -i input -af loudnorm=I=-14:TP=-1.5:LRA=11:measured_I=...:measured_LRA=...:measured_TP=... -c:a pcm_s16le output`
