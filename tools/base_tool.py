"""Base tool class implementing the expanded ToolContract.

Every tool in OpenMontage inherits from BaseTool. This enforces a uniform
interface for discovery, execution, cost estimation, and health reporting.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import json
import math
import os
import platform
import subprocess
import shutil
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional


def _load_dotenv() -> None:
    """Load .env into os.environ once at import time.

    This ensures API keys are available before any tool is instantiated,
    even when tools are imported directly without going through the registry.
    Only sets variables that are not already in the environment.
    """
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.is_file():
        return
    import re
    with open(env_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            # Quoted value: take the content inside the quotes verbatim.
            if value[:1] in ("'", '"'):
                quote = value[0]
                end = value.find(quote, 1)
                value = value[1:end] if end != -1 else value[1:]
            else:
                # Strip an inline comment ('#' at line start or after
                # whitespace) so "VAR=   # note" yields "" not "# note".
                match = re.search(r"(^|\s)#", value)
                if match:
                    value = value[: match.start()]
                value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


class ToolTier(str, Enum):
    CORE = "core"
    VOICE = "voice"
    ENHANCE = "enhance"
    GENERATE = "generate"
    SOURCE = "source"
    ANALYZE = "analyze"
    PUBLISH = "publish"


class ToolStability(str, Enum):
    EXPERIMENTAL = "experimental"
    BETA = "beta"
    PRODUCTION = "production"


class ToolStatus(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    DEGRADED = "degraded"


class ToolRuntime(str, Enum):
    """Where and how a tool executes."""
    LOCAL = "local"            # Runs entirely on-device, free, no network
    LOCAL_GPU = "local_gpu"    # Runs on-device but needs GPU (VRAM)
    API = "api"                # Calls an external API, requires API key, costs money
    HYBRID = "hybrid"          # Can run locally OR via API (e.g., image_selector)


class ExecutionMode(str, Enum):
    SYNC = "sync"
    ASYNC = "async"


class Determinism(str, Enum):
    DETERMINISTIC = "deterministic"
    SEEDED = "seeded"
    STOCHASTIC = "stochastic"


class ResumeSupport(str, Enum):
    NONE = "none"
    FROM_START = "from_start"
    FROM_CHECKPOINT = "from_checkpoint"


@dataclass
class ResourceProfile:
    """Hardware resource envelope for a tool."""
    cpu_cores: int = 1
    ram_mb: int = 512
    vram_mb: int = 0
    disk_mb: int = 100
    network_required: bool = False


@dataclass
class RetryPolicy:
    """Safe retry behavior for a tool."""
    max_retries: int = 0
    backoff_seconds: float = 1.0
    retryable_errors: list[str] = field(default_factory=list)


@dataclass
class ToolResult:
    """Standard result returned by tool execution."""
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    error: Optional[str] = None
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    seed: Optional[int] = None
    model: Optional[str] = None


import threading as _threading

# Shared nesting counter for instrumented execute() calls (thread-local so
# parallel tool threads don't see each other's depth).
_EXECUTE_DEPTH = _threading.local()


def _instrument_execute(fn: Callable) -> Callable:
    """Wrap a tool's execute() with Backlot event emission.

    Appends start/finish/error entries to the owning project's events.jsonl
    when the call can be attributed to a project (explicit project_dir input
    or any path input under projects/). Powers the board's live activity
    ticker and per-scene generating states with zero agent involvement.

    Instrumentation is strictly non-fatal: any failure inside the event layer
    is swallowed and the tool call proceeds untouched.
    """
    if getattr(fn, "_backlot_instrumented", False):
        return fn

    depth_state = _EXECUTE_DEPTH  # shared across all tools (selector → provider)

    @functools.wraps(fn)
    def wrapper(self, inputs: Any, *args: Any, **kwargs: Any):
        # Event layer is fully optional: if it can't import, run untouched.
        try:
            from lib.events import emit_event, infer_project_dir
        except Exception:
            return fn(self, inputs, *args, **kwargs)

        tool_name = getattr(self, "name", "") or self.__class__.__name__
        scene_id = inputs.get("scene_id") if isinstance(inputs, dict) else None
        output_path = inputs.get("output_path") if isinstance(inputs, dict) else None
        # Nesting depth: selector tools delegate to provider tools' execute().
        # Both emit (the ticker wants the provider name too), but depth lets
        # consumers dedupe — e.g. sum cost_usd only at depth 0.
        depth = getattr(depth_state, "value", 0)
        depth_state.value = depth + 1
        project_dir = infer_project_dir(inputs)

        base = {
            "tool": tool_name,
            "scene_id": scene_id,
            "depth": depth if depth else None,
        }
        if project_dir is not None:
            emit_event(project_dir, {
                **base, "event": "start",
                "output_path": str(output_path) if output_path else None,
            })

        started = time.monotonic()
        try:
            result = fn(self, inputs, *args, **kwargs)
        except Exception as exc:
            if project_dir is not None:
                emit_event(project_dir, {
                    **base, "event": "error",
                    "error": str(exc)[:300],
                    "duration_s": round(time.monotonic() - started, 2),
                })
            raise
        finally:
            depth_state.value = depth

        if project_dir is None:
            # The tool may have created its own project dir during execute
            # (first call of a run) — attribute the finish if possible.
            project_dir = infer_project_dir(inputs)
        if project_dir is not None:
            cost = getattr(result, "cost_usd", None)
            emit_event(project_dir, {
                **base, "event": "finish",
                "output_path": str(output_path) if output_path else None,
                "success": getattr(result, "success", None),
                # NOTE: 0.0 is meaningful (ran for free) — only None is dropped.
                "cost_usd": cost if isinstance(cost, (int, float)) else None,
                "duration_s": round(time.monotonic() - started, 2),
            })
        return result

    wrapper._backlot_instrumented = True  # type: ignore[attr-defined]
    return wrapper


def _enforce_budget(fn: Callable) -> Callable:
    """Wrap a tool's execute() with the budget hard cap.

    This is the choke point: every paid provider call in OpenMontage goes
    through a BaseTool.execute(), so gating here covers every tool that exists
    and every tool added later, with no per-tool wiring to forget.

    Unlike the event layer above, this wrapper is strictly FAIL-CLOSED. If the
    budget cannot be evaluated -- bad config, unreadable cost log, a paid tool
    with a broken estimate_cost() -- the call is refused rather than allowed.

    What is reserved is max_cost_usd(), NOT estimate_cost(). estimate_cost()
    is an approximation whose errors across this repo are biased downward (see
    the `.get(model, <cheap default>)` pattern), so reserving it would let a
    day's true spend exceed the cap. A tool that cannot state a defensible
    upper bound is refused by name rather than gambling the cap on a guess.

    Untouched paths (no tracker involvement, no cost log written):
      - runtime LOCAL / LOCAL_GPU  (FFmpeg, Remotion, HyperFrames, Piper, ...)
      - any tool whose estimate_cost() is 0  (free operations)
    This is what preserves the zero-key and local pipelines exactly.
    """
    if getattr(fn, "_budget_enforced", False):
        return fn

    @functools.wraps(fn)
    def wrapper(self, inputs: Any, *args: Any, **kwargs: Any):
        # Selectors delegate to provider tools; both reach this wrapper. Gate
        # only the outermost call, or one logical spend would reserve twice.
        if getattr(_EXECUTE_DEPTH, "value", 0) != 0:
            return fn(self, inputs, *args, **kwargs)

        runtime = getattr(self, "runtime", ToolRuntime.LOCAL)
        if runtime in (ToolRuntime.LOCAL, ToolRuntime.LOCAL_GPU):
            return fn(self, inputs, *args, **kwargs)

        tool_name = getattr(self, "name", "") or type(self).__name__
        safe_inputs = inputs if isinstance(inputs, dict) else {}

        estimated = self.estimate_cost(safe_inputs)
        if not isinstance(estimated, (int, float)) or isinstance(estimated, bool):
            raise BudgetGateError(
                f"{tool_name}.estimate_cost() returned {estimated!r}; a tool that "
                f"can spend money must return a number. Refusing to execute "
                f"(fail closed)."
            )
        if estimated <= 0:
            return fn(self, inputs, *args, **kwargs)

        bound = self.max_cost_usd(safe_inputs)
        if bound is None:
            raise BudgetGateError(
                f"{tool_name} cannot declare a bounded maximum cost for this call "
                f"(estimate ${float(estimated):.2f}). Refusing to execute (fail "
                f"closed): a daily hard cap cannot be guaranteed against an "
                f"unbounded cost. estimate_cost() is an approximation, not a "
                f"ceiling. Override max_cost_usd() on {tool_name} to declare a "
                f"defensible upper bound -- it must cover every provider request "
                f"the call can make, including retry_policy.max_retries."
            )
        if (
            isinstance(bound, bool)
            or not isinstance(bound, (int, float))
            or not math.isfinite(bound)
            or bound < 0
        ):
            raise BudgetGateError(
                f"{tool_name}.max_cost_usd() returned {bound!r}; a bound must be "
                f"finite and non-negative. Refusing to execute (fail closed)."
            )
        if float(bound) - float(estimated) < -1e-6:
            raise BudgetGateError(
                f"{tool_name}.max_cost_usd() returned ${float(bound):.4f}, which is "
                f"below its own estimate_cost() of ${float(estimated):.4f}. That is "
                f"not an upper bound. Refusing to execute (fail closed)."
            )

        from lib.budget_gate import reserve, settle

        # Reserve the BOUND. Actual spend replaces it at reconcile.
        handle = reserve(tool_name, "execute", float(bound))
        try:
            result = fn(self, inputs, *args, **kwargs)
        except BaseException:
            # Includes KeyboardInterrupt/cancellation. The provider may already
            # have billed, so charge the bound rather than release. Never leave
            # the reservation unresolved.
            settle(handle, None, success=False)
            raise
        actual = getattr(result, "cost_usd", None)
        settle(
            handle,
            actual if isinstance(actual, (int, float)) else None,
            success=bool(getattr(result, "success", True)),
        )
        return result

    wrapper._budget_enforced = True  # type: ignore[attr-defined]
    return wrapper


class BudgetGateError(Exception):
    """Raised when a paid call's cost cannot be bounded before dispatch."""
    pass


