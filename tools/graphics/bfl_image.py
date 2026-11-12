"""Direct BFL FLUX 3 Image with durable jobs and exact request validation."""

import json
import os
import time
from pathlib import Path
from urllib.parse import urlparse
from jsonschema import validate
from tools.base_tool import (
    BaseTool,
    Determinism,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ResourceProfile,
    ResumeSupport,
    ToolResult,
)
from tools.provider_pricing import PriceQuoteRequired
from tools.provider_jobs import request_json, download, save_job
from tools.schema_media import local_image


class BFLImage(BaseTool):
    determinism = Determinism.STOCHASTIC
    name = "bfl_image"
    provider = "bfl"
    capability = "image_generation"
    tier = ToolTier.GENERATE
    runtime = ToolRuntime.API
    stability = ToolStability.EXPERIMENTAL
    resource_profile = ResourceProfile(network_required=True)
    resume_support = ResumeSupport.FROM_CHECKPOINT
    dependencies = ["env:BFL_API_KEY"]
    install_instructions = "Configure BFL_API_KEY from https://dashboard.bfl.ai/."
    agent_skills = ["provider-refresh-oct23", "bfl-api"]
    capabilities = ["text_to_image", "image_edit", "layout_control"]
    supports = {"image_edit": True, "multiple_reference_images": True}
    contract = json.loads(
        (Path(__file__).parents[1] / "provider_contracts/bfl_flux3.json").read_text()
    )
    input_schema = {
        "type": "object",
        "properties": {
            **contract["properties"],
            "model": {"enum": ["flux-3-image"]},
            "generation_mode": {"enum": ["generate", "edit"]},
            "image_path": {"type": "string"},
            "image_paths": {"type": "array", "items": {"type": "string"}},
            "image_urls": {"type": "array", "items": {"type": "string"}},
            "image_url": {"type": "string"},
            "output_path": {"type": "string"},
            "resume_job": {"type": "object"},
            "job_path": {"type": "string"},
            "poll_timeout": {"type": "number", "exclusiveMinimum": 0},
            "poll_interval": {"type": "number", "exclusiveMinimum": 0},
        },
    }
    idempotency_key_fields = [
        "prompt",
        "images",
        "image_urls",
        "image_paths",
        "image_path",
        "image_url",
        "aspect_ratio",
        "resolution",
        "grounding",
        "version",
    ]
    side_effects = ["submits a paid BFL job", "writes image and resume checkpoint"]

    def __init__(self):
        self.idempotency_key_fields = sorted(
            set(self.input_schema["properties"])
            - {"output_path", "resume_job", "job_path", "poll_timeout", "poll_interval"}
        )

    def get_status(self):
        return (
            ToolStatus.AVAILABLE if os.getenv("BFL_API_KEY") else ToolStatus.UNAVAILABLE
        )

    def estimate_cost(self, inputs):
        raise PriceQuoteRequired("Quote BFL FLUX 3 image pricing for this resolution")

    def build_request(self, inputs):
        validate(inputs, self.input_schema)
        unsupported = set(inputs) & {"seed", "negative_prompt", "input_image"}
        if unsupported:
            raise ValueError(f"FLUX 3 does not accept {sorted(unsupported)}")
        payload = {k: v for k, v in inputs.items() if k in self.contract["properties"]}
        native = payload.get("images")
        images = ([native] if isinstance(native, str) else list(native or [])) + list(
            inputs.get("image_urls") or []
        )
        if inputs.get("image_url"):
            images.append(inputs["image_url"])
        paths = list(inputs.get("image_paths") or [])
        if inputs.get("image_path"):
            paths.insert(0, inputs["image_path"])
        images.extend(local_image(p) for p in paths)
        if len(images) > 10:
            raise ValueError("FLUX 3 supports at most ten references")
        if bool(inputs.get("width")) != bool(inputs.get("height")):
            raise ValueError("Supply width and height together")
        if images:
            payload["images"] = images
        if inputs.get("generation_mode") == "edit" and not images:
            raise ValueError("Edit requires source images")
        validate(payload, self.contract)
        return payload

    def execute(self, inputs):
        job = dict(inputs.get("resume_job") or {})
        try:
            key = os.getenv("BFL_API_KEY")
            if not key:
                raise ValueError(self.install_instructions)
            if not job:
                payload = self.build_request(inputs)
                body = request_json(
                    "POST",
                    "https://api.bfl.ai/v1/flux-3-image",
                    headers={"x-key": key},
                    json=payload,
                )
                job = {
                    "provider": self.provider,
                    "model": "flux-3-image",
                    "id": body["id"],
                    "polling_url": body["polling_url"],
                }
                save_job(inputs.get("job_path"), job)
            if (
                job.get("provider") != self.provider
                or job.get("model") != "flux-3-image"
            ):
                raise ValueError("Resume job provider/model mismatch")
            url = urlparse(job["polling_url"])
            if url.scheme != "https" or not (
                url.hostname == "api.bfl.ai" or (url.hostname or "").endswith(".bfl.ai")
            ):
                raise ValueError("Invalid BFL polling host")
            timeout = float(inputs.get("poll_timeout", 600))
            interval = float(inputs.get("poll_interval", 2))
            if timeout <= 0 or interval <= 0:
                raise ValueError("Polling bounds must be positive")
            deadline = time.monotonic() + timeout
            while True:
                body = request_json("GET", job["polling_url"], headers={"x-key": key})
                status = body.get("status")
                if status == "Ready":
                    break
                if status not in {"Pending", "Reasoning", "Generating"}:
                    raise ValueError(f"BFL job ended with {status}")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Resume this job; do not resubmit")
                time.sleep(min(interval, max(0, deadline - time.monotonic())))
            path = Path(inputs.get("output_path") or "flux3.png")
            download(body["result"]["sample"], path)
            return ToolResult(
                success=True,
                data={
                    "output": str(path),
                    "provider": self.provider,
                    "model": "flux-3-image",
                    "resume_job": job,
                    "cost_status": "unquoted",
                },
                artifacts=[str(path)],
                model="flux-3-image",
                cost_usd=None,
            )
        except Exception as exc:
            return ToolResult(
                success=False, error=str(exc), data={"resume_job": job} if job else {}
            )
