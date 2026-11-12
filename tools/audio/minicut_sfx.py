"""One sound effect from a line of text, through the MiniCut CLI.

Makes a single effect (a door slam, a whoosh, rain on a window) as its own
audio file at ``output_path``, with the ElevenLabs Sound Effects v2 model.

``dry_run`` returns the CLI's free price quote as an ``approval``, and
``execute`` sends exactly that approval and nothing else; sending it again
never starts a second paid job. The CLI calls live in ``tools/minicut_cli.py``.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from tools import minicut_cli
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
from tools.provider_pricing import PriceQuoteRequired

MODEL = "elevenlabs-sfx-v2"


class MiniCutSfx(BaseTool):
    name = "minicut_sfx"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "sound_effects"
    provider = "minicut"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["cmd:minicut"]
    install_instructions = minicut_cli.INSTALL_INSTRUCTIONS
    agent_skills = ["sound-effects"]

    capabilities = ["generate_sfx"]
    supports = {
        "loop": True,
        "price_quote_before_run": True,
    }
    best_for = [
        "one sound effect from a line of text, 0.5 to 22 seconds",
        "hits, whooshes and room sounds to place on the timeline with audio_mixer",
        "paid runs that must show the price and wait for a yes",
    ]
    not_good_for = [
        "music beds or songs",
        "speech",
        "offline generation",
        "runs with no user present to approve the price",
    ]
    fallback_tools = []

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "maxLength": 450,
                "description": "The sound, in plain words: 'a heavy wooden door slams shut'",
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 0.5,
                "maximum": 22,
                "description": "Length of the effect. Leave out to let the model pick.",
            },
            "prompt_influence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "How closely to follow the prompt. Model default 0.3.",
            },
            "loop": {"type": "boolean", "description": "Make an effect that loops cleanly"},
            "approval": {
                "type": "object",
                "description": (
                    "dry_run()['approval'], after the user said yes to its credits. "
                    "Without it nothing is sent. Sending the same approval again never pays twice."
                ),
            },
            "resume_job": {
                "type": "object",
                "description": "{'job_id': ...} from a run that timed out. Collects it, no new charge.",
            },
            "poll_timeout": {"type": "integer", "default": 300},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    # Paid submission: never retried automatically. A timeout is collected with resume_job.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "duration_seconds", "prompt_influence", "loop"]
    side_effects = [
        "writes audio file to output_path",
        "spends MiniCut credits after approval",
        "keeps a copy of the result in the MiniCut library",
    ]
    user_visible_verification = ["Listen to the effect against the cut it is meant for"]

    # ---- CLI ----

    def _gen_words(self, inputs: dict[str, Any]) -> list[str]:
        # The library file name; the result is copied to output_path once saved.
        out_name = Path(inputs.get("output_path") or "minicut_sfx.mp3").name
        loop = inputs.get("loop")
        settings = {
            "duration-seconds": inputs.get("duration_seconds"),
            "prompt-influence": inputs.get("prompt_influence"),
            # The CLI reads a --set value as JSON, so a switch goes out as true or false.
            "loop": None if loop is None else str(bool(loop)).lower(),
        }
        return minicut_cli.gen_words(MODEL, out_name, inputs["prompt"], settings)

    # ---- Contract ----

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if minicut_cli.find_cli() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "MiniCut prices each request in credits; dry_run returns the exact quote for free"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 20.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        result = super().dry_run(inputs)
        try:
            approval = minicut_cli.quote(self._gen_words(inputs))
        except Exception as exc:
            return {**result, "would_execute": False, "quote_reason": str(exc)}
        return {
            **result,
            "estimated_credits": approval["credits"],
            "approval": approval,
            "would_execute": False,
        }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        output_path = Path(inputs.get("output_path", "minicut_sfx.mp3"))
        job_id = (inputs.get("resume_job") or {}).get("job_id")
        try:
            if not job_id:
                if not inputs.get("approval"):
                    return minicut_cli.needs_yes(minicut_cli.quote(self._gen_words(inputs)))
                sent = minicut_cli.send(self._gen_words(inputs), inputs["approval"])
                if isinstance(sent, ToolResult):
                    return sent
                job_id = sent

            saved = minicut_cli.collect(job_id, inputs.get("poll_timeout", 300))
            if isinstance(saved, ToolResult):
                return saved
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(saved, output_path)
        except Exception as exc:
            data = {"resume_job": {"job_id": job_id}} if job_id else {}
            return ToolResult(
                success=False,
                error=f"MiniCut sound effect failed: {exc}",
                data=data,
                cost_usd=None if job_id else 0.0,
            )

        from tools.video._shared import probe_output

        return ToolResult(
            success=True,
            data={
                "provider": "minicut",
                "model": MODEL,
                "job_id": job_id,
                "prompt": inputs["prompt"],
                "output": str(output_path),
                "output_path": str(output_path),
                "format": Path(saved).suffix.lstrip(".").lower() or "mp3",
                # MiniCut bills in credits; the USD value depends on the user's plan.
                "cost_status": "unquoted",
                **probe_output(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=None,
            duration_seconds=round(time.time() - start, 2),
            model=MODEL,
        )
