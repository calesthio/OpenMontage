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
_DEFAULT_MODEL = "gemini-omni-1.1-flash"
# Billed at 5,792 output tokens per second of 720p video, $17.50/1M tokens
# (ai.google.dev/gemini-api/docs/pricing) — effectively ~$0.10 per second.
_OUTPUT_VIDEO_TOKENS_PER_SECOND = 5_792
_MAX_OUTPUT_DURATION_SECONDS = 10
_MAX_VIDEO_TOKEN_ESTIMATE = _MAX_OUTPUT_DURATION_SECONDS * _OUTPUT_VIDEO_TOKENS_PER_SECOND
_INPUT_COST_PER_MILLION_TOKENS = 1.50
_OUTPUT_TEXT_COST_PER_MILLION_TOKENS = 9.00
_OUTPUT_VIDEO_COST_PER_MILLION_TOKENS = 17.50
# Gemini image accounting has a 258-token floor; larger inline images use their
# base64 byte count as a deliberately conservative token upper estimate.
_MIN_IMAGE_INPUT_TOKENS = 258
_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_SECONDS = 900


class GeminiOmniVideo(BaseTool):
    name = "gemini_omni_video"
    version = "0.2.0"
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
        # The direct adapter intentionally exposes no sampler controls.
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
    # Conversational editing + native audio are unique in the fleet, but this
    # adapter is capped at 720p/10s — below seedance (0.95) and grok/runway (0.9)
    # on raw generation fidelity. Without a quality_score the scorer would only
    # count supports/stability flags and bury the editing capability entirely.
    # See lib/scoring.py.
    quality_score = 0.85

    input_schema = {
        "type": "object",
        "anyOf": [{"required": ["prompt"]}, {"required": ["resume_video_uri"]}],
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
            "model": {
                "type": "string",
                "enum": [_DEFAULT_MODEL],
                "default": _DEFAULT_MODEL,
                "description": "Stable Gemini Omni 1.1 Flash model.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16"],
                "default": "16:9",
            },
            "resolution": {
                "type": "string",
                "enum": ["720p"],
                "default": "720p",
                "description": "The direct adapter currently supports 720p output.",
            },
            "duration": {
                "type": "string",
                "description": (
                    "Optional 3-10 second planning/prompt hint for the caller. It is not sent "
                    "to the provider; the model chooses the actual duration, and this hint does "
                    "not cap billing or the conservative fallback cost estimate."
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
            "resume_video_uri": {
                "type": "string",
                "description": (
                    "Files API URI returned after an accepted generation whose download failed. "
                    "Downloads the existing output with GET requests only; no new generation is submitted."
                ),
            },
            "interaction_id": {
                "type": "string",
                "description": "Optional interaction id retained as provenance during resume_download.",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = [
        "model",
        "prompt",
        "operation",
        "aspect_ratio",
        "resolution",
        "previous_interaction_id",
        "resume_video_uri",
    ]
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

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        input_token_upper_bound = len(str(inputs.get("prompt") or "").encode("utf-8"))
        image_paths = list(inputs.get("reference_image_paths") or [])
        if inputs.get("reference_image_path"):
            image_paths.insert(0, inputs["reference_image_path"])
        for path_str in image_paths:
            path = Path(path_str)
            if path.is_file():
                size = path.stat().st_size
                base64_size = 4 * ((size + 2) // 3)
                input_token_upper_bound += max(_MIN_IMAGE_INPUT_TOKENS, base64_size)
        input_video_path = inputs.get("input_video_path")
        if input_video_path and Path(input_video_path).is_file():
            input_token_upper_bound += max(
                _MAX_VIDEO_TOKEN_ESTIMATE,
                Path(input_video_path).stat().st_size,
            )
        if inputs.get("previous_interaction_id"):
            input_token_upper_bound += _MAX_VIDEO_TOKEN_ESTIMATE
        output_token_upper_bound = _MAX_VIDEO_TOKEN_ESTIMATE
        return (
            input_token_upper_bound * _INPUT_COST_PER_MILLION_TOKENS
            + output_token_upper_bound * _OUTPUT_VIDEO_COST_PER_MILLION_TOKENS
        ) / 1_000_000

    @staticmethod
    def _cost_from_usage(usage: Any) -> float | None:
        if not isinstance(usage, dict):
            return None

        def token_count(value: Any) -> int | None:
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return None
            return value

        input_tokens = token_count(usage.get("total_input_tokens"))
        output_tokens = token_count(usage.get("total_output_tokens"))
        thought_tokens = token_count(usage.get("total_thought_tokens", 0))
        if input_tokens is None or output_tokens is None or thought_tokens is None:
            return None

        input_breakdown = usage.get("input_tokens_by_modality")
        if input_breakdown is not None:
            if not isinstance(input_breakdown, list):
                return None
            classified_input_tokens = 0.0
            for item in input_breakdown:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("modality"), str)
                    or not item["modality"].strip()
                ):
                    return None
                count = token_count(item.get("tokens"))
                if count is None:
                    return None
                classified_input_tokens += count
            if classified_input_tokens > input_tokens:
                return None

        output_cost = 0.0
        breakdown = usage.get("output_tokens_by_modality")
        if breakdown is None:
            output_cost = output_tokens * _OUTPUT_VIDEO_COST_PER_MILLION_TOKENS
        else:
            if not isinstance(breakdown, list):
                return None
            classified_tokens = 0.0
            for item in breakdown:
                if (
                    not isinstance(item, dict)
                    or not isinstance(item.get("modality"), str)
                    or not item["modality"].strip()
                ):
                    return None
                count = token_count(item.get("tokens"))
                if count is None:
                    return None
                classified_tokens += count
                rate = (
                    _OUTPUT_TEXT_COST_PER_MILLION_TOKENS
                    if item["modality"].strip().lower() == "text"
                    else _OUTPUT_VIDEO_COST_PER_MILLION_TOKENS
                )
                output_cost += count * rate
            if classified_tokens > output_tokens:
                return None
            output_cost += (
                output_tokens - classified_tokens
            ) * _OUTPUT_VIDEO_COST_PER_MILLION_TOKENS

        return (
            input_tokens * _INPUT_COST_PER_MILLION_TOKENS
            + output_cost
            + thought_tokens * _OUTPUT_VIDEO_COST_PER_MILLION_TOKENS
        ) / 1_000_000

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
        # REST responses may also carry the video inside model output steps.
        for step in data.get("steps") or []:
            if not isinstance(step, dict) or step.get("type") != "model_output":
                continue
            for item in step.get("content") or []:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "video"
                    and (item.get("data") or item.get("uri"))
                ):
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
        model = inputs.get("model", _DEFAULT_MODEL)
        if model != _DEFAULT_MODEL:
            return ToolResult(
                success=False,
                error=f"Unsupported Gemini Omni model {model!r}; use {_DEFAULT_MODEL}.",
            )
        resume_video_uri = inputs.get("resume_video_uri")
        if resume_video_uri:
            interaction_id = inputs.get("interaction_id")
            output_path = Path(inputs.get("output_path", "gemini_omni_output.mp4"))
            try:
                video_bytes = self._download_via_uri(requests, api_key, str(resume_video_uri))
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(video_bytes)
            except Exception as e:
                return ToolResult(
                    success=False,
                    data={
                        "interaction_id": interaction_id,
                        "output_uri": str(resume_video_uri),
                    },
                    error=f"Gemini Omni resume download failed: {e}",
                )
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "operation": "resume_download",
                    "output": str(output_path),
                    "output_uri": str(resume_video_uri),
                    "interaction_id": interaction_id,
                    "editable": bool(interaction_id) and inputs.get("store") is not False,
                },
                artifacts=[str(output_path)],
                cost_usd=0.0,
                duration_seconds=round(time.time() - start, 2),
                model=model,
            )
        operation = inputs.get("operation", "text_to_video")
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            return ToolResult(success=False, error="Gemini Omni generation requires a prompt.")
        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        if inputs.get("resolution", "720p") != "720p":
            return ToolResult(
                success=False,
                error="Gemini Omni direct adapter currently supports only 720p output.",
            )
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
                parts.append({"type": "video", "uri": video_uri})
        except Exception as e:
            return ToolResult(success=False, error=f"Gemini Omni input preparation failed: {e}")

        payload: dict[str, Any] = {
            "model": model,
            # Plain string for text-only turns (the documented minimal form),
            # typed parts when images or an uploaded video ride along.
            "input": prompt if not parts else parts + [{"type": "text", "text": prompt}],
            # uri delivery avoids the ~4MB inline-payload ceiling; inline data in
            # the response is still handled below if the API returns it anyway.
            "response_format": {
                "type": "video",
                "aspect_ratio": aspect_ratio,
                "resolution": "720p",
                "delivery": "uri",
            },
        }
        if previous_interaction_id:
            payload["previous_interaction_id"] = previous_interaction_id
        if inputs.get("store") is False:
            payload["store"] = False

        interaction_id = None
        output_uri = None
        generation_accepted = False
        usage = None
        try:
            try:
                resp = requests.post(
                    f"{_BASE_URL}/interactions",
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=payload,
                    timeout=600,
                )
            except Exception as e:
                return ToolResult(
                    success=False,
                    data={
                        "submission_outcome": "unknown",
                        "retry_safe": False,
                    },
                    error=(
                        "Gemini Omni submission outcome is unknown after transport failure: "
                        f"{e}. Do not retry or resubmit; the request may have been accepted "
                        "and charged."
                    ),
                    cost_usd=self.estimate_cost(inputs),
                )
            if not resp.ok:
                detail = resp.text[:1000]
                return ToolResult(
                    success=False,
                    error=f"Gemini Omni interaction failed ({resp.status_code}): {detail}",
                )
            generation_accepted = True
            data = resp.json()
            usage = data.get("usage")

            interaction_id = data.get("id")
            video = self._extract_output_video(data)
            if not video:
                usage_cost = self._cost_from_usage(usage)
                return ToolResult(
                    success=False,
                    data={"interaction_id": interaction_id} if interaction_id else {},
                    error=f"Gemini Omni response did not include an output video: {str(data)[:1000]}",
                    cost_usd=(
                        usage_cost if usage_cost is not None else self.estimate_cost(inputs)
                    ),
                )

            if video.get("data"):
                video_bytes = base64.b64decode(video["data"])
            else:
                output_uri = str(video["uri"])
                video_bytes = self._download_via_uri(requests, api_key, output_uri)

            output_path = Path(inputs.get("output_path", "gemini_omni_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_bytes)
        except Exception as e:
            failure_data: dict[str, Any] = {}
            if interaction_id:
                failure_data["interaction_id"] = interaction_id
            if output_uri:
                resume_download: dict[str, Any] = {
                    "resume_video_uri": output_uri,
                    "store": inputs.get("store") is not False,
                }
                if interaction_id:
                    resume_download["interaction_id"] = interaction_id
                failure_data.update(
                    {
                        "output_uri": output_uri,
                        "resume_download": resume_download,
                    }
                )
            usage_cost = self._cost_from_usage(usage)
            return ToolResult(
                success=False,
                data=failure_data,
                error=f"Gemini Omni video generation failed: {e}",
                cost_usd=(
                    usage_cost
                    if usage_cost is not None
                    else self.estimate_cost(inputs) if generation_accepted else 0.0
                ),
            )

        editable = inputs.get("store") is not False
        usage_cost = self._cost_from_usage(usage)
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
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
            cost_usd=usage_cost if usage_cost is not None else self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
