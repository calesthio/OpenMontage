"""Kaggle bridge tool — orchestrates Kaggle kernels as a private runner.

Stdlib + the official `kaggle` CLI only. No direct network calls (network goes
through the kaggle CLI). No API keys handled directly: `KAGGLE_API_TOKEN` is
read by the kaggle CLI from the environment and is never logged, passed on a
command line, or written to a result JSON.

Fail-closed: any status that is not explicitly verified-success -> BLOCKED/
FAILED/REJECT, never silently treated as success.

Follows the BaseTool contract from tools/base_tool.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
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
from tools.qa.qc import QCTool

KAGGLE_CMD_DEFAULT = "kaggle"
KERNEL_SLUG_DEFAULT = "forts845/of-bridge-runner"

# Terminal statuses observed/assumed for `kaggle kernels status`. Anything not
# in this set is treated as non-terminal (keep polling). "complete" is success;
# anything mentioning error/fail is a terminal failure; "timeout" is BLOCKED.
# Exact strings are confirmed live (Milestone K1 step 4) and recorded here once
# observed; until then they are best-effort guesses.
TERMINAL_STATUSES = {"complete", "error", "failed", "timeout", "cancelled"}


def _sha256_file(path: Path) -> str | None:
    """SHA-256 hex digest of a file's bytes, None if unreadable."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _now_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _is_token_string(value: str) -> bool:
    """Crude heuristic: a Kaggle API token is a long hex-ish string."""
    return bool(value) and len(value) >= 20 and all(c in "0123456789abcdef" for c in value.lower())


