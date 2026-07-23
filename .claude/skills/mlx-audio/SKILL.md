---
name: mlx-audio
description: Run local text-to-speech with the MLX-Audio Python API on Apple Silicon. Use when the user selects the mlx_audio provider, supplies an MLX-Audio TTS model, or needs local model-specific voice, language, instruction, speed, or reference-audio guidance.
---

# MLX-Audio TTS

Use MLX-Audio for in-process local TTS on Apple Silicon. In OpenMontage the public names are:

- provider: `mlx_audio`
- tool: `mlx_audio_tts`
- skill: `mlx-audio`

Qwen3-TTS is one supported model family, not a provider or tool name.

## Requirements and Installation

MLX-Audio requires macOS on Apple Silicon (`Darwin arm64`). Install the TTS dependencies into the active OpenMontage environment:

```bash
make install-mlx-audio
```

Then enable and optionally configure the provider in `.env`:

```bash
MLX_AUDIO_ENABLED=true
# MLX_AUDIO_MODEL_ID=mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit
# MLX_AUDIO_VOICE_ID=Ryan
```

The target installs:

```text
mlx-audio[tts]>=0.4.5,<0.5
```

FFmpeg's `ffprobe` binary is also required. OpenMontage uses it for mandatory WAV stream and positive-duration validation before publishing generated audio. Install FFmpeg with `brew install ffmpeg` if `ffprobe` is missing.

Do not install or start the MLX-Audio server. OpenMontage imports the Python package and runs inference in-process; there is no port, HTTP endpoint, or CLI subprocess.

## Python API

MLX-Audio loads a Hugging Face model ID or local model directory with `load_model()` and yields one or more audio segments from `model.generate()`:

```python
from mlx_audio.tts.utils import load_model

model = load_model("mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit")

for result in model.generate(
    text="Welcome to OpenMontage.",
    voice="Ryan",
    lang_code="English",
):
    audio = result.audio
    sample_rate = result.sample_rate
```

The exact optional arguments and supported values are model-specific. Consult the selected model's documentation; do not infer that every MLX-Audio model supports voices, languages, instructions, speed control, or cloning.

## OpenMontage Usage

Prefer `tts_selector` in pipeline work. Pin both selector fields when the user explicitly selected this provider:

```python
from tools.audio.tts_selector import TTSSelector

result = TTSSelector().execute({
    "preferred_provider": "mlx_audio",
    "allowed_providers": ["mlx_audio"],
    "text": "Welcome to OpenMontage.",
    "language": "English",
    "output_path": "projects/my-video/assets/audio/narration.wav",
})

if not result.success:
    raise RuntimeError(result.error)
```

`text` and `output_path` are required and must be non-empty. `output_path` must end in `.wav`. The built-in default is `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit` with the `Ryan` voice.

Request-level `model_id` and `voice_id` values override `MLX_AUDIO_MODEL_ID` and `MLX_AUDIO_VOICE_ID`; environment values override the built-in defaults. The built-in `Ryan` fallback is used only with the built-in default model. When selecting another model family, pass only the controls documented by that model.

### Canonical Parameter Mapping

| OpenMontage field | MLX-Audio call |
|---|---|
| `model_id` | `load_model(model_id)` |
| `text` | `model.generate(text=text, ...)` |
| `voice_id` | `voice` |
| `language` | `lang_code` |
| `instructions` | `instruct` |
| `speed` | `speed` |
| `reference_audio_path` | `ref_audio` |
| `reference_text` | `ref_text` |
| `generation_options` | Additional keyword arguments to `model.generate()` |
| `output_path` | One joined WAV written by OpenMontage |

Use `generation_options` only for extra arguments documented by the selected model. It cannot contain `text`, `voice`, `lang_code`, `instruct`, `speed`, `ref_audio`, `ref_text`, or `stream`; those keys would conflict with the public contract. Streaming and batch generation are outside this provider's scope.

