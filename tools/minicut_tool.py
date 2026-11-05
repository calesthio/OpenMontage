"""Shared base for the MiniCut image, voice and music tools.

Each tool names one MiniCut model and turns its inputs into ``gen`` words.
This base keeps the same price-then-yes flow as ``minicut_video``:
``dry_run`` returns the CLI's free quote as an ``approval``, ``execute``
sends exactly that approval, and sending it again never pays twice.
"""

from __future__ import annotations

import shutil
import time
from abc import abstractmethod
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

APPROVAL_SCHEMA = {
    "type": "object",
    "description": (
        "dry_run()['approval'], after the user said yes to its credits. "
        "Without it nothing is sent. Sending the same approval again never pays twice."
    ),
}
RESUME_SCHEMA = {
    "type": "object",
    "description": "{'job_id': ...} from a run that timed out. Collects it, no new charge.",
}


class MiniCutTool(BaseTool):
    """One MiniCut model behind the CLI's price-then-yes gate."""

    version = "0.1.0"
    tier = ToolTier.GENERATE
    provider = "minicut"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API
    dependencies = ["cmd:minicut"]
    install_instructions = minicut_cli.INSTALL_INSTRUCTIONS
    not_good_for = ["offline generation", "runs with no user present to approve the price"]
    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    # Paid submission: never retried automatically. A timeout is collected with resume_job.
    retry_policy = RetryPolicy(max_retries=0)

    model = ""  # the MiniCut model id
    default_output = "minicut_output"

    @abstractmethod
    def _request(self, inputs: dict[str, Any]) -> tuple[str, dict[str, Any], list[tuple[str, str | None]]]:
        """The prompt, the ``--set`` settings and the ``--in`` files for this model."""

    def _gen_words(self, inputs: dict[str, Any]) -> list[str]:
        prompt, settings, files = self._request(inputs)
        # The library file name; the result is copied to output_path once saved.
        out_name = Path(inputs.get("output_path") or self.default_output).name
        return minicut_cli.gen_words(self.model, out_name, prompt, settings, files)

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if minicut_cli.find_cli() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "MiniCut prices each request in credits; dry_run returns the exact quote for free"
        )

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

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
        output_path = Path(inputs.get("output_path") or self.default_output)
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
            # Keep the file type the model returned (a .wav stays .wav).
            suffix = Path(saved).suffix
            if suffix and suffix.lower() != output_path.suffix.lower():
                output_path = output_path.with_suffix(suffix)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(saved, output_path)
        except Exception as exc:
            data = {"resume_job": {"job_id": job_id}} if job_id else {}
            return ToolResult(
                success=False,
                error=f"MiniCut {self.model} failed: {exc}",
                data=data,
                cost_usd=None if job_id else 0.0,
            )

        return ToolResult(
            success=True,
            data={
                "provider": "minicut",
                "model": self.model,
                "job_id": job_id,
                "output": str(output_path),
                "output_path": str(output_path),
                "format": output_path.suffix.lstrip("."),
                # MiniCut bills in credits; the USD value depends on the user's plan.
                "cost_status": "unquoted",
            },
            artifacts=[str(output_path)],
            cost_usd=None,
            duration_seconds=round(time.time() - start, 2),
            model=self.model,
        )
