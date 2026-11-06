"""Flow Integration — converts preproduction outputs into Flow Job Manager
jobs that stop at READY_FOR_APPROVAL.

No generation is triggered.  Jobs are created, validated, and held for
manual human approval before any credit-spending submission to Google Flow.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from lib.flow_job_manager import FlowJobManager, get_manager


@dataclass
class SceneJob:
    """A Flow job representing one preproduction scene."""

    scene_id: str
    job_id: str
    state: str
    prompt_packet: dict[str, Any]
    quality_report: dict[str, Any]
    references: list[str]
    project: str
    scene: str


@dataclass
class FlowIntegrationOutput:
    """Complete result of integrating preproduction with Flow Job Manager."""

    version: str = "1.0"
    run_id: str = ""
    created_at: str = ""
    total_scenes: int = 0
    jobs_queued: int = 0
    jobs_blocked: int = 0
    jobs: list[SceneJob] = field(default_factory=list)
    queue_summary: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


class FlowIntegration:
    """Integrate preproduction outputs with the Flow Job Manager."""

    def __init__(self, manager: FlowJobManager | None = None) -> None:
        self.manager = manager or get_manager()

    def integrate(
        self,
        *,
        run_id: str,
        project: str,
        scene_plans: list[dict[str, Any]],
        prompt_packets: list[dict[str, Any]],
        quality_reports: dict[str, dict[str, Any]],
        references_by_scene: dict[str, list[str]] | None = None,
        generation_params: dict[str, Any] | None = None,
        auto_approve: bool = False,
    ) -> FlowIntegrationOutput:
        """Create Flow jobs for every scene that passed QC.

        Every job stops at READY_FOR_APPROVAL.  If auto_approve is False
        (default), no job advances past READY_FOR_APPROVAL.
        """
        references_by_scene = references_by_scene or {}
        generation_params = generation_params or {}

        # Index prompt packets and quality reports by scene_id.
        packets_by_id = {p.get("scene_id", ""): p for p in prompt_packets}

        jobs: list[SceneJob] = []
        queued = 0
        blocked = 0

        for scene in scene_plans:
            scene_id = scene.get("scene_id", "unknown")
            packet = packets_by_id.get(scene_id, {})
            qc = quality_reports.get(scene_id, {})

            # Determine the scene title for the job.
            job_id = f"{run_id}-job-{scene_id}"

            # Only queue scenes that passed QC (no blocking issues).
            qc_blocking = qc.get("blocking_issues", [])
            if qc_blocking:
                blocked += 1
                # Still record a FAILED job in the manager for audit.
                try:
                    self.manager.add_job(
                        job_id=job_id,
                        project=project,
                        scene=scene_id,
                        prompt=f"BLOCKED: {scene.get('visual_idea', '')}",
                        aspect_ratio="16:9",
                        resolution="1920x1080",
                        references=references_by_scene.get(scene_id, []),
                        generation_params={},
                    )
                    self.manager.fail(job_id, "; ".join(qc_blocking))
                except ValueError:
                    # Job already exists — skip.
                    pass
                continue

            # Build the job prompt from the prompt packet.
            main_prompt = packet.get("main_prompt", "")
            negative_prompt = packet.get("negative_prompt", "")
            full_prompt = (
                f"{main_prompt}\n\nNegative: {negative_prompt}\n\n"
                f"Format: {packet.get('image_format', '')} | "
                f"Aspect: {packet.get('aspect_ratio', '16:9')}"
            )

            try:
                job = self.manager.add_job(
                    job_id=job_id,
                    project=project,
                    scene=scene_id,
                    prompt=full_prompt,
                    aspect_ratio=packet.get("aspect_ratio", "16:9"),
                    resolution="1920x1080",
                    references=[],  # Flow media refs stored in generation_params, not local files
                    input_files=[],
                    generation_params={
                        **generation_params,
                        "flow_references": references_by_scene.get(scene_id, []),
                    },
                )
                # Validate and move to READY_FOR_APPROVAL.
                # Use skip_mcp=True because structural QC already ran separately;
                # MCP checks are slow browser subprocesses.
                self.manager.validate_job(job_id, skip_mcp=True)
                self.manager.ready_for_approval(job_id)
                queued += 1
            except ValueError as exc:
                # Job may already exist or fail validation — record and skip.
                blocked += 1
                continue

            jobs.append(
                SceneJob(
                    scene_id=scene_id,
                    job_id=job_id,
                    state=self.manager.get_job(job_id).state,
                    prompt_packet=packet,
                    quality_report=qc,
                    references=references_by_scene.get(scene_id, []),
                    project=project,
                    scene=scene_id,
                )
            )

        return FlowIntegrationOutput(
            run_id=run_id,
            total_scenes=len(scene_plans),
            jobs_queued=queued,
            jobs_blocked=blocked,
            jobs=jobs,
            queue_summary=self.manager.queue_summary(),
            metadata={
                "auto_approve": auto_approve,
                "stop_state": "READY_FOR_APPROVAL",
                "zero_cost": True,
            },
        )

    def to_dict(self, output: FlowIntegrationOutput) -> dict[str, Any]:
        return {
            "version": output.version,
            "run_id": output.run_id,
            "created_at": output.created_at,
            "total_scenes": output.total_scenes,
            "jobs_queued": output.jobs_queued,
            "jobs_blocked": output.jobs_blocked,
            "jobs": [
                {
                    "scene_id": j.scene_id,
                    "job_id": j.job_id,
                    "state": j.state,
                    "prompt_packet": j.prompt_packet,
                    "quality_report": j.quality_report,
                    "references": j.references,
                    "project": j.project,
                    "scene": j.scene,
                }
                for j in output.jobs
            ],
            "queue_summary": output.queue_summary,
            "metadata": output.metadata,
        }
