"""Element reference helpers for Kling official Omni providers.

These helpers intentionally do not inherit from BaseTool. Elements are an
internal provider reference mechanism in Phase 2, not a registry capability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .client import KlingClient


def normalize_element_list(element_list: Any | None) -> list[dict[str, int]]:
    """Normalize official Kling element references to element_list objects."""

    if not element_list:
        return []
    if not isinstance(element_list, list):
        raise ValueError("element_list must be a list of element ids or objects")

    normalized: list[dict[str, int]] = []
    for item in element_list:
        raw_id: Any
        if isinstance(item, dict):
            raw_id = item.get("element_id", item.get("id"))
        else:
            raw_id = item
        if raw_id is None:
            raise ValueError("each element_list item must include element_id")
        try:
            element_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"element_id must be an integer-compatible value: {raw_id!r}") from exc
        if element_id <= 0:
            raise ValueError("element_id must be positive")
        normalized.append({"element_id": element_id})
    return normalized


def element_ids(element_list: Any | None) -> list[int]:
    """Return normalized element ids from an element reference list."""

    return [item["element_id"] for item in normalize_element_list(element_list)]


def get_custom_element(element_id: int, client: KlingClient | None = None) -> dict[str, Any]:
    """Fetch one custom element for validation or diagnostics."""

    api = client or KlingClient()
    return api.get(f"/v1/general/advanced-custom-elements/{int(element_id)}")


def list_custom_elements(
    client: KlingClient | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List custom elements without creating or deleting assets."""

    api = client or KlingClient()
    return api.get("/v1/general/advanced-custom-elements", params=params)


def list_preset_elements(
    client: KlingClient | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """List official preset elements without entering the tool registry."""

    api = client or KlingClient()
    return api.get("/v1/general/advanced-presets-elements", params=params)


def write_elements_artifact(
    artifact_path: str | Path,
    elements: list[dict[str, Any]],
) -> Path:
    """Write element metadata in the Phase 2 reproducibility artifact shape."""

    path = Path(artifact_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"provider": "kling_official", "elements": elements}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
