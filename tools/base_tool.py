"""Base tool class implementing the expanded ToolContract.

Every tool in OpenMontage inherits from BaseTool. This enforces a uniform
interface for discovery, execution, cost estimation, and health reporting.
"""

from __future__ import annotations

import copy
import functools
import hashlib
import importlib.util
import inspect
import json
import logging
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

logger = logging.getLogger(__name__)


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


# Errors that a PAID tool must never auto-retry. A rate_limit means the
# provider REFUSED the request — nothing ran, nothing was billed, retrying is
# free. A timeout means we DON'T KNOW: for kling/veo/seedance the queue job may
# still be running and billing (poll_fal_queue raises TimeoutError at 600s
# precisely while the job is alive), so a retry submits a SECOND paid job and
# double-charges. Local/free tools retry timeouts happily — retrying costs
# nothing there.
_UNSAFE_TO_RETRY_WHEN_PAID = frozenset({"timeout", "timed out"})


def _tool_costs_money(tool: Any, inputs: Any) -> bool:
    """Whether this call is expected to be billed. Fails CLOSED (assumes paid).

    estimate_cost can legitimately raise on odd inputs (a duration string it
    can't parse), and guessing "free" there would be the expensive mistake.
    """
    try:
        return float(tool.estimate_cost(inputs)) > 0
    except Exception:
        return True


def _retryable_reason(policy: Any, error_text: str, paid: bool) -> Optional[str]:
    """The declared error substring matching `error_text`, or None.

    `retryable_errors` is an allowlist — the tool author naming the specific
    failures that are safe to repeat. A blanket retry is never correct here.
    """
    if not error_text:
        return None
    haystack = error_text.lower()
    for declared in policy.retryable_errors or []:
        needle = str(declared).lower()
        if needle and needle in haystack:
            if paid and any(u in needle for u in _UNSAFE_TO_RETRY_WHEN_PAID):
                continue  # declared, but not safe to honor on a paid call
            return str(declared)
    return None


def _run_with_retry(tool: Any, fn: Callable, inputs: Any, args: tuple, kwargs: dict):
    """Call fn, honoring the tool's declared retry_policy. Returns (result, attempts).

    Until now retry_policy was pure documentation: 56 tools declared one and
    NOTHING read it, so `max_retries=2, retryable_errors=["rate_limit"]` was a
    promise to the reader (and to any agent reading get_info()) that no code
    kept (audit 2026-07-15, S-5).

    Retries only when the failure matches the tool's OWN allowlist, and never
    on a timeout for a call that costs money (see _UNSAFE_TO_RETRY_WHEN_PAID).
    Default policy is max_retries=0, so a tool that declares nothing keeps its
    exact current behavior.
    """
    policy = getattr(tool, "retry_policy", None)
    max_retries = int(getattr(policy, "max_retries", 0) or 0)
    if max_retries <= 0 or not getattr(policy, "retryable_errors", None):
        return fn(tool, inputs, *args, **kwargs), 1

    paid = _tool_costs_money(tool, inputs)
    backoff = float(getattr(policy, "backoff_seconds", 1.0) or 1.0)
    log = logging.getLogger("tool_retry")
    tool_name = getattr(tool, "name", type(tool).__name__)

    attempt = 0
    while True:
        attempt += 1
        error_text = ""
        result = None
        try:
            result = fn(tool, inputs, *args, **kwargs)
            if getattr(result, "success", True):
                return result, attempt
            error_text = str(getattr(result, "error", "") or "")
        except Exception as exc:  # noqa: BLE001 — re-raised below if not retryable
            error_text = f"{type(exc).__name__}: {exc}"
            if attempt > max_retries or not _retryable_reason(policy, error_text, paid):
                raise
            log.warning(
                "%s attempt %d/%d raised a retryable error (%s) — retrying in %.1fs",
                tool_name, attempt, max_retries + 1, error_text[:120], backoff * attempt,
            )
            time.sleep(backoff * attempt)
            continue

        reason = _retryable_reason(policy, error_text, paid)
        if attempt > max_retries or reason is None:
            return result, attempt
        log.warning(
            "%s attempt %d/%d failed with declared-retryable %r — retrying in %.1fs",
            tool_name, attempt, max_retries + 1, reason, backoff * attempt,
        )
        time.sleep(backoff * attempt)


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
            result, attempts = _run_with_retry(self, fn, inputs, args, kwargs)
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
                # Only when a retry actually happened — keeps the common
                # event shape unchanged.
                **({"attempts": attempts} if attempts > 1 else {}),
            })
        return result

    wrapper._backlot_instrumented = True  # type: ignore[attr-defined]
    return wrapper


