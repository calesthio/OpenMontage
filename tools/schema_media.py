"""Schema-validated Atlas, Replicate and LTX jobs with durable resume metadata."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from abc import abstractmethod
from pathlib import Path
from urllib.parse import quote

from jsonschema import Draft202012Validator
from tools.provider_pricing import PriceQuoteRequired

from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ResourceProfile,
    ResumeSupport,
    ToolResult,
)
from tools.provider_jobs import request_json, download, poll, save_job


def local_image(path):
    return (
        "data:"
        + (mimetypes.guess_type(path)[0] or "image/png")
        + ";base64,"
        + base64.b64encode(Path(path).read_bytes()).decode()
    )


class SchemaMedia(BaseTool):
    tier = ToolTier.GENERATE
    runtime = ToolRuntime.API
    stability = ToolStability.BETA
    resource_profile = ResourceProfile(network_required=True)
    resume_support = ResumeSupport.FROM_CHECKPOINT
    agent_skills = ["provider-model-refresh"]
    side_effects = [
        "submits a paid generation job",
        "writes media and optional resume checkpoint",
    ]
    idempotency_key_fields = [
        "model",
        "operation",
        "generation_mode",
        "prompt",
        "provider_params",
        "image_url",
        "image_paths",
        "duration",
        "resolution",
        "seed",
    ]

    @property
    @abstractmethod
    def catalog_file(self):
        """Checked-in schema file name."""

    def __init__(self):
        self.contracts = json.loads(
            (
                Path(__file__).parent / "provider_contracts" / self.catalog_file
            ).read_text(encoding="utf8")
        )
        props = {}
        for endpoint in self.endpoints:
            for name, spec in self.contracts[endpoint]["input_schema"][
                "properties"
            ].items():
                # Public union is intentionally permissive; selected route is validated fully.
                props[name] = {"description": spec.get("description", name)}
        props.update(
            {
                "model": {
                    "type": "string",
                    "enum": list(self.models),
                    "default": next(iter(self.models)),
                },
                "operation": {"type": "string"},
                "generation_mode": {"type": "string"},
                "image_url": {"type": "string"},
                "image_path": {"type": "string"},
                "image_urls": {"type": "array", "items": {"type": "string"}},
                "image_paths": {"type": "array", "items": {"type": "string"}},
                "mask_url": {"type": "string"},
                "mask_path": {"type": "string"},
                "aspect_ratio": {"type": "string"},
                "generate_audio": {"type": "boolean"},
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

    @property
    def endpoints(self):
        return {
            endpoint for routes in self.models.values() for endpoint in routes.values()
        }

    def get_info(self):
        info = super().get_info()
        info["hosting_provider"] = self.provider
        info["model_catalog"] = {
            model: {
                "routes": routes,
                "verified_on": "2026-10-03",
                "pricing_status": "quote_required",
            }
            for model, routes in self.models.items()
        }
        return info

    def estimate_cost(self, inputs):
        raise PriceQuoteRequired(
            "Obtain a current price quote for this model, operation and resolution"
        )

    def build_request(self, inputs):
        model = inputs.get("model", next(iter(self.models)))
        routes = self.models.get(model, {})
        references = bool(
            inputs.get("image_url")
            or inputs.get("image_path")
            or inputs.get("image_urls")
            or inputs.get("image_paths")
        )
        operation = (
            inputs.get("generation_mode")
            or inputs.get("operation")
            or (
                "edit"
                if references and self.capability == "image_generation"
                else "image_to_video"
                if references
                else next(iter(routes), "")
            )
        )
        if operation == "generate" and self.capability == "video_generation":
            operation = "text_to_video"
        endpoint = routes.get(operation)
        if not endpoint:
            raise ValueError(f"Unsupported model/operation: {model}/{operation}")
        schema = self.contracts[endpoint]["input_schema"]
        props = schema["properties"]
        payload = {k: v for k, v in inputs.items() if k in props and k != "model"}
        payload.update(inputs.get("provider_params") or {})
        if self.provider == "atlascloud":
            payload["model"] = endpoint
        if self.provider == "ltx":
            payload["model"] = model
        aliases = (
            {"mask_url": "mask", "generate_audio": "audio", "aspect_ratio": "ratio"}
            if self.provider == "atlascloud"
            else {}
        )
        for public, native in aliases.items():
            if public in inputs:
                if public in props:
                    continue
                if native not in props:
                    raise ValueError(f"{endpoint} does not support {public}")
                payload[native] = inputs[public]
        if inputs.get("mask_path"):
            if "mask" not in props:
                raise ValueError(f"{endpoint} does not accept a mask")
            payload["mask"] = local_image(inputs["mask_path"])
        refs = list(inputs.get("image_urls") or [])
        if inputs.get("image_url"):
            refs.insert(0, inputs["image_url"])
        paths = list(inputs.get("image_paths") or [])
        if inputs.get("image_path"):
            paths.insert(0, inputs["image_path"])
        refs.extend(local_image(p) for p in paths)
        if refs:
            target = (
                "images"
                if "images" in props
                else "image_input"
                if "image_input" in props
                else "image"
                if "image" in props
                else "image_uri"
                if "image_uri" in props
                else None
            )
            if not target:
                raise ValueError(f"{endpoint} does not accept source images")
            if target in {"images", "image_input"}:
                payload[target] = list(payload.get(target) or []) + refs
            elif len(refs) == 1:
                if payload.get(target):
                    raise ValueError("Specify the source image only once")
                payload[target] = refs[0]
            else:
                raise ValueError("This route takes exactly one source image")
        for field in (
            "reference_image_urls",
            "reference_video_urls",
            "reference_audio_urls",
            "mask_url",
            "last_image",
            "last_frame_uri",
        ):
            if inputs.get(field) and field not in props and field not in aliases:
                raise ValueError(
                    f"{endpoint} does not support {field}; use its documented provider_params"
                )
        if self.provider == "replicate" and "allow_fallback_model" in props:
            if payload.get("allow_fallback_model"):
                raise ValueError(
                    "Model fallback is disabled; select the alternate model explicitly"
                )
            payload["allow_fallback_model"] = False
            if len(payload.get("image_input", [])) > 14:
                raise ValueError("At most 14 reference images")
        if (
            self.provider == "replicate"
            and operation == "image_to_video"
            and not payload.get("image")
        ):
            raise ValueError("image_to_video requires an image")
        if (
            self.provider == "replicate"
            and operation == "text_to_video"
            and payload.get("image")
        ):
            raise ValueError("Use image_to_video with a source image")
        if self.provider == "ltx":
            self.validate_ltx(payload, operation)
        Draft202012Validator(schema).validate(payload)
        return model, operation, endpoint, payload

    @staticmethod
    def validate_ltx(payload, operation):
        resolutions = {
            "1280x720",
            "720x1280",
            "1920x1080",
            "1080x1920",
            "2560x1440",
            "1440x2560",
            "3840x2160",
            "2160x3840",
        }
        if payload.get("resolution") not in resolutions:
            raise ValueError("Unsupported LTX-2.5 resolution")
        fps = payload.get("fps", 24)
        if fps not in {24, 25, 48, 50}:
            raise ValueError("LTX-2.5 supports 24, 25, 48 or 50 FPS")
        if operation != "audio_to_video":
            duration = payload.get("duration")
            max_duration = (
                20
                if payload["model"] == "ltx-2-5-fast"
                and fps in {24, 25}
                and payload["resolution"]
                in {"1280x720", "720x1280", "1920x1080", "1080x1920"}
                else 10
            )
            if duration is not None and duration not in range(6, max_duration + 1, 2):
                raise ValueError("Unsupported LTX duration for model/resolution/FPS")
            if duration is None and payload.get("last_frame_uri"):
                raise ValueError("Automatic duration cannot use a last frame")

    def execute(self, inputs):
        job = dict(inputs.get("resume_job") or {})
        try:
            key = os.environ[self.credential]
            headers = {"Authorization": f"Bearer {key}"}
            if not job:
                model, operation, endpoint, payload = self.build_request(inputs)
                if self.provider == "atlascloud":
                    action = (
                        "generateVideo"
                        if self.capability == "video_generation"
                        else "generateImage"
                    )
                    submitted = request_json(
                        "POST",
                        "https://api.atlascloud.ai/api/v1/model/" + action,
                        headers=headers,
                        json=payload,
                    )["data"]
                elif self.provider == "replicate":
                    submitted = request_json(
                        "POST",
                        "https://api.replicate.com/v1/models/"
                        + endpoint
                        + "/predictions",
                        headers=headers,
                        json={"input": payload},
                    )
                else:
                    submitted = request_json(
                        "POST",
                        "https://api.ltx.io/v2/" + endpoint,
                        headers=headers,
                        json=payload,
                    )
                job = {
                    "id": submitted["id"],
                    "model": model,
                    "operation": operation,
                    "endpoint": endpoint,
                    "tool": self.name,
                    "output_format": payload.get("output_format"),
                }
                save_job(inputs.get("job_path"), job)
            if job.get("tool") != self.name or self.models.get(
                job.get("model"), {}
            ).get(job.get("operation")) != job.get("endpoint"):
                raise ValueError("Resume job does not match this tool and route")
            identifier = quote(str(job["id"]), safe="")
            if self.provider == "atlascloud":
                url = "https://api.atlascloud.ai/api/v1/model/prediction/" + identifier
            elif self.provider == "replicate":
                url = "https://api.replicate.com/v1/predictions/" + identifier
            else:
                url = "https://api.ltx.io/v2/" + job["endpoint"] + "/" + identifier

            def fetch():
                response = request_json("GET", url, headers=headers)
                return response["data"] if self.provider == "atlascloud" else response

            result = poll(
                fetch,
                timeout=float(inputs.get("poll_timeout", 900)),
                interval=float(inputs.get("poll_interval", 2)),
            )
            values = (
                result.get("outputs")
                if self.provider == "atlascloud"
                else result.get("output")
                if self.provider == "replicate"
                else result.get("result", {}).get("video_url")
            )
            if isinstance(values, str):
                values = [values]
            if not values:
                raise ValueError("Completed job returned no media")
            ext = (
                "mp4"
                if self.capability == "video_generation"
                else job.get("output_format")
                or ("jpg" if self.provider == "replicate" else "png")
            )
            path = Path(inputs.get("output_path") or self.name + "." + ext)
            outputs = [
                download(
                    value,
                    path
                    if i == 0
                    else path.with_name(f"{path.stem}_{i + 1}{path.suffix}"),
                )
                for i, value in enumerate(values)
            ]
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
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
