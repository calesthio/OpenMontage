"""Clotho adapter — converts an OpenMontage scene_plan into a Clotho flow.yaml.

Pure-Python library module. Does NOT import the Clotho package.
Mirrors the pattern of lib/shot_prompt_builder.py — a library, not a BaseTool.

Primary use case: cinematic-ad-30s pipeline
  6 scenes × 5s clips → still → i2v → concat → flow.yaml → clotho run
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from lib.shot_prompt_builder import build_motion_prompt, build_shot_prompt

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Flux image_size param for each aspect ratio (Clotho B1 gotcha:
# Flux uses image_size, not aspect_ratio)
_ASPECT_TO_IMAGE_SIZE: dict[str, str] = {
    "9:16": "portrait_16_9",
    "16:9": "landscape_16_9",
    "1:1": "square_1_1",
}

# OM scene types that generate video via still → i2v
_GENERATIVE_TYPES = {"generated", "broll"}

# OM scene types that are local passthrough (trim existing source footage)
_LOCAL_PASSTHROUGH_TYPES = {"talking_head", "screen_recording"}

# OM scene types skipped (Remotion/FFmpeg territory, not Clotho)
_SKIP_TYPES = {"text_card", "animation", "diagram", "transition"}

# Lightweight cost table (USD per call).
# Keep in sync with ~/repos/clotho/src/clotho/data/model_costs.yaml.
# Last synced: 2026-04-12
_MODEL_COSTS_USD: dict[str, float] = {
    "flux-2-pro": 0.04,
    "kling-2.5-turbo-pro": 0.70,
    "kling-3.0-pro": 2.00,
    "seedance-2.0": 0.40,
    "veo-3.1-image": 1.25,
}
_IMAGE_GEN_COST_USD = 0.04  # flux-2-pro balanced default


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ClothoAdapterOptions:
    """Options for the clotho_adapter.adapt() call."""

    project_name: str
    aspect_ratio: str = "9:16"
    tier: str = "balanced"
    consumer: str = "openmontage-cinematic"
    output_path: str | None = None
    save_output: str | None = None
    scene_refs: dict[str, list[str]] = field(default_factory=dict)
    style_context: dict[str, Any] | None = None
    project_root: str = "."


@dataclass
class ClothoAdapterResult:
    """Return value of clotho_adapter.adapt()."""

    flow_yaml: str
    node_count: int
    skipped_scenes: list[str]
    estimated_cost_usd: float
    warnings: list[str]


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------

class ClothoAdapterError(ValueError):
    """Raised on fatal errors (no generatable scenes, invalid aspect_ratio, etc.)."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _slugify(name: str) -> str:
    """Produce a Clotho-safe slug: lowercase, hyphens, no special chars.

    Output satisfies Clotho node id regex: [a-z0-9][a-z0-9_-]*
    """
    slug = name.lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = slug.strip("-")
    # Ensure starts with [a-z0-9]
    if slug and not re.match(r"[a-z0-9]", slug):
        slug = "x" + slug
    return slug or "unnamed"


def _clamp_duration(seconds: float) -> str:
    """Clamp scene duration to Clotho Kling string enum: '5' or '10'.

    Clotho B4 gotcha: duration is a string enum, not an int.
    Returns '5' if seconds <= 7.5, else '10'.
    """
    return "5" if seconds <= 7.5 else "10"


def _select_model(scene: dict[str, Any], has_refs: bool) -> str | None:
    """Select a Clotho model id for a video.image_to_video node.

    Returns a model id string, or None to let Clotho tier default resolve.

    Priority order:
    1. talking_head → kling-2.5-turbo-pro (human face, Seedance B2 risk)
    2. has_refs + wide shot → kling-3.0-pro (multi-char wide drift)
    3. has_refs → kling-2.5-turbo-pro (any human scene with char refs)
    4. otherwise → None (Seedance OK for non-human scenes)
    """
    scene_type = scene.get("type", "")
    sl = scene.get("shot_language", {})
    shot_size = sl.get("shot_size", "")

    if scene_type == "talking_head":
        return "kling-2.5-turbo-pro"

    wide_shots = {"wide", "extreme_wide", "medium_wide"}
    if has_refs and shot_size in wide_shots:
        return "kling-3.0-pro"

    if has_refs:
        return "kling-2.5-turbo-pro"

    return None


