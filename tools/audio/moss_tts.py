"""MOSS-TTS MLX local text-to-speech provider tool."""

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
# Nano first: 16GB unified memory cannot hold the 8B variant + codec without
# swapping (LLM 9.7GiB + codec 6.6GiB > 16GB). Nano needs only ~0.4GiB.
# The 8B dir stays available via explicit inputs["model_path"].
# MOSS_TTS_MODEL_DIR overrides the search for custom layouts.
_MODEL_DIRS = [
    _PROJECT_ROOT / "moss-tts-mlx" / "moss-tts-nano",
]

# Inner generation script. Receives inputs as JSON via MOSS_TTS_INPUTS env var,
# so arbitrary text (quotes, newlines, unicode) cannot break the script.
_GENERATE_SCRIPT = r"""
import json, os
from pathlib import Path

inputs = json.loads(os.environ["MOSS_TTS_INPUTS"])

from mlx_audio.tts.generate import load_model, generate_audio

model = load_model(inputs["model_path"])

gen_kwargs = dict(
    text=inputs["text"],
    model=model,
    ref_audio=inputs["ref_audio"],
    ref_text=inputs["ref_text"],
    stt_model=None,  # never trigger Whisper download; ref_text is always provided
    output_path=inputs["work_dir"],
    file_prefix="moss",
    audio_format="wav",
    join_audio=True,
    max_tokens=inputs["max_tokens"],
    temperature=inputs["temperature"],
    lang_code=inputs["lang_code"],
    verbose=True,
)
# Optional liveliness knobs forwarded to the model (audio_* params of MOSS-Nano)
for key in ("top_p", "top_k", "text_temperature", "audio_temperature",
            "audio_top_p", "audio_repetition_penalty"):
    if inputs.get(key) is not None:
        gen_kwargs[key] = inputs[key]

generate_audio(**gen_kwargs)

expected = Path(inputs["work_dir"]) / "moss.wav"
if not expected.exists():
    # Fall back to first segment file (non-joined path)
    candidates = sorted(Path(inputs["work_dir"]).glob("moss*.wav"))
    if not candidates:
        raise SystemExit("MOSS-TTS produced no output audio")
    expected = candidates[0]
print("MOSS_OUTPUT=" + str(expected))
"""


