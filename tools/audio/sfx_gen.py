"""Sound-effect generation tool via the ElevenLabs sound-generation API.

Generates short sound effects from text descriptions — UI ticks, whooshes,
pops, impacts, ambient textures. This is the first-class SFX path; ``music_gen``
handles full background-music tracks and does not generate SFX.

Generated SFX are registered in the asset manifest (``type: "sfx"``) and are
either placed as frame-accurate ``<Audio>`` cues inside a Remotion composition
(the product-motion atelier path) or mixed in post via ``audio_mixer``'s ``sfx``
track role using ``edit_decisions.audio.sfx[]``.

Docs: https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert
"""

from __future__ import annotations

import os
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


class SfxGen(BaseTool):
    name = "sfx_gen"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "sfx_generation"
    provider = "elevenlabs"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []  # checked dynamically via API key
    install_instructions = (
        "Set the ELEVENLABS_API_KEY environment variable:\n"
        "  export ELEVENLABS_API_KEY=your_key_here\n"
        "Get a key at https://elevenlabs.io"
    )
    fallback_tools = []
    agent_skills = ["sound-effects", "elevenlabs"]

    capabilities = [
        "generate_sfx",
    ]
    supports = {
        "looping": True,
        "duration_control": True,
        "offline": False,
    }
    best_for = [
        "UI interaction sounds (ticks, clicks, pops) synced to motion",
        "whooshes and risers for element-assembly animations",
        "short cinematic impacts and ambient textures",
    ]
    not_good_for = [
        "background music tracks (use music_gen)",
        "speech (use a TTS tool)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": (
                    "Sound description (e.g. 'soft glass tick, short, subtle', "
                    "'airy whoosh rising, 1 second'). Describe texture, length, "
                    "and intensity."
                ),
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 30,
                "description": (
                    "Duration 0.5-30s. Omit to let the API auto-calculate from "
                    "the prompt. UI cue sounds are typically 0.5-1.5s."
                ),
            },
            "prompt_influence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "default": 0.3,
                "description": (
                    "How literally to follow the prompt (0-1). Higher = closer "
                    "adherence, lower = more creative interpretation."
                ),
            },
            "loop": {
                "type": "boolean",
                "default": False,
                "description": "Generate a seamlessly looping sound (for ambient beds).",
            },
            "output_path": {"type": "string"},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "prompt": {"type": "string"},
            "output": {"type": "string"},
            "format": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=10, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "duration_seconds", "prompt_influence", "loop"]
    side_effects = ["writes audio file to output_path", "calls ElevenLabs API"]
    user_visible_verification = [
        "Listen to the generated effect at the intended cue point in context",
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("ELEVENLABS_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # ElevenLabs bills sound generation per effect (credit-based);
        # roughly $0.03 per generated effect on paid tiers.
        return 0.03

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 10.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="No ElevenLabs API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as e:
            return ToolResult(success=False, error=f"SFX generation failed: {e}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        import requests

        prompt = inputs["prompt"]
        url = "https://api.elevenlabs.io/v1/sound-generation"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "text": prompt,
            "prompt_influence": inputs.get("prompt_influence", 0.3),
        }
        if inputs.get("duration_seconds") is not None:
            payload["duration_seconds"] = float(inputs["duration_seconds"])
        if inputs.get("loop"):
            payload["loop"] = True

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code != 200:
            detail = response.text[:500] if response.text else ""
            return ToolResult(
                success=False,
                error=f"ElevenLabs sound generation returned HTTP {response.status_code}: {detail}",
            )

        output_path = Path(inputs.get("output_path", "sfx_output.mp3"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "prompt": prompt,
                "output": str(output_path),
                "format": "mp3",
            },
            artifacts=[str(output_path)],
            model="elevenlabs-sound-generation",
        )
