"""Local MusicGen music generation via Hugging Face transformers.

Generates instrumental music from text descriptions using Meta's MusicGen
model (small/medium/large). Runs entirely offline once weights are cached.
"""

from __future__ import annotations

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


class MusicGenLocal(BaseTool):
    name = "musicgen_local"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "musicgen_local"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.SEEDED
    runtime = ToolRuntime.LOCAL_GPU

    dependencies = []  # checked dynamically
    install_instructions = (
        "Install MusicGen dependencies:\n"
        "  pip install transformers torch torchaudio scipy\n"
        "\n"
        "On first run the model weights (~2-5 GB depending on model size)\n"
        "will be downloaded from Hugging Face automatically.\n"
        "\n"
        "Model options:\n"
        "  facebook/musicgen-small   (~2 GB) — fastest, good quality\n"
        "  facebook/musicgen-medium  (~4 GB) — balanced\n"
        "  facebook/musicgen-large   (~6 GB) — best quality\n"
        "  facebook/musicgen-melody  (~4 GB) — supports melody conditioning"
    )
    agent_skills = []

    capabilities = [
        "generate_background_music",
        "generate_instrumental",
        "text_to_music",
        "offline_generation",
    ]
    supports = {
        "offline": True,
        "melody_conditioning": True,
        "duration_control": True,
        "model_size_choice": True,
    }
    best_for = [
        "offline/air-gapped music generation",
        "free music generation (no API cost)",
        "privacy-sensitive workflows",
        "background music for videos without API dependency",
    ]
    not_good_for = [
        "CPU-only machines (very slow, needs GPU)",
        "vocals or lyrics (instrumental only in base model)",
        "real-time generation (takes 10-60s)",
        "sound effects (use a dedicated SFX tool)",
    ]

    fallback_tools = ["music_gen", "pixabay_music", "freesound_music"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text description of the desired music, e.g. 'upbeat electronic dance music with a driving bass line and syncopated drums'",
            },
            "model": {
                "type": "string",
                "default": "facebook/musicgen-small",
                "description": "Hugging Face model ID. Options: facebook/musicgen-small, facebook/musicgen-medium, facebook/musicgen-large, facebook/musicgen-melody",
            },
            "duration_seconds": {
                "type": "integer",
                "default": 15,
                "minimum": 1,
                "maximum": 120,
                "description": "Duration of generated music in seconds",
            },
            "seed": {
                "type": "integer",
                "description": "Random seed for reproducible generation",
            },
            "guidance_scale": {
                "type": "number",
                "default": 3.0,
                "description": "Classifier-free guidance scale. Higher values follow the prompt more closely (3.0 is a good default, try 2.0-7.0)",
            },
            "temperature": {
                "type": "number",
                "default": 1.0,
                "description": "Sampling temperature. Higher = more creative, lower = more conservative",
            },
            "top_k": {
                "type": "integer",
                "default": 250,
                "description": "Top-k sampling parameter",
            },
            "top_p": {
                "type": "number",
                "default": 0.0,
                "description": "Top-p (nucleus) sampling parameter. 0.0 = disabled",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4,
        ram_mb=4000,
        vram_mb=4000,
        disk_mb=6000,
        network_required=False,
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["cuda_oom"])
    idempotency_key_fields = ["prompt", "model", "duration_seconds", "seed", "guidance_scale"]
    side_effects = [
        "writes audio file to output_path",
        "may download model weights on first run (~2-6 GB)",
    ]
    user_visible_verification = [
        "Listen to generated audio for musical coherence and prompt alignment",
    ]

    def get_status(self) -> ToolStatus:
        try:
            import transformers  # noqa: F401
            from transformers import MusicgenForConditionalGeneration  # noqa: F401
            return ToolStatus.AVAILABLE
        except ImportError:
            return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = inputs.get("duration_seconds", 15)
        return duration + 20.0  # ~20s overhead plus generation time

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(
                success=False,
                error="transformers with Musicgen not installed. " + self.install_instructions,
            )

        import torch
        import torchaudio
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        start = time.time()
        prompt = inputs["prompt"]
        model_id = inputs.get("model", "facebook/musicgen-small")
        duration = inputs.get("duration_seconds", 15)
        seed = inputs.get("seed")
        guidance = inputs.get("guidance_scale", 3.0)
        temperature = inputs.get("temperature", 1.0)
        top_k = inputs.get("top_k", 250)
        top_p = inputs.get("top_p", 0.0)

        try:
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cpu":
                return ToolResult(
                    success=False,
                    error="MusicGen requires a GPU. No CUDA device detected.",
                )

            dtype = torch.float16 if device == "cuda" else torch.float32

            processor = AutoProcessor.from_pretrained(model_id)
            model = MusicgenForConditionalGeneration.from_pretrained(
                model_id, torch_dtype=dtype
            )
            model = model.to(device)

            sampling_rate = model.config.audio_encoder.sampling_rate
            max_new_tokens = int(duration * sampling_rate / model.config.audio_encoder.frame_rate)

            inputs_processor = processor(
                text=[prompt],
                padding=True,
                return_tensors="pt",
            ).to(device)

            generator = None
            if seed is not None:
                generator = torch.Generator(device=device).manual_seed(seed)

            generate_kwargs = {
                "input_ids": None,
                "attention_mask": None,
                "guidance_scale": guidance,
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "do_sample": temperature > 0,
            }
            if generator is not None:
                generate_kwargs["generator"] = generator
            if top_k > 0:
                generate_kwargs["top_k"] = top_k
            if top_p > 0.0:
                generate_kwargs["top_p"] = top_p

            audio_values = model.generate(
                **inputs_processor,
                **generate_kwargs,
            )

            audio_arr = audio_values[0, 0].cpu().float()

            output_path = Path(inputs.get("output_path", "musicgen_output.wav"))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            torchaudio.save(str(output_path), audio_arr.unsqueeze(0), sampling_rate)

            actual_duration = audio_arr.shape[0] / sampling_rate

        except torch.cuda.OutOfMemoryError:
            return ToolResult(
                success=False,
                error=(
                    "CUDA out of memory. Try a smaller model (musicgen-small) or "
                    "shorter duration."
                ),
            )
        except Exception as e:
            return ToolResult(success=False, error=f"MusicGen generation failed: {e}")

        return ToolResult(
            success=True,
            data={
                "provider": "musicgen_local",
                "model": model_id,
                "prompt": prompt,
                "duration_seconds": round(actual_duration, 1),
                "sample_rate": sampling_rate,
                "output": str(output_path),
                "format": "wav",
            },
            artifacts=[str(output_path)],
            cost_usd=0.0,
            duration_seconds=round(time.time() - start, 2),
            seed=seed,
            model=model_id,
        )
