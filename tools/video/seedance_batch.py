"""Prepare Seedance provider tasks from an approved production plan."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)
from tools.video.seedance_constraints import (
    ALLOWED_DURATIONS,
    ALLOWED_RESOLUTIONS,
    DEFAULT_DURATION,
    DEFAULT_RESOLUTION,
    MAX_GENERATIONS_PER_BATCH,
    validate_seedance_constraints,
)


PROVIDER_TOOLS = {
    "runninghub": "runninghub_seedance_video",
    "fal": "seedance_video",
    "replicate": "seedance_replicate",
}
SAMPLE_APPROVAL_PHRASE = "RUN SEEDANCE SAMPLE"


def _safe_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-._")
    return slug or "seedance"


def _load_plan(inputs: dict[str, Any]) -> dict[str, Any]:
    if inputs.get("production_plan"):
        return dict(inputs["production_plan"])
    plan_path = inputs.get("production_plan_path")
    if not plan_path:
        raise ValueError("production_plan or production_plan_path is required")
    return json.loads(Path(plan_path).read_text(encoding="utf-8"))


def _constraint_inputs(plan: dict[str, Any]) -> dict[str, Any]:
    constraints = plan.get("seedance_constraints") or {}
    return {
        "duration": str(constraints.get("duration", DEFAULT_DURATION)),
        "resolution": str(constraints.get("resolution", DEFAULT_RESOLUTION)),
        "batch_size": constraints.get("batch_size", 1),
    }


def _batch_size(plan: dict[str, Any]) -> int:
    try:
        return int((plan.get("seedance_constraints") or {}).get("batch_size", 1))
    except (TypeError, ValueError):
        return 1


def _asset_image_paths(project_dir: Path, scene: dict[str, Any]) -> list[str]:
    image_paths: list[str] = []
    for asset in scene.get("selected_assets") or []:
        if not isinstance(asset, dict):
            continue
        asset_type = str(asset.get("type", "")).lower()
        path = str(asset.get("path", "")).strip()
        if not path or asset_type not in {"", "image"}:
            continue
        asset_path = Path(path)
        if not asset_path.is_absolute():
            asset_path = project_dir / asset_path
        image_paths.append(str(asset_path))
    return image_paths


def _provider_tool(provider: str) -> BaseTool:
    if provider == "runninghub":
        from tools.video.runninghub_seedance_video import RunningHubSeedanceVideo

        return RunningHubSeedanceVideo()
    if provider == "fal":
        from tools.video.seedance_video import SeedanceVideo

        return SeedanceVideo()
    if provider == "replicate":
        from tools.video.seedance_replicate import SeedanceReplicate

        return SeedanceReplicate()
    raise ValueError(f"Unsupported Seedance provider: {provider}")


class SeedanceBatch(BaseTool):
    name = "seedance_batch"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "video_generation_planning"
    provider = "openmontage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies: list[str] = []
    install_instructions = "No external dependencies for dry-run planning."
    capabilities = [
        "seedance_batch_dry_run",
        "seedance_single_sample_execution",
        "production_plan_to_provider_tasks",
        "paid_generation_guard",
    ]
    supports = {
        "dry_run": True,
        "paid_generation": "sample_only_with_explicit_approval",
        "providers": list(PROVIDER_TOOLS),
        "max_generations_per_batch": MAX_GENERATIONS_PER_BATCH,
    }
    best_for = [
        "previewing exactly which Seedance clips would be generated from a production_plan",
        "checking batch size, output paths, prompts, and uploaded references before paid generation",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=1,
        ram_mb=128,
        vram_mb=0,
        disk_mb=20,
        network_required=False,
    )
    idempotency_key_fields = [
        "production_plan",
        "production_plan_path",
        "provider",
        "model_variant",
        "dry_run",
    ]
    side_effects = ["writes Seedance batch task JSON"]

    input_schema = {
        "type": "object",
        "required": ["project_dir"],
        "properties": {
            "project_dir": {"type": "string"},
            "production_plan": {"type": "object"},
            "production_plan_path": {"type": "string"},
            "provider": {
                "type": "string",
                "enum": list(PROVIDER_TOOLS),
                "default": "runninghub",
            },
            "model_variant": {
                "type": "string",
                "default": "sparkvideo-2.0-mini",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["adaptive", "16:9", "4:3", "1:1", "3:4", "9:16", "21:9"],
                "default": "9:16",
            },
            "generate_audio": {"type": "boolean", "default": True},
            "dry_run": {"type": "boolean", "default": True},
            "allow_paid_generation": {"type": "boolean", "default": False},
            "sample_only": {"type": "boolean", "default": True},
            "approval_phrase": {"type": "string"},
            "output_dir": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "seedance_batch": {"type": "object"},
            "json_path": {"type": "string"},
        },
    }

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        try:
            plan = _load_plan(inputs)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return ToolResult(success=False, error=str(exc))

        dry_run = bool(inputs.get("dry_run", True))
        if not dry_run and not inputs.get("allow_paid_generation"):
            return ToolResult(
                success=False,
                error="Paid Seedance generation requires allow_paid_generation=true and a separate explicit approval.",
            )
        if not dry_run and not inputs.get("sample_only", True):
            return ToolResult(
                success=False,
                error="Seedance paid execution is limited to sample_only=true in this tool.",
            )
        if not dry_run and inputs.get("approval_phrase") != SAMPLE_APPROVAL_PHRASE:
            return ToolResult(
                success=False,
                error=f"Paid Seedance sample requires approval_phrase={SAMPLE_APPROVAL_PHRASE!r}.",
            )

        errors = self._validate_plan(plan)
        if errors:
            return ToolResult(success=False, error="; ".join(errors))

        project_dir = Path(inputs["project_dir"])
        provider = str(inputs.get("provider", "runninghub"))
        if provider not in PROVIDER_TOOLS:
            return ToolResult(success=False, error=f"Unsupported Seedance provider: {provider}")

        batch = self._build_batch(plan, inputs, project_dir, provider)
        if not dry_run:
            return self._execute_sample(batch, inputs, project_dir)

        return self._write_batch_result(
            batch=batch,
            inputs=inputs,
            project_dir=project_dir,
            suffix="seedance-batch-dry-run",
        )

    def _write_batch_result(
        self,
        batch: dict[str, Any],
        inputs: dict[str, Any],
        project_dir: Path,
        suffix: str,
        extra_artifacts: list[str] | None = None,
        cost_usd: float = 0.0,
        model: str | None = None,
    ) -> ToolResult:
        output_dir = Path(inputs.get("output_dir") or project_dir / "artifacts")
        output_dir.mkdir(parents=True, exist_ok=True)
        source_name = _safe_slug(
            Path(
                str(
                    (batch.get("source") or {}).get("local_video_path")
                    or (batch.get("source") or {}).get("input")
                    or "reference"
                )
            ).stem
        )
        json_path = output_dir / f"{source_name}-{suffix}.json"
        json_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts = [str(json_path), *(extra_artifacts or [])]

        return ToolResult(
            success=True,
            data={"seedance_batch": batch, "json_path": str(json_path)},
            artifacts=artifacts,
            cost_usd=cost_usd,
            model=model,
        )

    def _execute_sample(
        self,
        batch: dict[str, Any],
        inputs: dict[str, Any],
        project_dir: Path,
    ) -> ToolResult:
        tasks = batch.get("tasks") or []
        if not tasks:
            return ToolResult(success=False, error="Seedance sample execution requires at least one task")

        task = dict(tasks[0])
        provider_inputs = {
            "prompt": task["prompt"],
            "operation": task["operation"],
            "model_variant": task["model_variant"],
            "duration": task["duration"],
            "resolution": task["resolution"],
            "aspect_ratio": task["aspect_ratio"],
            "generate_audio": task["generate_audio"],
            "image_paths": task.get("image_paths", []),
            "output_path": task["output_path"],
            "batch_size": 1,
        }
        provider_result = _provider_tool(str(batch["provider"])).execute(provider_inputs)
        if not provider_result.success:
            return ToolResult(
                success=False,
                error=provider_result.error or "Seedance sample generation failed",
                cost_usd=provider_result.cost_usd,
                model=provider_result.model,
            )

        batch["status"] = "sample_generated"
        batch["dry_run"] = False
        batch["executed_task"] = task
        batch["execution_result"] = provider_result.data
        batch["approval"] = {
            "paid_generation_started": True,
            "requires_explicit_generation_approval": True,
            "approval_phrase": SAMPLE_APPROVAL_PHRASE,
            "sample_only": True,
        }
        batch["next_actions"] = [
            "Review the generated sample clip before approving the rest of the batch.",
            "If approved, run the next paid sample or batch step explicitly.",
        ]
        return self._write_batch_result(
            batch=batch,
            inputs=inputs,
            project_dir=project_dir,
            suffix="seedance-sample-result",
            extra_artifacts=provider_result.artifacts,
            cost_usd=provider_result.cost_usd,
            model=provider_result.model,
        )

    def _validate_plan(self, plan: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        if plan.get("status") != "ready_for_production":
            errors.append("production_plan.status must be ready_for_production")
        if plan.get("target_mode") != "seedance":
            errors.append("production_plan.target_mode must be seedance-only in reference-video v1")
        if not (plan.get("scenes") or []):
            errors.append("production_plan.scenes must include at least one scene")
        constraint_error = validate_seedance_constraints(_constraint_inputs(plan))
        if constraint_error:
            errors.append(constraint_error)
        return errors

    def _build_batch(
        self,
        plan: dict[str, Any],
        inputs: dict[str, Any],
        project_dir: Path,
        provider: str,
    ) -> dict[str, Any]:
        constraints = _constraint_inputs(plan)
        batch_size = _batch_size(plan)
        scenes = list(plan.get("scenes") or [])
        selected_scenes = scenes[:batch_size]
        skipped_scenes = scenes[batch_size:]
        provider_tool = PROVIDER_TOOLS[provider]
        model_variant = str(inputs.get("model_variant", "sparkvideo-2.0-mini"))
        aspect_ratio = str(inputs.get("aspect_ratio", "9:16"))
        generate_audio = bool(inputs.get("generate_audio", True))

        tasks = [
            {
                "task_id": f"seedance-{_safe_slug(str(scene.get('scene_id') or index))}",
                "scene_id": scene.get("scene_id", f"s{index}"),
                "provider": provider,
                "provider_tool": provider_tool,
                "model_variant": model_variant,
                "operation": "image_to_video"
                if _asset_image_paths(project_dir, scene)
                else "text_to_video",
                "prompt": str(scene.get("seedance_prompt", "")).strip(),
                "script_text": str(scene.get("script_text", "")).strip(),
                "duration": constraints["duration"],
                "resolution": constraints["resolution"],
                "aspect_ratio": aspect_ratio,
                "generate_audio": generate_audio,
                "image_paths": _asset_image_paths(project_dir, scene),
                "selected_asset_ids": scene.get("selected_asset_ids", []),
                "output_path": str(
                    project_dir
                    / "assets"
                    / "video"
                    / f"{_safe_slug(str(scene.get('scene_id') or index))}-seedance.mp4"
                ),
            }
            for index, scene in enumerate(selected_scenes, start=1)
        ]

        return {
            "version": "1.0",
            "status": "dry_run_ready",
            "dry_run": True,
            "source": plan.get("source", {}),
            "provider": provider,
            "provider_tool": provider_tool,
            "model_variant": model_variant,
            "duration": constraints["duration"],
            "resolution": constraints["resolution"],
            "batch_size": batch_size,
            "max_generations_per_batch": MAX_GENERATIONS_PER_BATCH,
            "allowed_durations": list(ALLOWED_DURATIONS),
            "allowed_resolutions": list(ALLOWED_RESOLUTIONS),
            "tasks": tasks,
            "skipped_scene_ids": [
                str(scene.get("scene_id", f"s{index}"))
                for index, scene in enumerate(skipped_scenes, start=batch_size + 1)
            ],
            "approval": {
                "paid_generation_started": False,
                "requires_explicit_generation_approval": True,
            },
            "next_actions": [
                "Review every task prompt, selected asset, and output path.",
                "Run paid Seedance generation only after explicit approval.",
            ],
        }
