"""Doubao/Volcengine Ark vision understanding via Responses API."""

from __future__ import annotations

import base64
import json
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


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"


def _api_key() -> str | None:
    return os.environ.get("DOUBAO_VISION_API_KEY") or os.environ.get("ARK_API_KEY")


def _base_url() -> str:
    return os.environ.get("DOUBAO_VISION_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _model_name(inputs: dict[str, Any]) -> str:
    model = str(inputs.get("model") or os.environ.get("DOUBAO_VISION_MODEL") or "").strip()
    if not model:
        raise ValueError("DOUBAO_VISION_MODEL or model input is required")
    return model


def _file_to_data_uri(path_str: str) -> str:
    path = Path(path_str)
    if not path.is_file():
        raise FileNotFoundError(f"Image file not found: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type:
        mime_type = "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_content(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    output = payload.get("output") or []
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        content_items = item.get("content") or []
        if isinstance(content_items, str):
            texts.append(content_items)
            continue
        for content in content_items:
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                texts.append(content["text"])
    if texts:
        return "".join(texts)

    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content", "")
    if isinstance(content, list):
        return "".join(str(item.get("text", "")) for item in content if isinstance(item, dict))
    return str(content)


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start : end + 1])
        raise


class DoubaoVisionUnderstand(BaseTool):
    name = "doubao_vision_understand"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "vision_understanding"
    provider = "doubao"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies: list[str] = []
    install_instructions = (
        "Set DOUBAO_VISION_API_KEY or ARK_API_KEY to a Volcengine Ark API key.\n"
        "Set DOUBAO_VISION_MODEL to your Doubao vision endpoint/model id.\n"
        "Optional: set DOUBAO_VISION_BASE_URL for a custom Volcengine Ark Responses endpoint."
    )
    agent_skills = ["video-understand", "ai-video-gen"]

    capabilities = [
        "image_description",
        "visual_qa",
        "seedance_prompt_reverse",
        "reference_video_keyframe_understanding",
    ]
    supports = {
        "volcengine_responses_api": True,
        "local_image_data_uri": True,
        "multiple_images": True,
        "json_output": True,
    }
    best_for = [
        "understanding reference-video keyframes",
        "reverse-engineering visual style, camera, pacing, and Seedance prompts",
        "Chinese creator-video visual analysis",
    ]
    not_good_for = ["offline analysis", "bypassing human review"]

    input_schema = {
        "type": "object",
        "required": ["image_paths", "prompt"],
        "properties": {
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "prompt": {"type": "string"},
            "model": {"type": "string"},
            "response_format": {
                "type": "string",
                "enum": ["text", "json"],
                "default": "json",
            },
            "temperature": {"type": "number", "default": 0.2},
            "max_tokens": {"type": "integer", "default": 1200},
            "timeout_seconds": {"type": "integer", "default": 120},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "parsed": {"type": "object"},
            "model": {"type": "string"},
            "provider": {"type": "string"},
        },
    }
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=256,
        vram_mb=0,
        disk_mb=20,
        network_required=True,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["image_paths", "image_urls", "prompt", "model"]
    side_effects = ["calls Doubao/Volcengine Ark vision API"]
    user_visible_verification = [
        "Review visual summary against keyframes",
        "Edit reversed Seedance prompts before approval",
    ]

    def get_status(self) -> ToolStatus:
        if _api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        image_paths = inputs.get("image_paths") or []
        image_urls = inputs.get("image_urls") or []
        if not image_paths and not image_urls:
            raise ValueError("image_paths or image_urls is required")

        content: list[dict[str, Any]] = []
        content.extend(
            {"type": "input_image", "image_url": _file_to_data_uri(path)}
            for path in image_paths
        )
        content.extend(
            {"type": "input_image", "image_url": url}
            for url in image_urls
        )
        content.append({"type": "input_text", "text": inputs["prompt"]})
        payload: dict[str, Any] = {
            "model": _model_name(inputs),
            "input": [{"role": "user", "content": content}],
            "temperature": float(inputs.get("temperature", 0.2)),
            "max_output_tokens": int(inputs.get("max_tokens", 1200)),
        }
        return payload

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = _api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="DOUBAO_VISION_API_KEY or ARK_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        try:
            payload = self._build_payload(inputs)
            response = requests.post(
                f"{_base_url()}/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=int(inputs.get("timeout_seconds", 120)),
            )
            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                detail = response.text[:800] if getattr(response, "text", "") else ""
                raise RuntimeError(f"{exc}; response={detail}") from exc
            response_payload = response.json()
            content = _extract_content(response_payload)
        except Exception as exc:
            return ToolResult(success=False, error=f"Doubao vision request failed: {exc}")

        parsed: dict[str, Any] | None = None
        if inputs.get("response_format", "json") == "json":
            try:
                parsed = _parse_json_content(content)
            except json.JSONDecodeError:
                if content.strip():
                    excerpt = content[:800]
                else:
                    excerpt = json.dumps(response_payload, ensure_ascii=False)[:1200]
                excerpt = excerpt.replace(_api_key() or "", "[redacted]")
                return ToolResult(
                    success=False,
                    error=(
                        "Doubao vision response was not valid JSON. "
                        f"Response excerpt: {excerpt}"
                    ),
                )

        return ToolResult(
            success=True,
            data={
                "provider": "doubao",
                "model": payload["model"],
                "content": content,
                "parsed": parsed or {},
                "usage": response_payload.get("usage", {}),
            },
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )
