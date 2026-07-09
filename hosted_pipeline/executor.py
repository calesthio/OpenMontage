"""Pipeline-agnostic headless stage executor skeleton for hosted Ray.

This module is intentionally infrastructure-only. It does not contain
cinematic-specific prompts or creative decisions; it loads the same manifests,
director skills, schemas, checkpoints, and tool registry that an OpenMontage
agent would use interactively.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from lib.checkpoint import get_next_stage, init_project, write_checkpoint
from lib.paths import PROJECTS_DIR
from lib.pipeline_loader import get_stage_skill, load_pipeline
from tools.tool_registry import registry


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"


class DirectorModelClient(Protocol):
    """Protocol for the hosted LLM adapter wired in M1 implementation."""

    def step(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Return one director-model step.

        Expected shape for the implementation:
        {"type": "tool_call", "tool": "video_selector", "arguments": {...}}
        or {"type": "final_artifact", "artifact_name": "...", "artifact": {...}}.
        """


@dataclass(frozen=True)
class LoopLimits:
    max_llm_iterations: int = int(os.environ.get("RAY_STAGE_MAX_LLM_ITERATIONS", "8"))
    max_tool_calls: int = int(os.environ.get("RAY_STAGE_MAX_TOOL_CALLS", "24"))
    wall_clock_timeout_seconds: int = int(
        os.environ.get("RAY_STAGE_WALL_CLOCK_TIMEOUT_SECONDS", "900")
    )


@dataclass(frozen=True)
class BudgetCaps:
    total_budget_cap_usd: float = 10.0
    llm_budget_cap_usd: float = 3.0
    media_budget_cap_usd: float = 7.0
    sample_budget_cap_usd: float = 1.0


@dataclass(frozen=True)
class StageRunRequest:
    project_id: str
    title: str
    pipeline_type: str
    stage: str | None = None
    brief: str = ""
    style_playbook: str | None = None
    attempt: int = 1
    budget_caps: BudgetCaps = field(default_factory=BudgetCaps)
    limits: LoopLimits = field(default_factory=LoopLimits)


@dataclass(frozen=True)
class StageRunResult:
    project_id: str
    pipeline_type: str
    stage: str
    status: str
    blocker: str | None = None
    checkpoint_path: Path | None = None
    repo_sha: str | None = None


def current_git_sha() -> str:
    env_sha = os.environ.get("RAY_REPO_SHA")
    if env_sha:
        return env_sha
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else "unknown"


