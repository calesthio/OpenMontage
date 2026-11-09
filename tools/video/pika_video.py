"""Pika H3 Flex video generation through the Pika API (api.dev.pika.art).

Pika H3 Flex generates 3-15 second clips with native synchronized stereo audio
from text, a first and/or last frame, or up to twelve ordered image, video and
audio references. 480p and 768p are native; 1080p, 2k and 4k are generated at
768p and upscaled once by the service.

The API is asynchronous: submit, poll ``/v1/media/jobs/{id}``, download. The
job record carries a settled billing charge, which this tool reports as the
actual ``cost_usd``. Local frame and reference files are uploaded through the
API's presigned upload flow; nothing is sent to a third-party host.

Request schemas and prices are pinned in
``tools/provider_contracts/pika_h3_flex.json`` from the public catalog.
"""

from __future__ import annotations

import json
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from jsonschema import Draft202012Validator
from requests.exceptions import RequestException

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
    ToolTier,
)
from tools.provider_jobs import download, poll, save_job
from tools.provider_pricing import PriceQuoteRequired

DEFAULT_BASE_URL = "https://api.dev.pika.art"
MODEL = "pika-h3-flex"
VENDOR = "pika"
CONTRACT_PATH = Path(__file__).resolve().parent.parent / "provider_contracts" / "pika_h3_flex.json"

OPERATION_FUNCTIONS = {
    "text_to_video": "text-to-video",
    "image_to_video": "image-to-video",
    "first_last_frame_to_video": "image-to-video",
    "reference_to_video": "reference-to-video",
}
NATIVE_RESOLUTIONS = ("480p", "768p")
UPSCALE_RESOLUTIONS = ("1080p", "2k", "4k")
RESOLUTIONS = NATIVE_RESOLUTIONS + UPSCALE_RESOLUTIONS
ASPECT_RATIOS = ["auto", "21:9", "16:9", "3:2", "4:3", "5:4", "1:1", "4:5", "3:4", "2:3", "9:16", "9:21"]
MIN_DURATION = 3
MAX_DURATION = 15
DEFAULT_DURATION = 5
DEFAULT_RESOLUTION = "768p"
REFERENCE_LIMITS = {"image": 9, "video": 3, "audio": 3}
REFERENCE_TOTAL_LIMIT = 12
# Output length rounds up to the model's 17n+5 frame grid; allow one extra second
# in estimates so preflight never undercounts. The settled charge is authoritative.
ESTIMATE_DURATION_ALLOWANCE_SECONDS = 1
BILLING_SETTLE_DELAYS = (1.0, 2.0, 5.0)
DRY_RUN_PLACEHOLDER = "https://dry-run.invalid/"

_CODE_HINTS = {
    "insufficient_balance": "Add funds at https://dev.pika.art (Billing) and submit again.",
    "cycle_limit_exceeded": "Your organization's billing cycle limit is reached; raise it at https://dev.pika.art.",
    "membership_required": "This model needs an eligible Pika plan; check https://dev.pika.art.",
    "rate_limited": "Per-minute, per-day or queue limit reached. Wait for Retry-After, then submit again.",
    "content_moderation": "The prompt or inputs were rejected by moderation; revise them.",
    "invalid_input": "The request was rejected as invalid; check the message for the field.",
    "provider_timeout": "The model timed out; a new submission is usually fine.",
    "provider_unavailable": "The model is temporarily unavailable; retry later.",
    "admission_suspended": "Admission is suspended for this organization; contact Pika support.",
}
_RETRYABLE_CODES = {"provider_timeout", "provider_unavailable", "rate_limited", "internal", "timed_out"}


class PikaAPIError(RuntimeError):
    """A request- or job-level error returned by the Pika API."""

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None,
                 retry_after: str | None = None, job_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.retry_after = retry_after
        self.job_id = job_id


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _rate_table(pricing: dict[str, Any], role: str) -> dict[str, float]:
    """Map resolution -> USD per unit for one pricing component of the catalog."""
    for component in pricing.get("components", []):
        if (component.get("name") or component.get("role")) != role:
            continue
        table: dict[str, float] = {}
        for tier in component.get("price_tiers", []):
            spec = tier.get("spec") or {}
            if set(spec) == {"resolution"}:
                table[spec["resolution"]] = int(tier["micro_usd"]) / 1_000_000
        return table
    return {}


