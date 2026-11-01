"""Common file-producing API speech contract; prices require explicit quotes."""

from __future__ import annotations
import json
import os
from pathlib import Path
from abc import abstractmethod
from jsonschema import validate
from tools.base_tool import (
    BaseTool,
    Determinism,
    ToolTier,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
)
from tools.provider_pricing import PriceQuoteRequired


class SpeechAPI(BaseTool):
    determinism = Determinism.STOCHASTIC
    tier = ToolTier.VOICE
    capability = "tts"
    runtime = ToolRuntime.API
    stability = ToolStability.EXPERIMENTAL
    resource_profile = ResourceProfile(network_required=True)
    retry_policy = RetryPolicy(max_retries=0)
    agent_skills = ["provider-refresh-oct23"]
    capabilities = ["text_to_speech"]
    side_effects = ["calls a paid speech API", "writes audio and alignment files"]
    idempotency_key_fields = [
        "text",
        "model",
        "model_id",
        "voice_id",
        "language",
        "output_format",
        "speed",
        "with_timestamps",
    ]

    def __init__(self):
        self.idempotency_key_fields = sorted(
            set(self.input_schema.get("properties", {})) - {"output_path"}
        )

    def get_status(self):
        return (
            ToolStatus.AVAILABLE
            if os.getenv(self.credential)
            else ToolStatus.UNAVAILABLE
        )

    def estimate_cost(self, inputs):
        raise PriceQuoteRequired("Obtain a current account-specific speech quote")

    def execute(self, inputs):
        try:
            validate(inputs, self.input_schema)
            if self.capability in {
                "tts",
                "voice_conversion",
                "music_generation",
            } and inputs.get("output_path"):
                fmt = inputs.get("output_format", "mp3")
                if isinstance(fmt, dict):
                    fmt = fmt.get("codec", "mp3")
                if self.name in {"heygen_tts", "heygen_voice_convert"}:
                    fmt = "wav"
                if (
                    self.name != "heygen_catalog_tts"
                    and Path(inputs["output_path"]).suffix.lower() != "." + fmt
                ):
                    raise ValueError(f"output_path must have .{fmt} extension")
            key = os.getenv(self.credential)
            if not key:
                raise ValueError(self.install_instructions)
            return self.generate(inputs, key)
        except Exception as exc:
            # requests exception text may contain signed URLs; no request body/header logging.
            return ToolResult(
                success=False, error=f"{self.name}: {type(exc).__name__}: {exc}"
            )

    @abstractmethod
    def generate(self, inputs, key):
        pass

    def save_audio(self, inputs, content, *, model, suffix, extra=None, alignment=None):
        if not content:
            raise ValueError("Provider returned empty audio")
        path = Path(inputs.get("output_path") or self.name + suffix)
        if path.suffix.lower() != suffix:
            raise ValueError(f"output_path must have {suffix} extension")
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".part")
        temp.write_bytes(content)
        temp.replace(path)
        artifacts = [str(path)]
        data = {
            "output": str(path),
            "provider": self.provider,
            "model": model,
            "voice_id": inputs.get("voice_id"),
            "cost_status": "unquoted",
            **(extra or {}),
        }
        if alignment is not None:
            sidecar = path.with_name(path.name + ".alignment.json")
            sidecar.write_text(
                json.dumps(alignment, ensure_ascii=False), encoding="utf8"
            )
            artifacts.append(str(sidecar))
            data["alignment_path"] = str(sidecar)
        return ToolResult(
            success=True, data=data, artifacts=artifacts, model=model, cost_usd=None
        )
