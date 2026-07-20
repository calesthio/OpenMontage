"""DashScope (Alibaba Cloud Bailian) ASR with word-level timestamps.

Uses the DashScope-native async transcription endpoint with
X-DashScope-Async: enable header. The model qwen3-asr-flash-filetrans is the
ONLY DashScope path that returns word-level timestamps (the sync
qwen3-asr-flash via /chat/completions does not).

Pattern: submit (POST) -> poll (GET /tasks/{task_id}) -> download
transcription_url -> parse transcripts[].sentences[].words[].

This tool replaces the broken `whisperx` slot for subtitle-aligned
transcription. Word timestamps are normalized from milliseconds to seconds.
"""

from __future__ import annotations

import os
import time
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


class DashscopeAsr(BaseTool):
    name = "dashscope_asr"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "dashscope"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set DASHSCOPE_API_KEY to your Alibaba Cloud DashScope API key.\n"
        "  Get one at https://dashscope.aliyun.com/"
    )
    fallback = "transcriber"
    fallback_tools = ["transcriber"]
    agent_skills = ["dashscope"]

    capabilities = [
        "speech_to_text",
        "word_timestamps",
        "multilingual",
    ]
    supports = {
        "word_timestamps": True,
        "multilingual": True,
        "offline": False,
    }
    best_for = [
        "word-level timestamp transcription for subtitle alignment",
        "Mandarin and English speech recognition",
        "replacing whisperx when word-level granularity is needed",
    ]
    not_good_for = [
        "real-time transcription",
        "local/offline transcription",
    ]

    input_schema = {
        "type": "object",
        "required": ["audio_url"],
        "properties": {
            "audio_url": {
                "type": "string",
                "description": (
                    "Publicly accessible URL of the audio file to transcribe. "
                    "Must be reachable by DashScope servers — local paths "
                    "are not supported."
                ),
            },
            "model": {
                "type": "string",
                "enum": ["qwen3-asr-flash-filetrans"],
                "default": "qwen3-asr-flash-filetrans",
            },
            "language_hints": {
                "type": "array",
                "items": {"type": "string"},
                "default": ["zh", "en"],
                "description": (
                    "Language hints to improve accuracy. "
                    'Examples: ["zh", "en", "ja"].'
                ),
            },
            "enable_words": {
                "type": "boolean",
                "default": True,
                "description": (
                    "Enable word-level timestamps. Required for subtitle "
                    "alignment."
                ),
            },
            "output_path": {"type": "string"},
            "poll_interval_seconds": {
                "type": "number",
                "default": 5.0,
                "minimum": 1.0,
            },
            "timeout_seconds": {
                "type": "integer",
                "default": 300,
                "minimum": 30,
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=20, network_required=True
    )
    retry_policy = RetryPolicy(
        max_retries=2,
        backoff_seconds=2.0,
        retryable_errors=["timeout", "rate_limit"],
    )
    idempotency_key_fields = ["audio_url", "model", "enable_words", "language_hints"]
    side_effects = [
        "writes transcription JSON to output_path",
        "calls DashScope (Alibaba Cloud) ASR API (async submit + poll)",
    ]
    user_visible_verification = [
        "Check transcription text for accuracy",
        "Verify word-level timestamps before building subtitles",
    ]

    SUBMIT_URL = (
        "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/"
        "transcription"
    )
    POLL_URL_TEMPLATE = (
        "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    )

    def get_status(self) -> ToolStatus:
        if os.environ.get("DASHSCOPE_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # DashScope ASR pricing is per-minute; check console for actual cost.
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="DASHSCOPE_API_KEY not set. " + self.install_instructions,
            )

        audio_url = inputs.get("audio_url", "").strip()
        if not audio_url:
            return ToolResult(
                success=False, error="audio_url is required."
            )
        if not self._is_public_url(audio_url):
            return ToolResult(
                success=False,
                error=(
                    "audio_url must be a publicly accessible URL (http/https). "
                    "DashScope servers fetch the file; local paths are not "
                    "supported. Upload the audio to a public location first."
                ),
            )
        # DashScope ASR rejects http:// URLs with InvalidParameter.MalformedURL;
        # upgrade to https:// before submitting. Note: signed OSS URLs with
        # query params (Expires, Signature) may also be rejected — prefer clean
        # public file URLs when possible.
        if audio_url.startswith("http://"):
            audio_url = "https://" + audio_url[len("http://"):]
            inputs = {**inputs, "audio_url": audio_url}

        start = time.time()
        try:
            result = self._transcribe(inputs, api_key=api_key)
        except Exception as exc:
            return ToolResult(
                success=False,
                error=f"DashScope ASR failed: {self._safe_error(exc)}",
            )

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _transcribe(
        self, inputs: dict[str, Any], *, api_key: str
    ) -> ToolResult:
        import json
        import requests

        payload = self._build_payload(inputs)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        # Submit
        submit_resp = requests.post(
            self.SUBMIT_URL, headers=headers, json=payload, timeout=(10, 60)
        )
        submit_data = self._json_or_raise(submit_resp)
        self._raise_for_error(submit_resp.status_code, submit_data)

        task_id = submit_data.get("output", {}).get("task_id")
        if not task_id:
            raise RuntimeError(
                "DashScope ASR submit succeeded but did not return "
                "output.task_id"
            )

        # Poll
        poll_data = self._poll_task(
            requests_module=requests,
            api_key=api_key,
            task_id=task_id,
            poll_interval=float(inputs.get("poll_interval_seconds", 5.0)),
            timeout_seconds=int(inputs.get("timeout_seconds", 300)),
        )

        # qwen3-asr-flash-filetrans returns output.result.transcription_url
        # (singular "result", NOT "results" array like paraformer-v2)
        result = poll_data.get("output", {}).get("result", {})
        transcription_url = result.get("transcription_url")
        if not transcription_url:
            raise RuntimeError(
                "DashScope ASR task succeeded but "
                "result.transcription_url missing"
            )

        # Download transcription JSON
        trans_resp = requests.get(transcription_url, timeout=120)
        trans_resp.raise_for_status()
        transcription = trans_resp.json()

        # Save full transcription
        output_path = Path(
            inputs.get("output_path", "dashscope_asr.json")
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(transcription, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        # Parse word-level timestamps (normalize ms -> seconds)
        words = self._extract_words(transcription)
        transcripts = transcription.get("transcripts", [])

        return ToolResult(
            success=True,
            data={
                "provider": "dashscope",
                "model": payload["model"],
                "audio_url": inputs["audio_url"],
                "task_id": task_id,
                "transcripts": transcripts,
                "words": words,
                "word_count": len(words),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            cost_usd=self.estimate_cost(inputs),
            model=payload["model"],
        )

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": inputs.get(
                "model", "qwen3-asr-flash-filetrans"
            ),
            "input": {
                "file_url": inputs["audio_url"],
            },
            "parameters": {
                "enable_words": bool(inputs.get("enable_words", True)),
                "language_hints": inputs.get(
                    "language_hints", ["zh", "en"]
                ),
            },
        }

    def _poll_task(
        self,
        *,
        requests_module: Any,
        api_key: str,
        task_id: str,
        poll_interval: float,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        deadline = time.time() + timeout_seconds
        headers = {"Authorization": f"Bearer {api_key}"}
        while time.time() < deadline:
            time.sleep(poll_interval)
            resp = requests_module.get(
                self.POLL_URL_TEMPLATE.format(task_id=task_id),
                headers=headers,
                timeout=(10, 60),
            )
            data = self._json_or_raise(resp)
            self._raise_for_error(resp.status_code, data)
            status = data.get("output", {}).get("task_status")
            if status == "SUCCEEDED":
                return data
            if status == "FAILED":
                msg = data.get("output", {}).get(
                    "message", "unknown error"
                )
                raise RuntimeError(
                    f"DashScope ASR task failed: {msg}"
                )
        raise TimeoutError(
            f"DashScope ASR task {task_id} did not finish within "
            f"{timeout_seconds}s"
        )

    @staticmethod
    def _is_public_url(url: str) -> bool:
        return url.startswith("http://") or url.startswith("https://")

    @staticmethod
    def _extract_words(
        transcription: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Extract flat word list with timestamps normalized to seconds."""
        words: list[dict[str, Any]] = []
        for transcript in transcription.get("transcripts", []):
            for sentence in transcript.get("sentences", []):
                for word in sentence.get("words", []):
                    words.append(
                        {
                            "text": word.get("text", ""),
                            "begin_time_seconds": round(
                                word.get("begin_time", 0) / 1000.0, 3
                            ),
                            "end_time_seconds": round(
                                word.get("end_time", 0) / 1000.0, 3
                            ),
                        }
                    )
        return words

    @staticmethod
    def _json_or_raise(response: Any) -> dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                f"Non-JSON response from DashScope API: "
                f"HTTP {response.status_code}"
            ) from exc

    def _raise_for_error(
        self, http_status: int, payload: dict[str, Any]
    ) -> None:
        if http_status < 400:
            return
        code = payload.get("code")
        message = payload.get("message", "unknown error")
        raise RuntimeError(
            f"DashScope API error: HTTP {http_status}, "
            f"code {code}: {message}"
        )

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace(
            os.environ.get("DASHSCOPE_API_KEY", ""), "[redacted]"
        )
