"""Cloud video upscale (Topaz) through the MiniCut CLI.

Needs no local GPU: the clip is sent to MiniCut model ``topaz-standard``
and the upscaled clip is written to ``output_path``. Video only (mp4, mov or
webm); still images are not covered, use ``upscale`` for those.

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

MODEL = "topaz-standard"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}


class MiniCutUpscale(BaseTool):
    name = "minicut_upscale"
    version = "0.1.0"
    tier = ToolTier.ENHANCE
    capability = "enhancement"
    provider = "minicut"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = ["cmd:minicut"]
    install_instructions = minicut_cli.INSTALL_INSTRUCTIONS
    agent_skills = ["ffmpeg"]

    capabilities = ["video_upscale"]
    supports = {
        "video_upscale": True,
        "image_upscale": False,
        "price_quote_before_run": True,
    }
    best_for = [
        "upscaling a finished clip without a local GPU",
        "paid runs that must show the price and wait for a yes",
    ]
    not_good_for = ["still images", "offline runs", "runs with no user present to approve the price"]
    fallback_tools = ["upscale"]

    input_schema = {
        "type": "object",
        "required": ["input_path"],
        "properties": {
            "input_path": {"type": "string", "description": "The clip to upscale (mp4, mov or webm)"},
            "output_path": {"type": "string"},
            "scale": {"type": "integer", "minimum": 1, "maximum": 4, "default": 2},
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
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=2000, network_required=True
    )
    # Paid submission: never retried automatically. A timeout is collected with resume_job.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["input_path", "scale"]
    side_effects = [
        "writes upscaled video to output_path",
        "spends MiniCut credits after approval",
        "keeps a copy of the result in the MiniCut library",
    ]
    user_visible_verification = ["Compare upscaled clip with the original for detail and artifacts"]

    # ---- CLI ----

    @staticmethod
    def _output_path(inputs: dict[str, Any]) -> Path:
        src = Path(inputs["input_path"])
        return Path(inputs.get("output_path") or src.with_name(f"{src.stem}_upscaled.mp4"))

    def _gen_words(self, inputs: dict[str, Any]) -> list[str]:
        src = Path(inputs["input_path"])
        if src.suffix.lower() not in VIDEO_EXTENSIONS:
            raise ValueError(
                f"minicut_upscale takes a video (mp4, mov or webm), got {src.name}. "
                "Use upscale for still images."
            )
        settings = {"upscale-factor": int(inputs.get("scale", 2))}
        # The library file name; the result is copied to output_path once saved.
        out_name = self._output_path(inputs).name
        return minicut_cli.gen_words(MODEL, out_name, None, settings, [("source", str(src))])

    # ---- Contract ----

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if minicut_cli.find_cli() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "MiniCut prices each request in credits; dry_run returns the exact quote for free"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 300.0

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
        output_path = self._output_path(inputs)
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
                error=f"MiniCut upscale failed: {exc}",
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
                "input": str(inputs["input_path"]),
                "output": str(output_path),
                "output_path": str(output_path),
                "scale": int(inputs.get("scale", 2)),
                "type": "video",
                # MiniCut bills in credits; the USD value depends on the user's plan.
                "cost_status": "unquoted",
                **probe_output(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=None,
            duration_seconds=round(time.time() - start, 2),
            model=MODEL,
        )
