"""MAI Image 2.6/Flash deployed on Microsoft Foundry."""

import base64
import os
from contextlib import ExitStack
from pathlib import Path
from urllib.parse import urlparse
import requests
from tools.audio._speech_api import SpeechAPI
from tools.base_tool import ToolTier, ToolStatus, ToolResult


class MAIImage(SpeechAPI):
    name = "mai_image"
    provider = "microsoft_mai"
    capability = "image_generation"
    tier = ToolTier.GENERATE
    credential = "MAI_API_KEY"
    dependencies = ["env:MAI_API_KEY", "env:MAI_ENDPOINT", "env:MAI_IMAGE_DEPLOYMENT"]
    install_instructions = "Configure MAI_API_KEY, MAI_ENDPOINT (Foundry resource HTTPS origin), MAI_IMAGE_DEPLOYMENT and MAI_IMAGE_MODEL (MAI-Image-2.6 or MAI-Image-2.6-Flash)."
    capabilities = ["text_to_image", "image_edit"]
    supports = {"image_edit": True, "multiple_reference_images": True}
    input_schema = {
        "type": "object",
        "required": ["prompt", "model"],
        "properties": {
            "prompt": {"type": "string", "minLength": 1},
            "model": {"enum": ["MAI-Image-2.6", "MAI-Image-2.6-Flash"]},
            "generation_mode": {"enum": ["generate", "edit"]},
            "image_path": {"type": "string"},
            "image_paths": {
                "type": "array",
                "maxItems": 5,
                "items": {"type": "string"},
            },
            "width": {"type": "integer", "minimum": 768},
            "height": {"type": "integer", "minimum": 768},
            "auto_aspect_ratio": {"type": "boolean"},
            "web_grounding": {"type": "boolean"},
            "output_path": {"type": "string"},
        },
    }

    def get_status(self):
        return (
            ToolStatus.AVAILABLE
            if all(
                os.getenv(k)
                for k in (
                    "MAI_API_KEY",
                    "MAI_ENDPOINT",
                    "MAI_IMAGE_DEPLOYMENT",
                    "MAI_IMAGE_MODEL",
                )
            )
            else ToolStatus.UNAVAILABLE
        )

    def generate(self, inputs, key):
        if (
            inputs.get("output_path")
            and Path(inputs["output_path"]).suffix.lower() != ".png"
        ):
            raise ValueError("MAI output_path must use .png")
        if inputs.get("width", 1024) * inputs.get("height", 1024) > 2359296:
            raise ValueError("MAI image dimensions exceed 2,359,296 pixels")
        endpoint = os.environ["MAI_ENDPOINT"].rstrip("/")
        url = urlparse(endpoint)
        if (
            url.scheme != "https"
            or not (url.hostname or "").endswith(".services.ai.azure.com")
            or url.path not in ("", "/")
        ):
            raise ValueError("MAI_ENDPOINT must be the HTTPS Foundry resource origin")
        if os.getenv("MAI_IMAGE_MODEL") != inputs["model"]:
            raise ValueError(
                "Selected model does not match the configured MAI_IMAGE_MODEL deployment"
            )
        paths = list(inputs.get("image_paths") or [])
        if inputs.get("image_path"):
            paths.insert(0, inputs["image_path"])
        operation = inputs.get("generation_mode", "edit" if paths else "generate")
        payload = {
            "model": os.environ["MAI_IMAGE_DEPLOYMENT"],
            "prompt": inputs["prompt"],
        }
        for field in ("auto_aspect_ratio", "web_grounding"):
            if field in inputs:
                payload[field] = inputs[field]
        headers = {"api-key": key}
        if operation == "edit":
            if not 1 <= len(paths) <= 5:
                raise ValueError("MAI edits require 1-5 source images")
            if "width" in inputs or "height" in inputs:
                raise ValueError("Explicit dimensions are generation-only")
            for field in ("auto_aspect_ratio", "web_grounding"):
                if field in payload:
                    payload[field] = str(payload[field]).lower()
            with ExitStack() as stack:
                files = [
                    ("image", (Path(p).name, stack.enter_context(open(p, "rb"))))
                    for p in paths
                ]
                r = requests.post(
                    endpoint + "/mai/v1/images/edits",
                    headers=headers,
                    data=payload,
                    files=files,
                    timeout=180,
                )
        else:
            if paths:
                raise ValueError("Select edit with source images")
            payload.update(
                width=inputs.get("width", 1024), height=inputs.get("height", 1024)
            )
            r = requests.post(
                endpoint + "/mai/v1/images/generations",
                headers=headers,
                json=payload,
                timeout=180,
            )
        r.raise_for_status()
        body = r.json()
        images = [x["b64_json"] for x in body.get("data", []) if x.get("b64_json")]
        if not images:
            raise ValueError("MAI returned no image data")
        out = Path(inputs.get("output_path") or "mai_image.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        outputs = []
        for i, encoded in enumerate(images):
            p = out if i == 0 else out.with_name(f"{out.stem}_{i+1}{out.suffix}")
            p.write_bytes(base64.b64decode(encoded, validate=True))
            outputs.append(str(p))
        return ToolResult(
            success=True,
            data={
                "output": outputs[0],
                "outputs": outputs,
                "provider": self.provider,
                "model": inputs["model"],
                "deployment": payload["model"],
                "cost_status": "unquoted",
            },
            artifacts=outputs,
            model=inputs["model"],
            cost_usd=None,
        )
