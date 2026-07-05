"""Mathematical animation tool via ManimCE.

Generates animated math/science/explainer videos from Python scene code
using the Manim Community Edition engine. Free, local, no API key required.
"""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

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


# --- Safety: caller-supplied scene_code is a local code-execution boundary ---
# math_animate runs Manim on Python supplied by the caller (often an LLM or
# prompt-influenced reference material). That is arbitrary local code execution
# (see issue #219). The static scan below is defense-in-depth: it blocks the
# constructs an attack needs — reading secrets/SSH material, opening network
# connections, spawning subprocesses — while leaving genuine math/animation
# scenes untouched. It is NOT a security sandbox: a determined attacker can
# evade a static denylist, so it is paired with an explicit `allow_unsafe_code`
# opt-out and a tool contract that names the boundary. A passing scan is not
# proof that code is safe to run.
_BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "socket", "shutil", "requests", "urllib",
    "http", "ftplib", "smtplib", "telnetlib", "ctypes", "pickle", "marshal",
    "importlib", "builtins", "multiprocessing", "threading", "pty", "glob",
    "resource", "signal", "tempfile", "webbrowser", "pathlib",
})
# Dangerous identifiers blocked wherever they appear as a bare name — not just
# as a direct call. This catches indirection like `__builtins__['open']`,
# `f = open`, or `getattr(x, '__class__')` that a call-target-only or
# attribute-only check would miss.
_BLOCKED_NAMES = frozenset({
    "eval", "exec", "compile", "__import__", "open", "input", "breakpoint",
    "__builtins__", "__loader__", "globals", "locals", "vars",
    "getattr", "setattr", "delattr",
})
# Reflection via dunder attributes is the general escape hatch: `().__class__`,
# `print.__self__` (the builtins module), `x.__globals__`, `f.__reduce__`, etc.
# Enumerating dangerous dunders one by one is whack-a-mole, so block ALL dunder
# *attribute access* and allow only a tiny set that legitimate scenes use
# (`super().__init__(...)`, occasional `Type.__name__`). A dunder is any name
# that starts and ends with double underscores.
_ALLOWED_DUNDER_ATTRS = frozenset({"__init__", "__name__"})


def _is_blocked_dunder(attr: str) -> bool:
    return (
        attr.startswith("__")
        and attr.endswith("__")
        and attr not in _ALLOWED_DUNDER_ATTRS
    )


# Quality presets mapping to Manim CLI flags
QUALITY_PRESETS = {
    "low": {"flag": "-ql", "resolution": "854x480", "fps": 15},
    "medium": {"flag": "-qm", "resolution": "1280x720", "fps": 30},
    "high": {"flag": "-qh", "resolution": "1920x1080", "fps": 60},
    "4k": {"flag": "-qk", "resolution": "3840x2160", "fps": 60},
    "preview": {"flag": "-ql --format gif", "resolution": "854x480", "fps": 15},
}


