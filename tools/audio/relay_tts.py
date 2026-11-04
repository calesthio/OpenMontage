"""Relay (中转站) text-to-speech tools, one per configured model.

Protocol ``openai_speech``: POST /audio/speech (JSON) → audio bytes.
Built from ``relay_providers.yaml`` by ``build_registry_tools``.
"""

from __future__ import annotations

import copy
import time
from typing import Any

from tools.base_tool import BaseTool, ExecutionMode, ToolResult, ToolTier
from tools.relay.engine import JobRequest, RelayHTTP
from tools.relay.tooling import CONTROL_PROPS, RelayToolBase, build_tools, check_allowed

_FORMATS = {"mp3", "wav", "opus", "aac", "flac", "pcm"}


class RelayTTS(RelayToolBase):
    capability = "tts"
    tier = ToolTier.VOICE
    execution_mode = ExecutionMode.SYNC

    def _build_supports(self) -> dict[str, Any]:
        return {"text_to_speech": True, "voice_selection": True, "local_save": True}

    def _build_input_schema(self) -> dict[str, Any]:
        m = self.relay_model
        voices = m.limits.get("voices")
        return {
            "type": "object",
            "required": ["text"],
            "properties": {
                "text": {"type": "string"},
                "model_id": {"type": "string", "enum": m.model_ids},
                "voice": {"type": "string", **({"enum": voices} if voices else {})},
                "voice_id": {"type": "string", "description": "Alias of voice."},
                "speed": {"type": "number"},
                "instructions": {"type": "string"},
                "output_format": {"type": "string", "enum": sorted(_FORMATS)},
                **copy.deepcopy(CONTROL_PROPS),
            },
        }

    def billable_units(self, inputs: dict[str, Any]) -> dict[str, float]:
        return {"chars": float(len(str(inputs.get("text") or "")))}

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        m = self.relay_model
        resumed = self._resume_only(inputs, started)
        if resumed is not None:
            return resumed
        blocked =self._guard(inputs, "text_to_speech")
        if blocked:
            return blocked
        text = str(inputs.get("text") or "").strip()
        if not text:
            return self._fail("text is required", code="bad_input")
        max_chars = int(m.limits.get("max_chars", 4096))
        if len(text) > max_chars:
            return self._fail(f"text is {len(text)} chars; {self.name} accepts at most {max_chars}. "
                              "Split narration per scene.", code="bad_param")
        voice = inputs.get("voice") or inputs.get("voice_id") or m.defaults.get("voice")
        if not voice:
            return self._fail("voice is required (set defaults.voice in relay_providers.yaml)", code="bad_input")
        problem = check_allowed("voice", voice, m.limits.get("voices"))
        if problem:
            return self._fail(problem, code="bad_param")
        fmt = str(inputs.get("output_format") or m.defaults.get("output_format") or "mp3").split("_")[0]
        if fmt not in _FORMATS:
            return self._fail(f"output_format must be one of {sorted(_FORMATS)}", code="bad_param")

        body: dict[str, Any] = {"model": m.model, "input": text, "voice": voice, "response_format": fmt}
        speed = inputs.get("speed", m.defaults.get("speed"))
        if speed is not None:
            body["speed"] = float(speed)
        if inputs.get("instructions"):
            body["instructions"] = inputs["instructions"]
        body.update(m.defaults.get("params") or {})
        if inputs.get("extra_params"):
            body.update(inputs["extra_params"])

        output_path, job_path = self._paths(inputs, f"{self.name}.{fmt}")
        estimated = self._estimated_cost_or_none(inputs)
        summary = {k: v for k, v in body.items() if k != "input"}
        summary["text_sha"] = self._fingerprint({"text": text})
        req = JobRequest(
            tool_name=self.name,
            operation="text_to_speech",
            output_path=output_path,
            job_path=job_path,
            fingerprint=self._fingerprint({"body": summary}),
            estimated_cost_usd=estimated,
            variables={},
            media_kind="audio",
            summary={**summary, "text_length": len(text)},
        )
        if inputs.get("dry_run"):
            return ToolResult(success=True, data={
                "dry_run": True, "tool": self.name, "endpoint": m.endpoint, "method": "POST",
                "path": "/audio/speech", "body": {**body, "input": f"<{len(text)} chars>"},
                "estimated_cost_usd": estimated, "output_path": str(output_path),
                "job_path": str(job_path), "billing_enabled": m.relay.billing_enabled})
        if not job_path.is_file() or inputs.get("confirm_resubmit"):
            gate = self._billing_gate(inputs, estimated)
            if gate:
                return gate

        http = RelayHTTP(m)

        def submit(_req: JobRequest) -> dict[str, Any]:
            response = http.submit("POST", "/audio/speech", json_body=body, timeout=m.submit_timeout_seconds)
            ctype = (response.headers.get("Content-Type") or "").lower()
            if "json" in ctype:
                from tools.relay.engine import SubmitRejected

                raise SubmitRejected(f"relay returned JSON instead of audio: {http.redact(response.text[:300])}",
                                     code="no_result")
            return {"inline": response.content}

        result = self._run(req, inputs, started, submit_fn=submit)
        if result.success:
            result.data.update({"voice": voice, "format": fmt, "text_length": len(text)})
            try:
                from tools.video._shared import probe_output
                from pathlib import Path

                result.data.update({k: v for k, v in probe_output(Path(output_path)).items() if k != "file_size_bytes"})
            except Exception:  # noqa: BLE001 — probing is informational
                pass
        return result


def build_registry_tools() -> list[BaseTool]:
    """Registry hook: one RelayTTS per tts model in relay_providers.yaml."""
    return build_tools("tts", RelayTTS)
