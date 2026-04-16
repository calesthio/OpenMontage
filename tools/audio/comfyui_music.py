"""ComfyUI music generation via ACE-Step model.

Generates background music and songs locally using the ACE-Step 3.5B
model running inside a ComfyUI server.  Custom workflows are accepted
via the ``workflow_json`` input.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

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
from tools._comfyui.client import ComfyUIClient, ComfyUIError

_WORKFLOWS = Path(__file__).resolve().parent.parent / "_comfyui" / "workflows"

_OUTPUT_NODE = "3"


class ComfyUIMusic(BaseTool):
    name = "comfyui_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "comfyui"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []
    install_instructions = (
        "Start a ComfyUI server and set COMFYUI_SERVER_URL "
        "(default http://localhost:8188).\n"
        "Requires ACE-Step model (ace_step_v1_3.5b.safetensors) in "
        "ComfyUI's checkpoints directory and the ACE-Step custom node installed."
    )
    agent_skills = ["music"]

    capabilities = [
        "generate_background_music",
        "generate_instrumental",
        "generate_song",
        "text_to_music",
    ]
    supports = {
        "seed": True,
        "duration_control": True,
        "lyrics": True,
        "custom_workflow": True,
        "offline": True,
    }
    best_for = [
        "local music generation without API costs",
        "background music and instrumentals for video production",
        "song generation with lyrics",
    ]
    not_good_for = [
        "setups without a running ComfyUI server",
        "highest quality commercial music (use Suno or ElevenLabs)",
    ]
    fallback = "suno_music"
    fallback_tools = ["suno_music", "elevenlabs_music", "freesound_music"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Music style / mood description (e.g. 'upbeat corporate background music')",
            },
            "lyrics": {
                "type": "string",
                "default": "",
                "description": "Optional lyrics for song generation",
            },
            "duration": {
                "type": "number",
                "default": 30.0,
                "description": "Duration in seconds",
            },
            "steps": {"type": "integer", "default": 60},
            "cfg": {"type": "number", "default": 3.0},
            "seed": {"type": "integer", "description": "Random if omitted"},
            "output_path": {"type": "string", "description": "Where to save the audio"},
            "workflow_json": {
                "type": "string",
                "description": "Optional full ComfyUI workflow JSON (overrides default)",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=8000, vram_mb=6000, disk_mb=500, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "lyrics", "duration", "steps", "seed"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for quality and mood match"]

    def __init__(self) -> None:
        self._client = ComfyUIClient()

    def get_status(self) -> ToolStatus:
        if self._client.is_available():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = inputs.get("duration", 30.0)
        return duration * 2.0  # rough: ~2x realtime

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not self._client.is_available():
            return ToolResult(
                success=False,
                error="ComfyUI server not reachable. " + self.install_instructions,
            )

        start = time.time()
        seed = inputs.get("seed") or ComfyUIClient.random_seed()
        duration = inputs.get("duration", 30.0)
        output_path = Path(
            inputs.get("output_path", f"comfyui_music_{seed}.wav")
        )

        try:
            if inputs.get("workflow_json"):
                workflow = json.loads(inputs["workflow_json"])
            else:
                workflow = ComfyUIClient.load_workflow(
                    _WORKFLOWS / "ace-step-music.json"
                )
                workflow = ComfyUIClient.patch_workflow(workflow, {
                    "2": {
                        "prompt": inputs["prompt"],
                        "lyrics": inputs.get("lyrics", ""),
                        "duration": duration,
                        "seed": seed,
                        "steps": inputs.get("steps", 60),
                        "cfg": inputs.get("cfg", 3.0),
                    },
                    "3": {"filename_prefix": output_path.stem},
                })

            paths = self._client.generate(
                workflow,
                output_node=_OUTPUT_NODE,
                dest=output_path,
                timeout=int(duration * 4),  # generous timeout
            )

        except ComfyUIError as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:
            return ToolResult(success=False, error=f"ComfyUI music generation failed: {exc}")

        return ToolResult(
            success=True,
            data={
                "provider": "comfyui",
                "model": "ace-step-v1-3.5b",
                "prompt": inputs["prompt"],
                "lyrics": inputs.get("lyrics", ""),
                "duration": duration,
                "output": str(paths[0]),
                "format": output_path.suffix.lstrip("."),
            },
            artifacts=[str(p) for p in paths],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model="ace-step-v1-3.5b",
        )
