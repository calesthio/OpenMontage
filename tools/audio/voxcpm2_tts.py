"""VoxCPM2 MLX local text-to-speech provider tool.

Diffusion-based voice cloning TTS (OpenBMB VoxCPM2). Preferred local TTS on
16GB Apple Silicon: high Turkish quality, cfg/timestep tuning, style
instructions. Runs fully offline once the model is local.

Tuned defaults proven in the video-gen project A/B tests:
  cfg_value=2.5-3.0, inference_timesteps=40-50.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
# 4bit is the default (better prosody + ~2x faster on 16GB machines);
# bf16 is available for final renders. Both download into models/ via:
#   huggingface-cli download mlx-community/VoxCPM2-4bit --local-dir models/VoxCPM2-4bit
# VOXCPM2_MODEL_DIR overrides the search for custom layouts.
_MODEL_DIRS = [
    _PROJECT_ROOT / "models" / "VoxCPM2-4bit",
    _PROJECT_ROOT / "models" / "VoxCPM2-bf16",
]

# Inner generation script. Inputs arrive as JSON via VOXCPM_INPUTS env var.
_GENERATE_SCRIPT = r"""
import json, os
from pathlib import Path

inputs = json.loads(os.environ["VOXCPM_INPUTS"])

from mlx_audio.tts import load
from mlx_audio.audio_io import write as audio_write
import mlx.core as mx

if inputs.get("seed") is not None:
    mx.random.seed(int(inputs["seed"]))  # seed() sets global PRNG; key() does NOT

model = load(inputs["model_path"])

gen_kwargs = dict(
    text=inputs["text"],
    inference_timesteps=inputs["inference_timesteps"],
    cfg_value=inputs["cfg_value"],
)
if inputs.get("max_tokens"):
    gen_kwargs["max_tokens"] = inputs["max_tokens"]
if inputs.get("instruct"):
    gen_kwargs["instruct"] = inputs["instruct"]
if inputs.get("ref_audio"):
    gen_kwargs["ref_audio"] = inputs["ref_audio"]
    gen_kwargs["ref_text"] = inputs.get("ref_text")

results = model.generate(**gen_kwargs)

out = Path(inputs["work_dir"]) / "voxcpm.wav"
for r in results:
    audio_write(str(out), r.audio, r.sample_rate)
    break  # single result expected for non-streaming
if not out.exists():
    raise SystemExit("VoxCPM2 produced no output audio")
