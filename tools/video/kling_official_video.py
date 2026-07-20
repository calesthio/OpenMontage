"""Kling official API video generation provider."""

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
from tools._kling.schemas import (
    CLASSIC_VIDEO_MODELS,
    OMNI_VIDEO_MODELS,
    SOUND_VALUES,
    VIDEO_ASPECT_RATIOS,
    VIDEO_DURATIONS,
    VIDEO_MODES,
    VIDEO_MODELS,
    VIDEO_RESOLUTIONS,
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
from tools.video._shared import probe_output


class KlingOfficialVideo(BaseTool):
    name = "kling_official_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
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
    agent_skills = ["ai-video-gen", "kling-official"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "reference_image": True,
        "negative_prompt": True,
        "aspect_ratio": True,
    }
    best_for = [
        "official Kling direct API access",
        "text-to-video and image-to-video with Kling model controls",
        "projects that need provider provenance separate from fal.ai Kling",
    ]
    not_good_for = ["offline generation", "free generation", "non-Kling model families"]
    fallback_tools = ["kling_video", "seedance_video", "veo_video", "minimax_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "reference_to_video", "omni_video"],
                "default": "text_to_video",
            },
            "api_family": {
                "type": "string",
                "enum": ["classic", "turbo", "omni"],
                "default": "classic",
            },
            "model_name": {"type": "string", "enum": VIDEO_MODELS, "default": "kling-v3"},
            "model_variant": {"type": "string", "description": "Compatibility alias for model_name."},
            "duration": {"type": "string", "enum": VIDEO_DURATIONS, "default": "5"},
            "aspect_ratio": {"type": "string", "enum": VIDEO_ASPECT_RATIOS, "default": "16:9"},
            "resolution": {"type": "string", "enum": VIDEO_RESOLUTIONS, "default": "720p"},
            "mode": {"type": "string", "enum": VIDEO_MODES, "default": "std"},
            "sound": {"type": "string", "enum": SOUND_VALUES, "default": "off"},
            "negative_prompt": {"type": "string"},
            "cfg_scale": {"type": "number", "default": 0.5},
            "reference_image_url": {"type": "string"},
            "reference_image_path": {"type": "string"},
            "reference_tail_image_url": {"type": "string"},
            "reference_tail_image_path": {"type": "string"},
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "reference_video_url": {"type": "string"},
            "reference_video_path": {"type": "string"},
            "video_urls": {"type": "array", "items": {"type": "string"}},
            "video_paths": {"type": "array", "items": {"type": "string"}},
            "image_list": {"type": "array"},
            "video_list": {"type": "array"},
            "element_list": {"type": "array"},
            "multi_shot": {"type": "boolean"},
            "shot_type": {"type": "string", "enum": ["customize", "intelligence"]},
            "multi_prompt": {"type": "array"},
            "camera_control": {"type": "object"},
            "watermark": {"type": "boolean", "default": False},
            "callback_url": {"type": "string"},
            "external_task_id": {"type": "string"},
            "include_account_usage": {
                "type": "boolean",
                "default": False,
                "description": "Optional low-frequency account usage diagnostic; not used by default.",
            },
            "timeout_seconds": {"type": "integer", "default": 900},
            "poll_interval": {"type": "number", "default": 5.0},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
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
        "model_variant",
        "duration",
        "aspect_ratio",
        "resolution",
        "mode",
        "sound",
        "cfg_scale",
        "camera_control",
        "reference_image_url",
        "reference_image_path",
        "reference_tail_image_url",
        "reference_tail_image_path",
        "reference_image_urls",
        "reference_image_paths",
        "reference_video_url",
        "video_urls",
        "image_list",
        "video_list",
        "element_list",
        "multi_shot",
        "shot_type",
        "multi_prompt",
        "watermark",
    ]
    side_effects = [
        "paid remote generation via official Kling API",
        "writes video file to output_path",
    ]
    user_visible_verification = ["Watch generated clip for motion coherence and prompt adherence"]

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        duration = int(str(inputs.get("duration", "5")))
        mode = str(inputs.get("mode", "std"))
        api_family = str(inputs.get("api_family", "classic"))
        base = 0.18
        if api_family == "turbo":
            base = 0.22
        if api_family == "omni":
            base = 0.30
        if mode == "pro":
            base *= 1.6
        if mode == "4k":
            base *= 3.0
        if inputs.get("sound") == "on":
            base += 0.05
        if api_family == "omni":
            reference_count = self._estimate_reference_count(inputs)
            base *= 1 + (0.12 * reference_count)
            multi_prompt = inputs.get("multi_prompt") or []
            if multi_prompt:
                base *= 1 + (0.10 * len(multi_prompt))
        return round(base * max(duration, 3) / 5, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0

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
            if request["protocol"] == "turbo":
                task_id = client.create_turbo(request["path"], request["payload"])
                outputs = client.poll_turbo(
                    task_id,
                    timeout_seconds=int(inputs.get("timeout_seconds", 900)),
                    poll_interval=float(inputs.get("poll_interval", 5.0)),
                )
            else:
                task_id = client.create_classic_task(request["path"], request["payload"])
                outputs = client.poll_classic(
                    request["path"],
                    task_id,
                    "videos",
                    timeout_seconds=int(inputs.get("timeout_seconds", 900)),
                    poll_interval=float(inputs.get("poll_interval", 5.0)),
                )
            paths = self._download_videos(client, outputs, inputs)
            video_url = self._first_output_url(outputs)
            probed = probe_output(paths[0])
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
            return ToolResult(success=False, data=data, error=f"Kling official video generation failed: {exc}")
        except Exception as exc:
            return ToolResult(success=False, data={"provider": self.provider}, error=f"Kling official video generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": request["model"],
                "task_id": task_id,
                "operation": request["operation"],
                "api_family": request["api_family"],
                "prompt": inputs["prompt"],
                "remote_url": video_url,
                "remote_outputs": outputs,
                "output": str(paths[0]),
                "output_path": str(paths[0]),
                "video_paths": [str(path) for path in paths],
                "format": "mp4",
                "references_used": request.get("references_used", []),
                "element_ids": request.get("element_ids", []),
                "cost_estimate_confidence": "low",
                "cost_estimate_basis": "Conservative estimate pending official account-usage reconciliation.",
                **self._account_usage_result(inputs, client),
                **self._callback_result_data(inputs, task_id),
                **probed,
            },
            artifacts=[str(path) for path in paths],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=request["model"],
        )

    def _build_request(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = str(inputs.get("operation", "text_to_video"))
        api_family = str(inputs.get("api_family", "classic"))
        if operation == "omni_video":
            operation = "reference_to_video"
            api_family = "omni"
        if api_family == "turbo":
            return self._build_turbo_request(inputs, operation)
        if api_family == "omni":
            return self._build_omni_request(inputs, operation)
        return self._build_classic_request(inputs, operation)

    def _build_classic_request(self, inputs: dict[str, Any], operation: str) -> dict[str, Any]:
        if operation == "text_to_video":
            payload = self._base_classic_payload(inputs)
            payload["prompt"] = self._prompt(inputs)
            if inputs.get("negative_prompt"):
                payload["negative_prompt"] = inputs["negative_prompt"]
            if inputs.get("aspect_ratio"):
                payload["aspect_ratio"] = inputs.get("aspect_ratio", "16:9")
            self._copy_multi_shot_fields(inputs, payload)
            path = "/v1/videos/text2video"
        elif operation == "image_to_video":
            image = normalize_image_input(inputs.get("reference_image_url"), inputs.get("reference_image_path"))
            if not image:
                raise ValueError("image_to_video requires reference_image_url or reference_image_path")
            payload = self._base_classic_payload(inputs)
            payload["image"] = image
            if inputs.get("prompt"):
                payload["prompt"] = inputs["prompt"]
            if inputs.get("negative_prompt"):
                payload["negative_prompt"] = inputs["negative_prompt"]
            tail = normalize_image_input(inputs.get("reference_tail_image_url"), inputs.get("reference_tail_image_path"))
            if tail:
                payload["image_tail"] = tail
            if inputs.get("element_list"):
                payload["element_list"] = normalize_element_list(inputs.get("element_list"))
            self._copy_multi_shot_fields(inputs, payload)
            path = "/v1/videos/image2video"
        else:
            raise ValueError(f"Unsupported classic video operation: {operation}")
        return {
            "protocol": "classic",
            "path": path,
            "payload": payload,
            "operation": operation,
            "api_family": "classic",
            "model": payload["model_name"],
            "references_used": self._reference_metadata_from_classic_payload(payload),
            "element_ids": element_ids(payload.get("element_list")),
        }

    def _build_turbo_request(self, inputs: dict[str, Any], operation: str) -> dict[str, Any]:
        settings = {
            "resolution": inputs.get("resolution", "720p"),
            "duration": int(str(inputs.get("duration", "5"))),
        }
        options = self._options_payload(inputs)
        if operation == "text_to_video":
            settings["aspect_ratio"] = inputs.get("aspect_ratio", "16:9")
            payload = {"prompt": self._prompt(inputs), "settings": settings}
            if options:
                payload["options"] = options
            path = "/text-to-video/kling-3.0-turbo"
        elif operation == "image_to_video":
            if inputs.get("reference_image_path") and not inputs.get("reference_image_url"):
                raise ValueError("Turbo image_to_video requires reference_image_url; local paths cannot be silently uploaded.")
            image_url = inputs.get("reference_image_url")
            if not image_url:
                raise ValueError("image_to_video requires reference_image_url for api_family=turbo")
            contents = [{"type": "prompt", "text": self._prompt(inputs)}, {"type": "first_frame", "url": image_url}]
            payload = {"contents": contents, "settings": settings}
            if options:
                payload["options"] = options
            path = "/image-to-video/kling-3.0-turbo"
        else:
            raise ValueError(f"Unsupported turbo video operation: {operation}")
        return {
            "protocol": "turbo",
            "path": path,
            "payload": payload,
            "operation": operation,
            "api_family": "turbo",
            "model": "kling-3.0-turbo",
        }

    def _build_omni_request(self, inputs: dict[str, Any], operation: str) -> dict[str, Any]:
        explicit_model = inputs.get("model_name") or inputs.get("model_variant")
        model_name = str(explicit_model or "kling-video-o1")
        if model_name not in OMNI_VIDEO_MODELS:
            raise ValueError(f"model_name {model_name!r} is not supported for api_family=omni")
        payload, references_used, element_id_values = self._build_omni_payload(inputs, operation, model_name)
        return {
            "protocol": "classic",
            "path": "/v1/videos/omni-video",
            "payload": payload,
            "operation": operation,
            "api_family": "omni",
            "model": model_name,
            "references_used": references_used,
            "element_ids": element_id_values,
        }

    def _build_omni_payload(
        self,
        inputs: dict[str, Any],
        operation: str,
        model_name: str,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[int]]:
        payload: dict[str, Any] = {
            "model_name": model_name,
            "prompt": self._prompt(inputs),
            "mode": inputs.get("mode", "pro"),
            "duration": str(inputs.get("duration", "5")),
        }
        if inputs.get("sound"):
            payload["sound"] = inputs["sound"]
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        self._copy_common_task_fields(inputs, payload)
        self._copy_multi_shot_fields(inputs, payload)

        references_used: list[dict[str, Any]] = []
        image_list, image_refs = self._normalize_omni_image_list(inputs)
        references_used.extend(image_refs)
        if image_list:
            payload["image_list"] = image_list

        video_list, video_refs = self._normalize_omni_video_list(inputs)
        references_used.extend(video_refs)
        if video_list:
            payload["video_list"] = video_list

        elements = normalize_element_list(inputs.get("element_list"))
        element_id_values = [item["element_id"] for item in elements]
        if elements:
            payload["element_list"] = elements
            references_used.extend(
                {"kind": "element", "element_id": item["element_id"]}
                for item in elements
            )
        if operation == "reference_to_video" and not any(payload.get(k) for k in ("image_list", "video_list", "element_list")):
            raise ValueError("reference_to_video with api_family=omni requires image_list, video_list, element_list, or reference image URLs.")
        return payload, references_used, element_id_values

    def _base_classic_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        model_name = str(inputs.get("model_name") or inputs.get("model_variant") or "kling-v3")
        if model_name not in CLASSIC_VIDEO_MODELS:
            raise ValueError(f"model_name {model_name!r} is not supported for api_family=classic")
        payload: dict[str, Any] = {
            "model_name": model_name,
            "duration": str(inputs.get("duration", "5")),
            "mode": inputs.get("mode", "std"),
            "sound": inputs.get("sound", "off"),
        }
        if inputs.get("cfg_scale") is not None:
            payload["cfg_scale"] = inputs["cfg_scale"]
        if inputs.get("camera_control"):
            payload["camera_control"] = inputs["camera_control"]
        self._copy_common_task_fields(inputs, payload)
        return payload

    def _options_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        options: dict[str, Any] = {}
        callback_url = validate_callback_url(inputs.get("callback_url"))
        if callback_url:
            options["callback_url"] = callback_url
        if inputs.get("external_task_id"):
            options["external_task_id"] = inputs["external_task_id"]
        if "watermark" in inputs:
            options["watermark_info"] = {"enabled": bool(inputs.get("watermark"))}
        return options

    def _copy_common_task_fields(self, inputs: dict[str, Any], payload: dict[str, Any]) -> None:
        if "watermark" in inputs:
            payload["watermark_info"] = {"enabled": bool(inputs.get("watermark"))}
        callback_url = validate_callback_url(inputs.get("callback_url"))
        if callback_url:
            payload["callback_url"] = callback_url
        if inputs.get("external_task_id"):
            payload["external_task_id"] = inputs["external_task_id"]

    def _copy_multi_shot_fields(self, inputs: dict[str, Any], payload: dict[str, Any]) -> None:
        if inputs.get("multi_shot") is None and not inputs.get("multi_prompt"):
            return
        payload["multi_shot"] = bool(inputs.get("multi_shot", True))
        shot_type = str(inputs.get("shot_type") or "customize")
        if shot_type not in {"customize", "intelligence"}:
            raise ValueError("shot_type must be one of: customize, intelligence")
        payload["shot_type"] = shot_type
        if inputs.get("multi_prompt"):
            if not isinstance(inputs["multi_prompt"], list):
                raise ValueError("multi_prompt must be a list")
            normalized: list[dict[str, Any]] = []
            for item in inputs["multi_prompt"]:
                if not isinstance(item, dict) or not item.get("prompt"):
                    raise ValueError("each multi_prompt item must be an object with prompt")
                allowed = {
                    key: item[key]
                    for key in ("prompt", "duration", "camera_control", "image_refs", "element_refs")
                    if key in item
                }
                normalized.append(allowed)
            payload["multi_prompt"] = normalized

    def _normalize_omni_image_list(
        self,
        inputs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        image_list: list[dict[str, Any]] = []
        references_used: list[dict[str, Any]] = []

        def add_image(value: str | None, *, kind: str, item_type: str | None = None) -> None:
            if not value:
                return
            record = {"image_url": value}
            if item_type:
                record["type"] = item_type
            image_list.append(record)
            references_used.append(
                {
                    "kind": "image",
                    "source": value,
                    "source_type": kind,
                    "type": item_type,
                }
            )

        for item in inputs.get("image_list") or []:
            if not isinstance(item, dict):
                raise ValueError("image_list items must be objects")
            value = normalize_image_input(item.get("image_url") or item.get("image"), item.get("image_path"))
            if not value:
                raise ValueError("image_list items must include image_url, image, or image_path")
            record = {"image_url": value}
            if item.get("type"):
                record["type"] = item["type"]
            image_list.append(record)
            references_used.append(
                {
                    "kind": "image",
                    "source": item.get("image_url") or item.get("image_path") or item.get("image"),
                    "source_type": "image_list",
                    "type": item.get("type"),
                }
            )

        add_image(
            normalize_image_input(inputs.get("reference_image_url"), inputs.get("reference_image_path")),
            kind="reference_image",
            item_type="first_frame",
        )
        add_image(
            normalize_image_input(inputs.get("reference_tail_image_url"), inputs.get("reference_tail_image_path")),
            kind="reference_tail_image",
            item_type="end_frame",
        )
        for url in inputs.get("reference_image_urls") or []:
            add_image(normalize_image_input(url=url), kind="reference_image_urls")
        for path in inputs.get("reference_image_paths") or []:
            add_image(normalize_image_input(path=path), kind="reference_image_paths")
        return image_list, references_used

    def _normalize_omni_video_list(
        self,
        inputs: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if inputs.get("reference_video_path") or inputs.get("video_paths"):
            raise ValueError("Video Omni requires video URLs; local video paths cannot be silently uploaded.")

        video_list: list[dict[str, Any]] = []
        references_used: list[dict[str, Any]] = []

        def add_video(item: dict[str, Any], source_type: str) -> None:
            if item.get("video_path"):
                raise ValueError("Video Omni requires video URLs; local video paths cannot be silently uploaded.")
            video_url = item.get("video_url") or item.get("url")
            if not video_url:
                raise ValueError("video_list items must include video_url")
            record = {"video_url": video_url}
            if item.get("refer_type"):
                record["refer_type"] = item["refer_type"]
            if "keep_original_sound" in item:
                value = item["keep_original_sound"]
                record["keep_original_sound"] = "yes" if value is True else "no" if value is False else value
            video_list.append(record)
            references_used.append(
                {
                    "kind": "video",
                    "source": video_url,
                    "source_type": source_type,
                    "refer_type": record.get("refer_type"),
                    "keep_original_sound": record.get("keep_original_sound"),
                }
            )

        for item in inputs.get("video_list") or []:
            if not isinstance(item, dict):
                raise ValueError("video_list items must be objects")
            add_video(item, "video_list")
        if inputs.get("reference_video_url"):
            add_video({"video_url": inputs["reference_video_url"]}, "reference_video_url")
        for url in inputs.get("video_urls") or []:
            add_video({"video_url": url}, "video_urls")
        return video_list, references_used

    def _download_videos(
        self,
        client: KlingClient,
        outputs: list[dict[str, Any]],
        inputs: dict[str, Any],
    ) -> list[Path]:
        if not outputs:
            raise ValueError("Kling video response contained no videos")
        base_path = Path(inputs.get("output_path", "kling_official_video.mp4"))
        paths: list[Path] = []
        for index, item in enumerate(outputs):
            url = self._output_url(item)
            suffix = extension_from_url(url, ".mp4")
            output_path = numbered_output_path(output_path_with_suffix(base_path, suffix), index, suffix)
            client.download(url, output_path)
            paths.append(output_path)
        return paths

    @staticmethod
    def _output_url(item: dict[str, Any]) -> str:
        url = item.get("url") or item.get("video_url") or item.get("resource_url")
        if url:
            return str(url)
        resource = item.get("resource") or {}
        if isinstance(resource, dict) and resource.get("url"):
            return str(resource["url"])
        raise ValueError(f"Kling video response contained no downloadable URL: {item}")

    @staticmethod
    def _reference_metadata_from_classic_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        if payload.get("image"):
            references.append({"kind": "image", "source_type": "reference_image"})
        if payload.get("image_tail"):
            references.append({"kind": "image", "source_type": "reference_tail_image"})
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

    @staticmethod
    def _estimate_reference_count(inputs: dict[str, Any]) -> int:
        count = 0
        for key in (
            "image_list",
            "video_list",
            "element_list",
            "reference_image_urls",
            "reference_image_paths",
            "video_urls",
        ):
            count += len(inputs.get(key) or [])
        for key in (
            "reference_image_url",
            "reference_image_path",
            "reference_tail_image_url",
            "reference_tail_image_path",
            "reference_video_url",
        ):
            if inputs.get(key):
                count += 1
        return count

    @staticmethod
    def _prompt(inputs: dict[str, Any]) -> str:
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")
        return prompt

    @staticmethod
    def _first_output_url(outputs: list[dict[str, Any]]) -> str:
        for item in outputs:
            try:
                return KlingOfficialVideo._output_url(item)
            except ValueError:
                continue
        raise ValueError(f"Kling video response contained no downloadable URL: {outputs}")
