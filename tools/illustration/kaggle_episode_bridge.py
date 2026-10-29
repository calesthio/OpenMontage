#!/usr/bin/env python3
"""tools/illustration/kaggle_episode_bridge.py - the real bridge.

One Kaggle kernel per batch. The job is embedded into the proven kernel
runner (`tools/kaggle_bridge/s7_bakeoff_run.py`), pushed ONCE (no polling
inside), and the output is downloaded afterwards.

The bridge never prints the token; the Kaggle CLI reads KAGGLE_API_TOKEN from
the environment. Media stays in /tmp or in the gitignored episode assets.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional

REPO = Path(__file__).resolve().parents[2]
KERNEL_SLUG = "forts845/openmontage-runner"
RUN_PY = REPO / "tools/kaggle_bridge/s7_bakeoff_run.py"
KAGGLE_CMD = "kaggle"
OUT_ROOT = Path("/tmp/kilo/episode_out")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _redact(text: str) -> str:
    return re.sub(r"[0-9a-f]{32,}", "<redacted>", text or "")


class KaggleEpisodeBridge:
    """Submit one batch per kernel, fetch the output afterwards."""

    def __init__(self, kernel_slug: str = KERNEL_SLUG,
                 work_root: Optional[str | Path] = None,
                 kaggle_cmd: str = KAGGLE_CMD,
                 enable_gpu: bool = True,
                 enable_internet: bool = True) -> None:
        self.kernel_slug = kernel_slug
        self.work_root = Path(work_root) if work_root else \
            REPO / "projects" / "episode_jobs"
        self.kaggle_cmd = kaggle_cmd
        self.enable_gpu = enable_gpu
        self.enable_internet = enable_internet

    # ---------------------------------------------------------------- job
    def _embed(self, run_text: str, job: Dict[str, Any]) -> str:
        marker = "JOB_EMBEDDED = None"
        if marker not in run_text:
            raise RuntimeError("JOB_EMBEDDED marker missing in the kernel runner")
        literal = json.dumps(json.dumps(job, ensure_ascii=False))
        return run_text.replace(marker, f"JOB_EMBEDDED = json.loads({literal})\n", 1)

    def submit(self, job: Dict[str, Any]) -> Dict[str, Any]:
        from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool

        work = self.work_root / job["job_id"]
        work.mkdir(parents=True, exist_ok=True)
        run_text = self._embed(RUN_PY.read_text(encoding="utf-8"), job)
        bridge = KaggleBridgeTool()
        built = bridge.execute({
            "command": "build_job_folder", "job_folder": str(work),
            "job_id": job["job_id"], "kernel_slug": self.kernel_slug,
            "job": job, "run_py": run_text, "enable_gpu": self.enable_gpu,
            "enable_internet": self.enable_internet, "kaggle_cmd": self.kaggle_cmd,
        })
        if not built.success:
            raise RuntimeError(f"BUILD FAILED: {built.error}")
        (work / "job.json").write_text(json.dumps(job, indent=2), encoding="utf-8")

        pushed = bridge.execute({
            "command": "push", "job_folder": str(work),
            "kernel_slug": self.kernel_slug, "timeout": 6600,
            "accelerator": "gpu", "max_retries": 1, "kaggle_cmd": self.kaggle_cmd,
        })
        if not pushed.success:
            raise RuntimeError(f"PUSH FAILED: {pushed.error}")
        (work / "submitted.json").write_text(json.dumps({
            "job_id": job["job_id"], "kernel_slug": self.kernel_slug,
            "num_renders": len(job.get("renders") or []),
            "submitted_utc": _now(),
        }, indent=2), encoding="utf-8")
        return {"run_id": job["job_id"], "job_id": job["job_id"],
                "work_dir": str(work)}

    # --------------------------------------------------------------- fetch
    def fetch(self, job: Dict[str, Any], run_id: str) -> Path:
        from tools.kaggle_bridge.kaggle_bridge import KaggleBridgeTool

        dest = OUT_ROOT / (run_id or job["job_id"])
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True, exist_ok=True)
        bridge = KaggleBridgeTool()
        out = bridge.execute({
            "command": "fetch_output", "kernel_slug": self.kernel_slug,
            "dest": str(dest), "file_pattern": "*", "kaggle_cmd": self.kaggle_cmd,
        })
        if not out.success:
            raise RuntimeError(f"FETCH FAILED: {out.error}")
        folder = dest / job.get("output_dir", "")
        root = folder if folder.is_dir() else dest
        if not (root / "manifest.json").is_file():
            raise RuntimeError(f"the fetched tree has no manifest: {root}")
        return root

    # -------------------------------------------------------------- status
    def status(self) -> str:
        proc = subprocess.run([self.kaggle_cmd, "kernels", "status",
                               self.kernel_slug],
                              capture_output=True, text=True, timeout=120)
        raw = _redact((proc.stdout or proc.stderr or "").strip())
        match = re.search(r"KernelWorkerStatus\.([A-Za-z_]+)", raw)
        return match.group(1) if match else (raw or "UNKNOWN")
