"""Video composition tool — FFmpeg + Remotion + HyperFrames (runtime-aware).

Pipeline-facing orchestration surface for composition. Takes `edit_decisions`,
`asset_manifest`, and audio, and delegates to the technical runtime chosen
at proposal stage.

Routing is driven by `edit_decisions.render_runtime` (locked at proposal):

- `remotion`   → React-based frame-accurate render via `npx remotion render`.
                 Handles the existing scene-component stack, word-level captions,
                 TalkingHead/CinematicRenderer. Current default.
- `hyperframes` → HTML/CSS/GSAP render via `hyperframes_compose`.
                 Handles kinetic typography, product promos, website-to-video,
                 registry blocks. Added in the parallel-runtime initiative.
- `ffmpeg`     → FFmpeg concat/trim. Used only for simple video cuts without
                 composition, or when the approved path explicitly names FFmpeg.

Authoring mode is orthogonal to runtime. Setting
`edit_decisions.composition_mode = "atelier"` (or `renderer_family="bespoke"`)
means the composition is hand-authored rather than assembled from stock scene
components. Runtime still wins first: HyperFrames atelier routes through
`hyperframes_compose`, FFmpeg stays FFmpeg-only, and only Remotion atelier uses
`_render_via_atelier` for a project-local Remotion entry that bypasses the
cut-schema and stock scene-type registry.

Silent runtime swaps are forbidden by governance. If the chosen runtime is
unavailable or fails, this tool surfaces a structured blocker and waits for
the agent to re-ask the user rather than substituting a different engine.
"""

from __future__ import annotations

