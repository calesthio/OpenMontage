"""iFlytek (讯飞) long-text text-to-speech provider tool.

Wraps the iFlytek Open Platform "长文本语音合成" (DTS) API, which is the
long-form endpoint of the family: submit a task, poll until it finishes, then
download the rendered audio. That shape fits video narration better than the
streaming WebSocket TTS endpoint, and it keeps this tool on `requests` alone --
no websocket-client dependency is added to the project.

API: https://www.xfyun.cn/doc/tts/long_text_tts/API.html
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import time
import uuid
from email.utils import formatdate
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from tools.provider_pricing import PriceQuoteRequired

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


class IFlytekTTS(BaseTool):
    name = "iflytek_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "iflytek"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    resume_support = ResumeSupport.FROM_CHECKPOINT
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = [
        "env:IFLYTEK_APP_ID",
        "env:IFLYTEK_API_KEY",
        "env:IFLYTEK_API_SECRET",
    ]
    install_instructions = (
        "Create an app at https://console.xfyun.cn/ , enable 长文本语音合成 (DTS), then set\n"
        "IFLYTEK_APP_ID, IFLYTEK_API_KEY, and IFLYTEK_API_SECRET.\n"
        "Optional: set IFLYTEK_TTS_VCN to the default authorized voice, e.g. x4_mingge.\n"
        "All three credentials are required -- DTS signs each request with APIKey + APISecret."
    )
    fallback = "doubao_tts"
    fallback_tools = ["doubao_tts", "dashscope_tts", "google_tts", "piper_tts"]
    agent_skills = ["iflytek-tts", "text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_selection",
        "long_form_narration",
        "dialect_voices",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
        "timestamps": False,
        "long_text_async": True,
    }
    best_for = [
        "long-form Mandarin narration in a single request (up to ~100k characters)",
        "Chinese documentary and audiobook voiceovers",
        "Mandarin dialect narration through voice selection",
    ]
    not_good_for = [
        "word-level subtitle alignment (DTS returns no word timings)",
        "real-time or interactive speech",
        "fully offline production",
        "voice clone matching",
    ]

    input_schema = {
        "type": "object",
        "anyOf": [{"required": ["text"]}, {"required": ["task_id"]}],
        "properties": {
            "text": {"type": "string", "minLength": 1, "description": "Text to convert to speech"},
            "task_id": {
                "type": "string", "minLength": 1,
                "description": "Resume an accepted DTS task by query/download only; never submits text.",
            },
            "voice_id": {
                "type": "string",
                "description": (
                    "iFlytek vcn (voice name), e.g. x4_mingge. Defaults to IFLYTEK_TTS_VCN. "
                    "The voice must be authorized for your app."
                ),
            },
            "language": {
                "type": "string",
                "default": "zh",
                "enum": ["zh", "en"],
            },
            "format": {
                "type": "string",
                "default": "lame",
                "enum": ["lame", "speex", "opus", "raw"],
                "description": "DTS audio encoding. lame is MP3; raw is headerless PCM.",
            },
            "sample_rate": {
                "type": "integer",
                "default": 24000,
                "enum": [8000, 16000, 24000],
            },
            "speed": {
                "type": "integer",
                "default": 50,
                "minimum": 0,
                "maximum": 100,
                "description": "Speaking rate. 50 is normal, 0 slowest, 100 fastest.",
            },
            "volume": {
                "type": "integer",
                "default": 50,
                "minimum": 0,
                "maximum": 100,
            },
            "pitch": {
                "type": "integer",
                "default": 50,
                "minimum": 0,
                "maximum": 100,
            },
            "read_punctuation": {
                "type": "boolean",
                "default": False,
                "description": "DTS 'ram'. True reads punctuation marks aloud.",
            },
            "output_path": {"type": "string"},
            "metadata_path": {
                "type": "string",
                "description": "Where to save the full query JSON. Defaults next to output_path.",
            },
            "poll_interval_seconds": {
                "type": "number",
                "default": 3.0,
                "minimum": 0.5,
            },
            "timeout_seconds": {
                "type": "integer",
                "default": 600,
                "minimum": 30,
                "description": "Long narrations take minutes; DTS is an async batch service.",
            },
        },
    }

    output_schema = {
        "type": "object",
        "properties": {
            "output": {"type": "string"},
            "metadata_path": {"type": "string"},
            "task_id": {"type": "string"},
            "audio_url": {"type": "string"},
            "audio_duration_seconds": {"type": ["number", "null"]},
        },
    }
    artifact_schema = {
        "type": "array",
        "items": {"type": "string"},
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=0,
        retryable_errors=[],
    )
    idempotency_key_fields = [
        "task_id",
        "text",
        "voice_id",
        "language",
        "format",
        "sample_rate",
        "speed",
        "volume",
        "pitch",
    ]
    side_effects = [
        "writes audio file to output_path",
        "writes iFlytek DTS query metadata JSON next to output_path",
        "calls the iFlytek Open Platform DTS API",
    ]
    user_visible_verification = [
        "Listen to generated audio for Mandarin naturalness and pacing",
        "Confirm the vcn is the voice the user approved",
    ]
    quality_score = 0.85
    latency_p50_seconds = 20.0

    HOST = "api-dx.xf-yun.com"
    CREATE_PATH = "/v1/private/dts_create"
    QUERY_PATH = "/v1/private/dts_query"
    DEFAULT_VOICE_ENV = "IFLYTEK_TTS_VCN"

    # DTS task_status: 1 created, 2 dispatch failed, 3 processing, 5 complete.
    STATUS_DISPATCH_FAILED = 2
    STATUS_COMPLETE = 5

    _EXTENSIONS = {"lame": "mp3", "speex": "speex", "opus": "opus", "raw": "pcm"}

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        raise PriceQuoteRequired(
            "Obtain an account-specific DTS character-package quote and currency conversion; "
            "the API does not report an actual USD charge."
        )

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        app_id = os.environ.get("IFLYTEK_APP_ID")
        api_key = os.environ.get("IFLYTEK_API_KEY")
        api_secret = os.environ.get("IFLYTEK_API_SECRET")
        missing = [
            name
            for name, value in (
                ("IFLYTEK_APP_ID", app_id),
                ("IFLYTEK_API_KEY", api_key),
                ("IFLYTEK_API_SECRET", api_secret),
            )
            if not value
        ]
        if missing:
            return ToolResult(
                success=False,
                error=(
                    f"Missing iFlytek credentials: {', '.join(missing)}. "
                    + self.install_instructions
                ),
            )

        voice_id = inputs.get("voice_id") or os.environ.get(self.DEFAULT_VOICE_ENV)
        if not voice_id and not inputs.get("task_id"):
            return ToolResult(
                success=False,
                error=(
                    "No iFlytek voice_id provided. Pass voice_id or set "
                    f"{self.DEFAULT_VOICE_ENV} in the environment. OpenMontage does not "
                    "guess a voice, because vcn availability depends on what your app is "
                    "authorized for."
                ),
            )

        start = time.time()
        try:
            result = self._generate(
                inputs,
                app_id=app_id,
                api_key=api_key,
                api_secret=api_secret,
                voice_id=voice_id,
            )
        except Exception as exc:
            return ToolResult(
                success=False, error=f"iFlytek TTS failed: {self._safe_error(exc)}",
                cost_usd=None, data={"cost_status": "unquoted"},
            )

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(
        self,
        inputs: dict[str, Any],
        *,
        app_id: str,
        api_key: str,
        api_secret: str,
        voice_id: str,
    ) -> ToolResult:
        import requests

        text = inputs.get("text", "")
        encoding = inputs.get("format", "lame")
        output_path = Path(
            inputs.get("output_path", f"iflytek_tts.{self._EXTENSIONS.get(encoding, 'mp3')}")
        )
        metadata_path = Path(
            inputs.get("metadata_path") or output_path.with_suffix(output_path.suffix + ".json")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        task_id = inputs.get("task_id")
        if not task_id:
            if not isinstance(text, str) or not text.strip():
                raise ValueError("Provide non-empty text or an existing task_id")
            create_response = requests.post(
                self._signed_url(self.CREATE_PATH, api_key=api_key, api_secret=api_secret),
                headers={"Content-Type": "application/json"},
                json=self._create_body(inputs, app_id=app_id, voice_id=voice_id),
                timeout=(10, 60),
            )
            create_data = self._json_or_raise(create_response)
            self._raise_for_iflytek_error(create_response.status_code, create_data)
            task_id = create_data.get("header", {}).get("task_id")
            if not task_id:
                raise RuntimeError("iFlytek dts_create succeeded but did not return header.task_id")

        # Keep recovery independent of text, voice selection, and another submission.
        resume_inputs = {
            "task_id": task_id, "output_path": str(output_path),
            "metadata_path": str(metadata_path), "format": encoding,
        }
        task_path = metadata_path.with_name(metadata_path.name + ".task.json")
        checkpoint_saved = False
        try:
            self._atomic_write(task_path, json.dumps(resume_inputs).encode("utf-8"))
            checkpoint_saved = True
            query_data = self._poll_query(
                requests_module=requests,
                app_id=app_id,
                api_key=api_key,
                api_secret=api_secret,
                task_id=task_id,
                poll_interval=float(inputs.get("poll_interval_seconds", 3.0)),
                timeout_seconds=int(inputs.get("timeout_seconds", 600)),
            )
            audio_url = self._audio_url(query_data)
            if not audio_url:
                raise RuntimeError("iFlytek task completed but returned no payload.audio.audio URL")

            audio_response = requests.get(audio_url, timeout=(10, 300))
            audio_response.raise_for_status()
            self._atomic_write(output_path, audio_response.content)
            self._atomic_write(
                metadata_path,
                (json.dumps(query_data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
            )

        except Exception as exc:
            return ToolResult(
                success=False, error=f"iFlytek TTS failed: {self._safe_error(exc)}",
                cost_usd=None, model="iflytek/dts",
                data={"task_id": task_id, "resume_inputs": resume_inputs,
                      "cost_status": "unquoted", "task_path": str(task_path)},
                artifacts=[str(task_path)] if checkpoint_saved else [],
            )

        audio_duration = self._audio_duration(output_path)
        audio_meta = query_data.get("payload", {}).get("audio", {})

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": "dts",
                "voice_id": voice_id,
                "vcn": voice_id,
                "language": inputs.get("language", "zh"),
                "format": encoding,
                "sample_rate": inputs.get("sample_rate", 24000),
                "speed": inputs.get("speed", 50),
                "volume": inputs.get("volume", 50),
                "pitch": inputs.get("pitch", 50),
                "text_length": len(text) if text else None,
                "cost_status": "unquoted",
                "task_path": str(task_path),
                "task_id": task_id,
                "task_status": query_data.get("header", {}).get("task_status"),
                "sid": query_data.get("header", {}).get("sid"),
                "audio_url": audio_url,
                "audio_encoding": audio_meta.get("encoding"),
                "audio_sample_rate": audio_meta.get("sample_rate"),
                "audio_duration_seconds": round(audio_duration, 2) if audio_duration else None,
                "output": str(output_path),
                "metadata_path": str(metadata_path),
            },
            artifacts=[str(output_path), str(metadata_path), str(task_path)],
            cost_usd=None,
            model="iflytek/dts",
        )

    @staticmethod
    def _atomic_write(path: Path, content: bytes) -> None:
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(content)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    # ---- Request building -------------------------------------------------

    def _signed_url(self, path: str, *, api_key: str, api_secret: str) -> str:
        """Build the DTS authenticated URL.

        iFlytek signs `host`, `date`, and the request line with HMAC-SHA256 and
        passes the result as query parameters rather than headers. `date` must
        be RFC1123 in GMT -- the server rejects anything more than 300 seconds
        away from its own clock.
        """
        date = formatdate(timeval=time.time(), usegmt=True)
        signature_origin = f"host: {self.HOST}\ndate: {date}\nPOST {path} HTTP/1.1"
        signature = base64.b64encode(
            hmac.new(
                api_secret.encode("utf-8"),
                signature_origin.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")
        authorization_origin = (
            f'api_key="{api_key}", algorithm="hmac-sha256", '
            f'headers="host date request-line", signature="{signature}"'
        )
        authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
        query = urlencode({"host": self.HOST, "date": date, "authorization": authorization})
        return f"https://{self.HOST}{path}?{query}"

    def _create_body(
        self, inputs: dict[str, Any], *, app_id: str, voice_id: str
    ) -> dict[str, Any]:
        text_b64 = base64.b64encode(inputs["text"].encode("utf-8")).decode("utf-8")
        return {
            "header": {
                "app_id": app_id,
                "request_id": inputs.get("request_id") or str(uuid.uuid4()),
            },
            "parameter": {
                "dts": {
                    "vcn": voice_id,
                    "language": inputs.get("language", "zh"),
                    "speed": int(inputs.get("speed", 50)),
                    "volume": int(inputs.get("volume", 50)),
                    "pitch": int(inputs.get("pitch", 50)),
                    "ram": 1 if inputs.get("read_punctuation") else 0,
                    "rhy": 0,
                    "audio": {
                        "encoding": inputs.get("format", "lame"),
                        "sample_rate": int(inputs.get("sample_rate", 24000)),
                    },
                    "pybuf": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain",
                    },
                }
            },
            "payload": {
                "text": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "plain",
                    "text": text_b64,
                }
            },
        }

    # ---- Polling ----------------------------------------------------------

    def _poll_query(
        self,
        *,
        requests_module: Any,
        app_id: str,
        api_key: str,
        api_secret: str,
        task_id: str,
        poll_interval: float,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            time.sleep(poll_interval)
            response = requests_module.post(
                self._signed_url(self.QUERY_PATH, api_key=api_key, api_secret=api_secret),
                headers={"Content-Type": "application/json"},
                json={"header": {"app_id": app_id, "task_id": task_id}},
                timeout=(10, 60),
            )
            query_data = self._json_or_raise(response)
            self._raise_for_iflytek_error(response.status_code, query_data)

            status = query_data.get("header", {}).get("task_status")
            status = int(status) if str(status).isdigit() else status
            if status == self.STATUS_DISPATCH_FAILED:
                raise RuntimeError(
                    f"iFlytek task {task_id} was not dispatched (task_status=2). "
                    "Check that 长文本语音合成 is enabled for this app and that the vcn is authorized."
                )
            # Terminal state is task_status=5, but treat a returned audio URL as
            # done too: the audio link is the only thing this tool needs, and a
            # status the docs do not enumerate should not strand a finished task.
            if status == self.STATUS_COMPLETE or self._audio_url(query_data):
                return query_data
        raise TimeoutError(f"iFlytek task did not finish within {timeout_seconds} seconds")

    # ---- Response helpers -------------------------------------------------

    @staticmethod
    def _audio_url(query_data: dict[str, Any]) -> str | None:
        """Decode payload.audio.audio, which holds a base64-encoded download URL."""
        encoded = query_data.get("payload", {}).get("audio", {}).get("audio")
        if not encoded:
            return None
        try:
            return base64.b64decode(encoded).decode("utf-8").strip()
        except Exception:
            return None

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Non-JSON response from iFlytek DTS API: HTTP {response.status_code}"
            ) from exc

    def _raise_for_iflytek_error(self, http_status: int, payload: dict[str, Any]) -> None:
        code = payload.get("header", {}).get("code")
        if http_status < 400 and code == 0:
            return
        message = payload.get("header", {}).get("message", "unknown error")
        raise RuntimeError(
            f"HTTP {http_status}, code {code}: {message}{self._diagnostic_hint(http_status, code)}"
        )

    @staticmethod
    def _diagnostic_hint(http_status: int, code: Any) -> str:
        if http_status == 401:
            return " (signature rejected -- check IFLYTEK_API_KEY and IFLYTEK_API_SECRET)"
        if http_status == 403:
            return " (clock skew -- the DTS server rejects a date more than 300s off)"
        if code == 10313:
            return " (app_id is empty or wrong -- check IFLYTEK_APP_ID)"
        if code == 10163:
            return " (request schema rejected -- check vcn, encoding, and sample_rate)"
        return ""

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        """Never echo credentials; the signed URL carries the api_key in a query param."""
        message = re.sub(r"https?://[^\s]+", "[redacted URL]", str(exc))
        for env_name in ("IFLYTEK_API_KEY", "IFLYTEK_API_SECRET", "IFLYTEK_APP_ID"):
            secret = os.environ.get(env_name)
            if secret:
                message = message.replace(secret, "***")
        return message

    @staticmethod
    def _audio_duration(path: Path) -> float | None:
        try:
            from tools.analysis.audio_probe import probe_duration

            return probe_duration(path)
        except Exception:
            return None
