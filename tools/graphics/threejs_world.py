"""Deterministic semantic Three.js world authoring for HyperFrames.

The agent owns creative planning. This tool validates and normalizes a structured
world specification, materializes an editable Three.js workspace, and emits a
diagnostic report. Rendering remains the responsibility of video_compose /
hyperframes_compose so pipeline governance and review stay intact.
"""

from __future__ import annotations

import copy
import html
import json
import math
import re
import shutil
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_LANDFORMS = {"plain", "peak", "ridge", "dune", "terrace", "basin", "canyon"}
_LANDMARKS = {"monolith", "arch", "tower", "ruin", "crystal", "settlement", "ring"}
_RENDER_MODES = {"cinematic", "semantic", "wireframe"}
_QUALITY_TIERS = {"blockout", "production"}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _number(value: Any, default: float) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _integer(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _slug(value: Any, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return text or fallback


def _color(value: Any, default: str) -> str:
    text = str(value or "")
    return text if _HEX.fullmatch(text) else default


def _vec(value: Any, length: int, default: list[float]) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) != length:
        return list(default)
    return [_number(component, default[index]) for index, component in enumerate(value)]


class ThreeJSWorld(BaseTool):
    """Build and validate an editable semantic world workspace."""

    name = "threejs_world"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "3d_world_generation"
    provider = "threejs"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL
    dependencies: list[str] = []
    install_instructions = (
        "World authoring is dependency-free. Final rendering requires the configured "
        "HyperFrames runtime (Node.js >= 22, npx, and FFmpeg)."
    )
    agent_skills = ["threejs-world-generation"]
    capabilities = [
        "semantic_region_planning",
        "procedural_height_field",
        "region_aware_asset_scattering",
        "explicit_landmark_placement",
        "deterministic_camera_flythrough",
        "semantic_and_wireframe_diagnostics",
        "hyperframes_atelier_workspace",
        "licensed_gltf_asset_palette",
        "production_fidelity_gate",
        "pbr_terrain_material_contract",
    ]
    best_for = [
        "Editable cinematic 3D worlds and terrain fly-throughs",
        "Free-viewpoint environments built without paid generation APIs",
        "Region-aware terrain, biomes, landmarks, and diagnostic passes",
        "Production worlds assembled from local licensed GLTF/PBR catalogs",
    ]
    not_good_for = [
        "Single-view mesh reconstruction without a separately configured provider",
        "Articulated characters, physics, navmeshes, or interactive game logic",
        "Single isolated product models where a normal Three.js scene is simpler",
    ]
    input_schema = {
        "type": "object",
        "required": ["operation", "world_spec"],
        "properties": {
            "operation": {"type": "string", "enum": ["build", "validate"]},
            "world_spec": {"type": "object"},
            "output_path": {"type": "string"},
            "duration_seconds": {"type": "number", "minimum": 1, "maximum": 600},
            "width": {"type": "integer", "minimum": 320, "maximum": 7680},
            "height": {"type": "integer", "minimum": 240, "maximum": 4320},
            "render_mode": {
                "type": "string",
                "enum": ["cinematic", "semantic", "wireframe"],
            },
            "quality_tier": {"type": "string", "enum": ["blockout", "production"]},
            "asset_catalog_paths": {"type": "array", "items": {"type": "string"}},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "workspace": {"type": "string"},
            "entry": {"type": "string"},
            "world_spec": {"type": "object"},
            "report": {"type": "object"},
        },
    }
    artifact_schema = {"artifact": "3d_world"}
    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=1024, disk_mb=2000, network_required=True
    )
    idempotency_key_fields = ["operation", "world_spec", "duration_seconds", "render_mode", "quality_tier", "asset_catalog_paths"]
    side_effects = [
        "writes an editable HyperFrames/Three.js workspace to output_path",
        "writes normalized world and diagnostic JSON files",
    ]
    fallback_tools: list[str] = []
    user_visible_verification = [
        "Inspect semantic, regional, and walk-level snapshots before final render",
        "Verify landmark contact, camera clearance, and stable region identities",
        "Open index.html with HyperFrames preview to explore the authored camera path",
    ]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        operation = str(inputs.get("operation", ""))
        duration = _clamp(_number(inputs.get("duration_seconds"), 60.0), 1.0, 600.0)
        width = int(_clamp(_integer(inputs.get("width"), 1920), 320, 7680))
        height = int(_clamp(_integer(inputs.get("height"), 1080), 240, 4320))
        render_mode = str(inputs.get("render_mode") or "cinematic").lower()
        if render_mode not in _RENDER_MODES:
            return ToolResult(success=False, error=f"Unknown render_mode: {render_mode}")
        quality_tier = str(inputs.get("quality_tier") or "blockout").lower()
        if quality_tier not in _QUALITY_TIERS:
            return ToolResult(success=False, error=f"Unknown quality_tier: {quality_tier}")
        catalog_paths = [Path(str(path)).expanduser().resolve() for path in inputs.get("asset_catalog_paths") or []]

        spec, normalize_warnings = self._normalize_spec(
            inputs.get("world_spec") or {}, duration=duration
        )
        report = self._report(spec, duration=duration, warnings=normalize_warnings)
        report["quality_tier"] = quality_tier
        report["asset_catalog_paths"] = [str(path) for path in catalog_paths]
        fidelity_errors, fidelity_warnings = self._fidelity_gate(spec, quality_tier, catalog_paths)
        report["errors"].extend(fidelity_errors)
        report["warnings"].extend(fidelity_warnings)

        if operation == "validate":
            return ToolResult(
                success=not report["errors"],
                data={"world_spec": spec, "report": report},
                error="; ".join(report["errors"]) if report["errors"] else None,
                duration_seconds=round(time.time() - started, 2),
                seed=spec["seed"],
                model=f"threejs-world-{quality_tier}-v2",
            )

        if operation != "build":
            return ToolResult(success=False, error=f"Unknown operation: {operation}")
        if report["errors"]:
            return ToolResult(
                success=False,
                data={"world_spec": spec, "report": report},
                error="World specification failed validation: " + "; ".join(report["errors"]),
            )

        output_raw = inputs.get("output_path")
        if not output_raw:
            return ToolResult(success=False, error="output_path is required for operation='build'")
        workspace = Path(str(output_raw)).expanduser().resolve()

        try:
            artifacts = self._write_workspace(
                workspace=workspace,
                spec=spec,
                report=report,
                duration=duration,
                width=width,
                height=height,
                render_mode=render_mode,
                quality_tier=quality_tier,
                catalog_paths=catalog_paths,
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"3D world build failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "workspace": str(workspace),
                "entry": str(workspace / "index.html"),
                "world_spec": spec,
                "report": report,
                "render_mode": render_mode,
                "duration_seconds": duration,
                "width": width,
                "height": height,
            },
            artifacts=artifacts,
            duration_seconds=round(time.time() - started, 2),
            seed=spec["seed"],
            model=f"threejs-world-{quality_tier}-v2",
        )

    @staticmethod
    def _fidelity_gate(
        spec: dict[str, Any], quality_tier: str, catalog_paths: list[Path]
    ) -> tuple[list[str], list[str]]:
        if quality_tier == "blockout":
            return [], [
                "Blockout tier may use procedural primitives and flat materials; "
                "do not present it as reference-grade or production-fidelity output."
            ]

        errors: list[str] = []
        warnings: list[str] = []
        manifests: list[dict[str, Any]] = []
        for catalog_path in catalog_paths:
            manifest_path = catalog_path / "catalog-manifest.json"
            if not manifest_path.is_file():
                errors.append(f"Production catalog manifest missing: {manifest_path}")
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                errors.append(f"Production catalog manifest unreadable: {manifest_path}: {exc}")
                continue
            if manifest.get("license") not in {"CC0", "CC0-1.0"}:
                errors.append(f"Catalog {manifest_path} lacks an approved CC0 license declaration.")
            if int(manifest.get("model_count") or 0) <= 0:
                errors.append(f"Catalog {manifest_path} contains no GLTF/GLB models.")
            manifests.append(manifest)

        asset_palette = spec.get("asset_palette") or []
        terrain_materials = spec.get("terrain_materials") or []
        if not catalog_paths:
            errors.append("Production tier requires at least one installed asset catalog path.")
        if len(asset_palette) < 8:
            errors.append("Production tier requires at least 8 distinct asset-palette entries.")
        if len(terrain_materials) < 3:
            errors.append("Production tier requires at least 3 terrain material layers.")
        if any(not item.get("catalog_id") or not item.get("model_id") for item in asset_palette):
            errors.append("Every production asset-palette entry requires catalog_id and model_id.")
        if any(not item.get("base_color") or not item.get("normal") or not item.get("roughness") for item in terrain_materials):
            errors.append("Every production terrain material requires base_color, normal, and roughness maps.")

        unique_categories = {str(item.get("category") or "") for item in asset_palette}
        if len(unique_categories - {""}) < 4:
            errors.append("Production asset palette requires at least 4 semantic categories.")
        if len(manifests) == 1:
            warnings.append("Only one asset catalog is installed; repetition must be checked at walk level.")
        return errors, warnings

    @classmethod
    def _normalize_spec(
        cls, raw: dict[str, Any], *, duration: float
    ) -> tuple[dict[str, Any], list[str]]:
        source = copy.deepcopy(raw) if isinstance(raw, dict) else {}
        warnings: list[str] = []
        world_raw = source.get("world") if isinstance(source.get("world"), dict) else {}
        atmosphere_raw = (
            source.get("atmosphere") if isinstance(source.get("atmosphere"), dict) else {}
        )
        terrain_materials_raw = source.get("terrain_materials") if isinstance(source.get("terrain_materials"), list) else []
        asset_palette_raw = source.get("asset_palette") if isinstance(source.get("asset_palette"), list) else []

        world = {
            "size": _clamp(_number(world_raw.get("size"), 120.0), 24.0, 500.0),
            "resolution": int(
                _clamp(_integer(world_raw.get("resolution"), 144), 24, 256)
            ),
            "elevation_scale": _clamp(
                _number(world_raw.get("elevation_scale"), 16.0), 1.0, 80.0
            ),
            "water_level": _clamp(
                _number(world_raw.get("water_level"), -2.0), -60.0, 60.0
            ),
        }
        atmosphere = {
            "sky_color": _color(atmosphere_raw.get("sky_color"), "#07111f"),
            "fog_color": _color(atmosphere_raw.get("fog_color"), "#13263a"),
            "fog_density": _clamp(
                _number(atmosphere_raw.get("fog_density"), 0.008), 0.0, 0.08
            ),
            "sun_color": _color(atmosphere_raw.get("sun_color"), "#ffd7a3"),
            "sun_intensity": _clamp(
                _number(atmosphere_raw.get("sun_intensity"), 3.0), 0.0, 12.0
            ),
            "sun_position": _vec(
                atmosphere_raw.get("sun_position"), 3, [45.0, 70.0, 20.0]
            ),
            "ground_color": _color(atmosphere_raw.get("ground_color"), "#151c23"),
        }

        palette = ["#315b48", "#73523d", "#2d5968", "#6f4b78", "#8b753f"]
        accent_palette = ["#8ee6b1", "#ff9a62", "#64d8ff", "#d4a8ff", "#ffe27a"]
        regions: list[dict[str, Any]] = []
        raw_regions = source.get("regions") if isinstance(source.get("regions"), list) else []
        for index, item in enumerate(raw_regions[:12]):
            item = item if isinstance(item, dict) else {}
            region_id = _slug(item.get("id") or item.get("label"), f"region-{index + 1}")
            landform = str(item.get("landform") or "plain").lower()
            if landform not in _LANDFORMS:
                warnings.append(
                    f"Region {region_id}: unknown landform {landform!r}; using 'plain'."
                )
                landform = "plain"
            scatter_raw = item.get("scatter") if isinstance(item.get("scatter"), dict) else {}
            center = _vec(item.get("center"), 2, [0.0, 0.0])
            center = [_clamp(center[0], -1.0, 1.0), _clamp(center[1], -1.0, 1.0)]
            regions.append(
                {
                    "id": region_id,
                    "label": str(item.get("label") or region_id.replace("-", " ").title()),
                    "center": center,
                    "radius": _clamp(_number(item.get("radius"), 0.75), 0.12, 2.5),
                    "base_elevation": _clamp(
                        _number(item.get("base_elevation"), 0.0), -2.0, 2.0
                    ),
                    "amplitude": _clamp(_number(item.get("amplitude"), 0.65), 0.0, 2.5),
                    "frequency": _clamp(_number(item.get("frequency"), 1.0), 0.15, 8.0),
                    "landform": landform,
                    "blend_width": _clamp(
                        _number(item.get("blend_width"), 0.22), 0.02, 1.0
                    ),
                    "color": _color(item.get("color"), palette[index % len(palette)]),
                    "accent_color": _color(
                        item.get("accent_color"), accent_palette[index % len(accent_palette)]
                    ),
                    "scatter": {
                        "tree": int(
                            _clamp(_integer(scatter_raw.get("tree"), 0), 0, 1200)
                        ),
                        "rock": int(
                            _clamp(_integer(scatter_raw.get("rock"), 35), 0, 1200)
                        ),
                        "crystal": int(
                            _clamp(_integer(scatter_raw.get("crystal"), 0), 0, 1200)
                        ),
                    },
                    "slope_limit": _clamp(
                        _number(item.get("slope_limit"), 1.8), 0.1, 12.0
                    ),
                }
            )

        landmarks: list[dict[str, Any]] = []
        raw_landmarks = (
            source.get("landmarks") if isinstance(source.get("landmarks"), list) else []
        )
        fallback_region = regions[0]["id"] if regions else ""
        for index, item in enumerate(raw_landmarks[:80]):
            item = item if isinstance(item, dict) else {}
            landmark_id = _slug(item.get("id"), f"landmark-{index + 1}")
            kind = str(item.get("type") or "monolith").lower()
            if kind not in _LANDMARKS:
                warnings.append(
                    f"Landmark {landmark_id}: unknown type {kind!r}; using 'monolith'."
                )
                kind = "monolith"
            landmarks.append(
                {
                    "id": landmark_id,
                    "type": kind,
                    "region_id": _slug(item.get("region_id"), fallback_region),
                    "position": _vec(item.get("position"), 3, [0.0, 0.0, 0.0]),
                    "rotation": _vec(item.get("rotation"), 3, [0.0, 0.0, 0.0]),
                    "scale": _clamp(_number(item.get("scale"), 4.0), 0.2, 30.0),
                    "color": _color(item.get("color"), "#30343b"),
                    "accent_color": _color(item.get("accent_color"), "#74e5ff"),
                }
            )

        camera_path: list[dict[str, Any]] = []
        raw_camera = (
            source.get("camera_path") if isinstance(source.get("camera_path"), list) else []
        )
        for index, item in enumerate(raw_camera[:40]):
            item = item if isinstance(item, dict) else {}
            default_time = (duration * index / max(1, len(raw_camera) - 1)) if raw_camera else 0
            camera_path.append(
                {
                    "time": _clamp(_number(item.get("time"), default_time), 0.0, duration),
                    "position": _vec(item.get("position"), 3, [60.0, 35.0, 60.0]),
                    "target": _vec(item.get("target"), 3, [0.0, 0.0, 0.0]),
                    "fov": _clamp(_number(item.get("fov"), 45.0), 18.0, 90.0),
                    "label": str(item.get("label") or ""),
                }
            )
        camera_path.sort(key=lambda key: key["time"])

        spec = {
            "version": str(source.get("version") or "1.0"),
            "title": str(source.get("title") or "Untitled Three.js World"),
            "seed": _integer(source.get("seed"), 1337),
            "explicit_constraints": [
                str(value)
                for value in source.get("explicit_constraints", [])
                if str(value).strip()
            ]
            if isinstance(source.get("explicit_constraints"), list)
            else [],
            "inferred_details": [
                str(value)
                for value in source.get("inferred_details", [])
                if str(value).strip()
            ]
            if isinstance(source.get("inferred_details"), list)
            else [],
            "world": world,
            "atmosphere": atmosphere,
            "terrain_materials": [copy.deepcopy(item) for item in terrain_materials_raw if isinstance(item, dict)],
            "asset_palette": [copy.deepcopy(item) for item in asset_palette_raw if isinstance(item, dict)],
            "regions": regions,
            "landmarks": landmarks,
            "camera_path": camera_path,
        }
        return spec, warnings

    @classmethod
    def _report(
        cls, spec: dict[str, Any], *, duration: float, warnings: list[str]
    ) -> dict[str, Any]:
        errors: list[str] = []
        warnings = list(warnings)
        regions = spec["regions"]
        landmarks = spec["landmarks"]
        camera_path = spec["camera_path"]

        if not regions:
            errors.append("At least one semantic region is required.")
        region_ids = [region["id"] for region in regions]
        if len(region_ids) != len(set(region_ids)):
            errors.append("Region IDs must be unique.")
        landmark_ids = [landmark["id"] for landmark in landmarks]
        if len(landmark_ids) != len(set(landmark_ids)):
            errors.append("Landmark IDs must be unique.")
        for landmark in landmarks:
            if landmark["region_id"] not in set(region_ids):
                errors.append(
                    f"Landmark {landmark['id']} references unknown region "
                    f"{landmark['region_id']!r}."
                )

        if len(camera_path) < 2:
            errors.append("Camera path requires at least two time keys.")
        else:
            if abs(camera_path[0]["time"]) > 1e-6:
                errors.append("First camera key must start at time 0.")
            if abs(camera_path[-1]["time"] - duration) > 1e-3:
                errors.append(
                    f"Last camera key must end at duration {duration:g} seconds."
                )
            times = [key["time"] for key in camera_path]
            if any(right <= left for left, right in zip(times, times[1:])):
                errors.append("Camera key times must be strictly increasing.")

        size = spec["world"]["size"]
        half = size / 2.0
        for landmark in landmarks:
            x, _, z = landmark["position"]
            if abs(x) > half or abs(z) > half:
                warnings.append(f"Landmark {landmark['id']} is outside world bounds.")

        coverage: dict[str, int] = {region_id: 0 for region_id in region_ids}
        if regions:
            for iz in range(15):
                for ix in range(15):
                    x = (ix / 14.0) * 2.0 - 1.0
                    z = (iz / 14.0) * 2.0 - 1.0
                    weights = cls._region_weights(spec, x, z)
                    winner = max(range(len(weights)), key=weights.__getitem__)
                    coverage[regions[winner]["id"]] += 1
            for region_id, samples in coverage.items():
                if samples == 0:
                    warnings.append(
                        f"Region {region_id} never dominates the sampled semantic layout."
                    )

        min_clearance: float | None = None
        if len(camera_path) >= 2 and regions:
            for sample_index in range(121):
                sample_time = duration * sample_index / 120.0
                position = cls._interpolate_camera(camera_path, sample_time)
                terrain_y = cls._height_at(spec, position[0], position[2])
                clearance = position[1] - terrain_y
                min_clearance = clearance if min_clearance is None else min(min_clearance, clearance)
            if min_clearance is not None and min_clearance < 2.0:
                warnings.append(
                    f"Camera path minimum terrain clearance is {min_clearance:.2f}; "
                    "review for clipping."
                )

        resolution = spec["world"]["resolution"]
        instance_count = sum(sum(region["scatter"].values()) for region in regions)
        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "stats": {
                "region_count": len(regions),
                "landmark_count": len(landmarks),
                "camera_key_count": len(camera_path),
                "terrain_triangles": resolution * resolution * 2,
                "environment_instances": instance_count,
                "semantic_coverage_samples": coverage,
                "minimum_camera_clearance": (
                    round(min_clearance, 3) if min_clearance is not None else None
                ),
            },
            "review_views": ["global", "regional", "walk", "semantic", "wireframe"],
            "diagnostic_passes": {
                "cinematic": "lit beauty render for final review",
                "semantic": "stable region-color pass for layout review",
                "wireframe": "explicit terrain and asset geometry pass",
            },
        }

    @classmethod
    def _region_weights(cls, spec: dict[str, Any], nx: float, nz: float) -> list[float]:
        raw: list[float] = []
        for region in spec["regions"]:
            dx = nx - region["center"][0]
            dz = nz - region["center"][1]
            radius = max(0.05, region["radius"])
            distance = math.sqrt(dx * dx + dz * dz) / radius
            softness = max(0.02, region["blend_width"])
            value = math.exp(-max(0.0, distance - 0.05) ** 2 / (softness * 2.8))
            raw.append(max(1e-5, value))
        total = sum(raw) or 1.0
        return [value / total for value in raw]

    @classmethod
    def _height_at(cls, spec: dict[str, Any], x: float, z: float) -> float:
        size = spec["world"]["size"]
        nx = x / (size / 2.0)
        nz = z / (size / 2.0)
        weights = cls._region_weights(spec, nx, nz)
        seed = spec["seed"] * 0.01337
        elevation = 0.0
        for index, (region, weight) in enumerate(zip(spec["regions"], weights)):
            frequency = region["frequency"]
            noise = (
                math.sin((nx * 3.1 + seed + index) * frequency * math.pi)
                + math.cos((nz * 2.7 - seed * 0.7 + index) * frequency * math.pi)
                + 0.5
                * math.sin((nx + nz) * frequency * 7.3 + seed * 3.0 + index)
            ) / 2.5
            dx = nx - region["center"][0]
            dz = nz - region["center"][1]
            distance = math.sqrt(dx * dx + dz * dz) / max(0.05, region["radius"])
            landform = cls._landform(region["landform"], dx, dz, distance)
            elevation += weight * (
                region["base_elevation"]
                + region["amplitude"] * (noise * 0.48 + landform * 0.8)
            )
        return elevation * spec["world"]["elevation_scale"]

    @staticmethod
    def _landform(kind: str, dx: float, dz: float, distance: float) -> float:
        if kind == "peak":
            return max(0.0, 1.0 - distance) ** 2.2
        if kind == "ridge":
            return max(0.0, 1.0 - abs(dx * 1.8 + math.sin(dz * 5.0) * 0.16))
        if kind == "dune":
            return (math.sin((dx + dz * 0.25) * 18.0) + 1.0) * 0.24
        if kind == "terrace":
            return math.floor(max(0.0, 1.0 - distance) * 5.0) / 5.0
        if kind == "basin":
            return -max(0.0, 1.0 - distance) ** 1.7
        if kind == "canyon":
            return -max(0.0, 1.0 - abs(dx + math.sin(dz * 7.0) * 0.1)) ** 2.0
        return 0.0

    @staticmethod
    def _interpolate_camera(camera_path: list[dict[str, Any]], time_value: float) -> list[float]:
        if time_value <= camera_path[0]["time"]:
            return list(camera_path[0]["position"])
        if time_value >= camera_path[-1]["time"]:
            return list(camera_path[-1]["position"])
        for left, right in zip(camera_path, camera_path[1:]):
            if left["time"] <= time_value <= right["time"]:
                span = max(1e-6, right["time"] - left["time"])
                t = _clamp((time_value - left["time"]) / span, 0.0, 1.0)
                smooth = t * t * (3.0 - 2.0 * t)
                return [
                    left["position"][axis]
                    + (right["position"][axis] - left["position"][axis]) * smooth
                    for axis in range(3)
                ]
        return list(camera_path[-1]["position"])

    @staticmethod
    def _write_workspace(
        *,
        workspace: Path,
        spec: dict[str, Any],
        report: dict[str, Any],
        duration: float,
        width: int,
        height: int,
        render_mode: str,
        quality_tier: str,
        catalog_paths: list[Path],
    ) -> list[str]:
        template_dir = Path(__file__).resolve().parent / "templates" / "threejs_world"
        required = ["index.html", "world.css", "world-runtime.js"]
        missing = [name for name in required if not (template_dir / name).is_file()]
        if missing:
            raise FileNotFoundError(f"Missing Three.js world templates: {', '.join(missing)}")

        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "assets").mkdir(exist_ok=True)
        (workspace / "renders").mkdir(exist_ok=True)

        catalog_index: dict[str, Any] = {"version": "1.0", "catalogs": []}
        model_root = workspace / "assets" / "models"
        model_root.mkdir(parents=True, exist_ok=True)
        for catalog_path in catalog_paths:
            manifest_path = catalog_path / "catalog-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            catalog_id = str(manifest["catalog_id"])
            target = model_root / catalog_id
            source = catalog_path / "source"
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)
            copied = copy.deepcopy(manifest)
            for model in copied.get("models", []):
                original = Path(model["path"])
                relative_inside_source = Path(*original.parts[1:]) if original.parts and original.parts[0] == "source" else original
                model["runtime_path"] = (Path("assets") / "models" / catalog_id / relative_inside_source).as_posix()
            copied.pop("download_url", None)
            catalog_index["catalogs"].append(copied)

        index_template = (template_dir / "index.html").read_text(encoding="utf-8")
        index_html = (
            index_template.replace("__TITLE__", html.escape(spec["title"], quote=True))
            .replace("__DURATION__", f"{duration:g}")
            .replace("__WIDTH__", str(width))
            .replace("__HEIGHT__", str(height))
            .replace("__RENDER_MODE__", render_mode)
            .replace("__QUALITY_TIER__", quality_tier)
        )

        index_path = workspace / "index.html"
        css_path = workspace / "world.css"
        runtime_path = workspace / "world-runtime.js"
        world_json_path = workspace / "world.json"
        world_js_path = workspace / "world-spec.js"
        report_path = workspace / "world-report.json"
        catalog_index_path = workspace / "asset-catalog-index.json"
        catalog_js_path = workspace / "asset-catalog.js"
        config_path = workspace / "hyperframes.json"

        index_path.write_text(index_html, encoding="utf-8")
        shutil.copyfile(template_dir / "world.css", css_path)
        shutil.copyfile(template_dir / "world-runtime.js", runtime_path)
        world_json_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
        world_js_path.write_text(
            "export const WORLD_SPEC = " + json.dumps(spec, indent=2) + ";\n",
            encoding="utf-8",
        )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        catalog_index_path.write_text(json.dumps(catalog_index, indent=2), encoding="utf-8")
        catalog_js_path.write_text(
            "export const ASSET_CATALOG = " + json.dumps(catalog_index, indent=2) + ";\n",
            encoding="utf-8",
        )
        config_path.write_text(
            json.dumps(
                {
                    "registry": (
                        "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry"
                    ),
                    "paths": {
                        "blocks": "compositions",
                        "components": "compositions/components",
                        "assets": "assets",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        return [
            str(index_path),
            str(css_path),
            str(runtime_path),
            str(world_json_path),
            str(world_js_path),
            str(report_path),
            str(catalog_index_path),
            str(catalog_js_path),
            str(config_path),
        ]