class MossTTS(BaseTool):
    name = "moss_tts"
    version = "0.3.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "moss"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL  # Apple Silicon MLX unified memory, no API

    dependencies = ["cmd:python3", "pip:mlx-audio"]
    install_instructions = (
        "Install MOSS-TTS MLX:\n"
        "  bash scripts/setup_moss_tts.sh\n"
        "Or manually:\n"
        "  pip install 'mlx-audio[tts]'\n"
        "  bash scripts/setup_moss_tts.sh  (downloads Nano LLM + codec via aria2c)"
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_cloning",
        "offline_generation",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": True,
        "native_audio": True,
    }
    best_for = [
        "high-quality voice cloning",
        "multilingual narration",
        "Apple Silicon local TTS",
    ]
    not_good_for = [
        "real-time streaming (use MOSS-TTS-Realtime)",
        "non-Apple-Silicon systems (use MOSS-TTS-Nano)",
    ]

    input_schema = {
        "type": "object",
        "required": ["text", "ref_audio"],
        "properties": {
            "text": {"type": "string"},
            "ref_audio": {
                "type": "string",
                "description": "Reference audio file for voice cloning (3-10s WAV/MP3 recommended)",
            },
            "ref_text": {
                "type": "string",
                "description": "Transcript of ref_audio. If omitted, transcribed locally via faster-whisper.",
            },
            "output_path": {"type": "string"},
            "model_path": {"type": "string"},
            "max_tokens": {
                "type": "integer",
                "default": 1200,
                "description": "Generation token ceiling",
            },
            "temperature": {
                "type": "number",
                "default": 0.8,
                "description": "audio_temperature — higher (0.9-1.0) = livelier, 0.7 = flatter",
            },
            "top_p": {"type": "number", "default": 0.95},
            "text_temperature": {
                "type": "number",
                "description": "Prosody planning temperature (default 1.0)",
            },
            "audio_temperature": {
                "type": "number",
                "description": "Overrides temperature if set",
            },
            "audio_repetition_penalty": {
                "type": "number",
                "description": "Lower (1.0-1.1) = more variation (default 1.2)",
            },
            "lang_code": {"type": "string", "default": "en"},
            "seed": {"type": "integer", "default": 42},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=2048, vram_mb=0, disk_mb=1024, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["timeout"])
    idempotency_key_fields = ["text", "ref_audio", "seed", "temperature"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for voice match"]

    def _resolve_model_dir(self) -> Path | None:
        search_dirs = list(_MODEL_DIRS)
        env_dir = os.environ.get("MOSS_TTS_MODEL_DIR")
        if env_dir:
            search_dirs.insert(0, Path(env_dir))
        for d in search_dirs:
            if (d / "config.json").exists() and any(d.glob("*.safetensors")):
                return d
        return None

    def get_status(self) -> ToolStatus:
        model_dir = self._resolve_model_dir()
        if model_dir is None:
            return ToolStatus.UNAVAILABLE
        # Codec (audio tokenizer) must be local too, otherwise generation
        # would try to download it from HuggingFace and hang.
        tok = model_dir / "audio_tokenizer"
        if not ((tok / "config.json").exists() and any(tok.glob("model-*.safetensors"))):
            return ToolStatus.UNAVAILABLE
        # aria2c leaves .aria2 control files behind until a download completes;
        # treat in-progress downloads as unavailable.
        if any(model_dir.glob("*.aria2")) or any(tok.glob("*.aria2")):
            return ToolStatus.UNAVAILABLE
        return ToolStatus.AVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # Local inference, no cost

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error=(
                    "MOSS-TTS model or audio tokenizer not found locally. "
                    "Run: bash scripts/setup_moss_tts.sh"
                ),
            )

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"MOSS-TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _transcribe_reference(self, ref_audio: str) -> str:
        """Transcribe ref_audio with the project's local faster-whisper tool."""
        from tools.analysis.transcriber import Transcriber

        result = Transcriber().execute(
            {"input_path": ref_audio, "model_size": "base"}
        )
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
        if not ref_audio or not Path(ref_audio).exists():
            return ToolResult(
                success=False, error=f"Reference audio not found: {ref_audio}"
            )

        model_dir = self._resolve_model_dir()
        model_path = inputs.get("model_path") or str(model_dir)

        ref_text = inputs.get("ref_text")
        if not ref_text:
            ref_text = self._transcribe_reference(str(Path(ref_audio).resolve()))

        output_path = Path(inputs.get("output_path", "moss_tts_output.wav")).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "model_path": model_path,
            "text": inputs["text"],
            "ref_audio": str(Path(ref_audio).resolve()),
            "ref_text": ref_text,
            "max_tokens": int(inputs.get("max_tokens", 1200)),
            "temperature": float(inputs.get("temperature", 0.8)),
            "lang_code": inputs.get("lang_code", "en"),
        }
        # Optional sampling knobs (None values are not forwarded)
        for key in ("top_p", "top_k", "text_temperature", "audio_temperature",
                    "audio_top_p", "audio_repetition_penalty"):
            if inputs.get(key) is not None:
                payload[key] = inputs[key]

        with tempfile.TemporaryDirectory(prefix="moss_tts_") as work_dir:
            payload["work_dir"] = work_dir

            env = os.environ.copy()
            env["MOSS_TTS_INPUTS"] = json.dumps(payload)
            # Hard offline: fail fast instead of hanging on HuggingFace downloads.
            env["HF_HUB_OFFLINE"] = "1"
            env["TRANSFORMERS_OFFLINE"] = "1"
            env.setdefault("OMP_NUM_THREADS", "4")

            with tempfile.NamedTemporaryFile(
                "w", suffix="_moss_generate.py", delete=False
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
                    error=f"MOSS-TTS failed (exit {proc.returncode}): {proc.stderr[-2000:]}",
                )

            produced = None
            for line in proc.stdout.splitlines():
                if line.startswith("MOSS_OUTPUT="):
                    produced = line.split("=", 1)[1]
            if not produced or not Path(produced).exists():
                return ToolResult(
                    success=False,
                    error=f"MOSS-TTS output missing. stderr: {proc.stderr[-1000:]}",
                )

            shutil.move(str(produced), str(output_path))

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": Path(model_path).name,
                "ref_audio": str(ref_audio),
                "ref_text": ref_text,
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
                "seed": inputs.get("seed", 42),
            },
            artifacts=[str(output_path)],
            model=Path(model_path).name,
        )