class MathAnimate(BaseTool):
    name = "math_animate"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "graphics"
    provider = "manim"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:manim"]
    install_instructions = (
        "Install ManimCE:\n"
        "  pip install manim\n"
        "  manim checkhealth\n"
        "Requires: Python 3.8+, FFmpeg, LaTeX (optional, for math formulas)\n"
        "  Windows: choco install miktex ffmpeg\n"
        "  macOS: brew install mactex ffmpeg\n"
        "  Linux: sudo apt install texlive-full ffmpeg"
    )
    agent_skills = ["manimce-best-practices", "manim-composer"]

    capabilities = [
        "render_scene",
        "render_from_code",
        "render_from_template",
    ]

    input_schema = {
        "type": "object",
        "required": ["scene_code"],
        "properties": {
            "scene_code": {
                "type": "string",
                "description": (
                    "Python code defining a Manim scene. Must contain a class "
                    "inheriting from Scene with a construct() method. "
                    "Import 'from manim import *' is auto-added if missing. "
                    "SECURITY: this code is EXECUTED on the host by Manim. It is "
                    "scanned for dangerous constructs (system/network/subprocess "
                    "access) and rejected by default; treat scene_code as trusted "
                    "input only."
                ),
            },
            "allow_unsafe_code": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Bypass the scene_code safety scan. Only set this for code "
                    "you fully trust — it permits arbitrary local code execution "
                    "(filesystem, network, subprocess). See issue #219."
                ),
            },
            "scene_name": {
                "type": "string",
                "description": "Name of the Scene class to render. Auto-detected if only one scene.",
            },
            "quality": {
                "type": "string",
                "enum": list(QUALITY_PRESETS.keys()),
                "default": "medium",
                "description": "Render quality preset",
            },
            "format": {
                "type": "string",
                "enum": ["mp4", "gif", "png", "webm"],
                "default": "mp4",
            },
            "output_path": {"type": "string"},
            "transparent": {
                "type": "boolean",
                "default": False,
                "description": "Render with transparent background (PNG sequence or WebM)",
            },
            "background_color": {
                "type": "string",
                "description": "Background hex color (e.g., '#1a1a2e'). Default: Manim default (black).",
            },
            "extra_args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional Manim CLI arguments",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["scene_code", "scene_name", "quality"]
    side_effects = [
        "EXECUTES caller-supplied Python (Manim scene_code) on the host — this "
        "is a local code-execution boundary; scene_code is scanned and rejected "
        "by default unless allow_unsafe_code=true (see issue #219)",
        "writes video/image file to output_path",
        "creates temp files",
    ]
    user_visible_verification = [
        "Watch the animation for correctness and visual quality",
        "Verify math formulas render correctly (requires LaTeX)",
    ]

    def get_status(self) -> ToolStatus:
        if shutil.which("manim"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # local, free

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        quality = inputs.get("quality", "medium")
        # Rough estimates based on scene complexity (assuming ~10s scene)
        estimates = {
            "low": 5.0,
            "medium": 15.0,
            "high": 45.0,
            "4k": 120.0,
            "preview": 3.0,
        }
        return estimates.get(quality, 15.0)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not shutil.which("manim"):
            return ToolResult(
                success=False,
                error="Manim not found. " + self.install_instructions,
            )

        start = time.time()

        try:
            result = self._render(inputs)
        except Exception as e:
            return ToolResult(success=False, error=f"Manim render failed: {e}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    @staticmethod
    def _scan_scene_code(code: str) -> list[str]:
        """Static safety scan of caller-supplied Manim scene code (issue #219).

        Returns a de-duplicated list of disallowed constructs (dangerous
        imports, builtins, and sandbox-escape dunders). Empty list means the
        scan found nothing to block — which is NOT a guarantee the code is safe.
        A syntax error is left for Manim to report, so it returns no violations.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in _BLOCKED_IMPORTS:
                        violations.append(f"import '{alias.name}'")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in _BLOCKED_IMPORTS:
                    violations.append(f"from '{node.module}' import ...")
            elif isinstance(node, ast.Name):
                # Blocks direct calls (eval(...)) and indirection alike:
                # `__builtins__['open']`, `f = open`, `getattr(o, '__class__')`.
                if node.id in _BLOCKED_NAMES:
                    violations.append(f"use of '{node.id}'")
            elif isinstance(node, ast.Attribute):
                if _is_blocked_dunder(node.attr):
                    violations.append(f"dunder attribute access '.{node.attr}'")

        seen: set[str] = set()
        deduped: list[str] = []
        for v in violations:
            if v not in seen:
                seen.add(v)
                deduped.append(v)
        return deduped

    def _render(self, inputs: dict[str, Any]) -> ToolResult:
        scene_code = inputs["scene_code"]
        scene_name = inputs.get("scene_name")
        quality = inputs.get("quality", "medium")
        output_format = inputs.get("format", "mp4")
        output_path = inputs.get("output_path")
        transparent = inputs.get("transparent", False)
        bg_color = inputs.get("background_color")
        extra_args = inputs.get("extra_args", [])

        # Ensure import statement
        if "from manim import" not in scene_code:
            scene_code = "from manim import *\n\n" + scene_code

        # Safety gate: scene_code is executed on the host by Manim. Reject
        # dangerous constructs unless the caller explicitly opts out. (issue #219)
        if not inputs.get("allow_unsafe_code", False):
            violations = self._scan_scene_code(scene_code)
            if violations:
                return ToolResult(
                    success=False,
                    error=(
                        "scene_code blocked by the math_animate safety scan. This "
                        "tool executes caller-supplied Python on the host; the "
                        "following constructs are disallowed by default:\n  - "
                        + "\n  - ".join(violations)
                        + "\nIf you fully trust this code and require them, pass "
                        "allow_unsafe_code=true. See issue #219."
                    ),
                )

        # Auto-detect scene name if not provided
        if not scene_name:
            scene_name = self._detect_scene_name(scene_code)
            if not scene_name:
                return ToolResult(
                    success=False,
                    error="Could not detect Scene class name. Provide scene_name explicitly.",
                )

        # Write scene code to temp file
        work_dir = Path(tempfile.mkdtemp(prefix="manim_"))
        scene_file = work_dir / "scene.py"
        scene_file.write_text(scene_code, encoding="utf-8")

        # Build Manim CLI command
        cmd = ["manim"]

        # Quality flag
        preset = QUALITY_PRESETS.get(quality, QUALITY_PRESETS["medium"])
        for flag_part in preset["flag"].split():
            cmd.append(flag_part)

        # Format
        if output_format == "gif":
            cmd.append("--format")
            cmd.append("gif")
        elif output_format == "webm":
            cmd.append("--format")
            cmd.append("webm")
        elif output_format == "png":
            cmd.append("-s")  # save last frame as PNG

        # Transparent background
        if transparent:
            cmd.append("--transparent")

        # Background color
        if bg_color:
            cmd.extend(["--background_color", bg_color])

        # Disable window preview (headless rendering)
        cmd.append("--disable_caching")

        # Extra args
        cmd.extend(extra_args)

        # Scene file and class name
        cmd.append(str(scene_file))
        cmd.append(scene_name)

        # Execute Manim
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
                cwd=str(work_dir),
            )
        except subprocess.TimeoutExpired:
            self._cleanup(work_dir)
            return ToolResult(
                success=False,
                error=f"Manim render timed out after 300s. Try 'low' or 'preview' quality.",
            )

        if proc.returncode != 0:
            error_msg = proc.stderr or proc.stdout or "Unknown error"
            # Extract the most useful part of the error
            lines = error_msg.strip().split("\n")
            # Look for the actual error (skip Manim header/progress)
            error_lines = [l for l in lines if "Error" in l or "error" in l or "Traceback" in l]
            if error_lines:
                error_msg = "\n".join(lines[lines.index(error_lines[0]):])
            self._cleanup(work_dir)
            return ToolResult(
                success=False,
                error=f"Manim render failed:\n{error_msg}",
                data={"full_stderr": proc.stderr, "full_stdout": proc.stdout},
            )

        # Find the output file
        rendered_file = self._find_output(work_dir, scene_name, output_format)
        if not rendered_file:
            self._cleanup(work_dir)
            return ToolResult(
                success=False,
                error=f"Render succeeded but output file not found. Manim output:\n{proc.stdout}",
            )

        # Move to desired output path
        if output_path:
            final_path = Path(output_path)
        else:
            ext = rendered_file.suffix
            final_path = Path(f"manim_{scene_name}{ext}")

        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(rendered_file), str(final_path))

        # Get video info
        video_info = self._probe_output(final_path)

        # Cleanup temp directory
        self._cleanup(work_dir)

        return ToolResult(
            success=True,
            data={
                "scene_name": scene_name,
                "quality": quality,
                "format": output_format,
                "output": str(final_path),
                "resolution": preset["resolution"],
                "fps": preset["fps"],
                **video_info,
            },
            artifacts=[str(final_path)],
        )

    def _detect_scene_name(self, code: str) -> Optional[str]:
        """Extract Scene subclass name from code."""
        import re

        # Match class definitions that inherit from Scene or its variants
        pattern = r"class\s+(\w+)\s*\(\s*(?:Scene|ThreeDScene|MovingCameraScene|ZoomedScene)\s*\)"
        matches = re.findall(pattern, code)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            # Return the last one (convention: main scene is last)
            return matches[-1]
        return None

    def _find_output(self, work_dir: Path, scene_name: str, fmt: str) -> Optional[Path]:
        """Find Manim's output file in the media directory."""
        media_dir = work_dir / "media"
        if not media_dir.exists():
            return None

        # Manim outputs to media/videos/<scene_file>/<quality>/<SceneName>.<ext>
        # or media/images/<scene_file>/<SceneName>.<ext> for -s flag
        ext_map = {"mp4": ".mp4", "gif": ".gif", "webm": ".webm", "png": ".png"}
        target_ext = ext_map.get(fmt, ".mp4")

        # Search recursively for the output file
        for path in media_dir.rglob(f"{scene_name}{target_ext}"):
            return path

        # Fallback: any file with the right extension
        for path in media_dir.rglob(f"*{target_ext}"):
            return path

        return None

    def _probe_output(self, path: Path) -> dict[str, Any]:
        """Get basic info about the rendered file."""
        info: dict[str, Any] = {"file_size_bytes": path.stat().st_size}

        if not shutil.which("ffprobe"):
            return info

        try:
            proc = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format", "-show_streams",
                    str(path),
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if proc.returncode == 0:
                import json
                probe = json.loads(proc.stdout)
                fmt = probe.get("format", {})
                info["duration_seconds"] = float(fmt.get("duration", 0))
                info["file_size_mb"] = round(path.stat().st_size / (1024 * 1024), 2)
                for stream in probe.get("streams", []):
                    if stream.get("codec_type") == "video":
                        info["video_width"] = int(stream.get("width", 0))
                        info["video_height"] = int(stream.get("height", 0))
                        info["video_codec"] = stream.get("codec_name", "")
                        break
        except Exception:
            pass

        return info

    def _cleanup(self, work_dir: Path) -> None:
        """Remove temp working directory."""
        try:
            shutil.rmtree(str(work_dir), ignore_errors=True)
        except Exception:
            pass
