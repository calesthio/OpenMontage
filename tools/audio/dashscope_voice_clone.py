"""DashScope (Alibaba Cloud Bailian) voice cloning via the voice-enrollment API.

Creates reusable, account-scoped voice IDs from a reference recording so that
`dashscope_tts` can narrate with a real cloned voice. The enrollment API is
*not* the same endpoint as synthesis:

    POST {base}/services/audio/tts/customization   (create/query/list/delete)
    model: "voice-enrollment"

Reference audio may be a public URL, an ``http(s)`` link, or a local file
(WAV / MP3 / M4A), which is inlined as a Base64 Data URI. Voices are bound to
the ``target_model`` they were enrolled with — synthesizing with any other
model fails, so `dashscope_tts` infers the model from the voice ID.

Documents: https://help.aliyun.com/zh/model-studio/voice-clone-design-http-api
"""

from __future__ import annotations

import base64
import os
import re
import time
from datetime import datetime
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

MIB = 1024 * 1024

# Target models that accept a cloned voice. The clone is bound to whichever
# model is chosen at enrollment time.
CLONED_VOICE_MODELS = [
    "qwen-audio-3.1-tts-flash",
    "qwen-audio-3.1-tts-plus",
    "qwen-audio-3.0-tts-flash",
    "qwen-audio-3.0-tts-plus",
    "cosyvoice-v3.5-flash",
    "cosyvoice-v3.5-plus",
    "cosyvoice-v3-flash",
    "cosyvoice-v3-plus",
    "cosyvoice-v2",
]

MIME_BY_SUFFIX = {
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
}

# Enrollment accepts 10-20 s clips (60 s hard ceiling); anything shorter than
# 5 s cannot contain the required stretch of continuous speech.
MIN_REFERENCE_SECONDS = 5.0
MAX_REFERENCE_SECONDS = 60.0
MAX_REFERENCE_BYTES = 10 * MIB


