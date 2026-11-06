"""Google Flow CLI wrapper — safe subprocess driver for gflow-cli 0.92.0.

Wraps `gflow image t2i`, `gflow run --config` and read-only status commands
through ``subprocess`` (argument list, never ``shell=True``).

Governance:
  * The strict zero-cost gate (``lib.zero_cost_gate``) is evaluated before
    every credit-bearing call.  Unknown cost (``cost_usd is None``) blocks
    the call — it is never treated as free.
  * Integrates with ``lib.flow_job_manager``: jobs are created in DRAFT,
    validated to VALIDATED, then moved to READY_FOR_APPROVAL where the
    automated system STOPS.  Transition to APPROVED/SUBMITTED (which would
    spend credits) requires explicit manual human approval and is never
    performed by this wrapper.
  * ``GFLOW_MCP_NO_SPEND`` / ``--no-spend`` are respected and never
    overridden.

All work outside an explicitly user-approved generation call is read-only
and zero-cost.
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
from typing import Any

from lib.flow_job_manager import FlowJob, FlowJobManager
from lib.zero_cost_gate import (
    STRICT_ZERO_COST,
    ToolFacts,
    evaluate_call,
    ZeroCostViolation,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GFLOW_BIN = os.environ.get("GFLOW_BIN", "gflow")
DEFAULT_PROFILE = os.environ.get("GFLOW_CLI_PROFILE", "flow_remote")
DEFAULT_MODEL = "nano2"          # Nano Banana 2.1 (NARWHAL), ref_cap=10
DEFAULT_ASPECT = "16:9"
DEFAULT_COUNT = 1

# gflow-cli 0.92.0 exit codes (observed).
EXIT_OK = 0
EXIT_ARGS = 2
EXIT_PROFILE = 11
EXIT_DOCTOR = 33

READ_ONLY_TOOLS = ("auth status", "credits user", "models", "doctor", "project list")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class GflowResult:
    """Outcome of one gflow-cli invocation."""

    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    success: bool
    parsed: Any = None
    media_id: str | None = None
    output_path: str | None = None
    width: int | None = None
    height: int | None = None
    sha256: str | None = None
    file_size: int | None = None
    error: str | None = None
    duration_seconds: float | None = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": " ".join(self.command),
            "exit_code": self.exit_code,
            "success": self.success,
            "parsed": self.parsed,
            "media_id": self.media_id,
            "output_path": self.output_path,
            "width": self.width,
            "height": self.height,
            "sha256": self.sha256,
            "file_size": self.file_size,
            "error": self.error,
            "duration_seconds": self.duration_seconds,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Wrapper
# ---------------------------------------------------------------------------


class GflowWrapper:
    """Safe driver around the gflow-cli binary."""

    def __init__(
        self,
        *,
        manager: FlowJobManager | None = None,
        gflow_bin: str = GFLOW_BIN,
        timeout_seconds: float = 300.0,
        headless: bool = True,
    ) -> None:
        self.gflow_bin = gflow_bin
        self.timeout_seconds = timeout_seconds
        self.manager = manager or FlowJobManager()
        self.headless = headless
        self._env = dict(os.environ)
        if headless:
            self._env.setdefault("GFLOW_CLI_HEADLESS", "true")
        # Never override the project's spend guard.
        self._env.setdefault("GFLOW_CLI_UPDATE_CHECK", "0")

    # ------------------------------------------------------------------
    # Availability / auth (read-only, zero-cost)
    # ------------------------------------------------------------------

    def check_available(self) -> bool:
        """Return True iff gflow CLI is installed and authenticated read-only.

        Runs ``gflow --version`` and ``gflow credits user`` (read-only,
        does not spend).  Logs the result.
        """
        try:
            ver = self._run([self.gflow_bin, "--version"], timeout=30.0)
            if not ver.success:
                return False
            creds = self._run(
                [self.gflow_bin, "credits", "user"], timeout=60.0
            )
            return creds.success
        except (FileNotFoundError, subprocess.SubprocessError, OSError):
            return False

    def version(self) -> str | None:
        """Return gflow-cli version string, or None if unavailable."""
        res = self._run([self.gflow_bin, "--version"], timeout=30.0)
        if res.success and res.stdout:
            return res.stdout.strip().splitlines()[0]
        return None

    # ------------------------------------------------------------------
    # Zero-cost-gated generation
    # ------------------------------------------------------------------

    def plan_image_job(
        self,
        *,
        sentence_id: str,
        project: str,
        prompt: str,
        output_path: str | Path,
        aspect_ratio: str = DEFAULT_ASPECT,
        model: str = DEFAULT_MODEL,
        reference_entity: str | None = None,
    ) -> FlowJob:
        """Create a DRAFT FlowJob for one image and advance to READY_FOR_APPROVAL.

        This is the planning path: it does NOT call credit-spending
        generation.  The job stops at READY_FOR_APPROVAL awaiting manual
        approval before any credits can be spent.
        """
        output_path = str(output_path)
        job_id = f"{project}-{sentence_id}"
        job = self.manager.add_job(
            job_id=job_id,
            project=project,
            scene=sentence_id,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution="1920x1080",
            references=[],
            input_files=[],
            generation_params={
                "model": model,
                "count": DEFAULT_COUNT,
                "aspect_ratio": aspect_ratio,
                "output_path": output_path,
                "reference_entity": reference_entity,
            },
        )
        # Structural validation only (skip slow MCP browser checks here;
        # QC runs separately via lib.quality_control / tools.qa.qc).
        self.manager.validate_job(job_id, skip_mcp=True)
        # Automated system stops here — never auto-approve (no spend).
        self.manager.ready_for_approval(job_id)
        return self.manager.get_job(job_id)

    def execute_image(
        self,
        *,
        job_id: str,
        user_approved: bool = False,
        cost_usd: float | None = None,
    ) -> GflowResult:
        """Execute one credit-bearing ``gflow image t2i`` call.

        Enforces the zero-cost gate first.  Blocks unless the route is
        known, the cost is known, and (in strict zero-cost mode) the user
        has explicitly approved this paid action.
        """
        job = self.manager.get_job(job_id)
        if job is None:
            return GflowResult(
                command=[self.gflow_bin, "image", "t2i"],
                exit_code=EXIT_ARGS,
                stdout="",
                stderr="",
                success=False,
                error=f"job not found: {job_id}",
            )

        # --- Zero-cost gate (runs before any state or generation logic) ---
        params = job.generation_params or {}
        route = (
            f"gflow image t2i model={params.get('model', DEFAULT_MODEL)} "
            f"aspect={params.get('aspect_ratio', DEFAULT_ASPECT)}"
        )
        facts = ToolFacts(
            tool="gflow_image_t2i",
            operation="execute",
            provider="google_flow",
            runtime="api",
            route=route,
            cost_usd=cost_usd,
            status="available",
        )
        decision = evaluate_call(
            facts, mode=STRICT_ZERO_COST, user_approved=user_approved
        )
        if decision.blocked:
            raise ZeroCostViolation(
                f"gflow image t2i blocked for job {job_id}: {decision.reason}"
            )

        # The automated system stops at READY_FOR_APPROVAL.  Credit-bearing
        # generation runs only on jobs the owner has explicitly approved.
        if job.state != "APPROVED":
            return GflowResult(
                command=[self.gflow_bin, "image", "t2i"],
                exit_code=EXIT_ARGS,
                stdout="",
                stderr="",
                success=False,
                error=f"job {job_id} is {job.state}, not APPROVED — "
                f"manual owner approval required before generation",
            )

        cmd = [
            self.gflow_bin,
            "image",
            "t2i",
            job.prompt,
            "--aspect",
            params.get("aspect_ratio", DEFAULT_ASPECT),
            "--model",
            params.get("model", DEFAULT_MODEL),
            "-n",
            str(params.get("count", DEFAULT_COUNT)),
            "--out",
            os.path.dirname(params.get("output_path", ".")) or ".",
            "--json",
            "--profile",
            DEFAULT_PROFILE,
        ]
        if params.get("reference_entity"):
            cmd += ["--reference-entity", str(params["reference_entity"])]
        if params.get("output_filename"):
            cmd += ["-o", params["output_filename"]]

        start = time.time()
        result = self._run(cmd, timeout=self.timeout_seconds)
        result.duration_seconds = round(time.time() - start, 3)

        if result.success:
            self._mark_completed(job_id, result)
        else:
            self._mark_failed(job_id, result.error or "gflow call failed")
        return result

    def execute_batch(
        self,
        *,
        config_path: str | Path,
        output_dir: str | Path,
        user_approved: bool = False,
        cost_usd: float | None = None,
    ) -> GflowResult:
        """Execute a JSON-manifest batch via ``gflow run --config``.

        Supports ``--continue-on-error`` and ``--resume`` for recovery.
        Gated by the zero-cost gate like :meth:`execute_image`.
        """
        config_path = str(config_path)
        route = f"gflow run --config {config_path} output_dir={output_dir}"
        facts = ToolFacts(
            tool="gflow_run_batch",
            operation="execute",
            provider="google_flow",
            runtime="api",
            route=route,
            cost_usd=cost_usd,
            status="available",
        )
        decision = evaluate_call(
            facts, mode=STRICT_ZERO_COST, user_approved=user_approved
        )
        if decision.blocked:
            raise ZeroCostViolation(
                f"gflow run batch blocked: {decision.reason}"
            )

        cmd = [
            self.gflow_bin,
            "run",
            "--config",
            config_path,
            "--output-dir",
            str(output_dir),
            "--profile",
            DEFAULT_PROFILE,
            "--continue-on-error",
            "--resume",
            "--json",
        ]
        start = time.time()
        result = self._run(cmd, timeout=self.timeout_seconds)
        result.duration_seconds = round(time.time() - start, 3)
        return result

    # ------------------------------------------------------------------
    # Subprocess runner (no shell=True)
    # ------------------------------------------------------------------

    def _run(
        self, cmd: list[str], *, timeout: float
    ) -> GflowResult:
        """Run one gflow command, capturing output and parsing JSON when present."""
        t0 = time.time()
        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=self._env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            return GflowResult(
                command=cmd,
                exit_code=-1,
                stdout=exc.stdout or "",
                stderr=(exc.stderr or "") + f"\ncommand timed out after {timeout}s",
                success=False,
                error=f"timeout after {timeout}s",
                duration_seconds=round(time.time() - t0, 3),
            )
        except FileNotFoundError as exc:
            return GflowResult(
                command=cmd,
                exit_code=127,
                stdout="",
                stderr=str(exc),
                success=False,
                error=f"gflow binary not found: {self.gflow_bin}",
                duration_seconds=round(time.time() - t0, 3),
            )
        except OSError as exc:
            return GflowResult(
                command=cmd,
                exit_code=1,
                stdout="",
                stderr=str(exc),
                success=False,
                error=str(exc),
                duration_seconds=round(time.time() - t0, 3),
            )

        parsed = None
        media_id = None
        output_path = None
        width = None
        height = None
        sha256 = None
        file_size = None
        error = None

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        success = proc.returncode == EXIT_OK

        # Try to parse a JSON object from stdout (gflow --json emits one).
        json_text = self._extract_json(stdout)
        if json_text is not None:
            try:
                parsed = json.loads(json_text)
            except json.JSONDecodeError:
                parsed = None

        if parsed is not None:
            media_id = self._dig(parsed, ("media_id", "id", "mediaId"))
            output_path = self._dig(parsed, ("output_path", "outputPath", "path", "file"))
        width = self._dig(parsed, ("width", "size", "resolution"))
        height = self._dig(parsed, ("height",))
        if isinstance(width, str) and "x" in width:
            parts = width.split("x")
            if len(parts) == 2:
                try:
                    width = int(parts[0])
                    height = int(parts[1])
                except ValueError:
                    width = None
                    height = None
            # sha256 / size if the CLI reports them
            sha256 = self._dig(parsed, ("sha256", "hash", "digest"))
            file_size = self._dig(parsed, ("size_bytes", "file_size", "bytes"))

        # Fallback: compute sha256 of a reported output file on disk.
        if output_path and not sha256:
            p = Path(output_path)
            if p.exists():
                sha256 = self._sha256(p)
                file_size = p.stat().st_size

        if proc.returncode != EXIT_OK:
            error = stderr.strip() or stdout.strip() or f"exit {proc.returncode}"

        return GflowResult(
            command=cmd,
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            success=success,
            parsed=parsed,
            media_id=media_id,
            output_path=output_path,
            width=width,
            height=height,
            sha256=sha256,
            file_size=file_size,
            error=error,
            duration_seconds=round(time.time() - t0, 3),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """Extract the first JSON object/array from *text*."""
        text = text.strip()
        if not text:
            return None
        # gflow --json may emit a single object; try whole string first.
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass
        # Fallback: locate the first balanced object.
        start = text.find("{")
        if start < 0:
            start = text.find("[")
        if start < 0:
            return None
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch in "{[":
                    depth += 1
                elif ch in "}]":
                    depth -= 1
                    if depth == 0:
                        return text[start : i + 1]
        return None

    @staticmethod
    def _dig(data: Any, keys: tuple[str, ...]) -> Any:
        """Walk nested dict/list using the first key that exists."""
        if not isinstance(data, dict):
            return None
        for k in keys:
            if k in data:
                return data[k]
        return None

    @staticmethod
    def _sha256(path: Path) -> str | None:
        """SHA-256 of a file, or None if unreadable."""
        try:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
            return h.hexdigest()
        except OSError:
            return None

    def _mark_completed(self, job_id: str, result: GflowResult) -> None:
        job = self.manager.get_job(job_id)
        if job:
            # APPROVED → SUBMITTED → COMPLETED (generation dispatched, then done).
            if job.state == "APPROVED":
                job.transition("SUBMITTED", "generation dispatched to Flow")
            job.transition("COMPLETED", "generation finished")
            job.generation_params = dict(job.generation_params or {})
            job.generation_params["gflow_result"] = result.to_dict()
            self.manager._persist(job)

    def _mark_failed(self, job_id: str, error: str) -> None:
        job = self.manager.get_job(job_id)
        if job:
            job.transition("FAILED", error)
            self.manager._persist(job)
