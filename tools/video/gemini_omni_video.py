"""Google Gemini Omni Flash video generation and conversational editing.

Calls the Gemini Interactions API (``POST /v1beta/interactions``) directly with
the project's Google API key — the same key that unlocks Imagen images and
Cloud TTS. Gemini Omni Flash generates 3-10 second 720p/24fps clips with
synthesized audio, and is the only provider in the fleet with stateful
conversational editing: pass ``previous_interaction_id`` and describe only the
delta ("Make the violin invisible. Keep everything else the same.").

Reference images bind to roles via inline prompt tags (``<FIRST_FRAME>``,
``<IMAGE_REF_N>``) and beats can be scheduled with timecode syntax
(``[0-3s] ... [3-6s] ...``). See the Layer 3 skill ``gemini-omni`` for the
authoritative prompting guide — read it before writing prompts.
"""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

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

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
_UPLOAD_URL = "https://generativelanguage.googleapis.com/upload/v1beta/files"
_DEFAULT_MODEL = "gemini-omni-flash-preview"
# Billed at 5,792 output tokens per second of 720p video, $17.50/1M tokens
# (ai.google.dev/gemini-api/docs/pricing) — effectively ~$0.10 per second.
_COST_PER_SECOND = 0.10
_DEFAULT_DURATION_SECONDS = 8
_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_SECONDS = 900


