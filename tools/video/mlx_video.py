"""MLX video generation via the sibling ``mlx-movie-director`` runtime.

The motion analog of ``mlx_image``: bridges OpenMontage's video-generation
capability to the Apple-Silicon-native MLX LTX-2.3 22B pipeline
(``python/mlx-movie-director/run.py video {generate, t2i2v}``).

Why this provider exists (see ``docs/REVIEW-image-to-video-voice.md`` §7):
OpenMontage already has four ``$0`` local i2v providers (wan / hunyuan / ltx /
cogvideo), but they require CUDA ``diffusers`` (8–24 GB VRAM) and do not run on
Apple Silicon. MLX LTX-2.3 is the **MPS-native** i2v/t2v path — a free, offline
local default, NOT a premium-cinema replacement for Seedance / Veo / Kling
(those advertise ``cinematic_quality`` / ``lip_sync`` / ``multi_shot``; this
provider deliberately does not).

Governance note: for a ``motion_required=true`` brief the locked ``render_runtime``
(FFmpeg / Remotion / HyperFrames) is a compose-stage commitment. ``mlx_video``
is a *generation* provider — it produces a clip, it does not satisfy or
substitute for the compose runtime. The motion-required prohibition
(``AGENT_GUIDE.md`` §"Motion-Required Requests") still applies upstream.

Env contract (same as ``mlx_image``):
* ``MLX_MOVIE_DIRECTOR_DIR``  — repo root containing ``python/mlx-movie-director/run.py``.
* ``MLX_VENV_PYTHON``         — venv interpreter (default
  ``<dir>/python/venv/bin/python``). Per-machine, NOT auto-created — see
  ``install_instructions``.

Discovery is automatic — ``video_selector`` picks up any
``capability="video_generation"`` tool, so this file required zero selector
edits.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
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
from tools._mlx.env import resolve_mlx_env

# Env contract + resolution live in tools/_mlx/env.py (shared with mlx_image +
# mlx_caption). Only the video-specific frame-count + output-extension
# constants are local to this file.

# LTX-2.3 output extensions (broader than mlx_image's image set).
_VIDEO_EXTS = ("*.mp4", "*.mov", "*.webm", "*.gif")
_JSON_SUMMARY_RE = re.compile(r"JSON_SUMMARY:(\{.*\})\s*$", re.MULTILINE)

# LTX-2.3 frame count must be 8k+1 (25, 33, 41, 49, 57, …). Default 97 ≈ 4s @ 24fps.
_DEFAULT_FRAMES = 97
_DEFAULT_FPS = 24.0


class MLXVideo(BaseTool):
    name = "mlx_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "mlx"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED  # LTX-2.3 is seed-deterministic on a fixed stack
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []
    install_instructions = (
        "Set MLX_MOVIE_DIRECTOR_DIR to the mlx-movie-director repo root "
        "(contains python/mlx-movie-director/run.py).\n"
        "Optionally set MLX_VENV_PYTHON to its venv interpreter (default "
        "<MLX_MOVIE_DIRECTOR_DIR>/python/venv/bin/python).\n"
        "The MLX venv is per-machine and NOT auto-created — recreate it with:\n"
        "  uv venv python/venv --python 3.12\n"
        "  uv pip install -r python/mlx-movie-director/requirements.txt "
        "--python python/venv/bin/python\n"
        "The VIDEO path needs substantially more than requirements.txt (tracked "
        "as upstream MLX-repo gap G1 — heavier than the image path):\n"
        "  - opencv-python (image-quality imports cv2)\n"
        "  - mflux (the Z-Image VAE loader)\n"
        "  - the ltx-2-mlx workspace members (editable): ltx-core-mlx,\n"
        "    ltx-pipelines-mlx, ltx-trainer from the sibling ltx-2-mlx repo\n"
        "    (`uv pip install -e <ltx-2-mlx>/packages/<member>`). The ltx-2-mlx\n"
        "    root pyproject currently fails under uv (PEP 639 license classifier)\n"
        "    so install each packages/* member directly.\n"
        "  - a transformers version compatible with the mlx_lm the members pull\n"
        "    (a known conflict point — the NewlineTokenizer register call).\n"
        "Until G1 lands, image (mlx_image) works end-to-end but video may need\n"
        "manual env resolution. Requires Apple Silicon (arm64)."
    )
    agent_skills = ["mlx-movie-director"]

    capabilities = ["text_to_video", "image_to_video"]
    # Honest surface: a free local default. Deliberately NOT advertising
    # cinematic_quality / native_audio / lip_sync / multi_shot — those are the
    # premium cloud flags (seedance/veo/kling); LTX-2.3 local is not that.
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "reference_image": True,
        "offline": True,
        "native_audio": False,
        "local_gpu": True,
        "seed": True,
    }
    best_for = [
        "local Apple Silicon video generation with no API cost",
        "free offline image-to-video (animating a still into a short clip)",
        "text-to-video local default before escalating to paid cloud providers",
    ]
    not_good_for = [
        "premium cinematic delivery (use seedance/veo/kling/runway)",
        "native audio / dialogue generation",
        "long-form video (LTX-2.3 local is short-clip oriented)",
        "non-Apple-Silicon hosts (no CUDA / no MPS)",
    ]
    fallback = "ltx_video_local"
    # Note: unlike the cloud/local diffusers providers, we do NOT append
    # image_selector here — mlx_video is motion-only and must never silently
    # degrade a motion-required brief to a still image.
    fallback_tools = ["ltx_video_local", "wan_video", "hunyuan_video", "ltx_video_modal"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt describing the desired motion / scene."},
            "action": {
                "type": "string",
                "enum": ["auto", "generate", "t2i2v"],
                "default": "auto",
                "description": (
                    "'generate' = direct LTX-2.3 (T2V or I2V depending on whether a "
                    "reference image is given). 't2i2v' = the 3-stage ZImage T2I → VLM "
                    "prompt → LTX-2.3 I2V pipeline (richer, slower). 'auto' picks "
                    "generate for I2V (image present) and t2i2v for pure T2V."
                ),
            },
            # I2V conditioning. Presence of reference_image/_path also satisfies
            # video_selector's _filter_candidates for the image_to_video operation.
            "reference_image": {"type": "string", "description": "Source image for I2V (image-to-video)."},
            "reference_image_path": {"type": "string", "description": "Alias of reference_image (source image path)."},
            "image_url": {"type": "string", "description": "Alias of reference_image (selector compatibility)."},
            "image_path": {"type": "string", "description": "Alias of reference_image (selector compatibility)."},
            "width": {"type": "integer", "description": "Video width (default 704; auto-snapped to multiple of 64)."},
            "height": {"type": "integer", "description": "Video height (default 448; auto-snapped to multiple of 64)."},
            "num_frames": {
                "type": "integer",
                "description": "Frame count (default 97 ≈ 4s @ 24fps; must be 8k+1: 25,33,41,49,…).",
            },
            "fps": {"type": "number", "description": "Output frame rate (default 24.0)."},
            "seed": {"type": "integer", "description": "Random seed (default 42)."},
            "cfg_scale": {
                "type": "number",
                "description": "Text guidance (default 5.0 T2V/I2V; lower = softer motion). Does not affect image conditioning.",
            },
            "stg_scale": {"type": "number", "description": "Spatial-temporal guidance (default 1.5 for dasiwa)."},
            "stage1_steps": {"type": "integer", "description": "Stage 1 denoising steps (default 8; 30 for max quality, slower)."},
            "transformer": {
                "type": "string",
                "description": "Transformer instance under models/transformer/ (e.g. 'dasiwa'). t2i2v default uses dasiwa.",
            },
            "output_path": {"type": "string", "description": "Where to save the generated video."},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=18000, vram_mb=0, disk_mb=2000, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "action", "num_frames", "seed", "width", "height"]
    side_effects = ["spawns python/venv/bin/python run.py video …", "writes video file to output_path"]
    user_visible_verification = ["Watch generated clip for motion coherence and artifacts."]

    # ------------------------------------------------------------------
    # Environment + availability (mirrors mlx_image)
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_env() -> dict[str, Any]:
        # Delegates to the shared resolver (need_models=True — video generation
        # needs the mlx-models stack + Apple Silicon). See tools/_mlx/env.py.
        return resolve_mlx_env(need_models=True)

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._resolve_env()["ok"] else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # LTX-2.3 ~2-4s/step stage1 × ~8 steps + decode; rough clip budget.
        steps = inputs.get("stage1_steps") or 8
        frames = inputs.get("num_frames") or _DEFAULT_FRAMES
        return float(steps) * 3.0 + frames * 0.15

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        env = self._resolve_env()
        info["mlx_env"] = {"configured": env["ok"], "reason": env.get("reason"), "arm64": env.get("arm64"), "mlx_dir": env.get("mlx_dir"), "venv_python": env.get("venv_python")}
        return info

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        env = self._resolve_env()
        if not env["ok"]:
            return ToolResult(success=False, error=env["reason"])

        run_py = env["run_py"]
        venv_python = env["venv_python"]

        action = self._resolve_action(inputs)
        cmd = [venv_python, run_py, "video", action]

        try:
            cmd.extend(self._build_args(inputs, action))
        except _BadInput as exc:
            return ToolResult(success=False, error=str(exc))

        out_dir = tempfile.mkdtemp(prefix="mlx_video_")
        # --gen-output-dir is a top-level run.py flag (accepted); --json-summary is
        # NOT registered on the video subparser (video.py:132 deliberately skips
        # add_common_generation_args, even though video-generate.py:875 reads
        # args.json_summary — an upstream MLX-repo asymmetry). So we rely on the
        # dir-scan fallback in _parse_outputs: the gen-output-dir is a fresh
        # isolated temp dir, so its only .mp4 is this run's output.
        cmd.extend(["--gen-output-dir", out_dir])

        start = time.time()
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, check=False)
        except subprocess.TimeoutExpired:
            shutil.rmtree(out_dir, ignore_errors=True)
            return ToolResult(success=False, error="MLX video generation timed out (>1800s).")
        except Exception as exc:  # pragma: no cover
            shutil.rmtree(out_dir, ignore_errors=True)
            return ToolResult(success=False, error=f"Failed to spawn MLX runtime: {exc}")

        elapsed = round(time.time() - start, 2)

        if proc.returncode != 0:
            shutil.rmtree(out_dir, ignore_errors=True)
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
            return ToolResult(success=False, error=f"run.py exited {proc.returncode}:\n" + "\n".join(tail))

        outputs = self._parse_outputs(proc.stdout, out_dir)
        if not outputs:
            shutil.rmtree(out_dir, ignore_errors=True)
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
            return ToolResult(success=False, error="run.py produced no video output:\n" + "\n".join(tail))

        src = Path(outputs[0])
        output_path = inputs.get("output_path")
        final_path = src
        if output_path:
            dest = Path(output_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.resolve() != src.resolve():
                shutil.copy2(src, dest)
            final_path = dest

        seed = self._effective_seed(inputs)
        model = self._model_label(inputs, action)

        return ToolResult(
            success=True,
            data={
                "provider": "mlx",
                "model": model,
                "prompt": inputs["prompt"],
                "action": action,
                "mode": "i2v" if self._has_reference_image(inputs) else "t2v",
                "width": inputs.get("width"),
                "height": inputs.get("height"),
                "num_frames": inputs.get("num_frames"),
                "fps": inputs.get("fps"),
                "seed": seed,
                "output": str(final_path),
                "format": final_path.suffix.lstrip(".") or "mp4",
                "mlx_run_py": run_py,
            },
            artifacts=[str(final_path)],
            cost_usd=0.0,
            duration_seconds=elapsed,
            seed=seed,
            model=model,
        )

    # ------------------------------------------------------------------
    # Action + argument mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _effective_seed(inputs: dict[str, Any]) -> int:
        s = inputs.get("seed")
        return s if isinstance(s, int) else 42  # run.py video default

    @staticmethod
    def _model_label(inputs: dict[str, Any], action: str) -> str:
        transformer = inputs.get("transformer") or ("dasiwa" if action == "t2i2v" else None)
        if transformer:
            return f"mlx-ltx2.3/{transformer}"
        return "mlx-ltx2.3"

    @staticmethod
    def _has_reference_image(inputs: dict[str, Any]) -> bool:
        return bool(
            inputs.get("reference_image")
            or inputs.get("reference_image_path")
            or inputs.get("image_url")
            or inputs.get("image_path")
        )

    @staticmethod
    def _resolve_reference(inputs: dict[str, Any]) -> str | None:
        return (
            inputs.get("reference_image")
            or inputs.get("reference_image_path")
            or inputs.get("image_url")
            or inputs.get("image_path")
        )

    @classmethod
    def _resolve_action(cls, inputs: dict[str, Any]) -> str:
        """Decide the run.py video action.

        - Explicit `action` input wins (generate | t2i2v).
        - auto: image present → generate (I2V); prompt only → t2i2v (the richer
          3-stage prompt→image→video path — MLX's headline feature).
        """
        action = inputs.get("action") or "auto"
        has_image = cls._has_reference_image(inputs)
        if action == "generate":
            return "generate"
        if action == "t2i2v":
            return "t2i2v"
        # auto
        return "generate" if has_image else "t2i2v"

    @classmethod
    def _build_args(cls, inputs: dict[str, Any], action: str) -> list[str]:
        out: list[str] = []
        prompt = inputs.get("prompt")
        if not prompt:
            raise _BadInput("prompt is required.")
        out += ["--prompt", str(prompt)]

        for key, flag, cast in (
            ("width", "--width", int),
            ("height", "--height", int),
            ("num_frames", "--frames", int),
            ("fps", "--fps", float),
            ("seed", "--seed", int),
            ("cfg_scale", "--cfg-scale", float),
            ("stg_scale", "--stg-scale", float),
            ("stage1_steps", "--stage1-steps", int),
            ("transformer", "--transformer", str),
        ):
            if inputs.get(key) is not None:
                out += [flag, str(cast(inputs[key]))]  # type: ignore[call-arg]

        ref = cls._resolve_reference(inputs)
        if action == "generate":
            if ref:
                out += ["--input-image", str(ref)]
            # t2v when no reference image
        elif action == "t2i2v":
            # t2i2v accepts an optional --input-image to animate a specific still;
            # otherwise it generates the keyframe from the prompt first.
            if ref:
                out += ["--input-image", str(ref)]
        return out

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_outputs(stdout: str, out_dir: str) -> list[str]:
        match = _JSON_SUMMARY_RE.search(stdout or "")
        if match:
            try:
                payload = json.loads(match.group(1))
                outs = payload.get("outputs") or []
                if isinstance(outs, list):
                    resolved = [o for o in outs if o and os.path.isfile(str(o))]
                    if resolved:
                        return resolved
            except json.JSONDecodeError:
                pass
        candidates: list[Path] = []
        for ext in _VIDEO_EXTS:
            candidates.extend(Path(out_dir).glob(ext))
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(p) for p in candidates]


class _BadInput(Exception):
    """Raised when provider inputs cannot map cleanly to run.py flags."""