class PikaVideo(BaseTool):
    name = "pika_video"
    version = "0.1.1"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "pika"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.API
    resume_support = ResumeSupport.FROM_CHECKPOINT

    dependencies = ["env:PIKA_API_KEY"]
    install_instructions = (
        "Set PIKA_API_KEY to a Pika API key.\n"
        "  1. Sign in at https://dev.pika.art and create an organization.\n"
        "  2. Open API Keys and create a key.\n"
        "  3. Add funds under Billing; generation is prepaid with no free tier.\n"
        "  Optional: PIKA_API_BASE_URL overrides https://api.dev.pika.art.\n"
        "  Support: support@pika.art"
    )
    agent_skills = ["pika-h3-flex", "ai-video-gen"]
    # Comparable to the other premium hosted providers; without this, a beta
    # tool is scored 0.7 by stability alone and ranks below older providers.
    quality_score = 0.9

    capabilities = [
        "text_to_video",
        "image_to_video",
        "first_last_frame_to_video",
        "reference_to_video",
    ]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_last_frame_to_video": True,
        "reference_to_video": True,
        "native_audio": True,
        "camera_direction": True,
        "multi_shot": True,
        "reference_image": True,
        "reference_video": True,
        "reference_audio": True,
        "last_frame": True,
        "seed": True,
        "prompt_rewrite": True,
        "upscale_4k": True,
        "short_clips": True,
        "social_ads": True,
    }
    # Routing hint for provider_routing.filter_explicit_route: model -> operation -> endpoint.
    models = {MODEL: dict(OPERATION_FUNCTIONS)}
    best_for = [
        "3-15 second clips with native synchronized dialogue, ambience and music",
        "multi-shot storytelling, motion graphics and product films from one prompt",
        "reference-guided animation from up to 9 images, 3 videos and 3 audio clips",
        "first/last-frame conditioning and 1080p/2k/4k delivery from one API",
    ]
    not_good_for = [
        "offline generation",
        "clips longer than 15 seconds",
        "silent output (audio is always generated; strip it in post if needed)",
    ]
    fallback_tools = ["minimax_video", "seedance_video", "veo_video", "kling_video"]

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=1500, network_required=True
    )
    # Paid submission: never retried automatically.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "model", "operation", "generation_mode", "prompt", "duration", "seconds",
        "resolution", "aspect_ratio", "ratio", "seed", "rewrite", "prompt_optimizer",
        "generate_audio", "image_url", "image_path", "reference_image_url",
        "reference_image_path", "first_frame_image", "last_frame_image_url",
        "last_frame_image_path", "last_frame_image", "end_image_url", "references",
        "reference_image_urls", "reference_video_urls", "reference_audio_urls",
        "reference_image_paths", "reference_video_paths", "reference_audio_paths",
        "reference_paths", "reference_video_seconds", "provider_params", "resume_job",
    ]
    side_effects = [
        "submits a paid Pika generation job",
        "uploads local frame and reference files to Pika storage",
        "writes an MP4 and an optional job checkpoint",
    ]
    user_visible_verification = [
        "Watch the clip with sound: motion coherence, lip/audio sync, reference fidelity",
        "Confirm the settled charge in data.billing matches expectations",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "minLength": 1, "maxLength": 8000},
            "operation": {
                "type": "string",
                "enum": list(OPERATION_FUNCTIONS) + ["generate"],
                "description": (
                    "Inferred when omitted: references -> reference_to_video, both frames -> "
                    "first_last_frame_to_video, one frame -> image_to_video, else text_to_video."
                ),
            },
            "model": {"type": "string", "enum": [MODEL], "default": MODEL},
            "duration": {
                "type": ["integer", "string"],
                "description": f"Whole seconds, {MIN_DURATION}-{MAX_DURATION}. Output rounds up to the model's frame grid.",
                "default": DEFAULT_DURATION,
            },
            "seconds": {"type": ["integer", "string"], "description": "Alias for duration."},
            "resolution": {
                "type": "string",
                "enum": list(RESOLUTIONS),
                "default": DEFAULT_RESOLUTION,
                "description": "480p/768p native; 1080p/2k/4k generated at 768p then upscaled once.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ASPECT_RATIOS,
                "description": "Omitted: auto when rewrite is on, else the first keyframe's ratio or 16:9.",
            },
            "ratio": {"type": "string", "enum": ASPECT_RATIOS, "description": "Alias for aspect_ratio."},
            "seed": {"type": "integer", "minimum": 0},
            "rewrite": {
                "type": "boolean",
                "default": True,
                "description": "Let Pika improve the prompt before generation. Disable for exact prompt control.",
            },
            "prompt_optimizer": {"type": "boolean", "description": "Alias for rewrite."},
            # First / last frame (image-to-video). URL forms must be http(s); local paths are
            # uploaded to Pika by this tool. The selector-facing names are used on purpose:
            # advertising image_url would make video_selector upload local frames to fal first.
            "reference_image_url": {"type": "string", "description": "First-frame image URL (JPEG, PNG or WebP, up to 24 MiB)."},
            "reference_image_path": {"type": "string", "description": "Local first-frame image; uploaded to Pika."},
            "first_frame_image": {"type": "string", "description": "Alias for reference_image_url."},
            "last_frame_image_url": {"type": "string", "description": "Last-frame image URL."},
            "last_frame_image_path": {"type": "string", "description": "Local last-frame image; uploaded to Pika."},
            "last_frame_image": {"type": "string", "description": "Alias for last_frame_image_url."},
            "end_image_url": {"type": "string", "description": "Alias for last_frame_image_url."},
            # References (reference-to-video).
            "references": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "enum": ["image", "video", "audio"]},
                        "url": {"type": "string"},
                        "path": {"type": "string"},
                    },
                    "required": ["type"],
                },
                "description": (
                    "Ordered references in Pika's native shape. Each item has type and either url "
                    "or a local path that is uploaded. Takes precedence over the per-type lists."
                ),
            },
            "reference_image_urls": {"type": "array", "items": {"type": "string"}},
            "reference_video_urls": {"type": "array", "items": {"type": "string"}},
            "reference_audio_urls": {"type": "array", "items": {"type": "string"}},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}},
            "reference_video_paths": {"type": "array", "items": {"type": "string"}},
            "reference_audio_paths": {"type": "array", "items": {"type": "string"}},
            "reference_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local reference files of any supported kind, typed by extension and uploaded.",
            },
            "reference_video_seconds": {
                "type": "number",
                "minimum": 0,
                "description": (
                    "Total seconds of reference video supplied. Reference-to-video bills input video "
                    "seconds as well as output seconds; provide this for an exact preflight estimate."
                ),
            },
            "generate_audio": {
                "type": "boolean",
                "description": "Pika H3 Flex always generates audio; false is rejected rather than ignored.",
            },
            "provider_params": {
                "type": "object",
                "description": "Extra fields merged into the request verbatim, validated against the pinned schema.",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Validate and return the exact quoted price without uploading or generating. "
                    "Local files are represented by https://dry-run.invalid/ placeholders in the quoted request."
                ),
            },
            "output_path": {"type": "string"},
            "job_path": {"type": "string", "description": "Where to persist the job checkpoint for resume."},
            "resume_job": {"type": "object", "description": "Job metadata from a timed-out call; polls without resubmitting."},
            "poll_timeout": {"type": "number", "exclusiveMinimum": 0, "default": 900},
            "poll_interval": {"type": "number", "exclusiveMinimum": 0, "default": 3},
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "provider": {"type": "string"},
            "model": {"type": "string"},
            "operation": {"type": "string"},
            "job_id": {"type": "string"},
            "output": {"type": "string"},
            "video_url": {"type": "string"},
            "request": {"type": "object"},
            "usage": {"type": ["object", "null"]},
            "billing": {"type": ["object", "null"]},
            "free_generation": {"type": ["object", "null"], "description": "Set when Pika covered the job under a promotional allowance; the settled charge is then 0."},
            "cost_status": {"type": "string", "enum": ["settled", "pending", "unavailable", "estimated", "quoted"]},
            "estimated_cost_usd": {"type": ["number", "null"]},
            "resume_job": {"type": "object"},
        },
    }

    # ------------------------------------------------------------------
    # Construction and contract access
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self.contract = _load_contract()
        self._rates = {
            "text-to-video": _rate_table(self.contract["text-to-video"]["pricing"], "output"),
            "image-to-video": _rate_table(self.contract["image-to-video"]["pricing"], "output"),
            "reference-to-video": _rate_table(self.contract["reference-to-video"]["pricing"], "output"),
            "reference-video-input": _rate_table(
                self.contract["reference-to-video"]["pricing"], "video_input"
            ),
        }

    @staticmethod
    def base_url() -> str:
        return os.environ.get("PIKA_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["hosting_provider"] = self.provider
        info["model_catalog"] = {
            MODEL: {
                "routes": dict(OPERATION_FUNCTIONS),
                "verified_on": self.contract["text-to-video"]["verified_on"],
                "pricing_status": "published",
                "usd_per_output_second": self._rates["text-to-video"],
            }
        }
        info["billing"] = {
            "model": "bring_your_own_key",
            "prepaid": True,
            "free_tier": False,
            "charged_on": "successful generations only",
            "dashboard": "https://dev.pika.art",
        }
        return info

    # ------------------------------------------------------------------
    # Estimates
    # ------------------------------------------------------------------

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Resuming a job submits nothing new; the original preflight estimate stands.
        resume_job = inputs.get("resume_job")
        if isinstance(resume_job, dict) and resume_job.get("id"):
            return float(resume_job.get("estimated_cost_usd") or 0.0)
        # Use the same validated payload as submission, including provider_params,
        # without uploading local files or contacting the provider during preflight.
        _, function, payload = self._build_request({**inputs, "dry_run": True}, {})
        return self._estimate_request(function, payload, inputs.get("reference_video_seconds"))

    def _estimate_request(self, function: str, payload: dict[str, Any], video_seconds: Any) -> float:
        resolution = payload["resolution"]
        seconds = payload["duration"] + ESTIMATE_DURATION_ALLOWANCE_SECONDS
        rates = self._rates[function]
        if resolution not in rates:
            raise PriceQuoteRequired(
                f"No published {function} rate for {resolution}; set dry_run=true for an exact quote"
            )
        cost = rates[resolution] * seconds
        if function == "reference-to-video":
            has_video = any(ref["type"] == "video" for ref in payload["references"])
            if has_video:
                if video_seconds is None:
                    raise PriceQuoteRequired(
                        "reference-to-video bills input video seconds; pass reference_video_seconds "
                        "or set dry_run=true for an exact quote"
                    )
                input_rate = self._rates["reference-video-input"].get(resolution)
                if input_rate is None:
                    raise PriceQuoteRequired(f"No published reference video input rate for {resolution}")
                cost += input_rate * float(video_seconds)
        return round(cost, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        seconds = self._normalize_duration(inputs)
        resolution = self._normalize_resolution(inputs)
        runtime = 45.0 + 10.0 * seconds
        if resolution in UPSCALE_RESOLUTIONS:
            runtime += 60.0
        return runtime

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        api_key = os.environ.get("PIKA_API_KEY")
        if not api_key:
            return ToolResult(success=False, error="PIKA_API_KEY not set. " + self.install_instructions)
        headers = {"X-API-Key": api_key}
        job = dict(inputs.get("resume_job") or {})

        try:
            if not job:
                operation, function, payload = self._build_request(inputs, headers)
                try:
                    estimate = self._estimate_request(function, payload, inputs.get("reference_video_seconds"))
                except PriceQuoteRequired:
                    estimate = None
                if inputs.get("dry_run"):
                    quoted = self._quote(function, payload)
                    return ToolResult(
                        success=True,
                        data={
                            "provider": self.provider,
                            "model": MODEL,
                            "operation": operation,
                            "dry_run": True,
                            "request": payload,
                            "local_files": self._local_files(inputs),
                            "quoted_cost_usd": quoted,
                            "estimated_cost_usd": estimate,
                            "cost_status": "quoted",
                        },
                        cost_usd=0.0,
                        duration_seconds=round(time.time() - started, 2),
                        model=MODEL,
                    )
                idempotency_key = str(uuid.uuid4())
                submitted = self._request(
                    "POST",
                    f"{self.base_url()}/v1/media/{VENDOR}/{MODEL}/{function}",
                    headers={**headers, "Content-Type": "application/json", "Idempotency-Key": idempotency_key},
                    json=payload,
                )
                self._raise_if_failed(submitted)
                job = {
                    "id": submitted["id"],
                    "tool": self.name,
                    "model": MODEL,
                    "operation": operation,
                    "function": function,
                    "request": payload,
                    "idempotency_key": idempotency_key,
                    "estimated_cost_usd": estimate,
                    "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                save_job(inputs.get("job_path"), job)

            if job.get("tool") != self.name or job.get("model") != MODEL or not job.get("id"):
                raise ValueError("resume_job does not belong to pika_video")

            job_url = f"{self.base_url()}/v1/media/jobs/{quote(str(job['id']), safe='')}"

            def fetch() -> dict[str, Any]:
                return self._request("GET", job_url, headers=headers)

            try:
                result = poll(
                    fetch,
                    timeout=float(inputs.get("poll_timeout", 900)),
                    interval=float(inputs.get("poll_interval", 3)),
                )
            except TimeoutError as exc:
                return ToolResult(
                    success=False,
                    error=f"Pika job {job['id']} is still running after poll_timeout. {exc}",
                    data={"resume_job": job, "job_id": job["id"], "retryable": True, "provider": self.provider},
                    cost_usd=0.0,
                    duration_seconds=round(time.time() - started, 2),
                    model=MODEL,
                )
            except RuntimeError as exc:
                # poll() raised on a terminal failed status; re-read for the structured error.
                final = fetch()
                error = final.get("error") or {}
                code = error.get("code") or "provider_error"
                return self._failure(
                    f"Pika job {job['id']} failed ({code}): {error.get('message') or exc}. "
                    + _CODE_HINTS.get(code, ""),
                    job=job,
                    code=code,
                    retryable=code in _RETRYABLE_CODES,
                    started=started,
                )

            output = (result.get("output") or {}).get("video") or {}
            video_url = output.get("url")
            if not video_url:
                raise ValueError(f"Completed job {job['id']} returned no video URL")
            output_path = Path(inputs.get("output_path") or f"pika_{job['id']}.mp4")
            artifact = download(video_url, output_path)

            billing, cost_usd, cost_status = self._settle_billing(fetch, result, job.get("estimated_cost_usd"))
            request = job.get("request") or {}
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": MODEL,
                    "operation": job.get("operation"),
                    "job_id": job["id"],
                    "output": artifact,
                    "format": "mp4",
                    "video_url": video_url,
                    "content_type": output.get("content_type"),
                    "request": request,
                    "resolution": request.get("resolution"),
                    "duration_requested": request.get("duration"),
                    "aspect_ratio": request.get("aspect_ratio"),
                    "rewrite": request.get("rewrite"),
                    "usage": result.get("usage"),
                    "billing": billing,
                    "free_generation": result.get("free_generation"),
                    "cost_status": cost_status,
                    "estimated_cost_usd": job.get("estimated_cost_usd"),
                    "resume_job": job,
                    "native_audio": True,
                },
                artifacts=[artifact],
                cost_usd=cost_usd,
                duration_seconds=round(time.time() - started, 2),
                seed=request.get("seed"),
                model=MODEL,
            )
        except PikaAPIError as exc:
            hint = _CODE_HINTS.get(exc.code or "", "")
            message = f"Pika API error ({exc.code or exc.status}): {exc}. {hint}".strip()
            if exc.retry_after:
                message += f" Retry-After: {exc.retry_after}."
            return self._failure(
                message, job=job, code=exc.code, retryable=(exc.code in _RETRYABLE_CODES), started=started,
                retry_after=exc.retry_after,
            )
        except Exception as exc:  # validation, upload, download and transport errors
            return self._failure(f"Pika video generation failed: {exc}", job=job, started=started)

    # ------------------------------------------------------------------
    # Request building
    # ------------------------------------------------------------------

    def _build_request(self, inputs: dict[str, Any], headers: dict[str, str]) -> tuple[str, str, dict[str, Any]]:
        if inputs.get("generate_audio") is False:
            raise ValueError(
                "Pika H3 Flex always generates native audio; omit generate_audio or strip audio in post"
            )
        model = inputs.get("model") or MODEL
        if model != MODEL:
            raise ValueError(f"Unsupported model {model!r}; pika_video currently serves {MODEL}")

        operation = self._resolve_operation(inputs)
        function = OPERATION_FUNCTIONS[operation]
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")

        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": self._normalize_duration(inputs),
            "resolution": self._normalize_resolution(inputs),
            "rewrite": self._normalize_rewrite(inputs),
        }
        aspect_ratio = inputs.get("aspect_ratio") or inputs.get("ratio")
        if aspect_ratio:
            aspect_ratio = str(aspect_ratio).lower()
            if aspect_ratio not in ASPECT_RATIOS:
                raise ValueError(f"aspect_ratio must be one of: {', '.join(ASPECT_RATIOS)}")
            payload["aspect_ratio"] = aspect_ratio
        if inputs.get("seed") is not None:
            payload["seed"] = int(inputs["seed"])

        uploading = not inputs.get("dry_run")
        if operation in {"image_to_video", "first_last_frame_to_video"}:
            first = self._first_frame(inputs, headers, uploading)
            last = self._last_frame(inputs, headers, uploading)
            if first:
                payload["image"] = first
            if last:
                payload["last_frame_image"] = last
            if operation == "first_last_frame_to_video" and not (first and last):
                raise ValueError("first_last_frame_to_video requires both a first and a last frame")
        elif operation == "reference_to_video":
            payload["references"] = self._references(inputs, headers, uploading)
        else:
            if self._first_frame(inputs, headers, False) or self._last_frame(inputs, headers, False):
                raise ValueError("text_to_video does not take frames; use image_to_video")
            if self._has_reference_inputs(inputs):
                raise ValueError("text_to_video does not take references; use reference_to_video")

        extra = inputs.get("provider_params") or {}
        if not isinstance(extra, dict):
            raise ValueError("provider_params must be an object")
        payload.update(extra)

        schema = self.contract[function]["input_schema"]
        Draft202012Validator(schema).validate(payload)
        return operation, function, payload

    def _resolve_operation(self, inputs: dict[str, Any]) -> str:
        operation = inputs.get("operation") or inputs.get("generation_mode")
        if operation in (None, "", "generate"):
            if self._has_reference_inputs(inputs):
                return "reference_to_video"
            first = self._first_frame(inputs, {}, False)
            last = self._last_frame(inputs, {}, False)
            if first and last:
                return "first_last_frame_to_video"
            if first or last:
                return "image_to_video"
            return "text_to_video"
        if operation not in OPERATION_FUNCTIONS:
            raise ValueError(f"operation must be one of: {', '.join(OPERATION_FUNCTIONS)}")
        return str(operation)

    @staticmethod
    def _local_files(inputs: dict[str, Any]) -> list[str]:
        files: list[str] = []
        for key in ("reference_image_path", "image_path", "last_frame_image_path"):
            if inputs.get(key):
                files.append(str(inputs[key]))
        for key in ("reference_image_paths", "reference_video_paths", "reference_audio_paths", "reference_paths"):
            files.extend(str(p) for p in (inputs.get(key) or []))
        files.extend(str(r["path"]) for r in (inputs.get("references") or []) if isinstance(r, dict) and r.get("path"))
        return files

    @staticmethod
    def _has_reference_inputs(inputs: dict[str, Any]) -> bool:
        return any(
            inputs.get(key)
            for key in (
                "references", "reference_image_urls", "reference_video_urls", "reference_audio_urls",
                "reference_image_paths", "reference_video_paths", "reference_audio_paths", "reference_paths",
            )
        )

    def _first_frame(self, inputs: dict[str, Any], headers: dict[str, str], uploading: bool) -> str | None:
        url = inputs.get("image_url") or inputs.get("reference_image_url") or inputs.get("first_frame_image")
        path = inputs.get("image_path") or inputs.get("reference_image_path")
        return self._media_url(url, path, headers, uploading, "first frame")

    def _last_frame(self, inputs: dict[str, Any], headers: dict[str, str], uploading: bool) -> str | None:
        url = inputs.get("last_frame_image_url") or inputs.get("last_frame_image") or inputs.get("end_image_url")
        path = inputs.get("last_frame_image_path")
        return self._media_url(url, path, headers, uploading, "last frame")

    def _media_url(self, url: Any, path: Any, headers: dict[str, str], uploading: bool, label: str) -> str | None:
        if url and path:
            raise ValueError(f"Specify the {label} as a URL or a local path, not both")
        if url:
            url = str(url)
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"{label} must be an http(s) URL; pass local files via the *_path input")
            return url
        if path:
            if uploading:
                return self._upload(Path(str(path)), headers)
            # dry_run / operation inference: nothing is uploaded; a placeholder keeps the
            # payload schema-valid for the free quote and is reported in data.local_files.
            return f"{DRY_RUN_PLACEHOLDER}{Path(str(path)).name}"
        return None

    def _references(self, inputs: dict[str, Any], headers: dict[str, str], uploading: bool) -> list[dict[str, str]]:
        ordered: list[tuple[str, str | None, str | None]] = []
        if inputs.get("references"):
            for item in inputs["references"]:
                if not isinstance(item, dict) or item.get("type") not in REFERENCE_LIMITS:
                    raise ValueError("Each reference needs a type of image, video or audio")
                ordered.append((item["type"], item.get("url"), item.get("path")))
        else:
            for kind in ("image", "video", "audio"):
                for url in inputs.get(f"reference_{kind}_urls") or []:
                    ordered.append((kind, str(url), None))
                for path in inputs.get(f"reference_{kind}_paths") or []:
                    ordered.append((kind, None, str(path)))
            for path in inputs.get("reference_paths") or []:
                kind = self._guess_kind(str(path))
                if kind is None:
                    raise ValueError(f"Cannot tell whether {path} is an image, video or audio file")
                ordered.append((kind, None, str(path)))

        counts = {kind: 0 for kind in REFERENCE_LIMITS}
        for kind, _, _ in ordered:
            counts[kind] += 1
        if len(ordered) > REFERENCE_TOTAL_LIMIT:
            raise ValueError(f"At most {REFERENCE_TOTAL_LIMIT} references in total")
        for kind, limit in REFERENCE_LIMITS.items():
            if counts[kind] > limit:
                raise ValueError(f"At most {limit} {kind} references")
        if counts["image"] + counts["video"] == 0:
            raise ValueError("reference_to_video needs at least one image or video reference")

        references = []
        for kind, url, path in ordered:
            resolved = self._media_url(url, path, headers, uploading, f"{kind} reference")
            references.append({"type": kind, "url": resolved})
        return references

    @staticmethod
    def _guess_kind(path: str) -> str | None:
        mime, _ = mimetypes.guess_type(path)
        if not mime:
            return None
        head = mime.split("/", 1)[0]
        return head if head in REFERENCE_LIMITS else None

    # ------------------------------------------------------------------
    # Normalizers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_duration(inputs: dict[str, Any]) -> int:
        raw = inputs.get("duration", inputs.get("seconds", DEFAULT_DURATION))
        if raw is None:
            raw = DEFAULT_DURATION
        text = str(raw).strip().lower()
        if text.endswith("s"):
            text = text[:-1]
        try:
            value = int(float(text))
        except ValueError as exc:
            raise ValueError(f"duration must be a whole number of seconds, got {raw!r}") from exc
        if value != float(text):
            raise ValueError("duration must be a whole number of seconds")
        if not MIN_DURATION <= value <= MAX_DURATION:
            raise ValueError(f"duration must be between {MIN_DURATION} and {MAX_DURATION} seconds")
        return value

    @staticmethod
    def _normalize_resolution(inputs: dict[str, Any]) -> str:
        raw = str(inputs.get("resolution") or DEFAULT_RESOLUTION).strip().lower()
        if raw not in RESOLUTIONS:
            raise ValueError(f"resolution must be one of: {', '.join(RESOLUTIONS)}")
        return raw

    @staticmethod
    def _normalize_rewrite(inputs: dict[str, Any]) -> bool:
        if "rewrite" in inputs and inputs["rewrite"] is not None:
            return bool(inputs["rewrite"])
        if "prompt_optimizer" in inputs and inputs["prompt_optimizer"] is not None:
            return bool(inputs["prompt_optimizer"])
        return True

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @staticmethod
    def _request(method: str, url: str, *, headers: dict[str, str] | None = None, **kwargs: Any) -> dict[str, Any]:
        """Call the Pika API and turn its two error shapes into PikaAPIError."""
        response = requests.request(method, url, headers=headers, timeout=60, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400:
            retry_after = response.headers.get("Retry-After") if response.headers else None
            if isinstance(body, dict) and isinstance(body.get("error"), dict):
                error = body["error"]
                raise PikaAPIError(
                    str(error.get("message") or response.reason or "request failed"),
                    code=error.get("code") or "provider_error",
                    status=response.status_code,
                    retry_after=retry_after,
                    job_id=body.get("id"),
                )
            message = body.get("message") if isinstance(body, dict) else None
            raise PikaAPIError(
                str(message or response.text or response.reason or "request failed"),
                code=None,
                status=response.status_code,
                retry_after=retry_after,
            )
        if not isinstance(body, dict):
            raise PikaAPIError("Unexpected non-JSON response from Pika", status=response.status_code)
        return body

    @staticmethod
    def _raise_if_failed(job: dict[str, Any]) -> None:
        if str(job.get("status", "")).lower() == "failed":
            error = job.get("error") or {}
            raise PikaAPIError(
                str(error.get("message") or "submission rejected"),
                code=error.get("code") or "provider_error",
                job_id=job.get("id"),
            )

    def _upload(self, path: Path, headers: dict[str, str]) -> str:
        if not path.is_file():
            raise FileNotFoundError(f"Input file not found: {path}")
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        size = path.stat().st_size
        ticket = self._request(
            "POST",
            f"{self.base_url()}/v1/media/uploads",
            headers={**headers, "Content-Type": "application/json"},
            json={"content_type": content_type, "size_bytes": size},
        )
        upload_url = ticket.get("upload_url")
        permanent_url = ticket.get("url")
        if not upload_url or not permanent_url:
            raise PikaAPIError("Upload ticket did not include upload_url and url")
        put_headers = dict(ticket.get("headers") or {})
        put_headers.setdefault("Content-Type", content_type)
        with path.open("rb") as handle:
            response = requests.request("PUT", upload_url, headers=put_headers, data=handle, timeout=300)
        if response.status_code >= 400:
            raise PikaAPIError(
                f"Upload of {path.name} failed with HTTP {response.status_code}", status=response.status_code
            )
        return str(permanent_url)

    def _quote(self, function: str, payload: dict[str, Any]) -> float | None:
        api_id = quote(f"{VENDOR}/{MODEL}/{function}", safe="")
        body = self._request(
            "POST",
            f"{self.base_url()}/catalog/apis/{api_id}/quote",
            headers={"Content-Type": "application/json"},
            json=payload,
        )
        micro = body.get("micro_usd")
        return int(micro) / 1_000_000 if micro is not None else None

    @staticmethod
    def _settle_billing(fetch, result: dict[str, Any], estimate: float | None) -> tuple[dict[str, Any] | None, float | None, str]:
        """Return a settled charge or a flagged estimate without losing completed media."""
        billing = result.get("billing")
        for delay in BILLING_SETTLE_DELAYS:
            state = (billing or {}).get("state")
            if state == "settled":
                break
            if state == "unavailable":
                break
            time.sleep(delay)
            try:
                refreshed = fetch().get("billing")
            except (PikaAPIError, RequestException):
                # Generation and download already succeeded. Keep the last billing
                # record and retry reconciliation only, never the paid submission.
                continue
            if refreshed is not None:
                billing = refreshed
        state = (billing or {}).get("state")
        if state == "settled" and billing.get("charge_micro_usd") is not None:
            return billing, int(billing["charge_micro_usd"]) / 1_000_000, "settled"
        status = "unavailable" if state == "unavailable" else "pending"
        return billing, estimate, status

    def _failure(self, message: str, *, job: dict[str, Any], started: float, code: str | None = None,
                 retryable: bool = False, retry_after: str | None = None) -> ToolResult:
        data: dict[str, Any] = {"provider": self.provider, "model": MODEL, "retryable": retryable}
        if code:
            data["error_code"] = code
        if retry_after:
            data["retry_after"] = retry_after
        if job:
            data["job_id"] = job.get("id")
            data["resume_job"] = job
        return ToolResult(
            success=False,
            error=message,
            data=data,
            cost_usd=0.0,
            duration_seconds=round(time.time() - started, 2),
            model=MODEL,
        )
