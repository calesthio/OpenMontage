"""Shared DreamAPI tool behavior. Subclasses set the capability and default output name."""

from __future__ import annotations

from abc import abstractmethod
import time
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
from tools.dreamapi_client import INSTALL_INSTRUCTIONS, DreamApiError, execute_catalog, get_api_key
from tools.dreamapi_models import models_for


class DreamApiTool(BaseTool):
    version = "0.1.0"
    tier = ToolTier.GENERATE
    provider = "dreamapi"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API
    dependencies = ["env:DREAMAPI_API_KEY"]
    install_instructions = INSTALL_INSTRUCTIONS
    agent_skills = ["dreamapi"]
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, disk_mb=250, network_required=True)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    side_effects = ["writes media files under output_path", "calls the DreamAPI account that owns DREAMAPI_API_KEY"]
    user_visible_verification = ["Inspect the saved artifact before using it in a later stage"]
    default_output = "dreamapi.bin"
    supports = {"multi_model_gateway": True, "bring_your_own_key": True}
    not_good_for = ["offline generation", "assuming one request schema fits every DreamAPI model"]
    fallback_tools: list[str] = []

    @abstractmethod
    def _dreamapi_concrete(self) -> None:
        """Marks this base class abstract so the registry does not instantiate it."""

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if get_api_key() else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["model_catalog"] = {
            model_id: {"note": spec["note"], "endpoint": spec["endpoint"], "capability": spec["capability"]}
            for model_id, spec in models_for(self.capability).items()
        }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float | None:
        return None

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        try:
            data = execute_catalog(self.capability, inputs, self.default_output)
        except (DreamApiError, ValueError) as exc:
            return ToolResult(success=False, error=str(exc))
        except Exception as exc:  # noqa: BLE001 — provider failures stay inside ToolResult
            return ToolResult(success=False, error=f"DreamAPI request failed: {exc}")
        return ToolResult(
            success=True,
            data=data,
            artifacts=list(data["outputs"]),
            duration_seconds=round(time.time() - started, 2),
            model=str(inputs.get("model") or ""),
            cost_usd=None,
        )
