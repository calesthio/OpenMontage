"""Shared BaseTool behaviour for config-driven relay adapters.

One tool instance is built per configured model, so every registry entry has
an exact ``supports`` matrix, an exact model id, a ``hosting_provider`` equal
to the relay name, and its own price. Selectors then route by the normal
``preferred_tool`` / ``hosting_provider`` / ``model`` constraints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)
from tools.provider_pricing import PriceQuoteRequired
from tools.relay.config import RelayModel, try_load_relay_config
from tools.relay.engine import (
    ImageInput,
    JobRequest,
    JobResult,
    JobRunner,
    RelayError,
    default_job_path,
    encode_image,
    file_sha256,
    fingerprint,
    load_image_input,
    load_job,
    protocol_spec,
    render_template,
)

RELAY_SKILL = "relay-providers"

# Width x height used when the relay wants a ``size`` and the caller gave an
# aspect ratio + resolution. Override per model with ``limits.size_map``.
_SIZE_TABLE = {
    "480p": {"16:9": "854x480", "9:16": "480x854", "1:1": "480x480", "4:3": "640x480", "3:4": "480x640"},
    "720p": {"16:9": "1280x720", "9:16": "720x1280", "1:1": "720x720", "4:3": "960x720", "3:4": "720x960"},
    "1080p": {"16:9": "1920x1080", "9:16": "1080x1920", "1:1": "1080x1080", "4:3": "1440x1080", "3:4": "1080x1440"},
}

_STABILITY = {
    "experimental": ToolStability.EXPERIMENTAL,
    "beta": ToolStability.BETA,
    "production": ToolStability.PRODUCTION,
}

CONTROL_PROPS = {
    "output_path": {"type": "string", "description": "Where the result is saved (under projects/<id>/assets/...)."},
    "job_path": {
        "type": "string",
        "description": "Job record path. Default <output_path>.relay-job.json. Re-calling resumes, never resubmits.",
    },
    "resume_job": {"type": "object", "description": "resume_job object returned by a previous pending call."},
    "confirm_resubmit": {
        "type": "boolean",
        "description": "Only after user approval: allow a NEW paid submit when the recorded one failed or has an unknown outcome.",
    },
    "allow_unpriced": {
        "type": "boolean",
        "description": "Only after user approval: run a model whose price is not configured.",
    },
    "dry_run": {"type": "boolean", "description": "Show the exact request mapping and cost; send nothing."},
    "extra_params": {
        "type": "object",
        "description": "Extra relay-native body fields merged into the request (provider-specific).",
    },
    "scene_id": {"type": "string"},
}


class RelayToolBase(BaseTool):
    """Base for relay tools. Never auto-instantiated by the registry."""

    _registry_template = True  # tool_registry skips classes carrying this flag
    is_relay_tool = True

    tier = ToolTier.GENERATE
    runtime = ToolRuntime.API
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, disk_mb=500, network_required=True)
    fallback_tools: list[str] = []  # relay tools never fall back to other paid vendors

    # filled per instance ----------------------------------------------------
    def __init__(self, model: RelayModel):
        self.relay_model = model
        self.name = model.tool_name
        self.provider = model.relay.name
        self.hosting_provider = model.relay.name
        self.version = "0.1.0"
        self.stability = _STABILITY.get(model.stability, ToolStability.EXPERIMENTAL)
        self.dependencies = [f"env:{model.relay.api_key_env}"]
        self.install_instructions = (
            f"Set {model.relay.api_key_env} in .env (the key for relay '{model.relay.name}'). "
            "The relay itself is defined in relay_providers.yaml — see docs/RELAY_PROVIDERS.zh-CN.md."
        )
        self.agent_skills = [RELAY_SKILL, *[s for s in model.agent_skills if s != RELAY_SKILL]]
        self.best_for = list(model.best_for) or [f"{model.display_name} via relay {model.relay.name}"]
        self.not_good_for = list(model.not_good_for)
        self.capabilities = sorted(model.capabilities)
        self.supports = self._build_supports()
        self.input_schema = self._build_input_schema()
        self.side_effects = [
            f"submits a billable request to relay '{model.relay.name}' ({model.endpoint})",
            "writes the result and a <output>.relay-job.json record next to output_path",
        ]
        self.user_visible_verification = [
            "Open the downloaded file; relay URLs expire, the local file is canonical",
        ]

    # subclasses -------------------------------------------------------------
    def _build_supports(self) -> dict[str, Any]:
        raise NotImplementedError

    def _build_input_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    # status -----------------------------------------------------------------
    def status_reason(self) -> Optional[str]:
        relay = self.relay_model.relay
        if not relay.api_key():
            return f"env var {relay.api_key_env} is not set"
        if not relay.billing_enabled:
            return (
                f"relay '{relay.name}' has live: false — real billable calls are disabled "
                "until the mock tests pass and you set live: true"
            )
        return None

    def get_status(self) -> ToolStatus:
        # live: false keeps the tool AVAILABLE on purpose: selectors must still
        # route to it (and get an explicit "live disabled" refusal from
        # execute) rather than skip it and pick some other paid vendor.
        if not self.relay_model.relay.api_key():
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        m = self.relay_model
        info.update(
            {
                "hosting_provider": m.relay.name,
                "is_relay_tool": True,
                "status_reason": self.status_reason(),
                "model_catalog": {
                    model_id: {
                        "kind": m.kind,
                        "protocol": m.protocol,
                        "capabilities": sorted(m.capabilities),
                        "display_name": m.display_name,
                    }
                    for model_id in m.model_ids
                },
                "relay": {
                    "name": m.relay.name,
                    "display_name": m.relay.display_name,
                    "endpoint": m.endpoint,
                    "protocol": m.protocol,
                    "live": m.relay.live,
                    "billing_enabled": m.relay.billing_enabled,
                    "api_key_env": m.relay.api_key_env,
                    "image_input": m.image_input,
                    "limits": m.limits,
                    "defaults": m.defaults,
                    "pricing": {
                        k: v
                        for k, v in vars(m.pricing).items()
                        if v is not None
                    },
                    "unsupported_capabilities": sorted(
                        self._all_capabilities() - set(m.capabilities)
                    ),
                },
            }
        )
        if not m.relay.billing_enabled:
            info["setup_offer"] = {
                "kind": "relay_live_switch",
                "fix_complexity": "1-minute config edit",
                "instructions": (
                    "Run `python -m pytest tests/tools/test_relay_providers.py` and "
                    f"`python -m tools.relay check`, then set live: true for relay '{m.relay.name}'."
                ),
            }
        return info

    def _all_capabilities(self) -> set[str]:
        from tools.relay.config import KIND_CAPABILITIES

        return set(KIND_CAPABILITIES[self.relay_model.kind])

    # pricing ----------------------------------------------------------------
    def billable_units(self, inputs: dict[str, Any]) -> dict[str, float]:
        return {}

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        pricing = self.relay_model.pricing
        if not pricing.configured:
            raise PriceQuoteRequired(
                f"no price configured for {self.name}; add pricing to relay_providers.yaml "
                "or pass allow_unpriced=true after the user approves an unpriced call"
            )
        units = self.billable_units(inputs)
        total = pricing.per_request or 0.0
        if pricing.per_image is not None:
            total += pricing.per_image * units.get("images", 1)
        per_second = pricing.per_second
        if pricing.per_second_by_resolution:
            resolution = str(inputs.get("resolution") or self.relay_model.defaults.get("resolution") or "").upper()
            if resolution not in pricing.per_second_by_resolution:
                raise PriceQuoteRequired(f"no per-second price for {self.name} at resolution {resolution!r}")
            per_second = pricing.per_second_by_resolution[resolution]
        if per_second is not None:
            total += per_second * units.get("seconds", 0)
        if pricing.per_1k_chars is not None:
            total += pricing.per_1k_chars * units.get("chars", 0) / 1000.0
        return round(pricing.to_usd(total), 4)

    def _estimated_cost_or_none(self, inputs: dict[str, Any]) -> Optional[float]:
        try:
            return self.estimate_cost(inputs)
        except PriceQuoteRequired:
            return None

    # shared execution guards -----------------------------------------------
    def _guard(self, inputs: dict[str, Any], operation: str) -> Optional[ToolResult]:
        m = self.relay_model
        requested_model = inputs.get("model") or inputs.get("model_id") or inputs.get("model_name")
        if requested_model and requested_model not in m.model_ids:
            return self._fail(
                f"{self.name} serves model {m.model!r}, not {requested_model!r}. "
                "Pick the tool that serves that model; models are never swapped silently.",
                code="model_mismatch",
            )
        if operation not in m.capabilities:
            return self._fail(
                f"{self.name} ({m.model} via {m.relay.name}) does not support {operation}. "
                f"Declared capabilities: {sorted(m.capabilities)}. Nothing was sent.",
                code="unsupported_capability",
            )
        return None

    def _billing_gate(self, inputs: dict[str, Any], estimated: Optional[float]) -> Optional[ToolResult]:
        m = self.relay_model
        if not m.relay.billing_enabled:
            return self._fail(
                f"relay '{m.relay.name}' is not enabled for real billable calls (live: false). "
                "Verify with the mock tests first, then set live: true in relay_providers.yaml.",
                code="live_disabled",
            )
        if estimated is None and not inputs.get("allow_unpriced"):
            return self._fail(
                f"{self.name} has no configured price, so the budget cannot account for it. "
                "Add pricing in relay_providers.yaml, or pass allow_unpriced=true once the user approves.",
                code="price_required",
            )
        return None

    def _fail(self, message: str, *, code: str, data: Optional[dict] = None) -> ToolResult:
        payload = {"error_code": code, "tool": self.name, "relay": self.relay_model.relay.name}
        payload.update(data or {})
        return ToolResult(success=False, error=message, data=payload, cost_usd=0.0)

    def _paths(self, inputs: dict[str, Any], default_name: str) -> tuple[Path, Path]:
        resume = inputs.get("resume_job") or {}
        job_path_value = inputs.get("job_path") or (resume.get("job_path") if isinstance(resume, dict) else None)
        output = inputs.get("output_path")
        if not output and job_path_value:
            job = load_job(Path(job_path_value)) or {}
            output = job.get("output_path")
        output_path = Path(output or default_name)
        job_path = Path(job_path_value) if job_path_value else default_job_path(output_path)
        return output_path, job_path

    def _to_tool_result(self, result: JobResult, started: float) -> ToolResult:
        import time

        data = dict(result.data)
        data.setdefault("provider", self.provider)
        data.setdefault("tool", self.name)
        return ToolResult(
            success=result.success,
            data=data,
            artifacts=result.artifacts,
            error=result.error,
            cost_usd=result.cost_usd,
            duration_seconds=round(time.time() - started, 2),
            model=self.relay_model.model,
        )

    def _resume_hooks(self) -> dict[str, Any]:
        """Protocol-specific poll/download callables for resume-only calls."""
        return {}

    def _resume_only(self, inputs: dict[str, Any], started: float) -> Optional[ToolResult]:
        """Continue a recorded job from ``resume_job`` / ``job_path`` alone.

        Needs no prompt or media: it can only poll and download the recorded
        task. It never resubmits (that requires the full original inputs).
        """
        resume = inputs.get("resume_job")
        job_path_value = inputs.get("job_path") or (resume.get("job_path") if isinstance(resume, dict) else None)
        if not job_path_value:
            return None
        job_path = Path(job_path_value)
        job = load_job(job_path)
        if not job:
            return None
        if job.get("tool") != self.name:
            return self._fail(f"job {job_path} belongs to {job.get('tool')}, not {self.name}", code="job_mismatch")
        req = JobRequest(
            tool_name=self.name,
            operation=str(job.get("operation")),
            output_path=Path(inputs.get("output_path") or job["output_path"]),
            job_path=job_path,
            fingerprint=str(job.get("fingerprint")),
            estimated_cost_usd=job.get("estimated_cost_usd"),
            variables={},
            media_kind=self.relay_model.kind,
        )
        safe_inputs = {k: v for k, v in inputs.items() if k != "confirm_resubmit"}
        safe_inputs["resume_job"] = {"job_path": str(job_path)}
        return self._run(req, safe_inputs, started, **self._resume_hooks())

    def _run(self, req: JobRequest, inputs: dict[str, Any], started: float, **hooks: Any) -> ToolResult:
        runner = JobRunner(self.relay_model)
        try:
            result = runner.run(req, inputs, **hooks)
        except RelayError as exc:
            return self._fail(runner.http.redact(str(exc)), code=exc.code, data={"job_path": str(req.job_path)})
        return self._to_tool_result(result, started)

    def _dry_run_payload(self, req: JobRequest, estimated: Optional[float]) -> ToolResult:
        spec = protocol_spec(self.relay_model)
        submit = spec.get("submit") or {}
        body = render_template(submit.get("body") or {}, _summarize_media(req.variables))
        headers = render_template(submit.get("headers") or {}, {**req.variables, "idempotency_key": "<per-job persistent UUID>"})
        return ToolResult(
            success=True,
            data={
                "dry_run": True,
                "tool": self.name,
                "relay": self.relay_model.relay.name,
                "endpoint": self.relay_model.endpoint,
                "method": submit.get("method", "POST"),
                "path": submit.get("path"),
                "body_format": submit.get("body_format", "json"),
                "body": body,
                "request_headers": headers,
                "files": {k: v.source for k, v in req.files.items()},
                "operation": req.operation,
                "estimated_cost_usd": estimated,
                "cost_status": "estimated_from_config" if estimated is not None else "unpriced",
                "output_path": str(req.output_path),
                "job_path": str(req.job_path),
                "billing_enabled": self.relay_model.relay.billing_enabled,
            },
            cost_usd=0.0,
        )

    # media helpers ----------------------------------------------------------
    def _load_image(self, ref: Any) -> ImageInput:
        max_mb = float(self.relay_model.limits.get("max_image_mb", 10))
        image = load_image_input(ref, max_mb=max_mb)
        max_kb = self.relay_model.limits.get("max_upload_kb")
        if max_kb and image.data is not None and len(image.data) > float(max_kb) * 1024:
            image = _shrink_image(image, int(float(max_kb) * 1024))
        return image

    def _encode(self, image: ImageInput) -> Any:
        return encode_image(image, self.relay_model.image_input)

    @staticmethod
    def _image_digest(image: ImageInput) -> str:
        if image.data is None:
            return image.url or image.source
        return image.digest

    def _fingerprint(self, payload: dict[str, Any]) -> str:
        return fingerprint({"tool": self.name, "model": self.relay_model.model, **payload})


def _summarize_media(variables: dict[str, Any]) -> dict[str, Any]:
    """Replace data URIs / base64 with short descriptions for dry-run output."""

    def short(value: Any) -> Any:
        if isinstance(value, str) and value.startswith("data:"):
            return f"<data-uri {value[5:value.find(';')]} {len(value)} chars>"
        if isinstance(value, str) and len(value) > 512:
            return f"<base64 {len(value)} chars>"
        if isinstance(value, list):
            return [short(v) for v in value]
        if isinstance(value, dict):
            return {k: short(v) for k, v in value.items()}
        return value

    return {k: short(v) for k, v in variables.items()}


def _shrink_image(image: ImageInput, max_bytes: int) -> ImageInput:
    """Re-encode an oversized upload as JPEG (then downscale) to fit ``max_bytes``.

    Only the bytes sent to the relay change; the user's file on disk is untouched.
    Same pixels/aspect are kept whenever quality reduction alone is enough.
    """
    import io

    from PIL import Image

    with Image.open(io.BytesIO(image.data)) as src:
        img = src.convert("RGB")
    scale = 1.0
    for _ in range(8):
        candidate = img if scale == 1.0 else img.resize(
            (max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS
        )
        for quality in (92, 85, 75):
            buf = io.BytesIO()
            candidate.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= max_bytes:
                return ImageInput(source=image.source, data=buf.getvalue(), mime="image/jpeg",
                                  filename="image.jpg", url=None)
        scale *= 0.8
    raise RelayError(f"cannot shrink {image.source} under {max_bytes // 1024} KB for this model", code="bad_image")


def size_for(model: RelayModel, aspect_ratio: Optional[str], resolution: Optional[str]) -> Optional[str]:
    size_map = model.limits.get("size_map") or {}
    if aspect_ratio and aspect_ratio in size_map:
        return str(size_map[aspect_ratio])
    if aspect_ratio and resolution:
        return _SIZE_TABLE.get(str(resolution).lower(), {}).get(aspect_ratio)
    return None


def check_allowed(name: str, value: Any, allowed: Any) -> Optional[str]:
    if value is None or not allowed:
        return None
    if isinstance(allowed, list) and value not in allowed and str(value) not in [str(a) for a in allowed]:
        return f"{name}={value!r} is not supported by this model; allowed: {allowed}"
    return None


def build_tools(kind: str, factory) -> list[BaseTool]:
    """Instantiate one tool per configured model of ``kind``."""
    config = try_load_relay_config()
    tools: list[BaseTool] = []
    for model in config.models_of_kind(kind):
        try:
            tool = factory(model)
        except Exception:  # noqa: BLE001 — a bad entry must not break discovery
            continue
        if tool is not None:
            tools.append(tool)
    return tools


__all__ = [
    "CONTROL_PROPS",
    "RelayToolBase",
    "build_tools",
    "check_allowed",
    "file_sha256",
    "size_for",
]
