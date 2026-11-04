"""Relay (中转站) video generation tools, one per configured model.

Protocols:
    openai_videos             POST /videos (multipart) → GET /videos/{id} → /videos/{id}/content
    openai_video_generations  POST /video/generations (JSON) → GET /videos/{id}
    generic_async             fully declarative submit/poll/download mapping
    ark_seedance              reuses SeedanceArkVideo's payload builder and
                              validation against an Ark-compatible relay

Every tool here is built from ``relay_providers.yaml`` by ``build_registry_tools``;
nothing is hardcoded. See docs/RELAY_PROVIDERS.zh-CN.md.
"""

from __future__ import annotations

import copy
import time
from typing import Any, Optional

from tools.base_tool import BaseTool, ToolResult
from tools.relay.config import RelayModel
from tools.relay.engine import JobRequest, PollOutcome, RelayHTTP, interpret_poll
from tools.relay.tooling import (
    CONTROL_PROPS,
    RelayToolBase,
    build_tools,
    check_allowed,
    size_for,
)
from tools.video.seedance_ark import SeedanceArkVideo

_FIRST_FRAME_KEYS = ("first_frame_path", "first_frame_url", "reference_image_path",
                     "reference_image_url", "image_path", "image_url")
_LAST_FRAME_KEYS = ("last_frame_path", "last_frame_url", "last_image_path", "last_image_url",
                    "end_image_path", "end_image_url")
_REFERENCE_LIST_KEYS = ("reference_image_paths", "reference_image_urls")


