"""Cap integration tool — local Loom alternative.

Detects whether Cap (https://cap.so) is installed, checks if it's running,
and picks up recordings from its output directory. If Cap isn't installed,
provides setup guidance the agent can present to the user.

Cap provides:
  - Polished recording UI with webcam overlay
  - Cursor highlight and click effects
  - Hardware-accelerated capture (GPU)
  - Built-in editor with captions
  - Clean system audio capture

This tool does NOT control Cap directly — it acts as a bridge:
  1. Detect Cap installation and status
  2. Guide user through setup if needed
  3. Pick up completed recordings for the screen-demo pipeline
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
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


def _find_cap_binary() -> str | None:
    """Find the Cap executable on the system."""
    sys_platform = platform.system()

    if sys_platform == "Windows":
        # Cap installs to AppData/Local on Windows
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Cap" / "Cap.exe",
            Path(os.environ.get("PROGRAMFILES", "")) / "Cap" / "Cap.exe",
            # Tauri apps sometimes install here
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "cap" / "Cap.exe",
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        # Try PATH
        if shutil.which("Cap") or shutil.which("cap"):
            return shutil.which("Cap") or shutil.which("cap")

    elif sys_platform == "Darwin":
        candidates = [
            Path("/Applications/Cap.app/Contents/MacOS/Cap"),
            Path.home() / "Applications" / "Cap.app" / "Contents" / "MacOS" / "Cap",
        ]
        for c in candidates:
            if c.exists():
                return str(c)

    elif sys_platform == "Linux":
        candidates = ["cap", "Cap"]
        for c in candidates:
            found = shutil.which(c)
            if found:
                return found
        # AppImage or Flatpak
        appimage = Path.home() / "Applications" / "Cap.AppImage"
        if appimage.exists():
            return str(appimage)

    return None


def _find_cap_recordings_dir() -> Path | None:
    """Find Cap's recording output directory."""
    sys_platform = platform.system()

    if sys_platform == "Windows":
        # Cap stores recordings in AppData
        base = Path(os.environ.get("APPDATA", "")) / "so.cap.desktop"
        if base.exists():
            return base
        # Alternative path
        base2 = Path(os.environ.get("LOCALAPPDATA", "")) / "so.cap.desktop"
        if base2.exists():
            return base2

    elif sys_platform == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "so.cap.desktop"
        if base.exists():
            return base

    elif sys_platform == "Linux":
        base = Path.home() / ".local" / "share" / "so.cap.desktop"
        if base.exists():
            return base

    return None