class BaseTool(ABC):
    """Abstract base class for all OpenMontage tools."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-instrument every concrete execute() with events + budget gate.

        The budget gate wraps outermost so it reads the nesting depth before
        the event layer increments it.
        """
        super().__init_subclass__(**kwargs)
        impl = cls.__dict__.get("execute")
        if impl is not None and not getattr(impl, "__isabstractmethod__", False):
            cls.execute = _enforce_budget(_instrument_execute(impl))

    # --- Identity (override in subclasses) ---
    name: str = ""
    version: str = "0.1.0"
    tier: ToolTier = ToolTier.CORE
    stability: ToolStability = ToolStability.EXPERIMENTAL
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    determinism: Determinism = Determinism.DETERMINISTIC
    runtime: ToolRuntime = ToolRuntime.LOCAL

    # --- Dependencies ---
    # For API tools, add "env:ENVVAR_NAME" to signal required API keys
    dependencies: list[str] = []
    install_instructions: str = ""

    # --- Capabilities ---
    capability: str = "generic"
    provider: str = "openmontage"
    capabilities: list[str] = []
    input_schema: dict = {}
    output_schema: dict = {}
    artifact_schema: dict = {}
    progress_schema: Optional[dict] = None
    supports: dict[str, Any] = {}
    best_for: list[str] = []
    not_good_for: list[str] = []
    provider_matrix: dict[str, Any] = {}

    # --- Resource & retry ---
    resource_profile: ResourceProfile = ResourceProfile()
    retry_policy: RetryPolicy = RetryPolicy()

    # --- Resume & idempotency ---
    resume_support: ResumeSupport = ResumeSupport.NONE
    idempotency_key_fields: list[str] = []

    # --- Side effects & fallback ---
    side_effects: list[str] = []
    fallback: Optional[str] = None
    fallback_tools: list[str] = []

    # --- Agent skills (Layer 3 references) ---
    # Names of installed agent skills in .agents/skills/ that teach the
    # underlying technology. The orchestrator uses these to load relevant
    # API knowledge when planning tool usage.
    agent_skills: list[str] = []

    # --- Verification ---
    user_visible_verification: list[str] = []

    # --- Optional telemetry / quality hints for the scoring engine ---
    # If set (0.0-1.0), lib/scoring.py uses these directly instead of falling
    # back to stability-based heuristics. Leave unset unless the tool has a
    # real measured or well-calibrated value.
    quality_score: Optional[float] = None
    historical_success_rate: Optional[float] = None
    latency_p50_seconds: Optional[float] = None

    # ---- Status reporting ----

    def get_status(self) -> ToolStatus:
        """Check if this tool's dependencies are satisfied."""
        try:
            self.check_dependencies()
            return ToolStatus.AVAILABLE
        except DependencyError:
            return ToolStatus.UNAVAILABLE

    def check_dependencies(self) -> None:
        """Verify all dependencies are installed. Raises DependencyError if not."""
        for dep in self.dependencies:
            if dep.startswith(("cmd:", "binary:")):
                prefix = "cmd:" if dep.startswith("cmd:") else "binary:"
                cmd_name = dep[len(prefix):]
                if shutil.which(cmd_name) is None:
                    raise DependencyError(
                        f"Command {cmd_name!r} not found. {self.install_instructions}"
                    )
            elif dep.startswith("env:"):
                env_name = dep[4:]
                if not os.environ.get(env_name):
                    raise DependencyError(
                        f"Environment variable {env_name!r} not set. {self.install_instructions}"
                    )
            elif dep.startswith("python:"):
                module_name = dep[7:]
                try:
                    __import__(module_name)
                except ImportError:
                    raise DependencyError(
                        f"Python module {module_name!r} not installed. {self.install_instructions}"
                    )

    def get_info(self) -> dict[str, Any]:
        """Return full tool contract info for registry/discovery."""
        usage_location = inspect.getfile(self.__class__)
        return {
            "name": self.name,
            "version": self.version,
            "tier": self.tier.value,
            "capability": self.capability,
            "provider": self.provider,
            "stability": self.stability.value,
            "status": self.get_status().value,
            "execution_mode": self.execution_mode.value,
            "determinism": self.determinism.value,
            "runtime": self.runtime.value,
            "module_path": self.__class__.__module__,
            "usage_location": usage_location,
            "dependencies": self.dependencies,
            "install_instructions": self.install_instructions,
            "capabilities": self.capabilities,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "artifact_schema": self.artifact_schema,
            "supports": self.supports,
            "best_for": self.best_for,
            "not_good_for": self.not_good_for,
            "provider_matrix": self.provider_matrix,
            "resource_profile": {
                "cpu_cores": self.resource_profile.cpu_cores,
                "ram_mb": self.resource_profile.ram_mb,
                "vram_mb": self.resource_profile.vram_mb,
                "disk_mb": self.resource_profile.disk_mb,
                "network_required": self.resource_profile.network_required,
            },
            "resume_support": self.resume_support.value,
            "side_effects": self.side_effects,
            "fallback": self.fallback,
            "fallback_tools": self.fallback_tools or ([self.fallback] if self.fallback else []),
            "agent_skills": self.agent_skills,
            "related_skills": self.agent_skills,
            "user_visible_verification": self.user_visible_verification,
            "quality_score": self.quality_score,
            "historical_success_rate": self.historical_success_rate,
            "latency_p50_seconds": self.latency_p50_seconds,
        }

    # ---- Cost estimation ----

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Estimate cost in USD for the given inputs. Override for paid tools.

        This is an APPROXIMATION for planning and provider ranking. It is NOT a
        guaranteed ceiling and must never be treated as one -- see
        max_cost_usd() for the value the budget gate actually reserves.
        """
        return 0.0

    def max_cost_usd(self, inputs: dict[str, Any]) -> Optional[float]:
        """Defensible UPPER BOUND on what this call can cost, or None.

        Returning None means "I cannot bound this", and the budget gate will
        refuse the call by name. That default is deliberate: a daily hard cap
        is only real if every paid call's worst case is known in advance, and
        it is safer to block a provider than to silently blow the cap.

        A correct override must cover EVERY provider request the call can make
        under the worst-case inputs, including:
          - retry_policy.max_retries (one execute() can bill many times)
          - provider-chosen quantities (e.g. duration="auto")
          - the most expensive model/quality the inputs could resolve to

        Return a finite, non-negative float >= estimate_cost(inputs).
        """
        return None

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate runtime in seconds. Override for long-running tools."""
        return 0.0

    # ---- Idempotency ----

    def idempotency_key(self, inputs: dict[str, Any]) -> str:
        """Compute a cache key from idempotency fields."""
        key_data = {k: inputs.get(k) for k in self.idempotency_key_fields}
        raw = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    # ---- Execution ----

    @abstractmethod
    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        """Run the tool. Subclasses must implement this."""
        ...

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Preflight check without side effects. Override for paid/publishing tools."""
        return {
            "tool": self.name,
            "estimated_cost_usd": self.estimate_cost(inputs),
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
        }

    # ---- CLI helper ----

    def run_command(
        self,
        cmd: list[str],
        *,
        timeout: Optional[int] = None,
        cwd: Optional[Path] = None,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess command with standard error handling.

        On Windows, resolves .cmd/.bat wrappers (e.g. npx, npm) via
        shutil.which() so subprocess.run() can find them without shell=True.
        """
        resolved_cmd = list(cmd)
        if platform.system() == "Windows" and resolved_cmd:
            exe = shutil.which(resolved_cmd[0])
            if exe:
                resolved_cmd[0] = exe
        try:
            return subprocess.run(
                resolved_cmd,
                capture_output=True,
                text=True,
                # Force UTF-8 decoding. The default uses the OS locale (cp1252 on
                # Windows), which raises UnicodeDecodeError on a subprocess that
                # emits Unicode/emoji (e.g. Remotion's progress output), killing the
                # reader thread and potentially swallowing the real error text.
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=cwd,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            stdout = (exc.stdout or "").strip()
            detail = stderr or stdout or str(exc)
            raise ToolCommandError(
                exc.returncode,
                exc.cmd,
                output=exc.output,
                stderr=exc.stderr,
                detail=detail,
            ) from exc


class ToolCommandError(subprocess.CalledProcessError):
    """CalledProcessError with stderr/stdout surfaced in str(error)."""

    def __init__(
        self,
        returncode: int,
        cmd: list[str],
        *,
        output: Optional[str] = None,
        stderr: Optional[str] = None,
        detail: str = "",
    ) -> None:
        super().__init__(returncode, cmd, output=output, stderr=stderr)
        self.detail = detail

    def __str__(self) -> str:
        base = super().__str__()
        if self.detail:
            return f"{base}\n{self.detail}"
        return base


class DependencyError(Exception):
    """Raised when a tool's dependency is not satisfied."""
    pass
