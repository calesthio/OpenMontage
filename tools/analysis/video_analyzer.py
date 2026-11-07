"""Video analyzer tool — comprehensive reference video analysis.

Orchestrates multiple analysis tools to produce a VideoAnalysisBrief from a
video URL or local file. Runs entirely locally with zero API keys: yt-dlp for
download, youtube-transcript-api for captions, PySceneDetect/FFmpeg for scene
detection, FFmpeg for frame extraction, and faster-whisper for transcription.

The agent's own vision model analyzes extracted keyframes — this tool provides
the structured data; the agent provides the visual interpretation.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
    ToolRuntime,
)


class VideoAnalyzer(BaseTool):
    name = "video_analyzer"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "multi"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffmpeg"]
    install_instructions = (
        "Core: FFmpeg is required (https://ffmpeg.org/download.html)\n"
        "For URL downloads: pip install yt-dlp\n"
        "For YouTube transcripts: pip install youtube-transcript-api\n"
        "For local transcription: pip install faster-whisper\n"
        "For scene detection: pip install scenedetect[opencv]\n"
        "All dependencies are free and local — no API keys needed."
    )
    agent_skills = ["video-understand", "ffmpeg"]

    capabilities = [
        "analyze_reference_video",
        "extract_structure",
        "extract_style",
        "extract_transcript",
    ]

    best_for = [
        "comprehensive video analysis",
        "reference video understanding",
        "style extraction from example video",
        "understanding video structure and pacing",
    ]

    not_good_for = [
        "editing or modifying video",
        "generating new video content",
    ]

    input_schema = {
        "type": "object",
        "required": ["source"],
        "properties": {
            "source": {
                "type": "string",
                "description": "Video file path or URL (YouTube, Shorts, Instagram, TikTok)",
            },
            "analysis_depth": {
                "type": "string",
                "enum": ["transcript_only", "standard", "deep"],
                "default": "standard",
                "description": (
                    "transcript_only: transcript + metadata only. "
                    "standard: + scene detection + keyframes + audio energy. "
                    "deep: + intra-scene sampling + detailed style extraction."
                ),
            },
            "max_keyframes": {
                "type": "integer",
                "default": 20,
                "minimum": 1,
                "maximum": 50,
                "description": "Maximum keyframes to extract",
            },
            "output_dir": {
                "type": "string",
                "description": "Directory for analysis outputs (default: auto-generated)",
            },
        },
    }

    output_schema = {
        "type": "object",
        "description": "VideoAnalysisBrief artifact — see schemas/artifacts/video_analysis_brief.schema.json",
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=2048, vram_mb=0, disk_mb=3000,
        network_required=False,  # Only needed for URL sources
    )
    idempotency_key_fields = ["source", "analysis_depth"]
    side_effects = [
        "downloads video to output_dir (if URL)",
        "writes keyframe images to output_dir/keyframes/",
        "writes analysis JSON to output_dir/video_analysis_brief.json",
    ]
    fallback_tools = []
    user_visible_verification = [
        "Review keyframe images for representative coverage",
        "Check transcript accuracy against video",
        "Verify scene boundaries look correct",
    ]

    def _is_url(self, source: str) -> bool:
        """Check if source is a URL vs local file."""
        return source.startswith(("http://", "https://", "www."))

    def _detect_platform(self, source: str) -> str:
        """Detect platform from URL."""
        if not self._is_url(source):
            return "local_file"
        s = source.lower()
        if "youtube.com/shorts" in s:
            return "shorts"
        if "youtube.com" in s or "youtu.be" in s:
            return "youtube"
        if "instagram.com" in s:
            return "instagram"
        if "tiktok.com" in s:
            return "tiktok"
        return "other_url"

    def _is_youtube(self, platform: str) -> bool:
        return platform in ("youtube", "shorts")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        source = inputs["source"]
        depth = inputs.get("analysis_depth", "standard")
        max_keyframes = inputs.get("max_keyframes", 20)

        # Setup output directory
        if inputs.get("output_dir"):
            output_dir = Path(inputs["output_dir"])
        else:
            output_dir = Path("projects/_analysis") / f"analysis_{int(time.time())}"
        output_dir.mkdir(parents=True, exist_ok=True)

        platform = self._detect_platform(source)
        is_url = self._is_url(source)
        start = time.time()

        # Initialize brief structure
        brief = {
            "version": "1.0",
            "source": {
                "type": platform,
                "duration_seconds": 0,
            },
            "content_analysis": {
                "summary": "",
                "topics": [],
                "target_audience": "general",
            },
            "structure_analysis": {
                "total_scenes": 0,
                "scenes": [],
                "pacing_profile": {},
            },
        }

        if is_url:
            brief["source"]["url"] = source
        else:
            brief["source"]["local_path"] = source

        # Track what succeeded and what failed
        steps_completed = []
        steps_failed = []

        # ─── STEP 1: Get metadata + download (if URL) ───
        video_path = None
        audio_path = None
        metadata = {}

        if is_url:
            try:
                from tools.analysis.video_downloader import VideoDownloader
                downloader = VideoDownloader()

                if depth == "transcript_only" and self._is_youtube(platform):
                    # Only get metadata, skip video download
                    dl_result = downloader.execute({
                        "url": source,
                        "output_dir": str(output_dir),
                        "format": "metadata_only",
                    })
                else:
                    dl_result = downloader.execute({
                        "url": source,
                        "output_dir": str(output_dir),
                        "format": "video",
                        "max_resolution": "720p",
                    })

                if dl_result.success:
                    metadata = dl_result.data.get("metadata", {})
                    video_path = dl_result.data.get("video_path")
                    audio_path = dl_result.data.get("audio_path")
                    brief["source"]["title"] = metadata.get("title", "")
                    brief["source"]["duration_seconds"] = metadata.get("duration", 0)
                    brief["source"]["resolution"] = metadata.get("resolution", "")
                    brief["source"]["platform_metadata"] = {
                        "uploader": metadata.get("uploader", ""),
                        "upload_date": metadata.get("upload_date", ""),
                        "view_count": metadata.get("view_count", 0),
                        "like_count": metadata.get("like_count", 0),
                        "description": metadata.get("description", ""),
                    }
                    steps_completed.append("metadata")
                    if video_path:
                        steps_completed.append("download")
                else:
                    steps_failed.append(f"download: {dl_result.error}")
            except Exception as e:
                steps_failed.append(f"download: {e}")
        else:
            # Local file
            local_path = Path(source)
            if not local_path.exists():
                return ToolResult(
                    success=False,
                    error=f"Local file not found: {source}",
                )
            video_path = str(local_path)
            # Get duration via ffprobe
            try:
                duration = self._get_duration(local_path)
                brief["source"]["duration_seconds"] = duration
                brief["source"]["title"] = local_path.stem
                steps_completed.append("metadata")
            except Exception as e:
                steps_failed.append(f"metadata: {e}")

        # ─── STEP 2: Get transcript ───
        transcript_data = None

        # Try youtube-transcript-api first (instant, for YouTube)
        if self._is_youtube(platform):
            try:
                from youtube_transcript_api import YouTubeTranscriptApi

                from tools.analysis.transcript_fetcher import TranscriptFetcher
                fetcher = TranscriptFetcher()

                # Auto-detect available languages instead of hardcoding "en"
                languages_to_try = ["en"]
                try:
                    ytt = YouTubeTranscriptApi()
                    available = ytt.list(fetcher._extract_video_id(source))
                    # Build priority list: manual first, then auto-generated
                    lang_codes = []
                    for t in available:
                        code = t.language_code if hasattr(t, "language_code") else str(t)
                        if code not in lang_codes:
                            lang_codes.append(code)
                    if lang_codes:
                        languages_to_try = lang_codes
                except Exception:
                    pass  # Fall through to default ["en"]

                tf_result = fetcher.execute({
                    "url_or_video_id": source,
                    "languages": languages_to_try,
                    "include_auto_generated": True,
                })
                if tf_result.success:
                    transcript_data = tf_result.data
                    brief["narration_transcript"] = {
                        "full_text": transcript_data.get("full_text", ""),
                        "segments": transcript_data.get("transcript", []),
                        "language": transcript_data.get("language", "en"),
                        "word_count": transcript_data.get("word_count", 0),
                    }
                    steps_completed.append("transcript_youtube")
            except Exception as e:
                steps_failed.append(f"transcript_youtube: {e}")

        # Fallback: If transcript failed and we don't have audio yet,
        # download the video to get audio for Whisper transcription
        if transcript_data is None and audio_path is None and video_path is None and is_url:
            try:
                from tools.analysis.video_downloader import VideoDownloader
                downloader = VideoDownloader()
                dl_result = downloader.execute({
                    "url": source,
                    "output_dir": str(output_dir),
                    "format": "video",
                    "max_resolution": "720p",
                })
                if dl_result.success:
                    video_path = dl_result.data.get("video_path")
                    audio_path = dl_result.data.get("audio_path")
                    if video_path:
                        steps_completed.append("download_for_whisper")
                    # Also update metadata if we didn't have it
                    if not metadata:
                        metadata = dl_result.data.get("metadata", {})
                        brief["source"]["title"] = metadata.get("title", "")
                        brief["source"]["duration_seconds"] = metadata.get("duration", 0)
            except Exception as e:
                steps_failed.append(f"download_for_whisper: {e}")

        # Fallback: Whisper transcription on audio
        if transcript_data is None and audio_path:
            try:
                from tools.analysis.transcriber import Transcriber
                transcriber = Transcriber()
                # Let Whisper auto-detect language instead of assuming English
                tr_inputs = {
                    "input_path": audio_path,
                    "model_size": "base",
                    "output_dir": str(output_dir),
                }
                # Only set language if we know it from transcript attempt
                detected_lang = brief.get("narration_transcript", {}).get("language")
                if detected_lang and detected_lang != "en":
                    tr_inputs["language"] = detected_lang
                # else: let Whisper auto-detect

                tr_result = transcriber.execute(tr_inputs)
                if tr_result.success:
                    segments = tr_result.data.get("segments", [])
                    full_text = " ".join(s.get("text", "") for s in segments)
                    brief["narration_transcript"] = {
                        "full_text": full_text,
                        "segments": [
                            {
                                "start": s.get("start", 0),
                                "end": s.get("end", 0),
                                "text": s.get("text", ""),
                            }
                            for s in segments
                        ],
                        "language": tr_result.data.get("language", "en"),
                        "word_count": len(full_text.split()),
                    }
                    transcript_data = brief["narration_transcript"]
                    steps_completed.append("transcript_whisper")
            except Exception as e:
                steps_failed.append(f"transcript_whisper: {e}")

        # For transcript_only depth, we're done
        if depth == "transcript_only":
            brief["_analysis_meta"] = {
                "depth": depth,
                "steps_completed": steps_completed,
                "steps_failed": steps_failed,
                "duration_seconds": round(time.time() - start, 2),
            }
            self._save_brief(brief, output_dir)
            return ToolResult(
                success=True,
                data=brief,
                artifacts=[str(output_dir / "video_analysis_brief.json")],
                duration_seconds=round(time.time() - start, 2),
            )

        # ─── STEP 3: Scene detection (standard + deep) ───
        scenes = []
        if video_path:
            try:
                from tools.analysis.scene_detect import SceneDetect
                detector = SceneDetect()
                sd_result = detector.execute({
                    "input_path": video_path,
                    "method": "content",
                    "min_scene_length_seconds": 0.5,
                    "output_path": str(output_dir / "scenes.json"),
                })
                if sd_result.success:
                    scenes = sd_result.data.get("scenes", [])
                    steps_completed.append("scene_detect")
            except Exception as e:
                steps_failed.append(f"scene_detect: {e}")

        # Build scene list for the brief
        if scenes:
            brief["structure_analysis"]["total_scenes"] = len(scenes)
            brief_scenes = []
            for scene in scenes:
                brief_scenes.append({
                    "scene_index": scene.get("index", scene.get("scene_index", 0)),
                    "start_time": scene.get("start_seconds", 0),
                    "end_time": scene.get("end_seconds", 0),
                    "description": "",  # Agent fills this via vision
                    "visual_type": "other",  # Agent classifies via vision
                    "energy_level": "medium",
                })
            brief["structure_analysis"]["scenes"] = brief_scenes

            # Compute pacing profile
            durations = [
                s.get("end_seconds", 0) - s.get("start_seconds", 0)
                for s in scenes
            ]
            total_duration = brief["source"]["duration_seconds"] or sum(durations)
            if durations:
                brief["structure_analysis"]["pacing_profile"] = {
                    "avg_scene_duration_seconds": round(sum(durations) / len(durations), 2),
                    "shortest_scene_seconds": round(min(durations), 2),
                    "longest_scene_seconds": round(max(durations), 2),
                    "cuts_per_minute": round(len(durations) / (total_duration / 60), 2) if total_duration > 0 else 0,
                    "pacing_style": self._classify_pacing(durations),
                }

        # ─── STEP 3b: Motion classification per scene ───
        if video_path and scenes:
            try:
                motion_results = self._classify_scene_motion(video_path, scenes)
                for bs, mr in zip(brief["structure_analysis"]["scenes"], motion_results):
                    bs["motion_type"] = mr["motion_type"]
                    bs["flow_variance"] = mr["flow_variance"]
                steps_completed.append("motion_classification")
            except Exception as e:
                steps_failed.append(f"motion_classification: {e}")

        # ─── STEP 4: Keyframe extraction (scene-guided) ───
        keyframes = []
        keyframe_dir = output_dir / "keyframes"
        if video_path and scenes:
            try:
                # Extract keyframes at scene boundaries + midpoints
                timestamps = self._compute_keyframe_timestamps(scenes, max_keyframes, depth)

                from tools.analysis.frame_sampler import FrameSampler
                sampler = FrameSampler()
                fs_result = sampler.execute({
                    "input_path": video_path,
                    "strategy": "timestamps",
                    "timestamps": timestamps,
                    "output_dir": str(keyframe_dir),
                    "format": "jpg",
                    "quality": 2,
                })
                if fs_result.success:
                    for frame in fs_result.data.get("frames", []):
                        # Map each frame to its scene
                        scene_idx = self._timestamp_to_scene(
                            frame["timestamp_seconds"], scenes
                        )
                        keyframes.append({
                            "timestamp": frame["timestamp_seconds"],
                            "scene_index": scene_idx,
                            "path": frame["path"],
                            "description": "",  # Agent fills via vision
                        })
                    steps_completed.append("keyframes")
            except Exception as e:
                steps_failed.append(f"keyframes: {e}")
        elif video_path and not scenes:
            # No scene detection — fall back to count-based extraction
            try:
                from tools.analysis.frame_sampler import FrameSampler
                sampler = FrameSampler()
                fs_result = sampler.execute({
                    "input_path": video_path,
                    "strategy": "count",
                    "count": min(max_keyframes, 15),
                    "output_dir": str(keyframe_dir),
                    "format": "jpg",
                    "quality": 2,
                })
                if fs_result.success:
                    for frame in fs_result.data.get("frames", []):
                        keyframes.append({
                            "timestamp": frame["timestamp_seconds"],
                            "scene_index": 0,
                            "path": frame["path"],
                            "description": "",
                        })
                    steps_completed.append("keyframes_uniform")
            except Exception as e:
                steps_failed.append(f"keyframes_uniform: {e}")

        brief["keyframes"] = keyframes

        # ─── STEP 5: Audio energy analysis ───
        if audio_path or video_path:
            audio_source = audio_path or video_path
            try:
                from tools.analysis.audio_energy import AudioEnergy
                energy = AudioEnergy()
                ae_result = energy.execute({
                    "input_path": audio_source,
                    "video_duration_seconds": brief["source"]["duration_seconds"],
                })
                if ae_result.success:
                    # Store energy profile summary in style_profile
                    if "style_profile" not in brief:
                        brief["style_profile"] = {}
                    brief["style_profile"]["audio_energy_profile"] = {
                        "recommended_offset": ae_result.data.get("recommended_offset_seconds", 0),
                        "has_energy_data": True,
                    }
                    steps_completed.append("audio_energy")
            except Exception as e:
                steps_failed.append(f"audio_energy: {e}")

        # ─── STEP 6: Build replication guidance ───
        brief["replication_guidance"] = {
            "suggested_pipeline": self._suggest_pipeline(brief),
            "suggested_playbook": "flat-motion-graphics",
            "key_elements_to_replicate": [],  # Agent fills via analysis
            "elements_requiring_custom_work": [],
            "estimated_complexity": self._estimate_complexity(brief),
            "motion_required": self._needs_motion(brief),
            "creative_differentiation_seeds": [],  # Agent fills
        }

        # ─── STEP 7: Initialize style_profile ───
        if "style_profile" not in brief:
            brief["style_profile"] = {}

        # Narration style from transcript
        if transcript_data:
            duration = brief["source"]["duration_seconds"]
            wc = transcript_data.get("word_count", 0) if isinstance(transcript_data, dict) else brief.get("narration_transcript", {}).get("word_count", 0)
            wpm = round(wc / (duration / 60), 1) if duration > 0 else 0
            brief["style_profile"]["narration_style"] = {
                "has_narration": wc > 20,
                "speaker_count": 1,  # Agent refines via analysis
                "delivery_style": "",  # Agent fills
                "words_per_minute": wpm,
            }

        # Initialize remaining style fields for agent to fill
        brief["style_profile"].setdefault("color_palette", {
            "primary_colors": [],
            "accent_colors": [],
            "overall_mood": "",
        })
        brief["style_profile"].setdefault("typography_observed", "")
        brief["style_profile"].setdefault("transition_types", [])
        brief["style_profile"].setdefault("music_style", "")
        brief["style_profile"].setdefault("subtitle_style", "")
        brief["style_profile"].setdefault("production_quality", "prosumer")
        brief["style_profile"].setdefault("closest_playbook", "")
        brief["style_profile"].setdefault("playbook_delta", "")

        # ─── Finalize ───
        brief["_analysis_meta"] = {
            "depth": depth,
            "steps_completed": steps_completed,
            "steps_failed": steps_failed,
            "keyframe_count": len(keyframes),
            "scene_count": len(scenes),
            "has_transcript": transcript_data is not None,
            "duration_seconds": round(time.time() - start, 2),
        }

        self._save_brief(brief, output_dir)

        elapsed = time.time() - start
        artifacts = [str(output_dir / "video_analysis_brief.json")]
        if keyframe_dir.exists():
            artifacts.append(str(keyframe_dir))

        return ToolResult(
            success=True,
            data=brief,
            artifacts=artifacts,
            duration_seconds=round(elapsed, 2),
        )

    # ─── Helpers ───

    def _get_duration(self, video_path: Path) -> float:
        """Get video duration via ffprobe."""
        cmd = [
            "ffprobe", "-v", "quiet",
            "-show_entries", "format=duration",
            "-of", "json",
            str(video_path),
        ]
        result = self.run_command(cmd)
        data = json.loads(result.stdout)
        return float(data.get("format", {}).get("duration", 0))

    def _compute_keyframe_timestamps(
        self, scenes: list[dict], max_frames: int, depth: str
    ) -> list[float]:
        """Compute optimal keyframe timestamps from scene boundaries."""
        timestamps = []

        for scene in scenes:
            start = scene.get("start_seconds", 0)
            end = scene.get("end_seconds", 0)
            duration = end - start

            # First frame of each scene
            timestamps.append(start + 0.1)

            # Midpoint for scenes > 3 seconds
            if duration > 3.0:
                timestamps.append(start + duration / 2)

            # For deep analysis, add more intra-scene samples
            if depth == "deep" and duration > 6.0:
                timestamps.append(start + duration * 0.25)
                timestamps.append(start + duration * 0.75)

        # Deduplicate, sort, and limit
        timestamps = sorted(set(round(t, 3) for t in timestamps))
        if len(timestamps) > max_frames:
            # Uniform subsample to max_frames
            step = len(timestamps) / max_frames
            timestamps = [timestamps[int(i * step)] for i in range(max_frames)]

        return timestamps

    def _timestamp_to_scene(self, ts: float, scenes: list[dict]) -> int:
        """Map a timestamp to its scene index."""
        for scene in scenes:
            start = scene.get("start_seconds", 0)
            end = scene.get("end_seconds", 0)
            if start <= ts <= end:
                return scene.get("index", scene.get("scene_index", 0))
        return 0

    def _classify_pacing(self, durations: list[float]) -> str:
        """Classify pacing style from scene durations."""
        if not durations:
            return "variable"
        avg = sum(durations) / len(durations)
        if avg > 10:
            return "slow_contemplative"
        if avg > 5:
            return "steady_educational"
        if avg > 2:
            return "dynamic_social"
        return "rapid_fire"

    def _suggest_pipeline(self, brief: dict) -> str:
        """Suggest the best pipeline based on content analysis."""
        platform = brief["source"]["type"]
        pacing = brief["structure_analysis"].get("pacing_profile", {}).get("pacing_style", "")

        if platform in ("shorts", "tiktok", "instagram"):
            return "animation"  # Short-form → animation pipeline works well
        if pacing in ("slow_contemplative",):
            return "cinematic"
        return "animated-explainer"

    def _estimate_complexity(self, brief: dict) -> str:
        """Estimate how complex it would be to recreate this style."""
        scenes = brief["structure_analysis"]["total_scenes"]
        duration = brief["source"]["duration_seconds"]

        if duration > 300 or scenes > 30:
            return "complex"
        if duration > 120 or scenes > 15:
            return "moderate"
        return "simple"

    def _needs_motion(self, brief: dict) -> bool:
        """Determine if motion (video gen or Remotion) is required."""
        # If we have per-scene motion data, use it — majority motion_clip = motion required
        scenes = brief["structure_analysis"].get("scenes", [])
        motion_scenes = [s for s in scenes if s.get("motion_type") == "motion_clip"]
        if scenes and motion_scenes:
            return len(motion_scenes) / len(scenes) >= 0.3
        # Fallback to pacing heuristic
        pacing = brief["structure_analysis"].get("pacing_profile", {}).get("pacing_style", "")
        return pacing in ("dynamic_social", "rapid_fire")

    def _classify_scene_motion(
        self, video_path: str, scenes: list[dict]
    ) -> list[dict]:
        """Classify each scene as static_image, animated_still, or motion_clip.

        Samples 2-3 frame pairs per scene and computes dense optical flow
        variance using Farneback. Low uniform flow = pan/zoom on a still.
        High heterogeneous flow = real character/object motion.
        """
        import numpy as np

        try:
            import cv2
        except ImportError:
            return [{"motion_type": "unknown", "flow_variance": -1}] * len(scenes)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return [{"motion_type": "unknown", "flow_variance": -1}] * len(scenes)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        results = []

        for scene in scenes:
            start = scene.get("start_seconds", 0)
            end = scene.get("end_seconds", 0)
            duration = end - start

            if duration < 0.3:
                results.append({"motion_type": "static_image", "flow_variance": 0.0})
                continue

            # Sample 2-3 frame pairs spaced across the scene
            gap = min(0.4, duration / 3)
            sample_times = [start + duration * p for p in (0.25, 0.5, 0.75) if start + duration * p + gap <= end]
            if not sample_times:
                sample_times = [start + 0.1]

            flow_variances = []
            flow_mag_means = []

            for t in sample_times:
                frame_a = self._read_frame_at(cap, t, fps)
                frame_b = self._read_frame_at(cap, t + gap, fps)
                if frame_a is None or frame_b is None:
                    continue

                # Downscale to 360p height for speed
                h, w = frame_a.shape[:2]
                scale = 360 / h if h > 360 else 1.0
                if scale < 1.0:
                    dim = (int(w * scale), 360)
                    frame_a = cv2.resize(frame_a, dim)
                    frame_b = cv2.resize(frame_b, dim)

                gray_a = cv2.cvtColor(frame_a, cv2.COLOR_BGR2GRAY)
                gray_b = cv2.cvtColor(frame_b, cv2.COLOR_BGR2GRAY)

                flow = cv2.calcOpticalFlowFarneback(
                    gray_a, gray_b, None,
                    pyr_scale=0.5, levels=3, winsize=15,
                    iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
                )

                mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
                flow_mag_means.append(float(np.mean(mag)))
                # Variance of magnitude = heterogeneity of motion
                flow_variances.append(float(np.var(mag)))

            if not flow_variances:
                results.append({"motion_type": "unknown", "flow_variance": -1})
                continue

            avg_variance = sum(flow_variances) / len(flow_variances)
            avg_magnitude = sum(flow_mag_means) / len(flow_mag_means)

            # Classification thresholds (tuned for 360p, 0.4s gap):
            # - static_image: near-zero flow (no motion at all)
            # - animated_still: uniform flow (pan/zoom on a still image)
            # - motion_clip: heterogeneous flow (objects moving independently)
            if avg_magnitude < 0.5:
                motion_type = "static_image"
            elif avg_variance < 2.0:
                motion_type = "animated_still"
            else:
                motion_type = "motion_clip"

            results.append({
                "motion_type": motion_type,
                "flow_variance": round(avg_variance, 3),
            })

        cap.release()
        return results

    def _read_frame_at(self, cap, timestamp: float, fps: float):
        """Read a single frame at the given timestamp."""
        import cv2
        frame_num = int(timestamp * fps)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
        ret, frame = cap.read()
        return frame if ret else None

    def _save_brief(self, brief: dict, output_dir: Path) -> None:
        """Save the VideoAnalysisBrief to disk."""
        out_path = output_dir / "video_analysis_brief.json"
        # Remove non-serializable items
        clean_brief = {k: v for k, v in brief.items()}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(clean_brief, f, indent=2, default=str)
