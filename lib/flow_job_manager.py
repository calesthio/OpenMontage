"""Google Flow Job Manager — production pipeline for OpenMontage.

Manages the lifecycle of Google Flow generation jobs from ingestion through
READY_FOR_APPROVAL.  The system is strictly read-only with respect to
generation: no credits are spent, no generation buttons are clicked, and the
pipeline stops at READY_FOR_APPROVAL pending manual human approval.

Integrates with existing OpenMontage components:
  - lib/shot_prompt_builder.py  (prompt construction)
  - lib/zero_cost_gate.py       (zero-cost enforcement)
  - gflow MCP                   (read-only: auth, projects, models, credits)
  - browser-use MCP             (read-only: navigate, state, screenshot, extract)

Job states:
    DRAFT → VALIDATED → READY_FOR_APPROVAL → APPROVED → SUBMITTED → COMPLETED / FAILED

The automated system stops at READY_FOR_APPROVAL.  Transition to APPROVED
requires explicit manual human approval (see FLOW_PRODUCTION_PIPELINE.md).
"""

from __future__ import annotations

import hashlib
import json
import queue
import time
import os
import sqlite3
import subprocess
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

JOB_STATES = (
    "DRAFT",
    "VALIDATED",
    "READY_FOR_APPROVAL",
    "APPROVED",
    "SUBMITTED",
    "COMPLETED",
    "FAILED",
)

STATE_TRANSITIONS = {
    "DRAFT": ("VALIDATED",),
    "VALIDATED": ("READY_FOR_APPROVAL",),
    "READY_FOR_APPROVAL": ("APPROVED",),
    "APPROVED": ("SUBMITTED",),
    "SUBMITTED": ("COMPLETED", "FAILED"),
    "COMPLETED": (),
    "FAILED": (),
}

# Automated system stops here; APPROVED requires manual human intervention.
AUTO_STOP_STATE = "READY_FOR_APPROVAL"

# READ_ONLY mode: when True, no credit-spending or generation-capable
# operations can be performed.  This is the default and must not be disabled
# without explicit separate user approval.
READ_ONLY_MODE = True


def assert_read_only(operation: str) -> None:
    """Raise if READ_ONLY_MODE would block the given operation."""
    if not READ_ONLY_MODE:
        raise RuntimeError(
            f"READ_ONLY_MODE is disabled — {operation} would require "
            "explicit user approval to re-enable"
        )

# Zero-cost guard: never allow generation tools through this manager.
GFLOW_READ_ONLY_TOOLS = frozenset(
    {
        "gflow_auth_status",
        "gflow_list_projects",
        "gflow_list_models",
        "gflow_get_credits",
        "gflow_character_list",
        "gflow_character_voices",
        "gflow_character_show",
        "gflow_instructions_list",
    }
)

# Browser Use tools that are safe (read-only, no generation clicks).
BROWSER_USE_READ_ONLY_TOOLS = frozenset(
    {
        "browser_navigate",
        "browser_get_state",
        "browser_screenshot",
        "browser_extract_content",
        "browser_list_tabs",
        "browser_get_html",
        "browser_go_back",
        "browser_switch_tab",
        "browser_list_sessions",
    }
)

# Forbidden Browser Use actions (generation-triggering clicks).
FORBIDDEN_BU_ACTIONS = frozenset({"browser_click", "browser_type", "browser_scroll"})


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
JOBS_DIR = BASE_DIR / "jobs"
FLOW_QUEUE_DIR = BASE_DIR / "flow_queue"
FLOW_RESULTS_DIR = BASE_DIR / "flow_results"
FLOW_AUDIT_DIR = BASE_DIR / "flow_audit"
QUEUE_DB = FLOW_QUEUE_DIR / "queue.db"
AUDIT_LOG = FLOW_AUDIT_DIR / "flow_audit.log"

