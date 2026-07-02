"""HyperFrames composition tool — HTML/CSS/GSAP render path.

Sibling to `video_compose` (FFmpeg + Remotion). This tool owns the HyperFrames
runtime end-to-end: workspace materialization, `hyperframes lint`,
`hyperframes validate`, visual QA helpers, and `hyperframes render`. It is invoked by
`video_compose` when `edit_decisions.render_runtime == "hyperframes"`, and
can also be called directly by pipelines that want HyperFrames-specific
operations (lint-only, validate-only, inspect-only, snapshot-only, scaffold-only).

This tool deliberately does NOT attempt parity with every Remotion scene
component. See `skills/core/hyperframes.md` for what is in scope in Phase 1
and what remains Remotion-only.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    ResumeSupport,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


log = logging.getLogger("hyperframes_compose")


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp", ".gif"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


class HyperFramesCompose(BaseTool):
    name = "hyperframes_compose"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_post"
    provider = "hyperframes"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:npx", "cmd:ffmpeg"]
    install_instructions = (
        "Requires Node.js >= 22 (https://nodejs.org/) and FFmpeg "
        "(https://ffmpeg.org/download.html). The HyperFrames CLI is fetched "
        "on first use via `npx hyperframes` (npm package: `hyperframes`). "
        "Note: the upstream monorepo develops the package as `@hyperframes/cli`, "
        "but it publishes to npm as `hyperframes`. `npx @hyperframes/cli` "
        "returns 404 -- do NOT use that form. Verify setup with "
        "`npx hyperframes doctor` or run the `doctor` operation on this tool."
    )
    agent_skills = [
        "hyperframes",
        "hyperframes-cli",
        "hyperframes-registry",
        "website-to-hyperframes",
        "gsap-core",
        "gsap-timeline",
    ]

    capabilities = [
        "hyperframes_render",
        "hyperframes_lint",
        "hyperframes_validate",
        "hyperframes_inspect",
        "hyperframes_snapshot",
        "hyperframes_doctor",
        "scaffold_workspace",
        "add_block",
    ]

    best_for = [
        "HTML/CSS/GSAP composition: kinetic typography, product promos, launch reels",
        "Motion-graphics-heavy briefs where the scene library in remotion-composer/ doesn't fit",
        "Website-to-video / UI-driven compositions",
        "Registry-block-driven scenes (hyperframes add data-chart, grain-overlay, etc.)",
    ]
    not_good_for = [
        "Word-level caption burn (stays on Remotion in Phase 1)",
        "Avatar / lip-sync presenter (stays on Remotion in Phase 1)",
        "Existing React scene stack (text_card, stat_card, chart, comparison): reuse Remotion",
    ]
    fallback_tools = ["video_compose"]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": [
                    "render",
                    "lint",
                    "validate",
                    "inspect",
                    "snapshot",
                    "doctor",
                    "scaffold_workspace",
                    "add_block",
                ],
                "description": (
                    "render: materialize workspace + lint + validate + render to MP4. "
                    "lint: run `hyperframes lint` on an existing workspace. "
                    "validate: run `hyperframes validate` (browser-based). "
                    "inspect: run `hyperframes inspect` for layout overflow QA. "
                    "snapshot: run `hyperframes snapshot` to capture keyframes. "
                    "doctor: run `hyperframes doctor` to check environment. "
                    "scaffold_workspace: materialize HTML/CSS/assets but do not render. "
                    "add_block: run `hyperframes add <name>` to install a registry "
                    "block or component into an existing workspace."
                ),
            },
            "block_name": {
                "type": "string",
                "description": (
                    "Registry block or component name for operation='add_block' "
                    "(e.g. 'data-chart', 'grain-overlay', 'shimmer-sweep'). "
                    "See https://hyperframes.heygen.com/catalog for the list."
                ),
            },
            "workspace_path": {
                "type": "string",
                "description": (
                    "Target HyperFrames workspace directory. Typically "
                    "`projects/<name>/hyperframes/`. Required for every op "
                    "except doctor."
                ),
            },
            "output_path": {
                "type": "string",
                "description": "Output MP4 path. Used by operation='render'.",
            },
            "edit_decisions": {
                "type": "object",
                "description": (
                    "Full edit_decisions artifact — required for render and "
                    "scaffold_workspace. Used to generate index.html + CSS."
                ),
            },
            "asset_manifest": {
                "type": "object",
                "description": (
                    "Full asset_manifest artifact — required for render and "
                    "scaffold_workspace. Used to resolve asset IDs to file paths."
                ),
            },
            "playbook": {
                "type": "object",
                "description": (
                    "Loaded playbook dict. Used to drive the style bridge "
                    "(CSS custom properties, typography, motion defaults)."
                ),
            },
            "profile": {
                "type": "string",
                "description": "Media profile name (youtube_landscape, tiktok_vertical, etc.).",
            },
            "quality": {
                "type": "string",
                "enum": ["draft", "standard", "high"],
                "default": "standard",
                "description": "Render quality. `draft` for iterating, `high` for delivery.",
            },
            "fps": {
                "type": "integer",
                "enum": [24, 30, 60],
                "default": 30,
            },
            "strict": {
                "type": "boolean",
                "default": False,
                "description": (
                    "If true, fail the render on any lint error. Matches "
                    "`hyperframes render --strict`."
                ),
            },
            "skip_contrast": {
                "type": "boolean",
                "default": False,
                "description": (
                    "Skip the WCAG contrast audit during validate. Acceptable "
                    "while iterating; forbidden for final delivery."
                ),
            },
            "samples": {
                "type": "integer",
                "default": 9,
                "description": "Number of timeline samples for operation='inspect'.",
            },
            "timestamps": {
                "type": "array",
                "items": {"type": "number"},
                "description": "Specific timestamps for inspect or snapshot operations.",
            },
            "overflow_tolerance_px": {
                "type": "number",
                "default": 2,
                "description": "Allowed pixel overflow for operation='inspect'.",
            },
            "max_issues": {
                "type": "integer",
                "default": 80,
                "description": "Maximum issues returned by operation='inspect'.",
            },
            "collapse_static": {
                "type": "boolean",
                "default": True,
                "description": "Collapse repeated static inspect issues across samples.",
            },
            "snapshot_frames": {
                "type": "integer",
                "default": 5,
                "description": "Number of evenly spaced keyframes for operation='snapshot'.",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=3072, vram_mb=0, disk_mb=2000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=0)
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["operation", "workspace_path", "edit_decisions"]
    side_effects = [
        "writes HTML/CSS/JS files into workspace_path",
        "copies asset files into workspace_path/assets/",
        "writes MP4 to output_path",
        "writes PNG screenshots in snapshot mode",
    ]
    user_visible_verification = [
        "Play the rendered MP4 and verify scene pacing, typography, and audio",
        "Inspect workspace_path/index.html in a browser via `npx hyperframes preview`",
    ]

    # ------------------------------------------------------------------
    # Status / availability
    # ------------------------------------------------------------------

    _NODE_FLOOR_MAJOR = 22
    _NPM_PACKAGE = "hyperframes"  # published npm name (NOT @hyperframes/cli — that's 404)
    # Process-level cache for the npm resolve check. Shape:
    #   {"version": "0.4.5"}   → package resolves
    #   {"error": "<short>"}   → resolution failed (offline, unpublished, etc.)
    # We cache per-process so the first call pays ~2-5s and subsequent calls
    # (get_info spam from the registry) are free.
    _npm_resolve_cache: Optional[dict[str, str]] = None

    @classmethod
    def _node_major_version(cls) -> Optional[int]:
        """Return Node.js major version, or None if node isn't installed."""
        node = shutil.which("node")
        if not node:
            return None
        try:
            out = subprocess.run(
                [node, "--version"], capture_output=True, text=True, timeout=5
            )
            if out.returncode != 0:
                return None
            match = re.match(r"v?(\d+)\.", out.stdout.strip())
            if not match:
                return None
            return int(match.group(1))
        except (OSError, subprocess.SubprocessError):
            return None

    @classmethod
    def _resolve_npm_package(cls) -> dict[str, str]:
        """Verify the `hyperframes` npm package actually resolves.

        `_runtime_check` previously only verified that node/ffmpeg/npx existed
        on PATH, which meant `runtime_available: True` on any machine with
        Node + FFmpeg — even offline, even if npm was down, even if the
        package was unpublished. This method performs a cheap
        `npm view hyperframes version` (5s timeout) and caches the answer
        for the rest of the process.

        Returns {"version": "X.Y.Z"} on success, {"error": "<short>"} on any
        failure (404, timeout, network error, npm missing). Never raises.
        """
        if cls._npm_resolve_cache is not None:
            return cls._npm_resolve_cache

        npm = shutil.which("npm")
        if not npm:
            cls._npm_resolve_cache = {"error": "npm not on PATH"}
            return cls._npm_resolve_cache

        try:
            proc = subprocess.run(
                [npm, "view", cls._NPM_PACKAGE, "version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            cls._npm_resolve_cache = {"error": "timeout (5s) — offline or slow registry"}
            return cls._npm_resolve_cache
        except (OSError, subprocess.SubprocessError) as e:
            cls._npm_resolve_cache = {"error": f"npm view failed: {type(e).__name__}"}
            return cls._npm_resolve_cache

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            # Most common failure is 404 (package unpublished or name wrong).
            if "404" in stderr or "E404" in stderr:
                cls._npm_resolve_cache = {
                    "error": f"npm package `{cls._NPM_PACKAGE}` not found (404)"
                }
            else:
                tail = stderr.splitlines()[-1][:200] if stderr else f"exit {proc.returncode}"
                cls._npm_resolve_cache = {"error": f"npm view failed: {tail}"}
            return cls._npm_resolve_cache

        version = (proc.stdout or "").strip()
        if not version:
            cls._npm_resolve_cache = {"error": "npm view returned empty version"}
        else:
            cls._npm_resolve_cache = {"version": version}
        return cls._npm_resolve_cache

    def _runtime_check(self) -> dict[str, Any]:
        """Return availability state for the HyperFrames runtime.

        Checks BOTH local binaries (node >= 22, ffmpeg, npx) AND that the
        `hyperframes` npm package actually resolves. A missing/404 package
        counts as unavailable — `runtime_available: True` means the runtime
        can genuinely run end-to-end, not just that the local tooling exists.
        """
        node_major = self._node_major_version()
        ffmpeg_ok = shutil.which("ffmpeg") is not None
        npx_ok = shutil.which("npx") is not None

        reasons: list[str] = []
        if node_major is None:
            reasons.append("node not found on PATH")
        elif node_major < self._NODE_FLOOR_MAJOR:
            reasons.append(
                f"node major version {node_major} < required {self._NODE_FLOOR_MAJOR}"
            )
        if not npx_ok:
            reasons.append("npx not found on PATH")
        if not ffmpeg_ok:
            reasons.append("ffmpeg not found on PATH")

        # Only probe npm if the local tooling is actually usable — otherwise
        # a missing-node run would also show a confusing npm error.
        npm_resolve: dict[str, str] = {}
        if not reasons:
            npm_resolve = self._resolve_npm_package()
            if "error" in npm_resolve:
                reasons.append(
                    f"npm package `{self._NPM_PACKAGE}` not resolvable: "
                    f"{npm_resolve['error']}"
                )

        return {
            "runtime_available": not reasons,
            "node_major": node_major,
            "ffmpeg_available": ffmpeg_ok,
            "npx_available": npx_ok,
            "npm_package": self._NPM_PACKAGE,
            "npm_package_version": npm_resolve.get("version"),
            "npm_resolve_error": npm_resolve.get("error"),
            "reasons": reasons,
        }

    def get_status(self) -> ToolStatus:
        check = self._runtime_check()
        return ToolStatus.AVAILABLE if check["runtime_available"] else ToolStatus.UNAVAILABLE

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        check = self._runtime_check()
        info["hyperframes_runtime"] = check
        if not check["runtime_available"]:
            info["setup_offer"] = {
                "effort": (
                    "1-minute fix"
                    if check["npx_available"] and check["ffmpeg_available"]
                    else "5-minute fix (install Node 22+ and/or FFmpeg)"
                ),
                "install_instructions": self.install_instructions,
                "unlocks": (
                    "HTML/CSS/GSAP composition runtime — kinetic typography, "
                    "product promos, registry blocks, website-to-video."
                ),
            }
        return info

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        ed = inputs.get("edit_decisions") or {}
        cuts = ed.get("cuts", [])
        total = 0.0
        for c in cuts:
            out_s = float(c.get("out_seconds", 0) or 0)
            in_s = float(c.get("in_seconds", 0) or 0)
            total += max(0.0, out_s - in_s)
        return 30.0 + total * 0.5

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs["operation"]
        start = time.time()
        try:
            if operation == "doctor":
                result = self._doctor(inputs)
            elif operation == "scaffold_workspace":
                result = self._scaffold(inputs)
            elif operation == "lint":
                result = self._lint(inputs)
            elif operation == "validate":
                result = self._validate(inputs)
            elif operation == "inspect":
                result = self._inspect(inputs)
            elif operation == "snapshot":
                result = self._snapshot(inputs)
            elif operation == "render":
                result = self._render(inputs)
            elif operation == "add_block":
                result = self._add_block(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")
        except Exception as e:
            log.exception("hyperframes_compose failed")
            return ToolResult(success=False, error=f"{type(e).__name__}: {e}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    # ------------------------------------------------------------------
    # Operations
    # ------------------------------------------------------------------

    def _doctor(self, inputs: dict[str, Any]) -> ToolResult:
        """Probe the environment. Reports node/ffmpeg/npx plus CLI doctor output."""
        check = self._runtime_check()
        out: dict[str, Any] = {"runtime_check": check}

        if not check["runtime_available"]:
            return ToolResult(
                success=False,
                error=(
                    "HyperFrames runtime floor not met: "
                    + "; ".join(check["reasons"])
                ),
                data=out,
            )

        # Ask the CLI itself for a deeper check. This also warms the npm
        # cache so the first real render doesn't pay the download cost.
        try:
            proc = self._run_hf(["doctor"], cwd=None, timeout=180, check=False)
            out["cli_doctor"] = {
                "exit_code": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-4000:],
                "stderr_tail": (proc.stderr or "")[-4000:],
            }
            ok = proc.returncode == 0
            return ToolResult(
                success=ok,
                data=out,
                error=None if ok else f"hyperframes doctor exit {proc.returncode}",
            )
        except Exception as e:
            out["cli_doctor_error"] = str(e)
            return ToolResult(
                success=False,
                error=f"hyperframes doctor failed: {e}",
                data=out,
            )

    def _scaffold(self, inputs: dict[str, Any]) -> ToolResult:
        """Materialize the HyperFrames workspace from OpenMontage artifacts.

        This does NOT call `hyperframes init` — we want full control over the
        generated files so they map cleanly to edit_decisions. `init` is
        meant for humans bootstrapping a project by hand.
        """
        workspace = self._require_workspace(inputs)
        edit_decisions = inputs.get("edit_decisions") or {}
        asset_manifest = inputs.get("asset_manifest") or {}
        playbook = inputs.get("playbook") or {}
        profile_name = inputs.get("profile")

        if not edit_decisions.get("cuts"):
            return ToolResult(
                success=False,
                error="edit_decisions with non-empty cuts[] is required for scaffold_workspace",
            )

        width, height, fps = self._resolve_dimensions(profile_name, inputs.get("fps", 30))

        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "compositions").mkdir(exist_ok=True)
        assets_dir = workspace / "assets"
        assets_dir.mkdir(exist_ok=True)

        # Resolve asset IDs → file paths + copy into workspace.
        resolved_cuts, asset_copies = self._resolve_and_stage_assets(
            edit_decisions.get("cuts", []),
            asset_manifest.get("assets", []),
            workspace,
        )

        audio_refs = self._resolve_audio_refs(
            edit_decisions.get("audio", {}),
            asset_manifest.get("assets", []),
            workspace,
        )

        # Style bridge: playbook → CSS custom properties + DESIGN.md.
        css_vars, design_md = self._style_bridge(playbook, edit_decisions)

        # Write hyperframes.json (registry config).
        (workspace / "hyperframes.json").write_text(
            json.dumps(
                {
                    "registry": "https://raw.githubusercontent.com/heygen-com/hyperframes/main/registry",
                    "paths": {
                        "blocks": "compositions",
                        "components": "compositions/components",
                        "assets": "assets",
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        # Write DESIGN.md (convenience file for human review + workspace context).
        if design_md:
            (workspace / "DESIGN.md").write_text(design_md, encoding="utf-8")

        # Write index.html — the main composition.
        total_duration = self._compute_total_duration(resolved_cuts)
        html = self._generate_index_html(
            cuts=resolved_cuts,
            audio_refs=audio_refs,
            width=width,
            height=height,
            total_duration=total_duration,
            css_vars=css_vars,
            title=edit_decisions.get("metadata", {}).get("title")
            or f"OpenMontage {edit_decisions.get('renderer_family', 'composition')}",
        )
        (workspace / "index.html").write_text(html, encoding="utf-8")

        return ToolResult(
            success=True,
            data={
                "operation": "scaffold_workspace",
                "workspace": str(workspace),
                "width": width,
                "height": height,
                "fps": fps,
                "total_duration_seconds": total_duration,
                "cut_count": len(resolved_cuts),
                "asset_copies": asset_copies,
            },
            artifacts=[str(workspace / "index.html")],
        )

    def _lint(self, inputs: dict[str, Any]) -> ToolResult:
        workspace = self._require_workspace(inputs)
        if not (workspace / "index.html").exists():
            return ToolResult(
                success=False,
                error=f"No index.html in {workspace}. Run scaffold_workspace first.",
            )
        proc = self._run_hf(["lint", "--json"], cwd=workspace, timeout=120, check=False)
        data: dict[str, Any] = {"exit_code": proc.returncode}
        payload = self._parse_json_output(proc.stdout)
        if payload is not None:
            data["report"] = payload
        else:
            data["stdout_tail"] = (proc.stdout or "")[-4000:]
        data["stderr_tail"] = (proc.stderr or "")[-2000:]
        ok = proc.returncode == 0
        return ToolResult(
            success=ok,
            data=data,
            error=None if ok else f"hyperframes lint exit {proc.returncode}",
        )

    def _validate(self, inputs: dict[str, Any]) -> ToolResult:
        workspace = self._require_workspace(inputs)
        if not (workspace / "index.html").exists():
            return ToolResult(
                success=False,
                error=f"No index.html in {workspace}. Run scaffold_workspace first.",
            )
        args = ["validate", "--json"]
        if inputs.get("skip_contrast"):
            args.append("--no-contrast")
        proc = self._run_hf(args, cwd=workspace, timeout=300, check=False)
        data: dict[str, Any] = {"exit_code": proc.returncode}
        payload = self._parse_json_output(proc.stdout)
        if payload is not None:
            data["report"] = payload
        else:
            data["stdout_tail"] = (proc.stdout or "")[-4000:]
        data["stderr_tail"] = (proc.stderr or "")[-2000:]
        ok = proc.returncode == 0
        return ToolResult(
            success=ok,
            data=data,
            error=None if ok else f"hyperframes validate exit {proc.returncode}",
        )

    def _inspect(self, inputs: dict[str, Any]) -> ToolResult:
        """Run HyperFrames layout inspection for overflow and container issues."""
        workspace = self._require_workspace(inputs)
        if not (workspace / "index.html").exists():
            return ToolResult(
                success=False,
                error=f"No index.html in {workspace}. Run scaffold_workspace first.",
            )
        args = [
            "inspect",
            "--json",
            f"--samples={int(inputs.get('samples', 9))}",
            f"--tolerance={inputs.get('overflow_tolerance_px', 2)}",
            f"--timeout={int(inputs.get('timeout_ms', 5000))}",
            f"--max-issues={int(inputs.get('max_issues', 80))}",
        ]
        timestamps = self._timestamp_arg(inputs.get("timestamps"))
        if timestamps:
            args.extend(["--at", timestamps])
        if inputs.get("collapse_static", True) is False:
            args.append("--no-collapse-static")
        if inputs.get("strict"):
            args.append("--strict")

        proc = self._run_hf(args, cwd=workspace, timeout=300, check=False)
        data = self._command_result_data(proc)
        data["operation"] = "inspect"
        ok = proc.returncode == 0
        return ToolResult(
            success=ok,
            data=data,
            error=None if ok else f"hyperframes inspect exit {proc.returncode}",
        )

    def _snapshot(self, inputs: dict[str, Any]) -> ToolResult:
        """Capture keyframes from a HyperFrames workspace for visual QA."""
        workspace = self._require_workspace(inputs)
        if not (workspace / "index.html").exists():
            return ToolResult(
                success=False,
                error=f"No index.html in {workspace}. Run scaffold_workspace first.",
            )
        before = self._png_files(workspace)
        args = [
            "snapshot",
            f"--frames={int(inputs.get('snapshot_frames', 5))}",
            f"--timeout={int(inputs.get('timeout_ms', 5000))}",
        ]
        timestamps = self._timestamp_arg(inputs.get("timestamps"))
        if timestamps:
            args.extend(["--at", timestamps])

        proc = self._run_hf(args, cwd=workspace, timeout=300, check=False)
        data = self._command_result_data(proc)
        after = self._png_files(workspace)
        new_files = [str(path) for path in after if path not in before]
        data.update(
            {
                "operation": "snapshot",
                "workspace": str(workspace),
                "snapshot_count": len(new_files),
                "snapshots": new_files,
            }
        )
        ok = proc.returncode == 0
        return ToolResult(
            success=ok,
            data=data,
            artifacts=new_files,
            error=None if ok else f"hyperframes snapshot exit {proc.returncode}",
        )

    def _add_block(self, inputs: dict[str, Any]) -> ToolResult:
        """Install a registry block or component via `hyperframes add`.

        Blocks are standalone sub-compositions (own dimensions, duration, timeline)
        that land at `compositions/<name>.html`. Components are effect snippets
        that land at `compositions/components/<name>.html`. After install, the
        caller is responsible for wiring the block into `index.html` via
        `data-composition-src` or pasting the component's snippet — see
        `.agents/skills/hyperframes-registry/SKILL.md`.
        """
        workspace = self._require_workspace(inputs)
        block = (inputs.get("block_name") or "").strip()
        if not block:
            return ToolResult(
                success=False,
                error="block_name is required for operation='add_block'",
            )
        if not workspace.exists():
            return ToolResult(
                success=False,
                error=(
                    f"Workspace {workspace} does not exist. Run "
                    "operation='scaffold_workspace' first."
                ),
            )
        args = ["add", block, "--json", "--no-clipboard"]
        proc = self._run_hf(args, cwd=workspace, timeout=300, check=False)
        data: dict[str, Any] = {
            "operation": "add_block",
            "block_name": block,
            "workspace": str(workspace),
            "exit_code": proc.returncode,
        }
        payload = self._parse_json_output(proc.stdout)
        if payload is not None:
            data["report"] = payload
        else:
            data["stdout_tail"] = (proc.stdout or "")[-4000:]
        data["stderr_tail"] = (proc.stderr or "")[-2000:]
        ok = proc.returncode == 0
        return ToolResult(
            success=ok,
            data=data,
            error=None if ok else f"hyperframes add {block} exit {proc.returncode}",
        )

    def _render(self, inputs: dict[str, Any]) -> ToolResult:
        """Full pipeline: scaffold → lint → validate → render."""
        runtime_ok = self._runtime_check()
        if not runtime_ok["runtime_available"]:
            return ToolResult(
                success=False,
                error=(
                    "HyperFrames runtime not available: "
                    + "; ".join(runtime_ok["reasons"])
                    + ". Per governance, this is a blocker — do NOT silently "
                    "fall back to another runtime without user approval."
                ),
                data={"runtime_check": runtime_ok},
            )

        workspace = self._require_workspace(inputs)
        output_path = Path(inputs.get("output_path") or (workspace / "renders" / "final.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        steps: dict[str, Any] = {}

        # 1. Scaffold — generate HTML/CSS/assets.
        scaffold = self._scaffold(inputs)
        steps["scaffold"] = scaffold.data
        if not scaffold.success:
            return ToolResult(
                success=False,
                error=f"Scaffold failed: {scaffold.error}",
                data={"steps": steps},
            )

        # 2. Lint — static contract checks.
        lint = self._lint({"workspace_path": str(workspace)})
        steps["lint"] = lint.data
        if not lint.success:
            if inputs.get("strict", False):
                return ToolResult(
                    success=False,
                    error=f"Lint failed (strict mode): {lint.error}",
                    data={"steps": steps},
                )
            log.warning("hyperframes lint reported issues (non-strict mode, continuing)")

        # 3. Validate — browser-based contract + contrast.
        validate = self._validate(
            {
                "workspace_path": str(workspace),
                "skip_contrast": inputs.get("skip_contrast", False),
            }
        )
        steps["validate"] = validate.data
        if not validate.success:
            return ToolResult(
                success=False,
                error=(
                    f"Validate failed: {validate.error}. HyperFrames render "
                    f"is blocked — fix the composition and re-run."
                ),
                data={"steps": steps},
            )

        # 4. Render.
        width, height, fps = self._resolve_dimensions(
            inputs.get("profile"), inputs.get("fps", 30)
        )
        quality = inputs.get("quality", "standard")
        args = [
            "render",
            "--output", str(output_path),
            "--fps", str(fps),
            "--quality", quality,
        ]
        proc = self._run_hf(args, cwd=workspace, timeout=1800, check=False)
        steps["render"] = {
            "exit_code": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-4000:],
            "stderr_tail": (proc.stderr or "")[-4000:],
        }
        if proc.returncode != 0:
            return ToolResult(
                success=False,
                error=f"hyperframes render exit {proc.returncode}",
                data={"steps": steps},
            )

        if not output_path.exists():
            return ToolResult(
                success=False,
                error=(
                    f"hyperframes render exited 0 but output file missing: "
                    f"{output_path}. Check stdout_tail for the real path."
                ),
                data={"steps": steps},
            )

        return ToolResult(
            success=True,
            data={
                "operation": "render",
                "output": str(output_path),
                "workspace": str(workspace),
                "width": width,
                "height": height,
                "fps": fps,
                "quality": quality,
                "steps": steps,
            },
            artifacts=[str(output_path)],
        )

    # ------------------------------------------------------------------
    # Workspace generation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _require_workspace(inputs: dict[str, Any]) -> Path:
        raw = inputs.get("workspace_path")
        if not raw:
            raise ValueError("workspace_path is required for this operation")
        return Path(raw).resolve()

    @staticmethod
    def _resolve_dimensions(
        profile_name: Optional[str], fps_in: int
    ) -> tuple[int, int, int]:
        """Resolve output dimensions from the media profile, with a safe default."""
        if profile_name:
            try:
                from lib.media_profiles import get_profile  # type: ignore
                p = get_profile(profile_name)
                return int(p.width), int(p.height), int(p.fps)
            except Exception:
                pass
        return 1920, 1080, int(fps_in)

    @staticmethod
    def _compute_total_duration(cuts: list[dict]) -> float:
        if not cuts:
            return 0.0
        return max(float(c.get("out_seconds", 0) or 0) for c in cuts)

    def _resolve_and_stage_assets(
        self,
        cuts: list[dict],
        assets: list[dict],
        workspace: Path,
    ) -> tuple[list[dict], list[dict[str, str]]]:
        """Resolve asset IDs in cuts[].source, copy files into workspace/assets/.

        HyperFrames resolves `src=` relative to the composition HTML file, so
        every asset must live inside the workspace tree. Copying is simpler
        (and portable) than symlinking, at the cost of disk space — these
        are regenerable under `projects/`.
        """
        asset_lookup = {a["id"]: a for a in assets if "id" in a}
        assets_dir = workspace / "assets"
        copies: list[dict[str, str]] = []
        resolved: list[dict] = []
        for cut in cuts:
            source = cut.get("source", "")
            resolved_cut = dict(cut)
            if source in asset_lookup:
                resolved_cut["source"] = asset_lookup[source].get("path", source)
            src_path = Path(resolved_cut["source"]) if resolved_cut.get("source") else None
            if src_path and src_path.exists() and not self._is_inside(src_path, workspace):
                dest = assets_dir / src_path.name
                if not dest.exists() or dest.stat().st_size != src_path.stat().st_size:
                    shutil.copy2(src_path, dest)
                resolved_cut["source"] = str(dest)
                copies.append({"from": str(src_path), "to": str(dest)})
            resolved.append(resolved_cut)
        return resolved, copies

    def _resolve_audio_refs(
        self,
        audio: dict[str, Any],
        assets: list[dict],
        workspace: Path,
    ) -> dict[str, Any]:
        """Resolve narration / music asset IDs and stage them."""
        asset_lookup = {a["id"]: a for a in assets if "id" in a}
        assets_dir = workspace / "assets"
        out: dict[str, Any] = {"narration": [], "music": None}

        for seg in audio.get("narration", {}).get("segments", []) or []:
            aid = seg.get("asset_id")
            if not aid or aid not in asset_lookup:
                continue
            src = Path(asset_lookup[aid].get("path", ""))
            if not src.exists():
                continue
            if not self._is_inside(src, workspace):
                dest = assets_dir / src.name
                if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                    shutil.copy2(src, dest)
            else:
                dest = src
            out["narration"].append(
                {
                    "src": str(dest),
                    "start_seconds": float(seg.get("start_seconds", 0) or 0),
                    "end_seconds": float(seg.get("end_seconds", 0) or 0) or None,
                }
            )

        music = audio.get("music", {})
        m_id = music.get("asset_id")
        if m_id and m_id in asset_lookup:
            src = Path(asset_lookup[m_id].get("path", ""))
            if src.exists():
                if not self._is_inside(src, workspace):
                    dest = assets_dir / src.name
                    if not dest.exists() or dest.stat().st_size != src.stat().st_size:
                        shutil.copy2(src, dest)
                else:
                    dest = src
                out["music"] = {
                    "src": str(dest),
                    "volume": float(music.get("volume", 0.15) or 0.15),
                    "fade_in_seconds": float(music.get("fade_in_seconds", 0) or 0),
                    "fade_out_seconds": float(music.get("fade_out_seconds", 0) or 0),
                }

        return out

    @staticmethod
    def _is_inside(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _style_bridge(
        self,
        playbook: dict[str, Any],
        edit_decisions: dict[str, Any],
    ) -> tuple[dict[str, str], str]:
        """Bridge OpenMontage playbook → HyperFrames CSS vars + DESIGN.md.

        Delegates to `lib/hyperframes_style_bridge.py` so the logic is
        shareable and testable. Falls back to a safe built-in default when
        the bridge module isn't available.
        """
        try:
            from lib.hyperframes_style_bridge import style_bridge  # type: ignore
            return style_bridge(playbook, edit_decisions)
        except Exception as e:
            log.debug("style_bridge fallback: %s", e)

        vl = (playbook or {}).get("visual_language", {})
        palette = vl.get("color_palette", {})
        typo = (playbook or {}).get("typography", {})

        def _first(raw: Any, default: str) -> str:
            if isinstance(raw, list) and raw:
                return str(raw[0])
            if isinstance(raw, str) and raw:
                return raw
            return default

        bg = _first(palette.get("background"), "#0B0F1A")
        fg = _first(palette.get("text"), "#F5F5F5")
        accent = _first(palette.get("accent"), "#F59E0B")
        primary = _first(palette.get("primary"), "#2563EB")
        heading = typo.get("heading", {}).get("font") or typo.get("heading", {}).get("family") or "Inter"
        body = typo.get("body", {}).get("font") or typo.get("body", {}).get("family") or "Inter"

        css_vars = {
            "--color-bg": bg,
            "--color-fg": fg,
            "--color-accent": accent,
            "--color-primary": primary,
            "--font-heading": heading,
            "--font-body": body,
            "--ease-primary": "cubic-bezier(0.65, 0, 0.35, 1)",
            "--duration-entrance": "0.6s",
        }
        design_md = (
            "# DESIGN\n\n"
            "Generated by OpenMontage HyperFrames style bridge (fallback).\n\n"
            f"- Background: `{bg}`\n"
            f"- Foreground: `{fg}`\n"
            f"- Accent: `{accent}`\n"
            f"- Primary: `{primary}`\n"
            f"- Heading font: `{heading}`\n"
            f"- Body font: `{body}`\n"
        )
        return css_vars, design_md

    # ------------------------------------------------------------------
    # HTML generation (minimal, Phase 1)
    # ------------------------------------------------------------------

    def _generate_index_html(
        self,
        cuts: list[dict],
        audio_refs: dict[str, Any],
        width: int,
        height: int,
        total_duration: float,
        css_vars: dict[str, str],
        title: str,
    ) -> str:
        """Emit a HyperFrames-contract-compliant index.html.

        Phase 1 covers the minimum required for smoke-testing the runtime:
        - still images (img.clip)
        - video clips (video.clip, muted playsinline + separate audio if needed)
        - text cards (div.clip with styled <h1>)
        - narration segments (audio)
        - music bed (audio, lower volume)

        Richer scene types (registry blocks, kinetic typography) are authored
        by the agent directly into compositions/ — this generator just
        provides a functional starting skeleton.
        """
        vars_css = "\n      ".join(f"{k}: {v};" for k, v in css_vars.items())

        clip_html: list[str] = []
        entrance_tweens: list[str] = []
        for i, cut in enumerate(cuts):
            html, tween = self._cut_to_html(i, cut, width, height)
            clip_html.append(html)
            if tween:
                entrance_tweens.append(tween)

        audio_html: list[str] = []
        for j, nar in enumerate(audio_refs.get("narration") or []):
            src = self._rel_from_workspace(nar["src"])
            start = nar.get("start_seconds", 0)
            end = nar.get("end_seconds")
            duration = (end - start) if end and end > start else (total_duration - start)
            audio_html.append(
                f'<audio id="nar-{j}" '
                f'data-start="{self._f(start)}" data-duration="{self._f(duration)}" '
                f'data-track-index="2" src="{self._escape_attr(src)}" '
                f'data-volume="1"></audio>'
            )

        music = audio_refs.get("music")
        if music:
            src = self._rel_from_workspace(music["src"])
            audio_html.append(
                f'<audio id="music" '
                f'data-start="0" data-duration="{self._f(total_duration)}" '
                f'data-track-index="3" src="{self._escape_attr(src)}" '
                f'data-volume="{self._f(music["volume"])}"></audio>'
            )

        tween_block = "\n        ".join(entrance_tweens) if entrance_tweens else "// no tweens"

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{self._escape_text(title)}</title>
  <style>
    :root {{
      {vars_css}
    }}
    body {{ margin: 0; background: var(--color-bg); color: var(--color-fg); font-family: var(--font-body); }}
    [data-composition-id="root"] {{
      position: relative;
      width: {width}px;
      height: {height}px;
      overflow: hidden;
    }}
    .clip {{ position: absolute; inset: 0; }}
    .clip.video-clip, .clip.image-clip {{ object-fit: cover; width: 100%; height: 100%; }}
    .clip.text-card {{ display: flex; align-items: center; justify-content: center; padding: 120px 160px; box-sizing: border-box; text-align: center; }}
    .clip.text-card h1 {{ font-family: var(--font-heading); font-weight: 700; font-size: 96px; line-height: 1.1; margin: 0; color: var(--color-fg); }}
    .clip.text-card .subtitle {{ font-size: 36px; margin-top: 24px; color: var(--color-accent); }}
  </style>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
</head>
<body>
  <div data-composition-id="root" data-start="0" data-duration="{self._f(total_duration)}" data-width="{width}" data-height="{height}">
    {"".join(clip_html)}
    {"".join(audio_html)}
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      {tween_block}
      window.__timelines["root"] = tl;
    </script>
  </div>
</body>
</html>
"""

    def _cut_to_html(
        self, index: int, cut: dict, width: int, height: int
    ) -> tuple[str, Optional[str]]:
        """Render one cut + its entrance tween. Returns (html, tween or None)."""
        cut_id = f"cut-{index}"
        in_s = float(cut.get("in_seconds", 0) or 0)
        out_s = float(cut.get("out_seconds", 0) or 0)
        duration = max(0.1, out_s - in_s)

        source = cut.get("source") or ""
        cut_type = (cut.get("type") or "").lower()
        text = cut.get("text") or cut.get("title") or ""

        src_path = Path(source) if source else None
        ext = src_path.suffix.lower() if src_path else ""

        # Decide scene shape
        if cut_type in {"text_card", "hero_title", "callout"} or (not source and text):
            inner = f'<h1>{self._escape_text(text or f"Scene {index + 1}")}</h1>'
            subtitle = cut.get("subtitle") or cut.get("caption")
            if subtitle:
                inner += f'<div class="subtitle">{self._escape_text(subtitle)}</div>'
            html = (
                f'<div id="{cut_id}" class="clip text-card" '
                f'data-start="{self._f(in_s)}" data-duration="{self._f(duration)}" '
                f'data-track-index="1">{inner}</div>'
            )
            # Mild entrance — fade + lift.
            tween = (
                f'tl.from("#{cut_id} h1", {{ y: 40, opacity: 0, duration: 0.6, '
                f'ease: "power3.out" }}, {self._f(in_s + 0.1)});'
            )
            return html, tween

        if ext in _IMAGE_EXTENSIONS and src_path:
            rel = self._rel_from_workspace(str(src_path))
            html = (
                f'<img id="{cut_id}" class="clip image-clip" '
                f'src="{self._escape_attr(rel)}" '
                f'data-start="{self._f(in_s)}" data-duration="{self._f(duration)}" '
                f'data-track-index="1" alt="">'
            )
            tween = (
                f'tl.from("#{cut_id}", {{ scale: 1.05, opacity: 0, duration: 0.5, '
                f'ease: "power2.out" }}, {self._f(in_s)});'
            )
            return html, tween

        if ext in _VIDEO_EXTENSIONS and src_path:
            rel = self._rel_from_workspace(str(src_path))
            html = (
                f'<video id="{cut_id}" class="clip video-clip" '
                f'src="{self._escape_attr(rel)}" '
                f'data-start="{self._f(in_s)}" data-duration="{self._f(duration)}" '
                f'data-track-index="1" muted playsinline></video>'
            )
            return html, None

        # Unknown cut shape — render a placeholder text card so the render
        # still succeeds; lint/validate will surface the issue.
        if ext in {".html", ".htm"} and src_path:
            rel = self._rel_from_workspace(str(src_path))
            composition_id = Path(rel).stem
            html = (
                f'<div id="{cut_id}" class="clip composition-clip" '
                f'data-composition-id="{self._escape_attr(composition_id)}" '
                f'data-composition-src="{self._escape_attr(rel)}" '
                f'data-start="{self._f(in_s)}" data-duration="{self._f(duration)}" '
                f'data-width="{width}" data-height="{height}" '
                f'data-track-index="1"></div>'
            )
            return html, None

        placeholder = self._escape_text(text or cut.get("reason") or f"Scene {index + 1}")
        html = (
            f'<div id="{cut_id}" class="clip text-card" '
            f'data-start="{self._f(in_s)}" data-duration="{self._f(duration)}" '
            f'data-track-index="1"><h1>{placeholder}</h1></div>'
        )
        return html, None

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _run_hf(
        self,
        args: list[str],
        *,
        cwd: Optional[Path],
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess:
        """Invoke `npx hyperframes <args>` with the right Windows quirks.

        We intentionally bypass `self.run_command` here because we do NOT
        want to raise CalledProcessError on non-zero exits — the caller
        parses lint/validate/render exit codes itself.
        """
        cmd = ["npx", "--yes", "hyperframes", *args]
        # On Windows, resolve the .cmd wrapper so subprocess can find it
        # without shell=True.
        if os.name == "nt":
            resolved = shutil.which(cmd[0])
            if resolved:
                cmd[0] = resolved
        try:
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(cwd) if cwd else None,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            # Surface timeouts as a failed CompletedProcess so callers get a
            # uniform shape. The stderr tail will say timeout.
            return subprocess.CompletedProcess(
                args=cmd,
                returncode=124,
                stdout=e.stdout or "",
                stderr=(e.stderr or "") + f"\n[timeout after {timeout}s]",
            )

    @staticmethod
    def _parse_json_output(stdout: str) -> Optional[Any]:
        """Parse a `--json` report, tolerating surrounding banner lines."""
        if not stdout:
            return None
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            return json.loads(stdout[start : end + 1])
        except json.JSONDecodeError:
            return None

    def _command_result_data(self, proc: subprocess.CompletedProcess) -> dict[str, Any]:
        data: dict[str, Any] = {"exit_code": proc.returncode}
        payload = self._parse_json_output(proc.stdout)
        if payload is not None:
            data["report"] = payload
        else:
            data["stdout_tail"] = (proc.stdout or "")[-4000:]
        data["stderr_tail"] = (proc.stderr or "")[-2000:]
        return data

    @staticmethod
    def _timestamp_arg(raw: Any) -> str:
        if not raw:
            return ""
        if isinstance(raw, str):
            return raw
        if isinstance(raw, (int, float)):
            return str(raw)
        if isinstance(raw, list):
            return ",".join(str(float(item)).rstrip("0").rstrip(".") for item in raw)
        return ""

    @staticmethod
    def _png_files(workspace: Path) -> set[Path]:
        return {path.resolve() for path in workspace.rglob("*.png") if path.is_file()}

    @staticmethod
    def _f(v: float) -> str:
        return f"{float(v):.3f}".rstrip("0").rstrip(".")

    @staticmethod
    def _escape_text(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def _escape_attr(s: str) -> str:
        return HyperFramesCompose._escape_text(s).replace('"', "&quot;")

    @staticmethod
    def _rel_from_workspace(path: str) -> str:
        """HyperFrames resolves src= relative to index.html. Our asset files
        live under workspace/assets/, so when we stage a copy we know the
        relative path is `assets/<name>`. For files already in the workspace
        tree, fall back to the file name.
        """
        p = Path(path)
        # If it's already a relative path starting with assets/, keep as-is.
        if not p.is_absolute():
            return str(p).replace("\\", "/")
        parts = p.parts
        for anchor in ("assets", "compositions"):
            if anchor in parts:
                index = len(parts) - 1 - list(reversed(parts)).index(anchor)
                return "/".join(parts[index:])
        # Otherwise emit just the basename under assets/.
        return f"assets/{p.name}"
