"""Dreamina (即梦) AIGC CLI video generation tool.

Provides flagship Seedance 2.0 video generation, text-to-video, image-to-video,
first-last-frames interpolation, and multimodal all-around reference video generation
using the official `dreamina` command-line interface.

Zero-cost painless execution:
- If `dreamina` CLI is not installed on PATH, this tool silently remains ToolStatus.UNAVAILABLE
  without throwing errors or blocking registry discovery.
- If `dreamina` CLI is installed and logged in (verified via `dreamina user_credit`), it activates as
  a video generation provider for OpenMontage pipelines.
"""

from __future__ import annotations

import json
import os
import re
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
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


class DreaminaCliVideo(BaseTool):
    name = "dreamina_cli_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "dreamina_cli"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cli:dreamina"]
    install_instructions = (
        "Install the official Dreamina (即梦) CLI binary on your system PATH or ~/bin/dreamina.exe,\n"
        "then run 'dreamina login' to complete login before generating videos."
    )
    agent_skills = ["ai-video-gen"]

    capabilities = [
        "text_to_video",
        "image_to_video",
        "first_last_frame",
        "multimodal_reference",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_last_frame": True,
        "multimodal_reference": True,
        "seedance_2_0": True,
        "native_audio": False,
    }
    best_for = [
        "Flagship Seedance 2.0 video generation via local Dreamina CLI",
        "Multimodal reference generation ('全能参考' mode with up to 9 images and 3 videos)",
        "First-last-frame smooth interpolation video generation (frames2video)",
        "Zero API key cost using local Dreamina account credits",
    ]
    not_good_for = ["headless servers without local dreamina CLI installation"]
    fallback_tools = ["jimeng_video", "kling_video", "veo_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "maxLength": 1000,
                "description": "Video description or motion prompt.",
            },
            "operation": {
                "type": "string",
                "enum": [
                    "text_to_video",
                    "image_to_video",
                    "frames_to_video",
                    "multimodal_to_video",
                ],
                "default": "text_to_video",
                "description": "Generation mode: text_to_video, image_to_video, frames_to_video, or multimodal_to_video.",
            },
            "image_url": {
                "type": "string",
                "description": "First frame image path or URL for image_to_video / multimodal.",
            },
            "last_image_url": {
                "type": "string",
                "description": "Last frame image path for frames_to_video mode.",
            },
            "images": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of reference image paths for multimodal_to_video (max 9).",
            },
            "videos": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of reference video paths for multimodal_to_video (max 3).",
            },
            "audios": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of reference audio paths for multimodal_to_video (max 3).",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
                "default": "16:9",
            },
            "duration": {
                "type": "integer",
                "minimum": 3,
                "maximum": 15,
                "default": 5,
                "description": "Video duration in seconds (4-15s for Seedance 2.0).",
            },
            "model_version": {
                "type": "string",
                "enum": [
                    "seedance2.0fast",
                    "seedance2.0",
                    "seedance2.0mini",
                    "seedance2.0_vip",
                    "seedance2.0fast_vip",
                    "3.5pro",
                    "3.0",
                ],
                "default": "seedance2.0fast",
                "description": "Dreamina model version (seedance2.0fast is recommended for balance of speed and cost).",
            },
            "video_resolution": {
                "type": "string",
                "enum": ["720p", "1080p"],
                "default": "720p",
                "description": "Output video resolution.",
            },
            "output_path": {"type": "string"},
            "poll_seconds": {
                "type": "integer",
                "default": 600,
                "description": "Maximum seconds to wait for CLI task completion polling.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=3.0,
        retryable_errors=["timeout", "busy"],
    )
    idempotency_key_fields = [
        "prompt",
        "operation",
        "aspect_ratio",
        "duration",
        "model_version",
    ]
    side_effects = [
        "invokes local dreamina CLI process",
        "consumes Dreamina user account credits",
        "writes video file to output_path",
    ]
    user_visible_verification = [
        "Check CLI output logs for task submit_id and credit consumption",
        "Watch generated clip for Seedance 2.0 motion quality",
    ]

    def _resolve_cli_path(self) -> str | None:
        """Find the dreamina CLI executable safely without throwing exceptions."""
        resolved = shutil.which("dreamina") or shutil.which("dreamina.exe")
        if resolved:
            return resolved
        user_bin_win = Path.home() / "bin" / "dreamina.exe"
        if user_bin_win.is_file():
            return str(user_bin_win)
        user_bin_posix = Path.home() / "bin" / "dreamina"
        if user_bin_posix.is_file():
            return str(user_bin_posix)
        return None

    def get_status(self) -> ToolStatus:
        """Painless status detection.

        1. If dreamina CLI is not installed, return ToolStatus.UNAVAILABLE quietly.
        2. If installed, run 'dreamina user_credit' with a short timeout to check login.
        """
        cli_path = self._resolve_cli_path()
        if not cli_path:
            return ToolStatus.UNAVAILABLE

        try:
            res = subprocess.run(
                [cli_path, "user_credit"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if res.returncode == 0:
                return ToolStatus.AVAILABLE
        except Exception:
            pass

        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        """Local CLI uses account credits, zero API dollar cost."""
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        return 60.0 + int(inputs.get("duration", 5)) * 4.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        cli_path = self._resolve_cli_path()
        if not cli_path:
            return ToolResult(
                success=False,
                error="dreamina CLI executable not found on PATH. " + self.install_instructions,
            )

        operation = inputs.get("operation", "text_to_video")
        prompt = inputs.get("prompt", "")
        duration = int(inputs.get("duration", 5))
        ratio = inputs.get("aspect_ratio", "16:9")
        model_version = inputs.get("model_version", "seedance2.0fast")
        video_resolution = inputs.get("video_resolution", "720p")
        poll_sec = int(inputs.get("poll_seconds", 600))

        output_path = Path(inputs.get("output_path", "dreamina_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        download_dir = output_path.parent / "dreamina_dl"
        download_dir.mkdir(parents=True, exist_ok=True)

        print(f"🎬 [OpenMontage] Using Provider: Dreamina CLI ({model_version}) for '{operation}'...")

        # Build subcommand and arguments
        cmd: list[str] = [cli_path]

        if operation == "text_to_video":
            cmd.extend([
                "text2video",
                f"--prompt={prompt}",
                f"--ratio={ratio}",
                f"--duration={duration}",
                f"--model_version={model_version}",
                f"--poll=5",
            ])
            if "vip" in model_version:
                cmd.append(f"--video_resolution={video_resolution}")

        elif operation == "image_to_video":
            image_src = inputs.get("image_url") or inputs.get("image")
            if not image_src:
                return ToolResult(success=False, error="image_to_video requires image_url or image input.")
            cmd.extend([
                "image2video",
                f"--image={image_src}",
                f"--prompt={prompt}",
                f"--duration={duration}",
                f"--model_version={model_version}",
                f"--poll=5",
            ])
            if "vip" in model_version:
                cmd.append(f"--video_resolution={video_resolution}")

        elif operation in ("frames_to_video", "frames2video"):
            first_frame = inputs.get("image_url") or inputs.get("first")
            last_frame = inputs.get("last_image_url") or inputs.get("last")
            if not first_frame or not last_frame:
                return ToolResult(
                    success=False,
                    error="frames_to_video requires both first and last image frames.",
                )
            cmd.extend([
                "frames2video",
                f"--first={first_frame}",
                f"--last={last_frame}",
                f"--prompt={prompt}",
                f"--duration={duration}",
                f"--model_version={model_version}",
                f"--poll=5",
            ])
            if "vip" in model_version:
                cmd.append(f"--video_resolution={video_resolution}")

        elif operation in ("multimodal_to_video", "multimodal2video"):
            cmd.extend([
                "multimodal2video",
                f"--prompt={prompt}",
                f"--ratio={ratio}",
                f"--duration={duration}",
                f"--model_version={model_version}",
                f"--poll=5",
            ])
            if "vip" in model_version:
                cmd.append(f"--video_resolution={video_resolution}")

            images = inputs.get("images", [])
            if not images and (inputs.get("image_url") or inputs.get("image")):
                images = [inputs.get("image_url") or inputs.get("image")]
            for img in images[:9]:
                cmd.extend(["--image", str(img)])
            for vid in inputs.get("videos", [])[:3]:
                cmd.extend(["--video", str(vid)])
            for aud in inputs.get("audios", [])[:3]:
                cmd.extend(["--audio", str(aud)])
        else:
            return ToolResult(success=False, error=f"Unsupported operation '{operation}' for DreaminaCliVideo.")

        start_time = time.time()
        try:
            # 1. Submit task asynchronously
            proc = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
            )
            combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")

            if proc.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"Dreamina CLI task submission failed: {combined_output.strip()}",
                )

            # 2. Extract submit_id from stdout/stderr JSON or text
            submit_id = None
            submit_id_match = re.search(r'(?:submit_id|task_id)[=:\s"]+([a-f0-9\-]+)', combined_output, re.IGNORECASE)
            if submit_id_match:
                submit_id = submit_id_match.group(1)

            if not submit_id:
                return ToolResult(
                    success=False,
                    error=f"Dreamina CLI submit succeeded but submit_id could not be parsed: {combined_output}",
                )

            print(f"✅ [OpenMontage] Dreamina task submitted successfully! Submit ID: {submit_id}")
            print(f"⏳ Polling task status via query_result for up to {poll_sec}s...")

            # 3. Async polling loop using query_result
            deadline = time.time() + poll_sec
            downloaded_file: Path | None = None

            while time.time() < deadline:
                time.sleep(5)
                q_cmd = [
                    cli_path,
                    "query_result",
                    f"--submit_id={submit_id}",
                    f"--download_dir={download_dir}",
                ]
                q_proc = subprocess.run(
                    q_cmd,
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=30,
                )
                q_output = (q_proc.stdout or "") + "\n" + (q_proc.stderr or "")

                # Parse JSON if possible
                try:
                    q_json = json.loads(q_proc.stdout.strip())
                    gen_status = q_json.get("gen_status", "")
                    if gen_status == "fail":
                        fail_msg = q_json.get("fail_reason", "unknown error")
                        return ToolResult(success=False, error=f"Dreamina generation failed: {fail_msg}")
                    if gen_status in ("success", "done"):
                        res_json = q_json.get("result_json") or {}
                        v_list = res_json.get("videos") or []
                        if v_list and "path" in v_list[0] and Path(v_list[0]["path"]).is_file():
                            downloaded_file = Path(v_list[0]["path"])
                            break
                        found_mp4s = list(download_dir.glob("*.mp4"))
                        if found_mp4s:
                            downloaded_file = max(found_mp4s, key=lambda p: p.stat().st_mtime)
                            break
                except Exception:
                    pass

                # Check if download_dir has received a new mp4 file
                found_mp4s = list(download_dir.glob("*.mp4"))
                if found_mp4s:
                    downloaded_file = max(found_mp4s, key=lambda p: p.stat().st_mtime)
                    break

            if downloaded_file and downloaded_file.is_file():
                if downloaded_file.resolve() != output_path.resolve():
                    shutil.copy(str(downloaded_file), str(output_path))
            elif not output_path.is_file():
                return ToolResult(
                    success=False,
                    error=f"Dreamina task {submit_id} timed out or video file not found after {poll_sec}s.",
                )

            from tools.video._shared import probe_output

            probed = probe_output(output_path)
            return ToolResult(
                success=True,
                data={
                    "provider": "dreamina_cli",
                    "model": f"dreamina/{model_version}",
                    "operation": operation,
                    "prompt": prompt,
                    "submit_id": submit_id,
                    "duration": duration,
                    "aspect_ratio": ratio,
                    "output": str(output_path),
                    "output_path": str(output_path),
                    "format": "mp4",
                    **probed,
                },
                artifacts=[str(output_path)],
                cost_usd=0.0,
                duration_seconds=round(time.time() - start_time, 2),
                model=f"dreamina/{model_version}",
            )

        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error=f"Dreamina CLI video generation timed out after {poll_sec}s.",
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"Dreamina CLI video generation failed: {exc}",
            )
