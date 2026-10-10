"""Local Qwen Image 2.1 generation/editing using the official Diffusers pipeline."""

import os
from pathlib import Path
from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolResult,
    ResourceProfile,
)


class QwenImage21(BaseTool):
    name = "qwen_image_21"
    provider = "qwen_local"
    capability = "image_generation"
    tier = ToolTier.GENERATE
    runtime = ToolRuntime.LOCAL_GPU
    stability = ToolStability.EXPERIMENTAL
    agent_skills = ["provider-model-refresh"]
    capabilities = ["text_to_image", "image_edit", "transparent_image"]
    supports = {"image_edit": True, "transparent_background": True, "offline": True}
    install_instructions = "Install Diffusers with QwenImage21Pipeline, torch, transformers >=5.17, accelerate and Pillow. Download Qwen/Qwen-Image-2.1 separately and set QWEN_IMAGE_21_PATH to its local directory."
    best_for = ["Local Qwen Image 2.1 generation, editing and native RGBA images"]
    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=32000, vram_mb=16000, network_required=False
    )
    idempotency_key_fields = [
        "prompt",
        "image_path",
        "width",
        "height",
        "seed",
        "steps",
        "transparent_background",
    ]
    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "model": {
                "type": "string",
                "enum": ["qwen-image-2.1"],
                "default": "qwen-image-2.1",
            },
            "prompt": {"type": "string", "minLength": 1},
            "image_path": {"type": "string"},
            "generation_mode": {"type": "string", "enum": ["generate", "edit"]},
            "width": {
                "type": "integer",
                "minimum": 256,
                "multipleOf": 16,
                "default": 2048,
            },
            "height": {
                "type": "integer",
                "minimum": 256,
                "multipleOf": 16,
                "default": 2048,
            },
            "steps": {"type": "integer", "minimum": 1, "maximum": 100, "default": 40},
            "seed": {"type": "integer", "minimum": 0},
            "cpu_offload": {"type": "boolean", "default": True},
            "transparent_background": {"type": "boolean", "default": False},
            "output_path": {"type": "string"},
        },
    }

    def get_status(self):
        if not Path(
            os.getenv("QWEN_IMAGE_21_PATH", "__missing__"), "model_index.json"
        ).is_file():
            return ToolStatus.UNAVAILABLE
        try:
            import torch
            from diffusers import QwenImage21Pipeline

            if not callable(QwenImage21Pipeline):
                return ToolStatus.UNAVAILABLE
            return (
                ToolStatus.AVAILABLE
                if torch.cuda.is_available()
                else ToolStatus.UNAVAILABLE
            )
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs):
        return 0.0

    def execute(self, inputs):
        try:
            from jsonschema import validate

            validate(inputs, self.input_schema)
            mode = inputs.get(
                "generation_mode", "edit" if inputs.get("image_path") else "generate"
            )
            if (mode == "edit") != bool(inputs.get("image_path")):
                raise ValueError(
                    "Edit requires a source image; generate cannot accept one"
                )
            path = Path(inputs.get("output_path", "qwen_image_21.png"))
            if inputs.get("transparent_background") and path.suffix.lower() != ".png":
                raise ValueError("RGBA output requires a PNG path")
            if self.get_status() != ToolStatus.AVAILABLE:
                raise ValueError(self.install_instructions)
            import torch
            from PIL import Image
            from diffusers import QwenImage21Pipeline

            pipe = QwenImage21Pipeline.from_pretrained(
                os.environ["QWEN_IMAGE_21_PATH"],
                torch_dtype=torch.bfloat16,
                local_files_only=True,
            )
            if inputs.get("cpu_offload", True):
                pipe.enable_model_cpu_offload()
            else:
                pipe.to("cuda")
            prompt = inputs["prompt"]
            if inputs.get("transparent_background"):
                prompt = (
                    "This is an RGBA image with transparency. "
                    + prompt
                    + " The image has alpha channel and the background is transparent."
                )
            params = {"prompt": prompt, "num_inference_steps": inputs.get("steps", 40)}
            if inputs.get("image_path"):
                with Image.open(inputs["image_path"]) as image:
                    params["image"] = image.copy()
            else:
                params.update(
                    width=inputs.get("width", 2048), height=inputs.get("height", 2048)
                )
            if "seed" in inputs:
                params["generator"] = torch.Generator("cuda").manual_seed(
                    inputs["seed"]
                )
            image = pipe(**params).images[0]
            if inputs.get("transparent_background") and (
                "A" not in image.getbands()
                or image.getchannel("A").getextrema()[0] == 255
            ):
                raise ValueError(
                    "Model did not produce a usable alpha channel; output was not accepted as transparent"
                )
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(path)
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": "qwen-image-2.1",
                    "output": str(path),
                    "image_mode": image.mode,
                },
                artifacts=[str(path)],
                model="qwen-image-2.1",
            )
        except Exception as exc:
            return ToolResult(success=False, error=str(exc))
