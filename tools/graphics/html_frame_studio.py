"""HTML Scene Studio: deterministic HTML -> frame sequence -> video tooling.

Renders a static HTML scene through named visual states in headless
Chromium (Playwright) and captures one PNG per state, plus:

- ``frames_manifest.json`` — frame -> step -> hold-duration mapping, and
- ``frames.txt``            — a ready ffmpeg concat-demuxer file, so
  ``ffmpeg -f concat -i frames.txt ...`` assembles the video with the
  intended per-step timing. No new assembly engine: frames feed the
  existing video_post tooling like any other frame sequence.

Two step styles:

- Declarative (recommended): the scene reacts to ``<body data-step="N">``;
  each step only sets the number. Self-documenting, portable, no JS blobs.
- Imperative escape hatch: arbitrary ``evaluate`` JS per step for DOM
  surgery that CSS states cannot express.

Steps advance deterministically: apply -> settle (rAF flush + wait_ms) ->
screenshot. Fonts/animations that need real time should be driven by the
step styles themselves, not by wall-clock hoping.
"""

from __future__ import annotations

import asyncio
import json
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

_DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
_DEFAULT_DURATION = 2.0  # seconds each frame is held in assembly
_DEFAULT_WAIT_MS = 150  # settle time after applying a step


class HtmlFrameStudio(BaseTool):
    name = "html_frame_studio"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "graphics"
    provider = "playwright"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL  # headless Chromium, no API

    dependencies = ["cmd:python3", "pip:playwright"]
    install_instructions = (
        "Install HTML Scene Studio:\n"
        "  pip install playwright\n"
        "  playwright install chromium"
    )
    agent_skills = ["html-frame-studio"]

    capabilities = [
        "html_to_frames",
        "state_stepped_capture",
        "transparent_background",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": False,
        "offline": True,
        "native_audio": False,
    }
    best_for = [
        "grid/table/board animations (spreadsheets, chess, seat maps)",
        "diagram and timeline reveals driven by CSS states",
        "dashboard-style scenes with exact typography control",
        "frame-exact visual storytelling without a React toolchain",
    ]
    not_good_for = [
        "footage-style photoreal motion (use video generation)",
        "reactive runtime-heavy web apps (use screen recording)",
    ]

    input_schema = {
        "type": "object",
        "required": ["html_path", "output_dir", "steps"],
        "properties": {
            "html_path": {
                "type": "string",
                "description": "Path to the scene HTML file (self-contained; inline CSS/JS)",
            },
            "output_dir": {
                "type": "string",
                "description": "Directory for frames + frames_manifest.json + frames.txt",
            },
            "steps": {
                "type": "array",
                "minItems": 1,
                "description": "Ordered visual states; one PNG is captured per step",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Human label recorded in the manifest",
                        },
                        "data_step": {
                            "type": "integer",
                            "description": "Sets <body data-step=\"N\">; scene CSS reacts to it (declarative style)",
                        },
                        "evaluate": {
                            "type": "string",
                            "description": "JS evaluated in the page before capture (imperative escape hatch)",
                        },
                        "wait_ms": {
                            "type": "number",
                            "default": 150,
                            "description": "Settle time after applying the step (with rAF flush)",
                        },
                        "duration": {
                            "type": "number",
                            "default": 2.0,
                            "description": "Seconds the frame is held in the concat/manifest timing",
                        },
                    },
                },
            },
            "viewport": {
                "type": "object",
                "description": "Capture size in CSS pixels",
                "properties": {
                    "width": {"type": "integer", "default": 1920},
                    "height": {"type": "integer", "default": 1080},
                },
            },
            "device_scale_factor": {
                "type": "number",
                "default": 1,
                "description": "2 = retina-sharp PNGs at 2x pixel size",
            },
            "transparent": {
                "type": "boolean",
                "default": False,
                "description": "Capture with omit_background (scene must not paint a body background)",
            },
            "full_page": {
                "type": "boolean",
                "default": False,
                "description": "Capture the full scrollable page instead of the viewport",
            },
            "frame_prefix": {
                "type": "string",
                "default": "frame",
                "description": "PNG filename prefix; files are zero-padded frame_0001.png ...",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=512, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["html_path", "steps", "viewport", "device_scale_factor"]
    side_effects = ["writes PNG frames and manifest files to output_dir"]
    user_visible_verification = ["Inspect frames and manifest in output_dir"]

    # ---- Pure helpers (unit-testable without a browser) ----

    @staticmethod
    def _validate_steps(steps: list[dict[str, Any]]) -> list[str]:
        errors: list[str] = []
        if not isinstance(steps, list) or not steps:
            return ["steps must be a non-empty list"]
        for i, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                errors.append(f"step {i}: must be an object")
                continue
            if "data_step" not in step and "evaluate" not in step:
                errors.append(f"step {i}: needs 'data_step' or 'evaluate'")
            if "data_step" in step and not isinstance(step["data_step"], int):
                errors.append(f"step {i}: 'data_step' must be an integer")
            duration = step.get("duration", _DEFAULT_DURATION)
            if not isinstance(duration, (int, float)) or duration <= 0:
                errors.append(f"step {i}: 'duration' must be a positive number")
            wait_ms = step.get("wait_ms", _DEFAULT_WAIT_MS)
            if not isinstance(wait_ms, (int, float)) or wait_ms < 0:
                errors.append(f"step {i}: 'wait_ms' must be >= 0")
        return errors

    @staticmethod
    def _data_step_js(data_step: int) -> str:
        return f'document.body.dataset.step = "{int(data_step)}"'

    @staticmethod
    def _frame_name(prefix: str, index: int) -> str:
        return f"{prefix}_{index:04d}.png"

    @staticmethod
    def _build_manifest(
        steps: list[dict[str, Any]],
        *,
        html_path: str,
        viewport: dict[str, int],
        device_scale_factor: float,
        transparent: bool,
        frame_prefix: str,
    ) -> dict[str, Any]:
        frames = []
        total = 0.0
        for i, step in enumerate(steps, 1):
            duration = float(step.get("duration", _DEFAULT_DURATION))
            total += duration
            frames.append(
                {
                    "file": HtmlFrameStudio._frame_name(frame_prefix, i),
                    "index": i,
                    "step": step.get("name") or (
                        f"data_step={step['data_step']}" if "data_step" in step else "evaluate"
                    ),
                    "duration": duration,
                }
            )
        return {
            "tool": "html_frame_studio",
            "html": html_path,
            "viewport": viewport,
            "device_scale_factor": device_scale_factor,
            "transparent": transparent,
            "frames": frames,
            "total_duration": round(total, 3),
            "concat_file": "frames.txt",
        }

    @staticmethod
    def _concat_lines(manifest: dict[str, Any]) -> str:
        # ffmpeg concat demuxer: durations apply to the preceding file.
        # The final file is repeated so its duration is honored.
        lines: list[str] = []
        for frame in manifest["frames"]:
            lines.append(f"file '{frame['file']}'")
            lines.append(f"duration {frame['duration']}")
        if manifest["frames"]:
            lines.append(f"file '{manifest['frames'][-1]['file']}'")
        return "\n".join(lines) + "\n"

    # ---- Status ----

    def get_status(self) -> ToolStatus:
        try:
            import playwright.async_api  # noqa: F401
        except ImportError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Local headless Chromium, no cost

    # ---- Execution ----

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        errors = self._validate_steps(inputs.get("steps"))
        if errors:
            return ToolResult(success=False, error="Invalid steps: " + "; ".join(errors))

        html_path = Path(inputs["html_path"])
        if not html_path.is_file():
            return ToolResult(success=False, error=f"Scene HTML not found: {html_path}")

        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="playwright is not installed. pip install playwright && playwright install chromium",
            )

        start = time.time()
        try:
            result = asyncio.run(
                self._render(
                    html_path=html_path,
                    output_dir=Path(inputs["output_dir"]),
                    steps=inputs["steps"],
                    viewport=inputs.get("viewport") or dict(_DEFAULT_VIEWPORT),
                    device_scale_factor=float(inputs.get("device_scale_factor", 1)),
                    transparent=bool(inputs.get("transparent", False)),
                    full_page=bool(inputs.get("full_page", False)),
                    frame_prefix=inputs.get("frame_prefix", "frame"),
                )
            )
        except Exception as exc:
            return ToolResult(success=False, error=f"HTML frame render failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    async def _render(
        self,
        *,
        html_path: Path,
        output_dir: Path,
        steps: list[dict[str, Any]],
        viewport: dict[str, int],
        device_scale_factor: float,
        transparent: bool,
        full_page: bool,
        frame_prefix: str,
    ) -> ToolResult:
        from playwright.async_api import async_playwright

        viewport = {
            "width": int(viewport.get("width", _DEFAULT_VIEWPORT["width"])),
            "height": int(viewport.get("height", _DEFAULT_VIEWPORT["height"])),
        }
        manifest = self._build_manifest(
            steps,
            html_path=str(html_path),
            viewport=viewport,
            device_scale_factor=device_scale_factor,
            transparent=transparent,
            frame_prefix=frame_prefix,
        )

        output_dir.mkdir(parents=True, exist_ok=True)
        captured: list[Path] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            context = await browser.new_context(
                viewport=viewport,
                device_scale_factor=device_scale_factor,
            )
            page = await context.new_page()
            await page.goto(html_path.resolve().as_uri(), wait_until="load")

            for i, step in enumerate(steps, 1):
                if "data_step" in step:
                    await page.evaluate(self._data_step_js(step["data_step"]))
                if step.get("evaluate"):
                    await page.evaluate(step["evaluate"])
                # Deterministic settle: flush two animation frames, then wait.
                await page.evaluate(
                    "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
                )
                await page.wait_for_timeout(int(step.get("wait_ms", _DEFAULT_WAIT_MS)))

                target = output_dir / self._frame_name(frame_prefix, i)
                await page.screenshot(
                    path=str(target), full_page=full_page, omit_background=transparent
                )
                captured.append(target)

            await browser.close()

        manifest_path = output_dir / "frames_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        concat_path = output_dir / manifest["concat_file"]
        concat_path.write_text(self._concat_lines(manifest), encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "output_dir": str(output_dir),
                "manifest": str(manifest_path),
                "concat_file": str(concat_path),
                "frames": [str(p) for p in captured],
                "frame_count": len(captured),
                "total_duration": manifest["total_duration"],
                "viewport": viewport,
            },
            artifacts=[str(p) for p in captured],
        )
