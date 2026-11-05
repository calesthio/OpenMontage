"""Kling 4 and Kling 4 Edit video through the MiniCut CLI.

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

MODELS = ["kling-4", "kling-4-edit"]


class MiniCutVideo(BaseTool):
    name = "minicut_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "minicut"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["cmd:minicut"]
    install_instructions = minicut_cli.INSTALL_INSTRUCTIONS
    agent_skills = ["ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video", "reference_to_video", "video_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "video_edit": True,
        "native_audio": True,
        "price_quote_before_run": True,
    }
    best_for = [
        "Kling 4 shots of 3 to 30 seconds with sound",
        "editing a finished clip with Kling 4 Edit",
        "paid runs that must show the price and wait for a yes",
    ]
    not_good_for = ["offline generation", "runs with no user present to approve the price"]
    fallback_tools = ["kling_video", "kling_official_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {"type": "string", "enum": MODELS, "default": "kling-4"},
            "seconds": {"type": "integer", "minimum": 3, "maximum": 30, "default": 5},
            "resolution": {"type": "string", "enum": ["720p", "1080p"], "default": "720p"},
            "ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "21:9"],
                "description": "Text and reference requests only. A start frame sets its own shape.",
            },
            "image_path": {"type": "string", "description": "Start frame (kling-4)"},
            "end_image_path": {"type": "string", "description": "End frame (kling-4)"},
            "reference_images": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "video_path": {"type": "string", "description": "The clip to edit (kling-4-edit)"},
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
            "poll_timeout": {"type": "integer", "default": 900},
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    # Paid submission: never retried automatically. A timeout is collected with resume_job.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "prompt", "model", "seconds", "resolution", "ratio",
        "image_path", "end_image_path", "reference_images", "video_path",
    ]
    side_effects = [
        "writes video file to output_path",
        "spends MiniCut credits after approval",
        "keeps a copy of the result in the MiniCut library",
    ]
    user_visible_verification = ["Watch generated clip for motion coherence and sound"]

    # ---- CLI ----

    def _gen_words(self, inputs: dict[str, Any]) -> list[str]:
        model = inputs.get("model", "kling-4")
        if model not in MODELS:
            raise ValueError(f"model must be one of {MODELS}")
        if model == "kling-4-edit" and not inputs.get("video_path"):
            raise ValueError("kling-4-edit needs video_path, the clip to edit")
        # The library file name; the result is copied to output_path once saved.
        out_name = Path(inputs.get("output_path") or "minicut_output.mp4").name
        settings = {
            "seconds": int(inputs.get("seconds", 5)),
            "resolution": inputs.get("resolution", "720p"),
            "ratio": inputs.get("ratio") or None,
        }
        files = [("start_frame", inputs.get("image_path")), ("end_frame", inputs.get("end_image_path"))]
        files += [(f"image_ref[{i}]", p) for i, p in enumerate(inputs.get("reference_images") or [])]
        # Kling 4 Edit takes the clip it edits as the first video input.
        files.append(("video_ref[0]", inputs.get("video_path")))
        return minicut_cli.gen_words(model, out_name, inputs["prompt"], settings, files)

    # ---- Contract ----

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if minicut_cli.find_cli() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "MiniCut prices each request in credits; dry_run returns the exact quote for free"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 180.0

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
        output_path = Path(inputs.get("output_path", "minicut_output.mp4"))
        job_id = (inputs.get("resume_job") or {}).get("job_id")
        try:
            if not job_id:
                if not inputs.get("approval"):
                    return minicut_cli.needs_yes(minicut_cli.quote(self._gen_words(inputs)))
                sent = minicut_cli.send(self._gen_words(inputs), inputs["approval"])
                if isinstance(sent, ToolResult):
                    return sent
                job_id = sent

            saved = minicut_cli.collect(job_id, inputs.get("poll_timeout", 900))
            if isinstance(saved, ToolResult):
                return saved
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(saved, output_path)
        except Exception as exc:
            data = {"resume_job": {"job_id": job_id}} if job_id else {}
            return ToolResult(
                success=False,
                error=f"MiniCut video failed: {exc}",
                data=data,
                cost_usd=None if job_id else 0.0,
            )

        from tools.video._shared import probe_output

        model = inputs.get("model", "kling-4")
        return ToolResult(
            success=True,
            data={
                "provider": "minicut",
                "model": model,
                "job_id": job_id,
                "prompt": inputs["prompt"],
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                # MiniCut bills in credits; the USD value depends on the user's plan.
                "cost_status": "unquoted",
                **probe_output(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=None,
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