class BaseTool(ABC):
    """Abstract base class for all OpenMontage tools."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-instrument every concrete execute() with Backlot events."""
        super().__init_subclass__(**kwargs)
        impl = cls.__dict__.get("execute")
        if impl is not None and not getattr(impl, "__isabstractmethod__", False):
            cls.execute = _instrument_execute(impl)

    # List/dataclass contract attributes that must not be shared as the same
    # object across sibling instances -- see __init__.
    _LIST_DEFAULTS_TO_ISOLATE = (
        "dependencies", "capabilities", "best_for", "not_good_for",
        "side_effects", "fallback_tools", "agent_skills",
        "user_visible_verification", "idempotency_key_fields",
    )
    _DATACLASS_DEFAULTS_TO_ISOLATE = ("resource_profile", "retry_policy")

    def __init__(self) -> None:
        """Give each instance its own copy of the mutable contract defaults.

        The attributes named above are declared at the class level so
        subclasses can override them with a plain assignment, but any
        subclass left at a BaseTool default would otherwise share the exact
        same list/dataclass object with every sibling subclass that also
        didn't override it -- mutating one in place would leak across tools.
        Copying here (whatever value -- BaseTool's default or a subclass's
        override -- is currently on the class) keeps that ergonomic while
        giving each instance independent storage.

        A few selector subclasses (e.g. tts_selector) instead expose one of
        these names as a computed `@property` (built from live registry
        state). Those are skipped: copying would either recurse into the
        property or raise on the assignment, and there's nothing to isolate
        since the property recomputes fresh on every access anyway.
        """
        cls = type(self)
        for attr_name in self._LIST_DEFAULTS_TO_ISOLATE:
            if isinstance(getattr(cls, attr_name, None), property):
                continue
            setattr(self, attr_name, list(getattr(self, attr_name)))
        for attr_name in self._DATACLASS_DEFAULTS_TO_ISOLATE:
            if isinstance(getattr(cls, attr_name, None), property):
                continue
            setattr(self, attr_name, copy.deepcopy(getattr(self, attr_name)))

    # --- Identity (override in subclasses) ---
    name: str = ""
    version: str = "0.1.0"
    tier: ToolTier = ToolTier.CORE
    stability: ToolStability = ToolStability.EXPERIMENTAL
    execution_mode: ExecutionMode = ExecutionMode.SYNC
    determinism: Determinism = Determinism.DETERMINISTIC
    runtime: ToolRuntime = ToolRuntime.LOCAL

    # The currency ToolResult.cost_usd is ACTUALLY denominated in for this
    # tool, despite its literal field name. Defaults to "USD", true for the
    # large majority of provider tools (ElevenLabs, OpenAI, Google, Kling,
    # Veo, Runway, Recraft, Suno, ...) whose cost_usd is real US-dollar
    # pricing from that provider's own API. Override to "CNY" only for a
    # tool that deliberately reports cost_usd in CNY to avoid a needless FX
    # round-trip (see tools/maas_base.py's MaasBaseTool — the MaaS gateway
    # bills internally in CNY). Every caller that treats cost_usd as a
    # job's CNY spend (server/app/runner/tool_bridge.py's cost ledger and
    # budget gate) MUST check this field and convert USD-declared tools —
    # confirmed live: before this field existed, EVERY tool's cost_usd was
    # summed as if it were CNY unconditionally, so a real $50 of ElevenLabs/
    # Kling/Veo spend would have shown as "¥50 spent" against a ¥50 budget
    # cap instead of the ~¥360 it actually was, silently blowing the cap.
    cost_currency: str = "USD"

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
            if dep.startswith("cmd:"):
                cmd_name = dep[4:]
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
                # find_spec, not __import__: this only has to answer "is it
                # installed?", and IMPORTING to find out is ruinous here.
                # Seven tools declare python:torch / python:cv2 /
                # python:transformers, and the registry's preflight surfaces
                # (support_envelope, provider_menu, get_by_status) call
                # get_status() on EVERY tool — so rendering a capability menu
                # on a machine with torch installed paid multi-second imports
                # and hundreds of MB of RSS just to list what's available
                # (audit 2026-07-15, finding 6). find_spec consults the
                # finders without executing the module.
                try:
                    found = importlib.util.find_spec(module_name) is not None
                except (ImportError, ValueError):
                    # A namespace package whose parent is missing raises
                    # rather than returning None — treat as absent.
                    found = False
                if not found:
                    raise DependencyError(
                        f"Python module {module_name!r} not installed. {self.install_instructions}"
                    )
            else:
                raise DependencyError(
                    f"Unrecognized dependency prefix in {dep!r} on tool {self.name!r}. "
                    "Expected one of 'cmd:', 'env:', 'python:'."
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
        """Estimate cost in USD for the given inputs. Override for paid tools."""
        # Safety net: a runtime=API tool (declared as calling a paid external
        # API -- see ToolRuntime.API) that never overrides this default $0.00
        # would otherwise sail through both budget-approval gates in
        # cost_tracker.reserve() silently (they only fire when
        # estimated > 0 / > threshold). This can't distinguish a subclass
        # that legitimately overrides estimate_cost() and then calls
        # super().estimate_cost() as part of its own logic, but that's a rare
        # and harmless false positive next to the silent-footgun default.
        if type(self).estimate_cost is BaseTool.estimate_cost and self.runtime == ToolRuntime.API:
            logger.warning(
                "%s is runtime=API (a paid tool) but does not override "
                "estimate_cost(); defaulting to $0.00 silently bypasses "
                "cost_tracker.reserve()'s budget-approval gates.",
                self.name or type(self).__name__,
            )
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        """Estimate runtime in seconds. Override for long-running tools."""
        return 0.0

    # ---- Idempotency ----

    def idempotency_key(self, inputs: dict[str, Any]) -> str:
        """Compute a cache key from idempotency fields."""
        key_data = {k: inputs.get(k) for k in self.idempotency_key_fields}
        # default=str: a Path/datetime/etc. value in idempotency_key_fields
        # would otherwise raise TypeError instead of producing a cache key.
        raw = json.dumps(key_data, sort_keys=True, default=str)
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


class DependencyError(Exception):
    """Raised when a tool's dependency is not satisfied."""
    pass
