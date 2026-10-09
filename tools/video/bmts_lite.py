"""OpenMontage adapter for the standalone BMTS-Lite rendering engine."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    DependencyError,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ResumeSupport,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolTier,
)


_ROOT_ENV = "BGM_MONTAGE_LITE_ROOT"
_PYTHON_ENV = "BGM_MONTAGE_LITE_PYTHON"
_RUNTIME_MODULES = ("librosa", "numpy", "cv2", "scipy", "soundfile")
_RATIOS = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "4:3": (1440, 1080),
    "3:4": (1080, 1440),
    "1:1": (1080, 1080),
    "4:5": (1080, 1350),
}
_RUNNER = Path(__file__).with_name("bmts_lite_runner.py")


def _fraction(value: Any) -> float | None:
    try:
        numerator, denominator = str(value).split("/", 1)
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return None


class BgmMontageLite(BaseTool):
    name = "bgm_montage_lite"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "bmts-lite"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Clone https://github.com/sharbvane/BMTS-Lite, create an isolated Python 3.11 "
        "environment, and install its requirements-runtime.txt. Set BGM_MONTAGE_LITE_ROOT "
        "to that checkout and optionally BGM_MONTAGE_LITE_PYTHON to the environment's "
        "interpreter. Install FFmpeg and ffprobe on PATH. See docs/bgm-montage-lite.md."
    )

    capabilities = [
        "audio_led_montage",
        "beat_synced_cuts",
        "whole_track_coverage",
        "automatic_aspect_ratio",
        "source_reuse",
        "full_decode_check",
    ]
    supports = {
        "reference_video_required": False,
        "api_key_required": False,
        "whole_audio_track": True,
        "source_reuse": True,
        "automatic_aspect_ratio": True,
        "semantic_asset_selection": False,
        "agent_visual_review": False,
    }
    best_for = [
        "Fast beat-led montage from one music track and supplied video clips",
        "Reference-free local rendering with automatic framing and source reuse",
    ]
    not_good_for = [
        "Reference-style matching, semantic clip selection, strict source-diversity gates, or a narrated composition",
    ]
    agent_skills = ["ffmpeg", "video-toolkit"]

    input_schema = {
        "type": "object",
        "required": ["audio_path", "video_paths"],
        "properties": {
            "audio_path": {"type": "string", "minLength": 1},
            "video_paths": {
                "type": "array",
                "items": {"type": "string", "minLength": 1},
                "minItems": 1,
                "maxItems": 100,
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["auto", "16:9", "9:16", "4:3", "3:4", "1:1", "4:5"],
                "default": "auto",
            },
            "project_dir": {
                "type": "string",
                "description": "Optional OpenMontage project root; defaults output to its renders folder.",
            },
            "output_path": {
                "type": "string",
                "description": "Optional MP4 destination; defaults beside the music file or under project_dir/renders.",
            },
        },
    }
    output_schema = {
        "type": "object",
        "required": [
            "output_path",
            "timeline_path",
            "audiomap_path",
            "duration_seconds",
            "aspect_ratio",
            "shot_count",
            "render_report",
        ],
        "properties": {
            "output_path": {"type": "string"},
            "timeline_path": {"type": "string"},
            "audiomap_path": {"type": "string"},
            "duration_seconds": {"type": "number", "minimum": 1},
            "aspect_ratio": {"type": "string"},
            "shot_count": {"type": "integer", "minimum": 1},
            "render_report": {"type": "object"},
        },
    }
    artifact_schema = {"type": "array", "items": {"type": "string"}}

    resource_profile = ResourceProfile(
        cpu_cores=4,
        ram_mb=4096,
        vram_mb=0,
        disk_mb=8192,
        network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=0)
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["audio_path", "video_paths", "output_path", "aspect_ratio"]
    side_effects = ["writes an MP4, timeline JSON, and audiomap JSON"]
    user_visible_verification = [
        "BMTS-Lite checks the output streams, dimensions, duration, and full FFmpeg decode; play the MP4 to review its creative result.",
    ]

    def _python_executable(self) -> str:
        requested = os.environ.get(_PYTHON_ENV, "").strip() or sys.executable
        path = Path(requested).expanduser()
        if path.is_file():
            return str(path.resolve())
        found = shutil.which(requested)
        if found:
            return found
        raise DependencyError(f"Python interpreter not found: {requested}")

    def _engine_root(self) -> Path:
        configured = os.environ.get(_ROOT_ENV, "").strip()
        if not configured:
            raise DependencyError(f"Set {_ROOT_ENV} to a BMTS-Lite source checkout.")
        root = Path(configured).expanduser().resolve()
        required = [
            root / "worker.py",
            root / "engine" / "analyze_bgm.py",
            root / "engine" / "timeline_planner.py",
            root / "engine" / "montage.py",
            root / "engine" / "visual_intelligence.py",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise DependencyError(
                f"{_ROOT_ENV} is not a complete BMTS-Lite checkout; missing: {', '.join(missing)}"
            )
        return root

    def check_dependencies(self) -> None:
        super().check_dependencies()
        root = self._engine_root()
        python = self._python_executable()
        code = (
            "import importlib.util, json, sys; "
            f"modules={_RUNTIME_MODULES!r}; "
            "missing=[name for name in modules if importlib.util.find_spec(name) is None]; "
            "print(json.dumps(missing)); sys.exit(bool(missing))"
        )
        try:
            result = subprocess.run(
                [python, "-c", code], capture_output=True, text=True, timeout=30, check=False
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DependencyError(f"Could not check the BMTS-Lite Python environment: {exc}") from exc
        if result.returncode:
            try:
                missing = json.loads(result.stdout)
            except (json.JSONDecodeError, TypeError):
                missing = list(_RUNTIME_MODULES)
            raise DependencyError(
                f"BMTS-Lite Python dependencies are missing: {', '.join(missing)}. "
                "Install requirements-runtime.txt in the configured environment."
            )
        if not _RUNNER.is_file():
            raise DependencyError(f"BMTS-Lite runner is missing: {_RUNNER}")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            audio = Path(inputs["audio_path"]).expanduser().resolve(strict=True)
            videos = [Path(path).expanduser().resolve(strict=True) for path in inputs["video_paths"]]
            if not audio.is_file() or not videos or any(not path.is_file() for path in videos):
                raise ValueError("Provide one existing music file and at least one existing video file.")
            if len(videos) > 100:
                raise ValueError("BMTS-Lite accepts at most 100 source videos per run.")
            total_bytes = sum(path.stat().st_size for path in [audio, *videos])
            if total_bytes > 4 * 1024**3:
                raise ValueError("BMTS-Lite inputs exceed its 4 GiB total upload limit.")

            ratio = str(inputs.get("aspect_ratio", "auto")).strip().lower()
            if ratio != "auto" and ratio not in _RATIOS:
                raise ValueError(f"Unsupported aspect_ratio {ratio!r}; choose auto or a supported ratio.")

            if inputs.get("output_path"):
                output = Path(inputs["output_path"]).expanduser().resolve()
            elif inputs.get("project_dir"):
                output = Path(inputs["project_dir"]).expanduser().resolve() / "renders" / "bgm-montage-lite.mp4"
            else:
                output = audio.with_name(f"{audio.stem}_montage.mp4")
            if output.suffix.lower() != ".mp4":
                raise ValueError("output_path must use the .mp4 extension.")

            timeline_path = output.with_suffix(".timeline.json")
            audiomap_path = output.with_suffix(".audiomap.json")
            destinations = [output, timeline_path, audiomap_path]
            source_paths = {audio, *videos}
            if any(path in source_paths for path in destinations):
                raise ValueError("Output artifacts must not overwrite the supplied audio or video files.")
            existing = [str(path) for path in destinations if path.exists()]
            if existing:
                raise FileExistsError(
                    "Output already exists; choose a new output_path: " + ", ".join(existing)
                )

            self.check_dependencies()
            root = self._engine_root()
            python = self._python_executable()
            output.parent.mkdir(parents=True, exist_ok=True)

            with tempfile.TemporaryDirectory(prefix=".bmts-lite-", dir=output.parent) as temp_name:
                workspace = Path(temp_name)
                request_path = workspace / "request.json"
                request_path.write_text(
                    json.dumps(
                        {
                            "ratio": ratio,
                            "media": [{"file": str(path)} for path in [*videos, audio]],
                        },
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
                process = self.run_command(
                    [
                        python,
                        str(_RUNNER),
                        "--root",
                        str(root),
                        "--workspace",
                        str(workspace),
                        "--request",
                        str(request_path),
                    ],
                    timeout=3600,
                    cwd=workspace,
                )
                summary = json.loads(process.stdout)
                video_file = workspace / "result.mp4"
                timeline_file = workspace / "timeline.json"
                audiomap_file = workspace / "audiomap.json"
                if any(not path.is_file() or path.stat().st_size == 0 for path in (video_file, timeline_file, audiomap_file)):
                    raise RuntimeError("BMTS-Lite returned without producing all expected artifacts.")

                probe = json.loads(
                    self.run_command(
                        [
                            "ffprobe",
                            "-v",
                            "error",
                            "-show_format",
                            "-show_streams",
                            "-of",
                            "json",
                            str(video_file),
                        ],
                        timeout=60,
                    ).stdout
                )
                video_stream = next(
                    (stream for stream in probe.get("streams", []) if stream.get("codec_type") == "video"),
                    None,
                )
                audio_stream = next(
                    (stream for stream in probe.get("streams", []) if stream.get("codec_type") == "audio"),
                    None,
                )
                output_duration = float(probe.get("format", {}).get("duration", 0))
                selected_ratio = str(summary.get("ratio", ""))
                if (
                    video_stream is None
                    or audio_stream is None
                    or selected_ratio not in _RATIOS
                    or (video_stream.get("width"), video_stream.get("height")) != _RATIOS[selected_ratio]
                    or output_duration <= 0
                    or abs(output_duration - float(summary["duration"])) > 0.15
                ):
                    raise RuntimeError("BMTS-Lite output failed OpenMontage's independent ffprobe checks.")

                fps = _fraction(video_stream.get("avg_frame_rate")) or _fraction(
                    video_stream.get("r_frame_rate")
                )
                render_report = {
                    "version": "1.0",
                    "outputs": [
                        {
                            "path": str(output),
                            "format": "mp4",
                            "codec": video_stream.get("codec_name", "h264"),
                            "audio_codec": audio_stream.get("codec_name", "aac"),
                            "resolution": f"{video_stream['width']}x{video_stream['height']}",
                            **({"fps": fps} if fps is not None else {}),
                            "duration_seconds": output_duration,
                            "file_size_bytes": video_file.stat().st_size,
                        }
                    ],
                    "render_time_seconds": round(time.monotonic() - started, 2),
                    "verification_notes": [
                        "BMTS-Lite passed its ffprobe and full FFmpeg decode checks.",
                        "OpenMontage independently confirmed video/audio streams, dimensions, and duration.",
                        "No reference video, API key, semantic asset selection, or agent visual review was used by this tool.",
                    ],
                    "metadata": {
                        "renderer": "BMTS-Lite",
                        "aspect_ratio": selected_ratio,
                        "shot_count": int(summary["shots"]),
                        "timeline_path": str(timeline_path),
                        "audiomap_path": str(audiomap_path),
                    },
                }
                published: list[Path] = []
                try:
                    for source, destination in (
                        (timeline_file, timeline_path),
                        (audiomap_file, audiomap_path),
                        (video_file, output),
                    ):
                        source.rename(destination)
                        published.append(destination)
                except OSError:
                    for path in published:
                        path.unlink(missing_ok=True)
                    raise

            return ToolResult(
                success=True,
                data={
                    "output_path": str(output),
                    "timeline_path": str(timeline_path),
                    "audiomap_path": str(audiomap_path),
                    "duration_seconds": output_duration,
                    "aspect_ratio": selected_ratio,
                    "shot_count": int(summary["shots"]),
                    "render_report": render_report,
                },
                artifacts=[str(output), str(timeline_path), str(audiomap_path)],
                cost_usd=0.0,
                duration_seconds=round(time.monotonic() - started, 2),
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=str(exc),
                cost_usd=0.0,
                duration_seconds=round(time.monotonic() - started, 2),
            )
