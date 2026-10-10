"""Schema-backed fal media jobs with explicit endpoint selection and resume."""

from __future__ import annotations

import json
import os
from abc import abstractmethod
from pathlib import Path
from urllib.parse import urlparse

from jsonschema import Draft202012Validator

from tools.provider_pricing import PriceQuoteRequired

from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    Determinism,
    ResourceProfile,
    ResumeSupport,
    ToolResult,
)
from tools.provider_jobs import request_json, download, poll, save_job

CONTRACTS = json.loads(
    (Path(__file__).parent / "provider_contracts/fal_models.json").read_text(
        encoding="utf-8"
    )
)


class FalMedia(BaseTool):
    provider = "fal.ai"
    runtime = ToolRuntime.API
    tier = ToolTier.GENERATE
    stability = ToolStability.BETA
    determinism = Determinism.STOCHASTIC
    dependencies = ["env:FAL_KEY"]
    install_instructions = "Configure FAL_KEY using https://fal.ai/dashboard/keys."
    resource_profile = ResourceProfile(network_required=True)
    resume_support = ResumeSupport.FROM_CHECKPOINT
    agent_skills = ["provider-model-refresh"]
    side_effects = [
        "submits a paid fal job",
        "writes media and optional job checkpoint",
    ]
    user_visible_verification = ["Inspect generated media and provider provenance"]
    idempotency_key_fields = [
        "model",
        "operation",
        "generation_mode",
        "prompt",
        "image_urls",
        "mask_url",
        "seed",
        "duration",
        "resolution",
        "provider_params",
    ]

    @property
    @abstractmethod
    def routes(self):
        """Map public model names to operation -> exact fal endpoint."""

    def __init__(self):
        models = list(self.routes)
        props = {}
        for routes in self.routes.values():
            for endpoint in routes.values():
                props.update(CONTRACTS[endpoint]["input_schema"]["properties"])
        # Full endpoint-specific validation happens before submitting a job.
        props = {
            key: {"description": value.get("description", key)}
            for key, value in props.items()
        }
        props.update(
            {
                "model": {"type": "string", "enum": models, "default": models[0]},
                "operation": {"type": "string"},
                "generation_mode": {"type": "string"},
                "image_url": {"type": "string"},
                "image_path": {"type": "string"},
                "mask_path": {"type": "string"},
                "image_paths": {"type": "array", "items": {"type": "string"}},
                "provider_params": {"type": "object"},
                "resume_job": {"type": "object"},
                "job_path": {"type": "string"},
                "output_path": {"type": "string"},
                "poll_timeout": {"type": "number", "exclusiveMinimum": 0},
                "poll_interval": {"type": "number", "exclusiveMinimum": 0},
            }
        )
        self.input_schema = {"type": "object", "properties": props}
        self.idempotency_key_fields = sorted(
            set(props)
            - {"resume_job", "job_path", "output_path", "poll_timeout", "poll_interval"}
        )

    def get_status(self):
        return (
            ToolStatus.AVAILABLE
            if os.getenv("FAL_KEY") or os.getenv("FAL_AI_API_KEY")
            else ToolStatus.UNAVAILABLE
        )

    def get_info(self):
        info = super().get_info()
        info["hosting_provider"] = "fal.ai"
        info["model_catalog"] = {
            m: {
                "routes": r,
                "verified_on": "2026-10-03",
                "pricing_status": "quote_required",
            }
            for m, r in self.routes.items()
        }
        return info

    def estimate_cost(self, inputs):
        # No fabricated per-image/per-second rates. Callers must obtain a quote.
        raise PriceQuoteRequired(
            "A current fal price quote is required for this model/operation"
        )

    def build_request(self, inputs):
        model = inputs.get("model", next(iter(self.routes)))
        references = any(
            inputs.get(k)
            for k in ("image_path", "image_paths", "image_url", "image_urls")
        )
        operation = (
            inputs.get("generation_mode")
            or inputs.get("operation")
            or (
                "edit"
                if references and self.capability == "image_generation"
                else "image_to_video"
                if references
                else next(iter(self.routes.get(model, {})), "")
            )
        )
        if operation == "generate":
            operation = (
                "generate"
                if "generate" in self.routes.get(model, {})
                else "text_to_video"
            )
        endpoint = self.routes.get(model, {}).get(operation)
        if not endpoint:
            raise ValueError(f"Unsupported model/operation: {model}/{operation}")
        schema = CONTRACTS[endpoint]["input_schema"]
        props = schema["properties"]
        payload = {k: v for k, v in inputs.items() if k in props}
        native = inputs.get("provider_params", {})
        if not isinstance(native, dict):
            raise ValueError("provider_params must be an object")
        payload.update(native)
        if "prompt_expansion_mode" in props:
            payload.setdefault("prompt_expansion_mode", "balanced")
        if inputs.get("image_url") and "start_image_url" in props:
            payload["start_image_url"] = inputs["image_url"]
        if inputs.get("image_url") and "image_urls" in props:
            payload["image_urls"] = [
                inputs["image_url"],
                *payload.get("image_urls", []),
            ]
        if inputs.get("mask_path"):
            if "mask_url" not in props:
                raise ValueError(f"{endpoint} does not accept a mask")
            from tools.schema_media import local_image

            payload["mask_url"] = local_image(inputs["mask_path"])
        paths = list(inputs.get("image_paths") or [])
        if inputs.get("image_path"):
            paths.insert(0, inputs["image_path"])
        if paths:
            import mimetypes, base64

            refs = [
                "data:"
                + (mimetypes.guess_type(p)[0] or "image/png")
                + ";base64,"
                + base64.b64encode(Path(p).read_bytes()).decode()
                for p in paths
            ]
            if "image_urls" in props:
                payload["image_urls"] = list(payload.get("image_urls") or []) + refs
            elif len(refs) == 1 and (
                "image_url" in props or "start_image_url" in props
            ):
                if payload.get("image_url") or payload.get("start_image_url"):
                    raise ValueError(
                        "This route accepts one source image; do not combine URL and local path"
                    )
                payload[
                    "start_image_url" if "start_image_url" in props else "image_url"
                ] = refs[0]
            else:
                raise ValueError("This route does not support the supplied image paths")
        if inputs.get("generate_audio") is not None and "audio" in props:
            payload["audio"] = inputs["generate_audio"]
        if inputs.get("n") is not None and "num_images" in props:
            payload["num_images"] = inputs["n"]
        if operation == "precise_edit":
            payload["edit_precision"] = "high"
        for key in (
            "image_url",
            "image_urls",
            "mask_url",
            "reference_image_urls",
            "reference_video_urls",
            "reference_audio_urls",
            "target_audio_url",
        ):
            if (
                inputs.get(key)
                and key not in props
                and not (
                    key == "image_url"
                    and ("start_image_url" in props or "image_urls" in props)
                )
            ):
                raise ValueError(f"{endpoint} does not accept {key}")
        Draft202012Validator(schema).validate(payload)
        if payload.get("mask_url") and len(payload.get("reference_image_urls", [])) > 3:
            raise ValueError(
                "Masked Ideogram edits allow at most three reference images"
            )
        if (payload.get("web_url") or payload.get("file_url")) and not payload.get(
            "enable_thinking"
        ):
            raise ValueError("web_url/file_url requires enable_thinking")
        return model, operation, endpoint, payload

    def execute(self, inputs):
        job = dict(inputs.get("resume_job") or {})
        try:
            key = os.getenv("FAL_KEY") or os.getenv("FAL_AI_API_KEY")
            if not key:
                raise ValueError("FAL_KEY is not configured")
            headers = {"Authorization": f"Key {key}"}
            if not job:
                model, operation, endpoint, payload = self.build_request(inputs)
                submitted = request_json(
                    "POST",
                    f"https://queue.fal.run/{endpoint}",
                    headers=headers,
                    json=payload,
                )
                job = {
                    k: submitted[k]
                    for k in ("request_id", "status_url", "response_url")
                }
                job.update(
                    model=model, operation=operation, endpoint=endpoint, tool=self.name
                )
                save_job(inputs.get("job_path"), job)
            if job.get("tool") != self.name or self.routes.get(
                job.get("model"), {}
            ).get(job.get("operation")) != job.get("endpoint"):
                raise ValueError("Resume job belongs to a different tool or endpoint")
            for field in ("status_url", "response_url"):
                parsed = urlparse(job[field])
                if parsed.scheme != "https" or parsed.netloc != "queue.fal.run":
                    raise ValueError("Invalid fal job URL")
            poll(
                lambda: request_json("GET", job["status_url"], headers=headers),
                timeout=float(inputs.get("poll_timeout", 600)),
                interval=float(inputs.get("poll_interval", 2)),
            )
            result = request_json("GET", job["response_url"], headers=headers)
            values = result.get("images") or (
                [result["video"]]
                if result.get("video")
                else [result["audio"]]
                if result.get("audio")
                else []
            )
            if not values:
                raise ValueError("Completed job returned no media")
            ext = (
                ".mp4"
                if self.capability == "video_generation"
                else "." + inputs.get("output_format", "png")
            )
            path = Path(inputs.get("output_path") or self.name + ext)
            outputs = [
                download(
                    v["url"],
                    path
                    if i == 0
                    else path.with_name(f"{path.stem}_{i + 1}{path.suffix}"),
                )
                for i, v in enumerate(values)
            ]
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "hosting_provider": "fal.ai",
                    "model": job["model"],
                    "operation": job["operation"],
                    "output": outputs[0],
                    "outputs": outputs,
                    "resume_job": job,
                    "cost_status": "unquoted",
                    "provider_result": result,
                },
                artifacts=outputs,
                cost_usd=None,
                model=job["model"],
            )
        except Exception as exc:
            return ToolResult(
                success=False, error=str(exc), data={"resume_job": job} if job else {}
            )
