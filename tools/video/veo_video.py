"""Generate video using Google Veo 3.1 via fal.ai or Google GenAI API.

Support text-to-video, image-to-video, reference-to-video, and first/last-frame
interpolation so agents can preserve visual consistency instead of relying only on
raw text prompts.
"""

from __future__ import annotations

import os
import mimetypes
import base64
import time
from pathlib import Path
from typing import Any

from tools.google_credentials import GOOGLE_API_TIMEOUT_SECONDS

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


class VeoVideo(BaseTool):
    name = "veo_video"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "veo"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Configure at least one backend API key:\n"
        "  - Direct Google GenAI backend: Set GEMINI_API_KEY (or GOOGLE_API_KEY).\n"
        "    Get a key at https://aistudio.google.com/\n"
        "    Or set GOOGLE_APPLICATION_CREDENTIALS for Vertex AI service account.\n"
        "  - FAL.ai backend: Set FAL_KEY (or FAL_AI_API_KEY).\n"
        "    Get one at https://fal.ai/dashboard/keys"
    )
    agent_skills = ["ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "reference_to_video",
        "first_last_frame_to_video",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "first_last_frame_to_video": True,
        "native_audio": True,
        "dialogue_generation": True,
        "ambient_sound": True,
    }
    best_for = [
        "videos with synchronized dialogue and audio",
        "cutting-edge quality from Google DeepMind",
        "ambient sound and music generation built in",
    ]
    not_good_for = ["budget projects", "offline generation", "quick iteration"]
    fallback_tools = ["gemini_omni_video", "kling_video", "minimax_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "backend": {
                "type": "string",
                "enum": ["auto", "google", "fal"],
                "default": "auto",
                "description": "API backend provider to use for generation",
            },
            "operation": {
                "type": "string",
                "enum": [
                    "text_to_video",
                    "image_to_video",
                    "reference_to_video",
                    "first_last_frame_to_video",
                ],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "default": "veo3.1",
                "description": "Model variant for FAL (e.g. veo3.1) or custom model for Google",
            },
            "duration": {
                "type": "string",
                "default": "8s",
                "description": "Duration (e.g., '4s', '6s', '8s')",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16"],
                "default": "16:9",
            },
            "generate_audio": {
                "type": "boolean",
                "default": True,
                "description": "Whether to generate synchronized audio",
            },
            "resolution": {
                "type": "string",
                "enum": ["720p", "1080p", "4k"],
                "default": "1080p",
            },
            "negative_prompt": {"type": "string"},
            "seed": {"type": "integer"},
            "auto_fix": {"type": "boolean", "default": True},
            "safety_tolerance": {
                "type": "string",
                "enum": ["1", "2", "3", "4", "5", "6"],
                "default": "4",
            },
            "image_url": {
                "type": "string",
                "description": "Reference image URL for image_to_video",
            },
            "image_path": {
                "type": "string",
                "description": "Local reference image path for image_to_video",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Reference image URLs for reference_to_video",
            },
            "reference_image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference image paths for reference_to_video",
            },
            "first_frame_url": {"type": "string"},
            "first_frame_path": {"type": "string"},
            "last_frame_url": {"type": "string"},
            "last_frame_path": {"type": "string"},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = ["prompt", "model_variant", "operation", "duration"]
    side_effects = ["writes video file to output_path", "calls fal.ai or Google APIs"]
    user_visible_verification = [
        "Watch generated clip for visual quality and motion",
        "Listen for audio synchronization and quality",
    ]

    def _get_google_credentials_status(self) -> bool:
        """Check whether Google API keys or Vertex AI service account credentials are set."""
        from tools.google_credentials import has_google_credentials

        return has_google_credentials()

    def _get_fal_api_key(self) -> str | None:
        """Retrieve the FAL API key from environment variables."""
        return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")

    def get_status(self) -> ToolStatus:
        """Determine whether the tool is available based on configured credentials."""
        if self._get_google_credentials_status() or self._get_fal_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Estimate the generation cost in USD based on input parameters."""
        # Determine active backend using inputs and environment
        backend = inputs.get("backend", "auto")
        if backend == "auto":
            if self._get_google_credentials_status():
                backend = "google"
            elif self._get_fal_api_key():
                backend = "fal"
            else:
                backend = "google"

        duration_text = str(inputs.get("duration", "8s")).lower().replace("s", "")
        try:
            duration = int(duration_text)
        except ValueError:
            duration = 8

        if backend == "google":
            # Standard Google Veo is $0.40 per second
            return round(duration * 0.40, 4)

        # FAL cost estimation
        variant = inputs.get("model_variant", "veo3.1")
        resolution = inputs.get("resolution", "1080p")
        generate_audio = bool(inputs.get("generate_audio", True))

        if "fast" in variant:
            base_per_second = 0.10
            audio_per_second = 0.20
        else:
            if resolution == "4k":
                base_per_second = 0.40
                audio_per_second = 0.60
            else:
                base_per_second = 0.20
                audio_per_second = 0.40

        return (audio_per_second if generate_audio else base_per_second) * duration

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate the expected runtime in seconds."""
        backend = inputs.get("backend", "auto")
        if backend == "auto":
            backend = "google" if self._get_google_credentials_status() else "fal"

        if backend == "google":
            return 90.0

        variant = inputs.get("model_variant", "veo3.1")
        if "fast" in variant:
            return 45.0
        return 120.0

    @staticmethod
    def _file_to_data_uri(path_str: str) -> str:
        """Convert a local file into a base64-encoded Data URI."""
        path = Path(path_str)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        mime_type, _ = mimetypes.guess_type(path.name)
        if not mime_type:
            mime_type = "application/octet-stream"
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime_type};base64,{encoded}"

    def _normalize_file_input(
        self, url_value: str | None, path_value: str | None
    ) -> str | None:
        """Normalize file input by converting local file paths to Data URIs or returning URLs."""
        if url_value:
            return url_value
        if path_value:
            return self._file_to_data_uri(path_value)
        return None

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute the video generation tool using the selected backend."""
        backend = inputs.get("backend", "auto")
        if backend == "auto":
            if self._get_google_credentials_status():
                backend = "google"
            elif self._get_fal_api_key():
                backend = "fal"
            else:
                return ToolResult(
                    success=False,
                    error="No backend credentials configured. "
                    + self.install_instructions,
                )

        if backend == "google":
            return self._execute_google(inputs)
        return self._execute_fal(inputs)

    def _execute_google(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute the generation request using the Google GenAI SDK backend."""
        start = time.time()
        try:
            from google.genai import types
            from PIL import Image
            from io import BytesIO
            import requests
            from tools.google_credentials import get_genai_client, GOOGLE_API_TIMEOUT_MS

            http_options = types.HttpOptions(timeout=GOOGLE_API_TIMEOUT_MS)
            client = get_genai_client(http_options=http_options)
        except ImportError as e:
            return ToolResult(
                success=False,
                error=f"Failed to import required Google libraries: {e}. Run 'uv pip install google-genai pillow requests'",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to initialize Google GenAI Client: {e}",
            )

        is_vertex = getattr(client, "vertexai", None)
        if is_vertex is None or not isinstance(is_vertex, bool):
            is_vertex = getattr(client, "_api_client", None) and getattr(
                client._api_client, "vertexai", False
            )

        if is_vertex:
            return ToolResult(
                success=False,
                error="Google Veo video generation via google-genai is only supported using the Gemini Developer API (API key) backend. "
                "Please configure GEMINI_API_KEY/GOOGLE_API_KEY or use the FAL.ai backend.",
            )

        prompt = inputs["prompt"]
        operation = inputs.get("operation", "text_to_video")
        model_variant = inputs.get("model_variant", "veo3.1")
        auto_fix = inputs.get("auto_fix", True)

        # Map to the official preview model unless a custom model name is provided
        if model_variant in {"veo3", "veo3/fast", "veo3.1", "veo3.1/fast"}:
            if is_vertex:
                model_name = "veo-3.1-generate-001"
            else:
                model_name = "veo-3.1-generate-preview"
        else:
            model_name = model_variant

        duration_text = str(inputs.get("duration", "8s")).lower().replace("s", "")
        try:
            duration_seconds = int(duration_text)
        except ValueError:
            duration_seconds = 8

        aspect_ratio = inputs.get("aspect_ratio", "16:9")
        resolution = inputs.get("resolution", "1080p")

        # Validate/Auto-Fix duration based on 1080p/4K or reference-to-video rules
        needs_8s = (resolution in {"1080p", "4k"}) or (
            operation == "reference_to_video"
        )
        if needs_8s and duration_seconds != 8:
            if auto_fix:
                import logging

                logging.getLogger(__name__).warning(
                    f"Google Veo 3.1 requires 8 seconds duration when using "
                    f"resolution={resolution} or operation={operation}. Coercing duration to 8s."
                )
                duration_seconds = 8
            else:
                return ToolResult(
                    success=False,
                    error=f"Google Veo 3.1 requires duration to be 8 seconds when resolution is {resolution} or operation is {operation}.",
                )

        # Construct generation configuration
        config = types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            duration_seconds=duration_seconds,
            resolution=resolution,
            number_of_videos=1,
        )

        if inputs.get("generate_audio") is not None:
            config.generate_audio = inputs["generate_audio"]
        if inputs.get("negative_prompt"):
            config.negative_prompt = inputs["negative_prompt"]
        if inputs.get("seed") is not None:
            config.seed = inputs["seed"]

        def _get_image(url: str | None, path: str | None) -> Image.Image | None:
            if path:
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Local input image not found: {path}")
                return Image.open(path)
            if url:
                resp = requests.get(url, timeout=30)
                resp.raise_for_status()
                return Image.open(BytesIO(resp.content))
            return None

        def _to_sdk_image(pil_img: Image.Image) -> types.Image:
            buf = BytesIO()
            fmt = pil_img.format or "PNG"
            try:
                pil_img.save(buf, format=fmt)
            except KeyError:
                pil_img.save(buf, format="PNG")
                fmt = "PNG"
            return types.Image(
                image_bytes=buf.getvalue(),
                mime_type=f"image/{fmt.lower()}",
            )

        # Build execution input args
        sdk_image = None
        try:
            if operation == "image_to_video":
                image_obj = _get_image(
                    inputs.get("image_url"), inputs.get("image_path")
                )
                if not image_obj:
                    return ToolResult(
                        success=False,
                        error="image_to_video requires image_url or image_path",
                    )
                sdk_image = _to_sdk_image(image_obj)

            elif operation == "first_last_frame_to_video":
                image_obj = _get_image(
                    inputs.get("first_frame_url"), inputs.get("first_frame_path")
                )
                last_image = _get_image(
                    inputs.get("last_frame_url"), inputs.get("last_frame_path")
                )
                if not image_obj or not last_image:
                    return ToolResult(
                        success=False,
                        error="first_last_frame_to_video requires first_frame_url/path and last_frame_url/path",
                    )
                config.last_frame = _to_sdk_image(last_image)
                sdk_image = _to_sdk_image(image_obj)

            elif operation == "reference_to_video":
                ref_images = []
                image_urls = list(inputs.get("reference_image_urls") or [])
                image_paths = list(inputs.get("reference_image_paths") or [])

                for path in image_paths:
                    if not os.path.exists(path):
                        raise FileNotFoundError(
                            f"Local reference image not found: {path}"
                        )
                    ref_images.append(
                        types.VideoGenerationReferenceImage(
                            image=_to_sdk_image(Image.open(path)),
                            reference_type=types.VideoGenerationReferenceType.ASSET,
                        )
                    )
                for url in image_urls:
                    resp = requests.get(url, timeout=30)
                    resp.raise_for_status()
                    ref_images.append(
                        types.VideoGenerationReferenceImage(
                            image=_to_sdk_image(Image.open(BytesIO(resp.content))),
                            reference_type=types.VideoGenerationReferenceType.ASSET,
                        )
                    )
                if not ref_images:
                    return ToolResult(
                        success=False,
                        error="reference_to_video requires reference_image_urls or reference_image_paths",
                    )
                config.reference_images = ref_images

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to load inputs for operation {operation}: {e}",
            )

        try:
            # Submit generation request
            operation_handle = client.models.generate_videos(
                model=model_name, prompt=prompt, image=sdk_image, config=config
            )

            # Poll for completion with safety timeout
            poll_interval = 5
            deadline = time.time() + GOOGLE_API_TIMEOUT_SECONDS
            while not operation_handle.done:
                if time.time() >= deadline:
                    return ToolResult(
                        success=False,
                        error=f"Veo video generation timed out after {GOOGLE_API_TIMEOUT_SECONDS} seconds.",
                    )
                time.sleep(poll_interval)
                operation_handle = client.operations.get(operation_handle)

            if operation_handle.error:
                return ToolResult(
                    success=False,
                    error=f"Veo direct API error: {operation_handle.error}",
                )

            # Download and save final file
            response = operation_handle.response
            if not response or not response.generated_videos:
                return ToolResult(
                    success=False,
                    error="No video generation response received.",
                )
            video_result = response.generated_videos[0]
            video_asset = video_result.video
            if not video_asset:
                return ToolResult(
                    success=False,
                    error="No video asset returned in the response.",
                )
            client.files.download(file=video_asset)

            output_path = Path(inputs.get("output_path", "veo_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            video_asset.save(str(output_path))

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Veo direct API generation failed: {e}",
            )

        from tools.video._shared import probe_output

        probed = probe_output(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": "veo",
                "gateway": "google",
                "model": model_name,
                "prompt": prompt,
                "operation": operation,
                "aspect_ratio": aspect_ratio,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model_name,
        )

    def _execute_fal(self, inputs: dict[str, Any]) -> ToolResult:
        """Execute the generation request using the fal.ai API backend."""
        api_key = self._get_fal_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="FAL_KEY / FAL_AI_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        operation = inputs.get("operation", "text_to_video")
        variant = inputs.get("model_variant", "veo3.1")
        duration = inputs.get("duration", "8s")

        # Current fal Veo 3.1 image-guided endpoints only accept 8-second clips.
        if (
            variant == "veo3.1"
            and operation in {"reference_to_video", "first_last_frame_to_video"}
            and duration != "8s"
        ):
            return ToolResult(
                success=False,
                error=(
                    f"{operation} with {variant} currently requires duration='8s' on fal.ai; "
                    f"received duration='{duration}'"
                ),
            )

        # Build fal.ai model path
        operation_map = {
            "text_to_video": variant,
            "image_to_video": f"{variant}/image-to-video",
            "reference_to_video": f"{variant}/reference-to-video",
            "first_last_frame_to_video": f"{variant}/first-last-frame-to-video",
        }
        model_path = operation_map[operation]

        payload: dict[str, Any] = {"prompt": inputs["prompt"]}
        if inputs.get("duration"):
            payload["duration"] = inputs["duration"]
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        if inputs.get("generate_audio") is not None:
            payload["generate_audio"] = inputs["generate_audio"]
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = inputs["negative_prompt"]
        if inputs.get("seed") is not None:
            payload["seed"] = inputs["seed"]
        if inputs.get("auto_fix") is not None:
            payload["auto_fix"] = inputs["auto_fix"]
        if inputs.get("safety_tolerance"):
            payload["safety_tolerance"] = inputs["safety_tolerance"]

        if operation == "image_to_video":
            image_value = self._normalize_file_input(
                inputs.get("image_url"), inputs.get("image_path")
            )
            if not image_value:
                return ToolResult(
                    success=False,
                    error="image_to_video requires image_url or image_path",
                )
            payload["image_url"] = image_value

        if operation == "reference_to_video":
            image_urls = list(inputs.get("reference_image_urls") or [])
            image_paths = list(inputs.get("reference_image_paths") or [])
            normalized = list(image_urls)
            normalized.extend(self._file_to_data_uri(path) for path in image_paths)
            if not normalized:
                return ToolResult(
                    success=False,
                    error="reference_to_video requires reference_image_urls or reference_image_paths",
                )
            payload["image_urls"] = normalized

        if operation == "first_last_frame_to_video":
            first_frame = self._normalize_file_input(
                inputs.get("first_frame_url"), inputs.get("first_frame_path")
            )
            last_frame = self._normalize_file_input(
                inputs.get("last_frame_url"), inputs.get("last_frame_path")
            )
            if not first_frame or not last_frame:
                return ToolResult(
                    success=False,
                    error="first_last_frame_to_video requires first_frame_url/path and last_frame_url/path",
                )
            payload["first_frame_url"] = first_frame
            payload["last_frame_url"] = last_frame

        headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        }

        try:
            # Submit to queue API (async) — sync endpoint times out for video gen
            submit_resp = requests.post(
                f"https://queue.fal.run/fal-ai/{model_path}",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_resp.raise_for_status()
            queue_data = submit_resp.json()
            status_url = queue_data["status_url"]
            response_url = queue_data["response_url"]

            # Poll until complete with safety timeout
            poll_interval = 5
            deadline = time.time() + GOOGLE_API_TIMEOUT_SECONDS
            while True:
                if time.time() >= deadline:
                    return ToolResult(
                        success=False,
                        error=f"Veo video generation timed out on FAL.ai after {GOOGLE_API_TIMEOUT_SECONDS} seconds.",
                    )
                time.sleep(poll_interval)
                status_resp = requests.get(status_url, headers=headers, timeout=15)
                status_resp.raise_for_status()
                status = status_resp.json().get("status", "UNKNOWN")
                if status == "COMPLETED":
                    break
                if status in ("FAILED", "CANCELLED"):
                    return ToolResult(
                        success=False,
                        error=f"Veo video generation {status.lower()}",
                    )

            # Fetch result
            result_resp = requests.get(response_url, headers=headers, timeout=30)
            if not result_resp.ok:
                detail = result_resp.text[:1000]
                return ToolResult(
                    success=False,
                    error=f"Veo video generation result fetch failed ({result_resp.status_code}): {detail}",
                )
            data = result_resp.json()

            video_url = data["video"]["url"]
            video_response = requests.get(video_url, timeout=120)
            video_response.raise_for_status()

            output_path = Path(inputs.get("output_path", "veo_output.mp4"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(video_response.content)

        except Exception as e:
            return ToolResult(success=False, error=f"Veo video generation failed: {e}")

        from tools.video._shared import probe_output

        probed = probe_output(output_path)

        return ToolResult(
            success=True,
            data={
                "provider": "veo",
                "gateway": "fal",
                "model": f"fal-ai/{model_path}",
                "prompt": inputs["prompt"],
                "operation": operation,
                "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=f"fal-ai/{model_path}",
        )
