# Reference Video Analysis — Analyze Director

Analyze the local reference video without changing it.

Use FFmpeg-backed tools to probe video duration, dimensions, and frame rate. Use `scene_detect` for scene boundaries and `frame_sampler` for representative keyframes. Use `video_analyzer` when available for richer visual summaries.

If scene detection is unavailable or weak, use fixed-interval segmentation and mark the method as `fixed_interval_fallback`. Output `reference_analysis` with metadata, scenes, keyframe paths, and analysis limitations.
