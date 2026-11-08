"""GPT Image 2 pictures through the MiniCut CLI (price first, then one yes)."""

from __future__ import annotations

from typing import Any

from tools.minicut_tool import APPROVAL_SCHEMA, RESUME_SCHEMA, MiniCutTool


class MiniCutImage(MiniCutTool):
    name = "minicut_image"
    capability = "image_generation"
    model = "gpt-image-2"
    default_output = "minicut_image.png"
    agent_skills: list[str] = []

    capabilities = ["text_to_image", "image_to_image"]
    supports = {"reference_images": True, "price_quote_before_run": True}
    best_for = [
        "GPT Image 2 stills and reference-guided edits on the same sign-in as MiniCut video, voice and music",
        "paid runs that must show the price and wait for a yes",
    ]
    fallback_tools = ["openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "quality": {"type": "string", "enum": ["low", "medium", "high"], "default": "medium"},
            "image_paths": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 16,
                "description": "Reference pictures to edit from or follow",
            },
            "approval": APPROVAL_SCHEMA,
            "resume_job": RESUME_SCHEMA,
            "poll_timeout": {"type": "integer", "default": 900},
            "output_path": {"type": "string", "default": "minicut_image.png"},
        },
    }
    idempotency_key_fields = ["prompt", "quality", "image_paths"]
    side_effects = [
        "writes an image file to output_path",
        "spends MiniCut credits after approval",
        "keeps a copy of the result in the MiniCut library",
    ]
    user_visible_verification = ["Look at the picture for the subject, text and framing asked for"]

    def _request(self, inputs: dict[str, Any]):
        files = [(f"image_ref[{i}]", p) for i, p in enumerate(inputs.get("image_paths") or [])]
        return inputs["prompt"], {"quality": inputs.get("quality", "medium")}, files
