"""Veo / Omni video generation billed to a Google Flow subscription.

Google Flow exposes its models through a web UI only — there is no public API
and no key to configure. This drives that UI with Playwright, attached over CDP
to a Chrome the user is signed into, and hands back the finished mp4.

Same economics as `codex_image`: $0.00 in cash, real spend against a
subscription's credit allowance. Different transport — a browser tab rather than
a CLI.

The heavy lifting lives in `lib/flow_driver.py`. This file is the registry
contract around it: status, cost honesty, serialization, and a check that the
clip handed back is the clip that was asked for.
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

from lib.paths import PROJECTS_DIR
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

# Matched against Flow's own dropdown labels ("Veo 3.1 - Fast", "Omni 1.1 Flash").
# The families are not interchangeable: Omni exposes duration and resolution
# controls and costs fewer credits; Veo fixes both and costs more.
_MODELS = ["Lite", "Fast", "Quality", "Omni"]
_DURATIONS = ["4", "6", "8", "10"]
_ASPECTS = ["16:9", "9:16", "1:1", "3:4", "4:3"]

_DEFAULT_CDP = "http://127.0.0.1:9222"


class FlowVideo(BaseTool):
    name = "flow_video"
    version = "0.2.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    # Not "veo": veo_video already owns that provider string for the API path,
    # and Flow also serves the Omni family.
    provider = "flow"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    # The browser is local even though it reaches Google on our behalf — what
    # matters to the agent is that no key or endpoint is ours to configure.
    runtime = ToolRuntime.LOCAL

    dependencies = ["python:playwright"]
    install_instructions = (
        "Veo / Omni video through your Google Flow subscription — no API key.\n"
        "  1. pip install playwright\n"
        "  2. Start Chrome:  python scripts/flow_chrome.py   (or flow-chrome.cmd)\n"
        "     It uses a dedicated profile at ~/.openmontage/chrome-flow. Since\n"
        "     Chrome 136 the debugging port is ignored on the default profile, a\n"
        "     separate --user-data-dir is required rather than preferred — which is\n"
        "     why there is a launcher instead of a bare chrome.exe command.\n"
        "  3. In that window, sign in to https://labs.google/fx/tools/flow once.\n"
        "     The profile keeps the session. Check it any time with\n"
        "       python scripts/flow_chrome.py --check\n"
        "     Opening Chrome from the normal shortcut uses the DEFAULT profile and\n"
        "     looks exactly like a lost login.\n"
        "Requires a paid Google Flow plan. Automating Flow may violate Google's\n"
        "terms of service and carries a risk of account suspension."
    )
    agent_skills = ["flow-video"]

    capabilities = ["text_to_video", "image_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "native_audio": True,
        "cinematic_quality": True,
        "offline": False,
        "no_api_key": True,
    }
    best_for = [
        "cinematic clips with no cash cost when a Google Flow subscription exists",
        "machines with no video provider API key",
        "video with natively generated synced audio",
    ]
    not_good_for = [
        "batches — one clip at a time through a single browser tab, and Flow caps daily credits",
        "unattended servers — needs a signed-in Chrome started with a debugging port",
        "pipelines that need a stable provider contract (Flow's UI changes often)",
    ]
    fallback_tools = ["veo_video", "seedance_video", "kling_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video"],
                "default": "text_to_video",
            },
            "model_variant": {
                "type": "string",
                "enum": _MODELS,
                "default": "Quality",
                "description": (
                    "Lite/Fast/Quality select a Veo 3.1 tier (fixed length, ~10 credits). "
                    "Omni selects Omni 1.1 Flash, the only family exposing duration and "
                    "resolution controls (~7 credits)."
                ),
            },
            "duration": {
                "type": "string",
                "enum": _DURATIONS,
                "description": (
                    "Seconds. Optional, and only honourable on models that expose a "
                    "duration control — Veo runs at its own fixed length and will reject "
                    "a request that names one. Omit to accept the model's length."
                ),
            },
            "aspect_ratio": {"type": "string", "enum": _ASPECTS, "default": "16:9"},
            "resolution": {
                "type": "string",
                "enum": ["360p", "720p"],
                "description": "Optional, and only offered by some models. 360p costs fewer credits.",
            },
            "reference_image_path": {
                "type": "string",
                "description": "Local first-frame image for image_to_video.",
            },
            "reference_images": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Local images attached as reference chips in Flow's 'Thành phần' "
                    "sub-mode. Any number allowed, and none becomes the opening frame — "
                    "use when several subjects or products must appear in one shot. "
                    "Mutually exclusive with reference_image_path, which sets a start frame."
                ),
            },
            "end_image_path": {
                "type": "string",
                "description": (
                    "Optional local last-frame image. Flow interpolates from the "
                    "first frame to this one, which is how a chained sequence lands "
                    "on an exact artwork instead of wherever the model drifts to."
                ),
            },
            "output_path": {
                "type": "string",
                "description": (
                    "Where to write the clip. Omit and it lands under "
                    "projects/_flow_video_scratch/ instead of wherever the shell's cwd "
                    "happened to be — a bare relative default previously left generated "
                    "mp4s loose at the repo root."
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

            "timeout_seconds": {
                "type": "integer",
                "default": 900,
                "minimum": 120,
                "maximum": 3600,
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    # No retry: a failed generation has usually already spent Flow credits, and a
    # silent second attempt doubles that spend without telling the user.
    retry_policy = RetryPolicy(max_retries=0)
    idempotency_key_fields = ["prompt", "duration", "aspect_ratio", "model_variant"]
    side_effects = [
        "writes a video file to output_path",
        "consumes Google Flow subscription credits (daily allowance)",
        "drives the user's open browser tab — the Flow UI will visibly change",
    ]
    user_visible_verification = [
        "Watch the clip for motion coherence and prompt adherence",
        "Check remaining Flow credits before planning more generations",
    ]

    # ---------------------------------------------------------------- status

    def get_status(self) -> ToolStatus:
        """AVAILABLE once Playwright is installed.

        Deliberately reports installation, not liveness. `video_selector` drops
        anything that is not AVAILABLE — and it drops DEGRADED *silently*, so a
        liveness check here would hide the provider on every machine where
        Chrome happens to be closed, and the user would never reach the point of
        being told to start it. Readiness is checked in execute(), which can
        explain what is wrong.
        """
        try:
            import playwright  # noqa: F401
        except ImportError:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        info["setup_offer"] = {
            "kind": "local_browser",
            "tool": self.name,
            "command": "pip install playwright",
            "health_check": "curl http://127.0.0.1:9222/json/version",
            "requires_api_key": False,
            "what_it_unlocks": [
                "Veo / Omni video generation with no API key, billed to a Google Flow subscription",
            ],
            "notes": (
                "Also needs Chrome started with --remote-debugging-port on a dedicated "
                "--user-data-dir, signed in to Flow. Paid Flow plan required."
            ),
        }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Zero dollars — but not zero cost. Every clip draws on the Flow plan's
        # daily credit allowance. The scheduler must not treat this as free.
        return 0.0

    # ------------------------------------------------------------- internals

    def _lock_path(self) -> Path:
        # One browser, one Flow tab. Two concurrent runs would type into the
        # same prompt editor and collect each other's video.
        # ponytail: O_EXCL lockfile, not a real mutex. Enough to stop this tool
        # racing itself; swap for a proper lock if other tools drive the browser.
        return Path.home() / ".openmontage" / "flow_video.lock"

    def _scratch_dir(self) -> Path:
        # A caller that omits output_path used to fall back to a bare relative
        # filename, which `.resolve()` pins to whatever the shell's cwd was —
        # usually the repo root, so a run left a stray `flow_output_*.mp4`
        # sitting loose outside every project. Route it under projects/ instead:
        # `infer_project_dir` (lib/events.py) only ever attributes an event to a
        # path under PROJECTS_DIR, so this is also the only default that gets a
        # real events.jsonl. The directory is created eagerly — emit_event
        # refuses to write into a project dir that doesn't exist yet.
        d = PROJECTS_DIR / "_flow_video_scratch"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _cdp_blocker(cdp_url: str) -> str | None:
        """Explain what is missing, in the order the user has to fix it."""
        import json
        import urllib.error
        import urllib.request

        try:
            with urllib.request.urlopen(f"{cdp_url}/json/version", timeout=3) as resp:
                json.load(resp)
        except (urllib.error.URLError, OSError, ValueError):
            return (
                f"No Chrome is listening for automation on {cdp_url}.\n"
                f"  Attempted: attach to an existing signed-in Chrome over CDP\n"
                f"  Failed: nothing answered\n"
                f"  Kind: local setup\n"
                f"  Options: run `python scripts/flow_chrome.py` (it launches Chrome "
                f"on the dedicated profile that holds the Flow session — the port is "
                f"ignored on the default profile since Chrome 136), or use an "
                f"API-backed provider (veo_video, seedance_video)"
            )
        return None

    # --------------------------------------------------------------- execute

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        # Imported here, never at module scope: tool_registry.discover() calls
        # importlib without a try/except, so a failing top-level import in any
        # tools/*.py takes down registration for the entire fleet.
        from lib.flow_driver import FlowDriver, FlowError
        from tools.video._shared import probe_output

        if self.get_status() is ToolStatus.UNAVAILABLE:
            return ToolResult(
                success=False,
                error="Playwright is not installed. " + self.install_instructions,
            )

        cdp_url = os.environ.get("FLOW_CDP_URL", _DEFAULT_CDP)
        blocker = self._cdp_blocker(cdp_url)
        if blocker:
            return ToolResult(success=False, error=blocker)

        timeout = int(inputs.get("timeout_seconds", 900))
        filename = f"flow_output_{uuid.uuid4().hex[:8]}.mp4"
        output_path = Path(inputs["output_path"]).resolve() if inputs.get("output_path") \
            else (self._scratch_dir() / filename).resolve()

        operation = inputs.get("operation", "text_to_video")
        asset_path = inputs.get("reference_image_path")
        if operation == "image_to_video":
            # Either a real file to upload, or the name of one already sitting
            # in the Flow project's library from a prior upload_only() call.
            if inputs.get("asset_uploaded_name"):
                asset_path = str(Path(asset_path).resolve()) if asset_path else None
            elif not asset_path or not Path(asset_path).is_file():
                return ToolResult(
                    success=False,
                    error="image_to_video needs reference_image_path pointing at a real "
                          "file, or asset_uploaded_name from a prior upload_only() call",
                )
            else:
                asset_path = str(Path(asset_path).resolve())
        else:
            asset_path = None

        job = {
            "prompt": inputs["prompt"],
            "operation": operation,
            "model_variant": inputs.get("model_variant", "Quality"),
            "aspect_ratio": inputs.get("aspect_ratio", "16:9"),
            # Passed through only when asked for: naming a duration the chosen
            # model cannot honour must fail before any credit is spent, not
            # silently return Flow's own length under the requested label.
            "duration": str(inputs["duration"]) if inputs.get("duration") else None,
            "resolution": inputs.get("resolution"),
            "output_path": str(output_path),
            "quality": inputs.get("quality", "max"),
            "asset_path": asset_path,
            "end_asset_path": (str(Path(inputs["end_image_path"]).resolve())
                               if inputs.get("end_image_path") else None),
            # A filename already sitting in the Flow project's library from a
            # prior upload_only() call. When set, generate() fills the frame
            # slot straight from the library and skips re-uploading asset_path.
            "asset_uploaded_name": inputs.get("asset_uploaded_name"),
            "end_asset_uploaded_name": inputs.get("end_asset_uploaded_name"),
            # Reference images attached as prompt chips in Flow's "Thành phần"
            # sub-mode. Unlike reference_image_path (a start frame), any number
            # can be given and none of them is the opening frame — use these when
            # several things must appear in one shot.
            "reference_images": [str(Path(r).resolve()) for r in
                                 (inputs.get("reference_images") or [])],
            "timeout_seconds": timeout,
        }
        missing_refs = [r for r in job["reference_images"] if not Path(r).is_file()]
        if missing_refs:
            return ToolResult(success=False,
                              error=f"reference_images not found: {missing_refs}")

        start = time.time()
        lock = self._lock_path()
        try:
            try:
                lock.parent.mkdir(parents=True, exist_ok=True)
                os.close(os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            except FileExistsError:
                return ToolResult(
                    success=False,
                    error=(
                        f"Another Flow generation is in progress ({lock}). There is one "
                        f"browser tab, so runs are serialized. Delete the lock file if a "
                        f"previous run crashed."
                    ),
                )

            try:
                with FlowDriver(cdp_url, os.environ.get("FLOW_PROJECT_URL")) as driver:
                    result = driver.generate(job)
            except FlowError as exc:
                return ToolResult(success=False, error=f"Flow generation failed: {exc}")
            except Exception as exc:  # noqa: BLE001 - surface, never swallow
                return ToolResult(success=False, error=f"Flow driver error: {exc}")
        finally:
            lock.unlink(missing_ok=True)

        probed = probe_output(output_path)

        # Independent check that the file is the clip that was asked for. Twice
        # during development a run downloaded an older clip from the same
        # project and reported success: the mp4 was valid, ffprobe was happy,
        # and only the duration gave it away.
        got = probed.get("duration_seconds")
        want = float(job["duration"]) if job["duration"] else None
        if want is not None and got is not None and abs(float(got) - want) > 1.0:
            return ToolResult(
                success=False,
                error=(
                    f"Flow returned a {got:.1f}s clip but {want:.0f}s was requested "
                    f"({output_path}). The download almost certainly picked up a "
                    f"different clip from the project — do not use this file."
                ),
            )

        return ToolResult(
            success=True,
            data={
                "provider": "flow",
                "gateway": "playwright_cdp",
                "prompt": job["prompt"],
                "operation": operation,
                "aspect_ratio": job["aspect_ratio"],
                "duration_requested": job["duration"],
                "resolution": job["resolution"],
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                "billing": "google_flow_subscription",
                # What Flow actually had selected and charged, read back from the
                # UI — not what we asked for. Reporting an unverified model is how
                # early runs silently generated on Omni while claiming Veo.
                "flow_model": result.get("model"),
                "flow_credits": result.get("credits"),
                "flow_media_id": result.get("media_id"),
                "flow_download_row": result.get("download_row"),
                "reference_image": asset_path,
                # The library names Flow actually attached. The only evidence
                # after the fact that every reference chip landed.
                "flow_reference_media_id": result.get("reference_media_id"),
                **probed,
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            model=result.get("model"),
        )
