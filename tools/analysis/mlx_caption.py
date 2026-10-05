"""MLX image/video understanding via the sibling ``mlx-movie-director`` runtime.

Bridges OpenMontage's ``analysis`` capability to the local VLM served by LM
Studio (Qwen3-VL 4B by default), invoked through ``python/mlx-movie-director/
run.py caption``. This is the analysis analog of ``mlx_image`` / ``mlx_video``:
the third leg of the MLX-runtime trio (image gen + video gen + VLM analysis),
all talking to the same Apple-Silicon-native runtime.

Why this provider exists alongside ``video_understand`` (also a local VLM):
``video_understand`` drives a HuggingFace ``transformers`` VLM directly (needs a
downloaded model + GPU/torch). ``mlx_caption`` talks to an *already-running* LM
Studio server loading an MLX-quantized model — the same server the
mlx-movie-director runtime itself uses, so a production Apple-Silicon box that
serves ``mlx_image``/``mlx_video`` already has it up. It is the $0, offline,
private, no-extra-download vision path.

Contract (mirrors mlx_image/mlx_video — env resolution is shared via
``tools/_mlx/env.py``):

* ``MLX_MOVIE_DIRECTOR_DIR``  — repo root containing ``python/mlx-movie-director/run.py``.
* ``MLX_VENV_PYTHON``         — the MLX venv interpreter.
* LM Studio reachable at ``http://localhost:1234/v1`` with a vision model loaded
  (e.g. Qwen3-VL 4B). The availability gate socket-probes this port.

run.py writes the caption to a JSON file (``--output``) with a ``styles`` map —
one entry per requested style (e.g. ``photography``, ``score``,
``video_analysis``). We surface that map verbatim plus a joined ``text`` field.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from tools._mlx.env import LM_STUDIO_URL, resolve_mlx_env
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

# Styles accepted by `run.py caption --style` (see app/commands/caption.py
# _STYLE_PROMPTS). Kept as a closed enum so the selector + caller see a stable
# surface; run.py itself is the authority (it rejects unknown styles).
_CAPTION_STYLES = (
    "t2i",
    "photography",
    "profile",
    "style",
    "score",
    "video_score",
    "video_analysis",
    "compare",
    "review",
    "playwright",
    "lora_quality",
    "ltx_i2v",
    "pose_dsg",
)
_LANGS = ("en", "zh_TW", "ja")


class MLXCaption(BaseTool):
    name = "mlx_caption"
    version = "0.1.0"
    tier = ToolTier.ANALYZE
    capability = "analysis"
    provider = "mlx"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC  # VLM at temp 0 is effectively deterministic
    runtime = ToolRuntime.LOCAL_GPU  # the VLM runs on-GPU via the LM Studio server

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
        "Then start LM Studio, load a vision model (e.g. Qwen3-VL 4B), and "
        "enable its local server (default http://localhost:1234/v1).\n"
        "Requires Apple Silicon (arm64) for the mlx-movie-director runtime."
    )
    agent_skills = ["mlx-movie-director"]

    capabilities = [
        "image_understanding",
        "video_understanding",
        "quality_scoring",
        "vision",
    ]
    # The analysis-tier analog of mlx_image's control surface: the only provider
    # that serves vision understanding from an already-running local LM Studio
    # (video_understand downloads + loads a transformers model each run).
    supports = {
        "offline": True,
        "local": True,
        "vision": True,
        "image_understanding": True,
        "video_understanding": True,
        "quality_scoring": True,
    }
    best_for = [
        "local, $0, private image/video understanding via LM Studio (Qwen3-VL)",
        "VLM quality scoring of generated frames (style 'score' / 'video_score')",
        "scene/shot analysis for automated review (style 'video_analysis')",
        "describing a reference image to seed a t2i/i2v prompt (style 't2i'/'photography')",
    ]
    not_good_for = [
        "hosts without LM Studio running a vision model",
        "setups without the MLX venv recreated (see install_instructions)",
    ]
    fallback = "video_understand"
    fallback_tools = ["video_understand", "visual_qa"]

    input_schema = {
        "type": "object",
        "required": ["image"],
        "properties": {
            "image": {
                "type": "string",
                "description": "Path to the image (or video) to analyze.",
            },
            "style": {
                "anyOf": [
                    {"type": "string", "enum": list(_CAPTION_STYLES)},
                    {"type": "array", "items": {"type": "string", "enum": list(_CAPTION_STYLES)}},
                ],
                "description": (
                    "Caption style(s). run.py accepts one OR MORE. Common: "
                    "'photography' (art-style desc), 't2i' (prompt-ready desc), "
                    "'score'/'video_score' (quality score), 'video_analysis', "
                    "'review'. Default 'photography'."
                ),
            },
            "lang": {
                "type": "string",
                "enum": list(_LANGS),
                "description": "Output language (default 'en').",
            },
            "model": {
                "type": "string",
                "description": "Override the LM Studio vision model id (default: server-loaded).",
            },
            "api_url": {
                "type": "string",
                "description": f"Override the LM Studio OpenAI-compatible endpoint (default {LM_STUDIO_URL}).",
            },
            "output_path": {
                "type": "string",
                "description": "Where to save the caption JSON (default: a temp file, returned in data).",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=4000, vram_mb=0, disk_mb=100, network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["image", "style", "lang", "model"]
    side_effects = ["spawns python/venv/bin/python run.py caption …", "writes caption JSON"]
    user_visible_verification = ["Inspect the returned caption text for accuracy."]

    # ------------------------------------------------------------------
    # Environment + availability
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_env() -> dict[str, Any]:
        """Resolve MLX runtime + LM Studio reachability.

        Delegates to ``tools/_mlx/env.py`` with need_models=False (caption talks
        to LM Studio, not the mlx-models generation stack) and need_lm_studio=True
        (socket-probes localhost:1234).
        """
        return resolve_mlx_env(need_models=False, need_lm_studio=True)

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._resolve_env()["ok"] else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # Qwen3-VL 4B caption: ~3-8s for an image, ~10-25s for a video sample.
        image = str(inputs.get("image", ""))
        return 20.0 if any(image.lower().endswith(ext) for ext in (".mp4", ".mov", ".webm", ".gif")) else 6.0

    def get_info(self) -> dict[str, Any]:
        info = super().get_info()
        env = self._resolve_env()
        info["mlx_env"] = {
            "configured": env["ok"],
            "reason": env.get("reason"),
            "arm64": env.get("arm64"),
            "mlx_dir": env.get("mlx_dir"),
            "venv_python": env.get("venv_python"),
            "lm_studio_url": LM_STUDIO_URL,
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

        image = inputs.get("image")
        if not image:
            return ToolResult(success=False, error="image is required.")
        image_path = Path(os.path.expanduser(str(image)))
        if not image_path.is_file():
            return ToolResult(success=False, error=f"image not found: {image}")

        cmd: list[str] = [venv_python, run_py, "caption", str(image_path)]
        cmd += self._build_args(inputs)

        # Deterministic output path so we can read the result back.
        out_json = tempfile.NamedTemporaryFile(
            prefix="mlx_caption_", suffix=".json", delete=False
        )
        out_json.close()
        cmd += ["--output", out_json.name]

        start = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
        except subprocess.TimeoutExpired:
            os.unlink(out_json.name)
            return ToolResult(success=False, error="MLX caption timed out (>300s).")
        except Exception as exc:  # pragma: no cover — defensive
            os.unlink(out_json.name)
            return ToolResult(success=False, error=f"Failed to spawn MLX runtime: {exc}")

        elapsed = round(time.time() - start, 2)

        if proc.returncode != 0:
            os.unlink(out_json.name)
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
            return ToolResult(
                success=False,
                error=f"run.py caption exited {proc.returncode}:\n" + "\n".join(tail),
            )

        styles_map, joined_text = self._parse_output(out_json.name)
        if not styles_map:
            os.unlink(out_json.name)
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-12:]
            return ToolResult(
                success=False,
                error="run.py caption produced no caption output:\n" + "\n".join(tail),
            )

        # Persist to a caller-chosen path if requested.
        final_json = out_json.name
        output_path = inputs.get("output_path")
        if output_path:
            dest = Path(output_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.resolve() != Path(final_json).resolve():
                shutil.copy2(final_json, dest)
            os.unlink(final_json)
            final_json = str(dest)
        else:
            # Keep the temp file only if no explicit destination; unlink the temp
            # handle but leave the JSON on disk under output_path semantics.
            # (Caller gets the full map via data, so the temp file is redundant.)
            os.unlink(final_json)
            final_json = ""

        model = inputs.get("model") or "qwen3-vl (lm-studio)"
        return ToolResult(
            success=True,
            data={
                "provider": "mlx",
                "model": model,
                "image": str(image_path),
                "styles": styles_map,
                "text": joined_text,
                "lang": inputs.get("lang", "en"),
                "lm_studio_url": inputs.get("api_url", LM_STUDIO_URL),
            },
            artifacts=[final_json] if final_json else [],
            cost_usd=0.0,
            duration_seconds=elapsed,
            model=model,
        )

    # ------------------------------------------------------------------
    # Argument mapping + output parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _build_args(inputs: dict[str, Any]) -> list[str]:
        """Map provider inputs to run.py caption CLI flags."""
        out: list[str] = []

        styles = inputs.get("style", "photography")
        if isinstance(styles, str):
            styles = [styles]
        elif not isinstance(styles, list):
            raise _BadInput("style must be a string or array of style strings.")
        if not styles:
            styles = ["photography"]
        # run.py --style is nargs="+": each style as its own token after the flag.
        out += ["--style", *styles]

        if inputs.get("lang"):
            out += ["--lang", str(inputs["lang"])]
        else:
            out += ["--lang", "en"]

        if inputs.get("model"):
            out += ["--model", str(inputs["model"])]
        if inputs.get("api_url"):
            out += ["--api-url", str(inputs["api_url"])]

        return out

    @staticmethod
    def _parse_output(out_json: str) -> tuple[dict[str, Any], str]:
        """Read the caption JSON. Returns (styles_map, joined_plain_text).

        run.py writes a dict with a ``styles`` key (style → text/score). Older
        files may be flat; we normalize both. ``text`` joins the non-score style
        values for callers that just want a single description string.
        """
        try:
            with open(out_json, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            return {}, ""

        styles_map: dict[str, Any]
        if isinstance(payload.get("styles"), dict):
            styles_map = payload["styles"]
        elif isinstance(payload, dict) and all(isinstance(k, str) for k in payload):
            # Flat legacy shape: top-level keys are styles.
            styles_map = payload
        else:
            return {}, ""

        # Join textual styles; skip numeric score-only entries.
        text_parts: list[str] = []
        for _style, value in styles_map.items():
            if isinstance(value, str):
                text_parts.append(value)
            elif isinstance(value, dict) and isinstance(value.get("text"), str):
                text_parts.append(value["text"])
        return styles_map, "\n\n".join(text_parts).strip()


class _BadInput(Exception):
    """Raised when provider inputs cannot map cleanly to run.py flags."""
