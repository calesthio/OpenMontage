"""Higgsfield video generation via the authenticated CLI or Cloud API.

The CLI path is the preferred integration for local OAuth sessions. The direct
Cloud API path remains available for installations that provision an API key
and secret explicitly.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlparse

import requests

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolCommandError,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Keep the public/default label stable for existing OpenMontage callers. The
# CLI uses the current job_type spelling, translated in _CLI_MODEL_ALIASES.
_DEFAULT_MODEL = "seedance_2.0"
_CLI_MODEL_ALIASES = {
    "seedance_2.0": "seedance_2_0",
    "kling_3.0": "kling3_0",
    "veo_3.1": "veo3_1",
}


class HiggsFieldVideo(BaseTool):
    name = "higgsfield_video"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "higgsfield"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.HYBRID

    # Authentication is intentionally alternative: either the authenticated
    # Higgsfield CLI or the explicitly provisioned direct API pair can work.
    dependencies = []
    install_instructions = (
        "Preferred OAuth path: run `higgsfield auth login`, select a workspace if prompted, "
        "and verify with `higgsfield account status`.\n"
        "  The CLI path needs no API key in .env.\n"
        "Direct API fallback: set HIGGSFIELD_API_KEY and HIGGSFIELD_API_SECRET, or "
        "HIGGSFIELD_KEY as a combined key:secret value."
    )
    agent_skills = ["seedance-2-0", "ai-video-gen"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "character_consistency": True,
        "multi_model_routing": True,
        "native_audio": True,
        "cinematic_quality": True,
        "camera_direction": True,
        "lip_sync": True,
        "multi_shot": True,
    }
    best_for = [
        "preferred premium video gen on Higgsfield (Seedance 2.0 is the default model)",
        "cinematic trailers, teasers, and high-fidelity clips with native synchronized audio",
        "character-consistent video generation (Soul ID + Seedance 2.0 identity consistency)",
        "director-level camera control and multi-shot editing in a single generation",
        "lip-sync from quoted dialogue in prompts",
        "multi-model access through the authenticated Higgsfield catalog",
    ]
    not_good_for = ["offline generation", "fine-grained model control", "budget projects without subscription"]
    fallback_tools = ["seedance_video", "seedance_replicate", "kling_video", "veo_video", "minimax_video"]
    quality_score = 0.9

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "default": _DEFAULT_MODEL,
                "description": (
                    "Higgsfield job_type. Defaults to the Seedance 2.0 alias; "
                    "use `higgsfield model list --video` for the current catalog."
                ),
            },
            "duration": {
                "type": "string",
                "enum": ["5", "10", "15"],
                "default": "5",
                "description": "Duration in seconds (availability varies by model)",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["16:9", "9:16", "1:1", "21:9"],
                "default": "16:9",
            },
            "image_url": {
                "type": "string",
                "description": "Reference image URL, local path, or Higgsfield upload ID for image_to_video",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration"]
    side_effects = ["writes video file to output_path", "calls Higgsfield via CLI or Cloud API"]
    user_visible_verification = ["Watch generated clip for motion coherence and visual quality"]

    _CLI_TIMEOUT_SECONDS = 900
    _REFERENCE_IMAGE_MAX_BYTES = 50 * 1024 * 1024
    _CLI_AUTH_CACHE_TTL_SECONDS = 60
    _cli_auth_cache: tuple[float, str, bool] | None = None

    def _get_credentials(self) -> tuple[str, str] | None:
        """Return (api_key, api_secret) or None if direct API auth is absent."""
        combined = os.environ.get("HIGGSFIELD_KEY")
        if combined and ":" in combined:
            key, secret = combined.split(":", 1)
            return key, secret
        key = os.environ.get("HIGGSFIELD_API_KEY")
        secret = os.environ.get("HIGGSFIELD_API_SECRET")
        if key and secret:
            return key, secret
        return None

    @staticmethod
    def _get_cli_path() -> str | None:
        return shutil.which("higgsfield")

    @classmethod
    def _has_authenticated_cli(cls) -> bool:
        """Check the local CLI session without returning account data to callers."""
        cli = cls._get_cli_path()
        if not cli:
            cls._cli_auth_cache = None
            return False

        now = time.time()
        cached = cls._cli_auth_cache
        if (
            cached
            and cached[1] == cli
            and now - cached[0] < cls._CLI_AUTH_CACHE_TTL_SECONDS
        ):
            return cached[2]

        try:
            result = subprocess.run(
                [cli, "account", "status", "--json"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
            )
            authenticated = result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            authenticated = False

        cls._cli_auth_cache = (now, cli, authenticated)
        return authenticated

    def get_status(self) -> ToolStatus:
        if self._get_credentials() or self._has_authenticated_cli():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = str(inputs.get("model", _DEFAULT_MODEL))
        duration = int(inputs.get("duration", "5"))
        # Approximate per-clip costs. Final provider billing remains authoritative.
        base_costs = {
            "seedance_2.0": 0.80,
            "seedance_2_0": 0.80,
            "seedance_2_0_mini": 0.60,
            "seedance_2.0_fast": 0.50,
            "kling_3.0": 0.10,
            "kling3_0": 0.10,
            "wan_2.5": 0.10,
            "wan2_6": 0.10,
            "veo_3.1": 0.50,
            "veo3_1": 0.50,
            "grok_video_v15": 0.15,
            "gemini_omni": 0.50,
            "seedance_2_5": 0.60,
            "sora_2": 0.50,
            "soul_cinema": 0.15,
        }
        base = base_costs.get(model, 0.15)
        return base * (duration / 5)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        model = str(inputs.get("model", _DEFAULT_MODEL))
        if model in ("veo_3.1", "veo3_1", "sora_2", "seedance_2.0", "seedance_2_0"):
            return 120.0
        if model in ("seedance_2.0_fast", "seedance_2_0_mini"):
            return 60.0
        return 60.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        start = time.time()
        operation = str(inputs.get("operation", "text_to_video"))
        if operation not in ("text_to_video", "image_to_video"):
            return ToolResult(success=False, error=f"Unsupported Higgsfield operation: {operation}")
        if operation == "image_to_video" and not inputs.get("image_url"):
            return ToolResult(success=False, error="image_to_video requires image_url")

        credentials = self._get_credentials()
        cli_path = self._get_cli_path()
        if credentials:
            return self._execute_via_api(inputs, credentials, start)
        if cli_path:
            return self._execute_via_cli(inputs, cli_path, start)
        return ToolResult(success=False, error="Higgsfield is not configured. " + self.install_instructions)

    def _execute_via_cli(
        self,
        inputs: dict[str, Any],
        cli_path: str,
        start: float,
    ) -> ToolResult:
        model = str(inputs.get("model", _DEFAULT_MODEL))
        try:
            with self._materialize_reference_image(inputs.get("image_url")) as reference:
                command = self._build_cli_command(cli_path, inputs, reference)
                result = self.run_command(command, timeout=self._CLI_TIMEOUT_SECONDS)
            response_payload, video_url = self._parse_cli_response(result.stdout)
            output_path = self._download_video(video_url, inputs)
            extra = {
                "auth_method": "oauth_cli",
                "cli_model": self._cli_model_id(model),
                "result_url": video_url,
            }
            job_id = self._find_job_id(response_payload)
            if job_id:
                extra["job_id"] = job_id
            return self._success_result(inputs, output_path, start, model, extra)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="Higgsfield CLI generation timed out after 15 minutes.")
        except ToolCommandError as exc:
            detail = getattr(exc, "detail", "") or "command failed"
            detail = detail.strip().splitlines()[-1][:300]
            return ToolResult(success=False, error=f"Higgsfield CLI generation failed: {detail}")
        except (OSError, requests.RequestException, ValueError) as exc:
            return ToolResult(success=False, error=f"Higgsfield CLI generation failed: {exc}")

    @classmethod
    def _cli_model_id(cls, model: str) -> str:
        return _CLI_MODEL_ALIASES.get(model, model)

    @classmethod
    def _build_cli_command(
        cls,
        cli_path: str,
        inputs: dict[str, Any],
        reference: str | None,
    ) -> list[str]:
        model = str(inputs.get("model", _DEFAULT_MODEL))
        command = [
            cli_path,
            "generate",
            "create",
            cls._cli_model_id(model),
            "--prompt",
            str(inputs["prompt"]),
        ]
        if inputs.get("duration") is not None:
            command.extend(["--duration", str(inputs["duration"])])
        if inputs.get("aspect_ratio"):
            command.extend(["--aspect_ratio", str(inputs["aspect_ratio"])])
        if str(inputs.get("operation", "text_to_video")) == "image_to_video":
            if not reference:
                raise ValueError("image_to_video requires image_url")
            command.extend(["--start-image", reference])
        command.extend(["--wait", "--json"])
        return command

    @staticmethod
    def _parse_cli_response(stdout: str) -> tuple[Any, str]:
        """Parse --json output and return its payload plus the media URL."""
        candidates: list[Any] = []
        text = (stdout or "").strip()
        if text:
            try:
                candidates.append(json.loads(text))
            except json.JSONDecodeError:
                pass
            for line in reversed(text.splitlines()):
                line = line.strip()
                for marker in ("{", "["):
                    start = line.find(marker)
                    if start < 0:
                        continue
                    try:
                        candidates.append(json.loads(line[start:]))
                    except json.JSONDecodeError:
                        continue
        for payload in candidates:
            url = HiggsFieldVideo._find_media_url(payload)
            if url:
                return payload, url
        raise ValueError("Higgsfield CLI returned no media URL")

    @staticmethod
    def _find_media_url(value: Any) -> str | None:
        media_keys = ("result_url", "output_url", "video_url", "download_url", "media_url", "min_result_url")
        if isinstance(value, dict):
            for key in media_keys:
                candidate = value.get(key)
                if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                    return candidate
            for child in value.values():
                found = HiggsFieldVideo._find_media_url(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = HiggsFieldVideo._find_media_url(child)
                if found:
                    return found
        return None

    @staticmethod
    def _find_job_id(value: Any) -> str | None:
        if isinstance(value, dict):
            candidate = value.get("id")
            if isinstance(candidate, str) and candidate:
                return candidate
            for child in value.values():
                found = HiggsFieldVideo._find_job_id(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = HiggsFieldVideo._find_job_id(child)
                if found:
                    return found
        return None

    @staticmethod
    def _output_path(inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("output_path") or "higgsfield_output.mp4"))

    def _download_video(self, video_url: str, inputs: dict[str, Any]) -> Path:
        response = requests.get(video_url, timeout=120)
        response.raise_for_status()
        if not response.content:
            raise ValueError("Higgsfield returned an empty video")
        output_path = self._output_path(inputs)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(response.content)
        return output_path

    @contextmanager
    def _materialize_reference_image(self, image_url: str | None) -> Iterator[str | None]:
        if not image_url or not image_url.startswith(("http://", "https://")):
            yield image_url
            return

        parsed = urlparse(image_url)
        suffix = Path(parsed.path).suffix
        if not suffix or len(suffix) > 10 or not suffix[1:].isalnum():
            suffix = ".img"
        temp_path: Path | None = None
        response = requests.get(image_url, timeout=30)
        try:
            response.raise_for_status()
            content = response.content
            if len(content) > self._REFERENCE_IMAGE_MAX_BYTES:
                raise ValueError("reference image exceeds the 50 MB limit")
            with tempfile.NamedTemporaryFile(
                prefix="higgsfield-reference-", suffix=suffix, delete=False
            ) as handle:
                handle.write(content)
                temp_path = Path(handle.name)
            yield str(temp_path)
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
            if temp_path:
                temp_path.unlink(missing_ok=True)

    def _execute_via_api(
        self,
        inputs: dict[str, Any],
        credentials: tuple[str, str],
        start: float,
    ) -> ToolResult:
        api_key, api_secret = credentials
        operation = str(inputs.get("operation", "text_to_video"))
        model = str(inputs.get("model", _DEFAULT_MODEL))
        payload: dict[str, Any] = {
            "prompt": inputs["prompt"],
            "model": model,
            "task": operation.replace("_", "-"),
        }
        if inputs.get("duration"):
            payload["duration"] = int(inputs["duration"])
        if inputs.get("aspect_ratio"):
            payload["aspect_ratio"] = inputs["aspect_ratio"]
        if operation == "image_to_video" and inputs.get("image_url"):
            payload["image_url"] = inputs["image_url"]

        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-API-Secret": api_secret,
            "Content-Type": "application/json",
        }
        try:
            submit_resp = requests.post(
                "https://platform.higgsfield.ai/v1/generations",
                headers=headers,
                json=payload,
                timeout=30,
            )
            submit_resp.raise_for_status()
            gen_data = submit_resp.json()
            generation_id = gen_data["id"]
            status_url = gen_data.get(
                "status_url",
                f"https://platform.higgsfield.ai/v1/generations/{generation_id}",
            )

            video_url = None
            for _ in range(72):
                time.sleep(5)
                poll_resp = requests.get(status_url, headers=headers, timeout=15)
                poll_resp.raise_for_status()
                poll_data = poll_resp.json()
                status = poll_data.get("status", "Unknown")
                if status in ("Completed", "COMPLETED"):
                    video_url = poll_data.get("output_url") or poll_data.get("url")
                    break
                if status in ("Failed", "FAILED", "NSFW", "Cancelled", "CANCELLED"):
                    return ToolResult(
                        success=False,
                        error=f"Higgsfield generation {status}: {poll_data.get('error', 'unknown')}",
                    )

            if not video_url:
                return ToolResult(success=False, error="Higgsfield generation timed out.")
            output_path = self._download_video(video_url, inputs)
            return self._success_result(
                inputs,
                output_path,
                start,
                model,
                {"auth_method": "direct_api", "job_id": generation_id},
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"Higgsfield video generation failed: {exc}")

    def _success_result(
        self,
        inputs: dict[str, Any],
        output_path: Path,
        start: float,
        model: str,
        extra: dict[str, Any],
    ) -> ToolResult:
        from tools.video._shared import probe_output

        probed = probe_output(output_path)
        data = {
            "provider": "higgsfield",
            "model": model,
            "prompt": inputs["prompt"],
            "operation": inputs.get("operation", "text_to_video"),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
            "output": str(output_path),
            "output_path": str(output_path),
            "format": "mp4",
            **extra,
            **probed,
        }
        return ToolResult(
            success=True,
            data=data,
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            duration_seconds=round(time.time() - start, 2),
            model=model,
        )
