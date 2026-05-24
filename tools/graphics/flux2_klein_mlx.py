"""FLUX.2 Klein 9B 8-bit local MLX image generation.

Apple-Silicon-native image generation via Filip Strand's `mflux`
(https://github.com/filipstrand/mflux) — pure MLX, no PyTorch, runs on
M-series unified memory. Substitute for fal.ai FLUX calls when:
  - the prompt is brand-internal (identity-wipe alignment)
  - the tenant wants zero per-image cost
  - the operator is offline / does not want a network roundtrip

Why a separate tool from `flux_image.py`:
  - `flux_image` wraps the fal.ai hosted API (paid, networked).
  - `flux2_klein_mlx` targets the local mflux Python path. M5 Max benchmark
    (2026-05-24): 17.0s end-to-end for 1024x1024 at 8 steps. See
    `~/.claude/skills/flux2-klein-mlx/SKILL.md`.

Important: mflux 0.17.5 has a CLI bug where `mflux-generate-flux2` ignores
`--base-model` when `--model` is a local path; resolution falls back to
`flux2-klein-4b` (24 attention heads) and the 9B weights (32 heads) reshape-
error in the first attention block. This tool bypasses the CLI by invoking
the mflux Python API directly through the Sovereign venv. See `_render_cmd`.

Install path:
  - Apple Silicon (M1+) + macOS 14+
  - Dedicated venv at ~/Library/Application Support/Sovereign/flux2-klein/.venv
    with `mflux` installed (per the SKILL.md install script).
  - Model weights at ~/Library/Application Support/Sovereign/flux2-klein/model-9b-8bit
"""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
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
from tools.dam_hook import DAM_INPUT_SCHEMA_FRAGMENT, maybe_register_artifact


SOVEREIGN_FLUX2_ROOT = Path.home() / "Library/Application Support/Sovereign/flux2-klein"
SOVEREIGN_FLUX2_VENV = SOVEREIGN_FLUX2_ROOT / ".venv"
SOVEREIGN_FLUX2_PY = SOVEREIGN_FLUX2_VENV / "bin" / "python"
SOVEREIGN_FLUX2_MODEL_DIR = SOVEREIGN_FLUX2_ROOT / "model-9b-8bit"


