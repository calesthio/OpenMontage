"""Pipeline-agnostic headless stage executor for hosted Ray.

The hosted service is a transport in front of OpenMontage's real pipeline
contract. This executor loads manifests, director skills, schemas, checkpoints,
and tools from the repo, then enforces the hosted safety gates around them.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from lib.checkpoint import (
    CANONICAL_STAGE_ARTIFACTS,
    CheckpointValidationError,
    get_next_stage,
    init_project,
    write_checkpoint,
)
from lib.paths import PROJECTS_DIR
from lib.pipeline_loader import (
    get_stage_human_approval_default,
    get_stage_skill,
    load_pipeline,
)
from schemas.artifacts import load_schema, validate_artifact
from tools.base_tool import ToolRuntime
from tools.tool_registry import registry


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = REPO_ROOT / "skills"


class DirectorModelClient(Protocol):
    """Hosted LLM adapter used by the stage executor."""

    def step(self, messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Return a director step.

        Expected shape:
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
    preapprove_human_gates: bool = False
    approval_note: str | None = None


@dataclass(frozen=True)
class StageRunResult:
    project_id: str
    pipeline_type: str
    stage: str
    status: str
    blocker: str | None = None
    checkpoint_path: Path | None = None
    repo_sha: str | None = None
    artifact_name: str | None = None


class StageExecutionBlocked(RuntimeError):
    """Base class for executor-side guard failures."""


class BudgetExceeded(StageExecutionBlocked):
    """Raised before a provider call when a configured budget cap would trip."""


class IdempotencyBlocked(StageExecutionBlocked):
    """Raised when a ledger entry is present but not safely reusable."""


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
        repo_sha = current_git_sha()
        stage = request.stage or "research"
        checkpoint_path: Path | None = None
        artifact_name: str | None = None

        try:
            manifest = load_pipeline(request.pipeline_type)
            stage = request.stage or get_next_stage(
                self.projects_dir, request.project_id, request.pipeline_type
            ) or ""
            if not stage:
                return StageRunResult(
                    project_id=request.project_id,
                    pipeline_type=request.pipeline_type,
                    stage="",
                    status="complete",
                    repo_sha=repo_sha,
                )

            project_dir = init_project(
                request.project_id,
                title=request.title,
                pipeline_type=request.pipeline_type,
                pipeline_dir=self.projects_dir,
                style_playbook=request.style_playbook,
            )
            skill_source = self._skill_source_status(repo_sha)
            if skill_source["mode"] == "unpinned":
                raise StageExecutionBlocked("skills_not_pinned")

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
                    "skill_source": skill_source,
                },
            )

            if self.model_client is None:
                raise StageExecutionBlocked("director_model_client_not_wired")

            context = self.load_stage_context(manifest, stage, request, skill_source)
            response = self.run_guarded_loop(request, stage, context)
            artifact_name = str(response.get("artifact_name") or CANONICAL_STAGE_ARTIFACTS[stage])
            status, checkpoint_path = self._checkpoint_final_artifact(
                request=request,
                stage=stage,
                response=response,
                context=context,
                repo_sha=repo_sha,
            )
            return StageRunResult(
                project_id=request.project_id,
                pipeline_type=request.pipeline_type,
                stage=stage,
                status=status,
                checkpoint_path=checkpoint_path,
                repo_sha=repo_sha,
                artifact_name=artifact_name,
            )
        except Exception as exc:  # no guard trip escapes without a failed checkpoint
            blocker = self._blocker_code(exc)
            checkpoint_path = self._write_failed_checkpoint_safely(
                request=request,
                stage=stage,
                blocker=blocker,
                exc=exc,
                repo_sha=repo_sha,
            )
            return StageRunResult(
                project_id=request.project_id,
                pipeline_type=request.pipeline_type,
                stage=stage,
                status="blocked",
                blocker=blocker,
                checkpoint_path=checkpoint_path,
                repo_sha=repo_sha,
                artifact_name=artifact_name,
            )

    def load_stage_context(
        self,
        manifest: dict[str, Any],
        stage: str,
        request: StageRunRequest,
        skill_source: dict[str, Any],
    ) -> dict[str, Any]:
        skill_ref = get_stage_skill(manifest, stage)
        stage_skill = self._read_skill(skill_ref) if skill_ref else ""
        artifact_name = CANONICAL_STAGE_ARTIFACTS[stage]
        available_tool_names = self._allowed_tool_names_for_stage(manifest, stage)
        web_search_available = "web_search" in available_tool_names and registry.get("web_search") is not None
        research_mode = (
            "web_search"
            if stage != "research" or web_search_available
            else "recorded_only_no_web_search_tool"
        )
        return {
            "manifest": manifest,
            "stage": stage,
            "stage_skill_ref": skill_ref,
            "stage_skill": stage_skill,
            "checkpoint_protocol_summary": (
                "Write in_progress first. Validate canonical artifact. "
                "Human-gated stages write awaiting_human unless explicitly preapproved."
            ),
            "reviewer_summary": (
                "Validate schema first, then review manifest focus and success criteria. "
                "Do not pass artifacts with critical findings."
            ),
            "provider_menu_summary": self._provider_menu_summary(),
            "brief": request.brief,
            "prior_artifacts": self._load_existing_artifacts(request.project_id),
            "canonical_artifact_name": artifact_name,
            "canonical_artifact_schema": load_schema(artifact_name),
            "stage_definition": self._stage_definition(manifest, stage),
            "repo_sha": current_git_sha(),
            "skill_source": skill_source,
            "loaded_sources": self._loaded_source_records(skill_ref),
            "execution_constraints": {
                "m1_no_paid_media_generation": True,
                "research_execution_mode": research_mode,
                "preapprove_human_gates": request.preapprove_human_gates,
                "approval_note": request.approval_note,
            },
        }

    def run_guarded_loop(
        self,
        request: StageRunRequest,
        stage: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        if self.model_client is None:
            raise StageExecutionBlocked("director model client is not wired")

        started = time.monotonic()
        tool_calls = 0
        messages = [
            {
                "role": "system",
                "content": (
                    "You are an OpenMontage stage director executing one hosted "
                    "pipeline stage. Use the loaded director skill and return "
                    "only the requested JSON response shape."
                ),
            },
            {"role": "user", "content": json.dumps(context, default=str)},
        ]
        tools = self._allowed_tools_for_stage(context["manifest"], stage)
        allowed_tool_names = {tool["name"] for tool in tools if "name" in tool}
        artifact_name = CANONICAL_STAGE_ARTIFACTS[stage]

        for iteration in range(1, request.limits.max_llm_iterations + 1):
            if time.monotonic() - started > request.limits.wall_clock_timeout_seconds:
                raise TimeoutError(f"stage {stage} exceeded wall-clock limit")

            reserve_id = self._reserve_cost(
                request=request,
                stage=stage,
                tool="director_llm",
                operation=f"{stage}:iteration:{iteration}",
                estimated_usd=self._estimate_model_step_cost(messages, tools),
                category="llm",
            )
            try:
                response = self.model_client.step(messages, tools)
            except Exception:
                self._complete_cost(request.project_id, reserve_id, actual_usd=0.0, failed=True)
                raise
            self._complete_cost(
                request.project_id,
                reserve_id,
                actual_usd=(
                    float(response["cost_usd"])
                    if response.get("cost_usd") is not None
                    else None
                ),
            )

            response_type = response.get("type")
            if response_type == "final_artifact":
                try:
                    self._validate_final_response(stage, artifact_name, response)
                    return response
                except Exception as exc:
                    if iteration >= request.limits.max_llm_iterations:
                        raise
                    messages.append({"role": "assistant", "content": json.dumps(response, default=str)})
                    messages.append({
                        "role": "user",
                        "content": (
                            "The final artifact failed validation. Return a corrected "
                            f"final_artifact JSON object only. Validation error: {exc}"
                        ),
                    })
                    continue

            if response_type != "tool_call":
                raise RuntimeError(f"unknown director response type: {response_type!r}")

            tool_name = str(response.get("tool") or "")
            if tool_name not in allowed_tool_names:
                raise StageExecutionBlocked(f"tool_not_allowed_for_stage:{tool_name}")

            tool_calls += 1
            if tool_calls > request.limits.max_tool_calls:
                raise RuntimeError(f"stage {stage} exceeded tool-call limit")

            tool_result = self._execute_tool_call(
                request=request,
                stage=stage,
                tool_name=tool_name,
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
        key = str(arguments["idempotency_key"])
        cached = self._idempotency_hit(request.project_id, key)
        if cached is not None:
            return cached

        estimated = float(tool.estimate_cost(arguments) or 0.0)
        paid_provider_call = estimated > 0 or getattr(tool, "runtime", None) == ToolRuntime.API
        reserve_id = None
        if paid_provider_call:
            reserve_id = self._reserve_cost(
                request=request,
                stage=stage,
                tool=tool_name,
                operation=str(arguments.get("operation") or tool_name),
                estimated_usd=estimated,
                category="media",
            )
            self._idempotency_mark_pending(request.project_id, key, tool_name, arguments)

        try:
            result = tool.execute(arguments)
            payload = {
                "success": result.success,
                "data": result.data,
                "artifacts": result.artifacts,
                "error": result.error,
                "cost_usd": result.cost_usd,
                "duration_seconds": result.duration_seconds,
            }
            if paid_provider_call:
                actual_cost = float(result.cost_usd) if result.cost_usd else estimated
                self._complete_cost(request.project_id, reserve_id, actual_usd=actual_cost)
                self._idempotency_mark_completed(request.project_id, key, payload)
            return payload
        except Exception as exc:
            if paid_provider_call:
                self._complete_cost(request.project_id, reserve_id, actual_usd=0.0, failed=True)
                self._idempotency_mark_failed(request.project_id, key, str(exc))
            raise

    def _checkpoint_final_artifact(
        self,
        *,
        request: StageRunRequest,
        stage: str,
        response: dict[str, Any],
        context: dict[str, Any],
        repo_sha: str,
    ) -> tuple[str, Path]:
        artifact_name = CANONICAL_STAGE_ARTIFACTS[stage]
        artifact = response["artifact"]
        artifacts: dict[str, Any] = {artifact_name: artifact}
        supplementary = response.get("supplementary_artifacts") or {}
        if not isinstance(supplementary, dict):
            raise CheckpointValidationError("supplementary_artifacts must be an object")
        artifacts.update(supplementary)

        validate_artifact(artifact_name, artifact)
        review = response.get("review") if isinstance(response.get("review"), dict) else {
            "decision": "PASS",
            "summary": "Schema-valid hosted director artifact.",
            "findings": [],
        }
        metadata = {
            "repo_sha": repo_sha,
            "executor": "hosted_stage_executor",
            "stage_skill_ref": context.get("stage_skill_ref"),
            "skill_source": context.get("skill_source"),
            "loaded_sources": context.get("loaded_sources"),
            "execution_constraints": context.get("execution_constraints"),
            "director_metadata": response.get("metadata") if isinstance(response.get("metadata"), dict) else {},
        }
        cost_snapshot = self._cost_snapshot(request.project_id, request.budget_caps)
        human_required = bool(get_stage_human_approval_default(load_pipeline(request.pipeline_type), stage))
        status = "awaiting_human" if human_required else "completed"
        checkpoint_path = write_checkpoint(
            self.projects_dir,
            request.project_id,
            stage,
            status,
            artifacts,
            pipeline_type=request.pipeline_type,
            style_playbook=request.style_playbook,
            human_approval_required=human_required,
            review=review,
            cost_snapshot=cost_snapshot,
            metadata=metadata,
        )
        self._write_artifact_files(request.project_id, artifacts)

        if human_required and request.preapprove_human_gates:
            artifacts = self._with_preapproval_decision(
                artifacts=artifacts,
                project_id=request.project_id,
                stage=stage,
                note=request.approval_note or "M1 saree smoke preapproval.",
            )
            checkpoint_path = write_checkpoint(
                self.projects_dir,
                request.project_id,
                stage,
                "completed",
                artifacts,
                pipeline_type=request.pipeline_type,
                style_playbook=request.style_playbook,
                human_approval_required=True,
                human_approved=True,
                review=review,
                cost_snapshot=self._cost_snapshot(request.project_id, request.budget_caps),
                metadata={**metadata, "preapproved_human_gate": True},
            )
            self._write_artifact_files(request.project_id, artifacts)
            status = "completed"
        return status, checkpoint_path

    def _validate_final_response(
        self,
        stage: str,
        artifact_name: str,
        response: dict[str, Any],
    ) -> None:
        if response.get("artifact_name") and response["artifact_name"] != artifact_name:
            raise CheckpointValidationError(
                f"stage {stage} must produce {artifact_name}, got {response['artifact_name']}"
            )
        artifact = response.get("artifact")
        if not isinstance(artifact, dict):
            raise CheckpointValidationError("final_artifact response missing object artifact")
        validate_artifact(artifact_name, artifact)
        supplementary = response.get("supplementary_artifacts") or {}
        if supplementary and not isinstance(supplementary, dict):
            raise CheckpointValidationError("supplementary_artifacts must be an object")
        for name, data in supplementary.items():
            if isinstance(data, dict):
                validate_artifact(name, data)

    @staticmethod
    def _blocker_code(exc: Exception) -> str:
        message = str(exc)
        if isinstance(exc, BudgetExceeded):
            return "budget_cap_exceeded"
        if isinstance(exc, TimeoutError):
            return "loop_timeout"
        if isinstance(exc, CheckpointValidationError):
            return "checkpoint_validation_failed"
        if isinstance(exc, StageExecutionBlocked):
            return message or "stage_execution_blocked"
        if "exceeded LLM-iteration" in message:
            return "llm_iteration_limit"
        if "exceeded tool-call" in message:
            return "tool_call_limit"
        return exc.__class__.__name__

    def _write_failed_checkpoint_safely(
        self,
        *,
        request: StageRunRequest,
        stage: str,
        blocker: str,
        exc: Exception,
        repo_sha: str,
    ) -> Path | None:
        try:
            init_project(
                request.project_id,
                title=request.title,
                pipeline_type=request.pipeline_type,
                pipeline_dir=self.projects_dir,
                style_playbook=request.style_playbook,
            )
            return write_checkpoint(
                self.projects_dir,
                request.project_id,
                stage,
                "failed",
                {},
                pipeline_type=request.pipeline_type,
                style_playbook=request.style_playbook,
                error=str(exc),
                cost_snapshot=self._cost_snapshot(request.project_id, request.budget_caps),
                metadata={
                    "repo_sha": repo_sha,
                    "executor": "hosted_stage_executor",
                    "blocker": blocker,
                },
            )
        except Exception:
            return None

    def _reserve_cost(
        self,
        *,
        request: StageRunRequest,
        stage: str,
        tool: str,
        operation: str,
        estimated_usd: float,
        category: str,
    ) -> str:
        entry_id = hashlib.sha256(
            f"{request.project_id}:{stage}:{tool}:{operation}:{time.time_ns()}".encode("utf-8")
        ).hexdigest()[:16]
        log = self._read_cost_log(request.project_id, request.budget_caps)
        spent = self._cost_totals(log)
        projected_total = spent["total_active"] + estimated_usd
        projected_category = spent.get(f"{category}_active", 0.0) + estimated_usd
        if projected_total > request.budget_caps.total_budget_cap_usd:
            raise BudgetExceeded(
                f"total budget cap would be exceeded: {projected_total:.4f} > "
                f"{request.budget_caps.total_budget_cap_usd:.4f}"
            )
        category_cap = (
            request.budget_caps.llm_budget_cap_usd
            if category == "llm"
            else request.budget_caps.media_budget_cap_usd
        )
        if projected_category > category_cap:
            raise BudgetExceeded(
                f"{category} budget cap would be exceeded: {projected_category:.4f} > "
                f"{category_cap:.4f}"
            )
        if estimated_usd <= 0:
            return entry_id
        log["entries"].append({
            "id": entry_id,
            "tool": tool,
            "operation": operation,
            "status": "reserved",
            "timestamp": self._now_iso(),
            "estimated_usd": round(estimated_usd, 6),
            "reserved_usd": round(estimated_usd, 6),
            "details": json.dumps({"category": category, "stage": stage}, sort_keys=True),
        })
        self._write_cost_log(request.project_id, log)
        return entry_id

    def _complete_cost(
        self,
        project_id: str,
        entry_id: str | None,
        *,
        actual_usd: float | None,
        failed: bool = False,
    ) -> None:
        if not entry_id:
            return
        log = self._read_cost_log(project_id, BudgetCaps())
        for entry in log.get("entries", []):
            if entry.get("id") == entry_id:
                entry["status"] = "failed" if failed else "completed"
                entry["timestamp"] = self._now_iso()
                settled = (
                    float(actual_usd)
                    if actual_usd is not None
                    else float(entry.get("estimated_usd") or 0.0)
                )
                entry["actual_usd"] = round(settled, 6)
                entry.pop("reserved_usd", None)
                self._write_cost_log(project_id, log)
                return

    def _cost_snapshot(self, project_id: str, caps: BudgetCaps) -> dict[str, Any]:
        log = self._read_cost_log(project_id, caps)
        totals = self._cost_totals(log)
        return {
            "budget_caps": caps.__dict__,
            "spent_usd": round(totals["spent"], 6),
            "reserved_usd": round(totals["reserved"], 6),
            "total_active_usd": round(totals["total_active"], 6),
            "entries": len(log.get("entries", [])),
        }

    def _read_cost_log(self, project_id: str, caps: BudgetCaps) -> dict[str, Any]:
        path = self.projects_dir / project_id / "artifacts" / "cost_log.json"
        if path.is_file():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("entries"), list):
                    return data
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "version": "1.0",
            "budget_total_usd": caps.total_budget_cap_usd,
            "budget_reserved_usd": 0.0,
            "budget_spent_usd": 0.0,
            "entries": [],
        }

    def _write_cost_log(self, project_id: str, log: dict[str, Any]) -> None:
        totals = self._cost_totals(log)
        log["budget_reserved_usd"] = round(totals["reserved"], 6)
        log["budget_spent_usd"] = round(totals["spent"], 6)
        path = self.projects_dir / project_id / "artifacts" / "cost_log.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)

    @staticmethod
    def _cost_totals(log: dict[str, Any]) -> dict[str, float]:
        totals = {
            "spent": 0.0,
            "reserved": 0.0,
            "total_active": 0.0,
            "llm_active": 0.0,
            "media_active": 0.0,
        }
        for entry in log.get("entries", []):
            status = entry.get("status")
            amount = 0.0
            if status == "completed":
                amount = float(entry.get("actual_usd") or entry.get("estimated_usd") or 0.0)
                totals["spent"] += amount
            elif status == "reserved":
                amount = float(entry.get("reserved_usd") or entry.get("estimated_usd") or 0.0)
                totals["reserved"] += amount
            else:
                continue
            totals["total_active"] += amount
            category = "media"
            try:
                details = json.loads(entry.get("details") or "{}")
                category = str(details.get("category") or category)
            except json.JSONDecodeError:
                pass
            if category == "llm":
                totals["llm_active"] += amount
            elif category == "media":
                totals["media_active"] += amount
        return totals

    def _idempotency_hit(self, project_id: str, key: str) -> dict[str, Any] | None:
        ledger = self._read_idempotency_ledger(project_id)
        entry = (ledger.get("entries") or {}).get(key)
        if not entry:
            return None
        if entry.get("status") == "completed" and isinstance(entry.get("result"), dict):
            result = dict(entry["result"])
            result["cached_from_idempotency"] = True
            return result
        raise IdempotencyBlocked(f"idempotency key {key} is {entry.get('status')}")

    def _idempotency_mark_pending(
        self,
        project_id: str,
        key: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> None:
        ledger = self._read_idempotency_ledger(project_id)
        ledger.setdefault("entries", {})[key] = {
            "status": "pending",
            "tool": tool_name,
            "arguments_hash": hashlib.sha256(
                json.dumps(arguments, sort_keys=True, default=str).encode("utf-8")
            ).hexdigest(),
            "timestamp": self._now_iso(),
        }
        self._write_idempotency_ledger(project_id, ledger)

    def _idempotency_mark_completed(self, project_id: str, key: str, result: dict[str, Any]) -> None:
        ledger = self._read_idempotency_ledger(project_id)
        ledger.setdefault("entries", {}).setdefault(key, {})
        ledger["entries"][key].update({
            "status": "completed",
            "result": result,
            "timestamp": self._now_iso(),
        })
        self._write_idempotency_ledger(project_id, ledger)

    def _idempotency_mark_failed(self, project_id: str, key: str, error: str) -> None:
        ledger = self._read_idempotency_ledger(project_id)
        ledger.setdefault("entries", {}).setdefault(key, {})
        ledger["entries"][key].update({
            "status": "failed",
            "error": error,
            "timestamp": self._now_iso(),
        })
        self._write_idempotency_ledger(project_id, ledger)

    def _read_idempotency_ledger(self, project_id: str) -> dict[str, Any]:
        path = self.projects_dir / project_id / "artifacts" / "idempotency_ledger.json"
        if path.is_file():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("entries", {})
                    return data
            except (OSError, json.JSONDecodeError):
                pass
        return {"version": "1.0", "entries": {}}

    def _write_idempotency_ledger(self, project_id: str, ledger: dict[str, Any]) -> None:
        path = self.projects_dir / project_id / "artifacts" / "idempotency_ledger.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ledger, f, indent=2)

    def _write_artifact_files(self, project_id: str, artifacts: dict[str, Any]) -> None:
        art_dir = self.projects_dir / project_id / "artifacts"
        art_dir.mkdir(parents=True, exist_ok=True)
        for name, value in artifacts.items():
            if not isinstance(value, dict):
                continue
            path = art_dir / f"{name}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(value, f, indent=2)

    def _load_existing_artifacts(self, project_id: str) -> dict[str, Any]:
        project_dir = self.projects_dir / project_id
        artifacts: dict[str, Any] = {}
        art_dir = project_dir / "artifacts"
        if art_dir.is_dir():
            for path in sorted(art_dir.glob("*.json")):
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        artifacts[path.stem] = data
                except (OSError, json.JSONDecodeError):
                    continue
        for path in sorted(project_dir.glob("checkpoint_*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    checkpoint = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            for name, value in (checkpoint.get("artifacts") or {}).items():
                if isinstance(value, dict):
                    artifacts.setdefault(name, value)
        return artifacts

    def _with_preapproval_decision(
        self,
        *,
        artifacts: dict[str, Any],
        project_id: str,
        stage: str,
        note: str,
    ) -> dict[str, Any]:
        out = dict(artifacts)
        decision_log = out.get("decision_log")
        if not isinstance(decision_log, dict):
            decision_log = {"version": "1.0", "project_id": project_id, "decisions": []}
        decisions = decision_log.setdefault("decisions", [])
        decision_id = f"m1-preapprove-{stage}"
        if not any(item.get("decision_id") == decision_id for item in decisions if isinstance(item, dict)):
            decisions.append({
                "decision_id": decision_id,
                "stage": stage,
                "category": "approval_policy",
                "subject": f"M1 demo preapproval for {stage}",
                "options_considered": [
                    {
                        "option_id": "stop_at_gate",
                        "label": "Stop at human gate",
                        "score": 0.5,
                        "reason": "Default upstream behavior for creative approvals.",
                    },
                    {
                        "option_id": "preapprove_for_smoke",
                        "label": "Preapprove M1 smoke",
                        "score": 1.0,
                        "reason": "User explicitly accepted saree job through scene_plan as M1 acceptance.",
                    },
                ],
                "selected": "preapprove_for_smoke",
                "reason": note,
                "user_visible": True,
                "user_approved": True,
                "confidence": 1.0,
            })
        out["decision_log"] = decision_log
        return out

    @staticmethod
    def _estimate_model_step_cost(messages: list[dict[str, str]], tools: list[dict[str, Any]]) -> float:
        chars = len(json.dumps(messages, default=str)) + len(json.dumps(tools, default=str))
        estimated_tokens = max(1, chars // 4)
        # Conservative enough to trip tiny caps before a hosted LLM call while
        # keeping M1 planning well under normal caps.
        return round((estimated_tokens / 1000.0) * 0.0008, 6)

    @staticmethod
    def _allowed_tool_names_for_stage(manifest: dict[str, Any], stage: str) -> set[str]:
        for stage_def in manifest.get("stages", []):
            if stage_def.get("name") != stage:
                continue
            return set(stage_def.get("tools_available", []) + stage_def.get("required_tools", []))
        return set()

    @staticmethod
    def _allowed_tools_for_stage(manifest: dict[str, Any], stage: str) -> list[dict[str, Any]]:
        names = sorted(StageExecutor._allowed_tool_names_for_stage(manifest, stage))
        registry.discover()
        return [
            registry.get(name).get_info()
            for name in names
            if registry.get(name) is not None
        ]

    @staticmethod
    def _provider_menu_summary() -> dict[str, Any]:
        registry.discover()
        return registry.provider_menu_summary()

    @staticmethod
    def _stage_definition(manifest: dict[str, Any], stage: str) -> dict[str, Any]:
        for stage_def in manifest.get("stages", []):
            if stage_def.get("name") == stage:
                return dict(stage_def)
        return {}

    @staticmethod
    def _read_skill(skill_ref: str | None) -> str:
        if not skill_ref:
            return ""
        path = SKILLS_DIR / f"{skill_ref}.md"
        if not path.is_file():
            raise FileNotFoundError(f"stage skill not found: {path}")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def _file_record(path: Path, repo_sha: str) -> dict[str, Any]:
        content = path.read_text(encoding="utf-8")
        return {
            "path": str(path.relative_to(REPO_ROOT)),
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "repo_sha": repo_sha,
        }

    def _loaded_source_records(self, skill_ref: str | None) -> list[dict[str, Any]]:
        repo_sha = current_git_sha()
        files = [
            REPO_ROOT / "AGENT_GUIDE.md",
            SKILLS_DIR / "meta/checkpoint-protocol.md",
            SKILLS_DIR / "meta/reviewer.md",
        ]
        if skill_ref:
            files.append(SKILLS_DIR / f"{skill_ref}.md")
        return [self._file_record(path, repo_sha) for path in files if path.is_file()]

    @staticmethod
    def _skill_source_status(repo_sha: str) -> dict[str, Any]:
        if not repo_sha or repo_sha == "unknown":
            return {
                "mode": "unpinned",
                "reason": "RAY_REPO_SHA/git SHA unavailable; production execution blocked.",
            }
        return {"mode": "pinned_sha", "repo_sha": repo_sha}

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
