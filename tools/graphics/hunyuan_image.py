"""Tencent Hunyuan (腾讯混元) cloud image generation (3.0) via TokenHub API.

Calls the Tencent TokenHub API (tokenhub.tencentmaas.com) using simple Bearer
token authentication. This is the OpenAI-compatible API gateway for Tencent
Hunyuan image models — no TC3-HMAC-SHA256 signing required.

API flow: POST /v1/api/image/submit -> poll /v1/api/image/query ->
download data[].url.

Authentication uses a TokenHub API key obtained from the Tencent Cloud
TokenHub console (https://console.cloud.tencent.com/tokenhub).
"""

from __future__ import annotations

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

_HOST = "tokenhub.tencentmaas.com"
_SUBMIT_PATH = "/v1/api/image/submit"
_QUERY_PATH = "/v1/api/image/query"

# TokenHub model identifier for 混元生图 3.0
_MODEL = "hy-image-v3.0"


class HunyuanImage(BaseTool):
    """Tencent Hunyuan cloud image generation (3.0) via TokenHub API."""

    name = "hunyuan_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "hunyuan_cloud"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API

    dependencies = ["env:TENCENT_TOKENHUB_API_KEY"]
    install_instructions = (
        "Set TENCENT_TOKENHUB_API_KEY to your Tencent Cloud TokenHub API key.\n"
        "  Get it at https://console.cloud.tencent.com/tokenhub"
    )
    agent_skills = ["visual-style"]

    capabilities = ["generate_image", "text_to_image"]
    supports = {
        "negative_prompt": False,
        "seed": True,
        "custom_size": True,
        "reference_image": True,
        "prompt_rewrite": True,
    }
    best_for = [
        "Hunyuan text-to-image via Tencent TokenHub API",
        "simple Bearer-token auth (no TC3 signing required)",
        "direct Tencent Cloud quota usage (not through a third-party gateway)",
        "Chinese-language prompt understanding",
    ]
    not_good_for = [
        "offline generation or air-gapped environments",
        "users without Tencent Cloud account and real-name verification",
    ]
    fallback_tools = ["dashscope_image", "flux_image", "openai_image", "recraft_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "maxLength": 8192,
                "description": (
                    "Image description. Max 8192 UTF-8 characters. "
                    "Supports Chinese and English. Be specific about subject, "
                    "composition, style, and mood."
                ),
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 3,
                "description": (
                    "Reference images per upstream Images.N param (max 3). "
                    "Each entry is a publicly accessible URL or a local file path "
                    "(auto-encoded to base64 data URI). "
                    "Single image: 50-5000px per side, base64 < 6MB. "
                    "Formats: jpg/png/jpeg/webp/bmp/tiff."
                ),
            },
            "resolution": {
                "type": "string",
                "default": "1024:1024",
                "description": (
                    'Image resolution as "W:H" (colon separator, per upstream '
                    "Resolution param). W, H in [512, 2048], product (W*H) <= "
                    '1024x1024 pixels. Examples: "1024:1024", "768:1024", '
                    '"1024:576".'
                ),
            },
            "seed": {
                "type": "integer",
                "minimum": 1,
                "maximum": 4294967295,
                "description": (
                    "Random seed in [1, 4294967295]. "
                    "Note: seed is ignored when revise is enabled (default)."
                ),
            },
            "revise": {
                "type": "integer",
                "enum": [0, 1],
                "default": 1,
                "description": (
                    "Prompt auto-rewrite toggle per upstream Revise param. "
                    "1 = enabled (default, adds ~20s processing), 0 = disabled. "
                    "When disabled, caller should handle prompt rewriting."
                ),
            },
            "logo_add": {
                "type": "integer",
                "enum": [0, 1],
                "default": 1,
                "description": (
                    "Add 'AI-generated' watermark per upstream LogoAdd param. "
                    "1 = add watermark (default), 0 = no watermark. "
                    "Values other than 0 or 1 are treated as 1."
                ),
            },
            "logo_param": {
                "type": "object",
                "properties": {
                    "logo_url": {
                        "type": "string",
                        "description": "Custom watermark image URL.",
                    },
                    "logo_image": {
                        "type": "string",
                        "description": "Custom watermark image as base64-encoded string.",
                    },
                },
                "description": (
                    "Custom watermark settings per upstream LogoParam. "
                    "Default: \"图片由 AI 生成\" at bottom-right. "
                    "Note: custom watermarks may not be supported by the engine "
                    "(error: InvalidParameterValue.LogoParamErr)."
                ),
            },
            "output_path": {
                "type": "string",
                "description": "Output file path for the generated image (PNG).",
            },
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 2,
                "default": 5.0,
                "description": "Seconds between status polls.",
            },
            "timeout_seconds": {
                "type": "integer",
                "minimum": 60,
                "default": 600,
                "description": "Maximum seconds to wait for generation.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["rate_limit", "timeout"],
    )
    idempotency_key_fields = [
        "prompt",
        "resolution",
        "images",
        "seed",
        "revise",
        "logo_add",
        "logo_param",
    ]
    side_effects = [
        "writes image file to output_path",
        "calls Tencent TokenHub API (Bearer-token submit + poll + download)",
    ]
    user_visible_verification = [
        "Inspect generated image for quality and prompt adherence",
        "Check for watermark if logo_add=0 was requested",
    ]

    # ------------------------------------------------------------------
    # Credential helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _api_key() -> str | None:
        val = os.environ.get("TENCENT_TOKENHUB_API_KEY", "")
        if val and not val.strip().startswith("#"):
            return val.strip()
        return None

    # ------------------------------------------------------------------
    # Tool contract methods
    # ------------------------------------------------------------------

    def get_status(self) -> ToolStatus:
        if self._api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Estimate cost in USD.

        Tencent TokenHub credit-based pricing (1 credit = 1.2 RMB ≈ $0.167 USD):
        - hy-image-v3.0: ~0.5 credits/image → ~$0.08

        Source: https://cloud.tencent.com.cn/document/product/1823/130054
        """
        _CREDIT_TO_USD = 1.2 / 7.2  # 1 credit = 1.2 RMB, ~7.2 RMB/USD
        credits = 0.5
        return round(credits * _CREDIT_TO_USD, 2)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate wall-clock time in seconds.

        Per upstream docs, prompt rewrite (revise=1) adds ~20s. Including
        queuing and download, 120s is a safe upper-bound.
        """
        return 120.0

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = self._api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="TENCENT_TOKENHUB_API_KEY not set. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key=api_key)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Hunyuan TokenHub image generation failed: {self._safe_error(exc)}",
            )

        result.duration_seconds = round(time.time() - start, 2)
        return result

    # ------------------------------------------------------------------
    # Generation pipeline
    # ------------------------------------------------------------------

    def _generate(
        self, inputs: dict[str, Any], *, api_key: str,
    ) -> ToolResult:
        import requests

        # Guard: refuse to make paid API calls without an explicit output_path.
        # A CWD-relative default would leak files into the project root when
        # called by selectors or other automated tooling.
        if not inputs.get("output_path"):
            return ToolResult(
                success=False,
                error="output_path is required for hunyuan_image generation.",
            )

        payload = self._build_payload(inputs)
        task_id = self._submit_task(payload, model=_MODEL, api_key=api_key)
        image_urls = self._poll_task(
            task_id,
            model=_MODEL,
            api_key=api_key,
            poll_interval=float(inputs.get("poll_interval_seconds", 5.0)),
            timeout_seconds=int(inputs.get("timeout_seconds", 600)),
        )

        output_paths = self._resolve_output_paths(
            inputs["output_path"],
            count=len(image_urls),
        )
        for path, url in zip(output_paths, image_urls):
            download = requests.get(url, timeout=120)
            download.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(download.content)

        return ToolResult(
            success=True,
            data={
                "provider": "hunyuan_cloud",
                "route": "tokenhub",
                "model": _MODEL,
                "prompt": inputs["prompt"],
                "resolution": payload.get("resolution", "1024:1024"),
                "revise": payload.get("revise", 1),
                "logo_add": payload.get("logo_add", 1),
                "task_id": task_id,
                "output": str(output_paths[0]),
                "outputs": [str(p) for p in output_paths],
                "images_generated": len(output_paths),
            },
            artifacts=[str(p) for p in output_paths],
            cost_usd=self.estimate_cost(inputs),
            model=_MODEL,
        )

    # ------------------------------------------------------------------
    # Payload construction
    # ------------------------------------------------------------------

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Build the request body for TokenHub image submit.

        TokenHub async endpoints use snake_case versions of the upstream
        SubmitTextToImageJob parameter names (e.g. Resolution -> resolution,
        Images -> images).
        """
        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
        }

        # Optional parameters (snake_case of upstream SubmitTextToImageJob params)
        if inputs.get("resolution"):
            payload["resolution"] = inputs["resolution"]
        if inputs.get("seed") is not None:
            payload["seed"] = int(inputs["seed"])
        if "revise" in inputs:
            payload["revise"] = int(inputs["revise"])
        if "logo_add" in inputs:
            payload["logo_add"] = int(inputs["logo_add"])
        if inputs.get("logo_param"):
            logo_param: dict[str, str] = {}
            lp = inputs["logo_param"]
            if lp.get("logo_url"):
                logo_param["logo_url"] = lp["logo_url"]
            if lp.get("logo_image"):
                logo_param["logo_image"] = lp["logo_image"]
            if logo_param:
                payload["logo_param"] = logo_param

        # Reference images — maps to upstream Images.N
        # TokenHub accepts URLs or base64 data URIs in the images array
        image_refs = inputs.get("images")
        if image_refs:
            payload["images"] = self._resolve_images(image_refs)

        return payload

    @staticmethod
    def _resolve_images(refs: list[str]) -> list[str]:
        """Resolve reference images to strings for the TokenHub API.

        Each entry may be:
        - An HTTP(S) URL → passed through unchanged
        - A data URI (``data:...``) → passed through unchanged
        - A local file path → base64-encoded as a data URI

        Per upstream docs: single image 50-5000px per side, base64 < 6MB.
        Formats: jpg/jpeg/png/bmp/tiff/webp.
        """
        import base64

        resolved: list[str] = []
        for ref in refs:
            if ref.startswith("data:") or ref.startswith("http://") or ref.startswith("https://"):
                resolved.append(ref)
                continue

            image_path = Path(ref)
            if not image_path.is_file():
                raise FileNotFoundError(f"Reference image not found: {ref}")

            raw = image_path.read_bytes()
            max_raw = 6 * 1024 * 1024  # 6MB per upstream limit
            if len(raw) > max_raw:
                raise ValueError(
                    f"Image too large ({len(raw)} bytes). Max ~6MB raw."
                )

            suffix = image_path.suffix.lower()
            mime_map = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".bmp": "image/bmp",
                ".tiff": "image/tiff",
                ".tif": "image/tiff",
                ".webp": "image/webp",
            }
            mime = mime_map.get(suffix, "image/png")
            data = base64.b64encode(raw).decode("ascii")
            resolved.append(f"data:{mime};base64,{data}")
        return resolved

    # ------------------------------------------------------------------
    # API communication (TokenHub OpenAI-compatible)
    # ------------------------------------------------------------------

    @staticmethod
    def _auth_headers(api_key: str) -> dict[str, str]:
        """Build common request headers for TokenHub API calls."""
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def _submit_task(
        self, payload: dict[str, Any], *, model: str, api_key: str,
    ) -> str:
        """Submit an image generation task and return the task ID.

        POST /v1/api/image/submit
        Request: {"model": "hy-image-v3.0", "prompt": "...", ...}
        Response: {"id": "...", "status": "queued", ...}
        """
        import requests

        body = {
            "model": model,
            **payload,
        }
        url = f"https://{_HOST}{_SUBMIT_PATH}"
        resp = requests.post(
            url,
            json=body,
            headers=self._auth_headers(api_key),
            timeout=30,
        )
        data = self._json_or_raise(resp)
        self._check_response(data)

        task_id = data.get("id")
        if not task_id:
            raise RuntimeError(
                f"TokenHub submit returned no task id: {data}"
            )
        return task_id

    def _poll_task(
        self,
        task_id: str,
        *,
        model: str,
        api_key: str,
        poll_interval: float,
        timeout_seconds: int,
    ) -> list[str]:
        """Poll /v1/api/image/query until completion, return image download URLs.

        Response when completed:
        {"status": "completed", "data": [{"url": "...", "revised_prompt": "..."}]}

        The data array may contain multiple images. Each URL is valid for ~1 hour.
        """
        import requests

        url = f"https://{_HOST}{_QUERY_PATH}"

        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            time.sleep(poll_interval)

            resp = requests.post(
                url,
                json={"model": model, "id": task_id},
                headers=self._auth_headers(api_key),
                timeout=30,
            )
            data = self._json_or_raise(resp)
            self._check_response(data)

            status = data.get("status", "")

            if status == "completed":
                result_data = data.get("data") or []
                urls = [item.get("url") for item in result_data if item.get("url")]
                if not urls:
                    raise RuntimeError(
                        f"TokenHub task {task_id} completed but no data[].url: {data}"
                    )
                return urls

            if status == "failed":
                error_info = data.get("error") or {}
                error_msg = error_info.get("message", "unknown error")
                raise RuntimeError(
                    f"TokenHub task {task_id} failed: {error_msg}"
                )

            # queued / running / in_progress — continue polling
            if status not in ("queued", "running", "in_progress"):
                raise RuntimeError(
                    f"TokenHub task {task_id} returned unknown status: {status}"
                )

        raise TimeoutError(
            f"TokenHub task {task_id} did not finish within {timeout_seconds}s"
        )

    # ------------------------------------------------------------------
    # Error handling helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        """Redact secret values from exception messages."""
        msg = str(exc)
        for var in ("TENCENT_TOKENHUB_API_KEY",):
            val = os.environ.get(var, "")
            if val:
                msg = msg.replace(val, "[redacted]")
        return msg

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        """Parse JSON response body or raise with HTTP status."""
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Non-JSON response from TokenHub API: HTTP {response.status_code}"
            ) from exc

    @staticmethod
    def _check_response(payload: dict[str, Any]) -> None:
        """Check the TokenHub API response for errors.

        TokenHub returns errors at the top level with an ``error`` field.
        """
        error = payload.get("error")
        if error:
            message = error.get("message", "unknown error")
            code = error.get("code", error.get("type", "unknown"))
            raise RuntimeError(
                f"TokenHub API error: code={code}, message={message}"
            )

    # ------------------------------------------------------------------
    # Output helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_output_paths(base: str, count: int) -> list[Path]:
        """Derive distinct paths for ``count`` images.

        Single image keeps the base path unchanged; multiple images insert an
        index before the extension (foo.png -> foo_1.png, foo_2.png, ...).
        """
        base_path = Path(base)
        if count <= 1:
            return [base_path]
        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        return [parent / f"{stem}_{i}{suffix}" for i in range(1, count + 1)]
