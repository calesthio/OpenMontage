---
name: beam-production-orchestrator
description: Automatic tool selection for OpenMontage production runs with Reflection Beam 1.0. Use for every episode to choose research, storyboard, animation, audio, motion, render, and QC tools.
---

# Beam production orchestrator

For every episode, apply tools in this order:

Research → Script → Fact-checking → Storyboard → Nano Banana → Stickman Rig → Scientific Animation → Kokoro → Audio Sync → Motion Design → Remotion → FFmpeg → Final QC.

Tool selection:
- Research: `youtube_competitor_research`, `transcript_fetcher`, `video_downloader`, web evidence.
- Storyboard: use animate/motion-graphics principles; no new renderer.
- Scientific animation: `math_animate` (if available) or `diagram_gen`.
- Audio: `kokoro_tts`/`piper_tts`, `audio_mixer`, `subtitle_gen`.
- Motion/Render: Remotion + FFmpeg only.
- QC: `visual_qa`, `qc`, frame sampling, blackdetect/freezedetect/silencedetect/ebur128.

Rules:
- Keep Zero-Cost Gate, --no-spend, MCP Security Proxy enabled.
- No paid APIs; no second renderer.
- Preserve P0–P5; do not modify yt-* skills.
- Record decisions in decision_log and checkpoints.
- Human approval required for publish and mass generation.
