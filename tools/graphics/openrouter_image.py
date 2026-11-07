"""Image generation through OpenRouter's chat-completions endpoint.

OpenRouter does not expose a dedicated /images route. Image models are driven
through /chat/completions and return their result in `message.images[]` as a
data: URL, not in the text body. That is the one non-obvious thing about this
API and the reason this wrapper exists.

There is no model literally called `gpt-image-2`; the OpenAI image model on
OpenRouter is `openai/gpt-5.4-image-2`. It takes image inputs, which is what
lets a reference photo carry a printed design that must never be described in
words (see skills/creative/printed-apparel-ad.md).
"""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
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

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
# `openai/gpt-5.4-image-2` was the first choice but it ALWAYS returns 1024x1024
# and silently ignores aspect_ratio - verified, including an explicit "do NOT
# output a square image" in the prompt. The Gemini image models honour it, so
# they are the default for anything that has to be vertical.
DEFAULT_MODEL = "google/gemini-3-pro-image"
SQUARE_ONLY = ("openai/gpt-5.4-image-2", "openai/gpt-5-image", "openai/gpt-5-image-mini")


def _key() -> str | None:
    for name in ("OPENROUTER_KEY", "OPENROUTER_API_KEY"):
        v = os.environ.get(name)
        if v:
            return v
    env = Path(__file__).resolve().parents[2] / ".env"
    if env.is_file():
        for line in env.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\s*(OPENROUTER_KEY|OPENROUTER_API_KEY)\s*=\s*(.*)$", line)
            if m:
                v = m.group(2).strip().strip('"').strip("'")
                if v:
                    return v
    return None


def _data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


class OpenRouterImage(BaseTool):
    name = "openrouter_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "openrouter"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:OPENROUTER_KEY"]
    install_instructions = (
        "Put an OpenRouter key in .env:\n"
        "  OPENROUTER_KEY=sk-or-v1-...\n"
        "Keys: https://openrouter.ai/keys"
    )

    capabilities = ["text_to_image", "image_to_image", "reference_image"]
    supports = {"reference_image": True, "multi_reference": True}
    best_for = [
        "generating a scene that must match a real product photo exactly",
        "image generation without a browser session",
    ]
    not_good_for = ["free generation (this one bills per call)"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {"type": "string", "default": DEFAULT_MODEL},
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Local image paths sent as inputs; the model matches them.",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "auto"],
                "description": (
                    "Honoured by the Gemini image models (9:16 -> 768x1376). "
                    "MUST be sent alone: adding `resolution` or `size` silently "
                    "reverts the output to 1024x1024 square. Measured, not assumed."
                ),
            },
            "output_path": {"type": "string"},
            "timeout_seconds": {"type": "integer", "default": 300},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50,
                                       network_required=True)
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["429", "500", "502", "503"])
    side_effects = ["writes an image file", "bills the OpenRouter account"]
    user_visible_verification = ["Open the image and check it matches the reference"]

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if _key() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # billed per token by OpenRouter; not a fixed per-image price

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        key = _key()
        if not key:
            return ToolResult(success=False, error="OPENROUTER_KEY not set. " + self.install_instructions)

        refs = [Path(r) for r in (inputs.get("reference_images") or [])]
        missing = [str(r) for r in refs if not r.is_file()]
        if missing:
            return ToolResult(success=False, error=f"reference_images not found: {missing}")

        content: list[dict] = [{"type": "text", "text": inputs["prompt"]}]
        for r in refs:
            content.append({"type": "image_url", "image_url": {"url": _data_url(r)}})

        model = inputs.get("model", DEFAULT_MODEL)
        payload_body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "modalities": ["image", "text"],
        }
        ar = inputs.get("aspect_ratio")
        if ar and ar != "auto":
            if model in SQUARE_ONLY:
                return ToolResult(success=False, error=(
                    f"{model} ignores aspect_ratio and always returns 1024x1024. "
                    f"Use a Gemini image model for {ar}."))
            # Sent ALONE on purpose - see the schema note.
            payload_body["aspect_ratio"] = ar
        body = json.dumps(payload_body).encode()

        req = urllib.request.Request(ENDPOINT, data=body, headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/openmontage",
            "X-Title": "OpenMontage",
        })

        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=inputs.get("timeout_seconds", 300)) as r:
                payload = json.load(r)
        except urllib.error.HTTPError as e:
            return ToolResult(success=False, error=f"HTTP {e.code}: {e.read()[:600].decode(errors='replace')}")
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, error=f"{type(e).__name__}: {e}")

        msg = (payload.get("choices") or [{}])[0].get("message") or {}
        # The image lives in message.images[], NOT in message.content.
        images = msg.get("images") or []
        if not images:
            return ToolResult(
                success=False,
                error=f"no image returned; text was: {str(msg.get('content'))[:300]!r}")

        url = images[0].get("image_url", {}).get("url") or images[0].get("url", "")
        if not url.startswith("data:"):
            return ToolResult(success=False, error=f"unexpected image payload: {url[:120]!r}")
        raw = base64.b64decode(url.split(",", 1)[1])

        out = Path(inputs.get("output_path") or "openrouter_image.png")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(raw)

        return ToolResult(success=True, data={
            "provider": self.provider,
            "model": model,
            "output": str(out),
            "bytes": len(raw),
            "elapsed_seconds": round(time.time() - start, 1),
            "usage": payload.get("usage", {}),
        })
