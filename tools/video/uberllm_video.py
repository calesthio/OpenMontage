"""Video generation through UberLLM (api.uberllm.dev).

One UberLLM key reaches Seedance 2.0, Wan 2.7, Kling 3, Veo 3.1 Fast, LTX 2.3,
Hailuo 02 and Vidu Q3 video models, and the same key and balance also serve
UberLLM's image, music and speech models. This tool covers video.

The API is asynchronous: submit to ``/v1/video/generations`` with an
``Idempotency-Key``, poll ``/v1/video/generations/{id}``, then download the
result with the same key. Failed, canceled and expired jobs cost nothing. The
finished job reports what it was billed as ``usage.cost_usd``, which this tool
returns as the actual ``cost_usd``.

The models this tool offers, their request schemas (from
``GET /v1/models/{model_id}``) and their per-second rates (from the free
``validate`` quote) are pinned in ``tools/provider_contracts/uberllm_video.json``.
Every payload is checked against the pinned schema before a paid submission.
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

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
from tools.provider_jobs import poll, save_job
from tools.provider_pricing import PriceQuoteRequired

DEFAULT_BASE_URL = "https://api.uberllm.dev"
CONTRACT_PATH = Path(__file__).resolve().parent.parent / "provider_contracts" / "uberllm_video.json"
DEFAULT_FAMILY = "seedance-2.0"
OPERATIONS = ("text_to_video", "image_to_video", "reference_to_video")
BILLING_SETTLE_DELAYS = (2.0, 5.0, 10.0)
MAX_INLINE_BYTES = 7 * 1024 * 1024

_CODE_HINTS = {
    "insufficient_balance": "Add credit at https://uberllm.dev/dashboard/credits and submit again.",
    "invalid_api_key": "Check UBERLLM_API_KEY; keys start with ull_ (https://uberllm.dev/signup).",
    "rate_limited": "Too many requests right now. Wait, then submit again.",
    "max_cost_too_low": "The job can cost more than max_cost_usd; raise it or pick a cheaper model or length.",
    "image_required": "This model needs a first frame or reference picture.",
    "invalid_image_url": "The picture link did not lead to a picture UberLLM could use.",
    "no_available_provider": "No seller can take this model right now; try again later or pick another model.",
}
_RETRYABLE_CODES = {"rate_limited", "no_available_provider", "provider_timeout", "provider_unavailable"}


class UberLLMAPIError(RuntimeError):
    """A request- or job-level error returned by the UberLLM API."""

    def __init__(self, message: str, *, code: str | None = None, status: int | None = None,
                 retry_after: str | None = None, retryable: bool | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.retry_after = retry_after
        self.retryable = retryable


def _load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


_CONTRACT = _load_contract()
FAMILIES: dict[str, dict[str, str]] = _CONTRACT["families"]
MODEL_SPECS: dict[str, dict[str, Any]] = _CONTRACT["models"]


class UberLLMVideo(BaseTool):
    name = "uberllm_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "uberllm"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API
    resume_support = ResumeSupport.FROM_CHECKPOINT

    dependencies = ["env:UBERLLM_API_KEY"]
    install_instructions = (
        "Set UBERLLM_API_KEY to an UberLLM key (starts with ull_).\n"
        "  1. Sign up at https://uberllm.dev/signup and create a key.\n"
        "  2. Add credit under Dashboard -> Credits; usage is prepaid, pay as you go from $5.\n"
        "  The same key also works for UberLLM's image, music, speech and chat models.\n"
        "  Optional: UBERLLM_BASE_URL overrides https://api.uberllm.dev."
    )
    agent_skills = ["uberllm-video", "ai-video-gen"]

    capabilities = list(OPERATIONS)
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_to_video": True,
        "native_audio": True,
        "aspect_ratio": True,
        "custom_duration": True,
        "reference_image": True,
        "multi_model_gateway": True,
        "short_clips": True,
    }
    # Routing hint for provider_routing.filter_explicit_route: model -> operation -> UberLLM model id.
    # Families first (the default family serves all three operations), then each exact id.
    models: dict[str, dict[str, str]] = {
        DEFAULT_FAMILY: dict(FAMILIES[DEFAULT_FAMILY]),
        **{family: dict(routes) for family, routes in FAMILIES.items() if family != DEFAULT_FAMILY},
        **{model_id: {spec["operation"]: model_id} for model_id, spec in MODEL_SPECS.items()},
    }
    best_for = [
        "one key for Seedance 2.0, Wan 2.7, Kling 3, Veo 3.1 Fast, LTX 2.3, Hailuo 02 and Vidu Q3",
        "the same key and prepaid balance as UberLLM image, music and speech models",
        "cheap drafts (Vidu Q3 Turbo, Hailuo 02) before rerunning the approved take on a premium model",
        "a free exact price check (dry_run) before any paid job",
    ]
    not_good_for = [
        "offline generation",
        "first/last-frame conditioning (not exposed here)",
        "clip lengths a model does not offer (each model has fixed lengths)",
    ]
    fallback_tools = ["seedance_video", "kling_video", "veo_video", "minimax_video"]

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=1500, network_required=True
    )
    # Paid submission: never retried automatically.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = [
        "model", "operation", "prompt", "duration", "resolution", "aspect_ratio", "generate_audio",
        "reference_image_url", "reference_image_path", "reference_image_urls", "reference_image_paths",
        "provider_params", "max_cost_usd", "resume_job",
    ]
    side_effects = [
        "submits a paid UberLLM video job",
        "uploads local frame and reference pictures to UberLLM file storage (kept 24 hours)",
        "writes an MP4 and an optional job checkpoint",
    ]
    user_visible_verification = [
        "Watch the clip (with sound when the model made audio): motion, prompt fidelity, reference fidelity",
        "Confirm data.cost_status is settled and cost_usd matches expectations",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "minLength": 1},
            "operation": {
                "type": "string",
                "enum": list(OPERATIONS) + ["generate"],
                "description": (
                    "Inferred when omitted: reference pictures -> reference_to_video, "
                    "a first frame -> image_to_video, else text_to_video."
                ),
            },
            "model": {
                "type": "string",
                "enum": list(FAMILIES) + list(MODEL_SPECS),
                "default": DEFAULT_FAMILY,
                "description": (
                    "A model family (the operation picks its text, image or reference route) "
                    "or an exact UberLLM model id. See get_info()['model_catalog']."
                ),
            },
            "duration": {
                "type": ["integer", "string"],
                "description": "Whole seconds. Each model offers fixed lengths; omitted: the model's shortest.",
            },
            "resolution": {"type": "string", "description": "e.g. 480p, 720p, 1080p, where the model offers it."},
            "aspect_ratio": {"type": "string", "description": "e.g. 16:9, 9:16, 1:1, where the model offers it."},
            "generate_audio": {
                "type": "boolean",
                "description": "Sound on or off, for models with a sound setting. Kling and Veo add sound unless false.",
            },
            # First frame (image_to_video). The selector-facing names are used on purpose:
            # advertising image_url would make video_selector upload local frames to fal first.
            "reference_image_url": {"type": "string", "description": "First-frame picture, https:// link."},
            "reference_image_path": {"type": "string", "description": "Local first-frame picture; uploaded to UberLLM."},
            # References (reference_to_video).
            "reference_image_urls": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "reference_image_paths": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "provider_params": {
                "type": "object",
                "description": "Extra fields merged into the request verbatim, checked against the model's pinned schema.",
            },
            "max_cost_usd": {
                "type": "number",
                "exclusiveMinimum": 0,
                "description": "Refuse (at no charge) a job that could cost more than this.",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Check the request and return UberLLM's exact quote without generating or charging. "
                    "Local pictures are sent inline for the check and not stored."
                ),
            },
            "output_path": {"type": "string"},
            "job_path": {"type": "string", "description": "Where to persist the job checkpoint for resume."},
            "resume_job": {"type": "object", "description": "Job metadata from a timed-out call; polls without resubmitting."},
            "poll_timeout": {"type": "number", "exclusiveMinimum": 0, "default": 900},
            "poll_interval": {"type": "number", "exclusiveMinimum": 0, "default": 5},
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
            "request": {"type": "object"},
            "usage": {"type": ["object", "null"]},
            "cost_status": {"type": "string", "enum": ["settled", "pending", "quoted"]},
            "estimated_cost_usd": {"type": ["number", "null"]},
            "max_cost_usd": {"type": ["number", "null"]},
            "resume_job": {"type": "object"},
        },
    }

    # ------------------------------------------------------------------
    # Contract access
    # ------------------------------------------------------------------

    @staticmethod
    def base_url() -> str:
        return os.environ.get("UBERLLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["hosting_provider"] = self.provider
        info["model_catalog"] = {
            model_id: {
                "family": spec["family"],
                "operation": spec["operation"],
                "display_name": spec["display_name"],
                "durations": spec["input_schema"]["properties"]["duration_seconds"]["enum"],
                "resolutions": spec["input_schema"]["properties"].get("resolution", {}).get("enum"),
                "aspect_ratios": spec["input_schema"]["properties"].get("aspect_ratio", {}).get("enum"),
                "audio_setting": "audio" in spec["input_schema"]["properties"],
                "usd_per_second": spec["usd_per_second"],
            }
            for model_id, spec in MODEL_SPECS.items()
        }
        info["model_families"] = FAMILIES
        info["billing"] = {
            "model": "bring_your_own_key",
            "prepaid": True,
            "free_tier": False,
            "charged_on": "finished jobs only; failed, canceled and expired jobs cost nothing",
            "prices": "https://uberllm.dev/models",
            "dashboard": "https://uberllm.dev/dashboard",
            "verified_on": _CONTRACT["_about"]["verified_on"],
        }
        return info

    # ------------------------------------------------------------------
    # Estimates
    # ------------------------------------------------------------------

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Resuming a job submits nothing new; the original estimate stands.
        resume_job = inputs.get("resume_job")
        if isinstance(resume_job, dict) and resume_job.get("id"):
            return float(resume_job.get("estimated_cost_usd") or 0.0)
        _, model_id, payload = self._build_request(inputs, {}, mode="estimate")
        return self._estimate_request(model_id, payload)

    @staticmethod
    def _estimate_request(model_id: str, payload: dict[str, Any]) -> float:
        rates = MODEL_SPECS[model_id]["usd_per_second"]
        resolution = payload.get("resolution", "default")
        if resolution not in rates:
            raise PriceQuoteRequired(
                f"No pinned {model_id} rate for {resolution}; set dry_run=true for UberLLM's exact quote"
            )
        return round(rates[resolution] * float(payload["duration_seconds"]), 6)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        try:
            _, _, payload = self._build_request(inputs, {}, mode="estimate")
            seconds = float(payload["duration_seconds"])
        except (ValueError, KeyError):
            seconds = 5.0
        return 60.0 + 12.0 * seconds

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        api_key = os.environ.get("UBERLLM_API_KEY", "").strip()
        if not api_key:
            return ToolResult(success=False, error="UBERLLM_API_KEY not set. " + self.install_instructions)
        headers = {"Authorization": f"Bearer {api_key}"}
        job = dict(inputs.get("resume_job") or {})

        try:
            if not job:
                dry_run = bool(inputs.get("dry_run"))
                operation, model_id, payload = self._build_request(
                    inputs, headers, mode="inline" if dry_run else "upload"
                )
                try:
                    estimate = self._estimate_request(model_id, payload)
                except PriceQuoteRequired:
                    estimate = None
                if inputs.get("max_cost_usd") is not None:
                    payload["max_cost"] = float(inputs["max_cost_usd"])
                if dry_run:
                    quoted = self._request(
                        "POST", f"{self.base_url()}/v1/video/generations",
                        headers={**headers, "Content-Type": "application/json"},
                        json={**payload, "validate": True},
                    )
                    return ToolResult(
                        success=True,
                        data={
                            "provider": self.provider,
                            "model": model_id,
                            "operation": operation,
                            "dry_run": True,
                            "request": self._redact(payload),
                            "quoted_cost_usd": quoted.get("cost_usd"),
                            "max_cost_usd": quoted.get("max_cost_usd"),
                            "defaults_applied": quoted.get("defaults_applied"),
                            "estimated_cost_usd": estimate,
                            "cost_status": "quoted",
                        },
                        cost_usd=0.0,
                        duration_seconds=round(time.time() - started, 2),
                        model=model_id,
                    )
                idempotency_key = str(uuid.uuid4())
                submitted = self._request(
                    "POST", f"{self.base_url()}/v1/video/generations",
                    headers={**headers, "Content-Type": "application/json", "Idempotency-Key": idempotency_key},
                    json=payload,
                )
                if not submitted.get("id"):
                    raise UberLLMAPIError("Submission returned no job id")
                job = {
                    "id": submitted["id"],
                    "tool": self.name,
                    "model": submitted.get("model") or model_id,
                    "operation": operation,
                    "request": payload,
                    "idempotency_key": idempotency_key,
                    "estimated_cost_usd": submitted.get("estimated_cost_usd", estimate),
                    "max_cost_usd": submitted.get("max_cost_usd"),
                    "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                save_job(inputs.get("job_path"), job)

            if job.get("tool") != self.name or not job.get("id"):
                raise ValueError("resume_job does not belong to uberllm_video")

            job_url = f"{self.base_url()}/v1/video/generations/{quote(str(job['id']), safe='')}"

            def fetch() -> dict[str, Any]:
                body = self._request("GET", job_url, headers=headers)
                # provider_jobs.poll keeps waiting on unknown states; "expired" is terminal here.
                if str(body.get("status", "")).lower() == "expired":
                    body = {**body, "status": "failed"}
                return body

            try:
                result = poll(
                    fetch,
                    timeout=float(inputs.get("poll_timeout", 900)),
                    interval=float(inputs.get("poll_interval", 5)),
                )
            except TimeoutError as exc:
                return ToolResult(
                    success=False,
                    error=f"UberLLM job {job['id']} is still running after poll_timeout. {exc}",
                    data={"resume_job": job, "job_id": job["id"], "retryable": True, "provider": self.provider},
                    cost_usd=0.0,
                    duration_seconds=round(time.time() - started, 2),
                    model=job.get("model"),
                )
            except RuntimeError as exc:
                final = self._request("GET", job_url, headers=headers)
                error = final.get("error") or {}
                code = error.get("code") or final.get("status") or "provider_error"
                retryable = error.get("retryable")
                return self._failure(
                    f"UberLLM job {job['id']} ended {final.get('status', 'failed')} ({code}): "
                    f"{error.get('message') or exc}. Nothing was charged. " + _CODE_HINTS.get(code, ""),
                    job=job,
                    code=code,
                    retryable=bool(retryable) if retryable is not None else code in _RETRYABLE_CODES,
                    started=started,
                )

            outputs = result.get("results") or []
            video_url = outputs[0].get("url") if outputs else None
            if not video_url:
                raise ValueError(f"Finished job {job['id']} returned no video URL")
            output_path = Path(inputs.get("output_path") or f"uberllm_{job['id']}.mp4")
            artifact = self._download(video_url, output_path, headers)

            usage, cost_usd, cost_status = self._settle_cost(fetch, result, job.get("estimated_cost_usd"))
            request = job.get("request") or {}
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": result.get("model") or job.get("model"),
                    "operation": job.get("operation"),
                    "job_id": job["id"],
                    "output": artifact,
                    "format": "mp4",
                    "content_type": outputs[0].get("content_type"),
                    "duration_delivered": outputs[0].get("duration_seconds"),
                    "request": self._redact(request),
                    "resolution": request.get("resolution"),
                    "duration_requested": request.get("duration_seconds"),
                    "aspect_ratio": request.get("aspect_ratio"),
                    "usage": usage,
                    "cost_status": cost_status,
                    "estimated_cost_usd": job.get("estimated_cost_usd"),
                    "max_cost_usd": job.get("max_cost_usd"),
                    "resume_job": job,
                },
                artifacts=[artifact],
                cost_usd=cost_usd,
                duration_seconds=round(time.time() - started, 2),
                model=result.get("model") or job.get("model"),
            )
        except UberLLMAPIError as exc:
            hint = _CODE_HINTS.get(exc.code or "", "")
            message = f"UberLLM API error ({exc.code or exc.status}): {exc}. {hint}".strip()
            if exc.retry_after:
                message += f" Retry-After: {exc.retry_after}."
            return self._failure(
                message, job=job, code=exc.code, started=started, retry_after=exc.retry_after,
                retryable=exc.retryable if exc.retryable is not None else exc.code in _RETRYABLE_CODES,
            )
        except Exception as exc:  # validation, upload, download and transport errors
            return self._failure(f"UberLLM video generation failed: {exc}", job=job, started=started)

    # ------------------------------------------------------------------
    # Request building
    # ------------------------------------------------------------------

    def _build_request(self, inputs: dict[str, Any], headers: dict[str, str],
                       *, mode: str) -> tuple[str, str, dict[str, Any]]:
        """mode: "estimate" (no I/O), "inline" (local pictures as data: URIs) or "upload"."""
        operation = self._resolve_operation(inputs)
        model_id = self._resolve_model(str(inputs.get("model") or DEFAULT_FAMILY), operation)
        spec = MODEL_SPECS[model_id]
        props = spec["input_schema"]["properties"]
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError("prompt is required")

        payload: dict[str, Any] = {"model": model_id, "prompt": prompt}
        durations = props["duration_seconds"]["enum"]
        raw_duration = inputs.get("duration")
        payload["duration_seconds"] = durations[0] if raw_duration is None else self._normalize_duration(raw_duration)
        for field, key in (("resolution", "resolution"), ("aspect_ratio", "aspect_ratio"), ("generate_audio", "audio")):
            value = inputs.get(field)
            if value is None:
                continue
            if key not in props:
                raise ValueError(f"{model_id} has no {field} setting; {self._who_offers(key, operation)}")
            payload[key] = value

        if operation == "image_to_video":
            first = self._picture(inputs.get("reference_image_url"), inputs.get("reference_image_path"),
                                  headers, mode, "first frame")
            if not first:
                raise ValueError("image_to_video needs reference_image_url or reference_image_path")
            payload["image_url"] = first
        elif operation == "reference_to_video":
            urls = [str(u) for u in inputs.get("reference_image_urls") or []]
            paths = [str(p) for p in inputs.get("reference_image_paths") or []]
            if not urls and not paths:
                raise ValueError("reference_to_video needs reference_image_urls or reference_image_paths")
            payload["input_images"] = [self._picture(u, None, headers, mode, "reference") for u in urls] + [
                self._picture(None, p, headers, mode, "reference") for p in paths
            ]

        extra = inputs.get("provider_params") or {}
        if not isinstance(extra, dict):
            raise ValueError("provider_params must be an object")
        payload.update(extra)

        # Unknown fields are refused rather than silently ignored by the model.
        Draft202012Validator({**spec["input_schema"], "additionalProperties": False}).validate(payload)
        return operation, model_id, payload

    @staticmethod
    def _resolve_operation(inputs: dict[str, Any]) -> str:
        operation = inputs.get("operation") or inputs.get("generation_mode")
        has_refs = bool(inputs.get("reference_image_urls") or inputs.get("reference_image_paths"))
        has_first = bool(inputs.get("reference_image_url") or inputs.get("reference_image_path"))
        if operation in (None, "", "generate"):
            if has_refs:
                return "reference_to_video"
            return "image_to_video" if has_first else "text_to_video"
        if operation not in OPERATIONS:
            raise ValueError(f"operation must be one of: {', '.join(OPERATIONS)}")
        if operation == "text_to_video" and (has_refs or has_first):
            raise ValueError("text_to_video does not take pictures; use image_to_video or reference_to_video")
        return str(operation)

    @staticmethod
    def _resolve_model(model: str, operation: str) -> str:
        if model in FAMILIES:
            model_id = FAMILIES[model].get(operation)
            if not model_id:
                offered = sorted(f for f, routes in FAMILIES.items() if operation in routes)
                raise ValueError(f"{model} has no {operation} model on UberLLM; families that do: {', '.join(offered)}")
            return model_id
        if model in MODEL_SPECS:
            if MODEL_SPECS[model]["operation"] != operation:
                raise ValueError(f"{model} is a {MODEL_SPECS[model]['operation']} model, not {operation}")
            return model
        raise ValueError(f"Unknown UberLLM video model {model!r}; see get_info()['model_catalog']")

    @staticmethod
    def _who_offers(key: str, operation: str) -> str:
        offered = sorted(
            spec["family"] for spec in MODEL_SPECS.values()
            if spec["operation"] == operation and key in spec["input_schema"]["properties"]
        )
        return f"families that offer it for {operation}: {', '.join(offered) or 'none'}"

    @staticmethod
    def _normalize_duration(raw: Any) -> int:
        text = str(raw).strip().lower().removesuffix("s")
        try:
            value = float(text)
        except ValueError as exc:
            raise ValueError(f"duration must be a whole number of seconds, got {raw!r}") from exc
        if value != int(value):
            raise ValueError("duration must be a whole number of seconds")
        return int(value)

    def _picture(self, url: Any, path: Any, headers: dict[str, str], mode: str, label: str) -> str | None:
        if url:
            url = str(url)
            if not url.startswith("https://"):
                raise ValueError(f"{label} must be an https:// link; pass local files via the *_path input")
            return url
        if not path:
            return None
        local = Path(str(path))
        if mode == "estimate":
            return f"https://dry-run.invalid/{local.name}"
        if not local.is_file():
            raise FileNotFoundError(f"Input file not found: {local}")
        if mode == "inline":
            if local.stat().st_size > MAX_INLINE_BYTES:
                raise ValueError(f"{local.name} is too large to check inline; dry_run with an https:// link instead")
            content_type = mimetypes.guess_type(local.name)[0] or "image/png"
            return f"data:{content_type};base64,{base64.b64encode(local.read_bytes()).decode('ascii')}"
        return self._upload(local, headers)

    @staticmethod
    def _redact(payload: dict[str, Any]) -> dict[str, Any]:
        """Keep inline pictures out of results and checkpoints."""
        def short(value: Any) -> Any:
            return "data:...(inline picture)" if isinstance(value, str) and value.startswith("data:") else value
        out = dict(payload)
        if "image_url" in out:
            out["image_url"] = short(out["image_url"])
        if "input_images" in out:
            out["input_images"] = [short(v) for v in out["input_images"]]
        return out

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @staticmethod
    def _request(method: str, url: str, *, headers: dict[str, str] | None = None, **kwargs: Any) -> dict[str, Any]:
        response = requests.request(method, url, headers=headers, timeout=60, **kwargs)
        try:
            body = response.json()
        except ValueError:
            body = None
        if response.status_code >= 400:
            retry_after = response.headers.get("Retry-After") if response.headers else None
            error = body.get("error") if isinstance(body, dict) else None
            if isinstance(error, dict):
                raise UberLLMAPIError(
                    str(error.get("message") or response.reason or "request failed"),
                    code=error.get("code"), status=response.status_code, retry_after=retry_after,
                    retryable=error.get("retryable"),
                )
            raise UberLLMAPIError(
                str(response.text or response.reason or "request failed"),
                status=response.status_code, retry_after=retry_after,
            )
        if not isinstance(body, dict):
            raise UberLLMAPIError("Unexpected non-JSON response from UberLLM", status=response.status_code)
        return body

    def _upload(self, path: Path, headers: dict[str, str]) -> str:
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        with path.open("rb") as handle:
            body = self._request(
                "POST", f"{self.base_url()}/v1/files", headers=headers,
                files={"file": (path.name, handle, content_type)},
            )
        if not body.get("url"):
            raise UberLLMAPIError(f"Upload of {path.name} returned no url")
        return str(body["url"])

    def _download(self, url: str, path: Path, headers: dict[str, str]) -> str:
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise ValueError("Video output must be an https:// URL")
        # The key goes only to the UberLLM host, never to a third-party link.
        same_host = parsed.netloc == urlparse(self.base_url()).netloc
        response = requests.get(url, headers=headers if same_host else None, timeout=300)
        if response.status_code >= 400:
            raise UberLLMAPIError(f"Download failed with HTTP {response.status_code}", status=response.status_code)
        if not response.content:
            raise ValueError("UberLLM returned an empty video")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".part")
        temp.write_bytes(response.content)
        temp.replace(path)
        return str(path)

    @staticmethod
    def _settle_cost(fetch, result: dict[str, Any], estimate: float | None) -> tuple[dict[str, Any] | None, float | None, str]:
        """The exact charge usually arrives within 30 s of the file; until then report the estimate."""
        usage = result.get("usage")
        for delay in BILLING_SETTLE_DELAYS:
            if usage and usage.get("cost_usd") is not None:
                break
            time.sleep(delay)
            try:
                usage = fetch().get("usage") or usage
            except (UberLLMAPIError, RequestException):
                # The video is already downloaded; only reconciliation is retried, never the paid job.
                continue
        if usage and usage.get("cost_usd") is not None:
            return usage, float(usage["cost_usd"]), "settled"
        return usage, estimate, "pending"

    def _failure(self, message: str, *, job: dict[str, Any], started: float, code: str | None = None,
                 retryable: bool = False, retry_after: str | None = None) -> ToolResult:
        data: dict[str, Any] = {"provider": self.provider, "retryable": retryable}
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
            model=job.get("model") if job else None,
        )