def _is_cap_running() -> bool:
    """Check if Cap is currently running."""
    sys_platform = platform.system()
    try:
        if sys_platform == "Windows":
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Cap.exe", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return "Cap.exe" in result.stdout
        elif sys_platform == "Darwin":
            result = subprocess.run(
                ["pgrep", "-x", "Cap"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        elif sys_platform == "Linux":
            result = subprocess.run(
                ["pgrep", "-x", "cap"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
    except Exception:
        pass
    return False


def _get_recent_recordings(recordings_dir: Path, since_seconds: int = 300) -> list[dict]:
    """Find Cap recordings created within the last N seconds."""
    recordings = []
    cutoff = time.time() - since_seconds

    # Cap stores recordings as directories with output/ subdirs
    for item in sorted(recordings_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not item.is_dir():
            continue
        # Look for video files in the recording directory
        for pattern in ["*.mp4", "output/*.mp4", "output/result.mp4"]:
            for video in item.glob(pattern):
                if video.stat().st_mtime > cutoff:
                    recordings.append({
                        "path": str(video),
                        "name": item.name,
                        "size_mb": round(video.stat().st_size / (1024 * 1024), 1),
                        "modified": video.stat().st_mtime,
                    })

    return recordings[:10]  # Return most recent 10


class CapRecorder(BaseTool):
    name = "cap_recorder"
    version = "0.1.0"
    tier = ToolTier.SOURCE
    capability = "screen_capture"
    provider = "cap"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = []  # No hard dependencies — detection is graceful
    install_instructions = (
        "Cap is a free, open-source Loom alternative.\n\n"
        "Install from: https://cap.so/download\n"
        "  - Windows: Download and run the installer\n"
        "  - macOS: Download the .dmg or use: brew install --cask cap\n"
        "  - Linux: Download the AppImage from GitHub releases\n\n"
        "Source code: https://github.com/CapSoftware/cap\n\n"
        "Cap provides webcam overlay, cursor highlighting, and a polished\n"
        "recording UI that FFmpeg-based recording cannot match."
    )

    capabilities = [
        "detect_cap",
        "check_status",
        "find_recordings",
        "setup_guidance",
    ]

    best_for = [
        "Professional screen recordings with webcam overlay",
        "Cursor highlight and click effect recordings",
        "Recording with a visual UI (not CLI-driven)",
        "Recordings that need polished audio capture",
    ]

    not_good_for = [
        "Automated/headless screen recording",
        "Recording without user interaction",
        "Quick recordings where setup time matters",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["detect", "status", "find_recordings", "setup_guide", "pick_latest"],
                "description": (
                    "'detect' — check if Cap is installed, "
                    "'status' — check if Cap is running, "
                    "'find_recordings' — list recent recordings, "
                    "'setup_guide' — get install instructions, "
                    "'pick_latest' — get the most recent recording file"
                ),
            },
            "output_dir": {
                "type": "string",
                "description": "For pick_latest: copy the recording here",
            },
            "since_minutes": {
                "type": "integer",
                "default": 5,
                "description": "For find_recordings: look back this many minutes",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "installed": {"type": "boolean"},
            "running": {"type": "boolean"},
            "binary_path": {"type": ["string", "null"]},
            "recordings_dir": {"type": ["string", "null"]},
            "recordings": {"type": "array"},
            "setup_instructions": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=64, vram_mb=0, disk_mb=0, network_required=False,
    )

    side_effects = []
    fallback_tools = ["screen_recorder"]

    def get_status(self):
        """Cap tool is always 'available' — it gracefully handles missing Cap."""
        from tools.base_tool import ToolStatus
        return ToolStatus.AVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs["operation"]

        if operation == "detect":
            return self._detect()
        elif operation == "status":
            return self._status()
        elif operation == "find_recordings":
            since = inputs.get("since_minutes", 5)
            return self._find_recordings(since)
        elif operation == "setup_guide":
            return self._setup_guide()
        elif operation == "pick_latest":
            output_dir = inputs.get("output_dir")
            return self._pick_latest(output_dir)
        else:
            return ToolResult(
                success=False,
                error=f"Unknown operation: {operation}. "
                      f"Valid: detect, status, find_recordings, setup_guide, pick_latest",
            )

    def _detect(self) -> ToolResult:
        binary = _find_cap_binary()
        recordings_dir = _find_cap_recordings_dir()
        running = _is_cap_running() if binary else False

        return ToolResult(
            success=True,
            data={
                "installed": binary is not None,
                "running": running,
                "binary_path": binary,
                "recordings_dir": str(recordings_dir) if recordings_dir else None,
                "platform": platform.system(),
            },
        )

    def _status(self) -> ToolResult:
        binary = _find_cap_binary()
        if not binary:
            return ToolResult(
                success=True,
                data={
                    "installed": False,
                    "running": False,
                    "message": "Cap is not installed. Use operation='setup_guide' for install instructions.",
                },
            )

        running = _is_cap_running()
        recordings_dir = _find_cap_recordings_dir()

        return ToolResult(
            success=True,
            data={
                "installed": True,
                "running": running,
                "binary_path": binary,
                "recordings_dir": str(recordings_dir) if recordings_dir else None,
                "message": "Cap is running and ready to record." if running
                          else "Cap is installed but not running. The user should open Cap to start recording.",
            },
        )

    def _find_recordings(self, since_minutes: int) -> ToolResult:
        recordings_dir = _find_cap_recordings_dir()
        if not recordings_dir:
            return ToolResult(
                success=True,
                data={
                    "recordings": [],
                    "message": "Cap recordings directory not found. Cap may not be installed or hasn't made any recordings yet.",
                },
            )

        recordings = _get_recent_recordings(recordings_dir, since_seconds=since_minutes * 60)

        return ToolResult(
            success=True,
            data={
                "recordings": recordings,
                "recordings_dir": str(recordings_dir),
                "count": len(recordings),
                "message": f"Found {len(recordings)} recording(s) from the last {since_minutes} minutes."
                          if recordings else f"No recordings found in the last {since_minutes} minutes.",
            },
        )

    def _setup_guide(self) -> ToolResult:
        sys_platform = platform.system()
        binary = _find_cap_binary()

        if binary:
            return ToolResult(
                success=True,
                data={
                    "installed": True,
                    "binary_path": binary,
                    "message": "Cap is already installed!",
                    "next_step": "Open Cap and start recording. When done, use operation='pick_latest' to grab the recording.",
                },
            )

        instructions = {
            "Windows": {
                "recommended": "Download from https://cap.so/download",
                "alternative": "winget install CapSoftware.Cap",
                "time_estimate": "2 minutes",
            },
            "Darwin": {
                "recommended": "brew install --cask cap",
                "alternative": "Download .dmg from https://cap.so/download",
                "time_estimate": "2 minutes",
            },
            "Linux": {
                "recommended": "Download AppImage from https://github.com/CapSoftware/cap/releases",
                "alternative": "Build from source: https://github.com/CapSoftware/cap",
                "time_estimate": "3-5 minutes",
            },
        }

        platform_guide = instructions.get(sys_platform, instructions["Linux"])

        return ToolResult(
            success=True,
            data={
                "installed": False,
                "platform": sys_platform,
                "setup": platform_guide,
                "what_you_get": [
                    "Webcam overlay (picture-in-picture)",
                    "Cursor highlight and click effects",
                    "Clean system + microphone audio capture",
                    "Built-in editor with auto-captions",
                    "Polished recording UI",
                ],
                "source_code": "https://github.com/CapSoftware/cap",
                "message": f"Cap is not installed. Setup takes about {platform_guide['time_estimate']}.",
            },
        )

    def _pick_latest(self, output_dir: str | None) -> ToolResult:
        recordings_dir = _find_cap_recordings_dir()
        if not recordings_dir:
            return ToolResult(
                success=False,
                error="Cap recordings directory not found.",
            )

        recordings = _get_recent_recordings(recordings_dir, since_seconds=3600)
        if not recordings:
            return ToolResult(
                success=False,
                error="No recent Cap recordings found. Record something in Cap first.",
            )

        latest = recordings[0]
        source = Path(latest["path"])

        if output_dir:
            dest = Path(output_dir) / source.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
            return ToolResult(
                success=True,
                data={
                    "output_path": str(dest),
                    "original_path": str(source),
                    "size_mb": latest["size_mb"],
                    "capture_method": "cap",
                },
                artifacts=[str(dest)],
            )

        return ToolResult(
            success=True,
            data={
                "output_path": str(source),
                "size_mb": latest["size_mb"],
                "capture_method": "cap",
            },
            artifacts=[str(source)],
        )