def _build_still_node(
    n: int,
    scene: dict[str, Any],
    aspect_ratio: str,
    style_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a Clotho image.generate node dict for scene index N (1-based)."""
    image_size = _ASPECT_TO_IMAGE_SIZE.get(aspect_ratio, "portrait_16_9")
    return {
        "id": f"s{n}-still",
        "kind": "image.generate",
        "provider": "fal",
        "params": {
            "prompt": build_shot_prompt(scene, style_context),
            "image_size": image_size,
        },
    }


def _build_clip_node(
    n: int,
    scene: dict[str, Any],
    aspect_ratio: str,
    refs: list[str],
    style_context: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a Clotho video.image_to_video node dict for scene index N (1-based).

    Critical invariants (Clotho v1.2 contract):
    - references field OMITTED (not []) when refs is empty
    - model field OMITTED when _select_model returns None
    - duration is STRING enum '5' or '10' (B4 gotcha)
    """
    duration_s = scene.get("end_seconds", 5) - scene.get("start_seconds", 0)
    node: dict[str, Any] = {
        "id": f"s{n}-clip",
        "kind": "video.image_to_video",
        "provider": "fal",
        "inputs": {
            "image": f"{{{{ s{n}-still.output }}}}",
        },
        "params": {
            "prompt": build_motion_prompt(scene, style_context),
            "duration": _clamp_duration(duration_s),
            "aspect_ratio": aspect_ratio,
        },
    }

    model = _select_model(scene, bool(refs))
    if model is not None:
        node["model"] = model

    if refs:
        node["references"] = refs

    return node


def _build_passthrough_node(
    n: int,
    scene: dict[str, Any],
    asset_manifest: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Build a Clotho video.trim node for a local passthrough scene.

    Returns (node_dict | None, warnings).
    Clotho video.trim uses 'from'/'to' params (not 'start'/'end').
    """
    warnings_out: list[str] = []
    scene_id = scene.get("id", "unknown")

    if asset_manifest is None:
        warnings_out.append(
            f"scene {scene_id!r} (type={scene.get('type')!r}): no asset_manifest provided — "
            "scene excluded from concat"
        )
        return None, warnings_out

    # Search asset_manifest["assets"] for a video asset matching this scene
    assets = asset_manifest.get("assets", [])
    video_asset = next(
        (a for a in assets if a.get("scene_id") == scene_id and a.get("type") == "video"),
        None,
    )

    if video_asset is None:
        warnings_out.append(
            f"scene {scene_id!r} (type={scene.get('type')!r}): no video asset found in "
            "asset_manifest — scene excluded from concat"
        )
        return None, warnings_out

    node: dict[str, Any] = {
        "id": f"s{n}-clip",
        "kind": "video.trim",
        "provider": "local",
        "tool": "ffmpeg",
        "inputs": {
            "video": video_asset["path"],
        },
        "params": {
            "from": scene.get("start_seconds", 0),
            "to": scene.get("end_seconds", 5),
        },
    }
    return node, warnings_out


def _build_concat_node(clip_node_ids: list[str]) -> dict[str, Any]:
    """Build the Clotho video.concat node that stitches all clips."""
    return {
        "id": "full-cut",
        "kind": "video.concat",
        "provider": "local",
        "tool": "ffmpeg",
        "inputs": {
            "videos": [f"{{{{ {cid}.output }}}}" for cid in clip_node_ids],
        },
    }


def _estimate_cost(nodes: list[dict[str, Any]]) -> float:
    """Naive cost estimate from local model cost table."""
    total = 0.0
    for node in nodes:
        kind = node.get("kind", "")
        if kind == "image.generate":
            total += _IMAGE_GEN_COST_USD
        elif kind == "video.image_to_video":
            model = node.get("model", "seedance-2.0")
            total += _MODEL_COSTS_USD.get(model, 0.40)
        # video.concat / video.trim → free
    return total


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def adapt(
    scene_plan: dict[str, Any],
    options: ClothoAdapterOptions,
    asset_manifest: dict[str, Any] | None = None,
) -> ClothoAdapterResult:
    """Convert an OpenMontage scene_plan artifact into a Clotho flow.yaml.

    Args:
        scene_plan: OM scene_plan artifact dict (validates against
                    schemas/artifacts/scene_plan.schema.json).
        options: Adapter configuration (ClothoAdapterOptions).
        asset_manifest: Optional OM asset_manifest dict. Required for
                        talking_head/screen_recording scenes with
                        source="source" (existing footage). Absent scenes
                        are excluded with a loud warning.

    Returns:
        ClothoAdapterResult with flow_yaml, node_count, skipped_scenes,
        estimated_cost_usd, and warnings.

    Raises:
        ClothoAdapterError: No generatable scenes found, invalid aspect_ratio,
                            or empty scene list.
    """
    if options.aspect_ratio not in _ASPECT_TO_IMAGE_SIZE:
        raise ClothoAdapterError(
            f"Invalid aspect_ratio {options.aspect_ratio!r}. "
            f"Must be one of: {sorted(_ASPECT_TO_IMAGE_SIZE)}"
        )

    raw_scenes = scene_plan.get("scenes", [])
    if not raw_scenes:
        raise ClothoAdapterError("scene_plan contains no scenes")

    # Sort by start_seconds
    scenes = sorted(raw_scenes, key=lambda s: s.get("start_seconds", 0))

    nodes: list[dict[str, Any]] = []
    clip_ids: list[str] = []
    skipped: list[str] = []
    all_warnings: list[str] = []

    for idx, scene in enumerate(scenes, start=1):
        scene_id = scene.get("id", f"scene-{idx}")
        scene_type = scene.get("type", "")

        # --- Skip non-Clotho-native types ---
        if scene_type in _SKIP_TYPES:
            skipped.append(scene_id)
            all_warnings.append(
                f"scene {scene_id!r} (type={scene_type!r}) skipped — "
                "not a Clotho-native kind (handled by Remotion/FFmpeg)"
            )
            continue

        # --- Resolve character refs ---
        refs = options.scene_refs.get(scene_id, [])
        valid_refs: list[str] = []
        for ref in refs:
            if not Path(ref).is_absolute():
                all_warnings.append(
                    f"scene {scene_id!r}: ref path {ref!r} is not absolute — dropped"
                )
            else:
                valid_refs.append(ref)

        # --- Determine if talking_head should be generative ---
        is_generative_talking_head = scene_type == "talking_head" and any(
            a.get("source") == "generate"
            for a in scene.get("required_assets", [])
        )

        # --- Generative path: still + clip nodes ---
        if scene_type in _GENERATIVE_TYPES or is_generative_talking_head:
            still_node = _build_still_node(idx, scene, options.aspect_ratio, options.style_context)
            clip_node = _build_clip_node(idx, scene, options.aspect_ratio, valid_refs, options.style_context)

            # Warn if duration clamped significantly
            duration_s = scene.get("end_seconds", 5) - scene.get("start_seconds", 0)
            clamped = int(_clamp_duration(duration_s))
            if abs(duration_s - clamped) > 2:
                all_warnings.append(
                    f"scene {scene_id!r}: duration {duration_s}s clamped to {clamped}s"
                )

            nodes.append(still_node)
            nodes.append(clip_node)
            clip_ids.append(clip_node["id"])

        # --- Local passthrough path: video.trim ---
        elif scene_type in _LOCAL_PASSTHROUGH_TYPES:
            passthrough_node, pw = _build_passthrough_node(idx, scene, asset_manifest)
            all_warnings.extend(pw)
            if passthrough_node is not None:
                nodes.append(passthrough_node)
                clip_ids.append(passthrough_node["id"])
            else:
                # Warning already added by _build_passthrough_node; also record skipped
                import sys
                print(
                    f"WARNING: scene {scene_id!r} excluded from Clotho flow — "
                    "no matching video asset in asset_manifest",
                    file=sys.stderr,
                )

        else:
            all_warnings.append(
                f"scene {scene_id!r} has unrecognised type {scene_type!r} — skipped"
            )
            skipped.append(scene_id)

    if not clip_ids:
        raise ClothoAdapterError(
            "no generatable scenes found in scene_plan — cannot build flow.yaml. "
            f"Skipped: {skipped}"
        )

    # --- Concat node ---
    concat_node = _build_concat_node(clip_ids)
    nodes.append(concat_node)

    # --- Outputs ---
    output_entry: dict[str, Any] = {
        "name": "final",
        "from": "{{ full-cut.output }}",
    }
    if options.save_output is not None:
        output_entry["save"] = options.save_output

    # --- Top-level flow dict ---
    flow: dict[str, Any] = {
        "version": 1,
        "name": _slugify(options.project_name),
        "consumer": options.consumer,
        "tier": options.tier,
        "nodes": nodes,
        "outputs": [output_entry],
    }

    flow_yaml = yaml.safe_dump(flow, sort_keys=False, allow_unicode=True)

    # --- Write to disk if requested ---
    if options.output_path is not None:
        out_path = Path(options.output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(flow_yaml, encoding="utf-8")

    cost = _estimate_cost(nodes)

    return ClothoAdapterResult(
        flow_yaml=flow_yaml,
        node_count=len(nodes),
        skipped_scenes=skipped,
        estimated_cost_usd=cost,
        warnings=all_warnings,
    )
