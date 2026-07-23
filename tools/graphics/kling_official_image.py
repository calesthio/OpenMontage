"""Kling official API image generation provider."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from tools._kling.account import account_usage_hint_for_error, get_account_costs
from tools._kling.callbacks import validate_callback_url
from tools._kling.client import KlingClient
from tools._kling.elements import element_ids, normalize_element_list
from tools._kling.errors import KlingAPIError
from tools._kling.media import (
    extension_from_url,
    normalize_image_input,
    numbered_output_path,
    output_path_with_suffix,
)
from tools._kling.omni import build_image_prompt_references
from tools._kling.schemas import (
    IMAGE_ASPECT_RATIOS,
    IMAGE_GENERATION_MODELS,
    IMAGE_MODELS,
    IMAGE_REFERENCE_TYPES,
    IMAGE_RESOLUTIONS,
    IMAGE_RESULT_TYPES,
    OMNI_IMAGE_MODELS,
)
from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


class KlingOfficialImage(BaseTool):
    name = "kling_official_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "kling_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:KLING_API_KEY"]
    install_instructions = (
        "Set KLING_API_KEY in .env for the official Kling API. "
        "Optionally set KLING_API_BASE_URL to override the default Singapore endpoint."
    )
    agent_skills = ["kling-official"]

    capabilities = ["generate_image", "text_to_image", "image_edit"]
    supports = {
        "text_to_image": True,
        "image_edit": True,
        "negative_prompt": True,
        "aspect_ratio": True,
    }
    best_for = [
        "official Kling image generation",
        "subject or face reference generation",
        "Omni multi-reference image workflows",
    ]
    not_good_for = ["offline generation", "free generation", "non-Kling model families"]
    fallback_tools = ["flux_image", "google_imagen", "openai_image", "recraft_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "negative_prompt": {"type": "string"},
            "operation": {"type": "string", "enum": ["generate", "omni"], "default": "generate"},
            "generation_mode": {"type": "string", "enum": ["generate", "edit"], "default": "generate"},
            "api_family": {"type": "string", "enum": ["generation", "omni"], "default": "generation"},
            "model_name": {"type": "string", "enum": IMAGE_MODELS, "default": "kling-v3"},
            "image_url": {"type": "string"},
            "image_path": {"type": "string"},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "image_list": {"type": "array"},
            "image_reference": {"type": "string", "enum": IMAGE_REFERENCE_TYPES},
            "image_fidelity": {"type": "number", "default": 0.5},
            "human_fidelity": {"type": "number", "default": 0.45},
            "resolution": {"type": "string", "enum": IMAGE_RESOLUTIONS, "default": "1k"},
            "aspect_ratio": {"type": "string", "enum": IMAGE_ASPECT_RATIOS, "default": "16:9"},
            "n": {"type": "integer", "default": 1},
            "result_type": {"type": "string", "enum": IMAGE_RESULT_TYPES, "default": "single"},
            "series_amount": {"type": "string"},
            "element_list": {"type": "array"},
            "watermark": {"type": "boolean", "default": False},
            "callback_url": {"type": "string"},
            "external_task_id": {"type": "string"},
            "include_account_usage": {
                "type": "boolean",
                "default": False,
                "description": "Optional low-frequency account usage diagnostic; not used by default.",
            },
            "timeout_seconds": {"type": "integer", "default": 600},
            "poll_interval": {"type": "number", "default": 3.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=200, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["1302", "1303", "5000", "5001", "5002"],
    )
    idempotency_key_fields = [
        "prompt",
        "negative_prompt",
        "operation",
        "api_family",
        "model_name",
        "image_url",
        "image_path",
        "image_urls",
        "image_paths",
        "image_list",
        "image_reference",
        "image_fidelity",
        "human_fidelity",
        "aspect_ratio",
        "resolution",
        "n",
        "result_type",
        "series_amount",
        "element_list",
        "watermark",
    ]
    side_effects = [
        "paid remote generation via official Kling API",
        "writes image file(s) to output_path",
    ]
    user_visible_verification = ["Inspect generated image for quality, prompt adherence, and reference fidelity"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        n = int(inputs.get("n", 1) or 1)
        resolution = str(inputs.get("resolution", "1k"))
        api_family = str(inputs.get("api_family", "generation"))
        base = 0.04 if api_family == "generation" else 0.08
        if resolution == "2k":
            base *= 1.8
        if resolution == "4k":
            base *= 3.5
        if inputs.get("result_type") == "series":
            base *= 1.5
            amount = inputs.get("series_amount")
            if amount and str(amount).isdigit():
                base *= max(int(str(amount)), 1)
        if api_family == "omni":
            reference_count = sum(len(inputs.get(key) or []) for key in ("image_list", "image_urls", "image_paths", "element_list"))
            if inputs.get("image_url") or inputs.get("image_path"):
                reference_count += 1
            base *= 1 + (0.08 * reference_count)
        return round(base * max(n, 1), 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 90.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = super().dry_run(inputs)
        result.update(
            {
                "paid_api": True,
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative OpenMontage estimate; official account usage reconciliation is planned for Phase 2.",
            }
        )
        return result

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            self.check_dependencies()
        except DependencyError as exc:
            return ToolResult(success=False, error=str(exc))

        start = time.time()
        try:
            request = self._build_request(inputs)
            client = KlingClient()
            task_id = client.create_classic_task(request["path"], request["payload"])
            outputs = client.poll_classic(
                request["path"],
                task_id,
                "images",
                timeout_seconds=int(inputs.get("timeout_seconds", 600)),
                poll_interval=float(inputs.get("poll_interval", 3.0)),
            )
            paths = self._download_images(client, outputs, inputs)
        except (KlingAPIError, TimeoutError, ValueError, KeyError, FileNotFoundError) as exc:
            data: dict[str, Any] = {"provider": self.provider}
            if isinstance(exc, KlingAPIError):
                data.update(
                    {
                        "error_code": exc.code,
                        "request_id": exc.request_id,
                        "http_status": exc.http_status,
                    }
                )
                data["account_usage_diagnostic"] = account_usage_hint_for_error(exc)
            return ToolResult(success=False, data=data, error=f"Kling official image generation failed: {exc}")
        except Exception as exc:
            return ToolResult(success=False, data={"provider": self.provider}, error=f"Kling official image generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": request["model"],
                "task_id": task_id,
                "api_family": request["api_family"],
                "operation": request["operation"],
                "prompt": request["payload"]["prompt"],
                "remote_outputs": outputs,
                "output": str(paths[0]),
                "output_path": str(paths[0]),
                "image_paths": [str(path) for path in paths],
                "format": paths[0].suffix.lstrip(".") or "png",
                "references_used": request.get("references_used", []),
                "element_ids": request.get("element_ids", []),
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative estimate pending official account-usage reconciliation.",
                **self._account_usage_result(inputs, client),
                **self._callback_result_data(inputs, task_id),
            },
            artifacts=[str(path) for path in paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=request["model"],
        )

    def _build_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        api_family = str(inputs.get("api_family", "generation"))
        if inputs.get("operation") == "omni":
            api_family = "omni"
        if api_family == "omni":
            return self._build_omni_request(inputs)
        return self._build_generation_request(inputs)

    def _build_generation_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        prompt = self._prompt(inputs)
        model_name = str(inputs.get("model_name") or "kling-v3")
        if model_name not in IMAGE_GENERATION_MODELS:
            raise ValueError(f"model_name {model_name!r} is not supported for api_family=generation")
        payload: dict[str, Any] = {
            "model_name": model_name,
            "prompt": prompt,
            "resolution": inputs.get("resolution", "1k"),
            "n": int(inputs.get("n", 1) or 1),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
        }
        if len(prompt) > 2500:
            raise ValueError("prompt exceeds Kling image generation limit of 2500 characters")
        if inputs.get("negative_prompt"):
            payload["negative_prompt"] = inputs["negative_prompt"]
        image = normalize_image_input(inputs.get("image_url"), inputs.get("image_path"))
        if image:
            payload["image"] = image
        if inputs.get("image_reference"):
            payload["image_reference"] = inputs["image_reference"]
        for key in ("image_fidelity", "human_fidelity"):
            if inputs.get(key) is not None:
                payload[key] = inputs[key]
        elements = normalize_element_list(inputs.get("element_list"))
        if elements:
            payload["element_list"] = elements
        self._copy_common_task_fields(inputs, payload)
        return {
            "protocol": "classic",
            "path": "/v1/images/generations",
            "payload": payload,
            "api_family": "generation",
            "operation": "generate",
            "model": payload["model_name"],
            "references_used": self._reference_metadata_from_generation_payload(payload),
            "element_ids": element_ids(payload.get("element_list")),
        }

    def _build_omni_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        model_name = str(inputs.get("model_name") or "kling-image-o1")
        if model_name not in OMNI_IMAGE_MODELS:
            raise ValueError(f"model_name {model_name!r} is not supported for api_family=omni")
        image_items, references_used = self._normalize_omni_image_list(inputs)
        prompt, prompt_references = build_image_prompt_references(self._prompt(inputs), image_items)
        references_used = prompt_references or references_used
        elements = normalize_element_list(inputs.get("element_list"))
        payload: dict[str, Any] = {
            "model_name": model_name,
            "prompt": prompt,
            "resolution": inputs.get("resolution", "1k"),
            "n": int(inputs.get("n", 1) or 1),
            "result_type": inputs.get("result_type", "single"),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
        }
        if image_items:
            payload["image_list"] = [{"image": item["image"]} for item in image_items]
        if elements:
            payload["element_list"] = elements
        if inputs.get("series_amount"):
            payload["series_amount"] = inputs["series_amount"]
        self._copy_common_task_fields(inputs, payload)
        return {
            "protocol": "classic",
            "path": "/v1/images/omni-image",
            "payload": payload,
            "api_family": "omni",
            "operation": "generate",
            "model": model_name,
            "references_used": references_used,
            "element_ids": [item["element_id"] for item in elements],
        }

    def _normalize_omni_image_list(
        self,
        inputs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        image_list: list[dict[str, Any]] = []
        references_used: list[dict[str, Any]] = []

        def add_image(value: str | None, *, source: str | None, source_type: str) -> None:
            if not value:
                return
            image_list.append({"image": value, "source": source or value, "source_type": source_type})
            references_used.append(
                {
                    "kind": "image",
                    "source": source or value,
                    "source_type": source_type,
                    "placeholder": f"<<<image_{len(image_list)}>>>",
                }
            )

        for item in inputs.get("image_list") or []:
            if not isinstance(item, dict):
                raise ValueError("image_list items must be objects")
            source = item.get("image") or item.get("image_url") or item.get("image_path")
            value = normalize_image_input(item.get("image") or item.get("image_url"), item.get("image_path"))
            if not value:
                raise ValueError("image_list items must include image, image_url, or image_path")
            add_image(value, source=source, source_type="image_list")
        for url in inputs.get("image_urls") or []:
            add_image(normalize_image_input(url=url), source=url, source_type="image_urls")
        for path in inputs.get("image_paths") or []:
            add_image(normalize_image_input(path=path), source=str(path), source_type="image_paths")
        if inputs.get("image_url") or inputs.get("image_path"):
            add_image(
                normalize_image_input(inputs.get("image_url"), inputs.get("image_path")),
                source=inputs.get("image_url") or inputs.get("image_path"),
                source_type="image",
            )

        return image_list, references_used

    def _download_images(self, client: KlingClient, outputs: list[dict[str, Any]], inputs: dict[str, Any]) -> list[Path]:
        if not outputs:
            raise ValueError("Kling image response contained no images")
        base_path = Path(inputs.get("output_path", "kling_official_image.png"))
        paths: list[Path] = []
        for index, item in enumerate(outputs):
            url = self._output_url(item)
            suffix = extension_from_url(url, ".png")
            output_path = numbered_output_path(output_path_with_suffix(base_path, suffix), index, suffix)
            client.download(url, output_path)
            paths.append(output_path)
        return paths

    @staticmethod
    def _output_url(item: dict[str, Any]) -> str:
        url = item.get("url") or item.get("image_url") or item.get("resource_url")
        if url:
            return str(url)
        resource = item.get("resource") or {}
        if isinstance(resource, dict) and resource.get("url"):
            return str(resource["url"])
        raise ValueError(f"Kling image response item contained no downloadable URL: {item}")

    @staticmethod
    def _prompt(inputs: dict[str, Any]) -> str:
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        return prompt

    @staticmethod
    def _copy_common_task_fields(inputs: dict[str, Any], payload: dict[str, Any]) -> None:
        if "watermark" in inputs:
            payload["watermark_info"] = {"enabled": bool(inputs.get("watermark"))}
        callback_url = validate_callback_url(inputs.get("callback_url"))
        if callback_url:
            payload["callback_url"] = callback_url
        if inputs.get("external_task_id"):
            payload["external_task_id"] = inputs["external_task_id"]

    @staticmethod
    def _reference_metadata_from_generation_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        if payload.get("image"):
            references.append({"kind": "image", "source_type": "image"})
        if payload.get("element_list"):
            references.extend(
                {"kind": "element", "element_id": item["element_id"]}
                for item in normalize_element_list(payload.get("element_list"))
            )
        return references

    @staticmethod
    def _callback_result_data(inputs: dict[str, Any], task_id: str) -> dict[str, Any]:
        callback_url = inputs.get("callback_url")
        if not callback_url:
            return {}
        return {
            "callback_url": str(callback_url),
            "callback_requested": True,
            "polling_used": True,
            "task_id": task_id,
        }

    @staticmethod
    def _account_usage_result(inputs: dict[str, Any], client: KlingClient) -> dict[str, Any]:
        if not inputs.get("include_account_usage"):
            return {}
        try:
            usage = get_account_costs(client=client)
            return {
                "account_usage": usage,
                "cost_source": "estimate_with_account_usage_context",
                "reconciled_cost_usd": None,
            }
        except Exception as exc:
            return {
                "account_usage_error": str(exc),
                "cost_source": "estimate",
                "reconciled_cost_usd": None,
            }
