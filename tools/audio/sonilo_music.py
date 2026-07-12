"""Sonilo music generation from an assembled video cut.

Generates an original track matched to a rendered cut via the Sonilo
video-to-music API. The model receives the video itself, so the returned
track natively matches the cut's duration — no window selection or offset
trimming pass afterwards. Tracks are licensed and safe for commercial use
(terms apply). Reports unavailable when no API key is configured.
"""

from __future__ import annotations

import base64
import binascii
import json
import mimetypes
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class SoniloMusic(BaseTool):
    name = "sonilo_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "sonilo"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via API key
    install_instructions = (
        "Set the SONILO_API_KEY environment variable:\n"
        "  export SONILO_API_KEY=your_key_here\n"
        "Get a key at https://platform.sonilo.com/dashboard/api-keys"
    )

    agent_skills = ["music"]

    capabilities = [
        "generate_background_music",
        "generate_music_from_video",
        "duration_matched_music",
    ]
    supports = {
        "video_conditioning": True,
        "native_duration_match": True,
        "style_prompt": True,
        "licensed_output": True,
    }
    best_for = [
        "background music generated from the assembled cut itself",
        "exact-duration tracks for shorts and social cuts",
        "client deliverables needing licensed music, safe for commercial use (terms apply)",
    ]
    not_good_for = [
        "music before a cut exists (needs a rendered video input — use a prompt-based provider)",
        "videos longer than 6 minutes (API limit)",
        "sound effects (use a dedicated SFX tool)",
    ]

    fallback_tools = ["music_gen", "pixabay_music", "freesound_music"]

    input_schema = {
        "type": "object",
        "properties": {
            "video_path": {
                "type": "string",
                "description": (
                    "Local path to the assembled cut (the rendered video the "
                    "track should match). Exactly one of video_path or "
                    "video_url is required. The API accepts videos up to "
                    "6 minutes."
                ),
            },
            "video_url": {
                "type": "string",
                "description": (
                    "HTTP(S) URL of the assembled cut; the backend fetches it "
                    "directly. Exactly one of video_path or video_url is "
                    "required."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Optional style hint for the track (mood, genre, "
                    "instruments). The video itself drives structure and "
                    "duration."
                ),
            },
            "output_path": {
                "type": "string",
                "default": "sonilo_music_output.m4a",
                "description": "Path where the generated .m4a file should be written",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    # No automatic retries: the generation endpoint is non-idempotent, so a
    # retry on a transient failure could double-charge the account.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["video_path", "video_url", "prompt"]
    side_effects = [
        "writes audio file to output_path",
        "uploads the input video to the Sonilo API (or passes video_url for the backend to fetch)",
    ]
    user_visible_verification = [
        "Listen to the track against the cut for pacing and mood",
    ]

    _BASE_URL = "https://api.sonilo.com"
    _ENDPOINT = "/v1/video-to-music"
    _MODEL = "video-to-music"
    # Matches the backend's generation read timeout. A long generation keeps
    # running (and charging) server-side, so timing out sooner would orphan
    # a paid request.
    _TIMEOUT = 600
    # The backend rejects videos longer than 6 minutes. Pre-checked locally
    # (best-effort, via ffprobe) to fail fast before uploading a large render.
    # Keep in sync with the backend's limit.
    _MAX_VIDEO_DURATION_SECONDS = 360

    def _get_api_key(self) -> Optional[str]:
        return os.environ.get("SONILO_API_KEY")

    def _get_base_url(self) -> str:
        return os.environ.get("SONILO_API_URL", self._BASE_URL).rstrip("/")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Sonilo bills in plan credits rather than a flat USD rate.
        # Approximation from the public Pro plan ($14.99/mo, up to 30 video
        # generations): ~$0.50 per generation.
        return 0.5

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 120.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No Sonilo API key. " + self.install_instructions,
            )

        video_path = inputs.get("video_path")
        video_url = inputs.get("video_url")
        if bool(video_path) == bool(video_url):
            return ToolResult(
                success=False,
                error="Provide either video_path or video_url (exactly one, not both).",
            )
        if video_url:
            scheme = urlparse(video_url).scheme.lower()
            if scheme not in ("http", "https"):
                return ToolResult(
                    success=False,
                    error="video_url must be an http:// or https:// URL.",
                )

        start = time.time()

        try:
            result = self._generate(inputs, api_key)
        except Exception as e:
            return ToolResult(success=False, error=f"Sonilo generation failed: {e}")

        result.duration_seconds = round(time.time() - start, 2)
        if result.success:
            result.cost_usd = self.estimate_cost(inputs)
            result.model = self._MODEL
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        url = self._get_base_url() + self._ENDPOINT
        headers = {"Authorization": f"Bearer {api_key}"}

        form: dict[str, str] = {}
        prompt = (inputs.get("prompt") or "").strip()
        if prompt:
            form["prompt"] = prompt

        video_path = inputs.get("video_path")
        if video_path:
            resolved = Path(video_path)
            if not resolved.is_file():
                return ToolResult(
                    success=False,
                    error=f"Input video not found: {resolved}",
                )
            probed = self._probe_duration(str(resolved))
            if probed is not None and probed > self._MAX_VIDEO_DURATION_SECONDS:
                return ToolResult(
                    success=False,
                    error=(
                        f"Input video is {probed:.0f}s; the Sonilo API accepts "
                        f"videos up to {self._MAX_VIDEO_DURATION_SECONDS}s "
                        "(6 minutes). Trim the cut or generate per segment."
                    ),
                )
            mime, _ = mimetypes.guess_type(resolved.name)
            with open(resolved, "rb") as fh:
                files = {
                    "video": (resolved.name, fh, mime or "application/octet-stream")
                }
                response = requests.post(
                    url,
                    headers=headers,
                    data=form or None,
                    files=files,
                    stream=True,
                    timeout=self._TIMEOUT,
                )
        else:
            # URL mode — the backend fetches the video itself; send form fields only.
            form["video_url"] = inputs["video_url"]
            response = requests.post(
                url,
                headers=headers,
                data=form,
                stream=True,
                timeout=self._TIMEOUT,
            )

        if response.status_code >= 400:
            return ToolResult(
                success=False,
                error=self._http_error(response.status_code, self._read_error_detail(response)),
            )

        audio_bytes, title = self._consume_stream(response)

        output_path = Path(inputs.get("output_path", "sonilo_music_output.m4a"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(audio_bytes)

        data: dict[str, Any] = {
            "provider": "sonilo",
            "model": self._MODEL,
            "prompt": prompt or None,
            "title": title,
            "output": str(output_path),
            "format": "m4a",
        }
        track_duration = self._probe_duration(str(output_path))
        if track_duration is not None:
            data["duration_seconds"] = round(track_duration, 2)

        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
        )

    def _consume_stream(self, response: Any) -> tuple[bytes, Optional[str]]:
        """Consume the NDJSON event stream returned by the generation endpoint.

        Event types: ``audio_chunk`` (base64 audio bytes, keyed by
        ``stream_index``), ``title``, ``complete`` (terminal success), and
        ``error`` (terminal failure). Progress events such as ``stage_start``
        / ``stage_complete`` and malformed lines are ignored.
        """
        streams: dict[int, bytearray] = {}
        title: Optional[str] = None
        completed = False

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.strip():
                continue
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            event_type = event.get("type")
            if event_type == "audio_chunk":
                data = event.get("data")
                if not isinstance(data, str):
                    continue
                try:
                    index = int(event.get("stream_index", 0))
                except (TypeError, ValueError):
                    continue
                if index < 0:
                    continue
                try:
                    decoded = base64.b64decode(data, validate=True)
                except (binascii.Error, ValueError):
                    continue
                streams.setdefault(index, bytearray()).extend(decoded)
            elif event_type == "title":
                value = event.get("title")
                if isinstance(value, str) and value.strip():
                    title = value.strip()
            elif event_type == "complete":
                completed = True
            elif event_type == "error":
                raise RuntimeError(
                    event.get("message") or event.get("code") or "Sonilo stream error"
                )

        if not completed:
            raise RuntimeError("Sonilo stream ended before completing.")
        if not streams:
            raise RuntimeError("Sonilo stream completed without returning audio data.")

        first_index = min(streams)
        return bytes(streams[first_index]), title

    @staticmethod
    def _read_error_detail(response: Any) -> str:
        try:
            body = response.json()
            if isinstance(body, dict):
                detail = body.get("detail") or body.get("error") or body.get("message")
                if isinstance(detail, str) and detail.strip():
                    return detail.strip()
        except Exception:
            pass
        text = getattr(response, "text", "") or ""
        return text.strip()[:300] or "no error detail"

    @staticmethod
    def _http_error(status: int, detail: str) -> str:
        if status == 401:
            return (
                "Sonilo API key was rejected. Check SONILO_API_KEY "
                "(keys: https://platform.sonilo.com/dashboard/api-keys)."
            )
        if status == 402:
            return detail or "Sonilo account has no remaining credits."
        if status == 413:
            return f"Sonilo upload is too large: {detail}"
        if status == 429:
            return f"Sonilo rate limit exceeded: {detail}"
        return f"Sonilo API error ({status}): {detail}"

    @staticmethod
    def _probe_duration(path: str) -> Optional[float]:
        """Best-effort ffprobe duration lookup; returns None when unavailable."""
        if shutil.which("ffprobe") is None:
            return None
        try:
            proc = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=True,
            )
            return float(proc.stdout.strip())
        except Exception:
            return None