def paid_call_idempotency_key(
    *,
    project_id: str,
    stage: str,
    scene_id: str | None,
    attempt: int,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    payload = json.dumps(arguments, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    scene = scene_id or "stage"
    return f"{project_id}:{stage}:{scene}:attempt-{attempt}:{tool_name}:{digest}"


class StageExecutor:
    """Thin hosted transport for the real OpenMontage stage contract."""

    def __init__(
        self,
        *,
        projects_dir: Path = PROJECTS_DIR,
        model_client: DirectorModelClient | None = None,
    ) -> None:
        self.projects_dir = projects_dir
        self.model_client = model_client

    def run_stage(self, request: StageRunRequest) -> StageRunResult:
        manifest = load_pipeline(request.pipeline_type)
        stage = request.stage or get_next_stage(
            self.projects_dir, request.project_id, request.pipeline_type
        )
        if not stage:
            return StageRunResult(
                project_id=request.project_id,
                pipeline_type=request.pipeline_type,
                stage="",
                status="complete",
                repo_sha=current_git_sha(),
            )

        project_dir = init_project(
            request.project_id,
            title=request.title,
            pipeline_type=request.pipeline_type,
            pipeline_dir=self.projects_dir,
            style_playbook=request.style_playbook,
        )
        repo_sha = current_git_sha()
        checkpoint_path = write_checkpoint(
            self.projects_dir,
            request.project_id,
            stage,
            "in_progress",
            {},
            pipeline_type=request.pipeline_type,
            style_playbook=request.style_playbook,
            metadata={
                "repo_sha": repo_sha,
                "executor": "hosted_stage_executor",
                "loop_limits": request.limits.__dict__,
                "budget_caps": request.budget_caps.__dict__,
            },
        )

        if self.model_client is None:
            blocker = "director_model_client_not_wired"
            checkpoint_path = write_checkpoint(
                self.projects_dir,
                request.project_id,
                stage,
                "failed",
                {},
                pipeline_type=request.pipeline_type,
                style_playbook=request.style_playbook,
                error=blocker,
                metadata={
                    "repo_sha": repo_sha,
                    "executor": "hosted_stage_executor",
                    "project_dir": str(project_dir),
                },
            )
            return StageRunResult(
                project_id=request.project_id,
                pipeline_type=request.pipeline_type,
                stage=stage,
                status="blocked",
                blocker=blocker,
                checkpoint_path=checkpoint_path,
                repo_sha=repo_sha,
            )

        context = self.load_stage_context(manifest, stage, request)
        self.run_guarded_loop(request, stage, context)
        return StageRunResult(
            project_id=request.project_id,
            pipeline_type=request.pipeline_type,
            stage=stage,
            status="in_progress",
            checkpoint_path=checkpoint_path,
            repo_sha=repo_sha,
        )

    def load_stage_context(
        self,
        manifest: dict[str, Any],
        stage: str,
        request: StageRunRequest,
    ) -> dict[str, Any]:
        skill_ref = get_stage_skill(manifest, stage)
        stage_skill = self._read_skill(skill_ref) if skill_ref else ""
        return {
            "agent_guide": (REPO_ROOT / "AGENT_GUIDE.md").read_text(encoding="utf-8"),
            "manifest": manifest,
            "stage": stage,
            "stage_skill_ref": skill_ref,
            "stage_skill": stage_skill,
            "checkpoint_protocol": self._read_skill("meta/checkpoint-protocol"),
            "reviewer": self._read_skill("meta/reviewer"),
            "provider_menu_summary": self._provider_menu_summary(),
            "brief": request.brief,
            "repo_sha": current_git_sha(),
        }

    def run_guarded_loop(
        self,
        request: StageRunRequest,
        stage: str,
        context: dict[str, Any],
    ) -> None:
        if self.model_client is None:
            raise RuntimeError("director model client is not wired")

        started = time.monotonic()
        tool_calls = 0
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an OpenMontage stage director. Follow the loaded "
                    "manifest, director skill, checkpoint protocol, and tool registry."
                ),
            },
            {"role": "user", "content": json.dumps(context, default=str)},
        ]
        tools = self._allowed_tools_for_stage(context["manifest"], stage)

        for iteration in range(1, request.limits.max_llm_iterations + 1):
            if time.monotonic() - started > request.limits.wall_clock_timeout_seconds:
                raise TimeoutError(f"stage {stage} exceeded wall-clock limit")

            response = self.model_client.step(messages, tools)
            response_type = response.get("type")
            if response_type == "final_artifact":
                return
            if response_type != "tool_call":
                raise RuntimeError(f"unknown director response type: {response_type!r}")

            tool_calls += 1
            if tool_calls > request.limits.max_tool_calls:
                raise RuntimeError(f"stage {stage} exceeded tool-call limit")

            tool_result = self._execute_tool_call(
                request=request,
                stage=stage,
                tool_name=response["tool"],
                arguments=response.get("arguments") or {},
            )
            messages.append({"role": "assistant", "content": json.dumps(response, default=str)})
            messages.append({"role": "tool", "content": json.dumps(tool_result, default=str)})

        raise RuntimeError(f"stage {stage} exceeded LLM-iteration limit")

    def _execute_tool_call(
        self,
        *,
        request: StageRunRequest,
        stage: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        tool = registry.get(tool_name)
        if tool is None:
            registry.discover()
            tool = registry.get(tool_name)
        if tool is None:
            raise RuntimeError(f"tool not found: {tool_name}")

        scene_id = str(arguments.get("scene_id") or "") or None
        arguments.setdefault(
            "idempotency_key",
            paid_call_idempotency_key(
                project_id=request.project_id,
                stage=stage,
                scene_id=scene_id,
                attempt=request.attempt,
                tool_name=tool_name,
                arguments=arguments,
            ),
        )
        result = tool.execute(arguments)
        return {
            "success": result.success,
            "data": result.data,
            "artifacts": result.artifacts,
            "error": result.error,
            "cost_usd": result.cost_usd,
            "duration_seconds": result.duration_seconds,
        }

    @staticmethod
    def _allowed_tools_for_stage(manifest: dict[str, Any], stage: str) -> list[dict[str, Any]]:
        for stage_def in manifest.get("stages", []):
            if stage_def.get("name") != stage:
                continue
            names = sorted(set(stage_def.get("tools_available", []) + stage_def.get("required_tools", [])))
            registry.discover()
            return [
                registry.get(name).get_info()
                for name in names
                if registry.get(name) is not None
            ]
        return []

    @staticmethod
    def _provider_menu_summary() -> dict[str, Any]:
        registry.discover()
        return registry.provider_menu_summary()

    @staticmethod
    def _read_skill(skill_ref: str | None) -> str:
        if not skill_ref:
            return ""
        path = SKILLS_DIR / f"{skill_ref}.md"
        if not path.is_file():
            raise FileNotFoundError(f"stage skill not found: {path}")
        return path.read_text(encoding="utf-8")
