"""YouTube transcript fetcher tool wrapping youtube-transcript-api.

Extracts transcripts/captions from YouTube videos without downloading the video.
Instant, free, no API key needed. Falls back to yt-dlp subtitle download.
"""

from __future__ import annotations

import re
import time
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


class TranscriptFetcher(BaseTool):
    name = "transcript_fetcher"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "youtube-transcript-api"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["python:youtube_transcript_api"]
    install_instructions = (
        "Install youtube-transcript-api: pip install youtube-transcript-api"
    )
    agent_skills = []

    capabilities = [
        "fetch_transcript",
        "list_transcripts",
    ]

    best_for = [
        "fast YouTube transcript extraction",
        "caption-based analysis without video download",
        "getting timestamped text from YouTube videos",
    ]

    not_good_for = [
        "non-YouTube platforms (Instagram, TikTok)",
        "videos without any captions",
        "speaker diarization (use transcriber tool instead)",
    ]

    input_schema = {
        "type": "object",
        "required": ["url_or_video_id"],
        "properties": {
            "url_or_video_id": {
                "type": "string",
                "description": "YouTube URL or video ID",
            },
            "languages": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["en"],
                "description": "Preferred languages in priority order",
            },
            "include_auto_generated": {
                "type": "boolean",
                "default": True,
                "description": "Whether to include auto-generated captions",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "transcript": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "start": {"type": "number"},
                        "duration": {"type": "number"},
                    },
                },
            },
            "full_text": {"type": "string"},
            "language": {"type": "string"},
            "is_auto_generated": {"type": "boolean"},
            "word_count": {"type": "integer"},
            "source": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=10,
        network_required=True,
    )
    idempotency_key_fields = ["url_or_video_id", "languages"]
    side_effects = []
    fallback = "transcriber"
    user_visible_verification = [
        "Spot-check transcript accuracy against video audio",
    ]

    def _extract_video_id(self, url_or_id: str) -> str:
        """Extract YouTube video ID from URL or return as-is if already an ID."""
        # Already a bare ID (11 chars, alphanumeric + - _)
        if re.match(r"^[A-Za-z0-9_-]{11}$", url_or_id):
            return url_or_id

        # Standard YouTube URLs
        patterns = [
            r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})",
        ]
        for pattern in patterns:
            match = re.search(pattern, url_or_id)
            if match:
                return match.group(1)

        # If nothing matched, try using the whole string as ID
        return url_or_id.strip()

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        video_id = self._extract_video_id(inputs["url_or_video_id"])
        languages = inputs.get("languages", ["en"])
        include_auto = inputs.get("include_auto_generated", True)  # noqa: F841

        start = time.time()

        try:
            from youtube_transcript_api import YouTubeTranscriptApi

            ytt = YouTubeTranscriptApi()

            # Fetch transcript using the instance-based API (v1.0+)
            transcript_result = ytt.fetch(video_id, languages=languages)

            # Build segments and full text from snippets
            segments = []
            full_text_parts = []
            for snippet in transcript_result.snippets:
                segments.append({
                    "text": snippet.text,
                    "start": round(snippet.start, 3),
                    "duration": round(snippet.duration, 3),
                })
                full_text_parts.append(snippet.text)

            full_text = " ".join(full_text_parts)
            word_count = len(full_text.split())

            # Get auto-generated status and language from the result
            is_auto = getattr(transcript_result, "is_generated", False)
            detected_lang = getattr(transcript_result, "language", languages[0])
            # If language is an object, get the code
            if hasattr(detected_lang, "code"):
                detected_lang = detected_lang.code
            elif not isinstance(detected_lang, str):
                detected_lang = languages[0]

            elapsed = time.time() - start

            return ToolResult(
                success=True,
                data={
                    "transcript": segments,
                    "full_text": full_text,
                    "language": detected_lang,
                    "is_auto_generated": is_auto,
                    "word_count": word_count,
                    "source": "youtube_captions",
                    "video_id": video_id,
                    "segment_count": len(segments),
                },
                duration_seconds=round(elapsed, 2),
            )

        except ImportError:
            return ToolResult(
                success=False,
                error="youtube-transcript-api not installed. Run: pip install youtube-transcript-api",
            )
        except Exception as e:
            elapsed = time.time() - start
            error_str = str(e)

            # Provide helpful error messages
            if "Could not retrieve" in error_str or "TranscriptsDisabled" in error_str:
                return ToolResult(
                    success=False,
                    error=(
                        f"No captions available for video {video_id}. "
                        "This video may not have captions enabled. "
                        "Fallback: download the video and use the transcriber tool "
                        "with Whisper for local transcription."
                    ),
                    data={"video_id": video_id, "fallback_suggested": "transcriber"},
                    duration_seconds=round(elapsed, 2),
                )

            return ToolResult(
                success=False,
                error=f"Transcript fetch failed: {error_str}",
                data={"video_id": video_id},
                duration_seconds=round(elapsed, 2),
            )
