"""Publish-stage final package helper for OpenMontage projects."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.analysis.audio_probe import probe_duration
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


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_entry(path: Path, role: str) -> dict[str, Any]:
    return {
        "role": role,
        "path": str(path),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _copy_file(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


class PublishPackager(BaseTool):
    name = "publish_packager"
    version = "0.1.0"
    tier = ToolTier.PUBLISH
    capability = "publishing"
    provider = "openmontage"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:ffprobe"]
    install_instructions = (
        "Install FFmpeg (includes ffprobe). FFmpeg itself is only required when "
        "cover_mode='replace_first_frame'."
    )

    capabilities = [
        "package_final_video",
        "copy_cover_asset",
        "replace_video_first_frame_with_cover",
        "write_final_package_manifest",
        "verify_duration_delta",
    ]
    best_for = [
        "turning an approved render into a publish-ready final package",
        "recording checksums and source paths for final deliverables",
        "making a cover image become the first visible frame without shifting audio",
    ]
    not_good_for = [
        "deciding the creative concept for a cover",
        "publishing to external platforms",
        "replacing project or version tracking",
    ]

    input_schema = {
        "type": "object",
        "required": ["video_path", "output_dir"],
        "properties": {
            "video_path": {"type": "string"},
            "output_dir": {"type": "string"},
            "project_id": {"type": "string"},
            "variant_id": {"type": "string"},
            "channel": {"type": "string"},
            "cover_path": {
                "type": "string",
                "description": "Optional poster/cover image to copy into the package.",
            },
            "cover_source_kind": {
                "type": "string",
                "enum": [
                    "rendered_frame",
                    "generated_image",
                    "generated_video_frame",
                    "source_footage_frame",
                    "manual_design",
                    "unknown",
                ],
                "default": "unknown",
                "description": "Where the cover asset came from; useful for model-generated or manual covers.",
            },
            "cover_generator": {
                "type": "object",
                "description": "Optional cover provenance, such as provider/model/prompt id.",
            },
            "cover_mode": {
                "type": "string",
                "enum": ["none", "replace_first_frame"],
                "default": "none",
                "description": "replace_first_frame swaps only the first video frame and keeps original audio timing.",
            },
            "script_path": {
                "type": "string",
                "description": "Optional script JSON. cover_direction is copied from it when present.",
            },
            "extra_files": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "role"],
                    "properties": {
                        "path": {"type": "string"},
                        "role": {"type": "string"},
                    },
                    "additionalProperties": False,
                },
                "description": "Optional sidecar files, such as subtitles, review notes, or metadata.",
            },
            "duration_tolerance_seconds": {
                "type": "number",
                "default": 0.15,
                "description": "Allowed duration delta after packaging.",
            },
            "overwrite": {"type": "boolean", "default": False},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=512, vram_mb=0, disk_mb=1000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0, retryable_errors=[])
    idempotency_key_fields = [
        "video_path",
        "output_dir",
        "cover_path",
        "cover_mode",
        "variant_id",
    ]
    side_effects = ["writes final package files and manifest JSON"]
    user_visible_verification = [
        "Open the packaged video and confirm the first frame, subtitles, and audio sync.",
        "Review final_package_manifest.json before marking a variant as published.",
    ]

    def get_status(self) -> ToolStatus:
        if shutil.which("ffprobe"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def dry_run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cover_mode = inputs.get("cover_mode", "none")
        return {
            "tool": self.name,
            "estimated_cost_usd": 0.0,
            "estimated_runtime_seconds": self.estimate_runtime(inputs),
            "status": self.get_status().value,
            "would_execute": True,
            "would_write": [
                str(Path(inputs["output_dir"]).expanduser() / "video" / Path(inputs["video_path"]).name),
                str(Path(inputs["output_dir"]).expanduser() / "final_package_manifest.json"),
            ],
            "requires_ffmpeg": cover_mode == "replace_first_frame",
        }

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 30.0 if inputs.get("cover_mode") == "replace_first_frame" else 2.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        try:
            result = self._package(inputs)
        except Exception as exc:
            result = ToolResult(success=False, error=f"{type(exc).__name__}: {exc}")
        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _package(self, inputs: dict[str, Any]) -> ToolResult:
        video_path = Path(inputs["video_path"]).expanduser().resolve()
        output_dir = Path(inputs["output_dir"]).expanduser().resolve()
        cover_path = (
            Path(inputs["cover_path"]).expanduser().resolve()
            if inputs.get("cover_path")
            else None
        )
        cover_direction, cover_policy = self._cover_metadata(inputs.get("script_path"))
        cover_mode = inputs.get("cover_mode") or (
            cover_policy or {}
        ).get("first_frame_mode", "none")
        overwrite = bool(inputs.get("overwrite", False))
        tolerance = float(inputs.get("duration_tolerance_seconds", 0.15))

        if not video_path.exists():
            return ToolResult(success=False, error=f"Video not found: {video_path}")
        if cover_mode == "replace_first_frame" and not cover_path:
            return ToolResult(
                success=False,
                error="cover_path is required when cover_mode='replace_first_frame'",
            )
        if cover_path and not cover_path.exists():
            return ToolResult(success=False, error=f"Cover not found: {cover_path}")
        if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
            return ToolResult(
                success=False,
                error=f"Output directory is not empty: {output_dir}. Pass overwrite=true.",
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        video_out = output_dir / "video" / video_path.name
        cover_out = output_dir / "cover" / cover_path.name if cover_path else None

        source_duration = probe_duration(video_path)
        if cover_mode == "replace_first_frame":
            video_out = video_out.with_name(f"{video_out.stem}-cover-first-frame{video_out.suffix}")
            self._replace_first_frame(video_path, cover_path, video_out)
        else:
            _copy_file(video_path, video_out)

        if cover_path and cover_out:
            _copy_file(cover_path, cover_out)

        files = [_file_entry(video_out, "video")]
        if cover_out:
            files.append(_file_entry(cover_out, "cover"))

        for item in inputs.get("extra_files", []) or []:
            src = Path(item["path"]).expanduser().resolve()
            if not src.exists():
                return ToolResult(success=False, error=f"Extra file not found: {src}")
            dst = output_dir / "sidecars" / src.name
            _copy_file(src, dst)
            files.append(_file_entry(dst, item["role"]))

        package_duration = probe_duration(video_out)
        duration_delta = (
            round(package_duration - source_duration, 3)
            if package_duration is not None and source_duration is not None
            else None
        )
        warnings: list[str] = []
        if duration_delta is not None and abs(duration_delta) > tolerance:
            warnings.append(
                f"Duration delta {duration_delta}s exceeds tolerance {tolerance}s"
            )

        manifest: dict[str, Any] = {
            "version": "1.0",
            "created_at": _now(),
            "package_dir": str(output_dir),
            "video": {
                "source_path": str(video_path),
                "package_path": str(video_out),
                "duration_seconds": package_duration,
                "source_duration_seconds": source_duration,
                "duration_delta_seconds": duration_delta,
                "cover_first_frame": cover_mode == "replace_first_frame",
                "cover_mode": cover_mode,
                "first_frame_verified": None,
            },
            "files": files,
            "verification": {
                "duration_tolerance_seconds": tolerance,
                "passed": not warnings,
                "warnings": warnings,
            },
        }
        for key in ("project_id", "variant_id", "channel"):
            if inputs.get(key):
                manifest[key] = inputs[key]
        if cover_direction:
            manifest["cover_direction"] = cover_direction
        if cover_policy:
            manifest["cover_policy"] = cover_policy
        if cover_out:
            manifest["cover"] = {
                "source_path": str(cover_path),
                "package_path": str(cover_out),
                "role": (
                    "poster_and_first_frame"
                    if cover_mode == "replace_first_frame"
                    else "poster"
                ),
                "source_kind": inputs.get("cover_source_kind", "unknown"),
            }
            if inputs.get("cover_generator"):
                manifest["cover"]["generator"] = inputs["cover_generator"]

        manifest_path = output_dir / "final_package_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        return ToolResult(
            success=not warnings,
            data=manifest,
            artifacts=[str(output_dir), str(manifest_path)],
            error="; ".join(warnings) if warnings else None,
        )

    def _cover_metadata(
        self, script_path: str | None
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        if not script_path:
            return None, None
        path = Path(script_path).expanduser().resolve()
        if not path.exists():
            return None, None
        try:
            script = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None, None
        return script.get("cover_direction"), script.get("cover_policy")

    def _replace_first_frame(self, video_path: Path, cover_path: Path, output_path: Path) -> None:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH")
        width, height, fps = self._video_info(video_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        frame_seconds = 1 / fps
        filter_complex = (
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2,setsar=1,"
            f"trim=duration={frame_seconds},setpts=PTS-STARTPTS[cover];"
            f"[0:v]trim=start={frame_seconds},setpts=PTS-STARTPTS[tail];"
            f"[cover][tail]concat=n=2:v=1:a=0[v]"
        )
        cmd = [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-loop",
            "1",
            "-i",
            str(cover_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            "-shortest",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=600)

    def _video_info(self, video_path: Path) -> tuple[int, int, float]:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            raise RuntimeError("ffprobe not found on PATH")
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-select_streams",
                "v:0",
                "-show_streams",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        data = json.loads(result.stdout)
        stream = data.get("streams", [{}])[0]
        width = int(stream.get("width") or 1920)
        height = int(stream.get("height") or 1080)
        fps_raw = stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "30/1"
        try:
            numerator, denominator = fps_raw.split("/", 1)
            fps = float(numerator) / float(denominator)
        except Exception:
            fps = 30.0
        if fps <= 0:
            fps = 30.0
        return width, height, fps
