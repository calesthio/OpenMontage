"""Direct Volcengine Ark Seedream image generation for product scenes."""

from __future__ import annotations

import base64
import io
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image

from lib.seedance_config import SeedanceConfigError, load_seedance_config
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
from tools.provider_pricing import PriceQuoteRequired


class SeedreamArkImage(BaseTool):
    """Generate product scene candidates through Ark's image API."""

    name = "seedream_ark_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "ark"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:ARK_API_KEY"]
    install_instructions = (
        "Initialize ~/.seedance/config.json with the seedance-product-scene "
        "setup command, or set ARK_API_KEY. Optional: ARK_BASE_URL and "
        "ARK_SEEDREAM_MODEL."
    )
    agent_skills = ["seedance-product-scene"]

    capabilities = [
        "generate_image",
        "image_to_image",
        "product_scene",
        "style_preview",
    ]
    supports = {
        "text_to_image": True,
        "image_to_image": True,
        "product_scene": True,
        "multiple_variants": True,
        "local_image_data_uri": True,
        "url_results": True,
        "base64_results": True,
    }
    best_for = [
        "preserving a supplied product while replacing scene background",
        "producing three controlled product scene candidates",
        "direct Volcengine Ark image generation without a gateway",
    ]
    not_good_for = [
        "offline image generation",
        "batch generation of unselected product styles",
        "adding product claims not supplied by the user",
    ]
    fallback_tools = ["seedream_image", "atlas_image", "openai_image"]

    input_schema = {
        "type": "object",
        "required": [
            "prompt",
            "source_image_path",
            "scene_preset",
            "output_dir",
        ],
        "properties": {
            "prompt": {"type": "string", "minLength": 1},
            "source_image_path": {"type": "string", "minLength": 1},
            "scene_preset": {
                "type": "string",
                "enum": ["luxury", "nature", "tech", "office"],
            },
            "product_name": {"type": "string", "default": "产品"},
            "model": {"type": "string"},
            "size": {"type": "string", "default": "1024x1024"},
            "count": {
                "type": "integer",
                "minimum": 1,
                "maximum": 3,
                "default": 3,
            },
            "output_dir": {"type": "string", "minLength": 1},
            "watermark": {"type": "boolean", "default": False},
        },
        "additionalProperties": False,
    }

    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=512,
        vram_mb=0,
        disk_mb=256,
        network_required=True,
    )
    retry_policy = RetryPolicy(
        max_retries=1,
        retryable_errors=["timeout", "rate_limit"],
    )
    idempotency_key_fields = [
        "prompt",
        "source_image_path",
        "scene_preset",
        "model",
        "size",
        "count",
    ]
    side_effects = [
        "submits a paid request to the Volcengine Ark image API",
        "writes one to three PNG files under output_dir",
    ]
    user_visible_verification = [
        "Inspect the product shape, label, color, and packaging for drift",
        "Compare all candidates before choosing one for video generation",
    ]

    def get_status(self) -> ToolStatus:
        try:
            load_seedance_config()
        except SeedanceConfigError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "Seedream image pricing is not configured; quote count and size "
            "before a paid generation."
        )

    @staticmethod
    def _parse_count(value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= 3:
            raise ValueError("count 必须是 1 到 3 的整数。")
        return value

    @staticmethod
    def _encode_source(path: Path) -> str:
        if not path.is_file():
            raise ValueError(f"找不到产品图：{path}")
        try:
            content = path.read_bytes()
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
                image_format = image.format
        except Exception as exc:
            raise ValueError("产品图无法读取，请上传 JPG、PNG 或 WebP 图片。") from exc
        if len(content) > 10 * 1024 * 1024:
            raise ValueError("产品图不能超过 10MB。")
        mime = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }.get(str(image_format).upper())
        if not mime:
            raise ValueError("产品图格式不支持，请使用 JPG、PNG 或 WebP。")
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    @staticmethod
    def _decode_image(item: Any) -> bytes:
        if isinstance(item, str):
            if item.startswith("data:image"):
                return base64.b64decode(item.split(",", 1)[1], validate=True)
            return base64.b64decode(item, validate=True)
        if isinstance(item, dict):
            encoded = item.get("b64_json") or item.get("base64")
            if encoded:
                return base64.b64decode(encoded, validate=True)
        raise ValueError("ARK 图片响应中没有可用的 base64 图片。")

    @staticmethod
    def _validate_png(content: bytes) -> None:
        try:
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
        except Exception as exc:
            raise ValueError("ARK 返回的图片数据无法解析。") from exc

    @staticmethod
    def _http_error(status_code: int) -> str:
        if status_code == 401:
            return "火山方舟 API Key 好像不对或已过期，请检查本地配置。"
        if status_code == 403:
            return "当前账号没有权限使用该 Seedream 模型，请检查模型是否已开通。"
        if status_code == 429:
            return "火山方舟调用太频繁或额度不足，请稍后再试或检查余额。"
        return f"火山方舟图片生成失败（HTTP {status_code}）。"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        import requests

        started = time.time()
        api_key: str | None = None
        outputs: list[str] = []
        try:
            config = load_seedance_config()
            api_key = config.api_key
            count = self._parse_count(inputs.get("count", 3))
            scene_preset = str(inputs["scene_preset"])
            if scene_preset not in {"luxury", "nature", "tech", "office"}:
                raise ValueError(
                    "scene_preset 必须是 luxury、nature、tech 或 office。"
                )
            source_image = self._encode_source(Path(inputs["source_image_path"]))
            model = str(inputs.get("model") or config.image_model)
            base_url = config.api_base.rstrip("/")
            output_dir = Path(inputs["output_dir"])
            output_dir.mkdir(parents=True, exist_ok=True)
            prompt = str(inputs["prompt"])
            candidate_paths = [
                output_dir / f"scene_{scene_preset}_{index}.png"
                for index in range(1, count + 1)
            ]
            existing_paths = [path for path in candidate_paths if path.exists()]
            if existing_paths:
                raise ValueError(
                    "候选图批次已存在，请使用新的 batch-NNN 目录后再生成。"
                )
            payload_base = {
                "model": model,
                "prompt": prompt,
                "image": source_image,
                "size": str(inputs.get("size", "1024x1024")),
                "output_format": "png",
                "watermark": bool(inputs.get("watermark", False)),
            }

            for output_path in candidate_paths:
                response = requests.post(
                    f"{base_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload_base,
                    timeout=(10, 180),
                )
                if response.status_code >= 400:
                    return ToolResult(
                        success=False,
                        data={"partial_outputs": outputs} if outputs else {},
                        artifacts=outputs,
                        error=self._http_error(response.status_code),
                        cost_usd=None,
                        duration_seconds=round(time.time() - started, 2),
                    )
                response.raise_for_status()
                response_payload = response.json()
                data = response_payload.get("data") or response_payload.get("images") or []
                if not data:
                    raise ValueError("ARK 图片响应为空。")
                item = data[0]
                if isinstance(item, dict) and item.get("url"):
                    url = str(item["url"])
                    if urlsplit(url).scheme != "https":
                        raise ValueError("ARK 返回了不安全的图片地址。")
                    download = requests.get(url, timeout=60)
                    download.raise_for_status()
                    blob = download.content
                else:
                    blob = self._decode_image(item)
                self._validate_png(blob)
                output_path.write_bytes(blob)
                outputs.append(str(output_path))
        except SeedanceConfigError as exc:
            return ToolResult(success=False, error=str(exc), cost_usd=None)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            message = str(exc)
            if api_key:
                message = message.replace(api_key, "[redacted]")
            return ToolResult(
                success=False,
                data={"partial_outputs": outputs} if outputs else {},
                artifacts=outputs,
                error=message,
                cost_usd=None,
                duration_seconds=round(time.time() - started, 2),
            )
        except Exception as exc:
            message = str(exc)
            if api_key:
                message = message.replace(api_key, "[redacted]")
            return ToolResult(
                success=False,
                data={"partial_outputs": outputs} if outputs else {},
                artifacts=outputs,
                error=f"火山方舟图片生成失败：{message}",
                cost_usd=None,
                duration_seconds=round(time.time() - started, 2),
            )

        return ToolResult(
            success=True,
            data={
                "style_preview_id": f"{scene_preset}-candidate-set",
                "scene_preset": scene_preset,
                "product_name": str(inputs.get("product_name", "产品")),
                "provider": "ark",
                "model": model,
                "prompt": prompt,
                "size": inputs.get("size", "1024x1024"),
                "outputs": outputs,
                "duration_seconds": round(time.time() - started, 2),
            },
            artifacts=outputs,
            cost_usd=None,
            duration_seconds=round(time.time() - started, 2),
            model=model,
        )