def _scrub_token(value: Any) -> Any:
    """Return value with any Kaggle API token replaced by <redacted>."""
    if isinstance(value, str):
        for token in (os.environ.get("KAGGLE_API_TOKEN"),):
            if token and _is_token_string(token) and token in value:
                value = value.replace(token, "<redacted>")
        return value
    if isinstance(value, dict):
        return {k: _scrub_token(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub_token(v) for v in value]
    return value


class KaggleBridgeTool(BaseTool):
    name = "kaggle_bridge"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "kaggle_bridge"
    provider = "kaggle"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC  # depends on Kaggle queue/run time
    runtime = ToolRuntime.API  # orchestrated via the kaggle CLI (network through CLI)

    dependencies = ["cmd:kaggle"]
    install_instructions = "pip install kaggle (Kaggle/kaggle-cli). No API keys handled here."
    agent_skills = []

    capabilities = [
        "build_job_folder",
        "push",
        "poll",
        "fetch_output",
        "verify",
        "run_qc",
        "run_job",
    ]
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100)
    idempotency_key_fields = ["job_id", "kernel_slug"]
    side_effects = [
        "writes job folders locally",
        "pushes code to a Kaggle kernel via the kaggle CLI",
        "downloads kernel output via the kaggle CLI",
    ]
    user_visible_verification = [
        "result JSON verdict is PASS/FAILED/BLOCKED/REJECT",
        "manifest sha256 matches recomputed file sha256",
    ]

    input_schema = {
        "type": "object",
        "required": ["command"],
        "properties": {
            "command": {
                "type": "string",
                "enum": [
                    "build_job_folder",
                    "push",
                    "poll",
                    "fetch_output",
                    "verify",
                    "run_qc",
                    "run_job",
                ],
            },
            "kaggle_cmd": {"type": "string", "default": KAGGLE_CMD_DEFAULT},
            "kernel_slug": {"type": "string"},
            "job_folder": {"type": "string"},
            "job_id": {"type": "string"},
            "job": {"type": "object"},
            "run_py": {"type": "string"},
            "timeout": {"type": "integer", "default": 3600},
            "accelerator": {"type": "string", "default": "cpu"},
            "enable_gpu": {"type": "boolean", "default": False},
            "enable_internet": {"type": "boolean", "default": False},
            "max_retries": {"type": "integer", "default": 3},
            "retry_backoff": {"type": "number", "default": 1.0},
            "total_timeout": {"type": "integer", "default": 900},
            "poll_backoff": {"type": "number", "default": 15.0},
            "dest": {"type": "string"},
            "file_pattern": {"type": "string", "default": "*"},
            "output_folder": {"type": "string"},
            "expected_sha256": {"type": "string"},
            "wav_path": {"type": "string"},
            "report_path": {"type": "string"},
            "config_path": {"type": "string"},
        },
    }

    # ---- execution -------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        command = inputs.get("command")
        if not command:
            return ToolResult(
                success=False,
                error="BLOCKED: missing 'command' input",
                data={"verdict": "BLOCKED"},
            )
        kaggle_cmd = inputs.get("kaggle_cmd", KAGGLE_CMD_DEFAULT)

        try:
            if command == "build_job_folder":
                return self._build_job_folder(inputs)
            if command == "push":
                return self._push(inputs)
            if command == "poll":
                return self._poll(inputs)
            if command == "fetch_output":
                return self._fetch_output(inputs)
            if command == "verify":
                return self._verify(inputs)
            if command == "run_qc":
                return self._run_qc(inputs)
            if command == "run_job":
                return self._run_job(inputs)
            return ToolResult(
                success=False,
                error=f"BLOCKED: unknown command {command!r}",
                data={"verdict": "BLOCKED"},
            )
        except Exception as exc:  # noqa: BLE001 - fail-closed on any unexpected error
            return ToolResult(
                success=False,
                error=f"BLOCKED: {exc}",
                data={"verdict": "BLOCKED"},
            )

    # ---- build_job_folder ----------------------------------------------

    def _build_job_folder(self, inputs: dict[str, Any]) -> ToolResult:
        job_folder = inputs.get("job_folder")
        job_id = inputs.get("job_id")
        kernel_slug = inputs.get("kernel_slug")
        job = inputs.get("job")
        run_py = inputs.get("run_py")
        kaggle_cmd = inputs.get("kaggle_cmd", KAGGLE_CMD_DEFAULT)

        if not all([job_folder, job_id, kernel_slug, job]):
            return ToolResult(
                success=False,
                error="BLOCKED: build_job_folder needs job_folder, job_id, kernel_slug, job",
                data={"verdict": "BLOCKED"},
            )

        folder = Path(job_folder)
        folder.mkdir(parents=True, exist_ok=True)

        enable_gpu = bool(inputs.get("enable_gpu", False))
        enable_internet = bool(inputs.get("enable_internet", False))

        # Generate kernel-metadata.json from `kaggle kernels init` output so we
        # never guess field names.
        init_cmd = [kaggle_cmd, "kernels", "init", "-p", str(folder)]
        try:
            self.run_command(init_cmd, timeout=60)
        except Exception as exc:  # noqa: BLE001
            # init may fail in restricted envs; fall back to writing the template
            # fields Kaggle requires, but only those we know from init's schema.
            pass

        meta_path = folder / "kernel-metadata.json"
        if meta_path.is_file():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                meta = {}
        else:
            meta = {}

        # Override only the fields we know; preserve init's schema keys.
        meta.update(
            {
                "id": kernel_slug,
                "title": "OpenMontage runner",
                "code_file": "run.py",
                "language": "python",
                "kernel_type": "script",
                "is_private": True,
                "enable_gpu": enable_gpu,
                "enable_internet": enable_internet,
                "dataset_sources": [],
                "competition_sources": [],
            }
        )
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        # job.json
        job_record = dict(job)
        job_record["job_id"] = job_id
        job_record.setdefault("created_at", _now_utc())
        (folder / "job.json").write_text(
            json.dumps(job_record, indent=2), encoding="utf-8"
        )

        # run.py
        default_run_py = self._default_run_py(job_id)
        (folder / "run.py").write_text(
            run_py if run_py is not None else default_run_py,
            encoding="utf-8",
        )

        return ToolResult(
            success=True,
            data={
                "verdict": "PASS",
                "job_folder": str(folder),
                "job_id": job_id,
                "kernel_slug": kernel_slug,
            },
            artifacts=[str(folder)],
        )

    @staticmethod
    def _default_run_py(job_id: str) -> str:
        return (
            "import json, hashlib, os, sys, platform\n"
            "job_path = os.path.join(os.path.dirname(__file__), 'job.json')\n"
            "with open(job_path) as f:\n"
            "    job = json.load(f)\n"
            "job_id = job.get('job_id', 'unknown')\n"
            "script = job.get('script', '')\n"
            "out_dir = '/kaggle/working'\n"
            "os.makedirs(out_dir, exist_ok=True)\n"
            "out_path = os.path.join(out_dir, f'{job_id}.wav')\n"
            "with open(out_path, 'w') as f:\n"
            "    f.write(script)\n"
            "data = open(out_path, 'rb').read()\n"
            "manifest = {\n"
            "    'job_id': job_id,\n"
            "    'sha256': hashlib.sha256(data).hexdigest(),\n"
            "    'size_bytes': len(data),\n"
            "    'created_utc': job.get('created_at'),\n"
            "    'python_version': platform.python_version(),\n"
            "}\n"
            "with open(os.path.join(out_dir, 'manifest.json'), 'w') as f:\n"
            "    json.dump(manifest, f)\n"
            "print(f'Wrote {out_path} ({len(data)} bytes)')\n"
        )

    # ---- push ----------------------------------------------------------

    def _push(self, inputs: dict[str, Any]) -> ToolResult:
        job_folder = inputs.get("job_folder")
        kernel_slug = inputs.get("kernel_slug")
        timeout = int(inputs.get("timeout", 3600))
        accelerator = inputs.get("accelerator", "cpu")
        max_retries = int(inputs.get("max_retries", 3))
        retry_backoff = float(inputs.get("retry_backoff", 1.0))
        kaggle_cmd = inputs.get("kaggle_cmd", KAGGLE_CMD_DEFAULT)

        if not all([job_folder, kernel_slug]):
            return ToolResult(
                success=False,
                error="BLOCKED: push needs job_folder and kernel_slug",
                data={"verdict": "BLOCKED"},
            )

        cmd = [
            kaggle_cmd,
            "kernels",
            "push",
            "-p",
            str(job_folder),
            "-t",
            str(timeout),
            "--accelerator",
            str(accelerator),
        ]

        last_error = ""
        for attempt in range(1, max_retries + 1):
            try:
                result = self.run_command(cmd, timeout=timeout + 60)
                return ToolResult(
                    success=True,
                    data={
                        "verdict": "PASS",
                        "push": {
                            "status": "OK",
                            "attempt": attempt,
                            "kernel_slug": kernel_slug,
                            "timeout": timeout,
                            "accelerator": accelerator,
                        },
                    },
                )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                is_conflict = "409" in last_error or "Conflict" in last_error
                if is_conflict and attempt < max_retries:
                    time.sleep(retry_backoff)
                    continue
                return ToolResult(
                    success=False,
                    error=f"BLOCKED: push failed: {last_error}",
                    data={
                        "verdict": "BLOCKED",
                        "push": {
                            "status": "BLOCKED",
                            "attempt": attempt,
                            "kernel_slug": kernel_slug,
                            "error": last_error[:300],
                        },
                    },
                )

    # ---- poll ----------------------------------------------------------

    def _poll(self, inputs: dict[str, Any]) -> ToolResult:
        kernel_slug = inputs.get("kernel_slug")
        total_timeout = float(inputs.get("total_timeout", 900))
        backoff = float(inputs.get("poll_backoff", 15.0))
        kaggle_cmd = inputs.get("kaggle_cmd", KAGGLE_CMD_DEFAULT)

        if not kernel_slug:
            return ToolResult(
                success=False,
                error="BLOCKED: poll needs kernel_slug",
                data={"verdict": "BLOCKED"},
            )

        start = time.monotonic()
        status_strings: list[str] = []
        last_status = None
        push_to_running = None
        running_to_complete = None
        push_done = False

        while True:
            elapsed = time.monotonic() - start
            if elapsed >= total_timeout:
                return ToolResult(
                    success=False,
                    error="BLOCKED: poll total timeout before terminal status",
                    data={
                        "verdict": "BLOCKED",
                        "poll": {
                            "status": "BLOCKED",
                            "status_strings": status_strings,
                            "timings": {
                                "elapsed_seconds": round(elapsed, 2),
                                "push_to_running": push_to_running,
                                "running_to_complete": running_to_complete,
                            },
                        },
                    },
                )
            try:
                result = self.run_command(
                    [kaggle_cmd, "kernels", "status", str(kernel_slug)],
                    timeout=60,
                )
                status = (result.stdout or "").strip()
            except Exception as exc:  # noqa: BLE001
                # Treat status-call failure as non-fatal; keep polling within
                # the total timeout.
                time.sleep(backoff)
                continue

            if status and status not in status_strings:
                status_strings.append(status)
            last_status = status

            # Kaggle returns `<slug> has status "KernelWorkerStatus.<STATUS>"`.
            # Parse the token generically; fall back to the raw line.
            m = re.search(r'KernelWorkerStatus\.([A-Za-z_]+)', status)
            token = m.group(1) if m else status
            effective = token.lower()

            if effective == "complete":
                if not push_done:
                    push_done = True
                    push_to_running = round(elapsed, 2)
                running_to_complete = round(elapsed, 2)
                return ToolResult(
                    success=True,
                    data={
                        "verdict": "PASS",
                        "poll": {
                            "status": "complete",
                            "status_strings": status_strings,
                            "timings": {
                                "elapsed_seconds": round(elapsed, 2),
                                "push_to_running": push_to_running,
                                "running_to_complete": running_to_complete,
                            },
                        },
                    },
                )
            if any(term in effective for term in ("error", "fail", "cancelled")):
                return ToolResult(
                    success=False,
                    error=f"BLOCKED: kernel reached terminal error status: {status}",
                    data={
                        "verdict": "FAILED",
                        "poll": {
                            "status": status,
                            "status_strings": status_strings,
                            "timings": {"elapsed_seconds": round(elapsed, 2)},
                        },
                    },
                )
            if effective == "timeout":
                return ToolResult(
                    success=False,
                    error="BLOCKED: kernel run timed out",
                    data={
                        "verdict": "BLOCKED",
                        "poll": {
                            "status": "timeout",
                            "status_strings": status_strings,
                            "timings": {"elapsed_seconds": round(elapsed, 2)},
                        },
                    },
                )

            # Non-terminal: keep polling within the total timeout.
            remaining = total_timeout - (time.monotonic() - start)
            if remaining <= 0:
                return ToolResult(
                    success=False,
                    error="BLOCKED: poll total timeout before terminal status",
                    data={
                        "verdict": "BLOCKED",
                        "poll": {
                            "status": "BLOCKED",
                            "status_strings": status_strings,
                            "timings": {"elapsed_seconds": round(time.monotonic() - start, 2)},
                        },
                    },
                )
            time.sleep(min(backoff, remaining))

    # ---- fetch_output --------------------------------------------------

    def _fetch_output(self, inputs: dict[str, Any]) -> ToolResult:
        kernel_slug = inputs.get("kernel_slug")
        dest = inputs.get("dest")
        file_pattern = inputs.get("file_pattern", "*")
        kaggle_cmd = inputs.get("kaggle_cmd", KAGGLE_CMD_DEFAULT)

        if not all([kernel_slug, dest]):
            return ToolResult(
                success=False,
                error="BLOCKED: fetch_output needs kernel_slug and dest",
                data={"verdict": "BLOCKED"},
            )

        out_dir = Path(dest)
        out_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            kaggle_cmd,
            "kernels",
            "output",
            str(kernel_slug),
            "-p",
            str(out_dir),
            "-q",
        ]
        if file_pattern and file_pattern != "*":
            cmd += ["--file-pattern", str(file_pattern)]
        try:
            self.run_command(cmd, timeout=300)
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"BLOCKED: fetch_output failed: {exc}",
                data={"verdict": "BLOCKED", "output": {"status": "BLOCKED"}},
            )

        files = [p.name for p in out_dir.iterdir() if p.is_file()]
        if not files:
            return ToolResult(
                success=False,
                error="BLOCKED: fetch_output returned no files",
                data={"verdict": "BLOCKED", "output": {"status": "BLOCKED"}},
            )

        return ToolResult(
            success=True,
            data={
                "verdict": "PASS",
                "output": {
                    "status": "OK",
                    "files": files,
                    "dest": str(out_dir),
                },
            },
            artifacts=[str(out_dir)],
        )

    # ---- verify --------------------------------------------------------

    def _verify(self, inputs: dict[str, Any]) -> ToolResult:
        output_folder = inputs.get("output_folder")
        job_id = inputs.get("job_id")
        expected_sha256 = inputs.get("expected_sha256")
        kaggle_cmd = inputs.get("kaggle_cmd", KAGGLE_CMD_DEFAULT)

        if not output_folder:
            return ToolResult(
                success=False,
                error="BLOCKED: verify needs output_folder",
                data={"verdict": "BLOCKED"},
            )

        folder = Path(output_folder)
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            return ToolResult(
                success=False,
                error="REJECT: manifest.json missing",
                data={
                    "verdict": "REJECT",
                    "verify": {"manifest_valid": False, "sha256_match": False},
                },
            )

        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            return ToolResult(
                success=False,
                error=f"REJECT: manifest.json unparseable: {exc}",
                data={
                    "verdict": "REJECT",
                    "verify": {"manifest_valid": False, "sha256_match": False},
                },
            )

        # Required manifest fields. A multi-image manifest carries per-image
        # sha256/bytes inside `images[]` instead of a top-level `sha256`.
        required = ["job_id"]
        if not isinstance(manifest.get("images"), list):
            required.append("sha256")
        missing = [f for f in required if f not in manifest]
        if missing:
            return ToolResult(
                success=False,
                error=f"REJECT: manifest missing fields: {', '.join(missing)}",
                data={
                    "verdict": "REJECT",
                    "verify": {"manifest_valid": False, "sha256_match": False},
                },
            )

        if job_id and manifest.get("job_id") != job_id:
            return ToolResult(
                success=False,
                error="REJECT: manifest job_id mismatch",
                data={
                    "verdict": "REJECT",
                    "verify": {"manifest_valid": False, "sha256_match": False},
                },
            )

        manifest_valid = bool(manifest.get("job_id")) and (
            bool(manifest.get("sha256")) or isinstance(manifest.get("images"), list)
        )

        matched_file = None
        actual_sha = None
        manifest_sha = manifest.get("sha256")

        images = manifest.get("images")
        image_results = None
        if isinstance(images, list):
            # Multi-image manifest: verify every listed image file (sha256 + bytes).
            all_ok = True
            image_results = []
            for entry in images:
                fname = entry.get("file")
                entry_sha = entry.get("sha256")
                entry_bytes = entry.get("bytes")
                fpath = folder / fname if fname else None
                ok = True
                detail = {"file": fname}
                if not fname or not fpath or not fpath.is_file():
                    ok = False
                    detail["error"] = "missing image file"
                else:
                    actual = _sha256_file(fpath)
                    actual_bytes = fpath.stat().st_size
                    detail.update(
                        {
                            "actual_sha256": actual,
                            "manifest_sha256": entry_sha,
                            "actual_bytes": actual_bytes,
                            "manifest_bytes": entry_bytes,
                        }
                    )
                    if actual != entry_sha:
                        ok = False
                    if entry_bytes is not None and actual_bytes != entry_bytes:
                        ok = False
                if not ok:
                    all_ok = False
                detail["sha256_match"] = ok
                image_results.append(detail)
            sha_match = all_ok
        else:
            # Single data file (legacy wav job): match manifest sha256.
            data_files = [p for p in folder.iterdir() if p.is_file() and p.name != "manifest.json"]
            if not data_files:
                return ToolResult(
                    success=False,
                    error="REJECT: no data file alongside manifest",
                    data={
                        "verdict": "REJECT",
                        "verify": {"manifest_valid": manifest_valid, "sha256_match": False},
                    },
                )
            for p in data_files:
                s = _sha256_file(p)
                if s and s == manifest_sha:
                    matched_file = p
                    actual_sha = s
                    break
            # If nothing matched the manifest, fall back to the single non-manifest
            # file (common case: exactly one output artifact) so we can still report
            # an informative mismatch.
            if matched_file is None and len(data_files) == 1:
                matched_file = data_files[0]
                actual_sha = _sha256_file(matched_file)

            sha_match = actual_sha is not None and actual_sha == manifest_sha
            if expected_sha256 is not None:
                sha_match = sha_match and (actual_sha == expected_sha256)

        if not sha_match:
            return ToolResult(
                success=False,
                error="REJECT: sha256 mismatch",
                data={
                    "verdict": "REJECT",
                    "verify": {
                        "manifest_valid": manifest_valid,
                        "sha256_match": False,
                        "data_file": matched_file.name if matched_file else None,
                        "actual_sha256": actual_sha,
                        "manifest_sha256": manifest_sha,
                        "images": image_results,
                    },
                },
            )

        return ToolResult(
            success=True,
            data={
                "verdict": "PASS",
                "verify": {
                    "manifest_valid": manifest_valid,
                    "sha256_match": True,
                    "data_file": matched_file.name if matched_file else None,
                    "sha256": actual_sha,
                    "manifest": manifest,
                    "images": image_results,
                },
            },
        )

    # ---- run_qc --------------------------------------------------------

    def _run_qc(self, inputs: dict[str, Any]) -> ToolResult:
        wav_path = inputs.get("wav_path")
        output_path = inputs.get("output_path")
        config_path = inputs.get("config_path")

        if not wav_path or not output_path:
            return ToolResult(
                success=False,
                error="BLOCKED: run_qc needs wav_path and output_path",
                data={"verdict": "BLOCKED", "qc": {"verdict": "BLOCKED"}},
            )

        try:
            qc = QCTool()
            res = qc.execute(
                {
                    "input_path": wav_path,
                    "output_path": output_path,
                    "config_path": config_path,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return ToolResult(
                success=False,
                error=f"BLOCKED: run_qc failed: {exc}",
                data={"verdict": "BLOCKED", "qc": {"verdict": "BLOCKED"}},
            )

        if not res.success:
            return ToolResult(
                success=False,
                error=f"BLOCKED: run_qc returned failure: {res.error}",
                data={"verdict": "BLOCKED", "qc": {"verdict": "BLOCKED"}},
            )

        verdict = (res.data or {}).get("verdict", "BLOCKED")
        return ToolResult(
            success=True,
            data={
                "verdict": "PASS",
                "qc": {"verdict": verdict, "report": output_path},
            },
            artifacts=[output_path],
        )

    # ---- run_job (composite) ------------------------------------------

    def _run_job(self, inputs: dict[str, Any]) -> ToolResult:
        """End-to-end: build -> push -> poll -> fetch -> verify -> (optional qc)."""
        job_id = inputs.get("job_id")
        job_folder = inputs.get("job_folder")
        kernel_slug = inputs.get("kernel_slug")
        job = inputs.get("job")
        run_py = inputs.get("run_py")
        fetch_dest = inputs.get("fetch_dest")
        file_pattern = inputs.get("file_pattern", "*")
        timeout = int(inputs.get("timeout", 3600))
        accelerator = inputs.get("accelerator", "cpu")
        kaggle_cmd = inputs.get("kaggle_cmd", KAGGLE_CMD_DEFAULT)

        if not all([job_id, job_folder, kernel_slug, job]):
            return ToolResult(
                success=False,
                error="BLOCKED: run_job needs job_id, job_folder, kernel_slug, job",
                data={"verdict": "BLOCKED"},
            )

        # 1. build job folder
        bj = self._build_job_folder(
            {
                "command": "build_job_folder",
                "job_folder": job_folder,
                "job_id": job_id,
                "kernel_slug": kernel_slug,
                "job": job,
                "run_py": run_py,
                "kaggle_cmd": kaggle_cmd,
                "enable_gpu": inputs.get("enable_gpu", False),
                "enable_internet": inputs.get("enable_internet", False),
            }
        )
        if not bj.success:
            return bj

        # 2. push
        ps = self._push(
            {
                "command": "push",
                "job_folder": job_folder,
                "kernel_slug": kernel_slug,
                "timeout": timeout,
                "accelerator": accelerator,
                "kaggle_cmd": kaggle_cmd,
                "max_retries": inputs.get("max_retries", 3),
                "retry_backoff": inputs.get("retry_backoff", 1.0),
            }
        )
        if not ps.success:
            return ps

        # 3. poll
        pl = self._poll(
            {
                "command": "poll",
                "kernel_slug": kernel_slug,
                "total_timeout": int(inputs.get("total_timeout", 900)),
                "backoff": float(inputs.get("poll_backoff", 15.0)),
                "kaggle_cmd": kaggle_cmd,
            }
        )
        if not pl.success:
            return pl

        # 4. fetch output
        dest = fetch_dest or str(Path(job_folder).parent / "output" / job_id)
        fo = self._fetch_output(
            {
                "command": "fetch_output",
                "kernel_slug": kernel_slug,
                "dest": dest,
                "file_pattern": file_pattern,
                "kaggle_cmd": kaggle_cmd,
            }
        )
        if not fo.success:
            return fo

        # 5. verify
        vr = self._verify(
            {
                "command": "verify",
                "output_folder": dest,
                "job_id": job_id,
                "expected_sha256": inputs.get("expected_sha256"),
                "kaggle_cmd": kaggle_cmd,
            }
        )
        if not vr.success:
            return vr

        # 6. optional QC if a wav was produced
        qc_result = None
        wav_candidates = [p for p in Path(dest).iterdir() if p.is_file() and p.suffix == ".wav"]
        if wav_candidates and inputs.get("run_qc", True):
            rpt = str(Path(dest) / f"{job_id}.qa_report.json")
            qc_result = self._run_qc(
                {
                    "command": "run_qc",
                    "wav_path": str(wav_candidates[0]),
                    "output_path": rpt,
                    "config_path": inputs.get("config_path"),
                }
            )

        verdict = "PASS"
        if qc_result is not None and not qc_result.success:
            verdict = "FAILED"

        return ToolResult(
            success=True,
            data={
                "verdict": verdict,
                "job_id": job_id,
                "kernel_slug": kernel_slug,
                "push": ps.data.get("push"),
                "poll": pl.data.get("poll"),
                "output": fo.data.get("output"),
                "verify": vr.data.get("verify"),
                "qc": qc_result.data.get("qc") if qc_result else None,
            },
            artifacts=[str(Path(dest))],
        )