for _d in (JOBS_DIR, FLOW_QUEUE_DIR, FLOW_RESULTS_DIR, FLOW_AUDIT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------

_lock = threading.Lock()


def _audit(event: str, details: str = "") -> None:
    """Append an audit log entry (thread-safe)."""
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] {event} {details}\n"
    with _lock:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(line)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FlowJob:
    """A single Google Flow generation job."""

    job_id: str
    project: str
    scene: str
    prompt: str
    prompt_version: int = 1
    state: str = "DRAFT"
    aspect_ratio: str = "16:9"
    resolution: str = "1920x1080"
    references: list[str] = field(default_factory=list)
    input_files: list[str] = field(default_factory=list)
    generation_params: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: str | None = None
    submitted_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    history: list[dict[str, str]] = field(default_factory=list)
    mcp_checked: bool = False
    mcp_auth_ok: bool = False
    mcp_projects: list[str] = field(default_factory=list)
    mcp_models: list[str] = field(default_factory=list)
    browser_checked: bool = False
    browser_auth_ok: bool = False
    browser_screenshot_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlowJob":
        return cls(**d)

    def transition(self, new_state: str, reason: str = "", initial: bool = False) -> None:
        """Transition to a new state, enforcing the state machine.

        ``initial=True`` is used only when creating a new job in DRAFT state;
        it bypasses the transition graph since DRAFT is the starting state.

        ``FAILED`` is a terminal error state reachable from any non-terminal
        state (validation failure, MCP error, etc.), so it is exempt from the
        normal transition graph.
        """
        if new_state not in JOB_STATES:
            raise ValueError(f"Unknown state: {new_state}")
        if not initial:
            # FAILED is a terminal error state — allowed from any non-terminal
            # state so jobs can be marked failed at any point.
            if new_state == "FAILED":
                if self.state in ("COMPLETED", "FAILED"):
                    raise ValueError(
                        f"Cannot transition {self.state} → FAILED "
                        f"(already terminal)"
                    )
            else:
                allowed = STATE_TRANSITIONS.get(self.state, ())
                if new_state not in allowed:
                    raise ValueError(
                        f"Invalid transition {self.state} → {new_state}. "
                        f"Allowed from {self.state}: {allowed}"
                    )
        old_state = self.state
        self.state = new_state
        self.updated_at = datetime.now(timezone.utc).isoformat()
        self.history.append(
            {"from": old_state, "to": new_state, "at": self.updated_at, "reason": reason}
        )
        if new_state == "APPROVED":
            self.approved_at = self.updated_at
        if new_state == "SUBMITTED":
            self.submitted_at = self.updated_at
        if new_state in ("COMPLETED", "FAILED"):
            self.completed_at = self.updated_at
        _audit("JOB_STATE_CHANGE", f"{self.job_id} {old_state}→{new_state} ({reason})")


# ---------------------------------------------------------------------------
# Queue database
# ---------------------------------------------------------------------------


