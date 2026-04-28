"""Local character-animation contract tools.

These tools provide deterministic artifact generation and validation for the
character-animation pipeline. They intentionally keep creative orchestration in
skills and manifests; Python only creates structured artifacts and lightweight
preview/review outputs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from schemas.artifacts import validate_artifact
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolStability,
    ToolTier,
)


def _write_json(path: str | None, data: dict[str, Any]) -> list[str]:
    if not path:
        return []
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return [str(out)]


def _slug(value: str) -> str:
    chars = [c.lower() if c.isalnum() else "-" for c in value.strip()]
    return "-".join("".join(chars).split("-")).strip("-") or "character"


def _character_color(index: int) -> tuple[str, str]:
    palettes = [
        ("#ff8f68", "#ffd39f"),
        ("#75b8ff", "#ffe7a3"),
        ("#8fd17f", "#f7c8ff"),
        ("#f2c94c", "#fce6c9"),
    ]
    return palettes[index % len(palettes)]


def _normalize_style(style: Any) -> dict[str, Any]:
    if not isinstance(style, dict):
        return {}
    normalized: dict[str, Any] = {}
    visual_style = style.get("visual_style") or style.get("name") or style.get("style")
    if visual_style:
        normalized["visual_style"] = str(visual_style)
    palette = style.get("palette")
    if isinstance(palette, list):
        normalized["palette"] = [str(color) for color in palette]
    for key in ["line_style", "texture"]:
        if style.get(key):
            normalized[key] = str(style[key])
    return normalized


def _render_preview_mp4(preview_path: Path, video_path: Path, duration_seconds: float, fps: int) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg is required to render preview MP4")
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - dependency-specific branch
        raise RuntimeError("Playwright is required to render preview MP4") from exc

    frame_dir = video_path.parent / f"{video_path.stem}_frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_count = max(2, int(duration_seconds * fps))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(preview_path.resolve().as_uri(), wait_until="networkidle")
        for frame in range(frame_count):
            if frame:
                page.wait_for_timeout(int(1000 / fps))
            page.screenshot(path=str(frame_dir / f"frame_{frame:04d}.png"))
        browser.close()

    cmd = [
        "ffmpeg",
        "-y",
        "-framerate",
        str(fps),
        "-i",
        str(frame_dir / "frame_%04d.png"),
        "-r",
        str(fps),
        "-pix_fmt",
        "yuv420p",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg failed to render preview MP4")


class CharacterSpecGenerator(BaseTool):
    name = "character_spec_generator"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "character_animation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)
    agent_skills = ["character-rigging", "pose-library-design"]
    capabilities = ["draft_character_design", "normalize_character_specs"]
    best_for = ["Converting approved concepts into structured character_design artifacts"]
    not_good_for = ["Generating artwork pixels or finished animation"]
    input_schema = {
        "type": "object",
        "properties": {
            "characters": {"type": "array"},
            "brief": {"type": "string"},
            "style": {"type": "object"},
            "output_path": {"type": "string"},
        },
    }
    output_schema = {"type": "object", "properties": {"character_design": {"type": "object"}}}
    artifact_schema = {"artifact": "character_design"}
    side_effects = ["optionally writes character_design JSON to output_path"]
    user_visible_verification = ["Review character count, action list, and emotional range"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        raw_characters = inputs.get("characters") or [
            {
                "id": "main_character",
                "role": "lead character",
                "body_type": "simple rounded cartoon character",
                "style": "local rigged cartoon",
                "required_emotions": ["neutral", "curious", "happy", "surprised"],
                "required_actions": ["idle", "blink", "look", "gesture"],
            }
        ]
        characters: list[dict[str, Any]] = []
        for raw in raw_characters:
            name = raw.get("id") or raw.get("name") or raw.get("display_name") or "character"
            characters.append(
                {
                    "id": _slug(str(name)),
                    "display_name": raw.get("display_name", str(name).replace("_", " ").title()),
                    "role": raw.get("role", "supporting character"),
                    "body_type": raw.get("body_type", "simple cartoon body"),
                    "style": raw.get("style", inputs.get("style", {}).get("visual_style", "cartoon")),
                    "silhouette_notes": raw.get("silhouette_notes", ""),
                    "required_emotions": raw.get("required_emotions", ["neutral", "happy", "surprised"]),
                    "required_actions": raw.get("required_actions", ["idle", "blink", "look"]),
                    "required_views": raw.get("required_views", ["front", "side"]),
                    "props": raw.get("props", []),
                    "constraints": raw.get("constraints", []),
                }
            )
        artifact = {
            "version": "1.0",
            "style": _normalize_style(inputs.get("style", {})),
            "characters": characters,
            "metadata": {
                "source": "character_spec_generator",
                "brief": inputs.get("brief", ""),
            },
        }
        artifacts = _write_json(inputs.get("output_path"), artifact)
        return ToolResult(
            success=True,
            data={"character_design": artifact},
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
        )


class SvgRigBuilder(BaseTool):
    name = "svg_rig_builder"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "character_animation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)
    agent_skills = ["character-rigging", "svg-character-animation", "gsap-core", "gsap-timeline"]
    capabilities = ["draft_svg_rig_plan", "define_parts_pivots_layers"]
    input_schema = {
        "type": "object",
        "required": ["character_design"],
        "properties": {
            "character_design": {"type": "object"},
            "output_path": {"type": "string"},
        },
    }
    artifact_schema = {"artifact": "rig_plan"}
    side_effects = ["optionally writes rig_plan JSON to output_path"]
    user_visible_verification = ["Check pivots and layers before asset generation"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        design = inputs["character_design"]
        rig_characters: list[dict[str, Any]] = []
        for character in design.get("characters", []):
            cid = character["id"]
            actions = character.get("required_actions", [])
            base_parts = [
                ("body", "torso", 20, None, [320, 380]),
                ("head", "head", 40, "body", [320, 220]),
                ("eye_left", "eye", 50, "head", [288, 210]),
                ("eye_right", "eye", 50, "head", [352, 210]),
                ("pupil_left", "pupil", 51, "eye_left", [288, 210]),
                ("pupil_right", "pupil", 51, "eye_right", [352, 210]),
                ("mouth", "mouth", 52, "head", [320, 260]),
                ("arm_left", "limb", 35, "body", [260, 330]),
                ("arm_right", "limb", 35, "body", [380, 330]),
                ("leg_left", "limb", 10, "body", [285, 470]),
                ("leg_right", "limb", 10, "body", [355, 470]),
            ]
            if "tail" in character.get("body_type", "").lower() or "mouse" in cid:
                base_parts.append(("tail", "tail", 5, "body", [245, 425]))
            if any("wing" in a for a in actions) or "bird" in cid:
                base_parts.extend(
                    [
                        ("wing_left", "wing", 30, "body", [275, 330]),
                        ("wing_right", "wing", 30, "body", [365, 330]),
                    ]
                )
            parts = [
                {
                    "id": part_id,
                    "kind": kind,
                    "layer": layer,
                    **({"parent": parent} if parent else {}),
                }
                for part_id, kind, layer, parent, _ in base_parts
            ]
            joints = {
                part_id: {
                    "pivot": pivot,
                    "rotation": [-35, 35] if kind in {"head", "tail"} else [-75, 95],
                    "scale": [0.8, 1.2],
                }
                for part_id, kind, _, _, pivot in base_parts
            }
            required_poses = sorted(
                set(["idle", "blink", "look_left", "look_right", "surprised"] + actions)
            )
            rig_characters.append(
                {
                    "character_id": cid,
                    "rig_type": "svg_rig",
                    "parts": parts,
                    "joints": joints,
                    "layers": [p["id"] for p in sorted(parts, key=lambda p: p["layer"])],
                    "views": character.get("required_views", ["front", "side"]),
                    "required_poses": required_poses,
                    "required_actions": actions,
                    "risks": [
                        "Generated pivots are first-pass estimates; review with preview frames.",
                    ],
                }
            )
        artifact = {"version": "1.0", "characters": rig_characters, "metadata": {"source": self.name}}
        artifacts = _write_json(inputs.get("output_path"), artifact)
        return ToolResult(
            success=True,
            data={"rig_plan": artifact},
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
        )


class PoseLibraryBuilder(BaseTool):
    name = "pose_library_builder"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "character_animation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)
    agent_skills = ["pose-library-design", "character-rigging", "svg-character-animation"]
    capabilities = ["draft_pose_library", "draft_action_cycles"]
    input_schema = {
        "type": "object",
        "required": ["rig_plan"],
        "properties": {"rig_plan": {"type": "object"}, "output_path": {"type": "string"}},
    }
    artifact_schema = {"artifact": "pose_library"}
    side_effects = ["optionally writes pose_library JSON to output_path"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        characters = []
        for rig in inputs["rig_plan"].get("characters", []):
            cid = rig["character_id"]
            poses = {
                "idle": {"description": "Neutral readable hold", "parts": {}, "hold_frames": 24},
                "blink": {
                    "description": "Quick eye close/open",
                    "parts": {"eye_left": {"scaleY": 0.08}, "eye_right": {"scaleY": 0.08}},
                    "hold_frames": 3,
                    "transition": "power1.inOut",
                },
                "look_left": {
                    "description": "Gaze shifts left",
                    "parts": {"pupil_left": {"x": -6}, "pupil_right": {"x": -6}},
                    "hold_frames": 18,
                },
                "look_right": {
                    "description": "Gaze shifts right",
                    "parts": {"pupil_left": {"x": 6}, "pupil_right": {"x": 6}},
                    "hold_frames": 18,
                },
                "surprised": {
                    "description": "Head lifts, eyes widen, mouth opens",
                    "parts": {"head": {"y": -4, "rotation": -4}, "mouth": {"shape": "small_o"}},
                    "expression": "surprised",
                    "hold_frames": 24,
                    "transition": "back.out",
                },
            }
            for action in rig.get("required_actions", []):
                poses.setdefault(
                    action,
                    {
                        "description": f"First-pass pose for {action}",
                        "parts": {},
                        "hold_frames": 18,
                        "transition": "power2.inOut",
                    },
                )
            characters.append(
                {
                    "character_id": cid,
                    "poses": poses,
                    "mouth_shapes": {
                        "closed": {"description": "Neutral closed mouth"},
                        "small_o": {"description": "Small open mouth for surprise or vowel"},
                        "wide": {"description": "Wide open mouth"},
                        "smile": {"description": "Smile shape"},
                    },
                    "action_cycles": {
                        "walk": ["walk_contact", "walk_passing"],
                        "breathe": ["idle"],
                    },
                }
            )
        artifact = {"version": "1.0", "characters": characters, "metadata": {"source": self.name}}
        artifacts = _write_json(inputs.get("output_path"), artifact)
        return ToolResult(
            success=True,
            data={"pose_library": artifact},
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
        )


class ActionTimelineCompiler(BaseTool):
    name = "action_timeline_compiler"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "character_animation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)
    agent_skills = ["pose-library-design", "svg-character-animation", "gsap-timeline"]
    capabilities = ["compile_scene_actions", "draft_action_timeline"]
    input_schema = {
        "type": "object",
        "required": ["scene_plan"],
        "properties": {
            "scene_plan": {"type": "object"},
            "character_ids": {"type": "array", "items": {"type": "string"}},
            "fps": {"type": "number"},
            "output_path": {"type": "string"},
        },
    }
    artifact_schema = {"artifact": "action_timeline"}
    side_effects = ["optionally writes action_timeline JSON to output_path"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        character_ids = inputs.get("character_ids") or ["main_character"]
        scenes = []
        for scene in inputs["scene_plan"].get("scenes", []):
            start_s = scene.get("start_seconds", 0)
            end_s = scene.get("end_seconds", start_s + 3)
            duration = max(0.1, end_s - start_s)
            actions = []
            for index, character_id in enumerate(character_ids):
                offset = min(duration * 0.08 * index, duration * 0.2)
                is_primary = index == 0
                actions.extend(
                    [
                        {
                            "at_seconds": start_s + offset,
                            "duration_seconds": min(0.5, duration / 4),
                            "character_id": character_id,
                            "action": "anticipate" if is_primary else "react",
                            "pose": "idle",
                            "easing": "power2.out",
                        },
                        {
                            "at_seconds": start_s + duration * 0.25 + offset,
                            "duration_seconds": duration * 0.35,
                            "character_id": character_id,
                            "action": "perform" if is_primary else "follow",
                            "pose": (
                                "surprised"
                                if scene.get("hero_moment") or not is_primary
                                else "look_right"
                            ),
                            "easing": "back.out",
                            "notes": scene.get("description", ""),
                        },
                        {
                            "at_seconds": start_s + duration * 0.7 + offset,
                            "duration_seconds": duration * 0.25,
                            "character_id": character_id,
                            "action": "settle",
                            "pose": "idle",
                            "easing": "power2.inOut",
                        },
                    ]
                )
            scenes.append(
                {
                    "scene_id": scene["id"],
                    "start_seconds": start_s,
                    "end_seconds": end_s,
                    "camera": {"framing": scene.get("framing", "medium")},
                    "background": scene.get("description", ""),
                    "effects": [],
                    "actions": actions,
                }
            )
        artifact = {
            "version": "1.0",
            "fps": inputs.get("fps", 30),
            "scenes": scenes,
            "metadata": {"source": self.name},
        }
        artifacts = _write_json(inputs.get("output_path"), artifact)
        return ToolResult(
            success=True,
            data={"action_timeline": artifact},
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
        )


class CharacterRigRenderer(BaseTool):
    name = "character_rig_renderer"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "character_animation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=50)
    agent_skills = [
        "character-rigging",
        "svg-character-animation",
        "canvas-procedural-animation",
        "gsap-core",
        "gsap-timeline",
        "remotion-best-practices",
        "hyperframes",
    ]
    capabilities = ["write_browser_preview", "prepare_character_render_package"]
    input_schema = {
        "type": "object",
        "required": ["action_timeline"],
        "properties": {
            "action_timeline": {"type": "object"},
            "rig_plan": {"type": "object"},
            "pose_library": {"type": "object"},
            "output_path": {"type": "string"},
            "workspace_path": {"type": "string"},
            "video_output_path": {"type": "string"},
            "render_video": {"type": "boolean", "default": False},
            "duration_seconds": {"type": "number", "minimum": 0.1, "default": 3},
            "fps": {"type": "integer", "minimum": 1, "default": 12},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "preview_path": {"type": "string"},
            "hyperframes_workspace": {"type": "string"},
            "composition_path": {"type": "string"},
            "video_path": {"type": "string"},
            "asset_manifest": {"type": "object"},
            "edit_decisions": {"type": "object"},
        },
    }
    side_effects = [
        "writes a lightweight HTML preview to output_path",
        "writes a HyperFrames workspace/package",
        "optionally writes preview MP4",
    ]
    user_visible_verification = ["Open preview and check character visibility and motion"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        output_path = Path(inputs.get("output_path", "projects/character-preview/preview.html"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        timeline_json = json.dumps(inputs["action_timeline"])
        rig_characters = (inputs.get("rig_plan") or {}).get("characters", [])
        if not rig_characters:
            seen_ids = {
                action.get("character_id")
                for scene in inputs["action_timeline"].get("scenes", [])
                for action in scene.get("actions", [])
                if action.get("character_id")
            }
            rig_characters = [{"character_id": cid} for cid in sorted(seen_ids)] or [
                {"character_id": "main_character"}
            ]
        count = len(rig_characters)
        spacing = 620 / max(count, 1)
        character_svgs = []
        for index, character in enumerate(rig_characters):
            cid = _slug(character.get("character_id", f"character-{index + 1}"))
            x = 110 + spacing * index if count > 1 else 320
            scale = 0.82 if count > 1 else 1
            body_fill, head_fill = _character_color(index)
            character_svgs.append(
                f"""
      <g class=\"character\" id=\"character_{cid}\" data-character=\"{cid}\" transform=\"translate({x - 320:.1f} 0) scale({scale})\">
        <ellipse class=\"shadow\" cx=\"320\" cy=\"560\" rx=\"120\" ry=\"22\" fill=\"rgba(0,0,0,.18)\" />
        <ellipse class=\"body outline\" cx=\"320\" cy=\"400\" rx=\"80\" ry=\"120\" fill=\"{body_fill}\" />
        <circle class=\"head outline\" cx=\"320\" cy=\"230\" r=\"90\" fill=\"{head_fill}\" />
        <ellipse class=\"eye eye-left outline\" cx=\"285\" cy=\"215\" rx=\"18\" ry=\"26\" fill=\"white\" />
        <ellipse class=\"eye eye-right outline\" cx=\"355\" cy=\"215\" rx=\"18\" ry=\"26\" fill=\"white\" />
        <circle class=\"pupil pupil-left\" cx=\"289\" cy=\"218\" r=\"8\" fill=\"#202632\" />
        <circle class=\"pupil pupil-right\" cx=\"359\" cy=\"218\" r=\"8\" fill=\"#202632\" />
        <path class=\"mouth outline\" d=\"M285 275 Q320 305 355 275\" fill=\"none\" />
        <path class=\"arm arm-left outline\" d=\"M255 360 C210 380 190 420 180 455\" fill=\"none\" />
        <path class=\"arm arm-right outline\" d=\"M385 360 C440 330 465 290 475 240\" fill=\"none\" />
      </g>"""
            )
        html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Character Animation Preview</title>
  <script src=\"https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js\"></script>
  <style>
    body {{ margin: 0; overflow: hidden; background: #9bd7ff; font-family: system-ui, sans-serif; }}
    #stage {{ width: 100vw; height: 100vh; display: grid; place-items: center; background: linear-gradient(#9bd7ff 0 65%, #75c878 65%); }}
    svg {{ width: min(82vw, 720px); overflow: visible; }}
    .outline {{ stroke: #202632; stroke-width: 7; stroke-linecap: round; stroke-linejoin: round; }}
    #note {{ position: fixed; left: 16px; bottom: 16px; background: white; border: 2px solid #202632; padding: 10px 12px; border-radius: 8px; }}
  </style>
</head>
<body>
  <div id=\"stage\">
    <svg viewBox=\"0 0 640 640\" role=\"img\" aria-label=\"Character preview\">
{''.join(character_svgs)}
    </svg>
  </div>
  <div id=\"note\">Local character preview. Characters: <span id=\"characters\"></span> · Scenes: <span id=\"count\"></span></div>
  <script>
    window.__ACTION_TIMELINE__ = {timeline_json};
    document.querySelector('#count').textContent = window.__ACTION_TIMELINE__.scenes.length;
    const characters = gsap.utils.toArray('.character');
    document.querySelector('#characters').textContent = characters.map((node) => node.dataset.character).join(', ');
    characters.forEach((node, index) => {{
      const q = gsap.utils.selector(node);
      gsap.set(q('.head'), {{ svgOrigin: '320 320' }});
      gsap.set(q('.arm-right'), {{ svgOrigin: '385 360' }});
      gsap.set(q('.arm-left'), {{ svgOrigin: '255 360' }});
      gsap.timeline({{ repeat: -1, defaults: {{ ease: 'power2.inOut' }}, delay: index * 0.12 }})
        .to(node, {{ y: -16, duration: 0.45 }})
        .to(node, {{ y: 0, duration: 0.45 }});
      gsap.timeline({{ repeat: -1, repeatDelay: 0.5, delay: index * 0.18 }})
        .to(q('.head'), {{ rotation: index % 2 ? 8 : -8, duration: 0.35 }})
        .to(q('.pupil'), {{ x: index % 2 ? -8 : 8, y: -3, duration: 0.2 }}, '<')
        .to(q('.arm-right'), {{ rotation: index % 2 ? -22 : 28, duration: 0.35 }}, '<')
        .to(q('.eye'), {{ scaleY: 0.08, transformOrigin: 'center', duration: 0.08 }})
        .to(q('.eye'), {{ scaleY: 1, duration: 0.1 }})
        .to(q('.head'), {{ rotation: index % 2 ? -6 : 6, duration: 0.35 }})
        .to(q('.pupil'), {{ x: index % 2 ? 6 : -6, y: 3, duration: 0.2 }}, '<')
        .to(q('.arm-right'), {{ rotation: index % 2 ? 8 : -8, duration: 0.35 }}, '<');
    }});
        </script>
</body>
</html>
"""
        output_path.write_text(html, encoding="utf-8")
        total_duration = max(
            [
                float(scene.get("end_seconds", 0) or 0)
                for scene in inputs["action_timeline"].get("scenes", [])
            ]
            or [float(inputs.get("duration_seconds", 3))]
        )
        workspace_path = Path(
            inputs.get("workspace_path")
            or output_path.parent / "hyperframes"
        )
        composition_dir = workspace_path / "compositions"
        composition_dir.mkdir(parents=True, exist_ok=True)
        (workspace_path / "assets").mkdir(parents=True, exist_ok=True)
        (workspace_path / "hyperframes.json").write_text(
            json.dumps(
                {
                    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
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
        (workspace_path / "DESIGN.md").write_text(
            "# DESIGN\n\n"
            "Generated for OpenMontage character animation.\n\n"
            "- Background: `#9bd7ff` sky and `#75c878` ground\n"
            "- Foreground: `#202632` ink outlines\n"
            "- Accent: saturated cartoon body colors\n"
            "- Motion: GSAP pose holds, squash/bounce, gaze, blink, and arm arcs\n",
            encoding="utf-8",
        )
        finite_bounce_repeats = max(0, int(total_duration / 0.9) - 1)
        finite_acting_repeats = max(0, int(total_duration / 2.1) - 1)
        composition_html = f"""<template id=\"character-scene-template\">
  <div data-composition-id=\"character-scene\" data-start=\"0\" data-duration=\"{total_duration:.3f}\" data-width=\"1280\" data-height=\"720\">
    <style>
      [data-composition-id=\"character-scene\"] {{ position: relative; width: 1280px; height: 720px; overflow: hidden; background: linear-gradient(#9bd7ff 0 65%, #75c878 65%); }}
      [data-composition-id=\"character-scene\"] svg {{ width: 920px; position: absolute; left: 180px; top: 42px; overflow: visible; }}
      [data-composition-id=\"character-scene\"] .outline {{ stroke: #202632; stroke-width: 7; stroke-linecap: round; stroke-linejoin: round; }}
    </style>
    <svg viewBox=\"0 0 640 640\" role=\"img\" aria-label=\"Character animation scene\">
{''.join(character_svgs)}
    </svg>
    <script src=\"https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js\"></script>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      const characters = gsap.utils.toArray('[data-composition-id=\"character-scene\"] .character');
      characters.forEach((node, index) => {{
        const q = gsap.utils.selector(node);
        tl.set(q('.head'), {{ svgOrigin: '320 320' }}, 0);
        tl.set(q('.arm-right'), {{ svgOrigin: '385 360' }}, 0);
        tl.set(q('.arm-left'), {{ svgOrigin: '255 360' }}, 0);
        tl.from(node, {{ y: 26, scale: 0.94, opacity: 0, duration: 0.45, ease: 'back.out(1.8)' }}, 0.15 + index * 0.12);
        tl.to(node, {{ y: -16, duration: 0.45, repeat: {finite_bounce_repeats}, yoyo: true, ease: 'power2.inOut' }}, 0.7 + index * 0.08);
        tl.to(q('.head'), {{ rotation: index % 2 ? 8 : -8, duration: 0.35, repeat: {finite_acting_repeats}, yoyo: true, ease: 'sine.inOut' }}, 0.55 + index * 0.16);
        tl.to(q('.pupil'), {{ x: index % 2 ? -8 : 8, y: -3, duration: 0.2, repeat: {finite_acting_repeats}, yoyo: true, ease: 'power2.inOut' }}, 0.6 + index * 0.16);
        tl.to(q('.arm-right'), {{ rotation: index % 2 ? -22 : 28, duration: 0.35, repeat: {finite_acting_repeats}, yoyo: true, ease: 'back.inOut(1.4)' }}, 0.65 + index * 0.16);
        tl.to(q('.eye'), {{ scaleY: 0.08, transformOrigin: 'center', duration: 0.08, repeat: {finite_acting_repeats}, repeatDelay: 1.4, yoyo: true, ease: 'power1.inOut' }}, 1.1 + index * 0.12);
      }});
      window.__timelines['character-scene'] = tl;
    </script>
  </div>
</template>
"""
        composition_path = composition_dir / "character-scene.html"
        composition_path.write_text(composition_html, encoding="utf-8")
        asset_id = "character_scene_hyperframes"
        asset_manifest = {
            "version": "1.0",
            "assets": [
                {
                    "id": asset_id,
                    "type": "animation",
                    "path": str(composition_path),
                    "source_tool": self.name,
                    "scene_id": "character_preview",
                    "duration_seconds": total_duration,
                    "format": "html",
                    "generation_summary": "HyperFrames SVG/GSAP character composition package.",
                }
            ],
            "total_cost_usd": 0,
            "metadata": {"source": self.name, "workspace_path": str(workspace_path)},
        }
        edit_decisions = {
            "version": "1.0",
            "render_runtime": "hyperframes",
            "renderer_family": "animation-first",
            "cuts": [
                {
                    "id": "character-scene",
                    "source": asset_id,
                    "in_seconds": 0,
                    "out_seconds": total_duration,
                    "reason": "HyperFrames SVG/GSAP character scene generated by character_rig_renderer.",
                }
            ],
            "metadata": {
                "proposal_render_runtime": "hyperframes",
                "title": "Character Animation",
            },
        }
        data: dict[str, Any] = {
            "preview_path": str(output_path),
            "render_package": "hyperframes_workspace",
            "hyperframes_workspace": str(workspace_path),
            "composition_path": str(composition_path),
            "asset_manifest": asset_manifest,
            "edit_decisions": edit_decisions,
        }
        artifacts = [str(output_path), str(workspace_path / "hyperframes.json"), str(composition_path)]
        render_video = bool(inputs.get("render_video") or inputs.get("video_output_path"))
        if render_video:
            video_path = Path(
                inputs.get("video_output_path")
                or output_path.with_suffix(".mp4")
            )
            video_path.parent.mkdir(parents=True, exist_ok=True)
            duration_seconds = float(inputs.get("duration_seconds", 3))
            fps = int(inputs.get("fps", 12))
            _render_preview_mp4(output_path, video_path, duration_seconds, fps)
            video_asset_id = f"{output_path.stem}_preview_video"
            video_asset_manifest = {
                "version": "1.0",
                "assets": [
                    {
                        "id": video_asset_id,
                        "type": "video",
                        "path": str(video_path),
                        "source_tool": self.name,
                        "scene_id": "character_preview",
                        "duration_seconds": duration_seconds,
                        "format": "mp4",
                        "generation_summary": "Rendered from local SVG/GSAP character preview via Playwright frame capture and ffmpeg.",
                    }
                ],
                "total_cost_usd": 0,
                "metadata": {"source": self.name, "preview_path": str(output_path)},
            }
            video_edit_decisions = {
                "version": "1.0",
                "render_runtime": "ffmpeg",
                "renderer_family": "animation-first",
                "cuts": [
                    {
                        "id": "character-preview-cut",
                        "source": video_asset_id,
                        "in_seconds": 0,
                        "out_seconds": duration_seconds,
                        "reason": "Local rendered character preview for video_compose handoff.",
                    }
                ],
                "metadata": {
                    "proposal_render_runtime": "ffmpeg",
                    "character_preview_path": str(output_path),
                },
            }
            data.update(
                {
                    "video_path": str(video_path),
                    "video_asset_manifest": video_asset_manifest,
                    "video_edit_decisions": video_edit_decisions,
                }
            )
            artifacts.append(str(video_path))
        return ToolResult(
            success=True,
            data=data,
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
        )


class CharacterAnimationReviewer(BaseTool):
    name = "character_animation_reviewer"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "character_animation"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=128, vram_mb=0, disk_mb=10)
    agent_skills = ["character-animation-qa"]
    capabilities = ["review_character_artifacts", "draft_character_qa_report"]
    input_schema = {
        "type": "object",
        "properties": {
            "rig_plan": {"type": "object"},
            "pose_library": {"type": "object"},
            "action_timeline": {"type": "object"},
            "preview_path": {"type": "string"},
            "review_level": {"type": "string", "enum": ["static", "browser", "final"], "default": "static"},
            "browser_preview_checked": {"type": "boolean", "default": False},
            "frame_samples_checked": {"type": "boolean", "default": False},
            "output_path": {"type": "string"},
        },
    }
    artifact_schema = {"artifact": "character_qa_report"}
    side_effects = ["optionally writes character_qa_report JSON to output_path"]

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        issues: list[str] = []
        rig = inputs.get("rig_plan") or {}
        poses = inputs.get("pose_library") or {}
        timeline = inputs.get("action_timeline") or {}
        preview_path = inputs.get("preview_path")
        review_level = inputs.get("review_level", "static")
        browser_preview_checked = bool(inputs.get("browser_preview_checked", False))
        frame_samples_checked = bool(inputs.get("frame_samples_checked", False))
        assets_exist = True
        if not preview_path:
            assets_exist = False
            issues.append("Preview path is required for character animation QA.")
        elif not Path(preview_path).exists():
            assets_exist = False
            issues.append(f"Preview path does not exist: {preview_path}")
        pivots_defined = all(
            bool(character.get("joints"))
            for character in rig.get("characters", [])
        ) if rig else False
        poses_defined = all(
            bool(character.get("poses"))
            for character in poses.get("characters", [])
        ) if poses else False
        actions_timed = all(
            bool(scene.get("actions"))
            for scene in timeline.get("scenes", [])
        ) if timeline else False
        if not pivots_defined:
            issues.append("Rig plan is missing joints/pivots for one or more characters.")
        if not poses_defined:
            issues.append("Pose library is missing poses for one or more characters.")
        if not actions_timed:
            issues.append("Action timeline has scenes without timed actions.")
        schema_valid = True
        for artifact_name, artifact in [
            ("rig_plan", rig),
            ("pose_library", poses),
            ("action_timeline", timeline),
        ]:
            if not artifact:
                continue
            try:
                validate_artifact(artifact_name, artifact)
            except Exception as exc:
                schema_valid = False
                issues.append(f"{artifact_name} schema validation failed: {exc}")
        if review_level in {"browser", "final"} and not browser_preview_checked:
            issues.append("Browser preview check is required for browser/final QA.")
        if review_level == "final" and not frame_samples_checked:
            issues.append("Frame sample check is required for final QA.")
        status = "pass" if not issues else "revise"
        report = {
            "version": "1.0",
            "status": status,
            "preview_path": preview_path or "",
            "checks": {
                "schema_valid": schema_valid,
                "assets_exist": assets_exist,
                "pivots_defined": pivots_defined,
                "poses_defined": poses_defined,
                "actions_timed": actions_timed,
                "motion_detected": actions_timed,
                "browser_preview_checked": browser_preview_checked,
                "frame_samples_checked": frame_samples_checked,
            },
            "issues": issues,
            "recommended_action": "present_to_user" if status == "pass" else "fix_rig",
            "metadata": {
                "source": self.name,
                "confidence": "static artifact review; run Playwright/FFmpeg checks in compose for final output",
            },
        }
        artifacts = _write_json(inputs.get("output_path"), report)
        return ToolResult(
            success=True,
            data={"character_qa_report": report},
            artifacts=artifacts,
            duration_seconds=round(time.time() - start, 2),
        )
