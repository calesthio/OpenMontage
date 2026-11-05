"""Shared helpers for tools that drive the public ``minicut`` CLI.

The CLI prices every request for free and sends nothing until it is run
again with that exact price. These helpers keep that gate: ``quote`` turns
the CLI's needs_yes answer into an ``approval``, and ``send`` sends exactly
that approval and nothing else. The approval carries the CLI's idempotency
key, so sending it again after a timeout or an error never starts a second
paid job. ``collect`` waits for the job and returns the saved file path.

Sign-in and the key stay inside the CLI's own key store. Nothing here reads
or stores a key. Model-specific inputs stay in each tool.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from tools.base_tool import ToolResult

# MiniCut files a result as a library item; this is the item OpenMontage results go to.
LIBRARY_ITEM = "prop:openmontage"
NEEDS_YES = 3  # the CLI's exit code for "priced, nothing sent"
NOT_READY = 6  # the CLI's exit code for "job still running"
INSTALL_INSTRUCTIONS = (
    "Install the MiniCut CLI: curl -fsSL https://minicut.ai/install.sh | bash\n"
    "  Then sign in once: minicut login"
)


def find_cli() -> str | None:
    """Path of the ``minicut`` command, or None when it is not installed."""
    return shutil.which("minicut")


def minicut_home() -> Path:
    """The CLI's home folder: MINICUT_HOME, else ~/.minicut (Windows: %LOCALAPPDATA%\\minicut)."""
    env = os.environ.get("MINICUT_HOME") or os.environ.get("MH_HOME")
    if env:
        return Path(env)
    if platform.system() == "Windows":
        local = os.environ.get("LOCALAPPDATA", "")
        if not local or not local.isascii():
            raise RuntimeError("Set MINICUT_HOME to the MiniCut home folder (minicut doctor shows it)")
        return Path(local) / "minicut"
    return Path.home() / ".minicut"


def run(words: list[str], timeout: int = 900) -> tuple[int, dict[str, Any]]:
    """Run ``minicut <words>``; return its exit code and its last JSON line."""
    exe = find_cli()
    if not exe:
        raise RuntimeError("minicut not found. " + INSTALL_INSTRUCTIONS)
    proc = subprocess.run(
        [exe, *words], capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout, check=False,
    )
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("{")]
    data = json.loads(lines[-1]) if lines else {}
    if not data and proc.returncode not in (0, NEEDS_YES, NOT_READY):
        data = {"error": {"message": (proc.stderr or proc.stdout or "").strip()[-500:]}}
    return proc.returncode, data


def stage(path: str) -> str:
    """Copy an input into the CLI's cache folder, the folders it reads inputs from."""
    src = Path(path).expanduser().resolve()
    if not src.is_file():
        raise ValueError(f"Input file not found: {src}")
    digest = hashlib.sha256(src.read_bytes()).hexdigest()[:16]
    dst = minicut_home() / "cache" / "openmontage" / f"{digest}{src.suffix.lower()}"
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    return str(dst)


def gen_words(
    model: str,
    out_name: str,
    prompt: str | None = None,
    settings: dict[str, Any] | None = None,
    files: list[tuple[str, str | None]] | None = None,
) -> list[str]:
    """``gen`` words for any model: --set word=value pairs, then --in role=file (staged)."""
    words = ["gen", model, out_name]
    if prompt is not None:
        words += ["--prompt", prompt]
    for key, value in (settings or {}).items():
        if value is not None:
            words += ["--set", f"{key}={value}"]
    for role, path in files or []:
        if path:
            words += ["--in", f"{role}={stage(path)}"]
    return words + ["--target", LIBRARY_ITEM, "--json"]


def approval(data: dict[str, Any]) -> dict[str, Any]:
    """The CLI's needs_yes answer as an approval: credits, its key and its quote fingerprint."""
    argv = shlex.split(data["next_step"])
    return {
        "credits": data["max_credits"],
        "model": data.get("model"),
        "key": argv[argv.index("--key") + 1],
        "quote": argv[argv.index("--quote") + 1],
    }


def message(data: dict[str, Any], code: int) -> str:
    """The CLI's error as one line, with its Why and Change when given."""
    err = data.get("error") or {}
    parts = [err.get("message") or err.get("code") or f"minicut exit {code}"]
    if err.get("reason"):
        parts.append(f"Why: {err['reason']}")
    if err.get("change"):
        parts.append(f"Change: {err['change']}")
    return " ".join(parts)


def needs_yes(approved: dict[str, Any], reason: str = "") -> ToolResult:
    """A result that hands the price back for the user's yes. Nothing was sent."""
    return ToolResult(
        success=False,
        error=(
            f"{reason}MiniCut price is {approved['credits']} credits. Nothing was sent. "
            "Show the user this price, then run again with this approval after their yes."
        ),
        data={"approval_required": True, "approval": approved},
        cost_usd=0.0,
    )


def quote(words: list[str]) -> dict[str, Any]:
    """The free price for ``gen`` words, as an approval. Sends nothing."""
    code, data = run(words)
    if code != NEEDS_YES or data.get("state") != "needs_yes":
        raise RuntimeError(message(data, code))
    return approval(data)


def send(words: list[str], approved: dict[str, Any]) -> ToolResult | str:
    """Send exactly the approved line. Returns the job id, or a result to hand back."""
    resend = {"approval_required": False, "approval": approved}
    try:
        code, sent = run(words + [
            "--yes", "--max-credits", str(approved["credits"]),
            "--key", approved["key"], "--quote", approved["quote"],
        ])
    except subprocess.TimeoutExpired:
        return ToolResult(
            success=False, cost_usd=None, data=resend,
            error="minicut did not answer in time. Run again with the same approval; "
            "it is never charged twice.",
        )
    if code == NEEDS_YES and sent.get("state") == "needs_yes":
        # The request or the price changed since the yes: a new price, a new yes.
        return needs_yes(approval(sent), "The price or request changed. ")
    if code == 0 and sent.get("job_id"):
        return sent["job_id"]
    return ToolResult(
        success=False, cost_usd=None, data=resend,
        error=f"MiniCut did not take the job: {message(sent, code)}",
    )


def collect(job_id: str, poll_timeout: int = 900) -> ToolResult | str:
    """Wait for a job. Returns the saved file path, or a result to hand back."""
    deadline = time.monotonic() + int(poll_timeout)
    while True:
        code, got = run(["jobs", "--get", job_id, "--json"])
        row = next((j for j in got.get("jobs", []) if j.get("job_id") == job_id), {})
        if row.get("state") == "done" and row.get("paths"):
            return row["paths"][0]
        if row.get("state") in ("failed", "stopped"):
            return ToolResult(
                success=False,
                cost_usd=None,
                error=f"MiniCut job {row['state']}: {message(row, code)}",
                data={"job_id": job_id, "credits_charged": row.get("credits_charged")},
            )
        if row.get("state") == "done" and not row.get("saving_elsewhere"):
            raise RuntimeError(f"job done but not saved here: {message(row, code)}")
        if code not in (0, NOT_READY):
            raise RuntimeError(message(got, code))
        if time.monotonic() >= deadline:
            return ToolResult(
                success=False,
                cost_usd=None,
                error="Job is still running; run again with resume_job, do not resubmit",
                data={"resume_job": {"job_id": job_id}},
            )
        time.sleep(10)