def _first(inputs: dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
    present = [inputs[k] for k in keys if inputs.get(k)]
    if len(set(map(str, present))) > 1:
        raise ValueError(f"conflicting values for {keys[0]}: {present}")
    return str(present[0]) if present else None


class RelayVideo(RelayToolBase):
    capability = "video_generation"

    def _build_supports(self) -> dict[str, Any]:
        caps = self.relay_model.capabilities
        return {
            "text_to_video": "text_to_video" in caps,
            "image_to_video": "image_to_video" in caps,
            "first_frame_local_file": "image_to_video" in caps and self.relay_model.image_input != "url",
            "first_last_frame": "first_last_frame" in caps,
            "reference_to_video": "reference_to_video" in caps,
            "async_resume": True,
            "local_save": True,
            "native_audio": bool(self.relay_model.limits.get("native_audio", False)),
        }

    def _build_input_schema(self) -> dict[str, Any]:
        m = self.relay_model
        caps = m.capabilities
        ops = [op for op in ("text_to_video", "image_to_video", "reference_to_video") if op in caps]
        props: dict[str, Any] = {
            "prompt": {"type": "string"},
            "operation": {"type": "string", "enum": ops},
            "model": {"type": "string", "enum": m.model_ids},
            "duration": {"description": f"Seconds. Allowed: {m.limits.get('durations') or m.limits.get('duration_range') or 'relay default'}"},
            "aspect_ratio": {"type": "string", **({"enum": m.limits["aspect_ratios"]} if m.limits.get("aspect_ratios") else {})},
            "resolution": {"type": "string", **({"enum": m.limits["resolutions"]} if m.limits.get("resolutions") else {})},
            "size": {"type": "string", "description": "Explicit WxH when the relay wants one."},
            "negative_prompt": {"type": "string"},
            "seed": {"type": "integer"},
            "poll_interval_seconds": {"type": "number"},
            "poll_timeout_seconds": {"type": "number"},
            **copy.deepcopy(CONTROL_PROPS),
        }
        # NOTE: no "image_url" property on purpose — video_selector would otherwise
        # auto-upload local first frames to fal.ai (a different paid vendor).
        if "image_to_video" in caps:
            props["reference_image_path"] = {"type": "string", "description": "Local first frame (preferred)."}
            props["reference_image_url"] = {"type": "string", "description": "Remote first frame URL."}
            props["first_frame_path"] = {"type": "string", "description": "Alias of reference_image_path."}
        if "first_last_frame" in caps:
            props["last_frame_path"] = {"type": "string"}
            props["last_frame_url"] = {"type": "string"}
        if "reference_to_video" in caps:
            props["reference_image_paths"] = {"type": "array", "items": {"type": "string"}}
            props["reference_image_urls"] = {"type": "array", "items": {"type": "string"}}
        return {"type": "object", "required": ["prompt"], "properties": props}

    def is_operation_available(self, operation: str) -> bool:
        """Consulted by video_selector so an i2v-only model is never picked for t2v."""
        if operation in ("generate", "rank"):
            return True
        return operation in self.relay_model.capabilities

    # -- helpers --------------------------------------------------------------
    def _operation(self, inputs: dict[str, Any], first: Optional[str], refs: list[str]) -> str:
        op = inputs.get("operation")
        if op in (None, "", "generate"):
            if first:
                return "image_to_video"
            return "reference_to_video" if refs else "text_to_video"
        return str(op)

    def _duration(self, inputs: dict[str, Any]) -> Optional[int]:
        raw = inputs.get("duration", self.relay_model.defaults.get("duration"))
        if raw in (None, ""):
            return None
        value = float(raw)
        if value <= 0 or value != int(value):
            raise ValueError(f"duration must be a positive whole number of seconds, got {raw!r}")
        return int(value)

    def billable_units(self, inputs: dict[str, Any]) -> dict[str, float]:
        try:
            seconds = self._duration(inputs)
        except ValueError:
            seconds = None
        return {"seconds": float(seconds or self.relay_model.limits.get("default_seconds", 5))}

    def _validate_params(self, inputs: dict[str, Any], duration: Optional[int]) -> list[str]:
        m = self.relay_model
        problems = []
        aspect = inputs.get("aspect_ratio", m.defaults.get("aspect_ratio"))
        resolution = inputs.get("resolution", m.defaults.get("resolution"))
        for name, value, allowed in (
            ("duration", duration, m.limits.get("durations")),
            ("aspect_ratio", aspect, m.limits.get("aspect_ratios")),
            ("resolution", resolution, m.limits.get("resolutions")),
            ("size", inputs.get("size"), m.limits.get("sizes")),
        ):
            msg = check_allowed(name, value, allowed)
            if msg:
                problems.append(msg)
        rng = m.limits.get("duration_range")
        if duration is not None and rng and not (rng[0] <= duration <= rng[1]):
            problems.append(f"duration={duration} outside allowed range {rng}")
        return problems

    # -- execute ----------------------------------------------------------------
    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        m = self.relay_model
        resumed = self._resume_only(inputs, started)
        if resumed is not None:
            return resumed
        try:
            first = _first(inputs, _FIRST_FRAME_KEYS)
            last = _first(inputs, _LAST_FRAME_KEYS)
            refs = [str(r) for k in _REFERENCE_LIST_KEYS for r in (inputs.get(k) or [])]
            operation = self._operation(inputs, first, refs)
            duration = self._duration(inputs)
        except (TypeError, ValueError) as exc:
            return self._fail(str(exc), code="bad_input")

        if operation == "text_to_video" and (first or last or refs):
            return self._fail(
                "operation=text_to_video but reference images were supplied; use "
                "image_to_video (first frame) so the image is not silently ignored",
                code="bad_input",
            )
        if operation == "image_to_video" and not first:
            return self._fail("image_to_video needs a first frame (reference_image_path or reference_image_url)",
                              code="bad_input")
        blocked = self._guard(inputs, operation)
        if blocked:
            return blocked
        if last and "first_last_frame" not in m.capabilities:
            return self._fail(f"{self.name} does not support a last frame (first_last_frame not declared)",
                              code="unsupported_capability")
        if refs and operation != "reference_to_video":
            return self._fail("reference_image_paths/urls require operation=reference_to_video", code="bad_input")
        max_refs = int(m.limits.get("max_reference_images", 4))
        if len(refs) > max_refs:
            return self._fail(f"at most {max_refs} reference images", code="bad_input")
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt and operation == "text_to_video":
            return self._fail("prompt is required", code="bad_input")
        problems = self._validate_params(inputs, duration)
        if problems:
            return self._fail("; ".join(problems) + ". Nothing was sent.", code="bad_param")

        if m.protocol == "ark_seedance":
            return self._execute_ark(inputs, operation, first, last, refs, duration, started)
        return self._execute_generic(inputs, operation, prompt, first, last, refs, duration, started)

    def _common_variables(self, inputs, prompt, duration) -> dict[str, Any]:
        m = self.relay_model
        aspect = inputs.get("aspect_ratio", m.defaults.get("aspect_ratio"))
        resolution = inputs.get("resolution", m.defaults.get("resolution"))
        size = inputs.get("size") or m.defaults.get("size") or size_for(m, aspect, resolution)
        width = height = None
        if size and "x" in str(size):
            w, _, h = str(size).partition("x")
            width, height = (int(w), int(h)) if w.isdigit() and h.isdigit() else (None, None)
        variables = {
            "model": m.model,
            "prompt": prompt,
            "negative_prompt": inputs.get("negative_prompt"),
            "duration": duration,
            "duration_str": str(duration) if duration is not None else None,
            "aspect_ratio": aspect,
            "resolution": resolution,
            "size": size,
            "width": width,
            "height": height,
            "seed": inputs.get("seed"),
            "extra_params": inputs.get("extra_params"),
        }
        for key, value in (m.defaults.get("params") or {}).items():
            variables.setdefault(key, value)
        return variables

    def _execute_generic(self, inputs, operation, prompt, first, last, refs, duration, started) -> ToolResult:
        m = self.relay_model
        try:
            variables = self._common_variables(inputs, prompt, duration)
            files = {}
            media_digest: dict[str, Any] = {}
            if first:
                img = self._load_image(first)
                files["first_frame_file"] = img
                variables["first_frame"] = self._encode(img) if m.image_input != "multipart" else None
                variables["first_frame_file"] = "<file>"
                media_digest["first_frame"] = self._image_digest(img)
            if last:
                img = self._load_image(last)
                files["last_frame_file"] = img
                variables["last_frame"] = self._encode(img) if m.image_input != "multipart" else None
                variables["last_frame_file"] = "<file>"
                media_digest["last_frame"] = self._image_digest(img)
            if refs:
                loaded = [self._load_image(r) for r in refs]
                variables["reference_images"] = [self._encode(i) for i in loaded]
                media_digest["reference_images"] = [self._image_digest(i) for i in loaded]
        except Exception as exc:  # noqa: BLE001
            return self._fail(str(exc), code=getattr(exc, "code", "bad_image"))

        output_path, job_path = self._paths(inputs, f"{self.name}.mp4")
        estimated = self._estimated_cost_or_none(inputs)
        summary = {k: v for k, v in variables.items() if k not in {"first_frame", "last_frame", "reference_images", "first_frame_file", "last_frame_file"} and v is not None}
        summary.update(media_digest)
        req = JobRequest(
            tool_name=self.name,
            operation=operation,
            output_path=output_path,
            job_path=job_path,
            fingerprint=self._fingerprint({"operation": operation, **summary}),
            estimated_cost_usd=estimated,
            variables=variables,
            files=files,
            media_kind="video",
            summary={**summary, "first_frame_source": files["first_frame_file"].source if first else None},
        )
        if inputs.get("dry_run"):
            return self._dry_run_payload(req, estimated)
        if not job_path.is_file() or inputs.get("confirm_resubmit"):
            gate = self._billing_gate(inputs, estimated)
            if gate:
                return gate
        return self._run(req, inputs, started)

    @staticmethod
    def _has_job(job_path) -> bool:
        return job_path.is_file()

    # -- Ark-compatible relays: reuse SeedanceArkVideo ------------------------
    def _execute_ark(self, inputs, operation, first, last, refs, duration, started) -> ToolResult:
        m = self.relay_model
        ark = _ArkPayloadBuilder()
        ark_inputs = dict(inputs)
        ark_inputs.update({"model": m.model, "operation": operation})
        for key in _FIRST_FRAME_KEYS + _LAST_FRAME_KEYS:
            ark_inputs.pop(key, None)
        if first:
            ark_inputs["reference_image_url" if first.startswith(("http://", "https://", "data:")) else "reference_image_path"] = first
        if last:
            ark_inputs["end_image_url" if last.startswith(("http://", "https://", "data:")) else "end_image_path"] = last
        if duration is not None:
            ark_inputs["duration"] = duration
        for key, value in m.defaults.items():
            if key not in {"params"}:
                ark_inputs.setdefault(key, value)
        try:
            payload = ark._build_payload(ark_inputs)
        except (TypeError, ValueError, OSError) as exc:
            return self._fail(f"Ark payload invalid: {exc}", code="bad_param")
        if inputs.get("extra_params"):
            payload.update(inputs["extra_params"])

        output_path, job_path = self._paths(inputs, f"{self.name}.mp4")
        estimated = self._estimated_cost_or_none(inputs)
        digest_payload = copy.deepcopy(payload)
        for item in digest_payload.get("content", []):
            for media in ("image_url", "audio_url", "video_url"):
                if isinstance(item.get(media), dict) and str(item[media].get("url", "")).startswith("data:"):
                    from hashlib import sha256

                    item[media]["url"] = "sha256:" + sha256(item[media]["url"].encode()).hexdigest()[:24]
        req = JobRequest(
            tool_name=self.name,
            operation=operation,
            output_path=output_path,
            job_path=job_path,
            fingerprint=self._fingerprint({"payload": digest_payload}),
            estimated_cost_usd=estimated,
            variables={},
            media_kind="video",
            summary={"payload": digest_payload},
        )
        if inputs.get("dry_run"):
            return ToolResult(
                success=True,
                data={"dry_run": True, "tool": self.name, "endpoint": m.endpoint,
                      "method": "POST", "path": "/contents/generations/tasks",
                      "body": digest_payload, "estimated_cost_usd": estimated,
                      "output_path": str(output_path), "job_path": str(job_path),
                      "billing_enabled": m.relay.billing_enabled},
            )
        if not job_path.is_file() or inputs.get("confirm_resubmit"):
            gate = self._billing_gate(inputs, estimated)
            if gate:
                return gate

        http = RelayHTTP(m)

        def submit(_req: JobRequest) -> dict[str, Any]:
            response = http.submit("POST", "/contents/generations/tasks", json_body=payload,
                                   timeout=m.submit_timeout_seconds)
            body = response.json()
            return {"task_id": body.get("id")}

        return self._run(req, inputs, started, submit_fn=submit, **self._ark_hooks(http))

    _ARK_POLL_SPEC = {"poll": {"status": "status", "success": ["succeeded"],
                               "failure": ["failed", "cancelled", "expired"],
                               "error": "error.message|error.code|error",
                               "result_url": "content.video_url"}}

    def _ark_hooks(self, http: RelayHTTP) -> dict[str, Any]:
        def poll(task_id: str) -> PollOutcome:
            return interpret_poll(self._ARK_POLL_SPEC, http.get_json(f"/contents/generations/tasks/{task_id}"))

        return {"poll_fn": poll}

    def _resume_hooks(self) -> dict[str, Any]:
        if self.relay_model.protocol == "ark_seedance":
            return self._ark_hooks(RelayHTTP(self.relay_model))
        return {}


class _ArkPayloadBuilder(SeedanceArkVideo):
    """Access to SeedanceArkVideo's request builder without registering a tool."""

    _registry_template = True

    def get_status(self):  # pragma: no cover - never registered
        from tools.base_tool import ToolStatus

        return ToolStatus.UNAVAILABLE


def build_registry_tools() -> list[BaseTool]:
    """Registry hook: one RelayVideo per video model in relay_providers.yaml."""
    return build_tools("video", RelayVideo)
