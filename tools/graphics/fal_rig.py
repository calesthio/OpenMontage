"""Humanoid auto-rigging and preset animation (Meshy via fal.ai)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


_MODEL = "fal-ai/meshy/rigging/multi-animation"
_LIBRARY_URL = "https://docs.meshy.ai/en/api/animation-library"
# Limits published on the fal endpoint page: IDs 0-696, at most 10 distinct clips per request
# (duplicates are de-duplicated server-side, so they are billed once).
_MAX_ACTION_ID = 696
_MAX_CLIPS = 10
# Pricing from the fal model page (checked 2026-10-11): $0.20 per request + $0.12 per clip.
_BASE_COST_USD = 0.20
_CLIP_COST_USD = 0.12

# A few library IDs that production briefs ask for by name, with the Meshy library names
# they resolve to (verified against _LIBRARY_URL on 2026-10-11). The full catalog is 0-696.
PRESETS = {
    "idle": 0,                  # Idle
    "walk": 30,                 # Casual_Walk (root motion)
    "walk_inplace": 613,        # Casual_Walk_inplace — use when the scene keys the character's position
    "skip": 118,                # Skip_Forward
    "skip_inplace": 668,        # Skip_Forward_inplace
    "wave_hello": 28,           # Big_Wave_Hello
    "wave_one_hand": 290,       # Wave_One_Hand
    "cheer": 303,               # Cheer_with_Both_Hands
    "happy_jump_f": 44,         # Happy_jump_f
    "happy_jump_m": 61,         # happy_jump_m
    "clap_sitting": 354,        # Sitting_Clap
    "jumping_jacks": 326,       # jumping_jacks
    "funny_dance_1": 22,        # FunnyDancing_01
}

_EXT_BY_TYPE = {
    "model/gltf-binary": ".glb",
    "model/gltf+json": ".gltf",
    "application/octet-stream": "",
    "model/fbx": ".fbx",
}


def _api_key() -> str | None:
    return os.environ.get("FAL_KEY") or os.environ.get("FAL_AI_API_KEY")


def _download(file_info: dict[str, Any], target_stem: Path) -> Path:
    """Download a fal File object; pick the extension from the URL, then content type, then file_name.

    The extension is appended to the stem's full name (not `with_suffix`) so a stem such as
    `alfie.tpose_rigged` keeps its dotted part instead of being truncated to `alfie.glb`.
    """
    url = str(file_info["url"])
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix not in {".glb", ".gltf", ".fbx", ".zip"}:
        suffix = _EXT_BY_TYPE.get(str(file_info.get("content_type", "")), "") or Path(str(file_info.get("file_name", ""))).suffix or ".bin"
    target = target_stem.with_name(target_stem.name + suffix)
    response = requests.get(url, timeout=300)
    response.raise_for_status()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(response.content)
    return target


def _strip_urls(value: Any) -> Any:
    """Provenance copy of the response without signed URLs."""
    if isinstance(value, dict):
        return {k: _strip_urls(v) for k, v in value.items() if k != "url"}
    if isinstance(value, list):
        return [_strip_urls(v) for v in value]
    return value


class FalRig(BaseTool):
    name = "fal_rig"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "character_rigging"
    provider = "fal"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API
    dependencies = ["env:FAL_KEY"]
    install_instructions = "Set FAL_KEY (or FAL_AI_API_KEY). Create a key at https://fal.ai/dashboard/keys."
    agent_skills = ["3d-asset-generation"]
    capabilities = ["auto_rig", "preset_animation", "fbx", "glb"]
    supports = {
        "humanoid": True,
        "quadruped": False,
        "preset_animations": True,
        "custom_motion": False,
        "fbx": True,
        "glb": True,
    }
    best_for = [
        "Rigging a humanoid character mesh (Hunyuan / Meshy / Trellis output) without a browser session",
        "Getting preset walk / wave / idle clips on that rig as FBX + GLB for Blender",
        "Batch-rigging a cast so new characters never need a manual Mixamo pass",
    ]
    not_good_for = [
        "Animals, vehicles or multi-limbed characters (humanoid only)",
        "Bespoke motion — retarget or keyframe in Blender on the returned rig instead",
        "Facial animation / lip-sync (body rig only)",
    ]
    input_schema = {
        "type": "object",
        "required": ["animation_action_ids", "output_dir"],
        "properties": {
            "model_url": {"type": "string", "description": "Public URL of a humanoid GLB in T- or A-pose"},
            "model_path": {"type": "string", "description": "Local GLB; uploaded to fal storage when model_url is absent"},
            "height_meters": {"type": "number", "default": 1.7, "description": "Character height — scales the rig and locomotion"},
            "animation_action_ids": {
                "type": "array",
                "items": {"type": "integer", "minimum": 0, "maximum": _MAX_ACTION_ID},
                "minItems": 1,
                "maxItems": _MAX_CLIPS,
                "description": f"Meshy animation-library IDs ({_LIBRARY_URL}); see PRESETS for named shortcuts",
            },
            "output_dir": {"type": "string", "description": "Directory for the rigged character and one file per clip"},
            "enable_safety_checker": {"type": "boolean", "default": True},
            "poll_timeout_seconds": {"type": "integer", "minimum": 60, "maximum": 3600, "default": 1500},
        },
    }
    output_schema = {"type": "object"}
    artifact_schema = {"artifact": "rigged_character"}
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=2000, network_required=True)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["model_url", "model_path", "height_meters", "animation_action_ids"]
    side_effects = ["calls fal.ai", "may upload a local GLB", "writes rigged meshes, animation clips and provenance"]
    user_visible_verification = [
        "Import the rigged FBX into Blender: skeleton aligned to the mesh, no collapsed limbs, clips play without twisting",
    ]
    quality_score = 0.85

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if _api_key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Base request fee plus one clip fee per *distinct* library ID (fal de-duplicates repeats)."""
        ids = {int(i) for i in (inputs.get("animation_action_ids") or [])}
        return round(_BASE_COST_USD + _CLIP_COST_USD * len(ids), 2)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        key = _api_key()
        if not key:
            return ToolResult(success=False, error="fal.ai API key not set. " + self.install_instructions)
        # Distinct IDs in request order: fal de-duplicates and returns one animations[] entry per distinct ID.
        ids = list(dict.fromkeys(int(i) for i in (inputs.get("animation_action_ids") or [])))
        if not ids:
            return ToolResult(success=False, error="animation_action_ids must contain at least one library ID")
        out_of_range = [i for i in ids if not 0 <= i <= _MAX_ACTION_ID]
        if out_of_range:
            return ToolResult(
                success=False,
                error=f"animation_action_ids must be within 0-{_MAX_ACTION_ID} ({_LIBRARY_URL}); got {out_of_range}",
            )
        if len(ids) > _MAX_CLIPS:
            return ToolResult(
                success=False,
                error=f"at most {_MAX_CLIPS} distinct animation clips per request; got {len(ids)}",
            )
        if not (inputs.get("model_url") or inputs.get("model_path")):
            return ToolResult(success=False, error="model_url or model_path (GLB) is required")

        started = time.time()
        try:
            model_url = inputs.get("model_url")
            if not model_url:
                from tools.video._shared import upload_file_fal
                model_url = upload_file_fal(str(inputs["model_path"]))
            payload: dict[str, Any] = {
                "model_url": model_url,
                "height_meters": float(inputs.get("height_meters", 1.7)),
                "animation_action_ids": ids,
                "enable_safety_checker": bool(inputs.get("enable_safety_checker", True)),
            }
            headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
            submit = requests.post(f"https://queue.fal.run/{_MODEL}", headers=headers, json=payload, timeout=45)
            submit.raise_for_status()
            queued = submit.json()
            status_url, response_url = queued["status_url"], queued["response_url"]
            deadline = time.monotonic() + int(inputs.get("poll_timeout_seconds", 1500))
            while time.monotonic() < deadline:
                status_response = requests.get(status_url, headers=headers, timeout=30)
                status_response.raise_for_status()
                status = str(status_response.json().get("status", "")).upper()
                if status == "COMPLETED":
                    break
                if status in {"FAILED", "CANCELLED"}:
                    raise RuntimeError(f"request {status.lower()}")
                time.sleep(5)
            else:
                raise TimeoutError("fal.ai request exceeded the poll timeout")
            result_response = requests.get(response_url, headers=headers, timeout=45)
            result_response.raise_for_status()
            data = result_response.json()

            out_dir = Path(str(inputs["output_dir"])).expanduser().resolve()
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = Path(str(inputs.get("model_path") or urlparse(str(model_url)).path)).stem or "character"
            artifacts: list[str] = []
            for field, label in (("rigged_character_glb", "rigged"), ("rigged_character_fbx", "rigged")):
                info = data.get(field)
                if isinstance(info, dict) and info.get("url"):
                    artifacts.append(str(_download(info, out_dir / f"{stem}_{label}")))
            basic = data.get("basic_animations") or {}
            if isinstance(basic, dict):
                for k, info in basic.items():
                    if isinstance(info, dict) and info.get("url"):
                        artifacts.append(str(_download(info, out_dir / f"{stem}_basic_{k}")))
            for index, clip in enumerate(data.get("animations") or []):
                if not isinstance(clip, dict):
                    continue
                action = clip.get("action_id", ids[index] if index < len(ids) else index)
                name = str(clip.get("action_name") or clip.get("name") or "").strip().replace(" ", "_")
                for k, info in clip.items():
                    if isinstance(info, dict) and info.get("url"):
                        label = f"{stem}_anim{index:02d}_id{action}" + (f"_{name}" if name else "") + f"_{k}"
                        artifacts.append(str(_download(info, out_dir / label)))
            if not artifacts:
                raise RuntimeError("fal.ai completed without any downloadable rig or clip")

            provenance = out_dir / f"{stem}_rig.provenance.json"
            provenance.write_text(json.dumps({
                "version": "1.0",
                "provider": "fal",
                "model": _MODEL,
                "request_id": queued.get("request_id"),
                "rig_task_id": data.get("rig_task_id"),
                "height_meters": payload["height_meters"],
                "animation_action_ids": ids,
                "source_url": f"https://fal.ai/models/{_MODEL}",
                "response": _strip_urls(data),
                "outputs": artifacts,
            }, indent=2), encoding="utf-8")
            artifacts.append(str(provenance))
        except Exception as exc:
            return ToolResult(success=False, error=f"fal.ai rigging failed: {exc}")

        return ToolResult(
            success=True,
            data={"provider": "fal", "model": _MODEL, "rig_task_id": data.get("rig_task_id"), "outputs": artifacts[:-1]},
            artifacts=artifacts,
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - started, 2),
            model=_MODEL,
        )