## Model Selection

Preserve the user's explicit `model_id` or `voice_id`. When neither is selected, use the configured or built-in defaults rather than asking unnecessarily. The provider accepts any MLX-Audio-compatible Hugging Face ID or local model directory and intentionally has no model whitelist.

Choose optional fields from the model's documented capabilities:

- Preset voice model: pass `voice_id` only when the model documents that voice.
- Multilingual model: pass `language` using the model's accepted language code or label.
- Instruction-capable model: pass `instructions` for the documented style or voice-design behavior.
- Speed-capable model: pass `speed` only when supported.
- Voice-cloning model: pass both `reference_audio_path` and the matching `reference_text` when the model requires a transcript.

If a selected model rejects an option, return the error. Do not silently change models or providers.

## Qwen3-TTS Model Examples

These examples are validation recipes for one model family. They do not define the provider's full model support.

### CustomVoice

```python
{
    "text": "The edit is ready for review.",
    "model_id": "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-6bit",
    "voice_id": "Ryan",
    "language": "English",
    "output_path": "projects/my-video/assets/audio/qwen3-custom.wav",
}
```

Add `instructions` only when the selected CustomVoice model documents instruction control.

The built-in Qwen3 CustomVoice model documents these preset voices: `Vivian`, `Serena`, `Uncle_Fu`, `Dylan`, `Eric`, `Ryan`, `Aiden`, `Ono_Anna`, and `Sohee`.

### VoiceDesign

```python
{
    "text": "The story begins beneath a quiet winter sky.",
    "model_id": "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-6bit",
    "language": "English",
    "instructions": "A calm, intimate documentary narrator with a warm low register.",
    "output_path": "projects/my-video/assets/audio/qwen3-design.wav",
}
```

### Base Voice Cloning

```python
{
    "text": "This line should match the approved reference speaker.",
    "model_id": "mlx-community/Qwen3-TTS-12Hz-1.7B-Base-6bit",
    "reference_audio_path": "projects/my-video/assets/audio/reference.wav",
    "reference_text": "The exact transcript spoken in the reference clip.",
    "output_path": "projects/my-video/assets/audio/qwen3-clone.wav",
}
```

Use reference audio only when the user has the right to use that voice. Keep the transcript aligned with the clip.

## Runtime Behavior

- The first use of a Hugging Face model may download weights and therefore need network access and sufficient disk space.
- A loaded model is reused for repeated generations with the same `model_id`.
- Selecting a different `model_id` releases the previous model and clears the MLX cache before loading the next one.
- Generation is serialized to protect the single-model cache and unified-memory usage.
- Local inference has no per-request provider fee, but it consumes local compute, memory, and storage.

## Troubleshooting

### Tool is unavailable

Confirm the platform, package import, and `ffprobe` status:

```bash
test "$MLX_AUDIO_ENABLED" = "true"
uname -s
uname -m
python -c "import mlx_audio; print('mlx_audio import OK')"
command -v ffprobe
ffprobe -version
```

`MLX_AUDIO_ENABLED` must be `true`. Expected platform output is `Darwin` and `arm64`, the Python import must succeed, and `ffprobe` must resolve and print its version. Re-run `make install-mlx-audio` in the same environment OpenMontage uses, or install FFmpeg if only `ffprobe` is missing.

### Model download or load fails

Verify the `model_id`, network access, disk space, and any Hugging Face access requirements. A local model path must exist. OpenMontage does not substitute another model.

### Reference audio fails

Verify that `reference_audio_path` exists, is readable, and is compatible with the model. Supply the matching `reference_text` when required by the model.

### Model rejects a keyword

Remove optional fields or `generation_options` that the selected model does not support. Do not rename canonical OpenMontage fields or place reserved keys in `generation_options`.

### Empty or invalid output

Treat empty generated segments as a failed inference. Check the model-specific required controls, shorten the test text, and validate a short sample before producing full narration.
