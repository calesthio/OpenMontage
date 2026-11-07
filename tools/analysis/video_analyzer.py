"""Video analyzer tool — comprehensive reference video analysis.

Orchestrates multiple analysis tools to produce a VideoAnalysisBrief from a
video URL or local file. Runs entirely locally with zero API keys: yt-dlp for
download, youtube-transcript-api for captions, PySceneDetect/FFmpeg for scene
detection, FFmpeg for frame extraction, and faster-whisper for transcription.

The agent's own vision model analyzes extracted keyframes — this tool provides
the structured data; the agent provides the visual interpretation.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolStatus,
    ToolTier,
    ToolRuntime,
)


class VideoAnalyzer(BaseTool):
    name = "video_analyzer"
    version = "0.2.0"
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
        "description": "VideoAnalysisBrief artifact — see the versioned artifact schema.",
    }
    artifact_schema = {"artifact": "video_analysis_brief", "version": "1.1"}

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=2048, vram_mb=0, disk_mb=3000,
        network_required=False,  # Only needed for URL sources
    )
    idempotency_key_fields = ["source", "analysis_depth", "max_keyframes", "output_dir"]
    side_effects = [
        "downloads video to output_dir (if URL)",
        "writes keyframe images to output_dir/keyframes/",
        "writes normalized source audio to output_dir/source_audio.wav (local sources)",
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

    def _source_fingerprint(self, source: str) -> dict[str, str]:
        """Return a stable content or locator fingerprint for one source."""
        path = Path(source)
        if not self._is_url(source) and path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return {"kind": "content", "algorithm": "sha256", "value": digest.hexdigest()}
        digest = hashlib.sha256(source.strip().encode("utf-8")).hexdigest()
        return {"kind": "locator", "algorithm": "sha256", "value": digest}

    def _source_surface(self, source: str, platform: str) -> tuple[str, str]:
        """Normalize platform and surface without changing legacy source.type."""
        if platform == "shorts":
            return "youtube", "shorts"
        if platform == "instagram":
            return "instagram", "reel" if "/reel" in source.lower() else "post"
        if platform == "tiktok":
            return "tiktok", "video"
        if platform == "local_file":
            return "local", "file"
        return platform, platform

    def _normalise_transcript_segments(self, segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize caption and Whisper segments into one stable time contract."""
        normalized = []
        for index, segment in enumerate(segments):
            start = float(segment.get("start", 0))
            raw_end = segment.get("end")
            if raw_end is None:
                raw_end = start + float(segment.get("duration", 0))
            end = float(raw_end)
            if end <= start:
                end = start + 0.001
            item: dict[str, Any] = {
                "id": f"segment-{index:04d}",
                "start": round(start, 3),
                "end": round(end, 3),
                "text": str(segment.get("text", "")).strip(),
            }
            for field in ("speaker", "words"):
                if field in segment:
                    item[field] = segment[field]
            normalized.append(item)
        return normalized

    def _build_five_aspect_observations(self, brief: dict[str, Any]) -> list[dict[str, Any]]:
        """Create an honest unknown scaffold for agent vision enrichment."""
        aspects = ("subject", "subject_motion", "scene", "spatial_framing", "camera")
        observations = []
        for scene in brief["structure_analysis"].get("scenes", []):
            scene_index = int(scene["scene_index"])
            ids = []
            for aspect in aspects:
                observation_id = f"obs-scene-{scene_index}-{aspect}"
                ids.append(observation_id)
                observations.append({
                    "id": observation_id,
                    "scene_index": scene_index,
                    "aspect": aspect,
                    "status": "unknown",
                    "value": "Not enriched by the analyzer; inspect the referenced keyframes.",
                    "evidence_refs": [],
                    "confidence": "low",
                })
            scene["observation_ids"] = ids
        return observations

    def _build_evidence(
        self,
        brief: dict[str, Any],
        output_dir: Path,
        source: str,
        steps_completed: list[str],
    ) -> list[dict[str, Any]]:
        """Build a typed evidence index from tool outputs without claiming vision findings."""
        evidence: list[dict[str, Any]] = [{
            "id": "ev-source-metadata",
            "kind": "source_metadata",
            "status": "available" if "metadata" in steps_completed else "unavailable",
            "source_ref": source,
            "description": "Source locator and technical metadata from the analysis run.",
        }]
        for scene in brief["structure_analysis"].get("scenes", []):
            evidence.append({
                "id": f"ev-scene-{scene['scene_index']}",
                "kind": "scene_detection",
                "status": "available" if "scene_detect" in steps_completed else "unavailable",
                "source_ref": str(output_dir / "scenes.json"),
                "start_seconds": scene["start_time"],
                "end_seconds": scene["end_time"],
                "scene_index": scene["scene_index"],
            })
        for segment in brief.get("narration_transcript", {}).get("segments", []):
            evidence.append({
                "id": f"ev-transcript-{segment['id']}",
                "kind": "transcript_segment",
                "status": "available",
                "source_ref": source,
                "start_seconds": segment["start"],
                "end_seconds": segment["end"],
                "excerpt": segment["text"],
            })
        for frame in brief.get("keyframes", []):
            evidence.append({
                "id": f"ev-keyframe-{frame['id']}",
                "kind": "keyframe",
                "status": "available" if "keyframes" in steps_completed or "keyframes_uniform" in steps_completed else "unavailable",
                "source_ref": frame["path"],
                "start_seconds": frame["timestamp"],
                "end_seconds": frame["timestamp"],
                "scene_index": frame["scene_index"],
            })
        if "audio_extract" in steps_completed:
            evidence.append({
                "id": "ev-audio-source",
                "kind": "audio_analysis",
                "status": "available",
                "source_ref": str(output_dir / "source_audio.wav"),
                "description": "Normalized local audio extracted for transcription and analysis.",
            })
        if "audio_energy" in steps_completed:
            evidence.append({
                "id": "ev-audio-energy",
                "kind": "audio_analysis",
                "status": "available",
                "source_ref": source,
                "description": "Audio energy profile produced by the local analyzer.",
            })
        return evidence

    def _extract_audio(self, video_path: Path, output_dir: Path) -> str:
        """Extract a stable mono WAV so local videos can use the transcript path."""
        audio_path = output_dir / "source_audio.wav"
        self.run_command([
            "ffmpeg", "-y", "-i", str(video_path),
            "-vn", "-ac", "1", "-ar", "16000", str(audio_path),
        ], timeout=120)
        if not audio_path.is_file():
            raise RuntimeError(f"FFmpeg did not create audio output: {audio_path}")
        return str(audio_path)

    def _record_failure(
        self,
        steps_failed: list[str],
        step: str,
        error: Any,
    ) -> None:
        """Record bounded diagnostics without copying raw subprocess logs."""
        summary = " ".join(str(error or "unknown failure").split())[:500]
        steps_failed.append(f"{step}: {summary}")

    def _has_transcript_content(self, brief: dict[str, Any]) -> bool:
        """Return whether transcript extraction yielded actual text or segments."""
        transcript = brief.get("narration_transcript", {})
        segments = transcript.get("segments", [])
        return bool(
            str(transcript.get("full_text", "")).strip()
            or any(
                isinstance(segment, dict) and str(segment.get("text", "")).strip()
                for segment in segments
            )
        )

    def _analysis_status(
        self,
        completed: list[str],
        failed: list[str],
        depth: str,
        has_transcript: bool,
        has_visual_scenes: bool,
        has_keyframes: bool,
    ) -> str:
        """Report completion against the requested depth, not incidental work."""
        if not completed:
            return "failed" if failed else "partial"
        if failed or "metadata" not in completed:
            return "partial"
        if depth == "transcript_only":
            has_transcript_step = any(step.startswith("transcript_") for step in completed)
            return "complete" if has_transcript and has_transcript_step else "partial"
        keyframe_steps = {"keyframes", "keyframes_uniform"}
        if (
            "scene_detect" not in completed
            or not keyframe_steps.intersection(completed)
            or not has_visual_scenes
            or not has_keyframes
        ):
            return "partial"
        if has_visual_scenes and "visual_enrichment" not in completed:
            return "partial"
        return "complete"

    def _finalize_v11_brief(
        self,
        brief: dict[str, Any],
        output_dir: Path,
        source: str,
        steps_completed: list[str],
        steps_failed: list[str],
        started_at: str,
        depth: str,
        has_transcript: bool,
    ) -> None:
        """Finalize v1.1 indexes and status before validation and persistence."""
        brief["five_aspect_observations"] = self._build_five_aspect_observations(brief)
        brief["evidence"] = self._build_evidence(brief, output_dir, source, steps_completed)
        brief["analysis_run"].update({
            "status": self._analysis_status(
                steps_completed,
                steps_failed,
                depth,
                has_transcript,
                bool(brief["structure_analysis"].get("scenes")),
                bool(brief.get("keyframes")),
            ),
            "steps_completed": list(steps_completed),
            "steps_failed": list(steps_failed),
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        })

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        source = str(inputs["source"])
        depth = inputs.get("analysis_depth", "standard")
        max_keyframes = inputs.get("max_keyframes", 20)

        fingerprint = self._source_fingerprint(source)
        analysis_id = f"analysis-{fingerprint['value'][:24]}"
        run_id = "run-" + hashlib.sha256(
            f"{analysis_id}:{depth}:{max_keyframes}:{self.version}".encode("utf-8")
        ).hexdigest()[:24]

        # Stable by source and analysis configuration. A caller may still
        # provide an explicit output_dir for a deliberate separate run.
        if inputs.get("output_dir"):
            output_dir = Path(inputs["output_dir"])
        else:
            output_dir = Path("projects/_analysis") / f"{analysis_id}_{depth}_{max_keyframes}"
        output_dir.mkdir(parents=True, exist_ok=True)

        platform = self._detect_platform(source)
        is_url = self._is_url(source)
        start = time.time()
        platform_name, surface = self._source_surface(source, platform)
        started_at = datetime.now(timezone.utc).isoformat()

        # Initialize the versioned brief. Vision enrichment may replace unknown
        # aspect values later, but it must never silently omit an aspect.
        brief = {
            "version": "1.1",
            "analysis_id": analysis_id,
            "source": {
                "type": platform,
                "platform": platform_name,
                "surface": surface,
                "duration_seconds": 0,
                "fingerprint": fingerprint,
                "rights_status": "unknown",
                "privacy_status": "review_required",
                "retention_policy": "caller_managed",
            },
            "analysis_run": {
                "id": run_id,
                "depth": depth,
                "status": "partial",
                "steps_completed": [],
                "steps_failed": [],
                "tool": {"name": self.name, "version": self.version},
                "config": {"analysis_depth": depth, "max_keyframes": max_keyframes},
                "started_at": started_at,
            },
            "evidence": [],
            "content_analysis": {
                "summary": "",
                "topics": [],
                "target_audience": "unknown",
            },
            "structure_analysis": {
                "total_scenes": 0,
                "scenes": [],
                "pacing_profile": {},
            },
            "five_aspect_observations": [],
            "assertions": [],
            "keyframes": [],
            "replication_guidance": {
                "suggested_pipeline": "",
                "suggested_playbook": "",
                "key_elements_to_replicate": [],
                "elements_requiring_custom_work": [],
                "estimated_complexity": "simple",
                "motion_required": False,
                "creative_differentiation_seeds": [],
                "preserve": [],
                "change": [],
                "avoid": [],
            },
            "style_profile": {},
        }

        if is_url:
            brief["source"]["url"] = source
        else:
            brief["source"]["local_path"] = source

        # Track what succeeded and what failed
        steps_completed: list[str] = []
        steps_failed: list[str] = []

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
                    brief["source"]["title"] = str(metadata.get("title") or "")
                    brief["source"]["duration_seconds"] = float(metadata.get("duration") or 0)
                    brief["source"]["resolution"] = str(metadata.get("resolution") or "")
                    brief["source"]["platform_metadata"] = {
                        "uploader": str(metadata.get("uploader") or ""),
                        "upload_date": str(metadata.get("upload_date") or ""),
                        "view_count": int(metadata.get("view_count") or 0),
                        "like_count": int(metadata.get("like_count") or 0),
                        "description": str(metadata.get("description") or ""),
                    }
                    steps_completed.append("metadata")
                    if video_path:
                        steps_completed.append("download")
                else:
                    self._record_failure(steps_failed, "download", dl_result.error)
            except Exception as e:
                self._record_failure(steps_failed, "download", e)
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
                self._record_failure(steps_failed, "metadata", e)

            try:
                audio_path = self._extract_audio(local_path, output_dir)
                steps_completed.append("audio_extract")
            except Exception as e:
                self._record_failure(steps_failed, "audio_extract", e)

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
                    segments = self._normalise_transcript_segments(
                        transcript_data.get("transcript", [])
                    )
                    brief["narration_transcript"] = {
                        "full_text": str(transcript_data.get("full_text") or ""),
                        "segments": segments,
                        "language": str(transcript_data.get("language") or "en"),
                        "word_count": int(transcript_data.get("word_count") or 0),
                    }
                    transcript_data = {**transcript_data, "transcript": segments}
                    steps_completed.append("transcript_youtube")
            except Exception as e:
                self._record_failure(steps_failed, "transcript_youtube", e)

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
                        brief["source"]["title"] = str(metadata.get("title") or "")
                        brief["source"]["duration_seconds"] = float(metadata.get("duration") or 0)
            except Exception as e:
                self._record_failure(steps_failed, "download_for_whisper", e)

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
                    normalized_segments = self._normalise_transcript_segments(segments)
                    brief["narration_transcript"] = {
                        "full_text": full_text,
                        "segments": normalized_segments,
                        "language": str(tr_result.data.get("language") or "en"),
                        "word_count": len(full_text.split()),
                    }
                    transcript_data = brief["narration_transcript"]
                    steps_completed.append("transcript_whisper")
            except Exception as e:
                self._record_failure(steps_failed, "transcript_whisper", e)

        # For transcript_only depth, we're done
        if depth == "transcript_only":
            self._finalize_v11_brief(
                brief,
                output_dir,
                source,
                steps_completed,
                steps_failed,
                started_at,
                depth,
                self._has_transcript_content(brief),
            )
            self._save_brief(brief, output_dir)
            return ToolResult(
                success=brief["analysis_run"]["status"] != "failed",
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
                self._record_failure(steps_failed, "scene_detect", e)

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
                self._record_failure(steps_failed, "motion_classification", e)

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
                            "id": f"keyframe-{len(keyframes):04d}",
                            "timestamp": frame["timestamp_seconds"],
                            "scene_index": scene_idx,
                            "path": frame["path"],
                            "description": "",  # Agent fills via vision
                        })
                    steps_completed.append("keyframes")
            except Exception as e:
                self._record_failure(steps_failed, "keyframes", e)
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
                            "id": f"keyframe-{len(keyframes):04d}",
                            "timestamp": frame["timestamp_seconds"],
                            "scene_index": 0,
                            "path": frame["path"],
                            "description": "",
                        })
                    steps_completed.append("keyframes_uniform")
            except Exception as e:
                self._record_failure(steps_failed, "keyframes_uniform", e)

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
                self._record_failure(steps_failed, "audio_energy", e)

        # ─── STEP 6: Build replication guidance ───
        brief["replication_guidance"] = {
            "suggested_pipeline": self._suggest_pipeline(brief),
            "suggested_playbook": "",  # Agent chooses after visual enrichment
            "key_elements_to_replicate": [],  # Agent fills via analysis
            "elements_requiring_custom_work": [],
            "estimated_complexity": self._estimate_complexity(brief),
            "motion_required": self._needs_motion(brief),
            "creative_differentiation_seeds": [],  # Agent fills
            "preserve": [],
            "change": [],
            "avoid": [],
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
        brief["style_profile"].setdefault("production_quality", "unknown")
        brief["style_profile"].setdefault("closest_playbook", "")
        brief["style_profile"].setdefault("playbook_delta", "")

        # ─── Finalize ───
        self._finalize_v11_brief(
            brief,
            output_dir,
            source,
            steps_completed,
            steps_failed,
            started_at,
            depth,
            transcript_data is not None,
        )
        brief["analysis_run"]["config"].update({
            "keyframe_count": len(keyframes),
            "scene_count": len(scenes),
            "has_transcript": self._has_transcript_content(brief),
        })

        self._save_brief(brief, output_dir)

        elapsed = time.time() - start
        artifacts = [str(output_dir / "video_analysis_brief.json")]
        if keyframe_dir.exists():
            artifacts.append(str(keyframe_dir))

        return ToolResult(
            success=brief["analysis_run"]["status"] != "failed",
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
        # Validate before writing so a partial or undeclared artifact cannot
        # masquerade as a grounded analysis.
        from schemas.artifacts import validate_artifact
        clean_brief = {k: v for k, v in brief.items()}
        validate_artifact("video_analysis_brief", clean_brief)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(clean_brief, f, indent=2, default=str)
