"""Qwen3 TTS provider tool — local user-installed model via system Python.

Runs in the user's global Python (3.14 / `/opt/homebrew/bin/python3.14`)
because `qwen-tts` is installed there (not in OpenMontage's .venv).
The tool calls the system Python via subprocess to run inference,
mirroring how PiperTTS shells out to the `piper` binary.

Three inference modes from qwen_tts.Qwen3TTSModel:
  - custom_voice  : direct text→audio via stock voice
  - voice_clone   : reference audio sample drives the clone
  - voice_design  : natural-language voice description

Default mode here is `custom_voice` (simplest path).

User added 2026-05-07 per service-offering setup.
"""

from __future__ import annotations

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


SYSTEM_PYTHON = "/opt/homebrew/bin/python3.14"
DEFAULT_CHECKPOINT = "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice"


# Inline runner — keeps qwen3 inference code in one place, no separate file.
# This is a Python source string that the tool subprocess-executes via
# `python3.14 -c <code>` so it runs in the user's global env where qwen_tts
# is installed.
_RUNNER_SCRIPT = r"""
import sys
import json

cfg = json.loads(sys.argv[1])

text = cfg["text"]
output_path = cfg["output_path"]
checkpoint = cfg.get("checkpoint", "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice")
mode = cfg.get("mode", "custom_voice")
speaker = cfg.get("speaker")
voice_description = cfg.get("voice_description")
ref_audio = cfg.get("reference_audio_path")
device = cfg.get("device", "cpu")
dtype = cfg.get("dtype", "float32")

try:
    from qwen_tts import Qwen3TTSModel
except ImportError as e:
    print(json.dumps({"ok": False, "error": f"qwen_tts not importable: {e}"}))
    sys.exit(1)

try:
    model = Qwen3TTSModel.from_pretrained(checkpoint, device=device, dtype=dtype)
except Exception as e:
    print(json.dumps({"ok": False, "error": f"model load failed: {e}"}))
    sys.exit(1)

try:
    if mode == "voice_design":
        if not voice_description:
            raise ValueError("voice_design mode needs `voice_description`")
        wav = model.generate_voice_design(text=text, voice_description=voice_description)
    elif mode == "voice_clone":
        if not ref_audio:
            raise ValueError("voice_clone mode needs `reference_audio_path`")
        wav = model.generate_voice_clone(text=text, reference_audio=ref_audio)
    else:
        # custom_voice (default)
        kwargs = {"text": text}
        if speaker is not None:
            kwargs["speaker"] = speaker
        wav = model.generate_custom_voice(**kwargs)
except Exception as e:
    print(json.dumps({"ok": False, "error": f"inference failed: {e}"}))
    sys.exit(1)

# `wav` is expected to be (audio_tensor, sample_rate) or similar — coerce to (samples, sr)
import torch, numpy as np, soundfile as sf
samples, sr = None, None
if isinstance(wav, tuple) and len(wav) == 2:
    samples, sr = wav
elif hasattr(wav, "audio") and hasattr(wav, "sample_rate"):
    samples, sr = wav.audio, wav.sample_rate
else:
    print(json.dumps({"ok": False, "error": f"unexpected output shape: {type(wav)}"}))
    sys.exit(1)

if isinstance(samples, torch.Tensor):
    samples = samples.detach().cpu().float().numpy()
samples = np.asarray(samples).squeeze()

sf.write(output_path, samples, sr)
print(json.dumps({"ok": True, "output_path": output_path, "sample_rate": int(sr), "duration_s": len(samples)/sr}))
"""


