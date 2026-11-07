---
name: video-pipeline-ffmpeg
description: Use when implementing media ingestion, probing, transcoding, trimming, concatenation, audio mixing, subtitles, proxy creation, normalization, thumbnail extraction or batch video processing with FFmpeg/ffprobe.
---

# FFmpeg pipeline engineering

- Inspect installed `ffmpeg` and `ffprobe` versions before relying on a flag.
- Use `ffprobe -v error -show_streams -show_format -of json` to inspect input media.
- Normalize inputs to explicit profiles: resolution, pixel format, frame rate, codec, sample rate, channel layout and color handling.
- Prefer argument arrays in subprocess calls; never interpolate untrusted paths into a shell command.
- Make temporary outputs unique, write to a temp path, validate output, then atomically rename.
- Preserve source media; do not overwrite originals.
- Handle variable frame rate, rotation metadata, missing audio, odd dimensions, corrupt files and Unicode paths.
- Use explicit filters and stream maps; do not assume every input has audio or the same codec.
- Add timeouts, cancellation, structured stderr capture and bounded retries.
- Use ffprobe after render to validate duration, dimensions, frame rate, streams and codec.
- Record command, tool version, input/output hashes and exit code in a job report.
- Check FFmpeg build configuration and licensing obligations before redistributing binaries.
