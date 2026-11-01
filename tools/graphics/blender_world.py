"""Deterministic Blender assembly and rendering for production 3D worlds."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
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
    ToolStatus,
    ToolTier,
)


_REPO_ROOT = Path(__file__).resolve().parents[2]
_PORTABLE_BLENDER = (
    _REPO_ROOT / ".runtime" / "blender" / "blender-4.5.10-windows-x64" / "blender.exe"
)
_RUNTIME_SCRIPT = Path(__file__).resolve().parent / "templates" / "blender-world-runtime.py"


def find_blender() -> Path | None:
    configured = os.environ.get("BLENDER_PATH")
    if configured and Path(configured).is_file():
        return Path(configured).resolve()
    if _PORTABLE_BLENDER.is_file():
        return _PORTABLE_BLENDER.resolve()
    discovered = shutil.which("blender")
    return Path(discovered).resolve() if discovered else None


def first_missing_frame(output_prefix: str | Path, start_frame: int, end_frame: int) -> int | None:
    """Return the first missing PNG in a contiguous Blender image sequence."""
    prefix = Path(output_prefix).expanduser().resolve()
    for frame in range(start_frame, end_frame + 1):
        candidate = prefix.parent / f"{prefix.name}{frame:04d}.png"
        if not candidate.is_file():
            return frame
    return None


class BlenderWorld(BaseTool):
    name = "blender_world"
    version = "0.3.0"
    tier = ToolTier.GENERATE
    capability = "3d_world_rendering"
    provider = "blender"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU
    dependencies: list[str] = []
    install_instructions = (
        "Install Blender 4.5 LTS, set BLENDER_PATH, or place the portable runtime at "
        ".runtime/blender/blender-4.5.10-windows-x64/blender.exe."
    )
    agent_skills = [
        "3d-asset-generation", "threejs-world-generation", "threejs-loaders", "threejs-materials",
        "threejs-textures", "threejs-lighting", "threejs-postprocessing",
    ]
    capabilities = [
        "gltf_glb_scene_assembly", "procedural_terrain", "linked_asset_scatter",
        "pbr_materials", "eevee_next_render", "camera_flythrough", "blend_project_export",
        "asset_unit_normalization", "bounding_box_ground_contact", "semantic_scatter_exclusions",
        "terrain_following_ribbons", "visibility_windows", "title_safe_final_hold",
    ]
    supports = {
        "glb": True,
        "gltf": True,
        "pbr": True,
        "linked_instances": True,
        "still": True,
        "animation": True,
        "transparent_background": True,
    }
    best_for = [
        "Production-quality world assembly from many generated and licensed assets",
        "Dense terrain, lighting, material, camera, and contact-shadow work",
        "Rendering a final image sequence for governed video composition",
    ]
    not_good_for = ["Interactive browser delivery", "Text-to-mesh generation"]
    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {"type": "string", "enum": ["doctor", "build", "render_still", "render_animation"]},
            "world_spec": {"type": "object"},
            "output_path": {"type": "string"},
            "blend_path": {"type": "string"},
            "width": {"type": "integer", "minimum": 320, "maximum": 7680, "default": 1920},
            "height": {"type": "integer", "minimum": 240, "maximum": 4320, "default": 1080},
            "samples": {"type": "integer", "minimum": 1, "maximum": 256, "default": 32},
            "fps": {"type": "integer", "minimum": 1, "maximum": 120, "default": 30},
            "duration_seconds": {"type": "number", "minimum": 1, "maximum": 600, "default": 60},
            "start_frame": {"type": "integer", "minimum": 1},
            "end_frame": {"type": "integer", "minimum": 1},
            "frame": {"type": "integer", "minimum": 1},
            "resume": {"type": "boolean", "default": False},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"artifact": "3d_world"}
    resource_profile = ResourceProfile(cpu_cores=8, ram_mb=8192, vram_mb=6000, disk_mb=20000)
    idempotency_key_fields = ["operation", "world_spec", "width", "height", "samples", "fps", "duration_seconds"]
    side_effects = ["writes a .blend project", "may render an image or PNG sequence"]
    user_visible_verification = [
        "Review global, regional, and walk-height stills before an animation render",
        "Check imported mesh scale, ground contact, texture color space, shadowing, and camera clearance",
    ]
    quality_score = 0.94

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if find_blender() and _RUNTIME_SCRIPT.is_file() else ToolStatus.UNAVAILABLE

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        if inputs.get("operation") == "render_animation":
            return float(inputs.get("duration_seconds", 60)) * float(inputs.get("fps", 30)) * 2.0
        return 30.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        blender = find_blender()
        if not blender:
            return ToolResult(success=False, error="Blender not found. " + self.install_instructions)
        operation = str(inputs.get("operation") or "")
        if operation == "doctor":
            process = subprocess.run(
                [str(blender), "--background", "--python-expr", "import bpy; print('OPENMONTAGE_BLENDER=' + bpy.app.version_string)"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60,
            )
            ok = process.returncode == 0 and "OPENMONTAGE_BLENDER=" in process.stdout
            return ToolResult(
                success=ok,
                data={"blender_path": str(blender), "version_line": next((line for line in process.stdout.splitlines() if line.startswith("OPENMONTAGE_BLENDER=")), "")},
                error=None if ok else (process.stderr or process.stdout)[-1000:],
                model="blender-4.5-lts",
            )

        if operation not in {"build", "render_still", "render_animation"}:
            return ToolResult(success=False, error=f"Unknown operation: {operation}")
        if not isinstance(inputs.get("world_spec"), dict):
            return ToolResult(success=False, error="world_spec is required")
        output_raw = inputs.get("output_path")
        if operation != "build" and not output_raw:
            return ToolResult(success=False, error="output_path is required for rendering")
        blend_raw = inputs.get("blend_path") or (
            str(Path(str(output_raw)).with_suffix(".blend")) if output_raw else "blender-world.blend"
        )
        blend_path = Path(str(blend_raw)).expanduser().resolve()
        blend_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path = blend_path.with_suffix(".world.json")
        spec_path.write_text(json.dumps(inputs["world_spec"], indent=2), encoding="utf-8")

        command = [
            str(blender), "--background", "--python", str(_RUNTIME_SCRIPT), "--",
            "--operation", operation,
            "--spec", str(spec_path),
            "--blend", str(blend_path),
            "--width", str(int(inputs.get("width", 1920))),
            "--height", str(int(inputs.get("height", 1080))),
            "--samples", str(int(inputs.get("samples", 32))),
            "--fps", str(int(inputs.get("fps", 30))),
            "--duration", str(float(inputs.get("duration_seconds", 60))),
        ]
        requested_start = int(inputs.get("start_frame", 1))
        requested_end = int(inputs.get("end_frame") or round(
            float(inputs.get("duration_seconds", 60)) * int(inputs.get("fps", 30))
        ))
        effective_start = requested_start
        if operation == "render_animation" and inputs.get("resume"):
            if not output_raw:
                return ToolResult(success=False, error="output_path is required to resume a render")
            missing = first_missing_frame(output_raw, requested_start, requested_end)
            if missing is None:
                return ToolResult(
                    success=True,
                    data={
                        "blender_path": str(blender),
                        "blend_path": str(blend_path),
                        "output": str(output_raw),
                        "already_complete": True,
                        "start_frame": requested_start,
                        "end_frame": requested_end,
                    },
                    model="blender-4.5-lts-eevee-next",
                )
            effective_start = missing
        if inputs.get("start_frame") is not None or operation == "render_animation":
            command.extend(["--start-frame", str(effective_start)])
        if inputs.get("end_frame") is not None or operation == "render_animation":
            command.extend(["--end-frame", str(requested_end)])
        if inputs.get("frame") is not None:
            command.extend(["--frame", str(int(inputs["frame"]))])
        if output_raw:
            command.extend(["--output", str(Path(str(output_raw)).expanduser().resolve())])

        started = time.time()
        try:
            process = subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                timeout=max(120, int(self.estimate_runtime(inputs) * 2.5)),
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Blender invocation failed: {exc}")
        if process.returncode != 0:
            return ToolResult(success=False, error="Blender world build failed: " + (process.stderr or process.stdout)[-3000:])

        artifacts = [str(spec_path), str(blend_path)]
        if output_raw:
            output = Path(str(output_raw)).expanduser().resolve()
            if output.exists():
                artifacts.append(str(output))
        report_path = blend_path.with_suffix(".report.json")
        if report_path.exists():
            artifacts.append(str(report_path))
        return ToolResult(
            success=True,
            data={
                "blender_path": str(blender),
                "blend_path": str(blend_path),
                "output": str(output_raw or ""),
                "report": str(report_path),
                "start_frame": effective_start if operation == "render_animation" else None,
                "end_frame": requested_end if operation == "render_animation" else None,
                "resumed": bool(operation == "render_animation" and inputs.get("resume") and effective_start > requested_start),
            },
            artifacts=artifacts,
            duration_seconds=round(time.time() - started, 2),
            seed=inputs["world_spec"].get("seed"),
            model="blender-4.5-lts-eevee-next",
        )