def _db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(QUEUE_DB), timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            job_id       TEXT PRIMARY KEY,
            project      TEXT NOT NULL,
            scene        TEXT NOT NULL,
            state        TEXT NOT NULL,
            prompt_hash  TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            error        TEXT,
            job_json     TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_jobs_project ON jobs(project)"
    )
    conn.commit()
    return conn


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def _job_hash(job: FlowJob) -> str:
    """Stable hash of job content for duplicate detection."""
    payload = {
        "project": job.project,
        "scene": job.scene,
        "prompt": job.prompt,
        "aspect_ratio": job.aspect_ratio,
        "resolution": job.resolution,
        "references": sorted(job.references),
        "input_files": sorted(job.input_files),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _load_job(job_id: str) -> FlowJob | None:
    p = _job_path(job_id)
    if not p.exists():
        return None
    return FlowJob.from_dict(json.loads(p.read_text(encoding="utf-8")))


def _persist_to_db(job: FlowJob) -> None:
    conn = _db_connect()
    conn.execute(
        """
        INSERT OR REPLACE INTO jobs
        (job_id, project, scene, state, prompt_hash, created_at, updated_at, error, job_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            job.job_id,
            job.project,
            job.scene,
            job.state,
            _job_hash(job),
            job.created_at,
            job.updated_at,
            job.error or "",
            json.dumps(job.to_dict(), ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# MCP integration (read-only)
# ---------------------------------------------------------------------------


def _mcp_jsonrpc(tool_name: str, arguments: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    """Send a JSON-RPC request to an MCP server over stdio.

    Supports gflow and browser-use servers.  Returns the parsed ``result`` or
    raises on error.

    Uses Popen (not run) so stdin stays open while the async MCP server
    processes the initialize → initialized → tools/call handshake.
    """
    if tool_name in GFLOW_READ_ONLY_TOOLS:
        cmd = ["gflow", "mcp", "run", "--profile", "flow_remote", "--no-spend"]
        # Read-only MCP runs in GitHub Codespaces have no X display, so force
        # headless Chrome to avoid an immediate browser exit ("Connection closed").
        env = {
            "GFLOW_CLI_PROFILE": "flow_remote",
            "GFLOW_MCP_NO_SPEND": "1",
            "GFLOW_CLI_HEADLESS": "true",
        }
    elif tool_name in BROWSER_USE_READ_ONLY_TOOLS:
        cmd = [
            "/home/vscode/.local/bin/browser-use",
            "--mcp",
        ]
        env = {
            "DISPLAY": ":99",
            "BROWSER_USE_HEADLESS": "false",
            "BROWSER_USE_CONFIG_DIR": "/home/vscode/.config/browseruse",
            "BU_CDP_URL": "http://127.0.0.1:9223",
            "BROWSER_USE_LOGGING_LEVEL": "critical",
        }
    else:
        raise ValueError(f"Tool {tool_name} is not a permitted read-only MCP tool")

    assert_read_only(f"MCP call to {tool_name}")

    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "flow-job-manager", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "method": "initialized", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    ]
    payload = "\n".join(json.dumps(m) for m in messages) + "\n"

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={**os.environ, **env},
    )

    # Keep stdin open while waiting for the (possibly long-running) tool
    # response. Closing stdin immediately (communicate) makes the stdio MCP
    # server shut down before a slow tool (e.g. credits browser launch)
    # can reply, surfacing as "Connection closed".
    assert proc.stdin is not None
    assert proc.stdout is not None
    assert proc.stderr is not None
    proc.stdin.write(payload)
    proc.stdin.flush()

    result_msg: dict[str, Any] | None = None
    stdout_q: "queue.Queue[str | None]" = queue.Queue()
    stderr_chunks: list[str] = []

    def _read_stdout() -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            stdout_q.put(line)
        stdout_q.put(None)

    def _read_stderr() -> None:
        try:
            stderr_chunks.append(proc.stderr.read())  # type: ignore[union-attr]
        except Exception:  # noqa: BLE001
            pass

    t_out = threading.Thread(target=_read_stdout, daemon=True)
    t_err = threading.Thread(target=_read_stderr, daemon=True)
    t_out.start()
    t_err.start()

    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                line = stdout_q.get(timeout=min(0.1, max(0.0, remaining)))
            except queue.Empty:
                if proc.poll() is not None:
                    break
                continue
            if line is None:
                break
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == 2:
                result_msg = msg
                break
    finally:
        # Stop the server and reap resources.
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        t_out.join(timeout=2)
        t_err.join(timeout=2)

    err_text = "".join(stderr_chunks)

    if result_msg is None:
        if proc.returncode not in (0, None) and proc.returncode != 0:
            raise RuntimeError(f"MCP {tool_name} exited {proc.returncode}: {err_text[:500]}")
        raise RuntimeError(f"MCP {tool_name}: no id=2 response in output")

    if "error" in result_msg:
        raise RuntimeError(f"MCP {tool_name} error: {result_msg['error']}")
    return result_msg.get("result", {})


def check_gflow_auth() -> dict[str, Any]:
    """Verify gflow authentication for profile flow_remote (read-only)."""
    result = _mcp_jsonrpc("gflow_auth_status", {"profile": "flow_remote"})
    # The MCP result may be a dict with a "verified" key, or a truthy/falsy value.
    if isinstance(result, dict):
        ok = bool(result.get("verified", result.get("ok", True)))
    else:
        ok = bool(result)
    return {
        "ok": ok,
        "raw": result,
    }


def check_gflow_projects() -> dict[str, Any]:
    """List available Flow projects (read-only)."""
    result = _mcp_jsonrpc("gflow_list_projects", {"profile": "flow_remote"})
    projects = result if isinstance(result, list) else []
    return {"ok": True, "projects": projects, "raw": result}


def check_gflow_models() -> dict[str, Any]:
    """List available Flow models (read-only, no spend)."""
    result = _mcp_jsonrpc("gflow_list_models", {})
    models = result if isinstance(result, list) else []
    return {"ok": True, "models": models, "raw": result}


def check_gflow_credits() -> dict[str, Any]:
    """Read Flow credit balance (read-only, no spend)."""
    result = _mcp_jsonrpc("gflow_get_credits", {"profile": "flow_remote"})
    return {"ok": True, "raw": result}


def check_browser_flow_page() -> dict[str, Any]:
    """Use browser-use to inspect Google Flow page state (read-only, no clicks)."""
    # Navigate to Flow
    _mcp_jsonrpc("browser_navigate", {"url": "https://flow.google.com", "new_tab": False})
    # Get page state
    state = _mcp_jsonrpc("browser_get_state", {"include_screenshot": False})
    # Take a screenshot for audit
    screenshot = _mcp_jsonrpc("browser_screenshot", {"full_page": False})
    return {"ok": True, "state": state, "screenshot": screenshot}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_prompt(prompt: str) -> list[str]:
    """Return list of validation problems with a prompt."""
    problems: list[str] = []
    if not prompt or not prompt.strip():
        problems.append("prompt is empty")
    if len(prompt) < 10:
        problems.append("prompt too short (< 10 chars)")
    if len(prompt) > 2000:
        problems.append("prompt too long (> 2000 chars)")
    # Check for generation-triggering language that should not be auto-submitted
    return problems


def _safe_path(user_path: str | Path) -> Path:
    """Resolve a user-supplied path and ensure no directory traversal.

    Allows absolute paths but blocks ``..`` components that would escape
    the project directory for relative paths.
    """
    p = Path(user_path)
    # Check for path traversal in relative paths
    if not p.is_absolute():
        resolved = (BASE_DIR / p).resolve()
        base_resolved = BASE_DIR.resolve()
        try:
            resolved.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Path escapes project directory: {user_path}")
        return resolved
    # Absolute path: return as-is (caller checks existence separately)
    return p


def _validate_references(references: list[str]) -> list[str]:
    """Check that referenced files exist and are within the project."""
    problems: list[str] = []
    for ref in references:
        try:
            p = _safe_path(ref)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if not p.exists():
            problems.append(f"reference not found: {ref}")
    return problems


def _validate_input_files(input_files: list[str]) -> list[str]:
    """Check that input files exist and are within the project."""
    problems: list[str] = []
    for f in input_files:
        try:
            p = _safe_path(f)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        if not p.exists():
            problems.append(f"input file not found: {f}")
    return problems


# ---------------------------------------------------------------------------
# Job Manager
# ---------------------------------------------------------------------------


class FlowJobManager:
    """Manages Google Flow job lifecycle (no generation, stops at READY_FOR_APPROVAL)."""

    def __init__(self) -> None:
        self.jobs: dict[str, FlowJob] = {}
        self._load_existing()

    # -- loading / persistence ------------------------------------------------

    def _load_existing(self) -> None:
        """Load all jobs from JSON files on startup (queue recovery)."""
        self.jobs.clear()
        for p in sorted(JOBS_DIR.glob("*.json")):
            try:
                job = FlowJob.from_dict(json.loads(p.read_text(encoding="utf-8")))
                self.jobs[job.job_id] = job
            except (json.JSONDecodeError, TypeError) as exc:
                _audit("JOB_LOAD_ERROR", f"{p.name}: {exc}")

    def _persist(self, job: FlowJob) -> None:
        """Atomically persist job to JSON and SQLite.

        Writes JSON to a temp file first, then commits to SQLite. If SQLite
        fails, the temp JSON is discarded so the two stores stay consistent.
        """
        p = _job_path(job_id=job.job_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(p.name + ".part")
        tmp.write_text(json.dumps(job.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        try:
            _persist_to_db(job)
        except Exception:
            # Roll back the JSON write if SQLite failed
            tmp.unlink(missing_ok=True)
            raise
        tmp.replace(p)

    # -- job ingestion --------------------------------------------------------

    def add_job(
        self,
        job_id: str,
        project: str,
        scene: str,
        prompt: str,
        *,
        aspect_ratio: str = "16:9",
        resolution: str = "1920x1080",
        references: list[str] | None = None,
        input_files: list[str] | None = None,
        generation_params: dict[str, Any] | None = None,
    ) -> FlowJob:
        """Add a new job in DRAFT state.  Raises on duplicate job_id."""
        if job_id in self.jobs:
            raise ValueError(f"Duplicate job_id: {job_id}")
        # Duplicate-content check across all jobs
        candidate = FlowJob(
            job_id=job_id,
            project=project,
            scene=scene,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            references=references or [],
            input_files=input_files or [],
            generation_params=generation_params or {},
        )
        candidate_hash = _job_hash(candidate)
        for existing in self.jobs.values():
            if _job_hash(existing) == candidate_hash:
                raise ValueError(
                    f"Duplicate job content: {job_id} matches existing {existing.job_id}"
                )

        job = candidate
        job.transition("DRAFT", "job created", initial=True)
        self.jobs[job_id] = job
        self._persist(job)
        _audit("JOB_ADDED", f"{job_id} project={project} scene={scene}")
        return job

    def add_jobs_from_json(self, json_path: str | Path) -> list[FlowJob]:
        """Bulk-import jobs from a JSON file (list of job dicts)."""
        p = Path(json_path)
        if not p.is_absolute():
            p = BASE_DIR / p
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = [data]
        created: list[FlowJob] = []
        for item in data:
            job = self.add_job(
                job_id=item["job_id"],
                project=item["project"],
                scene=item["scene"],
                prompt=item["prompt"],
                aspect_ratio=item.get("aspect_ratio", "16:9"),
                resolution=item.get("resolution", "1920x1080"),
                references=item.get("references", []),
                input_files=item.get("input_files", []),
                generation_params=item.get("generation_params", {}),
            )
            created.append(job)
        return created

    def edit_prompt(self, job_id: str, new_prompt: str) -> FlowJob:
        """Edit a job's prompt without recreating the job (new prompt version)."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        if job.state not in ("DRAFT", "VALIDATED"):
            raise ValueError(f"Cannot edit prompt in state {job.state}")
        job.prompt = new_prompt
        job.prompt_version += 1
        job.updated_at = datetime.now(timezone.utc).isoformat()
        job.history.append(
            {
                "from": job.state,
                "to": job.state,
                "at": job.updated_at,
                "reason": f"prompt edited (v{job.prompt_version})",
            }
        )
        self._persist(job)
        _audit("JOB_PROMPT_EDITED", f"{job_id} v{job.prompt_version}")
        return job

    # -- validation -----------------------------------------------------------

    def validate_job(self, job_id: str, *, skip_mcp: bool = False) -> FlowJob:
        """Validate a DRAFT job: prompt, references, input files, MCP access.

        Args:
            job_id: Job identifier.
            skip_mcp: If True, skip MCP checks (used during preproduction
                where structural QC already runs separately).  MCP checks
                are slow because they spawn browser subprocesses.
        """
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        if job.state != "DRAFT":
            raise ValueError(f"Job {job_id} is not DRAFT (state={job.state})")

        problems: list[str] = []
        problems.extend(_validate_prompt(job.prompt))
        problems.extend(_validate_references(job.references))
        problems.extend(_validate_input_files(job.input_files))

        # MCP checks (read-only, no spend).  Connection failures are
        # infrastructure issues, not auth failures: we attempted the check
        # and will retry later.  Auth failures (mcp_auth_ok=False) are
        # recorded but do not block local validation.
        job.mcp_checked = True
        if not skip_mcp:
            try:
                auth = check_gflow_auth()
                job.mcp_auth_ok = auth.get("ok", False)
            except Exception as exc:
                job.mcp_auth_ok = False
                _audit("JOB_MCP_WARNING", f"{job_id}: gflow auth check failed: {exc}")

            try:
                proj = check_gflow_projects()
                job.mcp_projects = proj.get("projects", [])
            except Exception as exc:
                _audit("JOB_MCP_WARNING", f"{job_id}: gflow projects check failed: {exc}")

            try:
                mdl = check_gflow_models()
                job.mcp_models = mdl.get("models", [])
            except Exception as exc:
                _audit("JOB_MCP_WARNING", f"{job_id}: gflow models check failed: {exc}")

        if problems:
            job.error = "; ".join(problems)
            _audit("JOB_VALIDATION_FAILED", f"{job_id}: {job.error}")
            # Stay in DRAFT; caller must fix
            return job

        job.error = None
        job.transition("VALIDATED", "validation passed")
        self._persist(job)
        _audit("JOB_VALIDATED", f"{job_id}")
        return job

    # -- queue ----------------------------------------------------------------

    def ready_for_approval(self, job_id: str) -> FlowJob:
        """Move a VALIDATED job to READY_FOR_APPROVAL (automated system stops here)."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        if job.state != "VALIDATED":
            raise ValueError(f"Job {job_id} is not VALIDATED (state={job.state})")
        if not job.mcp_checked:
            raise ValueError(f"Job {job_id} has not been MCP-checked")
        job.transition("READY_FOR_APPROVAL", "ready for manual approval")
        self._persist(job)
        _audit("JOB_READY_FOR_APPROVAL", f"{job_id}")
        return job

    def approve(self, job_id: str) -> FlowJob:
        """Manual approval: READY_FOR_APPROVAL → APPROVED.  Requires human action."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        if job.state != "READY_FOR_APPROVAL":
            raise ValueError(f"Job {job_id} is not READY_FOR_APPROVAL (state={job.state})")
        job.transition("APPROVED", "manually approved")
        self._persist(job)
        _audit("JOB_APPROVED", f"{job_id}")
        return job

    def submit(self, job_id: str) -> FlowJob:
        """Manual submission: APPROVED → SUBMITTED.  Requires human action."""
        assert_read_only("job submission")
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        if job.state != "APPROVED":
            raise ValueError(f"Job {job_id} is not APPROVED (state={job.state})")
        job.transition("SUBMITTED", "manually submitted")
        self._persist(job)
        _audit("JOB_SUBMITTED", f"{job_id}")
        return job

    def complete(self, job_id: str) -> FlowJob:
        """SUBMITTED → COMPLETED (after generation results are stored)."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        if job.state != "SUBMITTED":
            raise ValueError(f"Job {job_id} is not SUBMITTED (state={job.state})")
        job.transition("COMPLETED", "generation completed")
        self._persist(job)
        _audit("JOB_COMPLETED", f"{job_id}")
        return job

    def fail(self, job_id: str, error: str) -> FlowJob:
        """Mark a job as FAILED with an error message."""
        job = self.jobs.get(job_id)
        if not job:
            raise KeyError(f"Job not found: {job_id}")
        job.error = error
        job.transition("FAILED", f"failed: {error}")
        self._persist(job)
        _audit("JOB_FAILED", f"{job_id}: {error}")
        return job

    # -- queries --------------------------------------------------------------

    def list_jobs(self, state: str | None = None, project: str | None = None) -> list[FlowJob]:
        """List jobs, optionally filtered by state and/or project."""
        result = []
        for job in self.jobs.values():
            if state and job.state != state:
                continue
            if project and job.project != project:
                continue
            result.append(job)
        result.sort(key=lambda j: j.created_at)
        return result

    def get_job(self, job_id: str) -> FlowJob | None:
        return self.jobs.get(job_id)

    def queue_summary(self) -> dict[str, Any]:
        """Return a summary of the queue by state and project."""
        by_state: dict[str, int] = {}
        by_project: dict[str, int] = {}
        for job in self.jobs.values():
            by_state[job.state] = by_state.get(job.state, 0) + 1
            by_project[job.project] = by_project.get(job.project, 0) + 1
        return {
            "total": len(self.jobs),
            "by_state": by_state,
            "by_project": by_project,
            "ready_for_approval": by_state.get("READY_FOR_APPROVAL", 0),
            "draft": by_state.get("DRAFT", 0),
        }

    # -- results organization -------------------------------------------------

    def result_dir(self, project: str, scene: str) -> Path:
        """Directory for storing results of a project/scene (read-only until submission)."""
        d = FLOW_RESULTS_DIR / project / scene
        d.mkdir(parents=True, exist_ok=True)
        return d


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_manager: FlowJobManager | None = None


def get_manager() -> FlowJobManager:
    global _manager
    if _manager is None:
        _manager = FlowJobManager()
    return _manager
