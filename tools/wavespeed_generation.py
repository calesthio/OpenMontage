"""Shared execution helpers for WaveSpeed BaseTool providers."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import json
import mimetypes
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

from lib.wavespeed_config import WaveSpeedConfigError, resolve_wavespeed_task
from tools.base_tool import ToolResult
from tools.wavespeed_client import (
    WaveSpeedAuthError,
    WaveSpeedClient,
    WaveSpeedError,
)


RESERVED_INPUT_KEYS = {
    "prompt",
    "output_dir",
    "output_path",
    "model_id",
    "params",
    "task_type",
    "operation",
    "allow_stock_sources",
    "stock_sources_explicit",
    "preferred_provider",
    "allowed_providers",
    "task_context",
}
PARAM_PASSTHROUGH_KEYS = {
    "negative_prompt",
    "width",
    "height",
    "seed",
    "n",
    "num_images",
    "num_inference_steps",
    "guidance_scale",
    "aspect_ratio",
    "resolution",
    "duration",
    "fps",
    "ratio",
}
IMAGE_INPUT_KEYS = {
    "image",
    "image_url",
    "image_path",
    "reference_image_url",
    "reference_image_path",
}


def parse_params(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("params JSON must decode to an object.")
        return parsed
    raise ValueError("params must be a dict or JSON object string.")


def build_explicit_params(inputs: dict[str, Any]) -> dict[str, Any]:
    params = parse_params(inputs.get("params"))
    for key in PARAM_PASSTHROUGH_KEYS:
        if inputs.get(key) is not None:
            params[key] = inputs[key]
    return params


# Task types that consume a source image (resolved into payload["image"]).
IMAGE_INPUT_TASKS = {
    "image_to_video",
    "image_edit",
    "image_upscale",
    "background_removal",
}
# Task types that operate on a source asset and do not require a text prompt.
PROMPT_OPTIONAL_TASKS = {"image_upscale", "background_removal"}


def run_wavespeed_generation(
    *,
    task_type: str,
    asset_type: str,
    inputs: dict[str, Any],
    client: WaveSpeedClient | None = None,
) -> ToolResult:
    """Run one WaveSpeed task and return the standard OpenMontage contract."""

    started = datetime.now(timezone.utc)
    prompt = str(inputs.get("prompt") or "").strip()
    output_dir = _resolve_output_dir(inputs, asset_type)
    output_dir.mkdir(parents=True, exist_ok=True)

    metadata: dict[str, Any] = _base_contract(
        asset_type=asset_type,
        task_type=task_type,
        prompt=prompt,
        created_at=started,
    )
    metadata_path = (
        output_dir
        / f"{_safe_stem(task_type)}_{started.strftime('%Y%m%dT%H%M%S%fZ')}_metadata.json"
    )
    metadata["metadata_path"] = str(metadata_path)

    try:
        if not prompt and task_type not in PROMPT_OPTIONAL_TASKS:
            raise ValueError("prompt is required.")
        explicit_params = build_explicit_params(inputs)
        resolved = resolve_wavespeed_task(
            task_type,
            explicit_model_id=inputs.get("model_id"),
            explicit_params=explicit_params,
            explicit_profile=inputs.get("_wavespeed_profile"),
        )
        metadata.update(
            {
                "model_id": resolved.model_id,
                "profile": resolved.profile,
                "params": resolved.params,
            }
        )

        payload = dict(resolved.params)
        if prompt:
            payload["prompt"] = prompt

        input_reference = (
            _resolve_input_reference(inputs) if task_type in IMAGE_INPUT_TASKS else None
        )
        if input_reference:
            payload.setdefault("image", input_reference["payload_value"])
            metadata["input_reference"] = input_reference["metadata"]
        elif task_type in IMAGE_INPUT_TASKS:
            raise ValueError(
                f"{task_type} requires image_url, image_path, reference_image_url, or reference_image_path."
            )

        active_client = client or WaveSpeedClient()
        prediction = active_client.run_prediction(
            model_id=resolved.model_id,
            task_type=task_type,
            payload=payload,
        )

        metadata.update(
            {
                "task_id": prediction.task_id,
                "status": prediction.status,
                "outputs": prediction.outputs,
                "wavespeed_submit_response": prediction.submit_response,
                "wavespeed_result_response": prediction.result_response,
            }
        )

        local_paths = _download_outputs(
            client=active_client,
            outputs=prediction.outputs,
            output_dir=output_dir,
            asset_type=asset_type,
            task_type=task_type,
            task_id=prediction.task_id,
            output_path=inputs.get("output_path"),
        )
        metadata["local_paths"] = [str(path) for path in local_paths]

        media_info = _probe_media(local_paths[0], asset_type) if local_paths else {}
        metadata.update(media_info)
        _write_metadata(metadata_path, metadata)

        duration_seconds = round(
            (datetime.now(timezone.utc) - started).total_seconds(), 2
        )
        return ToolResult(
            success=True,
            data=metadata,
            artifacts=[*metadata["local_paths"], str(metadata_path)],
            duration_seconds=duration_seconds,
            model=resolved.model_id,
        )

    except WaveSpeedAuthError as exc:
        metadata["status"] = "failed"
        metadata["error"] = str(exc)
        _write_metadata(metadata_path, metadata)
        return ToolResult(
            success=False, data=metadata, artifacts=[str(metadata_path)], error=str(exc)
        )
    except WaveSpeedError as exc:
        metadata.update(exc.metadata)
        metadata.setdefault("status", exc.metadata.get("status", "failed"))
        metadata["error"] = str(exc)
        _write_metadata(metadata_path, metadata)
        return ToolResult(
            success=False, data=metadata, artifacts=[str(metadata_path)], error=str(exc)
        )
    except (WaveSpeedConfigError, ValueError, json.JSONDecodeError) as exc:
        metadata["status"] = "failed"
        metadata["error"] = str(exc)
        _write_metadata(metadata_path, metadata)
        return ToolResult(
            success=False, data=metadata, artifacts=[str(metadata_path)], error=str(exc)
        )
    except Exception as exc:
        metadata["status"] = "failed"
        metadata["error"] = f"WaveSpeed generation failed: {exc}"
        _write_metadata(metadata_path, metadata)
        return ToolResult(
            success=False,
            data=metadata,
            artifacts=[str(metadata_path)],
            error=metadata["error"],
        )


def _base_contract(
    *, asset_type: str, task_type: str, prompt: str, created_at: datetime
) -> dict[str, Any]:
    return {
        "asset_type": asset_type,
        "provider": "wavespeed",
        "task_type": task_type,
        "model_id": "",
        "profile": "",
        "task_id": "",
        "status": "failed",
        "prompt": prompt,
        "params": {},
        "outputs": [],
        "local_paths": [],
        "metadata_path": "",
        "created_at": created_at.isoformat(),
        "duration_sec": None,
        "width": None,
        "height": None,
    }


def _resolve_output_dir(inputs: dict[str, Any], asset_type: str) -> Path:
    if inputs.get("output_dir"):
        return Path(str(inputs["output_dir"]))
    if inputs.get("output_path"):
        return Path(str(inputs["output_path"])).parent
    return (
        Path("output") / "wavespeed" / ("images" if asset_type == "image" else "video")
    )


def _download_outputs(
    *,
    client: WaveSpeedClient,
    outputs: list[str],
    output_dir: Path,
    asset_type: str,
    task_type: str,
    task_id: str,
    output_path: str | None,
) -> list[Path]:
    local_paths: list[Path] = []
    for index, url in enumerate(outputs):
        if index == 0 and output_path:
            path = Path(output_path)
        else:
            path = (
                output_dir
                / f"{_safe_stem(task_type)}_{_safe_stem(task_id)[:12]}_{index + 1}{_extension_for_url(url, asset_type)}"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(client.download_url(url))
        local_paths.append(path)
    return local_paths


def _extension_for_url(url: str, asset_type: str) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix and len(suffix) <= 8:
        return suffix
    return ".png" if asset_type == "image" else ".mp4"


def _probe_media(path: Path, asset_type: str) -> dict[str, Any]:
    if asset_type == "image":
        try:
            from PIL import Image

            with Image.open(path) as image:
                width, height = image.size
            return {"width": width, "height": height}
        except Exception:
            return {}
    try:
        from tools.video._shared import probe_output

        probed = probe_output(path)
        return {
            "duration_sec": probed.get("duration_seconds")
            or probed.get("duration_sec"),
            "width": probed.get("width"),
            "height": probed.get("height"),
        }
    except Exception:
        return {}


def _resolve_input_reference(inputs: dict[str, Any]) -> dict[str, Any] | None:
    image_url = inputs.get("image_url") or inputs.get("reference_image_url")
    if image_url:
        return {
            "payload_value": str(image_url),
            "metadata": {"kind": "url", "value": str(image_url)},
        }

    image_path = inputs.get("image_path") or inputs.get("reference_image_path")
    if not image_path:
        return None
    path = Path(str(image_path))
    if not path.exists():
        raise ValueError(f"Input image path does not exist: {path}")

    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    data_uri = (
        f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"
    )
    return {
        "payload_value": data_uri,
        "metadata": {"kind": "path", "value": str(path)},
    }


def _write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")


def _safe_stem(value: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-")
    return stem or "wavespeed"


def cli_main(*, tool_name: str, task_type: str, asset_type: str) -> int:
    parser = argparse.ArgumentParser(prog=tool_name)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model-id")
    parser.add_argument("--params", default="{}")
    parser.add_argument("--output-path")
    parser.add_argument("--image-url")
    parser.add_argument("--image-path")
    parser.add_argument("--reference-image-url")
    parser.add_argument("--reference-image-path")
    args = parser.parse_args()

    inputs = {k: v for k, v in vars(args).items() if v is not None}
    result = run_wavespeed_generation(
        task_type=task_type, asset_type=asset_type, inputs=inputs
    )
    print(json.dumps(result.data, indent=2, sort_keys=True))
    return 0 if result.success else 1
