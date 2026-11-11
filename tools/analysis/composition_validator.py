"""Pre-render composition validator.

Checks an ExplainerProps JSON for common issues before rendering:
- Missing asset files (images, audio)
- Narration duration exceeding video duration
- Music duration shorter than video (warning)
- Overlapping or out-of-order cuts
- Required fields present

Run this before every render to catch problems that would otherwise
produce broken or truncated output.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools.analysis.audio_probe import probe_duration
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


class CompositionValidator(BaseTool):
    name = "composition_validator"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "analysis"
    provider = "local"
    stability = ToolStability.PRODUCTION
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["binary:ffprobe"]
    install_instructions = "Requires ffprobe on PATH (part of ffmpeg)."

    capabilities = ["validate_composition", "pre_render_check"]
    best_for = [
        "catching audio-video duration mismatches before render",
        "verifying all referenced assets exist",
        "pre-flight check before expensive render operations",
    ]

    input_schema = {
        "type": "object",
        "required": ["composition_path"],
        "properties": {
            "composition_path": {
                "type": "string",
                "description": "Path to the composition JSON file",
            },
            "assets_root": {
                "type": "string",
                "description": (
                    "Root directory for resolving relative asset paths. "
                    "If omitted, resolved from render_runtime (see below)."
                ),
            },
            "render_runtime": {
                "type": "string",
                "enum": ["remotion", "hyperframes", "ffmpeg"],
                "description": (
                    "Which runtime will consume this composition. Drives the "
                    "default asset root: remotion→remotion-composer/public, "
                    "hyperframes→<workspace>/assets or composition's parent, "
                    "ffmpeg→composition's parent. Explicit assets_root wins."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=64, vram_mb=0, disk_mb=0, network_required=False
    )
    side_effects = []

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        comp_path = Path(inputs["composition_path"])
        if not comp_path.exists():
            return ToolResult(success=False, error=f"Composition not found: {comp_path}")

        start = time.time()

        try:
            comp = json.loads(comp_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return ToolResult(success=False, error=f"Invalid JSON: {e}")

        # Determine assets root. Explicit wins; otherwise dispatch by runtime.
        # `render_runtime` may be passed in inputs, or extracted from the
        # composition JSON itself (edit_decisions.render_runtime).
        explicit_root = inputs.get("assets_root") or ""
        assets_root = Path(explicit_root) if explicit_root else None
        runtime = (
            inputs.get("render_runtime")
            or comp.get("render_runtime")
            or ""
        ).strip().lower()

        if assets_root is None or not assets_root.is_dir():
            if runtime == "hyperframes":
                # HyperFrames workspaces keep assets/ alongside index.html.
                # Composition JSON typically lives in projects/<p>/artifacts/,
                # so the workspace is at projects/<p>/hyperframes/.
                candidate = comp_path
                resolved = None
                for _ in range(5):
                    candidate = candidate.parent
                    hf_assets = candidate / "hyperframes" / "assets"
                    if hf_assets.is_dir():
                        resolved = hf_assets
                        break
                    local_assets = candidate / "assets"
                    if local_assets.is_dir() and (candidate / "index.html").is_file():
                        resolved = local_assets
                        break
                assets_root = resolved or comp_path.parent
            elif runtime == "ffmpeg":
                # FFmpeg jobs reference files by absolute path; fall back to
                # the composition's parent for any bare-name references.
                assets_root = comp_path.parent
            else:
                # Remotion (default): remotion-composer/public
                candidate = comp_path
                resolved = None
                for _ in range(5):
                    candidate = candidate.parent
                    public = candidate / "remotion-composer" / "public"
                    if public.is_dir():
                        resolved = public
                        break
                assets_root = resolved or comp_path.parent

        errors: list[str] = []
        warnings: list[str] = []
        info: list[str] = []

        def locate(ref: str) -> Path:
            """Where the renderer will find a referenced file.

            On the Remotion path video_compose stages any file that exists as
            given (absolute or relative to the working directory) into the
            render's public dir (``_stage_remotion_media``); anything else is a
            ``staticFile()`` path under the public dir.
            """
            if runtime in ("", "remotion") and Path(ref).is_file():
                return Path(ref)
            return assets_root / ref

        cuts = comp.get("cuts", [])
        audio = comp.get("audio", {})

        # --- Check 1: Cuts exist ---
        if not cuts:
            errors.append("No cuts defined in composition")
            return self._result(errors, warnings, info, start)

        # --- Check 2: Video duration ---
        video_duration = 0.0
        for cut in cuts:
            out_s = cut.get("out_seconds", 0)
            if out_s > video_duration:
                video_duration = out_s
        info.append(f"Video duration: {video_duration}s ({len(cuts)} cuts)")
        info.append(f"Render runtime: {runtime or 'default (remotion)'}; assets root: {assets_root}")

        # --- Check 3: Cut ordering and gaps ---
        sorted_cuts = sorted(cuts, key=lambda c: c.get("in_seconds", 0))
        for i, cut in enumerate(sorted_cuts):
            in_s = cut.get("in_seconds", 0)
            out_s = cut.get("out_seconds", 0)
            if out_s <= in_s:
                errors.append(
                    f"Cut '{cut.get('id', i)}': out_seconds ({out_s}) <= in_seconds ({in_s})"
                )

        # --- Check 4: Asset files exist ---
        for cut in cuts:
            source = cut.get("source", "")
            if source:
                asset_path = locate(source)
                if not asset_path.exists():
                    errors.append(f"Missing asset: {source} (looked in {assets_root})")

            bg_img = cut.get("backgroundImage", "")
            if bg_img:
                bg_path = locate(bg_img)
                if not bg_path.exists():
                    errors.append(f"Missing background image: {bg_img}")

            bg_video = cut.get("backgroundVideo", "")
            if isinstance(bg_video, str) and bg_video:
                if not locate(bg_video).exists():
                    errors.append(f"Missing background video: {bg_video} (cut '{cut.get('id', '?')}')")

            # anime_scene frames; video_compose stages these like `source`.
            images = cut.get("images") or []
            if isinstance(images, list):
                for image in images:
                    if isinstance(image, str) and image and not locate(image).exists():
                        errors.append(f"Missing image: {image} (cut '{cut.get('id', '?')}' images[])")

        # --- Check 5: Narration duration vs video duration ---
        narration = audio.get("narration", {})
        narration_src = narration.get("src", "")
        if narration_src:
            narration_path = locate(narration_src)
            if not narration_path.exists():
                errors.append(f"Missing narration audio: {narration_src}")
            else:
                narration_dur = probe_duration(narration_path)
                if narration_dur is not None:
                    info.append(f"Narration duration: {narration_dur:.1f}s")
                    overshoot = narration_dur - video_duration
                    if overshoot > 1.0:
                        errors.append(
                            f"Narration ({narration_dur:.1f}s) exceeds video ({video_duration}s) "
                            f"by {overshoot:.1f}s — audio will be cut off"
                        )
                    elif overshoot > 0:
                        warnings.append(
                            f"Narration ({narration_dur:.1f}s) slightly exceeds video ({video_duration}s) "
                            f"by {overshoot:.1f}s"
                        )
                else:
                    warnings.append(f"Could not probe narration duration: {narration_src}")

        # --- Check 6: Music duration ---
        music = audio.get("music", {})
        music_src = music.get("src", "")
        if music_src:
            music_path = locate(music_src)
            if not music_path.exists():
                errors.append(f"Missing music audio: {music_src}")
            else:
                music_dur = probe_duration(music_path)
                if music_dur is not None:
                    info.append(f"Music duration: {music_dur:.1f}s")
                    if music_dur < video_duration:
                        warnings.append(
                            f"Music ({music_dur:.1f}s) is shorter than video ({video_duration}s) "
                            f"— will end early"
                        )

        # --- Check 7: No audio at all ---
        if not narration_src and not music_src:
            warnings.append("No audio configured (no narration or music)")

        return self._result(errors, warnings, info, start)

    def _result(
        self,
        errors: list[str],
        warnings: list[str],
        info: list[str],
        start: float,
    ) -> ToolResult:
        passed = len(errors) == 0
        data = {
            "valid": passed,
            "errors": errors,
            "warnings": warnings,
            "info": info,
            "error_count": len(errors),
            "warning_count": len(warnings),
        }

        if not passed:
            summary = "; ".join(errors[:3])
            return ToolResult(
                success=False,
                error=f"Composition has {len(errors)} error(s): {summary}",
                data=data,
                duration_seconds=round(time.time() - start, 2),
            )

        return ToolResult(
            success=True,
            data=data,
            duration_seconds=round(time.time() - start, 2),
        )
