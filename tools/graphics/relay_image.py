"""Relay (中转站) image generation tools, one per configured model.

Protocols:
    openai_images   POST /images/generations (JSON) for text_to_image,
                    POST /images/edits (multipart, image[]) for image_to_image.
                    Accepts url or b64_json results.
    generic_async   declarative mapping (sync or async) for relays whose image
                    API is not OpenAI-shaped.

Built from ``relay_providers.yaml`` by ``build_registry_tools``.
"""

from __future__ import annotations

import copy
import time
from typing import Any

from tools.base_tool import BaseTool, ToolResult
from tools.relay.engine import JobRequest, RelayHTTP, get_path
from tools.relay.tooling import CONTROL_PROPS, RelayToolBase, build_tools, check_allowed


class RelayImage(RelayToolBase):
    capability = "image_generation"

    def _build_supports(self) -> dict[str, Any]:
        caps = self.relay_model.capabilities
        return {
            "text_to_image": "text_to_image" in caps,
            "image_edit": "image_to_image" in caps,
            "image_to_image": "image_to_image" in caps,
            "local_save": True,
            "async_resume": True,
        }

    def _build_input_schema(self) -> dict[str, Any]:
        m = self.relay_model
        props: dict[str, Any] = {
            "prompt": {"type": "string"},
            "model": {"type": "string", "enum": m.model_ids},
            "generation_mode": {"type": "string", "enum": [
                mode for mode, cap in (("generate", "text_to_image"), ("edit", "image_to_image"))
                if cap in m.capabilities
            ]},
            "size": {"type": "string", **({"enum": m.limits["sizes"]} if m.limits.get("sizes") else {})},
            "width": {"type": "integer"},
            "height": {"type": "integer"},
            "aspect_ratio": {"type": "string"},
            "quality": {"type": "string"},
            "negative_prompt": {"type": "string"},
            "seed": {"type": "integer"},
            **copy.deepcopy(CONTROL_PROPS),
        }
        if "image_to_image" in m.capabilities:
            props["image_path"] = {"type": "string"}
            props["image_paths"] = {"type": "array", "items": {"type": "string"}}
            props["image_url"] = {"type": "string"}
            props["image_urls"] = {"type": "array", "items": {"type": "string"}}
        return {"type": "object", "required": ["prompt"], "properties": props}

    def billable_units(self, inputs: dict[str, Any]) -> dict[str, float]:
        return {"images": 1}

    def _size(self, inputs: dict[str, Any]) -> Any:
        m = self.relay_model
        if inputs.get("size"):
            return inputs["size"]
        if inputs.get("width") and inputs.get("height"):
            return f"{int(inputs['width'])}x{int(inputs['height'])}"
        aspect = inputs.get("aspect_ratio")
        size_map = m.limits.get("size_map") or {}
        if aspect and aspect in size_map:
            return size_map[aspect]
        return m.defaults.get("size")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        started = time.time()
        m = self.relay_model
        resumed = self._resume_only(inputs, started)
        if resumed is not None:
            return resumed
        refs =[str(r) for r in (inputs.get("image_paths") or []) + (inputs.get("image_urls") or [])]
        refs += [str(inputs[k]) for k in ("image_path", "image_url") if inputs.get(k)]
        refs += [str(r) for r in (inputs.get("images") or [])]
        mode = inputs.get("generation_mode") or ("edit" if refs else "generate")
        operation = "image_to_image" if mode in {"edit", "precise_edit"} else "text_to_image"
        if operation == "image_to_image" and not refs:
            return self._fail("image_to_image needs image_path/image_paths/image_url", code="bad_input")
        if operation == "text_to_image" and refs:
            return self._fail("source images supplied but generation_mode is generate", code="bad_input")
        blocked = self._guard(inputs, operation)
        if blocked:
            return blocked
        if int(inputs.get("n") or 1) != 1:
            return self._fail("relay image tools produce one image per call; call once per image", code="bad_param")
        max_refs = int(m.limits.get("max_reference_images", 4))
        if len(refs) > max_refs:
            return self._fail(f"at most {max_refs} source images for {self.name}", code="bad_param")
        prompt = str(inputs.get("prompt") or "").strip()
        if not prompt:
            return self._fail("prompt is required", code="bad_input")
        size = self._size(inputs)
        problem = check_allowed("size", size, m.limits.get("sizes"))
        if problem:
            return self._fail(problem + ". Nothing was sent.", code="bad_param")

        try:
            images = [self._load_image(r) for r in refs]
        except Exception as exc:  # noqa: BLE001
            return self._fail(str(exc), code=getattr(exc, "code", "bad_image"))

        variables = {
            "model": m.model,
            "prompt": prompt,
            "negative_prompt": inputs.get("negative_prompt"),
            "size": size,
            "aspect_ratio": inputs.get("aspect_ratio", m.defaults.get("aspect_ratio")),
            "quality": inputs.get("quality", m.defaults.get("quality")),
            "seed": inputs.get("seed"),
            "extra_params": inputs.get("extra_params"),
        }
        files = {}
        if images:
            files["first_frame_file"] = images[0]
            if m.image_input != "multipart":
                variables["images"] = [self._encode(i) for i in images]
                variables["first_frame"] = variables["images"][0]
            variables["first_frame_file"] = "<file>"

        output_path, job_path = self._paths(inputs, f"{self.name}.png")
        estimated = self._estimated_cost_or_none(inputs)
        summary = {k: v for k, v in variables.items() if k not in {"images", "first_frame", "first_frame_file"} and v is not None}
        summary["images"] = [self._image_digest(i) for i in images]
        req = JobRequest(
            tool_name=self.name,
            operation=operation,
            output_path=output_path,
            job_path=job_path,
            fingerprint=self._fingerprint({"operation": operation, **summary}),
            estimated_cost_usd=estimated,
            variables=variables,
            files=files,
            media_kind="image",
            summary=summary,
        )
        if inputs.get("dry_run"):
            if m.protocol == "openai_images":
                return self._openai_dry_run(req, images, estimated)
            return self._dry_run_payload(req, estimated)
        if not job_path.is_file() or inputs.get("confirm_resubmit"):
            gate = self._billing_gate(inputs, estimated)
            if gate:
                return gate

        if m.protocol == "openai_images":
            http = RelayHTTP(m)
            return self._run(req, inputs, started, submit_fn=lambda r: self._openai_submit(http, r, images))
        return self._run(req, inputs, started)

    # -- OpenAI Images ----------------------------------------------------------
    def _openai_body(self, req: JobRequest) -> dict[str, Any]:
        v = req.variables
        body = {"model": v["model"], "prompt": v["prompt"], "n": 1}
        for key in ("size", "quality", "seed", "negative_prompt"):
            if v.get(key) is not None:
                body[key] = v[key]
        body.update(self.relay_model.defaults.get("params") or {})
        if v.get("extra_params"):
            body.update(v["extra_params"])
        return body

    def _edit_field(self, count: int) -> str:
        # gpt-image-* relays take image[]; dall-e-2 style relays take a single "image".
        return str(self.relay_model.request.get("edit_image_field") or "image[]")

    def _openai_submit(self, http: RelayHTTP, req: JobRequest, images: list) -> dict[str, Any]:
        body = self._openai_body(req)
        timeout = self.relay_model.submit_timeout_seconds
        if req.operation == "text_to_image":
            response = http.submit("POST", "/images/generations", json_body=body, timeout=timeout)
        else:
            if any(i.data is None for i in images):
                # The edits endpoint is multipart: URLs cannot be forwarded.
                from tools.relay.engine import SubmitRejected

                raise SubmitRejected("the /images/edits endpoint needs local image files, not URLs", code="bad_image")
            field = self._edit_field(len(images))
            files = [(field, (i.filename, i.data, i.mime)) for i in images]
            form = {k: str(v) for k, v in body.items()}
            response = http.submit("POST", "/images/edits", data=form, files=files, timeout=timeout)
        payload = response.json()
        url = get_path(payload, "data.0.url")
        b64 = get_path(payload, "data.0.b64_json")
        if b64:
            return {"result_url": f"data:image/png;base64,{b64}"}
        if url:
            return {"result_url": url}
        error = get_path(payload, "error.message|error")
        from tools.relay.engine import SubmitRejected

        raise SubmitRejected(f"relay returned no image: {http.redact(str(error or payload))[:300]}", code="no_result")

    def _openai_dry_run(self, req: JobRequest, images: list, estimated: Any) -> ToolResult:
        edit = req.operation == "image_to_image"
        return ToolResult(
            success=True,
            data={
                "dry_run": True,
                "tool": self.name,
                "endpoint": self.relay_model.endpoint,
                "method": "POST",
                "path": "/images/edits" if edit else "/images/generations",
                "body_format": "multipart" if edit else "json",
                "body": self._openai_body(req),
                "files": {self._edit_field(len(images)): [i.source for i in images]} if edit else {},
                "operation": req.operation,
                "estimated_cost_usd": estimated,
                "output_path": str(req.output_path),
                "job_path": str(req.job_path),
                "billing_enabled": self.relay_model.relay.billing_enabled,
            },
        )


def build_registry_tools() -> list[BaseTool]:
    """Registry hook: one RelayImage per image model in relay_providers.yaml."""
    return build_tools("image", RelayImage)