import json
import logging
import os
import re
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
        # "operation" is NOT required here even though it's the schema's one
        # semantically-obvious field: execute() below deliberately defaults it
        # to "compose" (see the comment there for why). Listing it as required
        # would make tool_bridge's generic required-field pre-validation
        # reject the exact calls this tool is designed to accept without an
        # explicit operation — reintroducing the KeyError-style bug that
        # default was added to fix. Keep this empty/absent unless a genuinely
        # non-defaulted field becomes required.
        "required": [],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["compose", "render", "remotion_render", "burn_subtitles", "overlay", "encode", "extract_poster"],
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
            "proposal_packet": {
                "type": "object",
                "description": (
                    "Full proposal_packet artifact. Optional but STRONGLY "
                    "recommended — when present, final_review compares "
                    "proposal_packet.production_plan.render_runtime against "
                    "edit_decisions.render_runtime and flags runtime_swap_detected. "
                    "Without it, runtime-swap detection falls back to checking "
                    "edit_decisions.metadata.proposal_render_runtime."
                ),
            },
            "narration_transcript_path": {
                "type": "string",
                "description": (
                    "Path to a word-level transcript JSON (from `transcriber` "
                    "tool output). Optional but STRONGLY recommended: when "
                    "combined with script_path/script_text, final_review "
                    "runs transcript_comparison and catches TTS failures "
                    "like 'Chirp3-HD reads ... as the word dot'. Without "
                    "it, content-level audio bugs ship silently."
                ),
            },
            "script_path": {
                "type": "string",
                "description": (
                    "Path to the source narration script (plain text). "
                    "Used by transcript_comparison to diff against the "
                    "transcribed audio. Provide this OR script_text."
                ),
            },
            "script_text": {
                "type": "string",
                "description": (
                    "Inline source narration script. Used by "
                    "transcript_comparison when a file path is unavailable."
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
            "remotion_timeout_ms": {
                "type": "integer",
                "description": (
                    "Remotion render timeout in milliseconds, passed through as "
                    "`--timeout` (governs headless-browser setup and delayRender). "
                    "Raise this when the browser is slow to start (e.g. restricted "
                    "networks). The subprocess timeout is widened to match."
                ),
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=5000, network_required=False
    )

    # Remotion scene types that trigger React-based rendering — the ONE list.
    # Mirrors remotion-composer/SCENE_TYPES.md's table (and Explainer's
    # SceneRenderer branches), which is the authority. This used to be two
    # hand-maintained lists that had drifted apart AND away from reality:
    # both advertised "progress" and "chart", which no renderer has ever
    # implemented, while omitting progress_bar, hero_title, terminal_scene,
    # anime_scene and screenshot_scene, which it does (audit 2026-07-15, B5).
    # get_info() exposes this to agents, so a stale entry is a lie they act on.
    _REMOTION_COMPONENTS = [
        "text_card", "stat_card", "callout", "comparison", "hero_title",
        "bar_chart", "line_chart", "pie_chart", "kpi_grid", "progress_bar",
        "anime_scene", "terminal_scene", "screenshot_scene",
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

    def _hyperframes_available(self) -> bool:
        """Check if HyperFrames rendering is available.

        Delegates to the dedicated tool so the availability check stays in
        one place (node 22 floor, ffmpeg + npx on PATH).
        """
        try:
            from tools.video.hyperframes_compose import HyperFramesCompose
            return bool(HyperFramesCompose()._runtime_check()["runtime_available"])
        except Exception:
            return False

    def get_info(self) -> dict[str, Any]:
        """Extend base get_info to surface all available render runtimes.

        Preflight reports each runtime's availability separately so the agent
        can choose an appropriate `render_runtime` at proposal stage. Silent
        fallback between runtimes is forbidden.
        """
        info = super().get_info()
        remotion_ok = self._remotion_available()
        hyperframes_ok = self._hyperframes_available()
        info["render_engines"] = {
            "ffmpeg": True,
            "remotion": remotion_ok,
            "hyperframes": hyperframes_ok,
        }
        # Backwards-compat alias — some proposal skills inspect this name.
        info["render_runtimes"] = info["render_engines"]

        if remotion_ok:
            info["remotion_components"] = self._REMOTION_COMPONENTS
            info["remotion_note"] = (
                "Remotion is available for React-based rendering. Use it for "
                "image-to-video with spring animations, animated text/stat cards, "
                "charts, callouts, comparisons, and word-level caption burn. "
                "Prefer Remotion over Ken Burns pan-and-zoom for explainer "
                "and motion-graphics pipelines that already use the scene-component stack."
            )
        else:
            composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
            if composer_dir.exists() and (composer_dir / "package.json").exists() and not (composer_dir / "node_modules").exists():
                info["remotion_note"] = (
                    "Remotion project exists but node_modules are NOT installed. "
                    "Run 'cd remotion-composer && npm install' to enable Remotion rendering."
                )
            else:
                info["remotion_note"] = (
                    "Remotion is NOT available (needs Node.js/npx + remotion-composer + node_modules)."
                )

        if hyperframes_ok:
            info["hyperframes_note"] = (
                "HyperFrames is available for HTML/CSS/GSAP composition. Use it "
                "for kinetic typography, product promos, launch reels, "
                "website-to-video, and registry-block-driven scenes. Consumed via "
                "'npx hyperframes' (npm package: 'hyperframes'). "
                "Before locking render_runtime='hyperframes' at the proposal stage, "
                "verify the runtime with `hyperframes_compose` operation='doctor' "
                "or `make hyperframes-doctor`. An 'available' flag from the runtime "
                "check means node + ffmpeg + the npm package all resolve; it does "
                "not guarantee a render will succeed on the first specific "
                "composition."
            )
        else:
            info["hyperframes_note"] = (
                "HyperFrames is NOT available. Requires Node.js >= 22, FFmpeg, "
                "npx on PATH, and the 'hyperframes' npm package to be resolvable. "
                "Run `make hyperframes-doctor` to see the specific missing piece, "
                "or call `hyperframes_compose` operation='doctor' directly."
            )

        # Governance note — agents and reviewers consume this.
        info["runtime_governance"] = (
            "render_runtime is locked at proposal stage and carried unchanged "
            "through edit_decisions. Silent swaps are forbidden. If the "
            "chosen runtime fails, surface a structured blocker and wait for "
            "user approval before switching."
        )
        return info

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        # "compose" is the overwhelmingly common call (assemble the final
        # render from edit_decisions) and tool_bridge's own output-path
        # routing already assumes it as the default when unspecified
        # (server/app/runner/tool_bridge.py). Requiring the agent to always
        # spell out operation="compose" for the one truly obvious case caused
        # repeated KeyError('operation') failures — burning through an entire
        # stage's turn budget before ever calling _compose().
        operation = inputs.get("operation", "compose")
        start = time.time()

        try:
            if operation == "compose":
                result = self._compose(inputs)
                # The direct compose operation is tool_bridge's DEFAULT and
                # its output is routed as the official renders/final.mp4 —
                # yet it previously bypassed the mandatory final self-review
                # entirely (only _render's engine paths ran it), so a silent
                # or broken deliverable shipped unreviewed (audit 2026-07-16,
                # Wave 1 ⑦). Gate it exactly like _render does.
                result = self._review_and_gate(
                    result,
                    Path(inputs.get("output_path", "composed_output.mp4")),
                    inputs.get("edit_decisions") or {},
                    inputs,
                )
            elif operation == "render":
                result = self._render(inputs)
            elif operation == "remotion_render":
                result = self._remotion_render(inputs)
            elif operation == "burn_subtitles":
                result = self._burn_subtitles(inputs)
            elif operation == "overlay":
                result = self._overlay(inputs)
            elif operation == "extract_poster":
                result = self._extract_poster(inputs)
            elif operation == "encode":
                result = self._encode(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

        result.duration_seconds = round(time.time() - start, 2)
        return result

    _IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}

    # Broadcast-standard HD color tagging for every libx264 encode. Mixed
    # provider sources (Seedance/Kling/Pexels) arrive with inconsistent or
    # missing color metadata; without explicit bt709 tags players guess —
    # concat output could shift/wash colors depending on the player (audit
    # 2026-07-16, Wave 1 ⑥). Tagging at encode time makes the deliverable
    # unambiguous.
    _COLOR_TAG_FLAGS = [
        "-colorspace", "bt709",
        "-color_primaries", "bt709",
        "-color_trc", "bt709",
    ]

    # ...but the flags above are NOT sufficient on an ENCODE path. Verified
    # against ffmpeg 8.1/libx264: as output options they only reach the SPS
    # VUI for `colorspace` (matrix coefficients) — primaries and trc are
    # dropped, producing a half-tagged stream (color_space=bt709,
    # color_primaries=unknown, color_transfer=unknown) that still leaves
    # players guessing 2 of the 3 values. Setting the properties on the
    # FRAMES via setparams makes the encoder emit all three. Encoder-
    # agnostic, unlike -x264-params. On a stream COPY the output flags do
    # write all three (container-level metadata), so they stay for that path.
    _SETPARAMS_BT709 = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709"

    # +faststart moves the moov atom to the file head so web players start
    # progressive playback immediately. Pure mux-time flag — works with
    # -c copy too.
    _FASTSTART_FLAGS = ["-movflags", "+faststart"]

    @staticmethod
    def _is_image(path: Path) -> bool:
        """Check if a file is a still image (routes to Remotion, not FFmpeg)."""
        return path.suffix.lower() in VideoCompose._IMAGE_EXTENSIONS

    @staticmethod
    def _has_audio_stream(path: Path) -> bool:
        """Return True iff ffprobe reports at least one audio stream.

        Many stock video clips (especially from Pexels) ship with no audio
        stream at all. If we blindly tell ffmpeg to transcode the 0:a stream
        on such a file it errors out. This helper lets the segment builder
        branch on stream presence so it can synthesize a silent track when
        needed, keeping the concat segment layout consistent.
        """
        try:
            out = subprocess.check_output(
                [
                    "ffprobe", "-v", "error",
                    "-select_streams", "a",
                    "-show_entries", "stream=codec_type",
                    "-of", "default=nw=1:nk=1",
                    str(path),
                ],
                stderr=subprocess.STDOUT,
                text=True,
            )
            return "audio" in out
        except Exception:
            return False

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
        # A named profile's codec/CRF are binding unless explicitly
        # overridden. media_profiles.py declares per-platform CRF 16-20, but
        # this method previously read only the profile's width/height/fps —
        # every profiled render silently fell back to CRF 23.
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                _p = get_profile(profile_name)
                if "codec" not in inputs:
                    codec = _p.codec
                if "crf" not in inputs:
                    crf = _p.crf
            except ImportError:
                pass  # lib unavailable — proceed with defaults
            except ValueError as e:
                # A typo'd profile name must NOT silently render the default
                # aspect ratio: asking for a 9:16 delivery and getting 16:9 is
                # an invisible, catastrophic substitution (found by E2E render
                # inspection, 2026-07-17 — 'douyin_vertical' silently produced
                # 1920x1080). get_profile's error already lists valid names.
                return ToolResult(success=False, error=str(e))

        # Resolve target resolution + fit mode. Priority: explicit `profile`
        # arg > edit_decisions.metadata.compose_target > default (landscape HD).
        # compose_target = {"width": W, "height": H, "fit": "pad"|"cover"} lets a
        # caller request vertical (9:16) or any aspect without a named profile.
        # fit="pad" letterboxes (no content loss, the historical default);
        # fit="cover" scales-to-fill and centre-crops (better for vertical social).
        resolution = "1920x1080"
        fit_mode = "pad"
        compose_target = (edit_decisions.get("metadata") or {}).get("compose_target")
        if isinstance(compose_target, dict):
            try:
                resolution = f"{int(compose_target['width'])}x{int(compose_target['height'])}"
            except (KeyError, ValueError, TypeError):
                pass
            if compose_target.get("fit") in ("pad", "cover"):
                fit_mode = compose_target["fit"]
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                p = get_profile(profile_name)
                resolution = f"{p.width}x{p.height}"
            except ImportError:
                pass  # lib unavailable — proceed with defaults
            except ValueError as e:
                # A typo'd profile name must NOT silently render the default
                # aspect ratio: asking for a 9:16 delivery and getting 16:9 is
                # an invisible, catastrophic substitution (found by E2E render
                # inspection, 2026-07-17 — 'douyin_vertical' silently produced
                # 1920x1080). get_profile's error already lists valid names.
                return ToolResult(success=False, error=str(e))
        try:
            target_w, target_h = (int(v) for v in resolution.split("x"))
        except ValueError:
            target_w, target_h = 1920, 1080

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

        aigc_explicit_burned = False

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

                # Explicit AIGC label on the OPENING segment (roadmap 0.1,
                # 《标识办法》): burned during the segment's own encode pass —
                # segment 0 is the timeline's start, so no extra generation
                # loss and no post-pass re-encode. The helper returns a
                # filtergraph SUFFIX (movie/overlay watermark — concatenated
                # directly, never comma-joined) or None (already logged) when
                # no CJK font exists; that gap is surfaced in the result data.
                aigc_vf = None
                if i == 0:
                    from tools.video.aigc_label import opening_label_filter
                    aigc_vf = opening_label_filter(target_w, target_h, temp_dir)
                    aigc_explicit_burned = bool(aigc_vf)

                if self._is_image(source):
                    # Eased zoompan Ken Burns segment (Wave 3, M6). The
                    # "degraded FFmpeg render (still images → Ken Burns)"
                    # this tool advertised never existed — stills were
                    # rejected outright, forcing Remotion even for a plain
                    # fallback render. Remotion remains the preferred route
                    # for image-led compositions; this keeps the ffmpeg
                    # fallback honest.
                    err = self._encode_kenburns_segment(
                        source, seg_path, duration, cut,
                        target_w, target_h, fit_mode, codec, crf, preset,
                        extra_vf=aigc_vf,
                    )
                    if err is not None:
                        return err
                    temp_segments.append(seg_path)
                    continue
                else:
                    # Video source: trim to segment.
                    #
                    # Semantics:
                    #   -ss BEFORE -i   → fast input-level seek to in_s
                    #   -t  AFTER  -i   → "play for `duration` seconds"
                    #                     (unambiguous regardless of seek mode)
                    #
                    # We MUST re-encode here — `-c copy` cannot do frame-accurate
                    # cuts because it snaps to keyframes. With sparse GOPs (common
                    # in Pexels / AI-generated clips), stream-copy can produce
                    # segments significantly longer than `duration`, breaking the
                    # target timeline. Re-encoding with libx264/AAC is slower but
                    # gives exact cut boundaries. Same resolution in → same
                    # resolution out, so same-res inputs concat cleanly.
                    cmd = [
                        "ffmpeg", "-y",
                        "-ss", str(in_s),
                        "-t", str(duration),
                        "-i", str(source),
                    ]

                    # Normalize every segment to a consistent container so the
                    # concat-copy step is always safe. The concat demuxer with
                    # `-c copy` requires identical codec / resolution / fps /
                    # pix_fmt / sar across ALL segments — otherwise it throws
                    # "Non-monotonous DTS" or silently produces corrupt output.
                    #
                    # Target is target_w x target_h @ 30fps, yuv420p, sar=1
                    # (default 1920x1080; overridable via `profile` or
                    # edit_decisions.metadata.compose_target — see above).
                    # fit="pad" letterboxes to preserve all content; fit="cover"
                    # scales-to-fill then centre-crops (no bars, for vertical social).
                    if fit_mode == "cover":
                        geom = [
                            f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase",
                            f"crop={target_w}:{target_h}",
                        ]
                    else:
                        geom = [
                            f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease",
                            f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black",
                        ]
                    vf_parts: list[str] = [*geom, "setsar=1", "fps=30", self._SETPARAMS_BT709]
                    af_parts: list[str] = []
                    if speed != 1.0:
                        vf_parts.append(f"setpts={1.0/speed}*PTS")
                        af_parts.append(self._build_atempo(speed))

                    # The aigc suffix is a labeled filtergraph tail
                    # ("[aigc_base];movie=...") — direct concat, never
                    # comma-joined (see opening_label_filter).
                    vf_str = ",".join(vf_parts) + (aigc_vf or "")
                    cmd.extend(["-filter:v", vf_str])
                    if af_parts:
                        cmd.extend(["-filter:a", ",".join(af_parts)])

                    cmd.extend([
                        "-c:v", codec,
                        "-crf", str(crf),
                        "-preset", preset,
                        "-pix_fmt", "yuv420p",
                        *self._COLOR_TAG_FLAGS,
                        "-r", "30",
                    ])

                    # Audio handling: some source clips have no audio stream
                    # (Pexels stock often ships silent). If we unconditionally
                    # ask ffmpeg to copy/encode the 0:a stream it errors out.
                    # Probe for an audio stream first — if present, transcode
                    # to AAC; if absent, synthesize a silent stereo track so
                    # concat segments have a consistent stream layout.
                    has_audio = self._has_audio_stream(source)
                    if has_audio:
                        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"])
                    else:
                        # Inject silent audio via lavfi before the output.
                        # We have to rebuild cmd to add the lavfi input
                        # before the output path and map streams explicitly.
                        cmd = [
                            "ffmpeg", "-y",
                            "-ss", str(in_s),
                            "-t", str(duration),
                            "-i", str(source),
                            "-f", "lavfi",
                            "-t", str(duration),
                            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                            "-filter:v", vf_str,
                        ]
                        if af_parts:
                            cmd.extend(["-filter:a", ",".join(af_parts)])
                        cmd.extend([
                            "-map", "0:v:0",
                            "-map", "1:a:0",
                            "-c:v", codec,
                            "-crf", str(crf),
                            "-preset", preset,
                            "-pix_fmt", "yuv420p",
                            *self._COLOR_TAG_FLAGS,
                            "-r", "30",
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-ar", "48000",
                            "-ac", "2",
                        ])

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
                except ImportError:
                    pass  # lib unavailable — proceed with defaults
                except ValueError as e:
                    # A typo'd profile name must NOT silently render the default
                    # aspect ratio: asking for a 9:16 delivery and getting 16:9 is
                    # an invisible, catastrophic substitution (found by E2E render
                    # inspection, 2026-07-17 — 'douyin_vertical' silently produced
                    # 1920x1080). get_profile's error already lists valid names.
                    return ToolResult(success=False, error=str(e))

            needs_reencode = bool(vfilters) or bool(profile_flags)

            if needs_reencode:
                # setparams keeps all three color tags on the re-encode (the
                # output flags alone only carry `colorspace` — see
                # _SETPARAMS_BT709).
                cmd.extend(["-vf", ",".join([*vfilters, self._SETPARAMS_BT709])])
                # This is the SECOND lossy generation (segments were already
                # encoded at `crf`) — finish at least one notch finer so the
                # subtitle-burn pass doesn't stack visible loss on top.
                finishing_crf = min(crf, 18)
                cmd.extend(["-c:v", codec, "-crf", str(finishing_crf), "-preset", preset])
                cmd.extend(self._COLOR_TAG_FLAGS)
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

            # Deliverable mux polish — works on the copy path too.
            cmd.extend(self._FASTSTART_FLAGS)
            cmd.append(str(output_path))
            self.run_command(cmd)

            # Same post-render normalization the Remotion path gets — the two
            # paths produce the same kind of deliverable and must meet the
            # same -14 LUFS target. Skipped for a genuinely silent
            # composition (nothing to normalize).
            loudness_normalized = False
            if self._has_audio_stream(output_path):
                loudness_normalized = self._normalize_deliverable_loudness(output_path)

            # Implicit AIGC label: provider identity + content ID in the
            # container metadata, via a lossless remux (roadmap 0.1 —
            # mandatory compose step; must survive export/download).
            from tools.video.aigc_label import embed_aigc_metadata
            aigc_meta = embed_aigc_metadata(output_path, run_command=self.run_command)

            return ToolResult(
                success=True,
                data={
                    "operation": "compose",
                    "loudness_normalized": loudness_normalized,
                    "loudness_target_lufs": -14 if loudness_normalized else None,
                    "cut_count": len(cuts),
                    "has_subtitles": subtitle_path is not None,
                    "has_mixed_audio": audio_path is not None,
                    "profile": profile_name,
                    "output": str(output_path),
                    "aigc_label": {
                        "explicit_burned": aigc_explicit_burned,
                        "metadata": aigc_meta,
                    },
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

    # Same set, for the _needs_remotion fast path — derived, never re-typed.
    _REMOTION_SCENE_TYPES = frozenset(_REMOTION_COMPONENTS)

    # Maps renderer_family (set at proposal stage) to Remotion composition ID.
    # Each family MUST map to a distinct composition — collapsing defeats visual grammar.
    # Maps renderer_family → Remotion composition ID.
    # Only compositions registered in remotion-composer/src/Root.tsx are valid.
    # Current compositions: Explainer, CinematicRenderer, TalkingHead
    RENDERER_FAMILY_MAP = {
        "explainer-data": "Explainer",
        "explainer-teacher": "Explainer",
        "cinematic-trailer": "CinematicRenderer",
        "documentary-montage": "CinematicRenderer",
        "product-reveal": "Explainer",
        "screen-demo": "Explainer",
        "presenter": "TalkingHead",
        "animation-first": "Explainer",
    }

    # Root-level prop field each composition actually reads its scene/clip
    # list from — see each .tsx's Props interface. Used by _remotion_render
    # to refuse a templated render whose edit_decisions can't possibly
    # satisfy the target composition (see the fail-loud guard there).
    _COMPOSITION_REQUIRED_FIELD = {
        "Explainer": "cuts",
        "CinematicRenderer": "scenes",
        "TalkingHead": "videoSrc",
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

    def _render_via_atelier(
        self,
        inputs: dict[str, Any],
        edit_decisions: dict[str, Any],
    ) -> ToolResult:
        """Render a hand-authored, project-local Remotion composition ("atelier" mode).

        Unlike the cut-schema path, atelier mode does NOT route through the
        stock Explainer/CinematicRenderer compositions, the cut.type scene
        registry, or RENDERER_FAMILY_MAP. The agent hand-authors a bespoke
        composition — its own scenes, theme, and motion — and points this
        renderer at the project-local entry. This is the deliberate
        "hand-stitched every time" path: zero reusable creative components,
        a fresh visual language per video.

        Contract — edit_decisions["bespoke"] = {
            "entry":          <path to the project-local Remotion entry .tsx;
                               MUST live under remotion-composer/ so the
                               Remotion bundler can resolve node_modules.
                               Convention: remotion-composer/projects/<slug>/index.tsx>,
            "composition_id": <id registered in that entry's Root>,
            "props_path":     <optional absolute path to a props JSON (--props)>,
            "public_dir":     <optional path to a SMALL per-project public dir,
                               avoids copying the bloated shared public/>,
            "scale":          <optional float, e.g. 0.5 for a fast draft>,
            "crf":            <optional int, e.g. 18 for a crisp final>,
            "concurrency":    <optional int>,
        }
        """
        bespoke = edit_decisions.get("bespoke") or {}
        entry = bespoke.get("entry")
        comp_id = bespoke.get("composition_id")
        if not entry or not comp_id:
            return ToolResult(
                success=False,
                error=(
                    "atelier mode requires edit_decisions.bespoke.entry (path to the "
                    "project-local Remotion entry .tsx) and edit_decisions.bespoke."
                    "composition_id (the id registered in that entry's Root)."
                ),
            )

        composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
        if not composer_dir.exists() or not (composer_dir / "node_modules").exists():
            return ToolResult(
                success=False,
                error=(
                    f"remotion-composer or its node_modules is missing at {composer_dir}. "
                    f"Run `cd remotion-composer && npm install` first."
                ),
            )

        entry_path = Path(entry)
        if not entry_path.is_absolute():
            # Resolve relative to repo root first, then to the composer dir.
            repo_root = composer_dir.parent
            cand = (repo_root / entry).resolve()
            entry_path = cand if cand.exists() else (composer_dir / entry).resolve()
        entry_path = entry_path.resolve()
        if not entry_path.exists():
            return ToolResult(success=False, error=f"atelier entry not found: {entry_path}")

        # Remotion's bundler resolves `remotion` and friends by walking up from the
        # entry file to find node_modules — so the entry must live under
        # remotion-composer/ at render time. But OpenMontage's project convention is
        # repo-root projects/<slug>/, where artifacts/assets/renders/ already live.
        # Resolution: keep the source of truth under projects/<slug>/ and auto-stage
        # a directory junction (Windows) / symlink (Unix) at
        # remotion-composer/projects/<slug>/ → projects/<slug>/ so the bundler sees
        # the entry inside the composer tree without us copying files. Junctions are
        # weightless, idempotent across renders, and need no admin/dev-mode on Windows.
        try:
            entry_path.relative_to(composer_dir)
            effective_entry = entry_path
        except ValueError:
            try:
                effective_entry = self._stage_atelier_project(entry_path, composer_dir)
            except Exception as e:
                return ToolResult(
                    success=False,
                    error=(
                        f"atelier auto-stage failed for entry {entry_path}: {e}. "
                        f"Either place the entry under {composer_dir}/projects/<slug>/ "
                        f"directly, or fix the staging permission issue."
                    ),
                )

        output_path = Path(inputs.get("output_path", "renders/output.mp4")).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "npx", "remotion", "render", str(effective_entry), str(comp_id), str(output_path),
            # bt709 like every other path in this tool — see _remotion_render.
            "--color-space=bt709",
        ]

        staged_props_path: Path | None = None
        props_path = bespoke.get("props_path")
        if props_path:
            pp = Path(props_path).resolve()
            if not pp.exists():
                return ToolResult(success=False, error=f"atelier props_path not found: {pp}")
            # Atelier props go through the SAME local-asset staging as the
            # templated path — this used to be skipped entirely, so any
            # scenes[].src / backgroundSrc pointing at a real project file
            # reached Remotion as a raw absolute path and was rejected with
            # "Can only download URLs starting with http:// or https://"
            # (Remotion has no file:// support; confirmed live 2026-07-19 —
            # the exact same failure the templated path was already fixed
            # for, just never ported to this second render path).
            with open(pp, encoding="utf-8") as f:
                props = json.load(f)
            # Unlike the templated cuts[] path (anchored via
            # _resolve_manifest_asset_path before it ever reaches staging),
            # atelier props are hand-authored by the agent with no anchoring
            # guarantee at all. Confirmed live 2026-07-19: an agent wrote
            # "projects/<slug>/assets/video/x.mp4" (relative to the repo
            # root) — neither a valid absolute path nor a real public/
            # -relative one, so staging's own contract (leave already
            # "relative" paths untouched) correctly but unhelpfully passed
            # it straight through, and it 404'd downstream. Try the two
            # roots a hand-typed relative path is plausibly meant against
            # before handing off to staging.
            self._anchor_atelier_props(props, project_dir=output_path.parent.parent, repo_root=composer_dir.parent)
            _, staged, missing_assets = self._stage_public_assets(props)
            if missing_assets:
                listed = "\n".join(f"  • {p}" for p in missing_assets)
                return ToolResult(
                    success=False,
                    error=(
                        f"{len(missing_assets)} local asset path(s) referenced by "
                        f"atelier props do not exist on disk:\n{listed}\n\n"
                        f"Check asset_manifest.json for a typo'd or corrupted path."
                    ),
                )
            staged_props_path = output_path.parent / ".remotion_atelier_props.json"
            with open(staged_props_path, "w", encoding="utf-8") as f:
                json.dump(props, f, ensure_ascii=False)
            # Equals form is required for cross-platform path parsing (see _remotion_render).
            cmd.append(f"--props={staged_props_path}")

        public_dir = bespoke.get("public_dir")
        if public_dir:
            pd = Path(public_dir).resolve()
            if pd.exists():
                cmd.append(f"--public-dir={pd}")

        if bespoke.get("scale"):
            cmd.append(f"--scale={bespoke['scale']}")
        if bespoke.get("crf") is not None:
            cmd.append(f"--crf={bespoke['crf']}")
        if bespoke.get("concurrency"):
            cmd.append(f"--concurrency={bespoke['concurrency']}")

        try:
            # Run from inside the composer dir so npx resolves the local
            # remotion binary (mirrors _remotion_render).
            self.run_command(cmd, timeout=1800, cwd=composer_dir)
        except subprocess.CalledProcessError as e:
            # Bare str(e) is just "returned non-zero exit status 1" — the
            # actual Remotion diagnostics live in stderr/stdout. Without
            # this, a real failure (e.g. the file:// asset error above)
            # reaches the agent as an empty signal, and it has to guess at
            # a root cause instead of reading one (observed live
            # 2026-07-19 — the agent guessed "missing node_modules").
            detail = (e.stderr or e.stdout or "").strip()
            tail = "\n".join(detail.splitlines()[-25:]) if detail else "(no output captured)"
            return ToolResult(
                success=False,
                error=f"Atelier (bespoke) Remotion render failed (exit {e.returncode}):\n{tail}",
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Atelier (bespoke) Remotion render failed: {e}")
        finally:
            if staged_props_path is not None and staged_props_path.exists():
                staged_props_path.unlink()

        if not output_path.exists():
            return ToolResult(
                success=False,
                error=f"Atelier render completed but output file missing: {output_path}",
            )

        # AIGC labeling (roadmap 0.1): the atelier entry is hand-authored JSX
        # that can't be trusted to include the badge the templated
        # compositions get via withAigcLabel — burn the explicit label in a
        # post-pass (crf 18, audio copied), then embed the implicit metadata
        # label. Done BEFORE the final review so the review inspects the file
        # that actually ships.
        from tools.video.aigc_label import burn_explicit_label, embed_aigc_metadata
        aigc_burned = burn_explicit_label(output_path, run_command=self.run_command)
        aigc_meta = embed_aigc_metadata(output_path, run_command=self.run_command)

        # --- Atelier post-render review -------------------------------------
        # The cut-schema paths run _run_final_review (technical/visual/audio
        # probes + transcript-vs-script). Atelier MUST do the same so hero
        # renders aren't shipped without the safety net — and additionally
        # enforce the bespoke doctrine: no stock-registry imports, an
        # art-direction declaration must exist. The distinctness review
        # ("could this be any other product's video?") stays human; what we
        # automate here is the *doctrine bypass*, not the taste call.
        final_review = self._run_final_review(
            output_path=output_path,
            edit_decisions=edit_decisions,
            proposal_packet=inputs.get("proposal_packet"),
            narration_transcript_path=inputs.get("narration_transcript_path"),
            script_text=inputs.get("script_text"),
        )

        atelier_checks = self._run_atelier_checks(entry_path, bespoke)
        final_review.setdefault("checks", {})["atelier"] = atelier_checks
        final_review["issues_found"] = list(final_review.get("issues_found", [])) + atelier_checks.get("issues", [])

        # Escalate atelier-critical issues (stock reuse) to the overall status.
        # Missing art-direction is a warning, not a fail — it shows in issues_found.
        if atelier_checks.get("stock_reuse_detected"):
            final_review["status"] = "fail"
            final_review["recommended_action"] = "re_author"

        data: dict[str, Any] = {
            "operation": "render",
            "composition_mode": "atelier",
            "entry": str(entry_path),
            "effective_entry": str(effective_entry) if effective_entry != entry_path else None,
            "composition_id": comp_id,
            "output": str(output_path),
            "final_review": final_review,
            "final_review_status": final_review.get("status"),
            "aigc_label": {
                "explicit_burned": aigc_burned,
                "metadata": aigc_meta,
            },
        }

        if final_review.get("status") == "fail":
            return ToolResult(
                success=False,
                error=(
                    "Atelier render produced an invalid output:\n"
                    + "\n".join(f"  • {i}" for i in final_review.get("issues_found", []))
                ),
                data=data,
                artifacts=[str(output_path)],
            )

        return ToolResult(success=True, data=data, artifacts=[str(output_path)])

    # Source-file extensions that get staged into the composer tree at render time.
    # Anything not in this set lives only under the real project dir (assets, renders,
    # artifacts) and is referenced via --public-dir or absolute paths.
    _ATELIER_STAGE_EXTS = {".tsx", ".ts", ".jsx", ".js", ".css"}

    def _stage_atelier_project(self, entry_path: Path, composer_dir: Path) -> Path:
        """Auto-stage a bespoke project under remotion-composer/projects/<slug>/.

        The source of truth lives under the repo-root `projects/<slug>/` (where
        artifacts/, assets/, renders/ already are). Remotion's webpack bundler,
        however, resolves modules (`remotion`, `@remotion/*`) by walking up from
        the entry's REAL location — so a directory junction/symlink would
        dereference and webpack would fail to find node_modules. We copy the
        source files into a sibling dir inside the composer tree instead.

        mtime-skip semantics make repeat renders cheap (typical project is a
        handful of small .tsx files). Non-source files (assets, renders, props
        JSON) stay only in the real project dir and are referenced via
        --public-dir or absolute paths in props.

        Resolves the slug as the first path segment under a `projects/` ancestor;
        falls back to the entry's parent directory name. Returns the staged entry
        path.
        """
        import shutil

        real_project_dir = entry_path.parent.resolve()

        # Derive a stable slug. Prefer the first segment under a `projects/` ancestor.
        slug = real_project_dir.name
        try:
            parts = real_project_dir.parts
            if "projects" in parts:
                i = parts.index("projects")
                if i + 1 < len(parts):
                    slug = parts[i + 1]
        except Exception:
            pass

        staging_root = composer_dir / "projects"
        staging_root.mkdir(parents=True, exist_ok=True)
        staging_dir = staging_root / slug

        # If a stale junction/symlink is in the way from an earlier (failed) attempt,
        # remove it before creating a real staging directory.
        if staging_dir.is_symlink() or (staging_dir.exists() and staging_dir.is_dir()
                                        and staging_dir.resolve() != staging_dir):
            try:
                staging_dir.unlink()
            except (OSError, PermissionError):
                # Some Windows junctions need rmdir
                import subprocess as _sp
                _sp.run(["cmd", "/c", "rmdir", str(staging_dir)], check=True)

        staging_dir.mkdir(parents=True, exist_ok=True)

        # mtime-skip copy of source files only. Mirrors directory structure so
        # relative imports work identically.
        for src in real_project_dir.rglob("*"):
            if not src.is_file():
                continue
            if src.suffix.lower() not in self._ATELIER_STAGE_EXTS:
                continue
            rel = src.relative_to(real_project_dir)
            dst = staging_dir / rel
            try:
                if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                    continue
            except OSError:
                pass
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        return staging_dir / entry_path.name

    # Stock-registry import patterns that violate the atelier doctrine.
    # Any of these inside a bespoke project tree means a creative component
    # was reused instead of hand-stitched. Engine knowledge (the `remotion`
    # package, `@remotion/*`, project-local files) is fine.
    _ATELIER_STOCK_IMPORT_RE = (
        r"""from\s+["']("""
        # parent-traversed paths into the stock src/
        r"""(?:\.\./)+src/(?:components|Explainer|CinematicRenderer|"""
        r"""TitledVideo|TalkingHead|CollageBurst|LyricOverlay|cinematic|crucix|phantom)"""
        # or absolute-ish paths into the same
        r"""|remotion-composer/src/(?:components|Explainer|CinematicRenderer|"""
        r"""TitledVideo|TalkingHead|CollageBurst|LyricOverlay|cinematic|crucix|phantom)"""
        r""")"""
    )

    def _run_atelier_checks(self, entry_path: Path, bespoke: dict[str, Any]) -> dict[str, Any]:
        """Doctrine-enforcement checks specific to atelier mode.

        Returns a dict with two checks:
          - stock_reuse_detected (bool) + offending_imports (list) — CRITICAL,
            fails the render. Catches `import X from "../../src/components/..."`
            and similar reuse of stock creative components.
          - art_direction_declared (bool) + art_direction (str|None) — WARNING.
            Forces step 1 of the bespoke-composition skill (commit to a fresh
            art direction per video) to be written down rather than skipped.
        """
        import re as _re

        issues: list[str] = []
        offending: list[dict[str, str]] = []
        project_dir = entry_path.parent
        pat = _re.compile(self._ATELIER_STOCK_IMPORT_RE)

        try:
            for f in project_dir.rglob("*"):
                if not f.is_file() or f.suffix.lower() not in {".tsx", ".ts", ".jsx", ".js"}:
                    continue
                try:
                    txt = f.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for m in pat.finditer(txt):
                    offending.append({"file": str(f.relative_to(project_dir)), "import": m.group(1)})
        except Exception as e:  # pragma: no cover — never let the check itself break a render
            issues.append(f"atelier stock-reuse scan errored: {e}")

        stock_reuse_detected = bool(offending)
        if stock_reuse_detected:
            issues.append(
                "atelier doctrine violation: bespoke project imports from the stock "
                "creative registry. Hand-author the scene instead — the registry is "
                "a mechanics codex, not a parts bin. Offending imports: "
                + ", ".join(f"{o['file']} → {o['import']}" for o in offending[:5])
                + ("…" if len(offending) > 5 else "")
            )

        art_direction = bespoke.get("art_direction") or bespoke.get("art_direction_note")
        art_direction_declared = bool(art_direction and str(art_direction).strip())
        if not art_direction_declared:
            issues.append(
                "atelier warning: no bespoke.art_direction declared. Per "
                "skills/meta/bespoke-composition.md step 1, every atelier piece must "
                "commit to a fresh art direction (palette, type, motion, signature "
                "device) before authoring. Pass edit_decisions.bespoke.art_direction "
                "as a short note or a path to art-direction.md."
            )

        return {
            "stock_reuse_detected": stock_reuse_detected,
            "offending_imports": offending,
            "art_direction_declared": art_direction_declared,
            "art_direction": str(art_direction) if art_direction else None,
            "issues": issues,
        }

    @staticmethod
    def _is_light_hex(color: str) -> bool:
        """See compose_theme._is_light_hex."""
        from tools.video.compose_theme import _is_light_hex
        return _is_light_hex(color)

    @staticmethod
    def _pick_caption_highlight(candidates: list[str], scrim_hex: str, light_bg: bool) -> str:
        """See compose_theme._pick_caption_highlight."""
        from tools.video.compose_theme import _pick_caption_highlight
        return _pick_caption_highlight(candidates, scrim_hex, light_bg)

    @staticmethod
    def _build_theme_from_playbook(
        playbook_name: str | None,
        composition_data: dict | None,
    ) -> dict[str, Any] | None:
        """See compose_theme._build_theme_from_playbook."""
        from tools.video.compose_theme import _build_theme_from_playbook
        return _build_theme_from_playbook(playbook_name, composition_data)

    def _needs_remotion(self, cuts: list[dict]) -> bool:
        """Determine whether Remotion should handle this composition.

        Remotion is the DEFAULT composition engine when available.  It handles
        video clips (via <OffthreadVideo>), still images, animated scene types,
        component types, transitions, and mixed content — all in a single
        React-based render pass.

        Returns False (i.e. use FFmpeg) only when Remotion is not
        available. For `operation="render"` the governance default is
        Remotion-first: the renderer family was chosen earlier, and the
        tool should preserve that decision instead of silently
        downgrading to FFmpeg.

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
                render_runtime = edit_decisions.get("render_runtime")
                risk = score_slideshow_risk(
                    scenes, edit_decisions, renderer_family, render_runtime
                )
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

        # --- 4. Timeline integrity + pacing (Wave 2, item 13) ---
        # Manifests promise "no gaps or overlaps" and playbooks declare
        # pacing_rules; neither had any enforcement. Inverted cuts and
        # same-layer overlaps BLOCK (they corrupt the ffmpeg path); gaps and
        # pacing misses warn.
        try:
            from lib.edit_timeline import validate_edit_timeline
            playbook = None
            playbook_name = edit_decisions.get("metadata", {}).get("style_playbook")
            if playbook_name:
                try:
                    from styles.playbook_loader import load_playbook
                    playbook = load_playbook(playbook_name)
                except Exception:
                    playbook = None
            timeline = validate_edit_timeline(edit_decisions, playbook)
            blocks.extend(timeline["issues"])
            warnings.extend(timeline["warnings"])
        except Exception as e:
            log.warning("Could not validate edit timeline: %s", e)

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

    @staticmethod
    def _resolve_manifest_asset_path(raw: str, output_path: Path) -> str:
        """Turn an asset_manifest path (e.g. "assets/video/sc-01.mp4",
        intentionally project-relative — the /media/<project>/<rel> URL
        convention depends on it) into an absolute one anchored at the job's
        project_dir, derived from output_path.

        Confirmed live: without this, a project-relative manifest path reached
        _stage_public_assets still relative. That function's contract (pinned
        by test_public_relative_paths_untouched) is to leave already-staged
        public-relative paths untouched — a reasonable rule for its own output,
        but a manifest path was never staged, so being left alone means it's
        handed to Remotion as-is. staticFile() then 404s on it silently, and
        the render "succeeds" with only the background composited — no clips,
        images, or overlays. output_path is reliably <project_dir>/renders/
        <file> (tool_bridge anchors it there — see _anchor_output_path), so
        project_dir is its grandparent; anything already absolute, or an
        unrecognized output_path shape, passes through untouched.
        """
        if not raw:
            return raw
        p = Path(raw)
        if p.is_absolute():
            candidate = p
        elif output_path.parent.name != "renders":
            return raw
        else:
            candidate = (output_path.parent.parent / p).resolve()

        if candidate.exists():
            return str(candidate)
        recovered = VideoCompose._recover_redacted_filename(candidate)
        return str(recovered) if recovered is not None else str(candidate)

    @staticmethod
    def _recover_redacted_filename(candidate: Path) -> Path | None:
        """Best-effort recovery for a manifest filename mangled by an
        upstream LLM-provider content filter.

        Observed live 2026-07-19: an agent's own completion redacted a
        digit run inside a hex asset hash mid-conversation (not a one-time
        file corruption — re-reading the correct file from disk and having
        the agent re-type/echo it reproduced the SAME redaction on a later
        turn), e.g. "maas_video_ltx-2-3_de2cd78360806541.mp4" ->
        "...de2cd[PHONE_REDACTED]1.mp4". Fixing the artifact on disk alone
        cannot prevent this — it can recur any time the agent re-echoes the
        digit run. Recover by wildcard-matching the bracketed placeholder:
        if the candidate's parent directory has exactly one file whose name
        starts with the text before "[" and ends with the text after "]"
        (same extension), that's almost certainly the real file.
        """
        name = candidate.name
        if "[" not in name or "]" not in name:
            return None
        prefix, _, rest = name.partition("[")
        _, _, suffix = rest.partition("]")
        if not candidate.parent.is_dir():
            return None
        matches = [
            f for f in candidate.parent.iterdir()
            if f.is_file() and f.name.startswith(prefix) and f.name.endswith(suffix)
        ]
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _anchor_atelier_props(props: dict[str, Any], project_dir: Path, repo_root: Path) -> None:
        """Rewrite hand-typed relative asset paths in atelier `scenes[]`
        in place, anchoring them against whichever of `project_dir` /
        `repo_root` actually contains the file — mirrors what
        `_resolve_manifest_asset_path` already does for the templated
        `cuts[]` path, which atelier props never got (they're hand-authored
        by the agent with no anchoring guarantee at all).

        Leaves alone: absolute paths, http(s)/data URLs, and anything
        already staged (`om-staged/...`) — only a bare relative path that
        doesn't exist as given gets a resolution attempt.
        """
        def anchor(value: Any) -> Any:
            if not isinstance(value, str) or not value:
                return value
            if value.startswith(("http://", "https://", "data:", "om-staged/")):
                return value
            p = Path(value)
            if p.is_absolute() or p.exists():
                return value
            for root in (project_dir, repo_root):
                candidate = (root / p).resolve()
                if candidate.exists():
                    return str(candidate)
                recovered = VideoCompose._recover_redacted_filename(candidate)
                if recovered is not None:
                    return str(recovered)
            return value

        for scene in props.get("scenes", []) or []:
            if not isinstance(scene, dict):
                continue
            for key in ("src", "backgroundSrc"):
                if key in scene:
                    scene[key] = anchor(scene[key])
        for track_key in ("music", "soundtrack"):
            track = props.get(track_key)
            if isinstance(track, dict) and "src" in track:
                track["src"] = anchor(track["src"])

    @classmethod
    def _resolve_audio_music(
        cls,
        edit_decisions: dict[str, Any],
        asset_lookup: dict[str, dict[str, Any]],
        output_path: Path,
    ) -> dict[str, Any]:
        """Resolve edit_decisions.audio.music.asset_id to a real `src` path,
        the same way cuts/overlays already are via _resolve_manifest_asset_path.

        edit_decisions.schema.json's audio.music ALWAYS references its asset
        via asset_id (never a raw path) — but nothing converted that to the
        `src` field Explainer.tsx's AudioConfig.music and _stage_public_assets
        both require, so a templated render's music track was silently never
        staged: Remotion got neither an asset_id it understands nor a src it
        could serve. Confirmed live: the compose agent tried ~20 tool calls
        across audio_enhance/audio_mixer/video_stitch chasing "Remotion can't
        find the music asset" — asset_id was never resolved to begin with, no
        matter what path format or volume setting was retried.

        Returns edit_decisions unchanged if there's nothing to resolve (no
        audio.music, or its asset_id isn't in the manifest — logged, not
        raised, matching the overlay resolver's same-shaped gap).

        narration.segments[] is deliberately NOT resolved here: Explainer's
        AudioConfig models narration as ONE track (audio.narration.src), not
        multiple independently-timed segments, so bridging segments[] would
        silently drop every segment but one — a real design gap, not a
        simple asset_id lookup like music.
        """
        audio = edit_decisions.get("audio")
        if not isinstance(audio, dict) or not isinstance(audio.get("music"), dict):
            return edit_decisions
        music = audio["music"]
        asset_id = music.get("asset_id")
        asset = asset_lookup.get(asset_id) if asset_id else None
        if asset is None:
            if asset_id:
                logging.getLogger("video_compose").warning(
                    "audio.music.asset_id %r is not in the asset_manifest — "
                    "the music track will not render.", asset_id,
                )
            return edit_decisions
        resolved_music = dict(music)
        resolved_music["src"] = cls._resolve_manifest_asset_path(asset["path"], output_path)
        return {**edit_decisions, "audio": {**audio, "music": resolved_music}}

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

        # --- Runtime routing: honor render_runtime locked at proposal ---
        # Silent swaps are forbidden by governance. Resolve this before any
        # composition-mode branching so `composition_mode="atelier"` cannot
        # accidentally force the Remotion atelier path when HyperFrames or
        # FFmpeg was approved.
        render_runtime = (edit_decisions.get("render_runtime") or "").strip().lower()

        if not render_runtime:
            return ToolResult(
                success=False,
                error=(
                    "render_runtime is not set in edit_decisions. Per governance, "
                    "it MUST be locked at proposal stage (proposal_packet."
                    "production_plan.render_runtime) and carried forward through "
                    "edit_decisions.render_runtime. Valid values: 'remotion', "
                    "'hyperframes', 'ffmpeg'. Re-run the proposal stage with an "
                    "explicit runtime choice — do NOT default this field."
                ),
            )

        if render_runtime not in {"remotion", "hyperframes", "ffmpeg"}:
            return ToolResult(
                success=False,
                error=(
                    f"Unknown render_runtime {render_runtime!r}. "
                    f"Valid values: remotion, hyperframes, ffmpeg. "
                    f"render_runtime must be set at proposal stage."
                ),
            )

        # --- Atelier (bespoke) mode -------------------------------------
        # Hand-authored, project-local Remotion composition. Deliberately
        # bypasses the cut-schema, the stock scene-type registry, and the
        # RENDERER_FAMILY_MAP. This is the "hand-stitched every time" path:
        # the agent writes a fresh composition (its own scenes, theme, motion)
        # under remotion-composer/projects/<slug>/ and points this renderer at
        # it. No reusable creative components; a new visual language per video.
        # Triggered by composition_mode="atelier" (or renderer_family="bespoke").
        remotion_atelier_requested = (
            edit_decisions.get("composition_mode") == "atelier"
            or edit_decisions.get("renderer_family") == "bespoke"
        )
        if render_runtime == "remotion" and remotion_atelier_requested:
            return self._render_via_atelier(inputs, edit_decisions)

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
                resolved_cut["source"] = self._resolve_manifest_asset_path(
                    asset_lookup[source_id]["path"], output_path,
                )
            resolved_cuts.append(resolved_cut)

        # Same for ASSET overlays. Cuts got this treatment from day one but
        # overlays never did, so an asset overlay reached the renderer with an
        # unresolved asset_id and simply didn't appear (audit 2026-07-16, B4).
        # `source` is what both renderers read; component overlays (keyed by
        # `type`) pass through untouched.
        resolved_overlays = []
        for overlay in edit_decisions.get("overlays") or []:
            resolved_overlay = dict(overlay)
            asset_id = overlay.get("asset_id")
            if asset_id:
                asset = asset_lookup.get(asset_id)
                if asset is None and ":" in asset_id:
                    # Real artifacts namespace these ("asset_manifest:hero_card").
                    asset = asset_lookup.get(asset_id.split(":", 1)[1])
                if asset is not None:
                    resolved_overlay["source"] = self._resolve_manifest_asset_path(
                        asset["path"], output_path,
                    )
                elif not overlay.get("source"):
                    logging.getLogger("video_compose").warning(
                        "Overlay asset_id %r is not in the asset_manifest — "
                        "this overlay will not render.", asset_id,
                    )
            resolved_overlays.append(resolved_overlay)
        if resolved_overlays:
            edit_decisions = {**edit_decisions, "overlays": resolved_overlays}

        # Resolve audio.music.asset_id to a real `src` path — see
        # _resolve_audio_music's docstring for why this was needed.
        edit_decisions = self._resolve_audio_music(edit_decisions, asset_lookup, output_path)

        # --- Pre-compose validation gate ---
        scene_plan = inputs.get("scene_plan")
        validation_block = self._pre_compose_validation(edit_decisions, resolved_cuts, scene_plan)
        if validation_block is not None:
            return validation_block

        # Also accept profile as "output_profile" (skill convention) or "profile"
        profile = inputs.get("profile") or inputs.get("output_profile")

        if render_runtime == "hyperframes":
            return self._render_via_hyperframes(
                inputs=inputs,
                edit_decisions=edit_decisions,
                asset_manifest=asset_manifest,
                resolved_cuts=resolved_cuts,
                output_path=output_path,
                profile=profile,
            )
        if render_runtime == "ffmpeg":
            # Caller explicitly asked for FFmpeg — don't auto-upgrade to Remotion.
            return self._render_via_ffmpeg(
                inputs=inputs,
                edit_decisions=edit_decisions,
                resolved_cuts=resolved_cuts,
                output_path=output_path,
                profile=profile,
            )
        # --- Explicit Remotion path (render_runtime == 'remotion') ---
        if self._needs_remotion(resolved_cuts):
            remotion_inputs: dict[str, Any] = {
                "edit_decisions": dict(edit_decisions, cuts=resolved_cuts),
                "output_path": str(output_path),
            }
            if profile:
                remotion_inputs["profile"] = profile
            # Forward the creator-facing render timeout through the high-level
            # render path (execute(operation="render") -> _render), otherwise it
            # would only take effect on a direct _remotion_render() call.
            if inputs.get("remotion_timeout_ms") is not None:
                remotion_inputs["remotion_timeout_ms"] = inputs["remotion_timeout_ms"]
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
        return self._review_and_gate(render_result, output_path, edit_decisions, inputs)

    def _review_and_gate(
        self,
        render_result: ToolResult,
        output_path: Path,
        edit_decisions: dict[str, Any],
        inputs: dict[str, Any],
    ) -> ToolResult:
        """Run the mandatory final self-review and gate the ToolResult on it.

        Shared by _render (all engine paths) and the direct `compose`
        operation — the latter is tool_bridge's default and produces the
        official final.mp4, yet previously shipped with ZERO review.
        """
        if not (render_result.success and output_path.exists()):
            return render_result

        final_review = self._run_final_review(
            output_path,
            edit_decisions,
            inputs.get("proposal_packet"),
            narration_transcript_path=inputs.get("narration_transcript_path"),
            script_text=inputs.get("script_text") or self._read_text_file(
                inputs.get("script_path")
            ),
        )

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

    def _render_via_hyperframes(
        self,
        *,
        inputs: dict[str, Any],
        edit_decisions: dict[str, Any],
        asset_manifest: dict[str, Any],
        resolved_cuts: list[dict],
        output_path: Path,
        profile: Optional[str],
    ) -> ToolResult:
        """Delegate to hyperframes_compose and run the mandatory final self-review.

        Governance: if HyperFrames is unavailable or fails, return a structured
        blocker — do NOT silently route to Remotion or FFmpeg. The agent must
        surface the blocker and get user approval before any runtime swap.
        """
        if not self._hyperframes_available():
            return ToolResult(
                success=False,
                error=(
                    "render_runtime='hyperframes' was locked at proposal, but "
                    "the HyperFrames runtime is not available on this machine. "
                    "Per governance this is a BLOCKER — surface it to the user "
                    "per AGENT_GUIDE.md > 'Escalate Blockers Explicitly' and wait "
                    "for approval before switching runtime. Requirements: "
                    "Node.js >= 22, FFmpeg, and npx on PATH. See "
                    "tools/video/hyperframes_compose.py for the specific missing piece."
                ),
            )

        try:
            from tools.video.hyperframes_compose import HyperFramesCompose
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Could not import hyperframes_compose: {e}",
            )

        workspace_path = (
            inputs.get("workspace_path")
            or str(output_path.parent.parent / "hyperframes")
        )

        # Pass the playbook through so the style bridge can emit CSS vars.
        playbook_data = inputs.get("playbook")
        if not playbook_data:
            playbook_name = (
                inputs.get("playbook_name")
                or (edit_decisions.get("metadata") or {}).get("playbook")
            )
            if playbook_name:
                try:
                    from styles.playbook_loader import load_playbook  # type: ignore
                    playbook_data = load_playbook(playbook_name)
                except Exception:
                    playbook_data = None

        hf_inputs: dict[str, Any] = {
            "operation": "render",
            "workspace_path": workspace_path,
            "output_path": str(output_path),
            "edit_decisions": dict(edit_decisions, cuts=resolved_cuts),
            "asset_manifest": asset_manifest,
        }
        if playbook_data:
            hf_inputs["playbook"] = playbook_data
        if profile:
            hf_inputs["profile"] = profile
        if "quality" in inputs:
            hf_inputs["quality"] = inputs["quality"]
        if "fps" in inputs:
            hf_inputs["fps"] = inputs["fps"]
        if "strict" in inputs:
            hf_inputs["strict"] = inputs["strict"]
        if "best_effort" in inputs:
            hf_inputs["best_effort"] = inputs["best_effort"]
        if "skip_contrast" in inputs:
            hf_inputs["skip_contrast"] = inputs["skip_contrast"]

        render_result = HyperFramesCompose().execute(hf_inputs)

        if not render_result.success:
            return ToolResult(
                success=False,
                error=(
                    f"HyperFrames render failed: {render_result.error}. "
                    "Per governance: do NOT silently fall back to Remotion or "
                    "FFmpeg. Surface the failure to the user along with the "
                    "hyperframes_compose step log before proposing a swap."
                ),
                data=render_result.data,
            )

        # Post-render: mandatory final self-review (identical contract to the Remotion path).
        if output_path.exists():
            final_review = self._run_final_review(
                output_path,
                edit_decisions,
                inputs.get("proposal_packet"),
                narration_transcript_path=inputs.get("narration_transcript_path"),
                script_text=inputs.get("script_text") or self._read_text_file(
                    inputs.get("script_path")
                ),
            )
            if render_result.data is None:
                render_result.data = {}
            render_result.data["final_review"] = final_review
            render_result.data["final_review_status"] = final_review["status"]
            if final_review["status"] == "fail":
                return ToolResult(
                    success=False,
                    error=(
                        "Post-render self-review FAILED (HyperFrames). The output is not presentable.\n"
                        + "\n".join(f"  • {i}" for i in final_review.get("issues_found", []))
                    ),
                    data=render_result.data,
                )

        return render_result

    def _render_via_ffmpeg(
        self,
        *,
        inputs: dict[str, Any],
        edit_decisions: dict[str, Any],
        resolved_cuts: list[dict],
        output_path: Path,
        profile: Optional[str],
    ) -> ToolResult:
        """Explicit FFmpeg-only render path.

        Use when the proposal locked `render_runtime="ffmpeg"` — e.g. simple
        source-footage concat/trim jobs that don't benefit from composition.
        Still runs the mandatory final self-review.
        """
        options = inputs.get("options", {})
        subtitle_burn = options.get("subtitle_burn", True)

        subtitle_path = inputs.get("subtitle_path")
        if subtitle_burn and not subtitle_path:
            ed_subs = edit_decisions.get("subtitles", {})
            if ed_subs.get("enabled") and ed_subs.get("source"):
                subtitle_path = ed_subs["source"]

        compose_inputs = dict(inputs)
        compose_inputs["edit_decisions"] = dict(edit_decisions, cuts=resolved_cuts)
        compose_inputs["output_path"] = str(output_path)
        if subtitle_path:
            compose_inputs["subtitle_path"] = subtitle_path
        if profile:
            compose_inputs["profile"] = profile

        render_result = self._compose(compose_inputs)

        if render_result.success and output_path.exists():
            final_review = self._run_final_review(
                output_path,
                edit_decisions,
                inputs.get("proposal_packet"),
                narration_transcript_path=inputs.get("narration_transcript_path"),
                script_text=inputs.get("script_text") or self._read_text_file(
                    inputs.get("script_path")
                ),
            )
            if render_result.data is None:
                render_result.data = {}
            render_result.data["final_review"] = final_review
            render_result.data["final_review_status"] = final_review["status"]
            if final_review["status"] == "fail":
                return ToolResult(
                    success=False,
                    error=(
                        "Post-render self-review FAILED (FFmpeg). The output is not presentable.\n"
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

        composition_data = inputs.get("edit_decisions") or inputs.get("composition_data")
        if not composition_data:
            return ToolResult(
                success=False,
                error="edit_decisions or composition_data required for remotion_render",
            )

        # Route to the correct Remotion composition based on renderer_family.
        # This prevents all pipelines from collapsing into the Explainer visual grammar.
        renderer_family = (composition_data or {}).get("renderer_family", "explainer-data")
        composition_id = self._get_composition_id(renderer_family)

        # Fail loudly instead of silently rendering background-only output.
        # Confirmed live (a full paid end-to-end run): this function passes
        # edit_decisions through as props VERBATIM — there is no
        # per-composition transform. Each composition reads its clip list
        # from a different top-level field (Explainer: cuts[], CinematicRenderer:
        # scenes[], TalkingHead: videoSrc) — see each .tsx's Props interface.
        # The generic (non-atelier) edit_decisions.schema.json ONLY ever
        # populates cuts[]; no edit-director skill writes scenes[] or
        # videoSrc. So routing a templated (non-atelier) render to
        # CinematicRenderer or TalkingHead silently produces a render with
        # only the background/theme layer and AIGC label — no clips, images,
        # or audio — while reporting success. The 30s render this surfaced
        # was billed real money for real clips that never got composited.
        # Until a real cuts/overlays -> scenes/videoSrc transform exists,
        # these renderer_families are atelier-only (hand-authored props in
        # the composition's real shape) — the code comment a few lines below
        # already documents this ("the templated cut path was dead on
        # arrival"); this makes it a hard stop instead of a silent one.
        # Checked before the npx/Node dependency check below — a malformed
        # request should fail on its own merits, not on environment setup.
        # Presence, not truthiness: an empty `cuts: []` is a legitimate (if
        # useless) Explainer render, not a shape mismatch — only an ABSENT
        # field means this composition_data was never meant for this
        # composition at all.
        required_field = self._COMPOSITION_REQUIRED_FIELD.get(composition_id)
        if required_field and required_field not in composition_data:
            explainer_families = sorted(
                fam for fam, comp in self.RENDERER_FAMILY_MAP.items() if comp == "Explainer"
            )
            return ToolResult(
                success=False,
                error=(
                    f"renderer_family={renderer_family!r} routes to Remotion composition "
                    f"{composition_id!r}, which reads its scene/clip list from "
                    f"`{required_field}` — edit_decisions has none (only the generic "
                    f"`cuts[]`, which {composition_id} does not read). The templated "
                    f"(non-atelier) edit_decisions schema can only ever populate "
                    f"`cuts[]`, so this renderer_family is not reachable via the "
                    f"templated path yet. Options: (1) use atelier mode — "
                    f"composition_mode='atelier' with edit_decisions.bespoke pointing "
                    f"at a hand-authored entry that sets `{required_field}` directly "
                    f"in {composition_id}'s real prop shape — or (2) pick an "
                    f"Explainer-routed renderer_family instead: {explainer_families}."
                ),
            )

        if not shutil.which("npx"):
            return ToolResult(
                success=False,
                error="npx not found. Install Node.js to use Remotion rendering.",
            )

        output_path = Path(inputs.get("output_path", "renders/remotion_output.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Absolutise so the CLI can resolve the output regardless of cwd.
        output_path = output_path.resolve()

        # Deep-copy props so we don't mutate the original
        props = json.loads(json.dumps(composition_data))

        # Stage every local asset into a public dir and rewrite props to
        # public-relative paths (resolved by staticFile() in the composer).
        #
        # This replaces a file:// URI conversion that NEVER WORKED — verified
        # empirically 2026-07-17 by rendering real project assets:
        #   <Img>            → Chrome: "Not allowed to load local resource"
        #   <OffthreadVideo> → its /proxy endpoint calls @remotion/renderer's
        #                      readFile(), which throws "Can only download URLs
        #                      starting with http:// or https://"
        # Neither 3- nor 4-slash form helps: Remotion has no file:// support at
        # all. Local assets MUST be served over http from the public dir, which
        # is exactly what the one working Remotion project (小兔子电视) did by
        # hand — its scenes[].src are public-relative paths, while the
        # absolute-path cuts[] this function rewrote went unused. The templated
        # cut path was dead on arrival for every local asset.
        public_dir, staged, missing_assets = self._stage_public_assets(props)
        if staged:
            logging.getLogger("video_compose").info(
                "Staged %d asset(s) into public dir %s", staged, public_dir
            )
        if missing_assets:
            # Fail before ever invoking npx — a missing path here can only
            # ever surface downstream as an opaque Remotion "file:// not
            # supported" proxy error, which hides the real cause (asset
            # never generated, a stale/typo'd manifest path, or — observed
            # live 2026-07-19 — an LLM-provider PII filter mangling a hex
            # asset hash that happens to contain a phone-number-length digit
            # run, e.g. "de2cd78360806541" -> "de2cd[PHONE_REDACTED]1").
            listed = "\n".join(f"  • {p}" for p in missing_assets)
            return ToolResult(
                success=False,
                error=(
                    f"{len(missing_assets)} local asset path(s) referenced by "
                    f"edit_decisions do not exist on disk:\n{listed}\n\n"
                    f"Check asset_manifest.json for a typo'd or corrupted "
                    f"path (a digit run that looks like a phone number can "
                    f"get silently mangled in transit), or a source_tool "
                    f"that never actually ran. If any of these are meant to "
                    f"be native Remotion title/text cards rather than media "
                    f"files, use cut.type='hero_title' or 'text_card' with "
                    f"cut.text instead of a fabricated asset + cut.source."
                ),
            )

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

        # Explicit AIGC label (roadmap 0.1, 《标识办法》): every registered
        # composition is wrapped in withAigcLabel (remotion-composer/src/
        # Root.tsx), which renders the opening-frame badge whenever this prop
        # is present. Injected here — not left to the agent's edit_decisions —
        # so it's on by default for every templated Remotion render; only the
        # config-level opt-out (aigc_label.enabled=false, loud) removes it.
        from tools.video.aigc_label import (
            EXPLICIT_LABEL_SECONDS, EXPLICIT_LABEL_TEXT, labeling_enabled,
        )
        if labeling_enabled() and "aigcLabel" not in props:
            props["aigcLabel"] = {
                "text": EXPLICIT_LABEL_TEXT,
                "seconds": EXPLICIT_LABEL_SECONDS,
            }

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

        cmd = [
            "npx", "remotion", "render",
            str(composer_dir / "src" / "index.tsx"),
            composition_id,
            str(output_path),
            # Use the `--props=<path>` equals form rather than two separate
            # args. On Windows, passing `--props` and the path separately makes
            # Remotion mis-parse the value (quote escaping differs), failing
            # with "neither valid JSON nor a file path". The equals form is the
            # API Remotion recommends for file paths and is cross-platform safe.
            f"--props={props_path}",
            # Remotion v4 defaults to bt601 ("default"), so its deliverable was
            # tagged bt470bg while EVERY ffmpeg path in this tool tags bt709 —
            # the same mixed-metadata inconsistency the encode-finishing pass
            # fixed on the ffmpeg side (verified by ffprobe on a real render).
            # Since 4.0.83 this performs a real conversion, not just tagging.
            "--color-space=bt709",
        ]

        # Apply media profile dimensions
        profile_name = inputs.get("profile")
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                p = get_profile(profile_name)
                cmd.extend(["--width", str(p.width), "--height", str(p.height)])
            except ImportError:
                pass  # lib unavailable — proceed with defaults
            except ValueError as e:
                # A typo'd profile name must NOT silently render the default
                # aspect ratio: asking for a 9:16 delivery and getting 16:9 is
                # an invisible, catastrophic substitution (found by E2E render
                # inspection, 2026-07-17 — 'douyin_vertical' silently produced
                # 1920x1080). get_profile's error already lists valid names.
                return ToolResult(success=False, error=str(e))

        # Optional creator-facing render timeout. Remotion's `--timeout` (ms)
        # governs headless-browser setup and delayRender(); on slow machines or
        # restricted networks the default 30s browser setup times out with an
        # opaque failure. Pass it through and give the subprocess enough headroom
        # so run_command() does not kill Remotion before its own timeout fires.
        remotion_timeout_ms = inputs.get("remotion_timeout_ms")
        subprocess_timeout = 600
        if remotion_timeout_ms:
            try:
                ms = int(remotion_timeout_ms)
                cmd.append(f"--timeout={ms}")
                subprocess_timeout = max(subprocess_timeout, ms // 1000 + 60)
            except (TypeError, ValueError):
                pass

        try:
            # Invoke from inside the composer dir so npx can resolve the
            # local remotion binary via node_modules/.bin. Without this,
            # Windows npx cannot locate the CLI and returns "could not
            # determine executable to run".
            self.run_command(cmd, timeout=subprocess_timeout, cwd=composer_dir)
        except subprocess.CalledProcessError as e:
            # run_command uses check=True + capture_output, so the useful
            # Remotion diagnostics live in stderr/stdout — surface the tail
            # instead of the bare "returned non-zero exit status 1".
            detail = (e.stderr or e.stdout or "").strip()
            tail = "\n".join(detail.splitlines()[-25:]) if detail else "(no output captured)"
            return ToolResult(
                success=False,
                error=f"Remotion render failed (exit {e.returncode}):\n{tail}",
            )
        except subprocess.TimeoutExpired as e:
            return ToolResult(
                success=False,
                error=(
                    f"Remotion render timed out after {e.timeout}s. If the headless "
                    "browser is slow to start, raise remotion_timeout_ms (ms)."
                ),
            )
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

        loudness_normalized = self._normalize_deliverable_loudness(output_path)

        # Implicit AIGC label — mandatory metadata step on every render path.
        from tools.video.aigc_label import embed_aigc_metadata
        aigc_meta = embed_aigc_metadata(output_path, run_command=self.run_command)

        return ToolResult(
            success=True,
            data={
                "operation": "remotion_render",
                "output": str(output_path),
                "profile": profile_name,
                "loudness_normalized": loudness_normalized,
                "loudness_target_lufs": -14 if loudness_normalized else None,
                "aigc_label": {
                    "explicit_burned": "aigcLabel" in props,
                    "metadata": aigc_meta,
                },
            },
            artifacts=[str(output_path)],
        )

    # ------------------------------------------------------------------
    # Final self-review — mandatory post-render inspection
    # ------------------------------------------------------------------

    # Punctuation/SSML-leak words that should NEVER appear in rendered audio.
    # When a TTS engine reads a literal "..." as the word "dot", or a "—" as
    # "hyphen", those leak into the transcript. Catching these in the final
    # review is the difference between catching a bad voice render in-tool
    # vs. shipping a video that says "dot dot dot" twelve times. CRITICAL.

    @staticmethod
    def _read_text_file(path: str | Path | None) -> str | None:
        """See compose_review._read_text_file."""
        from tools.video.compose_review import _read_text_file
        return _read_text_file(path)


    @staticmethod
    def _compare_transcript_to_script(transcript_path, script_text):
        """See compose_review._compare_transcript_to_script."""
        from tools.video.compose_review import _compare_transcript_to_script
        return _compare_transcript_to_script(transcript_path, script_text)

    def _run_final_review(
        self,
        output_path: Path,
        edit_decisions: dict[str, Any] | None = None,
        proposal_packet: dict[str, Any] | None = None,
        narration_transcript_path: str | Path | None = None,
        script_text: str | None = None,
    ) -> dict[str, Any]:
        """See compose_review._run_final_review — kept as a method so every
        existing call site and subclass override point is unchanged."""
        from tools.video.compose_review import _run_final_review
        return _run_final_review(
            output_path, edit_decisions, proposal_packet,
            narration_transcript_path, script_text,
        )

    # Prop paths that reference a local media asset, as (container, key)
    # traversal rules. Kept explicit rather than "rewrite any string that
    # looks like a path" so a caption word or a title can never be mangled.
    _ASSET_CUT_KEYS = ("source", "backgroundImage", "backgroundVideo", "backgroundSrc")

    def _stage_public_assets(self, props: dict[str, Any]) -> tuple[Path, int, list[str]]:
        """Symlink every local asset into a per-render public dir, rewriting
        props in place to public-relative paths.

        Returns (public_dir, staged_count, missing_paths). Remotion serves the
        public dir over http, and staticFile(relative) — which resolveAsset
        already produces for relative inputs — resolves against it.
        missing_paths lists every absolute local path that was referenced but
        does not exist on disk — the caller should fail loud on these rather
        than let them reach Remotion, where they can only ever surface as an
        opaque "file:// not supported" proxy error several layers removed
        from the real cause.

        HARD links, not symlinks: Remotion bundles by COPYING public/ into a
        webpack temp dir, and that copy does not follow symlinks (verified —
        the staged names 404'd from inside the bundle). A hard link is
        indistinguishable from a regular file to any copy routine and still
        costs no space; projects/ and remotion-composer/ live on one
        filesystem. Falls back to symlink, then copy, for the cross-device and
        Windows-without-dev-mode cases.

        Names are content-addressed by absolute path hash to avoid collisions
        between same-named assets from different scene folders, while staying
        stable across re-renders (so Remotion's file map can cache).
        """
        import hashlib

        composer_dir = Path(__file__).resolve().parent.parent.parent / "remotion-composer"
        public_dir = composer_dir / "public" / "om-staged"
        public_dir.mkdir(parents=True, exist_ok=True)

        staged = 0
        missing: list[str] = []

        def stage(value: str) -> str:
            nonlocal staged
            if not value or value.startswith(("http://", "https://", "data:")):
                return value
            raw = value[7:] if value.startswith("file://") else value
            src = Path(raw)
            if not src.is_absolute():
                # Already public-relative (the working convention) — leave it.
                return value
            if not src.exists():
                # Try recovery before giving up — this hits atelier props
                # too (hand-authored by the agent, not routed through
                # _resolve_manifest_asset_path), and the redaction that
                # produces a bracketed placeholder like "[PHONE_REDACTED]"
                # happens live in the agent's own completion each time it
                # transcribes the digit run — observed live 2026-07-19 to
                # recur even after the source asset_manifest.json on disk
                # was corrected, because the agent re-typed the path fresh
                # into its own props artifact and got redacted again.
                recovered = VideoCompose._recover_redacted_filename(src)
                if recovered is not None:
                    src = recovered
                else:
                    # An absolute path that doesn't exist on disk is never
                    # correct to hand to Remotion as-is — it can only ever
                    # surface downstream as an opaque "file:// not
                    # supported" proxy error, several layers removed from
                    # the real cause (missing asset, typo, or a corrupted
                    # path). Collect it so the caller can fail loud with
                    # the actual missing path instead of quietly shipping
                    # it through.
                    missing.append(str(src))
                    return value
            digest = hashlib.sha1(str(src.resolve()).encode()).hexdigest()[:12]
            link = public_dir / f"{digest}{src.suffix.lower()}"
            if not link.exists():
                real = src.resolve()
                try:
                    os.link(real, link)
                except OSError:
                    try:
                        link.symlink_to(real)
                    except OSError:
                        import shutil
                        shutil.copy2(real, link)
            staged += 1
            return f"om-staged/{link.name}"

        for cut in props.get("cuts", []) or []:
            for key in self._ASSET_CUT_KEYS:
                if isinstance(cut.get(key), str):
                    cut[key] = stage(cut[key])
            if isinstance(cut.get("images"), list):
                cut["images"] = [
                    stage(i) if isinstance(i, str) else i for i in cut["images"]
                ]
        # Asset overlays are assets too — this list handled cuts, scenes and
        # audio but not overlays, so a resolved overlay path reached the
        # browser as a bare file:// URL and failed to decode. Same
        # "overlays are second-class" pattern as B4 itself.
        for overlay in props.get("overlays", []) or []:
            for key in ("source", "src"):
                if isinstance(overlay.get(key), str):
                    overlay[key] = stage(overlay[key])
        for scene in props.get("scenes", []) or []:
            for key in ("src", "videoSrc", "backgroundSrc", "imageSrc"):
                if isinstance(scene.get(key), str):
                    scene[key] = stage(scene[key])
        audio = props.get("audio") or {}
        for layer in ("narration", "music"):
            entry = audio.get(layer)
            if isinstance(entry, dict) and isinstance(entry.get("src"), str):
                entry["src"] = stage(entry["src"])
        for track_key in ("music", "soundtrack"):
            track = props.get(track_key)
            if isinstance(track, dict) and isinstance(track.get("src"), str):
                track["src"] = stage(track["src"])
        if isinstance(props.get("videoSrc"), str):
            props["videoSrc"] = stage(props["videoSrc"])

        return public_dir, staged, missing

    def _normalize_deliverable_loudness(self, output_path: Path) -> bool:
        """Two-pass loudnorm the FINISHED file to -14 LUFS. Returns success.

        Runs on every render path that produces a deliverable. Normalizing the
        mix BEFORE muxing is not equivalent: muxing truncates audio to the
        video's length (`-shortest`), and integrated loudness is a property of
        the whole program — a mix normalized over its own 10s measured -11.8
        LUFS once cut to the 6s that actually ship (verified 2026-07-17).
        Only the finished file's loudness is the one anyone hears.

        `-c:v copy` makes this an audio-only remux, cheap even for long
        renders. Best-effort: a normalization failure never fails a render
        that already exists — the perceptual scan reports the off-target
        loudness either way.
        """
        loudness_normalized = False
        try:
            from tools.audio.loudness import normalize_media_loudness
            norm_path = output_path.with_name(output_path.stem + ".loudnorm.mp4")
            if normalize_media_loudness(output_path, norm_path, video_copy=True):
                norm_path.replace(output_path)
                loudness_normalized = True
            else:
                norm_path.unlink(missing_ok=True)
        except Exception:
            logging.getLogger("video_compose").warning(
                "Loudness normalization failed for %s", output_path, exc_info=True
            )
        return loudness_normalized

    def _encode_kenburns_segment(
        self,
        source: Path,
        seg_path: Path,
        duration: float,
        cut: dict[str, Any],
        target_w: int,
        target_h: int,
        fit_mode: str,
        codec: str,
        crf: int,
        preset: str,
        extra_vf: str | None = None,
    ) -> ToolResult | None:
        """Encode a still image into an eased Ken Burns video segment.

        extra_vf, when given, is a labeled filtergraph SUFFIX concatenated
        onto the chain (see aigc_label.opening_label_filter) — used to burn
        the AIGC explicit label into the opening segment during its own
        encode pass (no extra generation loss).

        Returns None on success, or a failed ToolResult. Progress is
        smoothstep-eased (p²(3-2p)) — linear zoompan is the slideshow tell.
        The image is upscaled 2× before zoompan to avoid its integer-step
        jitter. Output stream layout matches the video segments exactly
        (30fps yuv420p bt709 + 48kHz stereo silent audio) so concat-copy
        stays safe.
        """
        frames = max(1, int(round(duration * 30)))
        anim = str(cut.get("animation") or "ken-burns").replace("_", "-")
        p = f"(on/{frames})"
        eased = f"({p}*{p}*(3-2*{p}))"

        if anim == "zoom-out":
            z_expr = f"1.18-0.18*{eased}"
        elif anim in ("static", "none"):
            z_expr = "1.02"
        else:
            # zoom-in / ken-burns / pans all get the gentle eased push-in;
            # ken-burns adds a slight diagonal drift via the center offsets.
            z_expr = f"1+0.18*{eased}"

        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
        if anim in ("ken-burns", "ken-burns-slow-zoom", "pan-left"):
            x_expr = f"iw/2-(iw/zoom/2)-{eased}*iw*0.015"
            y_expr = f"ih/2-(ih/zoom/2)-{eased}*ih*0.01"
        elif anim == "pan-right":
            x_expr = f"iw/2-(iw/zoom/2)+{eased}*iw*0.015"

        # Pre-scale to cover 2× the target box (jitter headroom), then let
        # zoompan render the final size.
        if fit_mode == "cover":
            pre = (
                f"scale={target_w * 2}:{target_h * 2}:force_original_aspect_ratio=increase,"
                f"crop={target_w * 2}:{target_h * 2}"
            )
        else:
            pre = (
                f"scale={target_w * 2}:{target_h * 2}:force_original_aspect_ratio=decrease,"
                f"pad={target_w * 2}:{target_h * 2}:(ow-iw)/2:(oh-ih)/2:color=black"
            )
        vf = (
            f"{pre},zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
            f":d={frames}:s={target_w}x{target_h}:fps=30,setsar=1,"
            f"{self._SETPARAMS_BT709}"
        )
        if extra_vf:
            # Labeled filtergraph tail ("[aigc_base];movie=..." — see
            # opening_label_filter): direct concat, never comma-joined.
            vf = f"{vf}{extra_vf}"

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source),
            "-f", "lavfi", "-t", str(duration),
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map", "0:v", "-map", "1:a",
            "-filter:v", vf,
            "-c:v", codec, "-crf", str(crf), "-preset", preset,
            "-pix_fmt", "yuv420p",
            *self._COLOR_TAG_FLAGS,
            "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-shortest",
            str(seg_path),
        ]
        self.run_command(cmd)
        if not seg_path.exists():
            return ToolResult(
                success=False,
                error=f"Ken Burns segment encode produced no output for {source.name}",
            )
        return None

    def _extract_poster(self, inputs: dict[str, Any]) -> ToolResult:
        """Extract a poster/thumbnail frame from a rendered video.

        The publish stage promises a poster in publish_log but no tool
        existed to produce one (render_checks.py records a real fabrication
        incident). Picks the sharpest-looking default timestamp (15% in —
        past intro fades, before mid-video text density) unless overridden.
        """
        input_path = Path(inputs.get("input_path", ""))
        if not input_path.exists():
            return ToolResult(success=False, error=f"Input not found: {input_path}")
        output_path = Path(inputs.get("output_path", str(input_path.with_suffix("")) + "_poster.jpg"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        width = int(inputs.get("width", 1280))

        timestamp = inputs.get("timestamp_seconds")
        if timestamp is None:
            try:
                proc = self.run_command([
                    "ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(input_path),
                ], timeout=30)
                timestamp = round(float(proc.stdout.strip().splitlines()[0]) * 0.15, 2)
            except Exception:
                timestamp = 1.0

        self.run_command([
            "ffmpeg", "-y", "-ss", str(timestamp), "-i", str(input_path),
            "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "2",
            str(output_path),
        ], timeout=60)
        if not output_path.exists():
            # A timestamp past the end produces no frame — retry at 0.
            self.run_command([
                "ffmpeg", "-y", "-ss", "0", "-i", str(input_path),
                "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "2",
                str(output_path),
            ], timeout=60)
        if not output_path.exists():
            return ToolResult(success=False, error="Poster extraction produced no frame")
        return ToolResult(
            success=True,
            data={
                "operation": "extract_poster",
                "input": str(input_path),
                "output": str(output_path),
                "timestamp_seconds": timestamp,
                "width": width,
            },
            artifacts=[str(output_path)],
        )

    @staticmethod
    def _perceptual_scan(
        output_path: Path,
        duration: float,
        *,
        audio_expected: bool,
        has_audio: bool,
    ) -> dict[str, Any]:
        """See compose_review._perceptual_scan."""
        from tools.video.compose_review import _perceptual_scan
        return _perceptual_scan(
            output_path, duration, audio_expected=audio_expected, has_audio=has_audio
        )

    @staticmethod
    def _parse_probe_fps(fps_str: str) -> float:
        """See compose_review._parse_probe_fps."""
        from tools.video.compose_review import _parse_probe_fps
        return _parse_probe_fps(fps_str)

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
            "-vf", f"subtitles='{sub_escaped}':force_style='{ass_style}',{self._SETPARAMS_BT709}",
            "-c:v", codec, "-crf", str(crf),
            *self._COLOR_TAG_FLAGS,
            "-c:a", "copy",
            *self._FASTSTART_FLAGS,
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
        cmd.extend(["-c:v", codec, "-crf", str(crf), *self._COLOR_TAG_FLAGS, "-c:a", "copy"])
        cmd.extend(self._FASTSTART_FLAGS)
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

        # Profile codec/CRF are binding unless explicitly overridden — this
        # previously applied only the profile's resolution/fps (see _compose).
        profile_flags: list[str] = []
        if profile_name:
            try:
                from lib.media_profiles import get_profile
                profile = get_profile(profile_name)
                if "codec" not in inputs:
                    codec = profile.codec
                if "crf" not in inputs:
                    crf = profile.crf
                profile_flags = ["-s", f"{profile.width}x{profile.height}", "-r", str(profile.fps)]
            except ImportError:
                pass  # lib unavailable — proceed with defaults
            except ValueError as e:
                # A typo'd profile name must NOT silently render the default
                # aspect ratio: asking for a 9:16 delivery and getting 16:9 is
                # an invisible, catastrophic substitution (found by E2E render
                # inspection, 2026-07-17 — 'douyin_vertical' silently produced
                # 1920x1080). get_profile's error already lists valid names.
                return ToolResult(success=False, error=str(e))

        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-vf", self._SETPARAMS_BT709,
            "-c:v", codec, "-crf", str(crf), "-preset", preset,
            *self._COLOR_TAG_FLAGS,
            "-c:a", "aac", "-b:a", "192k",
            *profile_flags,
            *self._FASTSTART_FLAGS,
        ]

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
        """See compose_theme._resolve_subtitle_style."""
        from tools.video.compose_theme import _resolve_subtitle_style
        return _resolve_subtitle_style(explicit_style, edit_decisions, playbook)

    @staticmethod
    def _hex_to_ass_color(color: str, alpha: int = 0) -> str:
        """See compose_theme._hex_to_ass_color."""
        from tools.video.compose_theme import _hex_to_ass_color
        return _hex_to_ass_color(color, alpha)

    @staticmethod
    def _build_subtitle_style(style: dict) -> str:
        """See compose_theme._build_subtitle_style."""
        from tools.video.compose_theme import _build_subtitle_style
        return _build_subtitle_style(style)

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
