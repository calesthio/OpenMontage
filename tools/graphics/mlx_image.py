"""MLX image generation via the sibling ``mlx-movie-director`` runtime.

Bridges OpenMontage's image-generation capability to the Apple-Silicon-native
MLX pipeline (``python/mlx-movie-director/run.py`` — Z-Image / Flux2 Klein /
Lens, plus ControlNet, i2i, LoRA, faceswap). This is the provider that fills
OpenMontage's biggest verified gap: a local, ``$0`` path that advertises
``controlnet`` / ``img2img`` / ``reference_image`` / ``faceswap`` / ``lora``,
which today only Grok's edit mode partially covers.

Like ``comfyui_image``, this provider shells out to an external generator and
reads the result back. The contract:

* ``MLX_MOVIE_DIRECTOR_DIR``  — repo root containing ``python/mlx-movie-director/run.py``.
* ``MLX_VENV_PYTHON``         — the MLX venv interpreter (default
  ``<MLX_MOVIE_DIRECTOR_DIR>/python/venv/bin/python``). Per the MLX repo's
  CLAUDE.md, this venv is per-machine and NOT auto-created; on a fresh clone it
  is absent and must be recreated
  (``uv venv python/venv --python 3.12 && uv pip install -r .../requirements.txt --python ...``).

Discovery is automatic — ``image_selector`` picks up any
``capability="image_generation"`` tool, so adding this file required zero
selector edits. See ``docs/REVIEW-story-to-image.md`` §2.1 and
``docs/REVIEW-image-to-video-voice.md`` §7.
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

# Env constants + resolution live in tools/_mlx/env.py (shared with mlx_video +
# mlx_caption). Only the JSON-summary marker is local to image generation.

# The stdout marker emitted by `run.py ... --json-summary` (see
# app/commands/_shared.py:681 — execute_generation prints "JSON_SUMMARY:{...}").
_JSON_SUMMARY_RE = re.compile(r"JSON_SUMMARY:(\{.*\})\s*$", re.MULTILINE)


class MLXImage(BaseTool):
    name = "mlx_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "mlx"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # resolved at runtime via _resolve_env()
    install_instructions = (
        "Set MLX_MOVIE_DIRECTOR_DIR to the mlx-movie-director repo root "
        "(contains python/mlx-movie-director/run.py).\n"
        "Optionally set MLX_VENV_PYTHON to its venv interpreter (default "
        "<MLX_MOVIE_DIRECTOR_DIR>/python/venv/bin/python).\n"
        "The MLX venv is per-machine and NOT auto-created — recreate it with:\n"
        "  uv venv python/venv --python 3.12\n"
        "  uv pip install -r python/mlx-movie-director/requirements.txt "
        "--python python/venv/bin/python\n"
        "Plus two runtime deps not yet in that requirements.txt (tracked as an "
        "upstream MLX-repo gap): opencv-python (image-quality imports cv2) and "
        "mflux (the Z-Image VAE loader). Install both into the same venv.\n"
        "Requires Apple Silicon (arm64)."
    )
    agent_skills = ["mlx-movie-director"]

    capabilities = [
        "text_to_image",
        "image_to_image",
        "controlnet",
        "faceswap",
        "provider_selection",
    ]
    # These feed the scorer's `control` dimension — today only grok_image
    # advertises image_edit, so mlx_image is the first provider to cover the
    # full ControlNet / i2i / LoRA / faceswap surface (see REVIEW-story-to-image §6.1).
    supports = {
        "seed": True,
        "custom_size": True,
        "controlnet": True,
        "img2img": True,
        "image_edit": True,
        "reference_image": True,
        "faceswap": True,
        "lora": True,
        "multi_lora": True,
        "offline": True,
    }
    best_for = [
        "local Apple Silicon image generation with no API cost",
        "ControlNet-conditioned generation (pose / depth / region)",
        "true image-to-image edit and inpainting (denoise-strength controlled)",
        "LoRA / multi-LoRA character and style conditioning",
        "BFS face / head swap",
    ]
    not_good_for = [
        "non-Apple-Silicon hosts (no CUDA / no MPS)",
        "setups without the MLX venv recreated (see install_instructions)",
    ]
    # No `negative_prompt` here on purpose: run.py image t2i has no
    # --negative-prompt flag (Z-Image handles negatives internally). The
    # selector strips unsupported passthrough keys, so omitting it is correct.
    fallback = "flux_image"
    fallback_tools = ["comfyui_image", "flux_image", "local_diffusion", "openai_image"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string", "description": "Text prompt for image generation."},
            "width": {"type": "integer", "description": "Image width in pixels."},
            "height": {"type": "integer", "description": "Image height in pixels."},
            "resolution": {
                "type": "string",
                "description": (
                    "Resolution tier or explicit WxH passed through to run.py "
                    "('--resolution'). One of: model (default), benchmark, large, "
                    "or 'WxH'/'W:H' snapped to a multiple of 16."
                ),
            },
            "steps": {"type": "integer", "description": "Sampling steps (pipeline default if unset)."},
            "seed": {"type": "integer", "description": "Random seed (default 777)."},
            "pipeline": {
                "type": "string",
                "enum": ["zimage", "flux2-klein", "lens", "auto"],
                "description": "MLX pipeline family (default zimage).",
            },
            "cfg_scale": {"type": "number", "description": "Classifier-free guidance (opt-in; pipeline-dependent)."},
            # Edit-capable inputs — presence of `image`/`image_path` also makes
            # image_selector's _filter_candidates pick mlx_image for edit mode.
            "image": {"type": "string", "description": "Source image path for i2i / controlnet edit."},
            "image_path": {"type": "string", "description": "Alias of `image` (source image path)."},
            "reference_image": {
                "type": "string",
                "description": "Optional reference image for i2i pose/style conditioning.",
            },
            "denoise_strength": {
                "type": "number",
                "description": "i2i denoise strength (0–1; higher = more change).",
            },
            "controlnet_type": {
                "type": "string",
                "description": "ControlNet conditioning type (e.g. 'pose'). Forces the controlnet action.",
            },
            "controlnet_strength": {"type": "number", "description": "ControlNet strength (0–1)."},
            "face": {"type": "string", "description": "Face/head source image for faceswap (with `image` = body)."},
            "face_mode": {
                "type": "string",
                "enum": ["face", "head"],
                "description": "faceswap mode: 'face' (face only) or 'head' (head + hair).",
            },
            "lora_path": {
                "type": "array",
                "items": {"type": "string"},
                "description": "LoRA .safetensors path(s). Repeatable; paired with lora_scale.",
            },
            "lora_scale": {
                "type": "array",
                "items": {"type": "number"},
                "description": "LoRA scale per lora_path entry (same order).",
            },
            "output_path": {"type": "string", "description": "Where to save the generated image."},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=12000, vram_mb=0, disk_mb=500, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["prompt", "width", "height", "steps", "seed", "pipeline"]
    side_effects = ["spawns python/venv/bin/python run.py image …", "writes image file to output_path"]
    user_visible_verification = ["Inspect generated image for quality and prompt adherence."]

    # ------------------------------------------------------------------
    # Environment + availability
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_env() -> dict[str, Any]:
        """Resolve MLX repo dir + venv interpreter + presence flags.

        Delegates to the shared ``tools/_mlx/env.py`` resolver (need_models=True
        — image generation needs the mlx-models stack + Apple Silicon). Returns
        a dict with: mlx_dir, run_py, venv_python, arm64, ok (bool), reason (str
        when not ok). Pure filesystem checks — no subprocess spawn.
        """
        return resolve_mlx_env(need_models=True)

    def get_status(self) -> ToolStatus:
        env = self._resolve_env()
        return ToolStatus.AVAILABLE if env["ok"] else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Z-Image ~1.5s/step @ 9 steps; Flux2 Klein ~10s/step @ 4 steps; Lens ~0.4s/step.
        steps = inputs.get("steps")
        pipeline = inputs.get("pipeline", "zimage")
        if steps is None:
            steps = {"zimage": 9, "flux2-klein": 4, "lens": 20, "auto": 9}.get(pipeline, 9)
        per_step = {"flux2-klein": 10.0, "lens": 0.4}.get(pipeline, 1.5)
        return float(steps) * per_step

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        env = self._resolve_env()
        info["mlx_env"] = {
            "configured": env["ok"],
            "reason": env.get("reason"),
            "arm64": env.get("arm64"),
            "mlx_dir": env.get("mlx_dir"),
            "venv_python": env.get("venv_python"),
        }
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

        action, action_args = self._resolve_action(inputs)
        cmd = [venv_python, run_py, "image", action]

        try:
            cmd.extend(self._build_args(inputs, action_args))
        except _BadInput as exc:
            return ToolResult(success=False, error=str(exc))

        # Force a deterministic output dir + JSON summary so we can locate the result.
        out_dir = tempfile.mkdtemp(prefix="mlx_image_")
        cmd.extend(["--gen-output-dir", out_dir, "--json-summary"])

        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=900,
                check=False,
            )
        except subprocess.TimeoutExpired:
            shutil.rmtree(out_dir, ignore_errors=True)
            return ToolResult(success=False, error="MLX image generation timed out (>900s).")
        except Exception as exc:  # pragma: no cover — defensive
            shutil.rmtree(out_dir, ignore_errors=True)
            return ToolResult(success=False, error=f"Failed to spawn MLX runtime: {exc}")

        elapsed = round(time.time() - start, 2)

        if proc.returncode != 0:
            shutil.rmtree(out_dir, ignore_errors=True)
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
            return ToolResult(
                success=False,
                error=f"run.py exited {proc.returncode}:\n" + "\n".join(tail),
            )

        outputs = self._parse_outputs(proc.stdout, out_dir)
        if not outputs:
            shutil.rmtree(out_dir, ignore_errors=True)
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
            return ToolResult(
                success=False,
                error="run.py produced no image output:\n" + "\n".join(tail),
            )

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
        model = self._model_label(inputs)

        return ToolResult(
            success=True,
            data={
                "provider": "mlx",
                "model": model,
                "prompt": inputs["prompt"],
                "pipeline": inputs.get("pipeline", "zimage"),
                "action": action,
                "width": inputs.get("width"),
                "height": inputs.get("height"),
                "steps": inputs.get("steps"),
                "seed": seed,
                "output": str(final_path),
                "format": final_path.suffix.lstrip(".") or "png",
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
        seed = inputs.get("seed")
        if isinstance(seed, int):
            return seed
        return 777  # run.py default (app/commands/_shared.py:296)

    @staticmethod
    def _model_label(inputs: dict[str, Any]) -> str:
        pipeline = inputs.get("pipeline", "zimage")
        transformer = inputs.get("transformer")
        if transformer:
            return f"mlx-{pipeline}/{transformer}"
        return f"mlx-{pipeline}"

    @staticmethod
    def _resolve_action(inputs: dict[str, Any]) -> tuple[str, list[str]]:
        """Decide the run.py image action + any action-only flags.

        faceswap wins if both a body image and a face image are present;
        else controlnet if a controlnet_type / controlnet source is set;
        else i2i if any source image is present; else t2i.
        """
        body_image = inputs.get("image") or inputs.get("image_path")
        face_image = inputs.get("face")

        if body_image and face_image:
            return "faceswap", []
        if inputs.get("controlnet_type") or inputs.get("controlnet_strength") is not None:
            return "controlnet", []
        if body_image:
            return "i2i", []
        return "t2i", []

    @staticmethod
    def _build_args(inputs: dict[str, Any], action_args: list[str]) -> list[str]:
        """Map provider inputs to run.py CLI flags. Raises _BadInput on bad values."""
        out: list[str] = []
        prompt = inputs.get("prompt")
        if not prompt:
            raise _BadInput("prompt is required.")
        out += ["--prompt", str(prompt)]

        for key, flag, cast in (
            ("width", "--width", int),
            ("height", "--height", int),
            ("steps", "--steps", int),
            ("seed", "--seed", int),
            ("resolution", "--resolution", str),
            ("pipeline", "--pipeline", str),
            ("cfg_scale", "--cfg-scale", float),
            ("denoise_strength", "--denoise-strength", float),
            ("controlnet_strength", "--controlnet-strength", float),
        ):
            if inputs.get(key) is not None:
                out += [flag, str(cast(inputs[key]))]  # type: ignore[call-arg]

        if inputs.get("controlnet_type"):
            out += ["--controlnet-type", str(inputs["controlnet_type"])]

        body_image = inputs.get("image") or inputs.get("image_path")
        face_image = inputs.get("face")
        action, _ = MLXImage._resolve_action(inputs)

        if action == "faceswap":
            if not (body_image and face_image):
                raise _BadInput("faceswap requires both a body image (`image`) and a `face` source.")
            out += ["--input", str(body_image), "--face", str(face_image)]
            if inputs.get("face_mode"):
                out += ["--mode", str(inputs["face_mode"])]
        elif action in ("i2i", "controlnet"):
            if not body_image:
                raise _BadInput(f"{action} requires a source image (`image` or `image_path`).")
            # run.py i2i/controlnet use --input-image (NOT --input).
            out += ["--input-image", str(body_image)]
            if inputs.get("reference_image"):
                out += ["--reference-image", str(inputs["reference_image"])]

        # LoRA: --lora-path is repeatable, paired with --lora-scale (same order).
        lora_paths = inputs.get("lora_path") or []
        lora_scales = inputs.get("lora_scale") or []
        if lora_paths:
            if isinstance(lora_paths, str):
                lora_paths = [lora_paths]
            if isinstance(lora_scales, (int, float)):
                lora_scales = [float(lora_scales)]
            if len(lora_scales) and len(lora_scales) != len(lora_paths):
                raise _BadInput("lora_scale must have one entry per lora_path (or be omitted).")
            for i, lp in enumerate(lora_paths):
                out += ["--lora-path", str(lp)]
                if i < len(lora_scales):
                    out += ["--lora-scale", str(lora_scales[i])]

        out += action_args
        return out

    # ------------------------------------------------------------------
    # Output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_outputs(stdout: str, out_dir: str) -> list[str]:
        """Prefer the JSON_SUMMARY line; fall back to scanning the output dir."""
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
        # Fallback: newest image under the gen-output-dir.
        candidates: list[Path] = []
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            candidates.extend(Path(out_dir).glob(ext))
        candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [str(p) for p in candidates]


class _BadInput(Exception):
    """Raised when provider inputs cannot map cleanly to run.py flags."""