class DashscopeVoiceClone(BaseTool):
    name = "dashscope_voice_clone"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "voice_cloning"
    provider = "dashscope"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set DASHSCOPE_API_KEY to your Alibaba Cloud DashScope API key.\n"
        "  Get one at https://dashscope.aliyun.com/\n"
        "Clone jobs use the public endpoint by default; set "
        "DASHSCOPE_WORKSPACE_ID (or pass workspace_id) to use your "
        "workspace-specific domain instead."
    )
    # Degraded path when enrollment is blocked: create the clone in another
    # provider's dashboard and synthesize by voice_id there.
    fallback = "elevenlabs_tts"
    fallback_tools = ["elevenlabs_tts", "fish_audio_tts"]
    agent_skills = ["dashscope"]

    capabilities = [
        "create_voice",
        "query_voice",
        "list_voices",
        "delete_voice",
        "voice_cloning",
    ]
    supports = {
        "voice_cloning": True,
        "reference_audio": True,
        "multilingual": True,
        "offline": False,
    }
    best_for = [
        "reusing one narrator voice across an entire production run",
        "brand or presenter voices cloned from a short reference recording",
        "Mandarin narration that must match a supplied sample",
    ]
    not_good_for = [
        "fully offline production",
        "singing or music reference audio",
        "cross-model reuse (a clone only works with its target_model)",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["create", "query", "list", "delete"],
                "description": (
                    "'create' enrolls a voice from reference_audio; 'query' "
                    "checks one voice_id; 'list' pages through voices; "
                    "'delete' frees a voice slot."
                ),
            },
            "reference_audio": {
                "type": "string",
                "description": (
                    "Local path (.wav/.mp3/.m4a, <=10 MB, 10-20 s recommended) "
                    "or a public http(s) URL. Required for 'create'."
                ),
            },
            "target_model": {
                "type": "string",
                "enum": CLONED_VOICE_MODELS,
                "default": "qwen-audio-3.1-tts-flash",
                "description": (
                    "Model that will speak with this voice. The clone cannot "
                    "be used with a different model."
                ),
            },
            "prefix": {
                "type": "string",
                "description": (
                    "Voice name prefix, letters/digits only, max 10 chars. "
                    "Final ID looks like {target_model}-{prefix}-{hash}."
                ),
            },
            "language_hints": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "One language hint for the sample, e.g. [\"zh\"] or "
                    "[\"en\"]. Ignored if it does not match the audio."
                ),
            },
            "enable_preprocess": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Denoise / enhance the reference. Enable for noisy "
                    "recordings; keep off for clean studio takes."
                ),
            },
            "enable_volume_normalization": {
                "type": "boolean",
                "default": False,
                "description": "Normalize reference loudness before enrollment.",
            },
            "max_prompt_audio_length": {
                "type": "number",
                "minimum": 3.0,
                "maximum": 30.0,
                "default": 20.0,
                "description": (
                    "Seconds of the reference used for enrollment. More audio "
                    "usually improves similarity."
                ),
            },
            "voice_id": {
                "type": "string",
                "description": "Voice to query or delete.",
            },
            "page_index": {"type": "integer", "minimum": 0, "default": 0},
            "page_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 20,
            },
            "workspace_id": {
                "type": "string",
                "description": (
                    "Bailian workspace ID. Overrides DASHSCOPE_WORKSPACE_ID; "
                    "switches the call to the workspace-specific domain."
                ),
            },
            "base_url": {
                "type": "string",
                "description": (
                    "Full API base override, e.g. "
                    "https://<workspace>.cn-beijing.maas.aliyuncs.com/api/v1"
                ),
            },
            "wait_for_ready": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Poll until the voice leaves DEPLOYING. Audit usually "
                    "finishes in a few seconds."
                ),
            },
            "timeout_seconds": {
                "type": "number",
                "minimum": 10,
                "default": 180,
            },
            "poll_interval_seconds": {
                "type": "number",
                "minimum": 1,
                "default": 3,
            },
            "output_path": {
                "type": "string",
                "description": (
                    "Optional path for a JSON record of the enrollment "
                    "(voice_id, target_model, reference metadata) so later "
                    "stages can reuse the voice."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=20, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2, retryable_errors=["rate_limit", "timeout"]
    )
    idempotency_key_fields = [
        "operation",
        "voice_id",
        "target_model",
        "prefix",
        "reference_audio",
        "language_hints",
        "enable_preprocess",
        "enable_volume_normalization",
        "max_prompt_audio_length",
    ]
    side_effects = [
        "creates, updates, or deletes an account-scoped DashScope voice",
        "optionally writes an enrollment JSON record to output_path",
        "calls the DashScope (Alibaba Cloud) voice-enrollment API",
    ]
    user_visible_verification = [
        "Listen to a short synthesized sample before committing to full narration",
    ]

    PUBLIC_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1"
    WORKSPACE_DOMAIN = "https://{workspace_id}.cn-beijing.maas.aliyuncs.com/api/v1"
    CUSTOMIZATION_PATH = "/services/audio/tts/customization"

    # ------------------------------------------------------------------
    # Status / cost
    # ------------------------------------------------------------------

    def get_status(self) -> ToolStatus:
        if os.environ.get("DASHSCOPE_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Enrollment, query, list and delete are free; only synthesis bills.
        return 0.0

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY not set. " + self.install_instructions,
            )

        operation = str(inputs.get("operation") or "").strip().lower()
        if operation not in {"create", "query", "list", "delete"}:
            return ToolResult(
                success=False,
                error=(
                    "operation must be one of: create, query, list, delete "
                    f"(got {operation!r})"
                ),
            )

        try:
            if operation == "create":
                return self._create(inputs, api_key)
            if operation == "query":
                return self._query(inputs, api_key)
            if operation == "delete":
                return self._delete(inputs, api_key)
            return self._list(inputs, api_key)
        except ValueError as e:
            return ToolResult(success=False, error=str(e))
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"DashScope voice {operation} failed: {self._safe_error(e)}",
            )

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _create(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        start = time.time()
        reference = inputs.get("reference_audio")
        if not reference:
            raise ValueError("reference_audio is required for operation='create'")

        target_model = inputs.get("target_model", "qwen-audio-3.1-tts-flash")
        if target_model not in CLONED_VOICE_MODELS:
            raise ValueError(
                f"Unknown target_model {target_model!r}. "
                f"Valid values: {', '.join(CLONED_VOICE_MODELS)}"
            )

        prefix = self._normalize_prefix(inputs.get("prefix"))
        audio, reference_meta = self._resolve_reference(str(reference))

        body_input: dict[str, Any] = {
            "action": "create_voice",
            "target_model": target_model,
            "prefix": prefix,
            "audio": audio,
        }
        hints = inputs.get("language_hints")
        if hints:
            body_input["language_hints"] = [str(hints[0])] if isinstance(hints, list) else [str(hints)]
        if inputs.get("enable_preprocess") is not None:
            body_input["enable_preprocess"] = bool(inputs["enable_preprocess"])
        if inputs.get("enable_volume_normalization") is not None:
            body_input["enable_volume_normalization"] = (
                "true" if inputs["enable_volume_normalization"] else "false"
            )
        if inputs.get("max_prompt_audio_length") is not None:
            body_input["max_prompt_audio_length"] = float(
                inputs["max_prompt_audio_length"]
            )

        data = self._post(api_key, self._api_base(inputs), {
            "model": "voice-enrollment",
            "input": body_input,
        })
        voice_id = (data.get("output") or {}).get("voice_id")
        if not voice_id:
            raise RuntimeError(
                "voice-enrollment returned no voice_id: "
                + self._describe_response(data)
            )

        status = None
        if inputs.get("wait_for_ready", True):
            status = self._wait_for_ready(
                api_key,
                self._api_base(inputs),
                voice_id,
                timeout=float(inputs.get("timeout_seconds", 180)),
                interval=float(inputs.get("poll_interval_seconds", 3)),
            )

        record = {
            "provider": "dashscope",
            "operation": "create",
            "target_model": target_model,
            "voice_id": voice_id,
            "status": status or "DEPLOYING",
            "prefix": prefix,
            "reference": reference_meta,
            "enrollment_options": {
                key: body_input[key]
                for key in (
                    "language_hints",
                    "enable_preprocess",
                    "enable_volume_normalization",
                    "max_prompt_audio_length",
                )
                if key in body_input
            },
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "usage": data.get("usage"),
            "request_id": data.get("request_id"),
        }

        artifacts: list[str] = []
        output_path = inputs.get("output_path")
        if output_path:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            import json

            path.write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            artifacts.append(str(path))
            record["output"] = str(path)

        return ToolResult(
            success=True,
            data=record,
            artifacts=artifacts,
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=target_model,
        )

    def _query(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        voice_id = self._require_voice_id(inputs)
        start = time.time()
        data = self._post(api_key, self._api_base(inputs), {
            "model": "voice-enrollment",
            "input": {"action": "query_voice", "voice_id": voice_id},
        })
        output = data.get("output") or {}
        return ToolResult(
            success=True,
            data={
                "provider": "dashscope",
                "operation": "query",
                "voice_id": voice_id,
                "status": output.get("status"),
                "target_model": output.get("target_model"),
                "created_at": output.get("gmt_create"),
                "modified_at": output.get("gmt_modified"),
                "resource_link": output.get("resource_link"),
                "usage": data.get("usage"),
            },
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
        )

    def _list(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        start = time.time()
        body_input: dict[str, Any] = {
            "action": "list_voice",
            "page_index": int(inputs.get("page_index", 0)),
            "page_size": int(inputs.get("page_size", 20)),
        }
        if inputs.get("prefix"):
            body_input["prefix"] = str(inputs["prefix"])
        data = self._post(api_key, self._api_base(inputs), {
            "model": "voice-enrollment",
            "input": body_input,
        })
        voices = (data.get("output") or {}).get("voice_list") or []
        return ToolResult(
            success=True,
            data={
                "provider": "dashscope",
                "operation": "list",
                "voices": [
                    {
                        "voice_id": v.get("voice_id"),
                        "status": v.get("status"),
                        "created_at": v.get("gmt_create"),
                        "modified_at": v.get("gmt_modified"),
                    }
                    for v in voices
                ],
                "count": len(voices),
                "usage": data.get("usage"),
            },
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
        )

    def _delete(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        voice_id = self._require_voice_id(inputs)
        start = time.time()
        data = self._post(api_key, self._api_base(inputs), {
            "model": "voice-enrollment",
            "input": {"action": "delete_voice", "voice_id": voice_id},
        })
        return ToolResult(
            success=True,
            data={
                "provider": "dashscope",
                "operation": "delete",
                "voice_id": voice_id,
                "deleted": True,
                "usage": data.get("usage"),
            },
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _wait_for_ready(
        self,
        api_key: str,
        base: str,
        voice_id: str,
        *,
        timeout: float,
        interval: float,
    ) -> str:
        deadline = time.time() + timeout
        status = "DEPLOYING"
        while time.time() < deadline:
            data = self._post(api_key, base, {
                "model": "voice-enrollment",
                "input": {"action": "query_voice", "voice_id": voice_id},
            })
            status = str((data.get("output") or {}).get("status") or "")
            if status == "OK":
                return status
            if status == "UNDEPLOYED":
                raise RuntimeError(
                    f"Enrollment for {voice_id} was rejected (status UNDEPLOYED). "
                    "Check the reference audio against the docs: clean speech, "
                    "no music or background voices, 5-60 s."
                )
            time.sleep(interval)
        raise RuntimeError(
            f"Voice {voice_id} still {status or 'unknown'} after {timeout:.0f}s. "
            "It may finish later — re-run with operation='query'."
        )

    def _resolve_reference(self, reference: str) -> tuple[str, dict[str, Any]]:
        """Return (audio field, metadata) for a URL, data URI, or local file."""
        if reference.startswith(("http://", "https://", "data:")):
            return reference, {"source": "url" if reference.startswith("http") else "data_uri"}

        path = Path(reference)
        if not path.is_file():
            raise ValueError(f"reference_audio not found: {path}")

        size = path.stat().st_size
        if size > MAX_REFERENCE_BYTES:
            raise ValueError(
                f"reference_audio is {size / MIB:.1f} MB; the API limit is 10 MB. "
                "Trim the sample first."
            )

        mime = MIME_BY_SUFFIX.get(path.suffix.lower())
        if not mime:
            raise ValueError(
                f"Unsupported reference format {path.suffix!r}. "
                "Use .wav, .mp3, or .m4a."
            )

        duration = None
        try:
            from tools.analysis.audio_probe import probe_duration

            duration = probe_duration(path)
        except Exception:
            duration = None

        if duration is not None:
            if duration < MIN_REFERENCE_SECONDS:
                raise ValueError(
                    f"reference_audio is {duration:.1f}s; at least "
                    f"{MIN_REFERENCE_SECONDS:.0f}s of continuous speech is required."
                )
            if duration > MAX_REFERENCE_SECONDS:
                raise ValueError(
                    f"reference_audio is {duration:.1f}s; the API limit is "
                    f"{MAX_REFERENCE_SECONDS:.0f}s."
                )

        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
        meta: dict[str, Any] = {
            "source": "local_file",
            "path": str(path),
            "size_bytes": size,
            "format": mime,
        }
        if duration is not None:
            meta["duration_seconds"] = round(duration, 2)
        return f"data:{mime};base64,{encoded}", meta

    @staticmethod
    def _normalize_prefix(prefix: Any) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z]", "", str(prefix or ""))[:10]
        return cleaned or "omvoice"

    @staticmethod
    def _require_voice_id(inputs: dict[str, Any]) -> str:
        voice_id = str(inputs.get("voice_id") or "").strip()
        if not voice_id:
            raise ValueError(
                f"voice_id is required for operation={inputs.get('operation')!r}"
            )
        return voice_id

    def _api_base(self, inputs: dict[str, Any]) -> str:
        explicit = inputs.get("base_url") or os.environ.get(
            "DASHSCOPE_VOICE_CLONE_BASE_URL"
        )
        if explicit:
            base = str(explicit).rstrip("/")
            return base if base.endswith("/api/v1") else base + "/api/v1"
        workspace = inputs.get("workspace_id") or os.environ.get(
            "DASHSCOPE_WORKSPACE_ID"
        )
        if workspace:
            return self.WORKSPACE_DOMAIN.format(workspace_id=str(workspace).strip())
        return self.PUBLIC_ENDPOINT

    def _post(self, api_key: str, base: str, body: dict[str, Any]) -> dict[str, Any]:
        import requests

        response = requests.post(
            f"{base}{self.CUSTOMIZATION_PATH}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
        try:
            data = response.json()
        except Exception:
            response.raise_for_status()
            raise RuntimeError(
                f"DashScope returned non-JSON (HTTP {response.status_code})"
            )

        if response.status_code >= 400 or data.get("code"):
            raise RuntimeError(
                f"HTTP {response.status_code}: {self._describe_response(data)}"
            )
        return data

    @staticmethod
    def _describe_response(data: dict[str, Any]) -> str:
        parts = [
            str(data[key])
            for key in ("code", "message", "request_id")
            if data.get(key)
        ]
        return " | ".join(parts) or str(data)[:300]

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        key = os.environ.get("DASHSCOPE_API_KEY", "")
        message = str(exc)
        if key:
            message = message.replace(key, "[redacted]")
        return message
