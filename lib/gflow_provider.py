"""Image Provider Adapter — adapts GflowWrapper to the Image Generation Engine.

Responsibilities:

  * Convert an engine-level image request (sentence_id, prompt, asset info)
    into a Flow Job held at ``READY_FOR_APPROVAL``.
  * Expose execution that only proceeds after explicit owner approval and
    zero-cost-gate clearance (delegated to :class:`lib.gflow_wrapper.GflowWrapper`).
  * Translate ``GflowResult`` into engine-level generation records.

This adapter never generates images itself and never spends credits.  The
automated system stops at ``READY_FOR_APPROVAL``; moving to ``APPROVED`` /
``SUBMITTED`` requires manual owner action outside this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lib.flow_job_manager import FlowJobManager
from lib.gflow_wrapper import (
    DEFAULT_ASPECT,
    DEFAULT_MODEL,
    GflowResult,
    GflowWrapper,
    ZeroCostViolation,
)


@dataclass
class ProviderImageRequest:
    """One image-generation request from the engine."""

    sentence_id: str
    project_id: str
    prompt: str
    prompt_id: str
    asset_id: str
    output_path: str
    aspect_ratio: str = DEFAULT_ASPECT
    model: str = DEFAULT_MODEL
    reference_entity: str | None = None
    generation_params: dict[str, Any] | None = None


@dataclass
class ProviderImageResult:
    """Engine-level result of planning / executing one image."""

    sentence_id: str
    asset_id: str
    job_id: str
    state: str               # READY_FOR_APPROVAL | COMPLETED | FAILED | BLOCKED
    gflow_result: GflowResult | None = None
    error: str | None = None
    blocked_reason: str | None = None


class GflowProvider:
    """Adapter between the engine and gflow-cli via GflowWrapper."""

    def __init__(
        self,
        *,
        manager: FlowJobManager | None = None,
        wrapper: GflowWrapper | None = None,
    ) -> None:
        self.manager = manager or FlowJobManager()
        self.wrapper = wrapper or GflowWrapper(manager=self.manager)

    # ------------------------------------------------------------------
    # Planning (zero-cost, stops at READY_FOR_APPROVAL)
    # ------------------------------------------------------------------

    def plan_image(self, *, req: ProviderImageRequest) -> ProviderImageResult:
        """Create a Flow Job for *req* and hold it at READY_FOR_APPROVAL.

        No credits are spent.  Returns once the job is validated and moved
        to READY_FOR_APPROVAL awaiting manual owner approval.
        """
        generation_params = dict(req.generation_params or {})
        generation_params.update(
            {
                "model": req.model,
                "count": 1,
                "aspect_ratio": req.aspect_ratio,
                "output_path": req.output_path,
                "reference_entity": req.reference_entity,
                "prompt_id": req.prompt_id,
                "asset_id": req.asset_id,
            }
        )
        job = self.wrapper.plan_image_job(
            sentence_id=req.sentence_id,
            project=req.project_id,
            prompt=req.prompt,
            output_path=req.output_path,
            aspect_ratio=req.aspect_ratio,
            model=req.model,
            reference_entity=req.reference_entity,
        )
        # Store prompt_id / asset_id on the job for downstream lookup.
        job.generation_params = dict(job.generation_params or {})
        job.generation_params["prompt_id"] = req.prompt_id
        job.generation_params["asset_id"] = req.asset_id
        self.manager._persist(job)

        return ProviderImageResult(
            sentence_id=req.sentence_id,
            asset_id=req.asset_id,
            job_id=job.job_id,
            state=job.state,
        )

    # ------------------------------------------------------------------
    # Execution (credit-bearing; requires approval)
    # ------------------------------------------------------------------

    def execute_image(
        self,
        *,
        job_id: str,
        user_approved: bool = False,
        cost_usd: float | None = None,
    ) -> ProviderImageResult:
        """Execute one credit-bearing gflow image t2i call.

        Raises ``ZeroCostViolation`` if the zero-cost gate blocks.
        Returns an error result (not an exception) if the job is not
        APPROVED (manual owner gate) or if gflow returns non-zero.
        """
        try:
            result = self.wrapper.execute_image(
                job_id=job_id,
                user_approved=user_approved,
                cost_usd=cost_usd,
            )
        except ZeroCostViolation as exc:
            job = self.manager.get_job(job_id)
            return ProviderImageResult(
                sentence_id="",
                asset_id="",
                job_id=job_id,
                state="BLOCKED",
                error=str(exc),
                blocked_reason="zero_cost_gate",
            )

        job = self.manager.get_job(job_id)
        sentence_id = ""
        asset_id = ""
        if job and job.generation_params:
            sentence_id = job.generation_params.get("sentence_id", "")
            asset_id = job.generation_params.get("asset_id", "")

        return ProviderImageResult(
            sentence_id=sentence_id,
            asset_id=asset_id,
            job_id=job_id,
            state=job.state if job else "UNKNOWN",
            gflow_result=result,
            error=result.error,
        )

    def execute_batch(
        self,
        *,
        config_path: str,
        output_dir: str,
        user_approved: bool = False,
        cost_usd: float | None = None,
    ) -> GflowResult:
        """Execute a JSON batch via gflow run --config (gated, approved)."""
        return self.wrapper.execute_batch(
            config_path=config_path,
            output_dir=output_dir,
            user_approved=user_approved,
            cost_usd=cost_usd,
        )

    def job_state(self, job_id: str) -> str | None:
        job = self.manager.get_job(job_id)
        return job.state if job else None
