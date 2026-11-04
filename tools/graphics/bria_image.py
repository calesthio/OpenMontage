"""Bria Fibo 2 generation/editing with preserved structured result metadata."""

import os
from pathlib import Path
import requests
from jsonschema import validate
from tools.audio._speech_api import SpeechAPI
from tools.base_tool import ToolTier, ToolResult
from tools.schema_media import local_image
from tools.provider_jobs import download


class BriaImage(SpeechAPI):
    name = "bria_image"
    provider = "bria"
    capability = "image_generation"
    tier = ToolTier.GENERATE
    credential = "BRIA_API_TOKEN"
    dependencies = ["env:BRIA_API_TOKEN"]
    install_instructions = "Configure BRIA_API_TOKEN from https://platform.bria.ai/."
    capabilities = ["text_to_image", "image_edit"]
    supports = {"image_edit": True, "multiple_reference_images": True}
    input_schema = {
        "type": "object",
        "properties": {
            "model": {"enum": ["fibo-2"]},
            "generation_mode": {"enum": ["generate", "edit"]},
            "prompt": {"type": "string"},
            "instruction": {"type": "string"},
            "structured_prompt": {"type": "string"},
            "structured_instruction": {"type": "string"},
            "image_urls": {"type": "array", "maxItems": 4, "items": {"type": "string"}},
            "image_paths": {
                "type": "array",
                "maxItems": 4,
                "items": {"type": "string"},
            },
            "image_path": {"type": "string"},
            "mask_path": {"type": "string"},
            "mask_url": {"type": "string"},
            "aspect_ratio": {
                "enum": [
                    "1:1",
                    "2:3",
                    "3:2",
                    "3:4",
                    "4:3",
                    "4:5",
                    "5:4",
                    "9:16",
                    "16:9",
                    "16:10",
                    "10:16",
                    "2:1",
                    "1:2",
                    "21:9",
                    "9:21",
                    "3:1",
                    "1:3",
                    "4:1",
                    "1:4",
                    "5:1",
                    "1:5",
                ]
            },
            "style": {
                "enum": ["kodak_film", "hard_flash", "hazy_dreamy", "rough_realism"]
            },
            "seed": {"type": "integer"},
            "output_format": {"enum": ["png", "jpeg"]},
            "output_path": {"type": "string"},
        },
    }

    def build_request(self, inputs):
        validate(inputs, self.input_schema)
        images = list(inputs.get("image_urls") or [])
        paths = list(inputs.get("image_paths") or [])
        if inputs.get("image_path"):
            paths.insert(0, inputs["image_path"])
        images.extend(local_image(p) for p in paths)
        operation = inputs.get("generation_mode", "edit" if images else "generate")
        if len(images) > 4:
            raise ValueError("Fibo editing supports at most four images")
        payload = {"sync": True, "output_type": inputs.get("output_format", "png")}
        for k in ("aspect_ratio", "seed"):
            if k in inputs:
                payload[k] = inputs[k]
        if operation == "edit":
            if not images:
                raise ValueError("Edit requires images")
            payload["images"] = images
            if inputs.get("structured_instruction"):
                payload["structured_instruction"] = inputs["structured_instruction"]
            elif inputs.get("instruction") or inputs.get("prompt"):
                payload["instruction"] = inputs.get("instruction") or inputs["prompt"]
            else:
                raise ValueError("Edit requires instruction or structured_instruction")
            mask = (
                local_image(inputs["mask_path"])
                if inputs.get("mask_path")
                else inputs.get("mask_url")
            )
            if mask:
                if len(images) != 1:
                    raise ValueError("Mask requires exactly one image")
                payload["mask"] = mask
            if inputs.get("style"):
                raise ValueError("style is generation-only")
        else:
            if inputs.get("mask_path") or inputs.get("mask_url"):
                raise ValueError("Masks require edit mode")
            if len(images) > 1:
                raise ValueError("Generation supports one reference")
            if not inputs.get("prompt") and not inputs.get("structured_prompt"):
                raise ValueError("Generation requires prompt or structured_prompt")
            for k in ("prompt", "structured_prompt", "style"):
                if k in inputs:
                    payload[k] = inputs[k]
            if images:
                payload["images"] = images
            if payload.get("style") and (images or payload.get("structured_prompt")):
                raise ValueError("style requires text-only generation")
            # These combinations select older Fibo implementations on the shared API.
            if (images and not inputs.get("prompt")) or (
                inputs.get("prompt") and inputs.get("structured_prompt")
            ):
                raise ValueError(
                    "This combination is not served by Fibo 2; choose prompt+image or structured_prompt alone"
                )
        return operation, payload

    def generate(self, inputs, key):
        operation, payload = self.build_request(inputs)
        r = requests.post(
            "https://engine.prod.bria-api.com/v2/image/" + operation,
            headers={"api_token": key},
            json=payload,
            timeout=180,
        )
        r.raise_for_status()
        body = r.json()
        result = body["result"]
        path = Path(
            inputs.get("output_path") or "fibo2." + inputs.get("output_format", "png")
        )
        download(result["image_url"], path)
        import json

        meta = path.with_name(path.name + ".metadata.json")
        meta.write_text(json.dumps(body, indent=2), encoding="utf8")
        return ToolResult(
            success=True,
            data={
                "output": str(path),
                "provider": self.provider,
                "model": "fibo-2",
                "operation": operation,
                "provider_result": result,
                "cost_status": "unquoted",
            },
            artifacts=[str(path), str(meta)],
            model="fibo-2",
            cost_usd=None,
        )
