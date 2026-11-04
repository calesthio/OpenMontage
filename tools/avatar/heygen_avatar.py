"""HeyGen v3 Avatar V digital twins with eligibility checks and resumable jobs."""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from tools.provider_pricing import PriceQuoteRequired

from tools.base_tool import (
    BaseTool,
    ToolTier,
    ToolRuntime,
    ToolStability,
    Determinism,
    ResourceProfile,
    ResumeSupport,
    ToolResult,
)
from tools.provider_jobs import request_json, download, poll, save_job

BASE = "https://api.heygen.com/v3"


class HeyGenAvatar(BaseTool):
    name = "heygen_avatar"
    capability = "avatar"
    provider = "heygen"
    tier = ToolTier.GENERATE
    runtime = ToolRuntime.API
    stability = ToolStability.BETA
    determinism = Determinism.STOCHASTIC
    dependencies = ["env:HEYGEN_API_KEY"]
    install_instructions = "Configure HEYGEN_API_KEY from your HeyGen API account."
    agent_skills = ["provider-model-refresh"]
    capabilities = [
        "avatar_video",
        "audio_to_video",
        "list_looks",
        "inspect_look",
        "resume",
    ]
    supports = {
        "avatar_v": True,
        "script": True,
        "audio_url": True,
        "motion_prompt": True,
        "eligibility_preflight": True,
    }
    best_for = ["Avatar V digital-twin presenters with explicit engine selection"]
    resource_profile = ResourceProfile(network_required=True)
    resume_support = ResumeSupport.FROM_CHECKPOINT
    side_effects = [
        "submits paid HeyGen video generation",
        "writes video and optional job checkpoint",
    ]
    user_visible_verification = [
        "Review presenter identity, lip sync, motion and voice"
    ]
    idempotency_key_fields = [
        "avatar_id",
        "script",
        "voice_id",
        "audio_url",
        "audio_asset_id",
        "engine",
        "motion_prompt",
        "reference_look_id",
        "resolution",
        "aspect_ratio",
    ]
    input_schema = {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["generate", "list_looks", "inspect_look", "resume"],
                "default": "generate",
            },
            "avatar_id": {"type": "string"},
            "script": {"type": "string"},
            "voice_id": {"type": "string"},
            "audio_url": {"type": "string"},
            "audio_asset_id": {"type": "string"},
            "engine": {
                "type": "string",
                "enum": ["avatar_v", "avatar_iv"],
                "default": "avatar_v",
            },
            "motion_prompt": {"type": "string"},
            "reference_look_id": {"type": "string"},
            "resolution": {
                "type": "string",
                "enum": ["720p", "1080p", "4k"],
                "default": "1080p",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["auto", "16:9", "9:16", "4:5", "5:4", "1:1"],
                "default": "auto",
            },
            "output_format": {
                "type": "string",
                "enum": ["mp4", "webm"],
                "default": "mp4",
            },
            "remove_background": {"type": "boolean"},
            "title": {"type": "string"},
            "resume_job": {"type": "object"},
            "job_path": {"type": "string"},
            "output_path": {"type": "string"},
            "poll_timeout": {"type": "number", "exclusiveMinimum": 0},
            "poll_interval": {"type": "number", "exclusiveMinimum": 0},
            "token": {"type": "string"},
        },
    }

    def estimate_cost(self, inputs):
        if inputs.get("operation") in {"list_looks", "inspect_look"}:
            return 0.0
        raise PriceQuoteRequired(
            "Quote HeyGen account pricing and expected duration before generation"
        )

    @staticmethod
    def build_payload(inputs):
        from jsonschema import validate

        validate(inputs, HeyGenAvatar.input_schema)
        if not inputs.get("avatar_id"):
            raise ValueError("avatar_id must identify an existing look")
        sources = [
            k for k in ("script", "audio_url", "audio_asset_id") if inputs.get(k)
        ]
        if len(sources) != 1:
            raise ValueError("Provide exactly one of script, audio_url, audio_asset_id")
        if sources == ["script"] and not inputs.get("voice_id"):
            raise ValueError("Script generation requires voice_id")
        if sources != ["script"] and inputs.get("voice_id"):
            raise ValueError("voice_id is only used with script")
        engine = inputs.get("engine", "avatar_v")
        if inputs.get("reference_look_id") and engine != "avatar_v":
            raise ValueError("reference_look_id requires Avatar V")
        payload = {
            "type": "avatar",
            "avatar_id": inputs["avatar_id"],
            "engine": {"type": engine},
            "resolution": inputs.get("resolution", "1080p"),
            "aspect_ratio": inputs.get("aspect_ratio", "auto"),
        }
        for k in (
            "script",
            "voice_id",
            "audio_url",
            "audio_asset_id",
            "motion_prompt",
            "reference_look_id",
            "title",
            "output_format",
            "remove_background",
        ):
            if k in inputs:
                payload[k] = inputs[k]
        return payload

    def execute(self, inputs):
        job = dict(inputs.get("resume_job") or {})
        try:
            key = os.getenv("HEYGEN_API_KEY")
            if not key:
                raise ValueError("HEYGEN_API_KEY is not configured")
            headers = {"x-api-key": key}

            def get(path, **kwargs):
                return request_json("GET", BASE + path, headers=headers, **kwargs).get(
                    "data", {}
                )

            operation = inputs.get("operation", "generate")
            if operation == "list_looks":
                params = {"token": inputs["token"]} if inputs.get("token") else {}
                return ToolResult(
                    success=True, data=get("/avatars/looks", params=params)
                )
            if operation == "inspect_look":
                return ToolResult(
                    success=True,
                    data=get("/avatars/looks/" + quote(inputs["avatar_id"], safe="")),
                )
            if operation not in {"generate", "resume"}:
                raise ValueError("Unknown avatar operation")
            if operation == "resume" and not job:
                raise ValueError(
                    "resume requires resume_job from the original submission"
                )
            if not job:
                payload = self.build_payload(inputs)
                look = get("/avatars/looks/" + quote(inputs["avatar_id"], safe=""))
                engine = payload["engine"]["type"]
                if engine not in look.get("supported_api_engines", []):
                    raise ValueError(
                        f"Look does not support {engine}; no engine fallback was performed"
                    )
                if engine == "avatar_v" and look.get("avatar_type") != "digital_twin":
                    raise ValueError("Avatar V requires an eligible digital_twin look")
                if inputs.get("reference_look_id"):
                    reference = get(
                        "/avatars/looks/" + quote(inputs["reference_look_id"], safe="")
                    )
                    group = look.get("group_id") or look.get("avatar_group_id")
                    reference_group = reference.get("group_id") or reference.get(
                        "avatar_group_id"
                    )
                    if (
                        not group
                        or group != reference_group
                        or reference.get("avatar_type") != "digital_twin"
                    ):
                        raise ValueError(
                            "Reference look must be a digital twin in the same verified avatar group"
                        )
                result = request_json(
                    "POST", BASE + "/videos", headers=headers, json=payload
                )["data"]
                job = {
                    "video_id": result["video_id"],
                    "tool": self.name,
                    "model": engine,
                    "output_format": inputs.get("output_format", "mp4"),
                }
                save_job(inputs.get("job_path"), job)
            if job.get("tool") != self.name or job.get("model") not in {
                "avatar_v",
                "avatar_iv",
            }:
                raise ValueError("Invalid HeyGen resume job")
            result = poll(
                lambda: get("/videos/" + quote(job["video_id"], safe="")),
                timeout=float(inputs.get("poll_timeout", 900)),
                interval=float(inputs.get("poll_interval", 3)),
            )
            path = Path(
                inputs.get("output_path")
                or f"heygen_avatar.{job.get('output_format', 'mp4')}"
            )
            output = download(result["video_url"], path)
            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": job["model"],
                    "output": output,
                    "output_path": output,
                    "resume_job": job,
                    "cost_status": "unquoted",
                    "duration_seconds": result.get("duration"),
                    "subtitle_url": result.get("subtitle_url"),
                },
                artifacts=[output],
                cost_usd=None,
                model=job["model"],
            )
        except Exception as exc:
            return ToolResult(
                success=False, error=str(exc), data={"resume_job": job} if job else {}
            )