class Flux2KleinMlx(BaseTool):
    name = "flux2_klein_mlx"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
    provider = "mflux"
    stability = ToolStability.BETA
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    install_instructions = (
        "FLUX.2 Klein MLX requires Apple Silicon (M1/M2/M3/M4/M5) + macOS 14+.\n"
        "Bootstrap (one-time, ~17GB model download):\n"
        "  python3.12 -m venv ~/Library/Application\\ Support/Sovereign/flux2-klein/.venv\n"
        "  ~/Library/Application\\ Support/Sovereign/flux2-klein/.venv/bin/pip install mflux\n"
        "  huggingface-cli download lpalbou/flux2-klein-9b-8bit \\\n"
        "    --local-dir ~/Library/Application\\ Support/Sovereign/flux2-klein/model-9b-8bit\n"
        "See ~/.claude/skills/flux2-klein-mlx/SKILL.md for full install + smoke test."
    )
    fallback = "flux_image"
    fallback_tools = ["flux_image", "local_diffusion", "image_selector"]
    agent_skills = ["flux2-klein-mlx", "flux-best-practices"]

    capabilities = ["text_to_image", "generate_image", "offline_image_gen"]
    supports = {
        "negative_prompt": False,  # Klein is distilled; mflux rejects negative_prompt
        "seed": True,
        "custom_size": True,
        "offline": True,
        "local_gpu": True,
        "apple_silicon_only": True,
    }
    best_for = [
        "tenant marketing-sleeve stills (ATX Mats, GLI, GBB, Sovereign Mind, Sovereign Investments)",
        "identity-wipe-aligned workloads where the prompt should not leave the operator's machine",
        "high-volume campaigns where per-image API cost would dominate",
        "iterative prompt exploration without per-call cost",
    ]
    not_good_for = [
        "non-Apple-Silicon hardware (route to flux_image fal.ai path instead)",
        "operators without the ~17GB model on local disk",
        "negative-prompt-driven workflows (Klein does not support them)",
    ]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "width": {"type": "integer", "default": 1024},
            "height": {"type": "integer", "default": 1024},
            "num_inference_steps": {
                "type": "integer",
                "default": 8,
                "description": "Klein-9b is distilled few-step; 4-8 is the canonical range.",
            },
            "seed": {"type": "integer", "default": 42},
            "output_path": {
                "type": "string",
                "description": "Where to write the output PNG. Default: ./flux2_klein_<timestamp>.png",
            },
            **DAM_INPUT_SCHEMA_FRAGMENT,
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=24000, vram_mb=24000, disk_mb=17000, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1)
    idempotency_key_fields = ["prompt", "width", "height", "num_inference_steps", "seed"]
    side_effects = ["writes PNG to output_path", "loads model into unified memory"]
    user_visible_verification = [
        "Inspect generated PNG for prompt adherence, brand alignment, no obvious artifacts",
    ]

    # --------------------------------------------------------------- status

    def get_status(self) -> ToolStatus:
        # Apple Silicon gate
        if platform.system() != "Darwin" or platform.machine() not in ("arm64", "aarch64"):
            return ToolStatus.UNAVAILABLE
        # Sovereign venv + Python interpreter
        if not SOVEREIGN_FLUX2_PY.exists():
            return ToolStatus.UNAVAILABLE
        # Model weights
        if not SOVEREIGN_FLUX2_MODEL_DIR.exists():
            return ToolStatus.UNAVAILABLE
        # mflux importable inside the venv
        try:
            r = subprocess.run(
                [str(SOVEREIGN_FLUX2_PY), "-c", "import mflux"],
                capture_output=True, timeout=10,
            )
            if r.returncode != 0:
                return ToolStatus.UNAVAILABLE
        except Exception:
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        # M5 Max benchmark (2026-05-24): 0.6s load + ~2.0s/step generation
        # plus ~0.5s post-process for save.
        steps = int(inputs.get("num_inference_steps", 8))
        return 1.5 + 2.0 * steps

    # --------------------------------------------------------------- execute

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        status = self.get_status()
        if status != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="flux2_klein_mlx unavailable. " + self.install_instructions)

        prompt = inputs.get("prompt")
        if not prompt:
            return ToolResult(success=False, error="prompt is required")

        width = int(inputs.get("width", 1024))
        height = int(inputs.get("height", 1024))
        steps = int(inputs.get("num_inference_steps", 8))
        seed = int(inputs.get("seed", 42))

        output_path = Path(
            inputs.get("output_path") or f"flux2_klein_{int(time.time())}.png"
        ).expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Render via Sovereign venv's mflux Python API (CLI is broken — see module docstring).
        # We pass a small inline Python program that imports mflux, resolves the
        # config with the explicit `base_model` arg, and runs generation.
        cmd, py_program = self._render_cmd(prompt, width, height, steps, seed, output_path)
        start = time.time()
        try:
            r = subprocess.run(cmd, input=py_program, text=True, capture_output=True, timeout=600)
        except subprocess.TimeoutExpired:
            return ToolResult(success=False, error="flux2_klein_mlx timed out after 600s")
        duration = round(time.time() - start, 2)

        if r.returncode != 0 or not output_path.exists():
            return ToolResult(
                success=False,
                error=f"mflux Python invocation failed (rc={r.returncode}):\nSTDERR: {r.stderr[-2000:]}",
            )

        # Parse the trailing JSON status line we asked the program to print.
        meta: dict[str, Any] = {}
        for line in reversed(r.stdout.strip().splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    meta = json.loads(line)
                except json.JSONDecodeError:
                    pass
                break

        result = ToolResult(
            success=True,
            data={
                "provider": "mflux",
                "model": "flux2-klein-9b-8bit",
                "prompt": prompt,
                "width": width,
                "height": height,
                "num_inference_steps": steps,
                "seed": seed,
                "output": str(output_path),
                "load_s": meta.get("load_s"),
                "gen_s": meta.get("gen_s"),
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=duration,
            seed=seed,
            model="lpalbou/flux2-klein-9b-8bit",
        )
        asset_id = maybe_register_artifact(
            tool_result=result, inputs=inputs, capability=self.capability,
            created_by_tool=self.name, artifact_path=str(output_path),
            width=width, height=height,
        )
        if asset_id:
            result.data["dam_asset_id"] = asset_id
        return result

    # --------------------------------------------------------------- helpers

    def _render_cmd(
        self,
        prompt: str,
        width: int,
        height: int,
        steps: int,
        seed: int,
        output_path: Path,
    ) -> tuple[list[str], str]:
        """Build the (cmd, stdin_program) pair that invokes mflux in the Sovereign venv."""
        # We pipe a small Python program over stdin so the prompt/seed/etc. are
        # delivered as Python literals, not shell-quoted strings.
        prog = f"""
import json, time
from mflux.models.common.config import ModelConfig
from mflux.models.flux2.variants import Flux2Klein
from mflux.utils.image_util import ImageUtil

MODEL_DIR = {str(SOVEREIGN_FLUX2_MODEL_DIR)!r}
cfg = ModelConfig.from_name(model_name=MODEL_DIR, base_model="flux2-klein-9b")
assert cfg.transformer_overrides.get("num_attention_heads") == 32

t0 = time.time()
model = Flux2Klein(quantize=None, model_path=MODEL_DIR, model_config=cfg)
t_load = time.time() - t0

t1 = time.time()
image = model.generate_image(
    seed={seed},
    prompt={prompt!r},
    width={width},
    height={height},
    guidance=1.0,
    num_inference_steps={steps},
    scheduler="flow_match_euler_discrete",
    image_path=None,
    image_strength=None,
)
t_gen = time.time() - t1

ImageUtil.save_image(image=image, path={str(output_path)!r}, export_json_metadata=False)
print(json.dumps({{"load_s": round(t_load, 2), "gen_s": round(t_gen, 2)}}))
"""
        return [str(SOVEREIGN_FLUX2_PY), "-"], prog
