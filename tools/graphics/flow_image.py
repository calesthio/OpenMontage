"""Nano Banana image generation billed to a Google Flow subscription.

Same transport as `flow_video`: Playwright attached over CDP to the user's
signed-in Chrome, driving the Flow UI. Image mode is switched with the "Hình
ảnh" radio, offers three Nano Banana models and five aspects, and — measured
2026-09-05 — charges 0 credits per image. The finished file is taken from the
tile's own "Tải xuống → 1K Kích thước gốc", a ~1K JPEG.

`lib/flow_driver.py` does the driving; this file is the registry contract.
"""

from __future__ import annotations

import os
import time
import uuid
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

# Short names -> Flow's own dropdown labels. Matched exactly: "Nano Banana 2"
# is a prefix of "Nano Banana 2 Lite".
_MODELS = {
    "Pro": "🍌 Nano Banana Pro",
    "2": "🍌 Nano Banana 2",
    "2 Lite": "🍌 Nano Banana 2 Lite",
}
_ASPECTS = ["1:1", "16:9", "9:16", "4:3", "3:4"]
_DEFAULT_CDP = "http://127.0.0.1:9222"


class FlowImage(BaseTool):
    name = "flow_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "flow"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["python:playwright"]
    install_instructions = (
        "Nano Banana images through your Google Flow subscription — no API key.\n"
        "  1. pip install playwright\n"
        "  2. Start Chrome:  python scripts/flow_chrome.py   (or flow-chrome.cmd)\n"
        "  3. In that window, sign in to https://flow.google.com once.\n"
        "Automating Flow may violate Google's terms of service."
    )
    agent_skills = ["flow-video"]

    capabilities = ["text_to_image", "multi_output"]
    supports = {
        "text_to_image": True,
        "multiple_outputs": True,
        "reference_image": True,    # via the prompt bar's "Thêm thành phần" picker
        "transparent_background": False,
        "offline": False,
        "no_api_key": True,
    }
    best_for = [
        "photographic or illustrated stills with no cash cost when a Google Flow subscription exists",
        "batches of variations (x4 per call) for sprite sheets, stickers, GIF frames",
        "machines with no image provider API key",
    ]
    not_good_for = [
        "unattended servers — needs a signed-in Chrome with a debugging port",
        "exact pixel sizes — Flow returns ~1K JPEGs at fixed aspects",
        "pipelines that need a stable provider contract (Flow's UI changes often)",
    ]
    fallback_tools = ["codex_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model_variant": {
                "type": "string",
                "enum": list(_MODELS),
                "default": "2",
                "description": "Pro = Nano Banana Pro (best), 2 = Nano Banana 2 (fast), 2 Lite = cheapest.",
            },
            "aspect_ratio": {"type": "string", "enum": _ASPECTS, "default": "1:1"},
            "n": {"type": "integer", "default": 1, "minimum": 1, "maximum": 4,
                  "description": "Images per call (Flow's x1..x4). Files are numbered _1.._n."},
            "output_path": {"type": "string", "description": "Base path; .jpg or .png (converted)."},
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Local image paths uploaded to the project library and dropped into "
                    "the prompt as reference chips. Use when the output must match a real "
                    "product, character or style rather than a text description of it."
                ),
            },
            "quality": {
                "type": "string",
                "default": "max",
                "description": (
                    "max: the highest tier the Flow plan allows, including its upscale rows "
                    "(rows marked 'Nâng cấp' are a paywall and are never clicked). "
                    "native: the size the model rendered at. "
                    "Or name a tier exactly — '1080p', '2K', '4K' — which fails loudly if Flow "
                    "does not offer it, rather than silently handing back another size."
                ),
            },

            "timeout_seconds": {"type": "integer", "default": 600, "minimum": 120, "maximum": 3600},
        },
    }

    resource_profile = ResourceProfile(cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True)
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "aspect_ratio", "model_variant", "n"]
    side_effects = [
        "writes image files next to output_path",
        "drives the user's open browser tab — the Flow UI will visibly change",
    ]
    user_visible_verification = ["Open the images and check prompt adherence and artifacts"]

    def get_status(self) -> ToolStatus:
        try:
            import playwright  # noqa: F401
        except ImportError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def _lock_path(self) -> Path:
        # Shared with flow_video: it is the same browser tab.
        return Path.home() / ".openmontage" / "flow_video.lock"

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.flow_driver import FlowDriver, FlowError
        from tools.video.flow_video import FlowVideo

        if self.get_status() is ToolStatus.UNAVAILABLE:
            return ToolResult(success=False, error="Playwright is not installed. " + self.install_instructions)

        cdp_url = os.environ.get("FLOW_CDP_URL", _DEFAULT_CDP)
        blocker = FlowVideo._cdp_blocker(cdp_url)
        if blocker:
            return ToolResult(success=False, error=blocker)

        n = max(1, min(4, int(inputs.get("n", 1))))
        base = Path(inputs.get("output_path") or f"flow_image_{uuid.uuid4().hex[:8]}.jpg").resolve()
        want_png = base.suffix.lower() == ".png"
        stems = [base.with_suffix("")] if n == 1 else [base.with_name(f"{base.stem}_{i + 1}") for i in range(n)]
        jpg_paths = [s.with_suffix(".jpg") for s in stems]

        job = {
            "prompt": inputs["prompt"],
            "model": _MODELS[inputs.get("model_variant", "2")],
            "aspect_ratio": inputs.get("aspect_ratio", "1:1"),
            "count": n,
            "output_paths": [str(p) for p in jpg_paths],
            "quality": inputs.get("quality", "max"),
            "reference_images": [str(Path(r).resolve()) for r in
                                 (inputs.get("reference_images") or [])],
            "timeout_seconds": int(inputs.get("timeout_seconds", 600)),
        }
        missing = [r for r in job["reference_images"] if not Path(r).is_file()]
        if missing:
            return ToolResult(success=False,
                              error=f"reference_images not found: {missing}")

        start = time.time()
        lock = self._lock_path()
        try:
            try:
                lock.parent.mkdir(parents=True, exist_ok=True)
                os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            except FileExistsError:
                return ToolResult(success=False, error=(
                    f"Another Flow generation is in progress ({lock}). There is one browser tab, "
                    f"so runs are serialized. Delete the lock file if a previous run crashed."))
            try:
                with FlowDriver(cdp_url, os.environ.get("FLOW_PROJECT_URL")) as driver:
                    result = driver.generate_image(job)
            except FlowError as exc:
                return ToolResult(success=False, error=f"Flow image generation failed: {exc}")
            except Exception as exc:  # noqa: BLE001 - surface, never swallow
                return ToolResult(success=False, error=f"Flow driver error: {exc}")
        finally:
            lock.unlink(missing_ok=True)

        outputs = [str(p) for p in jpg_paths]
        if want_png:
            outputs = [_to_png(p) for p in jpg_paths]

        return ToolResult(
            success=True,
            data={
                "provider": "flow",
                "gateway": "playwright_cdp",
                "prompt": job["prompt"],
                "aspect_ratio": job["aspect_ratio"],
                "n": n,
                "output": outputs[0],
                "outputs": outputs,
                "format": "png" if want_png else "jpg",
                "billing": "google_flow_subscription",
                "flow_model": result.get("model"),
                "flow_credits": result.get("credits"),
                "flow_media_id": result.get("media_id"),
                "flow_download_row": result.get("download_row"),
            },
            artifacts=outputs,
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=result.get("model"),
        )


def _to_png(jpg: Path) -> str:
    from PIL import Image

    png = jpg.with_suffix(".png")
    Image.open(jpg).convert("RGB").save(png)
    jpg.unlink(missing_ok=True)
    return str(png)
