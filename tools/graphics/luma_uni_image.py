"""Luma Agents uni-1 / uni-1-max image generation and edit adapter."""

from __future__ import annotations

import base64
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool, Determinism, ExecutionMode, ResourceProfile, RetryPolicy,
    ToolResult, ToolRuntime, ToolStability, ToolStatus, ToolTier,
)


class LumaUniImage(BaseTool):
    name = "luma_uni_image"
    version = "1.0.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "luma_agents"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    BASE_URL = "https://agents.lumalabs.ai/v1"
    dependencies = ["env:LUMA_AGENTS_API_KEY"]
    install_instructions = "Set LUMA_AGENTS_API_KEY to a Luma Agents API key."
    agent_skills = ["luma-uni-image"]
    capabilities = ["generate_image", "edit_image", "reference_image"]
    supports = {"image_edit": True, "image_reference": True, "multi_reference": True, "async_jobs": True}
    best_for = ["high-value hero frames", "reference-guided compositions", "controlled edits"]
    not_good_for = ["bulk inexpensive plates when FLUX is sufficient"]
    input_schema = {
        "type": "object", "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "minLength": 1, "maxLength": 6000},
            "operation": {"type": "string", "enum": ["generate", "edit"], "default": "generate"},
            "model": {"type": "string", "enum": ["uni-1", "uni-1-max"], "default": "uni-1"},
            "aspect_ratio": {"type": "string", "default": "16:9"},
            "output_format": {"type": "string", "enum": ["png", "jpeg"], "default": "png"},
            "source_path": {"type": "string"}, "source_url": {"type": "string"},
            "reference_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 9},
            "reference_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 9},
            "output_path": {"type": "string"}, "timeout_seconds": {"type": "integer", "default": 600},
        },
    }
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, network_required=True)
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    side_effects = ["writes image file", "submits paid Luma generation"]
    user_visible_verification = ["Inspect the saved image and provenance metadata"]

    def _key(self) -> str | None:
        return os.environ.get("LUMA_AGENTS_API_KEY") or os.environ.get("LUMA_API_KEY")

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._key() else ToolStatus.UNAVAILABLE

    @staticmethod
    def _image_ref(path: str | None = None, url: str | None = None) -> dict[str, str]:
        if path:
            source = Path(path).expanduser()
            if not source.is_file():
                raise ValueError(f"Image file not found: {source}")
            if source.stat().st_size > 30 * 1024 * 1024:
                raise ValueError("Image reference exceeds 30 MB")
            mime = mimetypes.guess_type(source.name)[0] or "image/png"
            return {"data": base64.b64encode(source.read_bytes()).decode("ascii"), "media_type": mime}
        if url:
            if not url.startswith("https://"):
                raise ValueError("Image reference URL must use HTTPS")
            return {"url": url}
        raise ValueError("An image reference path or URL is required")

    def build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = inputs.get("operation", "generate")
        model = inputs.get("model", "uni-1")
        if operation not in {"generate", "edit"}:
            raise ValueError("operation must be generate or edit")
        if model not in {"uni-1", "uni-1-max"}:
            raise ValueError("model must be uni-1 or uni-1-max")
        prompt = str(inputs.get("prompt", "")).strip()
        if not prompt or len(prompt) > 6000:
            raise ValueError("prompt must contain 1 to 6000 characters")
        payload: dict[str, Any] = {
            "model": model, "type": "image_edit" if operation == "edit" else "image",
            "prompt": prompt, "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
            "output_format": inputs.get("output_format", "png"),
        }
        paths = list(inputs.get("reference_paths") or [])
        urls = list(inputs.get("reference_urls") or [])
        if operation == "edit":
            source = self._image_ref(inputs.get("source_path"), inputs.get("source_url"))
            payload["source"] = source
        elif inputs.get("source_path") or inputs.get("source_url"):
            raise ValueError("source_path/source_url require operation=edit")
        if len(paths) + len(urls) > (8 if operation == "edit" else 9):
            raise ValueError("Too many reference images for the selected operation")
        refs = [self._image_ref(path=p) for p in paths]
        refs.extend(self._image_ref(url=u) for u in urls)
        if refs:
            payload["image_ref"] = refs
        return payload

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        model = inputs.get("model", "uni-1")
        references = len(inputs.get("reference_paths") or []) + len(inputs.get("reference_urls") or [])
        edited = inputs.get("operation", "generate") == "edit"
        if model == "uni-1-max":
            return 0.103 if edited or references else 0.100
        return 0.0434 if edited or references else 0.0404

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        key = self._key()
        if not key:
            return ToolResult(success=False, error=self.install_instructions)
        try:
            payload = self.build_payload(inputs)
        except (TypeError, ValueError, OSError) as exc:
            return ToolResult(success=False, error=str(exc))
        import requests

        started = time.monotonic()
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        try:
            response = requests.post(f"{self.BASE_URL}/generations", headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            job = response.json()
            job_id = job.get("id")
            if not job_id:
                raise RuntimeError("Luma response did not contain a generation id")
            deadline = started + int(inputs.get("timeout_seconds", 600))
            while time.monotonic() < deadline:
                time.sleep(2)
                response = requests.get(f"{self.BASE_URL}/generations/{job_id}", headers=headers, timeout=30)
                response.raise_for_status()
                job = response.json()
                state = job.get("state")
                if state == "failed":
                    raise RuntimeError(f"Luma generation failed ({job.get('failure_code', 'unknown')})")
                if state == "completed":
                    break
            else:
                return ToolResult(success=False, data={"job_id": job_id, "status": "timeout"}, error="Luma generation polling timed out; job can be resumed by id.")
            outputs = job.get("output") or []
            image_url = next((item.get("url") for item in outputs if item.get("url")), None)
            if not image_url:
                raise RuntimeError("Completed Luma generation did not return an output URL")
            image_response = requests.get(image_url, timeout=90)
            image_response.raise_for_status()
            suffix = ".jpg" if payload["output_format"] == "jpeg" else ".png"
            path = Path(inputs.get("output_path", f"luma_{job_id}{suffix}")).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(image_response.content)
            return ToolResult(success=True, data={"provider": self.provider, "model": job.get("model", payload["model"]), "job_id": job_id, "status": "completed", "output": str(path), "prompt": payload["prompt"], "output_format": payload["output_format"]}, artifacts=[str(path)], cost_usd=self.estimate_cost(inputs), duration_seconds=round(time.monotonic() - started, 2), model=job.get("model", payload["model"]))
        except Exception as exc:
            # Never return provider response bodies or credential-bearing URLs.
            status = getattr(getattr(exc, "response", None), "status_code", None)
            detail = f"HTTP {status}" if status else type(exc).__name__
            return ToolResult(success=False, error=f"Luma image request failed ({detail})", duration_seconds=round(time.monotonic() - started, 2))