print("VOXCPM_OUTPUT=" + str(out))
"""


class VoxCPM2TTS(BaseTool):
    name = "voxcpm2_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "voxcpm"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL  # Apple Silicon MLX, no API

    dependencies = ["cmd:python3", "pip:mlx-audio"]
    install_instructions = (
        "Install VoxCPM2 MLX:\n"
        "  pip install 'mlx-audio[tts]'\n"
        "  huggingface-cli download mlx-community/VoxCPM2-4bit --local-dir models/VoxCPM2-4bit\n"
        "  (or VoxCPM2-bf16 for final renders; set VOXCPM2_MODEL_DIR to use a custom location)"
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_cloning",
        "style_instructions",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,  # strong TR/EN, see VoxCPM2 language list
        "offline": True,
        "native_audio": True,
        "style_control": True,
    }
    best_for = [
        "high-quality Turkish narration",
        "voice cloning with tuning (cfg/timesteps)",
        "style-controllable speech via instructions",
        "Apple Silicon local TTS",
    ]
    not_good_for = [
        "real-time streaming",
        "machines without Apple Silicon",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "ref_audio": {
                "type": "string",
                "description": "Reference audio for voice cloning (optional; omit for zero-shot/design voice)",
            },
            "ref_text": {
                "type": "string",
                "description": "Transcript of ref_audio. If omitted, transcribed locally via faster-whisper.",
            },
            "instruct": {
                "type": "string",
                "description": "Style instruction (e.g. 'Istanbul agzi ile telaffuz et. Ton: Neseli'). Used when ref_audio is absent.",
            },
            "output_path": {"type": "string"},
            "model_path": {"type": "string"},
            "cfg_value": {
                "type": "number",
                "default": 2.5,
                "description": "Classifier-free guidance. 2.5-3.0 recommended; higher = stronger adherence, possible artifacts",
            },
            "inference_timesteps": {
                "type": "integer",
                "default": 50,
                "description": "Diffusion steps. 40-50 for quality, ~25 for speed",
            },
            "max_tokens": {"type": "integer", "default": 2000},
            "seed": {
                "type": "integer",
                "default": 42,
                "description": "RNG seed for reproducible generation (proven value from video-gen tuning)",
            },
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=6144, vram_mb=0, disk_mb=5120, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["text", "ref_audio", "cfg_value", "inference_timesteps", "seed"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for voice match"]

    def _resolve_model_dir(self) -> Path | None:
        search_dirs = list(_MODEL_DIRS)
        env_dir = os.environ.get("VOXCPM2_MODEL_DIR")
        if env_dir:
            search_dirs.insert(0, Path(env_dir))
        for d in search_dirs:
            if not (d / "config.json").exists():
                continue
            if not any(d.glob("*.safetensors")):
                continue
            # Skip incomplete aria2c downloads (control files present)
            if any(d.glob("*.aria2")):
                continue
            # Sharded models need their index; single-file models don't
            shards = list(d.glob("model-*.safetensors"))
            if shards and not (d / "model.safetensors.index.json").exists():
                continue
            return d
        return None

    def get_status(self) -> ToolStatus:
        return ToolStatus.AVAILABLE if self._resolve_model_dir() else ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Local inference, no cost

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="VoxCPM2 model not found locally. Download mlx-community/VoxCPM2-bf16 or VoxCPM2-4bit into models/",
            )

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"VoxCPM2 generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _transcribe_reference(self, ref_audio: str) -> str:
        """Transcribe ref_audio with the project's local faster-whisper tool."""
        from tools.analysis.transcriber import Transcriber

        result = Transcriber().execute({"input_path": ref_audio, "model_size": "small"})
        if not result.success:
            raise RuntimeError(f"ref_text missing and transcription failed: {result.error}")
        segments = result.data.get("segments", [])
        text = " ".join(s.get("text", "") for s in segments).strip()
        if not text:
            raise RuntimeError(
                "ref_audio transcription came back empty (is the reference valid speech?)"
            )
        return text

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        ref_audio = inputs.get("ref_audio")
        if ref_audio and not Path(ref_audio).exists():
            return ToolResult(success=False, error=f"Reference audio not found: {ref_audio}")

        model_dir = self._resolve_model_dir()
        model_path = inputs.get("model_path") or str(model_dir)

        ref_text = inputs.get("ref_text")
        if ref_audio and not ref_text:
            ref_text = self._transcribe_reference(str(Path(ref_audio).resolve()))

        output_path = Path(inputs.get("output_path", "voxcpm2_output.wav")).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model_path": model_path,
            "text": inputs["text"],
            "cfg_value": float(inputs.get("cfg_value", 2.5)),
            "inference_timesteps": int(inputs.get("inference_timesteps", 50)),
            "max_tokens": int(inputs.get("max_tokens", 2000)),
            "seed": inputs.get("seed", 42),
            "instruct": inputs.get("instruct"),
            "ref_audio": str(Path(ref_audio).resolve()) if ref_audio else None,
            "ref_text": ref_text if ref_audio else None,
        }

        with tempfile.TemporaryDirectory(prefix="voxcpm_") as work_dir:
            payload["work_dir"] = work_dir

            env = os.environ.copy()
            env["VOXCPM_INPUTS"] = json.dumps(payload)
            # Hard offline: fail fast instead of hanging on HuggingFace downloads.
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"

            with tempfile.NamedTemporaryFile(
                "w", suffix="_voxcpm_generate.py", delete=False
            ) as script_file:
                script_file.write(_GENERATE_SCRIPT)
                script_path = script_file.name

            try:
                proc = subprocess.run(
                    [sys.executable, script_path],
                    capture_output=True,
                    text=True,
                    timeout=900,
                    cwd=str(model_dir.parent),
                    env=env,
                )
            finally:
                os.unlink(script_path)

            if proc.returncode != 0:
                return ToolResult(
                    success=False,
                    error=f"VoxCPM2 failed (exit {proc.returncode}): {proc.stderr[-2000:]}",
                )

            produced = None
            for line in proc.stdout.splitlines():
                if line.startswith("VOXCPM_OUTPUT="):
                    produced = line.split("=", 1)[1]
            if not produced or not Path(produced).exists():
                return ToolResult(
                    success=False,
                    error=f"VoxCPM2 output missing. stderr: {proc.stderr[-1000:]}",
                )

            shutil.move(str(produced), str(output_path))

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": Path(model_path).name,
                "ref_audio": str(ref_audio) if ref_audio else None,
                "ref_text": ref_text,
                "cfg_value": payload["cfg_value"],
                "inference_timesteps": payload["inference_timesteps"],
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            model=Path(model_path).name,
        )
