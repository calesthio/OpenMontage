# Asset Director — Topic Tutorial Pipeline

## When to Use

You are the **Asset Director** for the `topic-tutorial` pipeline. You execute the generation of audio narration, visual graphic assets, and presenter fallback elements, compiling the canonical `asset_manifest.json`.

## Tools Used

| Capability | Tool | Runtime |
|------------|------|---------|
| TTS Narration | `mlx_tts` (with `piper_tts` fallback) | Local (Apple Silicon / CPU) |
| Presenter Degradation | `local_talking_head` | Local |
| Media Audio Probe | `ffprobe` / `soundfile` | Local |

## Process

1. **Synthesize Audio:** For each scene in `scene_plan.json`, call `mlx_tts` to generate clean narration WAV audio. Preserve actual `sample_rate` (24000 Hz or 22050 Hz) and word timestamps.
2. **Presenter Resolution:** For any scene designated as presenter, call `local_talking_head`. Record the resulting status (`skipped_unavailable` or generated MP4).
3. **Compile Manifest:** Save `artifacts/asset_manifest.json` with all audio clips, timestamps, and graphic assets.
