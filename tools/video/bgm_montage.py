"""OpenMontage bridge for the independently maintained BGM Montage project.

The bridge keeps BGM Montage's analyzer, planner, asset acquisition, FFmpeg
renderer, and QA implementation in its own repository. OpenMontage contributes
the BaseTool contract, agent-facing schemas, project-scoped paths, and canonical
artifact mapping; it does not copy or reimplement the montage engine.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ResumeSupport,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


BGM_MONTAGE_URL = "https://github.com/sharbvane/bgm-montage"
_OPERATIONS = {"analyze", "plan", "run", "validate"}
_REFERENCE_VIDEO_EXTENSIONS = frozenset(
    {
        ".mp4",
        ".mov",
        ".m4v",
        ".mkv",
        ".webm",
        ".avi",
        ".wmv",
        ".flv",
        ".mts",
        ".m2ts",
        ".ts",
    }
)


def _has_reference_video(directory: Path) -> bool:
    return any(
        path.is_file() and path.suffix.lower() in _REFERENCE_VIDEO_EXTENSIONS
        for path in directory.rglob("*")
    )


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _path(value: Any, label: str) -> Path:
    if not value:
        raise ValueError(f"{label} is required")
    return Path(str(value)).expanduser().resolve()


def _project_output_path(
    project: Path,
    value: Any,
    default: Path,
    label: str,
) -> Path:
    path = _path(value, label) if value else default.resolve()
    if not path.is_relative_to(project.resolve()):
        raise ValueError(f"{label} must be inside project_dir: {project}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _parse_last_json(text: str) -> dict[str, Any]:
    """Extract the final JSON object from progress output plus a JSON summary."""

    decoder = json.JSONDecoder()
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for index in range(len(text) - 1, -1, -1):
        if text[index] != "{":
            continue
        try:
            payload, consumed = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            end = index + consumed
            candidates.append((end, index, payload))
    for _, _, payload in sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True):
        if "status" in payload and "artifacts" in payload:
            return payload
    if candidates:
        end, index, payload = max(candidates, key=lambda item: (item[0], -item[1]))
        return payload
    raise ValueError("BGM Montage did not emit a final JSON summary")


def _redact(text: str) -> str:
    result = text
    for name in (
        "PIXABAY_API_KEY",
        "YOUTUBE_API_KEY",
        "HF_TOKEN",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        secret = os.environ.get(name)
        if secret:
            result = result.replace(secret, "[redacted]")
    return result


def _process_error(process: subprocess.CompletedProcess[str]) -> str:
    text = (process.stderr or process.stdout or "").strip()
    if not text:
        return f"child process exited with code {process.returncode}"
    return _redact("\n".join(text.splitlines()[-12:]))[-2400:]


def _asset_items(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    raw = payload.get("selected_assets") or payload.get("selected") or payload.get("assets") or []
    if isinstance(raw, Mapping):
        raw = list(raw.values())
    return [dict(item) for item in raw if isinstance(item, Mapping)]


def _asset_path(item: Mapping[str, Any]) -> str:
    return str(
        item.get("local_path")
        or item.get("path")
        or item.get("file")
        or item.get("source_path")
        or ""
    )


def _canonical_asset_manifest(
    payload: Mapping[str, Any],
    *,
    bgm_path: str | None,
    source_manifest_path: str | None,
) -> dict[str, Any]:
    assets: list[dict[str, Any]] = []
    path_to_id: dict[str, str] = {}
    provider = str(payload.get("provider") or "bgm-montage")

    for index, raw in enumerate(_asset_items(payload), start=1):
        local_path = _asset_path(raw)
        if not local_path:
            continue
        asset_id = str(raw.get("asset_id") or raw.get("id") or f"bgm_asset_{index:04d}")
        asset_type = str(raw.get("type") or "video").lower()
        if asset_type not in {
            "image", "video", "audio", "narration", "music", "sfx", "diagram",
            "animation", "3d_asset", "3d_world", "code_snippet", "subtitle",
            "font", "lut",
        }:
            asset_type = "video"
        scene_id = str(raw.get("scene_id") or raw.get("slot_id") or f"bgm_slot_{index:04d}")
        item: dict[str, Any] = {
            "id": asset_id,
            "type": asset_type,
            "path": local_path,
            "source_tool": "bgm_montage",
            "scene_id": scene_id,
        }
        optional = {
            "provider": raw.get("provider") or provider,
            "license": raw.get("license") or raw.get("license_name"),
            "original_url": raw.get("original_url") or raw.get("url") or raw.get("source_url"),
            "duration_seconds": raw.get("duration_seconds") or raw.get("duration"),
            "resolution": raw.get("resolution"),
            "format": raw.get("format") or Path(local_path).suffix.lstrip("."),
            "quality_score": raw.get("quality_score") or raw.get("score"),
            "subtype": raw.get("subtype"),
        }
        for key, value in optional.items():
            if value is None or value == "":
                continue
            if key in {"duration_seconds", "quality_score"}:
                value = _number(value)
                if key == "quality_score":
                    value = min(1.0, max(0.0, value))
            item[key] = value
        assets.append(item)
        path_to_id[str(Path(local_path).expanduser().resolve())] = asset_id

    if bgm_path:
        audio_id = "bgm_music"
        item = {
            "id": audio_id,
            "type": "music",
            "path": bgm_path,
            "source_tool": "bgm_montage",
            "scene_id": "music",
            "subtype": "background_music",
            "format": Path(bgm_path).suffix.lstrip("."),
        }
        assets.append(item)
        path_to_id[str(Path(bgm_path).expanduser().resolve())] = audio_id

    return {
        "version": "1.0",
        "assets": assets,
        "metadata": {
            "provider": "bgm-montage",
            "source_project": BGM_MONTAGE_URL,
            "author": "sharbvane",
            "source_manifest": source_manifest_path,
            "path_to_id": path_to_id,
        },
    }


def _canonical_edit_decisions(
    payload: Mapping[str, Any],
    *,
    assets: Mapping[str, Any],
    audiomap_path: str | None,
    timeline_path: str | None,
    bgm_path: str | None,
) -> dict[str, Any]:
    path_to_id = (
        assets.get("metadata", {}).get("path_to_id", {})
        if isinstance(assets.get("metadata"), Mapping)
        else {}
    )
    cuts: list[dict[str, Any]] = []
    shots = payload.get("shots") if isinstance(payload.get("shots"), list) else []
    for index, raw in enumerate(shots, start=1):
        if not isinstance(raw, Mapping):
            continue
        source_path = str(raw.get("source_path") or raw.get("local_path") or raw.get("path") or "")
        source_id = path_to_id.get(
            str(Path(source_path).expanduser().resolve()),
            source_path,
        )
        in_seconds = max(0.0, _number(raw.get("source_start") or raw.get("trim_start")))
        out_seconds = _number(raw.get("source_end") or raw.get("trim_end"))
        duration = _number(raw.get("duration") or raw.get("output_duration"))
        if out_seconds <= in_seconds:
            out_seconds = in_seconds + max(duration, 0.001)
        cut: dict[str, Any] = {
            "id": f"bgm_cut_{index:04d}",
            "source": source_id,
            "in_seconds": round(max(0.0, in_seconds), 6),
            "out_seconds": round(max(in_seconds + 0.001, out_seconds), 6),
            "speed": max(0.1, _number(raw.get("speed"), 1.0)),
            "layer": "primary",
            "reason": str(
                raw.get("reason")
                or raw.get("selection_reason")
                or "Selected by BGM Montage's music-aware timeline"
            ),
        }
        transition = raw.get("transition") or raw.get("transition_in")
        if transition:
            cut["transition_in"] = str(transition)
        transition_out = raw.get("transition_out")
        if transition_out:
            cut["transition_out"] = str(transition_out)
        transition_duration = raw.get("transition_duration")
        if transition_duration is not None:
            cut["transition_duration"] = max(0.0, _number(transition_duration))
        cuts.append(cut)

    result: dict[str, Any] = {
        "version": "1.0",
        "cuts": cuts,
        "render_runtime": "ffmpeg",
        "renderer_family": "documentary-montage",
        "audio": {
            "music": {
                "asset_id": "bgm_music",
                "volume": 1.0,
            }
        },
        "metadata": {
            "provider": "bgm-montage",
            "source_project": BGM_MONTAGE_URL,
            "author": "sharbvane",
            "audiomap": audiomap_path,
            "timeline": timeline_path,
            "source_edit_schema": payload.get("schema_version"),
            "bgm_path": bgm_path,
        },
    }
    return result


def _canonical_render_report(
    validation: Mapping[str, Any],
    *,
    run_report_path: str | None,
    bgm_artifacts: Mapping[str, Any],
    status: str | None,
) -> dict[str, Any] | None:
    path = str(validation.get("path") or bgm_artifacts.get("video") or "")
    video = validation.get("video") if isinstance(validation.get("video"), Mapping) else {}
    audio = validation.get("audio") if isinstance(validation.get("audio"), Mapping) else {}
    width = int(_number(video.get("width")))
    height = int(_number(video.get("height")))
    duration = max(0.0, _number(validation.get("duration_seconds") or video.get("duration_seconds")))
    if not path or duration <= 0:
        return None
    output: dict[str, Any] = {
        "path": path,
        "format": Path(path).suffix.lstrip(".") or "mp4",
        "resolution": f"{width}x{height}" if width and height else "unknown",
        "duration_seconds": duration,
    }
    optional = {
        "codec": video.get("codec"),
        "audio_codec": audio.get("codec"),
        "fps": video.get("frame_rate_fps"),
        "file_size_bytes": validation.get("size_bytes"),
    }
    for key, value in optional.items():
        if value is not None and value != "":
            output[key] = value
    checks = validation.get("checks") if isinstance(validation.get("checks"), Mapping) else {}
    failed_checks = [str(name) for name, passed in checks.items() if not passed]
    qa_passed = bool(validation.get("passed"))
    notes = [
        f"BGM Montage programmatic QA: {'passed' if qa_passed else 'failed'}.",
        "Music analysis, beat-aware planning, rendering, and media QA remain owned by BGM Montage.",
    ]
    if status == "awaiting_agent_visual_review":
        notes.append("Programmatic QA passed; BGM Montage is awaiting agent visual review.")
    report: dict[str, Any] = {
        "version": "1.0",
        "outputs": [output],
        "warnings": failed_checks,
        "verification_notes": notes,
        "render_grammar": "documentary-montage",
        "metadata": {
            "provider": "bgm-montage",
            "source_project": BGM_MONTAGE_URL,
            "author": "sharbvane",
            "license": "AGPL-3.0-or-later",
            "qa_passed": qa_passed,
            "qa_checks": dict(checks),
            "bgm_render_report": bgm_artifacts.get("render_report"),
            "bgm_run_report": run_report_path,
            "status": status,
        },
    }
    return report


class BgmMontage(BaseTool):
    name = "bgm_montage"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "bgm-montage"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.HYBRID

    dependencies = ["cmd:ffmpeg", "cmd:ffprobe"]
    install_instructions = (
        "Clone https://github.com/sharbvane/bgm-montage, install its "
        "requirements.lock.txt in an isolated Python 3.11 environment, and "
        "set BGM_MONTAGE_ROOT. BGM_MONTAGE_PYTHON may point to that environment."
    )
    agent_skills = ["ffmpeg", "video-toolkit"]
    capabilities = [
        "music_analysis",
        "beat_sync",
        "material_matching",
        "timeline_generation",
        "rendering",
        "quality_assurance",
        "full_montage",
    ]
    supports = {
        "operations": sorted(_OPERATIONS),
        "local_library": True,
        "online_sources": True,
        "agent_visual_review": True,
        "jianying_draft_export": True,
        "canonical_artifacts": [
            "asset_manifest",
            "edit_decisions",
            "render_report",
        ],
    }
    best_for = [
        "music-driven documentary or thematic montages",
        "beat-aware editing with auditable source intervals",
        "local-library production without network acquisition",
    ]
    not_good_for = [
        "Remotion or HyperFrames motion-graphics compositions",
        "runs where the BGM Montage checkout and its isolated dependencies are unavailable",
    ]
    resource_profile = ResourceProfile(
        cpu_cores=4,
        ram_mb=4096,
        vram_mb=0,
        disk_mb=5000,
        network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    resume_support = ResumeSupport.FROM_CHECKPOINT
    idempotency_key_fields = [
        "operation",
        "project_dir",
        "bgm",
        "theme",
        "duration_seconds",
        "ratio",
        "run_id",
    ]
    side_effects = [
        "writes project-scoped BGM Montage cache, analysis, timeline, media, render, and QA artifacts",
        "may download source media when an online source provider is selected",
        "when jianying_draft is enabled, writes an editable draft to the configured JianYing workspace",
    ]
    user_visible_verification = [
        "Inspect the BGM Montage render_report and OpenMontage render_report",
        "Inspect validation_frames and the visual_review artifacts when agent review is required",
        "Play the final MP4 and verify beat cuts, framing, and source attribution",
        "When requested, open the JianYing draft and inspect its generated draft report",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation", "project_dir"],
        "properties": {
            "operation": {"type": "string", "enum": sorted(_OPERATIONS)},
            "project_dir": {
                "type": "string",
                "description": "OpenMontage project directory receiving all generated artifacts.",
            },
            "bgm": {"type": "string", "description": "Input music path for analyze/run."},
            "theme": {"type": "string", "description": "Visual theme for run."},
            "duration_seconds": {"type": "number", "exclusiveMinimum": 0},
            "ratio": {"type": "string", "description": "9:16, 16:9, 1:1, 4:5, or WIDTHxHEIGHT."},
            "audiomap_path": {"type": "string"},
            "cache_dir": {
                "type": "string",
                "description": "Optional cache path inside project_dir.",
            },
            "video_path": {"type": "string"},
            "output_path": {"type": "string"},
            "report_path": {"type": "string"},
            "frames_dir": {"type": "string"},
            "edit_plan_path": {"type": "string"},
            "style_profile_path": {"type": "string"},
            "editing_grammar_path": {"type": "string"},
            "reference_dir": {"type": "string"},
            "local_library_dir": {"type": "string"},
            "asset_manifest": {"type": "string"},
            "source_provider": {
                "type": "string",
                "enum": ["youtube-first", "youtube", "pixabay", "local-library"],
                "default": "youtube-first",
            },
            "usage_mode": {
                "type": "string",
                "enum": ["local_evaluation", "publish"],
                "default": "local_evaluation",
            },
            "agent_visual_review": {
                "type": "string",
                "enum": ["required", "off"],
                "default": "required",
            },
            "project_name": {"type": "string"},
            "run_id": {"type": "string"},
            "resume_run": {"type": "boolean"},
            "visual_style": {"type": "string"},
            "priority_queries": {"type": "array", "items": {"type": "string"}},
            "youtube_source_windows": {"type": "array", "items": {"type": "string"}},
            "exclude_youtube_ids": {"type": "array", "items": {"type": "string"}},
            "exclude_pixabay_ids": {"type": "array", "items": {"type": "string"}},
            "allow_semantic_fallback": {"type": "boolean"},
            "wide_aerial_only": {"type": "boolean"},
            "max_rework_attempts": {"type": "integer", "minimum": 0},
            "max_reuse_per_asset": {"type": "integer", "minimum": 1},
            "max_asset_screen_share": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
            "min_repeat_gap_shots": {"type": "integer", "minimum": 0},
            "min_repeat_gap_seconds": {"type": "number", "minimum": 0},
            "assets": {"type": "integer", "minimum": 1},
            "min_width": {"type": "integer", "minimum": 1},
            "min_height": {"type": "integer", "minimum": 1},
            "candidate_pool_multiplier": {"type": "integer", "minimum": 1},
            "max_search_pages": {"type": "integer", "minimum": 1},
            "youtube_results_per_query": {"type": "integer", "minimum": 1},
            "youtube_max_download_candidates": {"type": "integer", "minimum": 1},
            "youtube_max_search_rounds": {"type": "integer", "minimum": 1},
            "expected_fps": {"type": "number", "exclusiveMinimum": 0},
            "jianying_draft": {"type": "boolean"},
            "jianying_draft_name": {"type": "string"},
            "jianying_draft_root": {"type": "string"},
            "jianying_python": {"type": "string"},
        },
    }
    output_schema = {
        "type": "object",
        "properties": {
            "operation": {"type": "string"},
            "status": {"type": "string"},
            "passed": {"type": "boolean"},
            "audiomap": {"type": "object"},
            "timeline": {"type": "object"},
            "asset_manifest": {"type": "object"},
            "edit_decisions": {"type": "object"},
            "render_report": {"type": "object"},
        },
        "additionalProperties": True,
    }

    @staticmethod
    def _root() -> Path | None:
        value = os.environ.get("BGM_MONTAGE_ROOT", "").strip()
        return Path(value).expanduser().resolve() if value else None

    @staticmethod
    def _python() -> str | None:
        value = os.environ.get("BGM_MONTAGE_PYTHON", "").strip()
        if not value:
            return sys.executable
        candidate = Path(value).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
        return shutil.which(value)

    def get_status(self) -> ToolStatus:
        status = super().get_status()
        if status != ToolStatus.AVAILABLE:
            return status
        root = self._root()
        python = self._python()
        required_scripts = ("bgm_montage.py", "analyze_bgm.py", "timeline_planner.py", "validate_output.py")
        if root is None or any(not (root / "scripts" / name).is_file() for name in required_scripts):
            return ToolStatus.UNAVAILABLE
        if python is None or not Path(python).is_file():
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.monotonic()
        try:
            operation = str(inputs.get("operation") or "").lower()
            if operation not in _OPERATIONS:
                return ToolResult(success=False, error=f"Unsupported operation: {operation!r}")
            if operation == "analyze":
                result = self._analyze(inputs)
            elif operation == "plan":
                result = self._plan(inputs)
            elif operation == "validate":
                result = self._validate(inputs)
            else:
                result = self._run(inputs)
        except subprocess.TimeoutExpired as exc:
            result = ToolResult(success=False, error=f"BGM Montage timed out after {exc.timeout}s")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            result = ToolResult(success=False, error=_redact(str(exc)))
        result.duration_seconds = round(time.monotonic() - started, 2)
        return result

    def _context(self, inputs: Mapping[str, Any]) -> tuple[Path, Path, str]:
        root = self._root()
        python = self._python()
        if root is None:
            raise ValueError("BGM_MONTAGE_ROOT is not set")
        if not root.is_dir():
            raise ValueError(f"BGM_MONTAGE_ROOT is not a directory: {root}")
        if python is None:
            raise ValueError("BGM_MONTAGE_PYTHON does not resolve to a Python executable")
        project = _path(inputs.get("project_dir"), "project_dir")
        project.mkdir(parents=True, exist_ok=True)
        return root, project, python

    def _run_script(
        self,
        root: Path,
        python: str,
        script_name: str,
        args: list[str],
        *,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        script = root / "scripts" / script_name
        if not script.is_file():
            raise ValueError(f"BGM Montage script not found: {script}")
        return subprocess.run(
            [python, str(script), *args],
            cwd=str(root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )

    @staticmethod
    def _required_file(inputs: Mapping[str, Any], key: str) -> Path:
        value = _path(inputs.get(key), key)
        if not value.is_file():
            raise ValueError(f"{key} does not exist: {value}")
        return value

    def _analyze(self, inputs: Mapping[str, Any]) -> ToolResult:
        root, project, python = self._context(inputs)
        bgm = self._required_file(inputs, "bgm")
        output = _project_output_path(
            project, inputs.get("output_path"), project / "artifacts" / "audiomap.json", "output_path"
        )
        cache = _project_output_path(
            project, inputs.get("cache_dir"), project / ".bgm-montage-cache" / "bgm", "cache_dir"
        )
        cache.mkdir(parents=True, exist_ok=True)
        args = ["--bgm", str(bgm), "--cache-dir", str(cache), "--output", str(output)]
        if inputs.get("duration_seconds") is not None:
            args.extend(["--target-duration", str(_number(inputs["duration_seconds"]))])
        process = self._run_script(root, python, "analyze_bgm.py", args, timeout=600)
        if process.returncode != 0 or not output.is_file():
            return ToolResult(success=False, error=_process_error(process))
        return ToolResult(
            success=True,
            data={
                "operation": "analyze",
                "audiomap": _read_json(output),
                "artifact_path": str(output),
            },
            artifacts=[str(output)],
        )

    def _plan(self, inputs: Mapping[str, Any]) -> ToolResult:
        root, project, python = self._context(inputs)
        audiomap = self._required_file(inputs, "audiomap_path")
        output = _project_output_path(
            project, inputs.get("output_path"), project / "artifacts" / "timeline.json", "output_path"
        )
        args = ["--audiomap", str(audiomap), "--output", str(output)]
        if inputs.get("duration_seconds") is not None:
            args.extend(["--duration", str(_number(inputs["duration_seconds"]))])
        for key, flag in (
            ("style_profile_path", "--style-profile"),
            ("editing_grammar_path", "--editing-grammar"),
        ):
            if inputs.get(key):
                args.extend([flag, str(_path(inputs[key], key))])
        process = self._run_script(root, python, "timeline_planner.py", args, timeout=180)
        if process.returncode != 0 or not output.is_file():
            return ToolResult(success=False, error=_process_error(process))
        return ToolResult(
            success=True,
            data={
                "operation": "plan",
                "timeline": _read_json(output),
                "artifact_path": str(output),
            },
            artifacts=[str(output)],
        )

    def _validate(self, inputs: Mapping[str, Any]) -> ToolResult:
        root, project, python = self._context(inputs)
        video = self._required_file(inputs, "video_path")
        report_path = _project_output_path(
            project,
            inputs.get("report_path"),
            project / "artifacts" / "bgm_render_report.json",
            "report_path",
        )
        frames_dir = _project_output_path(
            project,
            inputs.get("frames_dir"),
            report_path.parent / "validation_frames",
            "frames_dir",
        )
        frames_dir.mkdir(parents=True, exist_ok=True)
        args = [
            str(video),
            "--report", str(report_path),
            "--frames-dir", str(frames_dir),
        ]
        for key, flag in (
            ("duration_seconds", "--expected-duration"),
            ("ratio", "--ratio"),
            ("edit_plan_path", "--edit-plan"),
            ("audiomap_path", "--audiomap"),
            ("expected_fps", "--expected-fps"),
        ):
            if inputs.get(key) is not None:
                value = _path(inputs[key], key) if key.endswith("_path") else inputs[key]
                args.extend([flag, str(value)])
        process = self._run_script(root, python, "validate_output.py", args, timeout=900)
        if not report_path.is_file():
            return ToolResult(success=False, error=_process_error(process))
        validation = _read_json(report_path)
        canonical = _canonical_render_report(
            validation,
            run_report_path=None,
            bgm_artifacts={"render_report": str(report_path), "video": str(video)},
            status="passed" if validation.get("passed") else "failed_qa",
        )
        artifact_paths = [str(report_path), str(frames_dir)]
        if canonical:
            canonical_path = report_path.with_name("openmontage_render_report.json")
            _write_json(canonical_path, canonical)
            artifact_paths.append(str(canonical_path))
        passed = bool(validation.get("passed")) and process.returncode == 0
        return ToolResult(
            success=passed,
            data={
                "operation": "validate",
                "passed": passed,
                "validation": validation,
                "render_report": canonical,
            },
            artifacts=artifact_paths,
            error=None if passed else "BGM Montage programmatic QA failed",
        )

    def _run(self, inputs: Mapping[str, Any]) -> ToolResult:
        root, project, python = self._context(inputs)
        bgm = self._required_file(inputs, "bgm")
        theme = str(inputs.get("theme") or "").strip()
        if not theme:
            raise ValueError("theme is required for run")
        duration = _number(inputs.get("duration_seconds"))
        if duration <= 0:
            raise ValueError("duration_seconds must be greater than zero")
        ratio = str(inputs.get("ratio") or "").strip()
        if not ratio:
            raise ValueError("ratio is required for run")
        has_explicit_reference_dir = bool(inputs.get("reference_dir"))
        reference = (
            _path(inputs["reference_dir"], "reference_dir")
            if has_explicit_reference_dir
            else project / "references"
        )
        if has_explicit_reference_dir and not reference.is_dir():
            raise ValueError(f"reference_dir does not exist: {reference}")
        if not reference.is_dir() or not _has_reference_video(reference):
            raise ValueError(
                "operation=run requires at least one supported reference video under "
                f"reference_dir (default: {project / 'references'}); this BGM Montage route is reference-dependent"
            )
        output_root = project / "renders" / "bgm-montage"
        material_dir = project / "assets" / "bgm-montage"
        cache_dir = project / ".bgm-montage-cache"
        output_root.mkdir(parents=True, exist_ok=True)
        material_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)

        source_provider = str(inputs.get("source_provider") or "youtube-first")
        usage_mode = str(inputs.get("usage_mode") or "local_evaluation")
        review_mode = str(inputs.get("agent_visual_review") or "required")
        args = [
            "--bgm", str(bgm),
            "--theme", theme,
            "--duration", str(duration),
            "--ratio", ratio,
            "--output-dir", str(output_root),
            "--reference-dir", str(reference),
            "--material-dir", str(material_dir),
            "--cache-dir", str(cache_dir),
            "--source-provider", source_provider,
            "--usage-mode", usage_mode,
            "--agent-visual-review", review_mode,
        ]
        scalar_flags = (
            ("project_name", "--project-name"),
            ("run_id", "--run-id"),
            ("asset_manifest", "--asset-manifest"),
            ("assets", "--assets"),
            ("min_width", "--min-width"),
            ("min_height", "--min-height"),
            ("candidate_pool_multiplier", "--candidate-pool-multiplier"),
            ("max_search_pages", "--max-search-pages"),
            ("youtube_results_per_query", "--youtube-results-per-query"),
            ("youtube_max_download_candidates", "--youtube-max-download-candidates"),
            ("youtube_max_search_rounds", "--youtube-max-search-rounds"),
            ("visual_style", "--visual-style"),
            ("max_reuse_per_asset", "--max-reuse-per-asset"),
            ("max_asset_screen_share", "--max-asset-screen-share"),
            ("min_repeat_gap_shots", "--min-repeat-gap-shots"),
            ("min_repeat_gap_seconds", "--min-repeat-gap-seconds"),
            ("max_rework_attempts", "--max-rework-attempts"),
            ("local_library_dir", "--local-library-dir"),
            ("jianying_draft_name", "--jianying-draft-name"),
            ("jianying_draft_root", "--jianying-draft-root"),
            ("jianying_python", "--jianying-python"),
        )
        for key, flag in scalar_flags:
            if inputs.get(key) is not None:
                args.extend([flag, str(inputs[key])])
        for key, flag in (
            ("priority_queries", "--search-query"),
            ("youtube_source_windows", "--youtube-source-window"),
            ("exclude_youtube_ids", "--exclude-youtube-id"),
            ("exclude_pixabay_ids", "--exclude-pixabay-id"),
        ):
            for value in inputs.get(key, []) or []:
                args.extend([flag, str(value)])
        for key, flag in (
            ("resume_run", "--resume-run"),
            ("wide_aerial_only", "--wide-aerial-only"),
            ("allow_semantic_fallback", "--allow-semantic-fallback"),
            ("jianying_draft", "--jianying-draft"),
        ):
            if inputs.get(key):
                args.append(flag)

        process = self._run_script(root, python, "bgm_montage.py", args, timeout=7200)
        try:
            summary = _parse_last_json(process.stdout)
        except ValueError:
            if process.returncode != 0:
                return ToolResult(success=False, error=_process_error(process))
            return ToolResult(success=False, error="BGM Montage completed without a JSON summary")

        raw_artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), Mapping) else {}
        run_report_path = str(raw_artifacts.get("run_report") or "")
        run_report = _read_json(Path(run_report_path)) if run_report_path and Path(run_report_path).is_file() else {}
        if isinstance(run_report.get("artifacts"), Mapping):
            raw_artifacts = run_report["artifacts"]
        status = str(summary.get("status") or run_report.get("status") or "")
        passed = bool(summary.get("passed") if "passed" in summary else run_report.get("passed"))
        data: dict[str, Any] = {
            "operation": "run",
            "status": status,
            "passed": passed,
            "summary": summary,
            "run_report": run_report,
        }
        artifact_paths = [
            str(value)
            for value in raw_artifacts.values()
            if isinstance(value, str) and value
        ]
        bgm_path = str(bgm)
        canonical_paths = self._write_canonical_artifacts(
            data,
            run_report,
            raw_artifacts,
            status=status,
            bgm_path=bgm_path,
            run_report_path=run_report_path,
        )
        artifact_paths.extend(canonical_paths)
        artifact_paths = list(dict.fromkeys(artifact_paths))
        if process.returncode not in {0, 3}:
            return ToolResult(success=False, data=data, artifacts=artifact_paths, error=_process_error(process))
        if process.returncode == 3:
            data["passed"] = False
            data["status"] = "awaiting_agent_visual_review"
            return ToolResult(success=True, data=data, artifacts=artifact_paths)
        if not passed:
            return ToolResult(success=False, data=data, artifacts=artifact_paths, error="BGM Montage reported a failed run")
        return ToolResult(success=True, data=data, artifacts=artifact_paths)

    @staticmethod
    def _write_canonical_artifacts(
        data: dict[str, Any],
        run_report: Mapping[str, Any],
        raw_artifacts: Mapping[str, Any],
        *,
        status: str,
        bgm_path: str,
        run_report_path: str,
    ) -> list[str]:
        paths: list[str] = []
        asset_manifest_path = str(raw_artifacts.get("asset_manifest") or "")
        asset_manifest: dict[str, Any] | None = None
        if asset_manifest_path and Path(asset_manifest_path).is_file():
            raw_assets = _read_json(Path(asset_manifest_path))
            if isinstance(raw_assets, Mapping):
                asset_manifest = _canonical_asset_manifest(
                    raw_assets,
                    bgm_path=bgm_path,
                    source_manifest_path=asset_manifest_path,
                )
                target = Path(asset_manifest_path).with_name("openmontage_asset_manifest.json")
                _write_json(target, asset_manifest)
                data["asset_manifest"] = asset_manifest
                paths.append(str(target))

        edit_path = str(raw_artifacts.get("edit_decisions") or "")
        if asset_manifest and edit_path and Path(edit_path).is_file():
            raw_edit = _read_json(Path(edit_path))
            if isinstance(raw_edit, Mapping):
                edit = _canonical_edit_decisions(
                    raw_edit,
                    assets=asset_manifest,
                    audiomap_path=str(raw_artifacts.get("audiomap") or ""),
                    timeline_path=str(raw_artifacts.get("timeline") or ""),
                    bgm_path=bgm_path,
                )
                target = Path(edit_path).with_name("openmontage_edit_decisions.json")
                _write_json(target, edit)
                data["edit_decisions"] = edit
                paths.append(str(target))

        render_path = str(raw_artifacts.get("render_report") or "")
        if render_path and Path(render_path).is_file():
            raw_render = _read_json(Path(render_path))
            if isinstance(raw_render, Mapping):
                render = _canonical_render_report(
                    raw_render,
                    run_report_path=run_report_path,
                    bgm_artifacts=raw_artifacts,
                    status=status,
                )
                if render:
                    target = Path(render_path).with_name("openmontage_render_report.json")
                    _write_json(target, render)
                    data["render_report"] = render
                    paths.append(str(target))
        return paths
