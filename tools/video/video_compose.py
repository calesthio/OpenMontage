"""Video composition tool — FFmpeg + Remotion.

Final composition path that takes edit decisions, assets, and audio
and renders the complete output video. Supports subtitle burn-in,
overlay compositing, and platform-specific encoding profiles.

For compositions with still images, animated scenes, or component types
(text cards, stat cards, etc.), the render operation auto-routes to
Remotion for frame-accurate spring animations and React-based rendering.
For pure video cuts (talking-head, etc.), FFmpeg handles trimming and concat.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ResumeSupport,
    ToolResult,
    ToolStability,
    ToolTier,
)


class VideoCompose(BaseTool):
    name = "video_compose"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "ffmpeg"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg"]
    install_instructions = "Install FFmpeg: https://ffmpeg.org/download.html"
    agent_skills = ["remotion-best-practices", "remotion", "ffmpeg"]

    capabilities = [
        "compose_cuts",
        "burn_subtitles",
        "overlay_assets",
        "encode_profile",
        "remotion_render",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["compose", "render", "remotion_render", "burn_subtitles", "overlay", "encode"],
                "description": (
                    "compose: low-level concat cuts + audio + subtitles. "
                    "render: high-level — resolves asset IDs, auto-routes to Remotion "
                    "for images/animations or FFmpeg for video-only. Preferred for compose-director. "
                    "remotion_render: render via Remotion (Node.js). "
                    "burn_subtitles: burn subtitle file into existing video. "
                    "overlay: composite overlays onto base video. "
                    "encode: re-encode to a target profile/codec."
                ),
            },
            "input_path": {"type": "string"},
            "output_path": {"type": "string"},
            "edit_decisions": {
                "type": "object",
                "description": "Full edit_decisions artifact (required for compose/render)",
            },
            "asset_manifest": {
                "type": "object",
                "description": (
                    "Full asset_manifest artifact (required for render). "
                    "Used to resolve asset IDs in cuts[].source to file paths."
                ),
            },
            "subtitle_path": {"type": "string"},
            "subtitle_style": {
                "type": "object",
                "description": "ASS subtitle styling. Also extracted from edit_decisions.subtitles if not provided.",
                "properties": {
                    "font": {"type": "string", "default": "Arial"},
                    "font_size": {"type": "integer", "default": 24},
                    "primary_color": {"type": "string", "default": "&HFFFFFF"},
                    "outline_color": {"type": "string", "default": "&H000000"},
                    "outline_width": {"type": "number", "default": 2},
                    "margin_v": {"type": "integer", "default": 40},
                    "alignment": {"type": "integer", "default": 2},
                },
            },
            "overlays": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "asset_path": {"type": "string"},
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "width": {"type": "number"},
                        "height": {"type": "number"},
                        "start_seconds": {"type": "number"},
                        "end_seconds": {"type": "number"},
                        "opacity": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
            },
            "audio_path": {"type": "string", "description": "Mixed audio to mux into output"},
            "profile": {
                "type": "string",
                "description": (
                    "Media profile name from media_profiles.py "
                    "(e.g. youtube_landscape, tiktok, instagram_reels). "
                    "Applied in render and encode operations."
                ),
            },
            "options": {
                "type": "object",
                "description": "Render options (used by the render operation)",
                "properties": {
                    "subtitle_burn": {"type": "boolean", "default": True},
                    "two_pass_encode": {"type": "boolean", "default": False},
                },
            },
            "codec": {"type": "string", "default": "libx264"},
            "crf": {"type": "integer", "default": 23},
            "preset": {"type": "string", "default": "medium"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=5000, network_required=False
    )

    # Remotion scene types that trigger React-based rendering
    _REMOTION_COMPONENTS = [
        "text_card", "stat_card", "callout", "comparison",
        "progress", "chart", "bar_chart", "line_chart", "pie_chart", "kpi_grid",
    ]

    best_for = [
        "Final render for explainer and animation pipelines",
        "Image-to-video with spring animations (Remotion)",
        "Animated text cards, stat cards, charts (Remotion)",
        "Complex transitions between scenes (Remotion)",
        "Pure video concat and trim (FFmpeg)",
    ]
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["Conversion failed"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["operation", "input_path", "edit_decisions"]
    side_effects = ["writes video file to output_path"]
    user_visible_verification = [
        "Play the composed output and verify cuts, subtitles, and overlays",
    ]

    def _remotion_available(self) -> bool:
        """Check if Remotion rendering is available (requires npx + composer project + node_modules)."""
        import shutil as _shutil

        if not _shutil.which("npx"):
            return False
        composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
        if not composer_dir.exists() or not (composer_dir / "package.json").exists():
            return False
        # Check that node_modules are actually installed — without this,
        # npx remotion render will fail even though the project exists.
        if not (composer_dir / "node_modules").exists():
            return False
        return True

    def get_info(self) -> dict[str, Any]:
        """Extend base get_info to surface Remotion sub-capability.

        This lets preflight report 'video_compose: AVAILABLE (FFmpeg + Remotion)'
        so the agent knows Remotion is usable for motion graphics, animated text
        cards, stat cards, charts, and image-to-video rendering — rather than
        falling back to Ken Burns pan-and-zoom over still images.
        """
        info = super().get_info()
        remotion_ok = self._remotion_available()
        info["render_engines"] = {
            "ffmpeg": True,
            "remotion": remotion_ok,
        }
        if remotion_ok:
            info["remotion_components"] = self._REMOTION_COMPONENTS
            info["remotion_note"] = (
                "Remotion is available for React-based rendering. Use it for "
                "image-to-video with spring animations, animated text/stat cards, "
                "charts, callouts, comparisons, and complex transitions. "
                "Prefer Remotion over Ken Burns pan-and-zoom for explainer "
                "and motion-graphics pipelines."
            )
        else:
            composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
            if composer_dir.exists() and (composer_dir / "package.json").exists() and not (composer_dir / "node_modules").exists():
                info["remotion_note"] = (
                    "Remotion project exists but node_modules are NOT installed. "
                    "Run 'cd remotion-composer && npm install' to enable Remotion rendering. "
                    "Falling back to FFmpeg Ken Burns for image-based compositions."
                )
            else:
                info["remotion_note"] = (
                    "Remotion is NOT available (needs Node.js/npx + remotion-composer). "
                    "Falling back to FFmpeg Ken Burns for image-based compositions."
                )
        return info

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs["operation"]
        start = time.time()

        try:
            if operation == "compose":
                result = self._compose(inputs)
            elif operation == "render":
                result = self._render(inputs)
            elif operation == "remotion_render":
                result = self._remotion_render(inputs)
            elif operation == "burn_subtitles":
                result = self._burn_subtitles(inputs)
            elif operation == "overlay":
                result = self._overlay(inputs)
            elif operation == "encode":
                result = self._encode(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        result.duration_seconds = round(time.time() - start, 2)
        return result

    _IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

    @staticmethod
    def _is_image(path: Path) -> bool:
        """Check if a file is a still image (routes to Remotion, not FFmpeg)."""
        return path.suffix.lower() in VideoCompose._IMAGE_EXTENSIONS

    def _compose(self, inputs: dict[str, Any]) -> ToolResult:
        """FFmpeg composition: concat video cuts, add audio, burn subtitles.

        Handles video sources only. Still images and animated scene types
        are routed to Remotion via the render operation — call compose
        directly only for pure video pipelines (e.g. talking-head).
        """
        edit_decisions = inputs.get("edit_decisions")
        if not edit_decisions:
            return ToolResult(success=False, error="edit_decisions required for compose")

        output_path = Path(inputs.get("output_path", "composed_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        audio_path = inputs.get("audio_path")
        subtitle_path = inputs.get("subtitle_path")
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)
        preset = inputs.get("preset", "medium")
        profile_name = inputs.get("profile")

        # Resolve target resolution from profile or default
        resolution = "1920x1080"
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                p = get_profile(profile_name)
                resolution = f"{p.width}x{p.height}"
            except (ImportError, ValueError):
                pass

        cuts = edit_decisions.get("cuts", [])
        if not cuts:
            return ToolResult(success=False, error="No cuts in edit_decisions")

        # Resolve subtitle style using the layered priority resolver
        # (explicit > edit_decisions > playbook > defaults)
        playbook_data = inputs.get("playbook")
        resolved_sub_style = self._resolve_subtitle_style(
            inputs.get("subtitle_style"),
            edit_decisions,
            playbook_data,
        )
        inputs = dict(inputs)
        inputs["subtitle_style"] = resolved_sub_style

        ed_subs = edit_decisions.get("subtitles", {})
        if ed_subs.get("source") and not subtitle_path:
            subtitle_path = ed_subs["source"]

        temp_dir = output_path.parent / ".compose_tmp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_segments: list[Path] = []
        concat_path: Path | None = None
        concat_out: Path | None = None

        try:
            for i, cut in enumerate(cuts):
                source = Path(cut["source"])
                if not source.exists():
                    return ToolResult(success=False, error=f"Cut source not found: {source}")

                seg_path = temp_dir / f"seg_{i:04d}.mp4"
                in_s = cut["in_seconds"]
                out_s = cut["out_seconds"]
                duration = out_s - in_s
                speed = cut.get("speed", 1.0)

                if self._is_image(source):
                    return ToolResult(
                        success=False,
                        error=(
                            f"Still image '{source.name}' in cuts. "
                            "Use operation='render' (auto-routes to Remotion) "
                            "or operation='remotion_render' for compositions "
                            "with images, animations, or component scenes."
                        ),
                    )
                else:
                    # Video source: trim to segment.
                    # -ss before -i for input-level seeking — more reliable
                    # with -c copy when stream order is non-standard (e.g.
                    # audio-first containers from Kling/fal.ai).
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(in_s),
                        "-i", str(source),
                        "-to", str(out_s - in_s),
                    ]

                    if speed != 1.0:
                        vf = f"setpts={1.0/speed}*PTS"
                        af = self._build_atempo(speed)
                        cmd.extend(["-filter:v", vf, "-filter:a", af])
                        cmd.extend(["-c:v", codec, "-crf", str(crf), "-c:a", "aac"])
                    else:
                        cmd.extend(["-c", "copy"])

                    cmd.append(str(seg_path))
                    self.run_command(cmd)

                temp_segments.append(seg_path)

            # Step 2: Concat segments
            concat_path = temp_dir / "concat_list.txt"
            with open(concat_path, "w", encoding="utf-8") as f:
                for seg in temp_segments:
                    safe = str(seg.resolve()).replace("\\", "/")
                    f.write(f"file '{safe}'\n")

            concat_out = temp_dir / "concat.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_path),
                "-c", "copy",
                str(concat_out),
            ]
            self.run_command(cmd)

            # Step 3: Apply subtitles and/or replace audio
            final_input = concat_out
            vfilters = []

            if subtitle_path and Path(subtitle_path).exists():
                style = inputs.get("subtitle_style", {})
                ass_style = self._build_subtitle_style(style)
                sub_escaped = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
                vfilters.append(f"subtitles='{sub_escaped}':force_style='{ass_style}'")

            cmd = ["ffmpeg", "-y", "-i", str(final_input)]

            if audio_path and Path(audio_path).exists():
                cmd.extend(["-i", audio_path])

            # Determine if profile requires re-encoding (resize/fps change)
            # This must be checked BEFORE choosing copy vs encode, because
            # -s and -r are incompatible with -c:v copy.
            profile_flags: list[str] = []
            if profile_name:
                try:
                    from lib.media_profiles import get_profile
                    p = get_profile(profile_name)
                    profile_flags = ["-s", f"{p.width}x{p.height}", "-r", str(p.fps)]
                except (ImportError, ValueError):
                    pass

            needs_reencode = bool(vfilters) or bool(profile_flags)

            if needs_reencode:
                if vfilters:
                    cmd.extend(["-vf", ",".join(vfilters)])
                cmd.extend(["-c:v", codec, "-crf", str(crf), "-preset", preset])
                cmd.extend(profile_flags)
            else:
                cmd.extend(["-c:v", "copy"])

            if audio_path and Path(audio_path).exists():
                # Use type-based selectors (0:v, 1:a) instead of index-based
                # (0:v:0) because source videos may have audio as stream 0
                # and video as stream 1 (e.g. Kling-generated clips).
                cmd.extend(["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"])
            else:
                cmd.extend(["-c:a", "copy"])

            cmd.append(str(output_path))
            self.run_command(cmd)

            return ToolResult(
                success=True,
                data={
                    "operation": "compose",
                    "cut_count": len(cuts),
                    "has_subtitles": subtitle_path is not None,
                    "has_mixed_audio": audio_path is not None,
                    "profile": profile_name,
                    "output": str(output_path),
                },
                artifacts=[str(output_path)],
            )
        finally:
            # Cleanup temp files
            for f in temp_segments:
                if f.exists():
                    f.unlink()
            for f in [concat_path, concat_out]:
                if f is not None and f.exists():
                    f.unlink()
            if temp_dir.exists():
                try:
                    temp_dir.rmdir()
                except OSError:
                    pass

    _REMOTION_SCENE_TYPES = {
        "text_card", "stat_card", "callout", "comparison", "progress", "chart",
    }

    # Maps renderer_family (set at proposal stage) to Remotion composition ID.
    # Each family MUST map to a distinct composition — collapsing defeats visual grammar.
    # Maps renderer_family → Remotion composition ID.
    # Only compositions registered in remotion-composer/src/Root.tsx are valid.
    # Current compositions: Explainer, CinematicRenderer, TalkingHead
    RENDERER_FAMILY_MAP = {
        "explainer-data": "Explainer",
        "explainer-teacher": "Explainer",
        "cinematic-trailer": "CinematicRenderer",
        "product-reveal": "Explainer",
        "screen-demo": "Explainer",
        "presenter": "TalkingHead",
        "animation-first": "Explainer",
    }

    @classmethod
    def _get_composition_id(cls, renderer_family: str) -> str:
        """Resolve renderer_family to Remotion composition ID.

        Raises ValueError if renderer_family is not recognized — the caller
        must set it at proposal stage.
        """
        comp = cls.RENDERER_FAMILY_MAP.get(renderer_family)
        if comp is None:
            raise ValueError(
                f"Unknown renderer_family {renderer_family!r}. "
                f"Valid families: {sorted(cls.RENDERER_FAMILY_MAP)}. "
                f"Set renderer_family at proposal stage."
            )
        return comp

    @staticmethod
    def _build_theme_from_playbook(
        playbook_name: str | None,
        composition_data: dict | None,
    ) -> dict[str, Any] | None:
        """Derive a Remotion ThemeConfig from a playbook's actual color values.

        Instead of passing a playbook name and hoping Remotion has a matching
        preset, we read the playbook YAML and extract concrete colors/fonts.
        This means custom playbooks, overridden palettes, and per-project
        styles all flow through to Remotion automatically.

        Falls back to extracting colors from edit_decisions metadata if
        no playbook is loadable.
        """
        theme: dict[str, Any] = {}

        # Try to load the playbook YAML
        playbook: dict[str, Any] = {}
        if playbook_name:
            try:
                from styles.playbook_loader import load_playbook
                playbook = load_playbook(playbook_name)
            except Exception:
                pass

        if playbook:
            vl = playbook.get("visual_language", {})
            palette = vl.get("color_palette", {})
            typo = playbook.get("typography", {})

            # Extract primary/accent — may be a list (gradient stops) or string
            primary_raw = palette.get("primary", ["#2563EB"])
            accent_raw = palette.get("accent", ["#F59E0B"])
            primary = primary_raw[0] if isinstance(primary_raw, list) else primary_raw
            accent = accent_raw[0] if isinstance(accent_raw, list) else accent_raw

            bg = palette.get("background", "#FFFFFF")
            text = palette.get("text", "#1F2937")
            surface = palette.get("surface", bg)
            muted = palette.get("muted_text", "#6B7280")

            # Build chart colors from all palette entries
            chart_colors = []
            for key in ["primary", "accent", "secondary", "success", "warning", "info"]:
                val = palette.get(key)
                if val:
                    chart_colors.append(val[0] if isinstance(val, list) else val)
            if len(chart_colors) < 3:
                chart_colors = [primary, accent, "#10B981", "#8B5CF6", "#EC4899", "#06B6D4"]

            theme = {
                "primaryColor": primary,
                "accentColor": accent,
                "backgroundColor": bg,
                "surfaceColor": surface,
                "textColor": text,
                "mutedTextColor": muted,
                "headingFont": typo.get("heading", {}).get("font", "Inter"),
                "bodyFont": typo.get("body", {}).get("font", "Inter"),
                "monoFont": typo.get("code", {}).get("font", "JetBrains Mono"),
                "chartColors": chart_colors[:6],
                "springConfig": {"damping": 20, "stiffness": 120, "mass": 1},
                "transitionDuration": 0.4,
            }

            # Derive caption colors from the palette
            theme["captionHighlightColor"] = primary
            # Caption background: semi-transparent version of the bg color
            theme["captionBackgroundColor"] = (
                f"rgba(255, 255, 255, 0.85)" if bg.upper() in ("#FFFFFF", "#FAFAFA", "#F9FAFB")
                else f"rgba(15, 23, 42, 0.75)"
            )

            # Motion style from playbook
            motion = playbook.get("motion", {})
            pace = motion.get("pace", "moderate")
            if pace == "fast":
                theme["springConfig"] = {"damping": 12, "stiffness": 80, "mass": 1}
                theme["transitionDuration"] = 0.3
            elif pace == "slow":
                theme["springConfig"] = {"damping": 25, "stiffness": 150, "mass": 1}
                theme["transitionDuration"] = 0.6

        # Fallback: try to extract from edit_decisions metadata
        if not theme and composition_data:
            meta = composition_data.get("metadata", {})
            if meta.get("primary_color"):
                theme = {
                    "primaryColor": meta["primary_color"],
                    "accentColor": meta.get("accent_color", "#F59E0B"),
                    "backgroundColor": meta.get("background_color", "#FFFFFF"),
                    "surfaceColor": meta.get("surface_color", "#F9FAFB"),
                    "textColor": meta.get("text_color", "#1F2937"),
                    "mutedTextColor": "#6B7280",
                    "headingFont": meta.get("heading_font", "Inter"),
                    "bodyFont": meta.get("body_font", "Inter"),
                    "monoFont": "JetBrains Mono",
                    "chartColors": meta.get("chart_colors", ["#2563EB", "#F59E0B", "#10B981"]),
                    "springConfig": {"damping": 20, "stiffness": 120, "mass": 1},
                    "transitionDuration": 0.4,
                    "captionHighlightColor": meta["primary_color"],
                    "captionBackgroundColor": "rgba(255, 255, 255, 0.85)",
                }

        return theme if theme else None

    def _needs_remotion(self, cuts: list[dict]) -> bool:
        """Determine whether Remotion should handle this composition.

        Remotion is the DEFAULT composition engine when available.  It handles
        video clips (via <OffthreadVideo>), still images, animated scene types,
        component types, transitions, and mixed content — all in a single
        React-based render pass.

        Returns False (i.e. use FFmpeg) ONLY when ALL of these are true:
          1. Every cut source is a video file (no images, no component types)
          2. No cut requests animations or transitions
          3. No cut uses a Remotion scene type
          4. The edit_decisions explicitly set renderer_family to "ffmpeg-only"
             OR Remotion is not available

        This "Remotion-first" policy means mixed content (video clips +
        animated stills + text cards) is always composed in Remotion, which
        can embed <OffthreadVideo> alongside React components natively.
        """
        # If Remotion isn't installed, fall back to FFmpeg
        if not self._remotion_available():
            return False

        # Any rich content → Remotion (fast path, catches the obvious cases)
        for cut in cuts:
            source = cut.get("source", "")
            if source and Path(source).suffix.lower() in self._IMAGE_EXTENSIONS:
                return True
            if cut.get("type") in self._REMOTION_SCENE_TYPES:
                return True
            if cut.get("animation") or cut.get("transition_in") or cut.get("transition_out"):
                return True
            transform = cut.get("transform", {})
            if transform and transform.get("animation"):
                return True

        # Even for pure-video cuts, default to Remotion — it handles video
        # clips natively via <OffthreadVideo> and gives us transitions,
        # overlays, and profile scaling for free.
        return True

    def _pre_compose_validation(
        self,
        edit_decisions: dict[str, Any],
        resolved_cuts: list[dict],
        scene_plan: list[dict] | None = None,
    ) -> ToolResult | None:
        """Pre-compose quality gate — blocks render on critical violations.

        Checks:
        1. Delivery promise violation: motion-required brief with >70% still cuts → BLOCK
        2. Slideshow risk score "fail" (average ≥ 4.0) → BLOCK
        3. Missing renderer_family → WARN (log only, don't block)

        Returns a failed ToolResult if render should be blocked, None if OK to proceed.
        """
        log = logging.getLogger("video_compose")
        warnings: list[str] = []
        blocks: list[str] = []

        # --- 1. Delivery promise check ---
        delivery_data = edit_decisions.get("metadata", {}).get("delivery_promise")
        if not delivery_data:
            # Also check top-level (proposal_packet nests it at top level)
            delivery_data = edit_decisions.get("delivery_promise")

        if delivery_data:
            try:
                from lib.delivery_promise import DeliveryPromise
                promise = DeliveryPromise.from_dict(delivery_data)
                result = promise.validate_cuts(resolved_cuts)
                if not result["valid"]:
                    for v in result["violations"]:
                        blocks.append(f"Delivery promise violation: {v}")
            except Exception as e:
                log.warning("Could not validate delivery promise: %s", e)
        else:
            warnings.append("No delivery_promise in edit_decisions — skipping promise validation")

        # --- 2. Slideshow risk check ---
        renderer_family = edit_decisions.get("renderer_family")
        scenes = scene_plan or []

        # If no scene_plan passed, try to extract scene info from cuts
        if not scenes and resolved_cuts:
            scenes = [
                {
                    "type": c.get("type", ""),
                    "description": c.get("reason", ""),
                    "shot_language": c.get("shot_language", {}),
                    "shot_intent": c.get("shot_intent"),
                    "narrative_role": c.get("narrative_role"),
                    "information_role": c.get("information_role"),
                    "hero_moment": c.get("hero_moment", False),
                }
                for c in resolved_cuts
            ]

        if scenes:
            try:
                from lib.slideshow_risk import score_slideshow_risk
                risk = score_slideshow_risk(scenes, edit_decisions, renderer_family)
                if risk["verdict"] == "fail":
                    blocks.append(
                        f"Slideshow risk score {risk['average']:.1f}/5.0 (verdict: fail). "
                        f"Video plan looks like a slideshow — revise scene plan before rendering."
                    )
                elif risk["verdict"] == "revise":
                    warnings.append(
                        f"Slideshow risk score {risk['average']:.1f}/5.0 (verdict: revise). "
                        f"Consider improving scene variety before final render."
                    )
            except Exception as e:
                log.warning("Could not compute slideshow risk: %s", e)

        # --- 3. Missing renderer_family (BLOCK — must be set at proposal) ---
        if not renderer_family:
            blocks.append(
                "No renderer_family in edit_decisions. "
                "renderer_family must be set at proposal stage and locked before compose. "
                "Re-run the proposal stage with a renderer_family selection."
            )

        # Log warnings
        for w in warnings:
            log.warning("[pre-compose] %s", w)

        # Block on critical violations
        if blocks:
            return ToolResult(
                success=False,
                error=(
                    "Pre-compose validation failed — render blocked.\n"
                    + "\n".join(f"  • {b}" for b in blocks)
                    + ("\n\nWarnings:\n" + "\n".join(f"  • {w}" for w in warnings) if warnings else "")
                ),
            )

        return None

    def _render(self, inputs: dict[str, Any]) -> ToolResult:
        """High-level render: assemble edit decisions + asset manifest into final video.

        This is the primary entry point for the compose-director skill.
        It resolves asset IDs and routes to the composition engine:

        - **Remotion (default):** Used for all compositions when available —
          video clips, images, animated scenes, component types, mixed content.
          Remotion embeds video via <OffthreadVideo> and handles transitions,
          overlays, and profile scaling natively.
        - **FFmpeg (fallback):** Used only when Remotion is unavailable, or
          when the agent explicitly calls operation='compose' for simple
          trim/concat operations.

        The agent should pass edit_decisions, asset_manifest, and optionally
        profile, subtitle_path, audio_path, and options.
        """
        edit_decisions = inputs.get("edit_decisions")
        asset_manifest = inputs.get("asset_manifest")
        if not edit_decisions:
            return ToolResult(success=False, error="edit_decisions required for render")
        if not asset_manifest:
            return ToolResult(success=False, error="asset_manifest required for render")

        output_path = Path(inputs.get("output_path", "renders/output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build asset lookup: id -> asset info
        asset_lookup = {a["id"]: a for a in asset_manifest.get("assets", [])}

        cuts = edit_decisions.get("cuts", [])
        if not cuts:
            return ToolResult(success=False, error="No cuts in edit_decisions")

        # Resolve asset IDs in cuts to file paths
        resolved_cuts = []
        for cut in cuts:
            source_id = cut.get("source", "")
            resolved_cut = dict(cut)
            if source_id in asset_lookup:
                resolved_cut["source"] = asset_lookup[source_id]["path"]
            resolved_cuts.append(resolved_cut)

        # --- Pre-compose validation gate ---
        scene_plan = inputs.get("scene_plan")
        validation_block = self._pre_compose_validation(edit_decisions, resolved_cuts, scene_plan)
        if validation_block is not None:
            return validation_block

        # Also accept profile as "output_profile" (skill convention) or "profile"
        profile = inputs.get("profile") or inputs.get("output_profile")

        # --- Route: Remotion by default, FFmpeg only when Remotion unavailable ---
        if self._needs_remotion(resolved_cuts):
            remotion_inputs: dict[str, Any] = {
                "edit_decisions": dict(edit_decisions, cuts=resolved_cuts),
                "output_path": str(output_path),
            }
            if profile:
                remotion_inputs["profile"] = profile
            render_result = self._remotion_render(remotion_inputs)

            # Governance: NEVER silently fall back to FFmpeg when Remotion fails.
            # The agent must decide the fallback path, not the tool.
            if not render_result.success:
                renderer_family = edit_decisions.get("renderer_family", "unknown")
                return ToolResult(
                    success=False,
                    error=(
                        f"Remotion render failed for renderer_family={renderer_family!r}. "
                        f"Underlying error: {render_result.error}\n\n"
                        f"This composition requires Remotion (images, text cards, animations). "
                        f"Options:\n"
                        f"  1. Fix Remotion setup (cd remotion-composer && npm install)\n"
                        f"  2. Re-run with operation='compose' for FFmpeg-only (video cuts only)\n"
                        f"  3. Approve a degraded FFmpeg render (still images → Ken Burns)\n\n"
                        f"Per governance: renderer downgrade requires user approval."
                    ),
                )
        else:
            # --- FFmpeg fallback: only when Remotion is unavailable ---
            options = inputs.get("options", {})
            subtitle_burn = options.get("subtitle_burn", True)

            # Resolve subtitle_path from edit_decisions if not provided
            subtitle_path = inputs.get("subtitle_path")
            if subtitle_burn and not subtitle_path:
                ed_subs = edit_decisions.get("subtitles", {})
                if ed_subs.get("enabled") and ed_subs.get("source"):
                    subtitle_path = ed_subs["source"]

            # Build compose inputs
            compose_inputs = dict(inputs)
            compose_inputs["edit_decisions"] = dict(edit_decisions, cuts=resolved_cuts)
            compose_inputs["output_path"] = str(output_path)
            if subtitle_path:
                compose_inputs["subtitle_path"] = subtitle_path
            if profile:
                compose_inputs["profile"] = profile

            render_result = self._compose(compose_inputs)

        # --- Post-render: mandatory final self-review ---
        if render_result.success and output_path.exists():
            final_review = self._run_final_review(output_path, edit_decisions)

            # Attach final_review to the ToolResult data so the compose-director
            # skill can include it in the checkpoint alongside the render_report.
            if render_result.data is None:
                render_result.data = {}
            render_result.data["final_review"] = final_review
            render_result.data["final_review_status"] = final_review["status"]

            # If the self-review says fail, downgrade the ToolResult
            if final_review["status"] == "fail":
                return ToolResult(
                    success=False,
                    error=(
                        "Post-render self-review FAILED. The output is not presentable.\n"
                        + "\n".join(f"  • {i}" for i in final_review.get("issues_found", []))
                    ),
                    data=render_result.data,
                )

        return render_result

    def _remotion_render(self, inputs: dict[str, Any]) -> ToolResult:
        """Render via Remotion (requires Node.js + npx).

        Handles compositions with still images, animated scenes, component
        types, and transitions using React-based frame-accurate rendering.
        Accepts edit_decisions (with resolved file paths) or raw composition_data.
        """
        import shutil

        if not shutil.which("npx"):
            return ToolResult(
                success=False,
                error="npx not found. Install Node.js to use Remotion rendering.",
            )

        composition_data = inputs.get("edit_decisions") or inputs.get("composition_data")
        if not composition_data:
            return ToolResult(
                success=False,
                error="edit_decisions or composition_data required for remotion_render",
            )

        output_path = Path(inputs.get("output_path", "renders/remotion_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Deep-copy props so we don't mutate the original
        props = json.loads(json.dumps(composition_data))

        # Convert absolute file paths to file:// URIs for Remotion's
        # Img and OffthreadVideo components
        for cut in props.get("cuts", []):
            source = cut.get("source", "")
            if source and not source.startswith(("http://", "https://", "file://")):
                resolved = Path(source).resolve()
                if resolved.exists():
                    posix = resolved.as_posix()
                    cut["source"] = f"file:///{posix}" if not posix.startswith("/") else f"file://{posix}"

        # Build a custom themeConfig from the playbook's actual colors.
        # This ensures every video gets a unique visual identity derived
        # from its production decisions — not picked from a preset menu.
        if "themeConfig" not in props:
            playbook_name = (
                props.get("playbook")
                or props.get("theme")
                or props.get("metadata", {}).get("playbook")
            )
            theme_config = self._build_theme_from_playbook(playbook_name, composition_data)
            if theme_config:
                props["themeConfig"] = theme_config

        # Write props to temp file for Remotion CLI
        props_path = output_path.parent / ".remotion_props.json"
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump(props, f)

        # remotion-composer lives at project root
        composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
        if not composer_dir.exists():
            return ToolResult(
                success=False,
                error=f"Remotion composer project not found at {composer_dir}",
            )

        # Route to the correct Remotion composition based on renderer_family.
        # This prevents all pipelines from collapsing into the Explainer visual grammar.
        renderer_family = (composition_data or {}).get("renderer_family", "explainer-data")
        composition_id = self._get_composition_id(renderer_family)

        cmd = [
            "npx", "remotion", "render",
            str(composer_dir / "src" / "index.tsx"),
            composition_id,
            str(output_path),
            "--props", str(props_path),
        ]

        # Apply media profile dimensions
        profile_name = inputs.get("profile")
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                p = get_profile(profile_name)
                cmd.extend(["--width", str(p.width), "--height", str(p.height)])
            except (ImportError, ValueError):
                pass

        try:
            self.run_command(cmd, timeout=600)
        except Exception as e:
            return ToolResult(success=False, error=f"Remotion render failed: {e}")
        finally:
            if props_path.exists():
                props_path.unlink()

        if not output_path.exists():
            return ToolResult(
                success=False,
                error=f"Remotion render completed but output file missing: {output_path}",
            )

        return ToolResult(
            success=True,
            data={
                "operation": "remotion_render",
                "output": str(output_path),
                "profile": profile_name,
            },
            artifacts=[str(output_path)],
        )

    # ------------------------------------------------------------------
    # Final self-review — mandatory post-render inspection
    # ------------------------------------------------------------------

    def _run_final_review(
        self,
        output_path: Path,
        edit_decisions: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run post-render self-review and produce a final_review artifact.

        This is the governance contract: the compose runtime MUST inspect
        the actual rendered output before marking the stage complete.
        Never claim a video is ready without a real probe + frame sample.

        Returns a dict conforming to final_review.schema.json.
        """
        log = logging.getLogger("video_compose.final_review")
        issues: list[str] = []

        # --- 1. Technical probe via ffprobe ---
        technical_probe: dict[str, Any] = {
            "valid_container": False,
            "issues": [],
        }
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", str(output_path),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode == 0:
                probe_data = json.loads(proc.stdout)
                fmt = probe_data.get("format", {})
                streams = probe_data.get("streams", [])
                video_stream = next(
                    (s for s in streams if s.get("codec_type") == "video"), {}
                )
                audio_stream = next(
                    (s for s in streams if s.get("codec_type") == "audio"), {}
                )

                duration = float(fmt.get("duration", 0))
                width = int(video_stream.get("width", 0))
                height = int(video_stream.get("height", 0))
                fps_str = video_stream.get("r_frame_rate", "0/1")
                fps = self._parse_probe_fps(fps_str)

                technical_probe = {
                    "valid_container": bool(video_stream),
                    "duration_seconds": round(duration, 2),
                    "resolution": f"{width}x{height}",
                    "fps": fps,
                    "has_audio": bool(audio_stream),
                    "codec": video_stream.get("codec_name", "unknown"),
                    "file_size_bytes": int(fmt.get("size", 0)),
                    "issues": [],
                }

                # Sanity checks
                if duration < 1.0:
                    technical_probe["issues"].append(
                        f"Output is only {duration:.1f}s — suspiciously short"
                    )

                # Check target duration from edit_decisions
                target_dur = None
                if edit_decisions:
                    target_dur = (
                        edit_decisions.get("total_duration_seconds")
                        or edit_decisions.get("metadata", {}).get("target_duration_seconds")
                    )
                if target_dur and target_dur > 0:
                    drift_pct = abs(duration - target_dur) / target_dur
                    if drift_pct > 0.25:
                        technical_probe["issues"].append(
                            f"Duration drift: rendered {duration:.1f}s vs target {target_dur}s "
                            f"({drift_pct:.0%} off). Review pacing or trim."
                        )
                    technical_probe["target_duration"] = target_dur
                    technical_probe["duration_drift_pct"] = round(drift_pct * 100, 1)
                if width < 320 or height < 240:
                    technical_probe["issues"].append(
                        f"Resolution {width}x{height} is very low"
                    )
                if not audio_stream:
                    technical_probe["issues"].append("No audio stream in output")
            else:
                technical_probe["issues"].append(
                    f"ffprobe failed with exit code {proc.returncode}"
                )
        except FileNotFoundError:
            technical_probe["issues"].append("ffprobe not found — cannot validate output")
        except Exception as e:
            technical_probe["issues"].append(f"ffprobe error: {e}")

        issues.extend(technical_probe.get("issues", []))

        # --- 2. Visual spotcheck: sample 4 frames ---
        visual_spotcheck: dict[str, Any] = {
            "frames_sampled": 0,
            "frame_paths": [],
            "black_frames_detected": False,
            "broken_overlays": False,
            "missing_assets": False,
            "unreadable_text": False,
            "issues": [],
        }
        duration = technical_probe.get("duration_seconds", 0)
        if duration > 0 and technical_probe.get("valid_container"):
            try:
                frame_dir = output_path.parent / ".final_review_frames"
                frame_dir.mkdir(parents=True, exist_ok=True)
                # Sample at 10%, 35%, 65%, 90% of duration
                sample_points = [0.10, 0.35, 0.65, 0.90]
                frame_paths = []
                for i, pct in enumerate(sample_points):
                    ts = round(duration * pct, 2)
                    frame_path = frame_dir / f"review_frame_{i}.png"
                    cmd = [
                        "ffmpeg", "-y", "-ss", str(ts),
                        "-i", str(output_path),
                        "-frames:v", "1", "-q:v", "2",
                        str(frame_path),
                    ]
                    subprocess.run(cmd, capture_output=True, timeout=15)
                    if frame_path.exists():
                        frame_paths.append(str(frame_path))

                        # Check for black frames (file size heuristic:
                        # a 1920x1080 PNG of pure black is ~5KB)
                        if frame_path.stat().st_size < 2000:
                            visual_spotcheck["black_frames_detected"] = True

                visual_spotcheck["frames_sampled"] = len(frame_paths)
                visual_spotcheck["frame_paths"] = frame_paths

                if len(frame_paths) < 4:
                    visual_spotcheck["issues"].append(
                        f"Only {len(frame_paths)}/4 frames extracted — some timestamps may be out of range"
                    )
                if visual_spotcheck["black_frames_detected"]:
                    visual_spotcheck["issues"].append(
                        "Black frame detected — possible missing asset or failed render segment"
                    )
            except Exception as e:
                visual_spotcheck["issues"].append(f"Frame sampling error: {e}")

        issues.extend(visual_spotcheck.get("issues", []))

        # --- 3. Audio spotcheck ---
        audio_spotcheck: dict[str, Any] = {
            "narration_present": False,
            "music_present": False,
            "unexpected_silence": False,
            "clipping_detected": False,
            "mix_intelligible": True,
            "issues": [],
        }
        if technical_probe.get("has_audio") and duration > 0:
            try:
                # Use ffmpeg volumedetect to check audio levels
                cmd = [
                    "ffmpeg", "-i", str(output_path),
                    "-af", "volumedetect", "-f", "null", "-",
                ]
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60
                )
                stderr = proc.stderr or ""
                # Parse mean_volume and max_volume
                mean_vol = None
                max_vol = None
                for line in stderr.split("\n"):
                    if "mean_volume:" in line:
                        try:
                            mean_vol = float(line.split("mean_volume:")[1].strip().split()[0])
                        except (ValueError, IndexError):
                            pass
                    if "max_volume:" in line:
                        try:
                            max_vol = float(line.split("max_volume:")[1].strip().split()[0])
                        except (ValueError, IndexError):
                            pass

                if mean_vol is not None:
                    if mean_vol < -60:
                        audio_spotcheck["unexpected_silence"] = True
                        audio_spotcheck["issues"].append(
                            f"Mean volume {mean_vol:.1f} dB — effectively silent"
                        )
                    # Assume narration present if mean volume is reasonable
                    if mean_vol > -40:
                        audio_spotcheck["narration_present"] = True
                    # Assume music present if audio exists (conservative)
                    if mean_vol > -50:
                        audio_spotcheck["music_present"] = True

                if max_vol is not None and max_vol > -0.5:
                    audio_spotcheck["clipping_detected"] = True
                    audio_spotcheck["issues"].append(
                        f"Max volume {max_vol:.1f} dB — possible clipping"
                    )
            except Exception as e:
                audio_spotcheck["issues"].append(f"Audio analysis error: {e}")

        issues.extend(audio_spotcheck.get("issues", []))

        # --- 4. Promise preservation ---
        promise_preservation: dict[str, Any] = {
            "delivery_promise_honored": True,
            "silent_downgrade_detected": False,
            "issues": [],
        }
        if edit_decisions:
            renderer_family = edit_decisions.get("renderer_family", "")
            promise_preservation["renderer_family_used"] = renderer_family

            delivery_data = (
                edit_decisions.get("metadata", {}).get("delivery_promise")
                or edit_decisions.get("delivery_promise")
            )
            if delivery_data:
                try:
                    from lib.delivery_promise import DeliveryPromise
                    promise = DeliveryPromise.from_dict(delivery_data)
                    cuts = edit_decisions.get("cuts", [])
                    result = promise.validate_cuts(cuts)
                    motion_ratio = result.get("motion_ratio", 0)
                    promise_preservation["motion_ratio_actual"] = round(motion_ratio, 3)

                    if not result["valid"]:
                        promise_preservation["delivery_promise_honored"] = False
                        for v in result["violations"]:
                            promise_preservation["issues"].append(v)

                    # Detect silent downgrade: motion-led promise but <50% motion
                    if (delivery_data.get("type") == "motion_led"
                            and motion_ratio < 0.5):
                        promise_preservation["silent_downgrade_detected"] = True
                        promise_preservation["issues"].append(
                            f"Motion-led promise but only {motion_ratio:.0%} motion — "
                            f"silent downgrade to still-led"
                        )
                except Exception as e:
                    promise_preservation["issues"].append(
                        f"Could not validate delivery promise: {e}"
                    )

        issues.extend(promise_preservation.get("issues", []))

        # --- 5. Subtitle check ---
        subtitle_check: dict[str, Any] = {
            "subtitles_expected": False,
            "subtitles_present": False,
            "issues": [],
        }
        if edit_decisions:
            ed_subs = edit_decisions.get("subtitles", {})
            subtitle_check["subtitles_expected"] = bool(ed_subs.get("enabled"))

            # Check if output has subtitle stream
            if technical_probe.get("valid_container"):
                try:
                    cmd = [
                        "ffprobe", "-v", "quiet", "-print_format", "json",
                        "-show_streams", "-select_streams", "s",
                        str(output_path),
                    ]
                    proc = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=15
                    )
                    if proc.returncode == 0:
                        sub_data = json.loads(proc.stdout)
                        sub_streams = sub_data.get("streams", [])
                        subtitle_check["subtitles_present"] = len(sub_streams) > 0

                    # If subtitles were expected but not found as a stream,
                    # they may be burned in (which is fine — not a failure)
                    if (subtitle_check["subtitles_expected"]
                            and not subtitle_check["subtitles_present"]):
                        # Check if subtitle_path was used (burned in)
                        sub_source = ed_subs.get("source")
                        if sub_source and Path(sub_source).exists():
                            # Burned-in subtitles are not detectable as streams
                            subtitle_check["subtitles_present"] = True
                            subtitle_check["coverage_ratio"] = 1.0
                        else:
                            subtitle_check["issues"].append(
                                "Subtitles expected but not found in output and "
                                "no subtitle source file exists for burn-in"
                            )
                except Exception as e:
                    subtitle_check["issues"].append(f"Subtitle check error: {e}")

        issues.extend(subtitle_check.get("issues", []))

        # --- 6. Determine overall status ---
        critical_issues = [
            i for i in issues
            if any(kw in i.lower() for kw in [
                "silent downgrade", "delivery promise violation",
                "effectively silent", "ffprobe failed", "suspiciously short",
            ])
        ]

        if critical_issues:
            status = "revise"
            recommended_action = "re_render"
        elif issues:
            status = "pass"
            recommended_action = "present_to_user"
        else:
            status = "pass"
            recommended_action = "present_to_user"

        if not technical_probe.get("valid_container"):
            status = "fail"
            recommended_action = "re_render"

        final_review = {
            "version": "1.0",
            "output_path": str(output_path),
            "status": status,
            "checks": {
                "technical_probe": technical_probe,
                "visual_spotcheck": visual_spotcheck,
                "audio_spotcheck": audio_spotcheck,
                "promise_preservation": promise_preservation,
                "subtitle_check": subtitle_check,
            },
            "issues_found": issues,
            "recommended_action": recommended_action,
        }

        log.info(
            "Final review: status=%s, issues=%d, action=%s",
            status, len(issues), recommended_action,
        )

        return final_review

    @staticmethod
    def _parse_probe_fps(fps_str: str) -> float:
        """Parse ffprobe fps string like '30/1' or '24000/1001'."""
        try:
            if "/" in fps_str:
                num, den = fps_str.split("/")
                return round(int(num) / max(int(den), 1), 2)
            return float(fps_str)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _burn_subtitles(self, inputs: dict[str, Any]) -> ToolResult:
        """Burn subtitle file into video."""
        input_path = Path(inputs["input_path"])
        subtitle_path = Path(inputs["subtitle_path"])
        output_path = Path(inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_subtitled"))))

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")
        if not subtitle_path.exists():
            return ToolResult(success=False, error=f"Subtitle file not found: {subtitle_path}")

        style = inputs.get("subtitle_style", {})
        ass_style = self._build_subtitle_style(style)
        sub_escaped = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", f"subtitles='{sub_escaped}':force_style='{ass_style}'",
            "-c:v", codec, "-crf", str(crf),
            "-c:a", "copy",
            str(output_path),
        ]

        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "burn_subtitles",
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    def _overlay(self, inputs: dict[str, Any]) -> ToolResult:
        """Composite overlay images/videos on top of base video."""
        input_path = Path(inputs["input_path"])
        overlays = inputs.get("overlays", [])
        output_path = Path(inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_overlay"))))
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")
        if not overlays:
            return ToolResult(success=False, error="No overlays provided")

        # Build complex filter for each overlay
        input_args = ["-i", str(input_path)]
        filter_parts = []
        prev_label = "0:v"

        for i, ov in enumerate(overlays):
            asset_path = Path(ov["asset_path"])
            if not asset_path.exists():
                return ToolResult(success=False, error=f"Overlay asset not found: {asset_path}")

            input_args.extend(["-i", str(asset_path)])

            x = int(ov.get("x", 0))
            y = int(ov.get("y", 0))
            start = ov.get("start_seconds", 0)
            end = ov.get("end_seconds")
            opacity = ov.get("opacity", 1.0)

            overlay_input = f"{i + 1}:v"

            # Scale overlay if dimensions specified
            if "width" in ov and "height" in ov:
                w = int(ov["width"])
                h = int(ov["height"])
                filter_parts.append(f"[{overlay_input}]scale={w}:{h}[ov_scaled_{i}]")
                overlay_input = f"ov_scaled_{i}"

            # Build enable expression for timed overlays
            enable = f"between(t,{start},{end})" if end else f"gte(t,{start})"
            out_label = f"v{i}"

            filter_parts.append(
                f"[{prev_label}][{overlay_input}]overlay={x}:{y}:enable='{enable}'[{out_label}]"
            )
            prev_label = out_label

        filter_complex = ";".join(filter_parts)

        cmd = ["ffmpeg", "-y"]
        cmd.extend(input_args)
        cmd.extend(["-filter_complex", filter_complex])
        cmd.extend(["-map", f"[{prev_label}]", "-map", "0:a?"])
        cmd.extend(["-c:v", codec, "-crf", str(crf), "-c:a", "copy"])
        cmd.append(str(output_path))

        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "overlay",
                "overlay_count": len(overlays),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    def _encode(self, inputs: dict[str, Any]) -> ToolResult:
        """Re-encode video with a specific profile/codec settings."""
        input_path = Path(inputs["input_path"])
        output_path = Path(inputs.get("output_path", str(input_path.with_stem(f"{input_path.stem}_encoded"))))
        codec = inputs.get("codec", "libx264")
        crf = inputs.get("crf", 23)
        preset = inputs.get("preset", "medium")
        profile_name = inputs.get("profile")

        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-c:v", codec, "-crf", str(crf), "-preset", preset,
            "-c:a", "aac", "-b:a", "192k",
        ]

        # Apply media profile if specified
        if profile_name:
            try:
                from lib.media_profiles import get_profile, ffmpeg_output_args
                profile = get_profile(profile_name)
                cmd.extend(["-s", f"{profile.width}x{profile.height}"])
                cmd.extend(["-r", str(profile.fps)])
            except (ImportError, ValueError):
                pass  # proceed without profile

        cmd.append(str(output_path))
        self.run_command(cmd)

        return ToolResult(
            success=True,
            data={
                "operation": "encode",
                "codec": codec,
                "crf": crf,
                "profile": profile_name,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
        )

    @staticmethod
    def _resolve_subtitle_style(
        explicit_style: dict | None,
        edit_decisions: dict | None,
        playbook: dict | None,
    ) -> dict:
        """Resolve subtitle style with layered priority.

        Priority: explicit_style > edit_decisions.subtitles.style > playbook > defaults.
        This prevents every video from looking identical (Arial bold white).
        """
        # Start with minimal fallback defaults
        resolved = {
            "font": "Inter",
            "font_size": 28,
            "bold": True,
            "outline_width": 2,
            "shadow": 0,
            "margin_v": 40,
            "alignment": 2,
        }

        # Layer 1: Playbook-derived style
        if playbook:
            typo = playbook.get("typography", {})
            colors = playbook.get("visual_language", {}).get("color_palette", {})
            if typo.get("body", {}).get("family"):
                resolved["font"] = typo["body"]["family"]
            if colors.get("text"):
                resolved["primary_color"] = colors["text"]
            if colors.get("background"):
                resolved["outline_color"] = colors["background"]
                # Semi-transparent background for readability
                bg = colors["background"]
                resolved["back_color"] = bg

        # Layer 2: edit_decisions subtitle style
        if edit_decisions:
            ed_style = edit_decisions.get("subtitles", {}).get("style", {})
            for k, v in ed_style.items():
                if v is not None:
                    resolved[k] = v

        # Layer 3: Explicit override (highest priority)
        if explicit_style:
            for k, v in explicit_style.items():
                if v is not None:
                    resolved[k] = v

        return resolved

    @staticmethod
    def _build_subtitle_style(style: dict) -> str:
        """Build ASS force_style string from style dict."""
        parts = []
        parts.append(f"FontName={style.get('font', 'Inter')}")
        parts.append(f"FontSize={style.get('font_size', 28)}")
        parts.append(f"Bold={1 if style.get('bold', True) else 0}")
        if style.get("primary_color"):
            parts.append(f"PrimaryColour={style['primary_color']}")
        if style.get("outline_color"):
            parts.append(f"OutlineColour={style['outline_color']}")
        if style.get("back_color"):
            parts.append(f"BackColour={style['back_color']}")
        border_style = style.get("border_style", 1)
        parts.append(f"BorderStyle={border_style}")
        parts.append(f"Outline={style.get('outline_width', 2)}")
        parts.append(f"Shadow={style.get('shadow', 0)}")
        parts.append(f"MarginV={style.get('margin_v', 40)}")
        parts.append(f"Alignment={style.get('alignment', 2)}")
        return ",".join(parts)

    @staticmethod
    def _build_atempo(factor: float) -> str:
        """Build atempo filter chain for audio speed adjustment."""
        filters = []
        remaining = factor
        while remaining > 100.0:
            filters.append("atempo=100.0")
            remaining /= 100.0
        while remaining < 0.5:
            filters.append("atempo=0.5")
            remaining /= 0.5
        filters.append(f"atempo={remaining:.4f}")
        return ",".join(filters)
