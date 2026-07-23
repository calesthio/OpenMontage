"""Omni reference helpers for Kling official providers."""

from __future__ import annotations

import re
from typing import Any

PLACEHOLDER_RE = re.compile(r"<<<image_(\d+)>>>")


def build_image_prompt_references(
    prompt: str,
    image_list: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """Bind image_list entries to stable Image Omni placeholders."""

    references = [
        {
            "index": index,
            "placeholder": f"<<<image_{index}>>>",
            "source": item.get("source") or item.get("image") or item.get("image_url"),
            "source_type": item.get("source_type", "unknown"),
        }
        for index, item in enumerate(image_list, start=1)
    ]
    if not references:
        return prompt, []

    existing_numbers = [int(value) for value in PLACEHOLDER_RE.findall(prompt)]
    if existing_numbers:
        if max(existing_numbers) > len(references):
            raise ValueError(
                f"prompt references <<<image_{max(existing_numbers)}>>> but only {len(references)} image(s) were provided"
            )
        if min(existing_numbers) < 1:
            raise ValueError("Image Omni prompt placeholders must start at <<<image_1>>>")
        return prompt, references

    placeholders = " ".join(item["placeholder"] for item in references)
    return f"{prompt}\nReferences: {placeholders}", references