class Qwen3TTS(BaseTool):
    name = "qwen3_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "qwen"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC  # voice design / clone is non-deterministic
    runtime = ToolRuntime.LOCAL

    dependencies = [
        "binary:/opt/homebrew/bin/python3.14",
        "package:qwen_tts (in system Python)",
        "package:soundfile (in system Python)",
        "package:torch (in system Python)",
    ]
    install_instructions = (
        "Qwen3 TTS runs in the user's GLOBAL Python (system /opt/homebrew/bin/python3.14),\n"
        "not OpenMontage's .venv. To install on the system Python:\n"
        "  /opt/homebrew/bin/python3.14 -m pip install qwen-tts soundfile torch\n"
        "First run downloads the checkpoint (~1-2 GB) from Hugging Face."
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "voice_cloning",        # generate_voice_clone
        "voice_design",         # generate_voice_design (natural-language description)
        "offline_generation",
        "multilingual",
    ]
    supports = {
        "voice_cloning": True,
        "multilingual": True,
        "offline": True,
        "native_audio": True,
    }
    best_for = [
        "user-preferred local TTS (memory: feedback_tts_qwen3_only.md)",
        "voice clone from a 3-30 second reference clip",
        "custom voice design via natural-language description",
        "premium-quality narration without paid API",
    ]
    not_good_for = [
        "real-time low-latency (cold start ~30s for first inference)",
        "machines without 4+ GB RAM (model is large)",
        "GPU-less environments without `bfloat16` support (slow on CPU)",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Text to synthesize (≤ ~500 chars per call recommended)"},
            "output_path": {"type": "string", "default": "qwen3_tts_output.wav"},
            "checkpoint": {
                "type": "string",
                "enum": [
                    "Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice",
                    "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign",
                    "Qwen/Qwen3-TTS-12Hz-1.7B-Base",
                ],
                "default": DEFAULT_CHECKPOINT,
            },
            "mode": {
                "type": "string",
                "enum": ["custom_voice", "voice_clone", "voice_design"],
                "default": "custom_voice",
            },
            "speaker": {
                "type": "string",
                "description": "(custom_voice mode) Stock speaker ID — see Qwen3TTSModel.get_supported_speakers()",
            },
            "voice_description": {
                "type": "string",
                "description": "(voice_design mode) Natural-language voice description, e.g. 'warm female voice in her 20s, slightly breathy, conversational pace'",
            },
            "reference_audio_path": {
                "type": "string",
                "description": "(voice_clone mode) Local path to 3-30s reference WAV/MP3 clip",
            },
            "device": {"type": "string", "default": "cpu", "enum": ["cpu", "cuda:0", "mps"]},
            "dtype": {"type": "string", "default": "float32", "enum": ["float32", "bfloat16", "float16"]},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=4096, vram_mb=2048, disk_mb=2048, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=[])
    idempotency_key_fields = ["text", "checkpoint", "mode", "speaker", "voice_description"]
    side_effects = ["writes audio file to output_path", "downloads ~2GB checkpoint on first run"]
    user_visible_verification = ["Listen to generated audio for naturalness + correct prosody"]

    # ── Status check ────────────────────────────────────────────────

    def get_status(self) -> ToolStatus:
        if not shutil.which(SYSTEM_PYTHON):
            return ToolStatus.UNAVAILABLE
        # Check qwen_tts module is importable in system python
        try:
            proc = subprocess.run(
                [SYSTEM_PYTHON, "-c", "import qwen_tts; import soundfile; import torch; print('ok')"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if proc.returncode == 0 and "ok" in proc.stdout:
                return ToolStatus.AVAILABLE
            return ToolStatus.UNAVAILABLE
        except Exception:
            return ToolStatus.UNAVAILABLE

    # ── Cost ────────────────────────────────────────────────────────

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0  # local

    # ── Execute ─────────────────────────────────────────────────────

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="Qwen3 TTS not available. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Qwen3 TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        import json

        output_path = Path(inputs.get("output_path", "qwen3_tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cfg = {
            "text": inputs["text"],
            "output_path": str(output_path),
            "checkpoint": inputs.get("checkpoint", DEFAULT_CHECKPOINT),
            "mode": inputs.get("mode", "custom_voice"),
            "speaker": inputs.get("speaker"),
            "voice_description": inputs.get("voice_description"),
            "reference_audio_path": inputs.get("reference_audio_path"),
            "device": inputs.get("device", "cpu"),
            "dtype": inputs.get("dtype", "float32"),
        }

        proc = subprocess.run(
            [SYSTEM_PYTHON, "-c", _RUNNER_SCRIPT, json.dumps(cfg)],
            capture_output=True,
            text=True,
            timeout=600,  # First inference can take 30-60s for model load
        )

        if proc.returncode != 0:
            return ToolResult(
                success=False,
                error=f"Qwen3 subprocess failed (exit {proc.returncode}): {proc.stderr[-500:]}",
            )

        # Last line of stdout should be the JSON status
        stdout = proc.stdout.strip().splitlines()
        if not stdout:
            return ToolResult(success=False, error="Qwen3 returned empty stdout")
        try:
            status = json.loads(stdout[-1])
        except json.JSONDecodeError:
            return ToolResult(success=False, error=f"Qwen3 returned non-JSON: {stdout[-1][:200]}")

        if not status.get("ok"):
            return ToolResult(success=False, error=f"Qwen3 inference: {status.get('error')}")

        if not output_path.exists():
            return ToolResult(success=False, error=f"Qwen3 output file missing: {output_path}")

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": cfg["checkpoint"],
                "mode": cfg["mode"],
                "text_length": len(inputs["text"]),
                "output": str(output_path),
                "format": "wav",
                "sample_rate": status.get("sample_rate"),
                "duration_s": status.get("duration_s"),
            },
            artifacts=[str(output_path)],
            model=cfg["checkpoint"],
        )