class GeminiOmniVideo(BaseTool):
    name = "gemini_omni_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "gemini_omni"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set GEMINI_API_KEY or GOOGLE_API_KEY to a Google AI Studio API key.\n"
        "  Get one at https://aistudio.google.com/apikey\n"
        "  Gemini Omni Flash is paid-tier only (no free tier); ~$0.10 per second of video."
    )
    agent_skills = ["gemini-omni", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video", "edit_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "edit_video": True,
        "conversational_editing": True,
        "native_audio": True,
        "text_rendering": True,
        "timecode_control": True,
        # Preview limitations — no sampler controls of any kind.
        "seed": False,
        "negative_prompt": False,
        "first_last_frame_to_video": False,
    }
    best_for = [
        "iterative natural-language video editing (edit a clip without regenerating it)",
        "reference-image-driven clips via <FIRST_FRAME>/<IMAGE_REF_N> prompt tags",
        "fast 3-10s clips with synced audio, rendered text, and timecoded beats from one Google key",
    ]
    not_good_for = [
        "clips longer than 10 seconds or above 720p",
        "seed-reproducible output or negative-prompt control",
        "offline generation",
    ]
    fallback_tools = ["veo_video", "sora_video", "kling_video", "minimax_video"]
    # Conversational editing + native audio are unique in the fleet, but preview
    # output is capped at 720p/10s — below seedance (0.95) and grok/runway (0.9)
    # on raw generation fidelity. Without a quality_score the scorer would only
    # count supports/stability flags and bury the editing capability entirely.
    # See lib/scoring.py.
    quality_score = 0.85

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Video description, or for edit_video the change to apply. "
                    "Supports <FIRST_FRAME>/<IMAGE_REF_N> tags and [0-3s] timecodes — "
                    "see the gemini-omni skill."
                ),
            },
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video", "edit_video"],
                "default": "text_to_video",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16"],
                "default": "16:9",
            },
            "duration": {
                "type": "string",
                "description": (
                    "Duration hint in seconds (3-10). The model chooses the actual length; "
                    "this only shapes the prompt-independent cost estimate."
                ),
            },
            "reference_image_path": {
                "type": "string",
                "description": "Local reference image (jpg/png) for image_to_video.",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference images, bound in the prompt as <IMAGE_REF_0>, <IMAGE_REF_1>, ...",
            },
            "previous_interaction_id": {
                "type": "string",
                "description": (
                    "Interaction id from a prior gemini_omni_video result — edits that video "
                    "in place (edit_video). Requires the prior call to have used store=true."
                ),
            },
            "input_video_path": {
                "type": "string",
                "description": (
                    "Local video to edit (edit_video). Uploaded via the Files API. "
                    "Editing uploaded videos is unavailable in the EEA, Switzerland, and the UK."
                ),
            },
            "store": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Keep the interaction server-side so the result can be edited in later turns "
                    "via previous_interaction_id. Set false only for one-shot generations."
                ),
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "operation", "aspect_ratio", "previous_interaction_id"]
    side_effects = [
        "writes video file to output_path",
        "calls the Gemini Interactions API",
        "stores the interaction server-side when store=true (enables later edits)",
    ]
    user_visible_verification = [
        "Watch generated clip for visual quality, motion, and prompt adherence",
        "Listen for synthesized audio quality and any requested dialogue/music",
        "After an edit turn, confirm unmentioned elements were preserved",
    ]

    @staticmethod
    def _get_api_key() -> str | None:
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")

    def get_status(self) -> ToolStatus:
        if self._get_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    @staticmethod
    def _duration_hint(inputs: dict[str, Any]) -> int:
        raw = str(inputs.get("duration") or _DEFAULT_DURATION_SECONDS).strip().lower()
        raw = raw[:-1] if raw.endswith("s") else raw
        try:
            seconds = int(float(raw))
        except ValueError:
            seconds = _DEFAULT_DURATION_SECONDS
        return max(3, min(10, seconds))

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return _COST_PER_SECOND * self._duration_hint(inputs)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0

    @staticmethod
    def _image_part(path_str: str) -> dict[str, Any]:
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Reference image not found: {path}")
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type or not mime_type.startswith("image/"):
            mime_type = "image/png"
        return {
            "type": "image",
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
            "mime_type": mime_type,
        }

    def _upload_video_file(self, requests_mod: Any, api_key: str, path_str: str) -> str:
        """Upload a local video via the Files API (resumable) and return its URI."""
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Input video not found: {path}")
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type or not mime_type.startswith("video/"):
            mime_type = "video/mp4"
        video_bytes = path.read_bytes()

        start_resp = requests_mod.post(
            _UPLOAD_URL,
            headers={
                "x-goog-api-key": api_key,
                "X-Goog-Upload-Protocol": "resumable",
                "X-Goog-Upload-Command": "start",
                "X-Goog-Upload-Header-Content-Length": str(len(video_bytes)),
                "X-Goog-Upload-Header-Content-Type": mime_type,
                "Content-Type": "application/json",
            },
            json={"file": {"display_name": path.name}},
            timeout=30,
        )
        start_resp.raise_for_status()
        upload_url = start_resp.headers.get("X-Goog-Upload-URL")
        if not upload_url:
            raise RuntimeError("Files API did not return an upload URL")

        upload_resp = requests_mod.post(
            upload_url,
            headers={
                "X-Goog-Upload-Command": "upload, finalize",
                "X-Goog-Upload-Offset": "0",
                "Content-Length": str(len(video_bytes)),
            },
            data=video_bytes,
            timeout=300,
        )
        upload_resp.raise_for_status()
        file_info = upload_resp.json().get("file", {})

        # Wait until the uploaded video is processed before referencing it.
        deadline = time.time() + _MAX_POLL_SECONDS
        while str(file_info.get("state", "")).upper() == "PROCESSING":
            if time.time() > deadline:
                raise TimeoutError("Uploaded video did not finish processing in time")
            time.sleep(_POLL_INTERVAL_SECONDS)
            status_resp = requests_mod.get(
                f"{_BASE_URL}/{file_info.get('name')}",
                headers={"x-goog-api-key": api_key},
                timeout=15,
            )
            status_resp.raise_for_status()
            file_info = status_resp.json()
        if str(file_info.get("state", "")).upper() == "FAILED":
            raise RuntimeError("Files API failed to process the uploaded video")

        uri = file_info.get("uri")
        if not uri:
            raise RuntimeError(f"Files API response missing uri: {file_info}")
        return uri

    @staticmethod
    def _extract_output_video(data: dict[str, Any]) -> dict[str, Any] | None:
        """Find the output video payload ({'data': b64} or {'uri': files/...})."""
        for key in ("output_video", "outputVideo"):
            video = data.get(key)
            if isinstance(video, dict) and (video.get("data") or video.get("uri")):
                return video
        # REST responses may also carry the video inside steps[].content[].
        for step in data.get("steps") or []:
            for item in step.get("content") or []:
                if isinstance(item, dict) and (item.get("data") or item.get("uri")):
                    if "video" in str(item.get("type", "")).lower() or item.get("mime_type", "").startswith("video/"):
                        return item
                    if item.get("data") or str(item.get("uri", "")).startswith("files/"):
                        return item
        return None

    @staticmethod
    def _file_id_from_uri(uri: str) -> str:
        """Extract the bare file id from any documented URI shape.

        The API may return ``files/<id>``, a full
        ``https://.../v1beta/files/<id>`` resource URI, or a ready-made
        download URL ``.../files/<id>:download?alt=media``. Polling and
        download both need just ``<id>``.
        """
        path = uri.split("?", 1)[0].rstrip("/")
        marker = "files/"
        idx = path.rfind(marker)
        tail = path[idx + len(marker):] if idx != -1 else path.split("/")[-1]
        return tail.split(":", 1)[0]

    def _download_via_uri(self, requests_mod: Any, api_key: str, uri: str) -> bytes:
        """Poll a Files API entry until ACTIVE, then download its bytes."""
        file_id = self._file_id_from_uri(uri)
        headers = {"x-goog-api-key": api_key}
        deadline = time.time() + _MAX_POLL_SECONDS
        while True:
            status_resp = requests_mod.get(
                f"{_BASE_URL}/files/{file_id}", headers=headers, timeout=15
            )
            status_resp.raise_for_status()
            state = str(status_resp.json().get("state", "")).upper()
            if state == "ACTIVE":
                break
            if state == "FAILED":
                raise RuntimeError("Gemini Omni video generation failed during processing")
            if time.time() > deadline:
                raise TimeoutError("Timed out waiting for Gemini Omni video to become ACTIVE")
            time.sleep(_POLL_INTERVAL_SECONDS)

        download_resp = requests_mod.get(
            f"{_BASE_URL}/files/{file_id}:download",
            params={"alt": "media"},
            headers=headers,
            timeout=300,
        )
        download_resp.raise_for_status()
        return download_resp.content

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._get_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="GEMINI_API_KEY / GOOGLE_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        prompt = str(inputs["prompt"]).strip()
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        previous_interaction_id = inputs.get("previous_interaction_id")

        if operation == "edit_video" and not previous_interaction_id and not inputs.get("input_video_path"):
            return ToolResult(
                success=False,
                error="edit_video requires previous_interaction_id (edit a generated clip) or input_video_path (edit an uploaded clip)",
            )

        reference_paths = list(inputs.get("reference_image_paths") or [])
        if inputs.get("reference_image_path"):
            reference_paths.insert(0, inputs["reference_image_path"])
        if operation in {"image_to_video", "reference_to_video"} and not reference_paths:
            return ToolResult(
                success=False,
                error=f"{operation} requires reference_image_path or reference_image_paths",
            )

        try:
            parts: list[dict[str, Any]] = [self._image_part(p) for p in reference_paths]
            if inputs.get("input_video_path"):
                video_uri = self._upload_video_file(requests, api_key, inputs["input_video_path"])
                parts.append({"type": "document", "uri": video_uri})
        except Exception as e:
            return ToolResult(success=False, error=f"Gemini Omni input preparation failed: {e}")

        payload: dict[str, Any] = {
            "model": _DEFAULT_MODEL,
            # Plain string for text-only turns (the documented minimal form),
            # typed parts when images or an uploaded video ride along.
            "input": prompt if not parts else parts + [{"type": "text", "text": prompt}],
            # uri delivery avoids the ~4MB inline-payload ceiling; inline data in
            # the response is still handled below if the API returns it anyway.
            "response_format": {
                "type": "video",
                "aspect_ratio": aspect_ratio,
                "delivery": "uri",
            },
        }
        if previous_interaction_id:
            payload["previous_interaction_id"] = previous_interaction_id
        if inputs.get("store") is False:
            payload["store"] = False

        try:
            resp = requests.post(
                f"{_BASE_URL}/interactions",
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=600,
            )
            if not resp.ok:
                detail = resp.text[:1000]
                return ToolResult(
                    success=False,
                    error=f"Gemini Omni interaction failed ({resp.status_code}): {detail}",
                )
            data = resp.json()

            interaction_id = data.get("id")
            video = self._extract_output_video(data)
            if not video:
                return ToolResult(
                    success=False,
                    error=f"Gemini Omni response did not include an output video: {str(data)[:1000]}",
                )

            if video.get("data"):
                video_bytes = base64.b64decode(video["data"])
            else:
                video_bytes = self._download_via_uri(requests, api_key, str(video["uri"]))

            output_path = Path(inputs.get("output_path", "gemini_omni_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_bytes)
        except Exception as e:
            return ToolResult(success=False, error=f"Gemini Omni video generation failed: {e}")

        editable = inputs.get("store") is not False
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": _DEFAULT_MODEL,
                "prompt": prompt,
                "operation": operation,
                "output": str(output_path),
                "aspect_ratio": aspect_ratio,
                "has_audio": True,
                # Feed this back as previous_interaction_id to edit this clip.
                "interaction_id": interaction_id,
                "editable": editable,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=_DEFAULT_MODEL,
        )
