"""DashScope (Alibaba Cloud Bailian) image generation via Qwen-Image models.

Uses the DashScope-native multimodal-generation endpoint (NOT OpenAI-compatible
mode, which only supports /chat/completions and /embeddings). The response
contains a temporary image URL (valid ~24h) that must be downloaded separately.
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


class DashscopeImage(BaseTool):
    name = "dashscope_image"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "dashscope"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set DASHSCOPE_API_KEY to your Alibaba Cloud DashScope API key.\n"
        "  Get one at https://dashscope.aliyun.com/"
    )
    fallback = "grok_image"
    fallback_tools = ["grok_image", "openai_image", "flux_image", "recraft_image"]
    agent_skills = ["dashscope"]

    capabilities = ["generate_image", "text_to_image"]
    supports = {
        "multiple_outputs": True,
        "aspect_ratio": True,
        "resolution": True,
        "negative_prompt": True,
        "seed": True,
    }
    best_for = [
        "high-quality image generation with Qwen-Image models",
        "Chinese-language prompt understanding",
        "cost-effective image generation via Alibaba Cloud",
    ]
    not_good_for = ["offline generation", "image editing (use grok_image edit mode)"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "enum": [
                    "qwen-image-3.0-pro",
                    "qwen-image-3.0",
                    "qwen-image-2.1-pro",
                    "qwen-image-2.1-turbo",
                    "qwen-image-2.0-pro",
                    "qwen-image-2.0",
                    "qwen-image-max",
                    "wan2.7-image",
                    "z-image-turbo",
                ],
                "default": "qwen-image-2.0-pro",
                "description": (
                    "qwen-image-3.0-* and qwen-image-2.1-* are the current "
                    "generation/editing models; the 2.0 series is legacy. "
                    "This tool calls text-to-image only."
                ),
            },
            "size": {
                "type": "string",
                "default": "1024*1024",
                "description": (
                    'Image size as "W*H" (asterisk separator, NOT "x"). '
                    'Examples: "1024*1024", "2048*2048", "2688*1536". '
                    '"auto" lets qwen-image-2.1-*/3.0-* choose a resolution '
                    "from the prompt; legacy models reject it."
                ),
            },
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 6},
            "negative_prompt": {
                "type": "string",
                "description": (
                    "Negative prompt (max 500 chars). Things to avoid in the "
                    "image. Supported by qwen-image-3.0-* and the legacy 2.0 "
                    "series; omitted automatically for qwen-image-2.1-*."
                ),
            },
            "prompt_extend": {
                "type": "boolean",
                "default": True,
                "description": "Enable DashScope prompt auto-rewrite for better results.",
            },
            "prompt_extend_mode": {
                "type": "string",
                "enum": ["direct", "agent"],
                "description": (
                    "Prompt-rewrite mode for qwen-image-2.1-*/3.0-* only. "
                    "'direct' is the provider default; 'agent' (text-to-image "
                    "only) produces more elaborate rewrites."
                ),
            },
            "enable_thinking": {
                "type": "boolean",
                "description": (
                    "qwen-image-2.1-*/3.0-* only. Enables model reasoning for "
                    "better quality at the cost of latency; requires "
                    "prompt_extend=true."
                ),
            },
            "watermark": {"type": "boolean", "default": False},
            "seed": {"type": "integer", "minimum": 0, "maximum": 2147483647},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = [
        "prompt",
        "model",
        "size",
        "n",
        "negative_prompt",
        "seed",
        "prompt_extend",
        "watermark",
    ]
    side_effects = [
        "writes image file to output_path",
        "calls DashScope (Alibaba Cloud) image generation API",
    ]
    user_visible_verification = [
        "Inspect generated image for relevance and quality"
    ]

    ENDPOINT = (
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation"
    )

    # Parameter support changed across Qwen-Image generations: the 2.1 series
    # dropped negative_prompt, and only 2.1/3.0 accept prompt_extend_mode,
    # enable_thinking, and size="auto".
    V21_PREFIX = "qwen-image-2.1"
    V30_PREFIX = "qwen-image-3.0"
    MODERN_FAMILIES = {"v21", "v30"}

    @classmethod
    def _model_family(cls, model: str) -> str:
        if model.startswith(cls.V30_PREFIX):
            return "v30"
        if model.startswith(cls.V21_PREFIX):
            return "v21"
        return "legacy"

    def get_status(self) -> ToolStatus:
        if os.environ.get("DASHSCOPE_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Conservative baseline for the 2.0 series; DashScope bills per image.
        # The 2.1 and 3.0 series are priced by output tier (1k/2k) — check the
        # DashScope console, and treat this figure as a floor for those models.
        n = int(inputs.get("n", 1))
        return n * 0.02

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY not set. " + self.install_instructions,
            )

        import requests

        start = time.time()
        try:
            payload = self._build_payload(inputs)
            response = requests.post(
                self.ENDPOINT,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            data = response.json()

            image_urls = self._extract_image_urls(data)
            if not image_urls:
                return ToolResult(
                    success=False,
                    error="DashScope returned no image URLs",
                )

            # DashScope bills per image and URLs expire ~24h; save every one.
            output_paths = self._resolve_output_paths(
                inputs.get("output_path", "dashscope_image.png"),
                count=len(image_urls),
            )
            for path, url in zip(output_paths, image_urls):
                download = requests.get(url, timeout=120)
                download.raise_for_status()
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(download.content)

            usage = data.get("usage", {})
            n_generated = len(image_urls)

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"DashScope image generation failed: {self._safe_error(e)}",
            )

        return ToolResult(
            success=True,
            data={
                "provider": "dashscope",
                "model": payload["model"],
                "prompt": inputs["prompt"],
                "size": payload["parameters"]["size"],
                "parameters": dict(payload["parameters"]),
                "output": str(output_paths[0]),
                "outputs": [str(p) for p in output_paths],
                "images_generated": n_generated,
                "usage": usage,
            },
            artifacts=[str(p) for p in output_paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=payload["model"],
        )

    @staticmethod
    def _extract_image_urls(data: dict[str, Any]) -> list[str]:
        """Collect image URLs from every choice whose finish_reason is "stop".

        Per Qwen Cloud docs, a multi-output task is SUCCEEDED if at least one
        image is generated; failed choices carry finish_reason != "stop" and
        must be skipped to avoid downloading partial/empty results.
        """
        urls: list[str] = []
        for choice in data.get("output", {}).get("choices", []):
            if choice.get("finish_reason") != "stop":
                continue
            for item in choice.get("message", {}).get("content", []):
                url = item.get("image")
                if url:
                    urls.append(url)
        return urls

    @staticmethod
    def _resolve_output_paths(base: str, count: int) -> list[Path]:
        """Derive distinct paths for `count` images. Single image keeps the
        base path unchanged; multiple images insert an index before the
        extension (foo.png -> foo_1.png, foo_2.png, ...)."""
        base_path = Path(base)
        if count <= 1:
            return [base_path]
        stem = base_path.stem
        suffix = base_path.suffix
        parent = base_path.parent
        return [parent / f"{stem}_{i}{suffix}" for i in range(1, count + 1)]

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        model = inputs.get("model", "qwen-image-2.0-pro")
        family = self._model_family(model)
        modern = family in self.MODERN_FAMILIES

        size = inputs.get("size", "1024*1024")
        if size == "auto" and not modern:
            raise ValueError(
                'size="auto" is only supported by qwen-image-2.1-*/3.0-*; '
                f"pass an explicit W*H size for {model!r}."
            )

        mode = inputs.get("prompt_extend_mode")
        if mode and not modern:
            raise ValueError(
                "prompt_extend_mode is only supported by qwen-image-2.1-*/"
                f"3.0-* (got model {model!r})."
            )

        thinking = inputs.get("enable_thinking")
        if thinking is not None and not modern:
            raise ValueError(
                "enable_thinking is only supported by qwen-image-2.1-*/"
                f"3.0-* (got model {model!r})."
            )

        prompt_extend = bool(inputs.get("prompt_extend", True))
        if thinking and not prompt_extend:
            raise ValueError(
                "enable_thinking requires prompt_extend=true."
            )

        parameters: dict[str, Any] = {
            "size": size,
            "n": int(inputs.get("n", 1)),
            "prompt_extend": prompt_extend,
            "watermark": bool(inputs.get("watermark", False)),
        }
        # The 2.1 series does not accept negative_prompt; 3.0 and legacy 2.0 do.
        if inputs.get("negative_prompt") and family != "v21":
            parameters["negative_prompt"] = inputs["negative_prompt"]
        if inputs.get("seed") is not None:
            parameters["seed"] = int(inputs["seed"])
        if modern:
            if mode:
                parameters["prompt_extend_mode"] = mode
            if thinking is not None:
                parameters["enable_thinking"] = bool(thinking)

        return {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": inputs["prompt"]}],
                    }
                ]
            },
            "parameters": parameters,
        }

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace(
            os.environ.get("DASHSCOPE_API_KEY", ""), "[redacted]"
        )
