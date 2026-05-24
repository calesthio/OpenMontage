"""DAM auto-registration hook for OpenMontage generation tools (B8 P2).

A thin optional-import shim. If ``sovereign_swarm.dam`` is importable AND
the caller supplied ``tenant_key`` in the tool inputs, a successful
``ToolResult`` is registered in the Sovereign DAM and the result's
``data`` dict gains a ``dam_asset_id`` field. Otherwise this module is a
no-op — OpenMontage continues to work standalone.

This is the only DAM-aware code path inside OpenMontage. Tools call
``maybe_register_artifact()`` once at the end of a successful ``execute()``
and the helper handles all of:

  - resolving the global registry (lazy-singleton)
  - mapping ``capability``/asset_type to the DAM ``asset_type`` enum
  - extracting prompt / seed / model / provider from the ``ToolResult``
  - calling ``registry.register()`` with the right parameters
  - swallowing all failures (DAM registration must NEVER block a
    successful generation — it is observability, not gating)

Per the B8 spec, this code currently imports from ``sovereign_swarm.dam``
because the DAM lives as a draft subpackage of sovereign-swarm. If/when
the DAM is extracted to its own ``sovereign-dam`` repo (operator-greenlit
repo lifecycle action), update only this file.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# Capability → DAM asset_type mapping
# ----------------------------------------------------------------------

# Each OpenMontage tool declares a `capability` class-level attribute. We
# translate that to the canonical DAM asset_type. If a tool's capability
# isn't in this table, we skip registration (don't guess — explicit list).
CAPABILITY_TO_ASSET_TYPE: dict[str, str] = {
    "image_generation": "still",
    "video_generation": "motion_clip",
    "video_post": "composed_video",
    "audio_generation": "audio",
    "audio_processing": "audio",  # audio_mixer outputs (mixed track)
    "tts": "narration",
    "music_generation": "music",
}


# ----------------------------------------------------------------------
# Registry singleton
# ----------------------------------------------------------------------

_REGISTRY = None  # populated lazily on first call


def _resolve_registry():
    """Return a shared AssetRegistry, or None if the DAM package is unavailable."""
    global _REGISTRY
    if _REGISTRY is False:
        # We've previously decided the DAM is unavailable on this machine.
        return None
    if _REGISTRY is not None:
        return _REGISTRY
    try:
        from sovereign_swarm.dam.registry import AssetRegistry  # type: ignore
    except ImportError:
        logger.debug("sovereign_swarm.dam not importable; DAM auto-registration disabled")
        _REGISTRY = False
        return None
    try:
        # Honor SOVEREIGN_DAM_ROOT env override for tests; otherwise default
        # to the spec'd TCC-safe path.
        root = os.environ.get("SOVEREIGN_DAM_ROOT")
        _REGISTRY = AssetRegistry(dam_root=root) if root else AssetRegistry()
    except Exception as e:  # pragma: no cover — defensive
        logger.warning("Failed to initialize AssetRegistry: %s", e)
        _REGISTRY = False
        return None
    return _REGISTRY


def reset_registry_for_tests() -> None:
    """Clear the cached singleton — test helper only."""
    global _REGISTRY
    _REGISTRY = None


# ----------------------------------------------------------------------
# Public hook
# ----------------------------------------------------------------------

def maybe_register_artifact(
    *,
    tool_result,  # ToolResult — typed loosely to avoid a circular import on tools.base_tool
    inputs: dict[str, Any],
    capability: str,
    created_by_tool: str,
    artifact_path: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    duration_s: Optional[float] = None,
) -> Optional[str]:
    """Register a successful tool output in the DAM.

    Returns the new ``asset_id`` if registration happened, else None.

    Behavior:
      - No-op if ``inputs.get("dam_register") is False``  (caller opt-out).
      - No-op if ``inputs.get("tenant_key")`` is absent  (no tenant → no DAM row).
      - No-op if ``sovereign_swarm.dam`` is not importable.
      - No-op if the tool's ``capability`` is not in CAPABILITY_TO_ASSET_TYPE.
      - No-op if registration raises — DAM registration must never break
        generation. The exception is logged at WARNING.

    Tools call this AFTER they've decided the run succeeded but BEFORE
    they return the ToolResult. The caller is responsible for mutating
    ``tool_result.data`` to include the asset_id when this returns non-None.
    """
    if inputs.get("dam_register") is False:
        return None

    tenant_key = inputs.get("tenant_key")
    if not tenant_key:
        return None

    asset_type = CAPABILITY_TO_ASSET_TYPE.get(capability)
    if asset_type is None:
        logger.debug("No DAM asset_type mapping for capability=%r; skipping", capability)
        return None

    reg = _resolve_registry()
    if reg is None:
        return None

    # Find the artifact file. Prefer an explicit arg, then ToolResult.artifacts[0],
    # then the conventional `output` / `output_path` keys from .data.
    path_str = artifact_path
    if not path_str and getattr(tool_result, "artifacts", None):
        path_str = tool_result.artifacts[0] if tool_result.artifacts else None
    if not path_str:
        data = getattr(tool_result, "data", None) or {}
        path_str = data.get("output") or data.get("output_path")
    if not path_str:
        logger.debug("DAM hook: no artifact path discoverable; skipping")
        return None

    fp = Path(path_str)
    if not fp.exists():
        logger.debug("DAM hook: artifact path %s does not exist; skipping", fp)
        return None

    data = getattr(tool_result, "data", None) or {}
    try:
        asset = reg.register(
            tenant_key=tenant_key,
            asset_type=asset_type,
            file_path=fp,
            created_by_tool=created_by_tool,
            provider=data.get("provider"),
            model=data.get("model") or getattr(tool_result, "model", None),
            prompt=data.get("prompt") or inputs.get("prompt"),
            seed=data.get("seed") if data.get("seed") is not None else inputs.get("seed"),
            brand_key=inputs.get("brand_key") or tenant_key,
            tags=tuple(inputs.get("dam_tags") or ()),
            width=width or inputs.get("width"),
            height=height or inputs.get("height"),
            duration_s=duration_s,
            quality_score=inputs.get("quality_score"),
            compliance_status=inputs.get("compliance_status", "unreviewed"),
        )
    except Exception as e:
        logger.warning("DAM registration failed (%s); continuing without it", e)
        return None

    return asset.asset_id


# ----------------------------------------------------------------------
# Schema fragment — every tool's input_schema should merge this in
# ----------------------------------------------------------------------

DAM_INPUT_SCHEMA_FRAGMENT: dict[str, Any] = {
    "tenant_key": {
        "type": "string",
        "description": (
            "Sovereign tenant key (atx_mats / gli / gbb / sovereign / sovereign_mind). "
            "When provided, the successful output is auto-registered in the DAM and "
            "the result's data.dam_asset_id is populated."
        ),
    },
    "brand_key": {
        "type": "string",
        "description": "DAM brand_key. Defaults to tenant_key when omitted.",
    },
    "dam_tags": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Free-form tags applied to the registered DAM record.",
    },
    "dam_register": {
        "type": "boolean",
        "default": True,
        "description": "Set false to skip DAM auto-registration even with tenant_key.",
    },
    "quality_score": {"type": "number", "description": "0.0-1.0 quality estimate."},
    "compliance_status": {
        "type": "string",
        "enum": ["unreviewed", "approved", "flagged", "restricted"],
        "default": "unreviewed",
    },
}
