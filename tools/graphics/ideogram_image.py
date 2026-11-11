"""Ideogram 4.5 direct generation, editing and pixel-preserving Precise Edit."""

import os
from contextlib import ExitStack
from pathlib import Path

from tools.provider_pricing import PriceQuoteRequired

from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ResourceProfile,
    ToolResult,
)
from tools.provider_jobs import request_json, download


class IdeogramImage(BaseTool):
    name = "ideogram_image"
    provider = "ideogram"
    capability = "image_generation"
    tier = ToolTier.GENERATE
    runtime = ToolRuntime.API
    stability = ToolStability.BETA
    dependencies = ["env:IDEOGRAM_API_KEY"]
    install_instructions = "Configure IDEOGRAM_API_KEY."
    agent_skills = ["provider-model-refresh"]
    capabilities = ["text_to_image", "image_edit", "precise_edit", "price_quote"]
    supports = {
        "image_edit": True,
        "mask": True,
        "multiple_reference_images": True,
        "precise_edit": True,
    }
    best_for = ["Precise local edits preserving unchanged pixels and typography"]
    resource_profile = ResourceProfile(network_required=True)
    idempotency_key_fields = [
        "prompt",
        "generation_mode",
        "image_paths",
        "image_path",
        "mask_path",
        "quality",
        "size",
        "seed",
    ]
    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "minLength": 1},
            "model": {
                "type": "string",
                "enum": ["ideogram-4.5"],
                "default": "ideogram-4.5",
            },
            "generation_mode": {
                "type": "string",
                "enum": ["generate", "edit", "precise_edit"],
            },
            "image_path": {"type": "string"},
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 5,
            },
            "mask_path": {"type": "string"},
            "quality": {
                "type": "string",
                "enum": ["very_low", "low", "medium", "high"],
            },
            "size": {"type": "string"},
            "seed": {"type": "integer"},
            "num_images": {"type": "integer", "minimum": 1, "maximum": 8},
            "magic_prompt": {"type": "string", "enum": ["auto", "on", "off"]},
            "dry_run": {"type": "boolean", "default": False},
            "output_path": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs):
        raise PriceQuoteRequired(
            "Use dry_run=true with the exact request to obtain an unbilled Ideogram price quote"
        )

    def execute(self, inputs):
        try:
            from jsonschema import validate

            validate(inputs, self.input_schema)
            paths = list(inputs.get("image_paths") or [])
            if inputs.get("image_path"):
                paths.insert(0, inputs["image_path"])
            mode = inputs.get("generation_mode", "edit" if paths else "generate")
            if mode in {"edit", "precise_edit"} and not paths:
                raise ValueError("Editing requires a source image")
            if mode == "generate" and paths:
                raise ValueError("Use edit with source images")
            if len(paths) > (4 if inputs.get("mask_path") else 5):
                raise ValueError("Too many source/reference images")
            if inputs.get("mask_path") and (not paths or inputs.get("size")):
                raise ValueError("Mask requires a source image and cannot use size")
            if mode == "precise_edit" and (
                inputs.get("size") or inputs.get("magic_prompt")
            ):
                raise ValueError(
                    "Precise Edit preserves source size and does not accept magic_prompt"
                )
            if not paths and (
                inputs.get("quality") == "very_low" or inputs.get("size") == "source"
            ):
                raise ValueError("very_low/source requires a source image")
            data = {
                k: inputs[k]
                for k in (
                    "prompt",
                    "quality",
                    "size",
                    "seed",
                    "num_images",
                    "magic_prompt",
                )
                if k in inputs
            }
            endpoint = "precise-edit" if mode == "precise_edit" else "generate"
            with ExitStack() as stack:
                files = []
                for i, path in enumerate(paths):
                    if Path(path).stat().st_size > 25 * 1024 * 1024:
                        raise ValueError("Images must not exceed 25 MB")
                    field = (
                        ("image" if i == 0 else "reference_images")
                        if mode == "precise_edit"
                        else "images"
                    )
                    files.append(
                        (
                            field,
                            (Path(path).name, stack.enter_context(open(path, "rb"))),
                        )
                    )
                if inputs.get("mask_path"):
                    files.append(
                        (
                            "mask",
                            (
                                "mask.png",
                                stack.enter_context(open(inputs["mask_path"], "rb")),
                            ),
                        )
                    )
                # JSON is supported for text-only generation; edits require multipart.
                body = {"data": data, "files": files} if files else {"json": data}
                result = request_json(
                    "POST",
                    "https://api.ideogram.ai/v2/image/" + endpoint + "/ideogram-4-5",
                    headers={"Api-Key": os.environ["IDEOGRAM_API_KEY"]},
                    params={"dry_run": str(bool(inputs.get("dry_run"))).lower()},
                    **body,
                )
            if inputs.get("dry_run"):
                return ToolResult(
                    success=True,
                    data={
                        "provider": self.provider,
                        "price_quote": result,
                        "dry_run": True,
                    },
                )
            images = result.get("data") or []
            if not images:
                raise ValueError("Ideogram returned no images")
            if any(item.get("is_image_safe") is False for item in images):
                raise ValueError(
                    "Provider flagged an output; no unsafe output was downloaded"
                )
            path = Path(inputs.get("output_path", "ideogram.png"))
            outputs = [
                download(
                    item["url"],
                    path
                    if i == 0
                    else path.with_name(f"{path.stem}_{i + 1}{path.suffix}"),
                )
                for i, item in enumerate(images)
            ]
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": "ideogram-4.5",
                    "operation": mode,
                    "output": outputs[0],
                    "outputs": outputs,
                    "generation_id": result.get("generation_id"),
                    "cost_status": "unquoted",
                },
                artifacts=outputs,
                cost_usd=None,
                model="ideogram-4.5",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
