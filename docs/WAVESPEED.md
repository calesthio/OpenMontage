# WaveSpeed Provider

WaveSpeed is a multi-model AI generation provider for OpenMontage.
It supports image generation, video generation, audio/TTS, and digital human (avatar) video creation.

## How model selection works

- WaveSpeed is one of the AI generation providers. It is discovered by the image/video selectors and competes with the other providers (fal.ai, OpenAI, Google, etc.) by score, like any provider.
- What makes WaveSpeed different is *where the model comes from*: `WAVESPEED_API_KEY` is only an authentication secret, and model selection is based on `task_type`, the active WaveSpeed profile in `config.yaml`, and an optional one-task `model_id` override.
- Do not use API-key presence to choose a model.
- Setup, tests, doctors, and smoke checks must not trigger paid generation unless a command is clearly marked as paid.

## Supported Task Types

- `text_to_image`: Generate images from text descriptions
- `image_to_video`: Generate video from image + motion prompt
- `text_to_video`: Generate video directly from text prompt
- `text_to_audio`: Text-to-speech (TTS) and music generation
- `digital_human`: Digital human/avatar video generation
- `image_edit`: Edit / image-to-image from a source image + instruction
- `image_upscale`: Super-resolution / upscaling of a source image
- `text_to_music`: Music generation from a text prompt

Each task type has model IDs configured in the active WaveSpeed profile.

## Environment

Set secrets in `.env` or your shell:

```bash
WAVESPEED_API_KEY=your-wavespeed-api-key
```

Optional runtime configuration (can also be set in `config.yaml`):

```bash
WAVESPEED_API_BASE_URL=https://api.wavespeed.ai/api/v3  # Default: official WaveSpeed endpoint
```

Runtime tuning (rarely needed):

```bash
WAVESPEED_POLL_INTERVAL_IMAGE_SECONDS=2      # How often to poll for image generation
WAVESPEED_POLL_INTERVAL_VIDEO_SECONDS=5      # How often to poll for video generation
WAVESPEED_MAX_WAIT_SECONDS=900                # Max seconds to wait for generation
WAVESPEED_MAX_TASKS_PER_RUN=20                # Max tasks to submit in one run
```

Do not commit real secrets.

## Model Profiles

Model profiles live in `config.yaml` under `wavespeed.profiles`.

```yaml
wavespeed:
  active_profile: null  # null = all profiles compete; "default"/"fast"/"quality" = specific profile

  profiles:
    default:
      text_to_image:
        model_id: "..."
        params: {}
      image_to_video:
        model_id: "..."
        params: {}
      text_to_video:
        model_id: "..."
        params: {}
      text_to_audio:
        model_id: "..."
        params: {}
      digital_human:
        model_id: "..."
        params: {}
      image_edit:
        model_id: "..."
        params: {}
      image_upscale:
        model_id: "..."
        params: {}
      text_to_music:
        model_id: "..."
        params: {}
```

### Profile Selection

**`active_profile: null`** (default): All profiles compete equally in multi-provider scoring.
Each profile becomes a separate candidate, and the system picks the best by 7-dimension score.
This is the recommended mode for adaptive generation.

**`active_profile: "named"`** (e.g., `default`, `quality`, `fast`): Only that profile's models are WaveSpeed candidates.
They still compete with other providers (FAL, OpenAI, etc.) by score, but WaveSpeed selection stays deterministic within the profile.

## Model Resolution

For every WaveSpeed generation task:

1. **Identify task type:** `text_to_image`, `image_to_video`, `text_to_video`, `text_to_audio`, `digital_human`, `image_edit`, `image_upscale`, or `text_to_music`.
2. **Load active profile:** Determined by `wavespeed.active_profile` in config.yaml.
3. **Resolve model_id:**
   - Explicit `--model-id` argument (one-task override) → use it
   - Profile's `model_id` for task_type → use it
   - No model ID available → stop and ask user to configure it
4. **Merge params:**
   - Profile default `params` (base)
   - Explicit CLI/tool `params` (override)

## Tools

Registry-discovered tools (auto-discoverable from Python):

**Image/Video Generation:**
- `wavespeed_text_to_image`: Text → Image (capability `image_generation`)
- `wavespeed_image_to_video`: Image + motion prompt → Video (capability `video_generation`)
- `wavespeed_text_to_video`: Text → Video (capability `video_generation`)

**Audio + Digital Human:**
- `wavespeed_text_to_audio`: Text → Audio, TTS/music (capability `tts`; discovered by `tts_selector`)
- `wavespeed_digital_human`: Text → Digital human video (capability `avatar`)

**Editing / Enhancement / Music:**
- `wavespeed_image_edit`: Image + instruction → edited Image (capability `image_generation`)
- `wavespeed_image_upscale`: Image → upscaled Image (capability `enhancement`)
- `wavespeed_text_to_music`: Text → Music (capability `music_generation`)

All tools:
- Read active profile from `config.yaml`
- Submit requests to WaveSpeed: `POST /{model_id}`
- Poll for results: `GET /predictions/{task_id}/result`
- Write metadata sidecars (JSON) alongside outputs

## Example Commands

These commands are paid because they submit generation tasks.

**Image generation:**

```bash
python -m tools.graphics.wavespeed_text_to_image \
  --prompt "A clean editorial hero image of a product launch control room" \
  --output-dir projects/example/assets/images
```

**Image to video:**

```bash
python -m tools.video.wavespeed_image_to_video \
  --prompt "Slow cinematic push-in, subtle parallax, polished launch-film lighting" \
  --image-path projects/example/assets/images/hero.png \
  --output-dir projects/example/assets/video
```

**Text to video:**

```bash
python -m tools.video.wavespeed_text_to_video \
  --prompt "A 5-second cinematic macro shot of a data center cooling aisle, controlled dolly movement" \
  --output-dir projects/example/assets/video
```

**Text to audio (TTS/music):**

```bash
python -m tools.wavespeed_text_to_audio \
  --prompt "Professional voiceover: Clear, warm male voice explaining quantum computing fundamentals" \
  --output-dir projects/example/assets/audio
```

**Digital human video:**

```bash
python -m tools.wavespeed_digital_human \
  --prompt "Professional female presenter in business suit, modern office, delivering a 30-second product pitch" \
  --output-dir projects/example/assets/video
```

**Override model for one task:**

```bash
python -m tools.video.wavespeed_text_to_video \
  --prompt "A short establishing shot of a New York skyline at dawn" \
  --output-dir projects/example/assets/video \
  --model-id "your/verified-wavespeed-model-id"
```

**Override params:**

```bash
python -m tools.graphics.wavespeed_text_to_image \
  --prompt "Studio-lit product render on white background" \
  --output-dir projects/example/assets/images \
  --params '{"aspect_ratio":"16:9","seed":1234}'
```

## Output Contract

Each tool prints machine-readable JSON and writes a metadata sidecar:

```json
{
  "asset_type": "image",
  "provider": "wavespeed",
  "task_type": "text_to_image",
  "model_id": "...",
  "profile": "default",
  "task_id": "...",
  "status": "completed",
  "prompt": "...",
  "params": {},
  "outputs": ["https://..."],
  "local_paths": ["projects/example/assets/images/file.png"],
  "metadata_path": "projects/example/assets/images/file_metadata.json",
  "created_at": "2026-06-30T00:00:00+00:00",
  "duration_sec": null,
  "width": null,
  "height": null
}
```

Failed or timed-out tasks still write metadata when an output directory can be resolved.

## Doctor

Run a no-network setup check:

```bash
make wavespeed-doctor
```

The doctor checks:

- `WAVESPEED_API_KEY` is set and valid format
- active profile exists and is readable
- configuration for all supported task types is present

It does not submit a paid task.

## Adding New Task Types

To extend WaveSpeed with a new task type (e.g., `image_to_image`, `audio_to_audio`, `video_effects`):

### Step 1: Add to config.yaml

Add the new task type to all profiles in `wavespeed.profiles`:

```yaml
wavespeed:
  profiles:
    default:
      new_task_type:
        model_id: ""  # Empty for optional models; fill in quality profile
        params: {}
    fast:
      new_task_type:
        model_id: ""
        params: {}
    quality:
      new_task_type:
        model_id: "provider/model-name"
        params: {custom_param: value}
```

### Step 2: Register in lib/wavespeed_config.py

Add the new task type to `SUPPORTED_TASK_TYPES`:

```python
SUPPORTED_TASK_TYPES = {
    "text_to_image",
    "image_to_video",
    "text_to_video",
    "text_to_audio",
    "digital_human",
    "image_edit",
    "image_upscale",
    "text_to_music",
    "new_task_type",  # ← Add here
}
```

### Step 3: Implement the Tool

Create a new tool file following the existing pattern. Example: `tools/graphics/wavespeed_image_to_image.py`

```python
from tools.base_tool import BaseTool
import tools.wavespeed_generation as wavespeed_generation

class WaveSpeedImageToImage(BaseTool):
    """Generate modified images from source images using WaveSpeed."""

    name = "wavespeed_image_to_image"
    description = "Edit, transform, or modify images using WaveSpeed models."

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._wavespeed_profile: str | None = None
        self._wavespeed_model_id: str | None = None

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute image-to-image transformation.
        
        Args:
            inputs: {prompt, image_path, output_dir, model_id, task_params}
        """
        prompt = inputs.get("prompt", "")
        image_path = inputs.get("image_path", "")
        output_dir = inputs.get("output_dir")
        task_params = inputs.get("task_params") or {}

        if hasattr(self, "_wavespeed_profile"):
            inputs = dict(inputs)
            inputs["_wavespeed_profile"] = self._wavespeed_profile
            if hasattr(self, "_wavespeed_model_id"):
                inputs["model_id"] = self._wavespeed_model_id

        return wavespeed_generation.run_wavespeed_generation(
            task_type="image_to_image",
            payload={"prompt": prompt, "image_path": image_path, **task_params},
            explicit_model_id=inputs.get("model_id"),
            explicit_params=task_params,
            explicit_profile=inputs.get("_wavespeed_profile"),
            output_dir=Path(output_dir) if output_dir else None,
        )

    @property
    def can_run(self) -> bool:
        return bool(os.getenv("WAVESPEED_API_KEY"))
```

**Key points:**
- Inherit from `BaseTool`
- Accept `_wavespeed_profile` and `_wavespeed_model_id` from selectors
- Call `run_wavespeed_generation()` with explicit `task_type`
- Set `can_run` to check API key availability
- Add to `tools/__init__.py` if not auto-discovered

### Step 4: Add Unit Tests

In `tests/tools/test_wavespeed.py`, add a test for profile resolution:

```python
def test_image_to_image_profile_resolution(tmp_path):
    """Test image_to_image task type resolution."""
    config_path = write_config(
        tmp_path,
        """
        wavespeed:
          active_profile: null
          profiles:
            default:
              image_to_image:
                model_id: ""
                params: {}
            quality:
              image_to_image:
                model_id: "provider/i2i-model"
                params: {}
        """,
    )
    
    candidates = get_wavespeed_candidates_for_task("image_to_image", config_path)
    assert len(candidates) == 2
    quality_models = [m for m, p in candidates if p == "quality"]
    assert len(quality_models) > 0
```

### Step 5: (Optional) Implement Selector

If you need multi-provider scoring for this task type, create a selector (e.g., `tools/graphics/image_to_image_selector.py`):

```python
from lib.wavespeed_config import get_wavespeed_candidates_for_task

def select_image_to_image_provider(inputs, task_context=None):
    """Select best provider for image-to-image transformation."""
    candidates = []
    
    # Gather WaveSpeed candidates
    if os.getenv("WAVESPEED_API_KEY"):
        ws_candidates = get_wavespeed_candidates_for_task("image_to_image")
        for model_id, profile_name in ws_candidates:
            tool = WaveSpeedImageToImage()
            tool._wavespeed_profile = profile_name
            tool._wavespeed_model_id = model_id
            candidates.append(tool)
    
    # Add other providers (FAL, OpenAI, etc.)
    candidates.extend([...])
    
    # Score and select
    tool, score = select_best_tool(inputs, candidates, task_context)
    return tool
```

### Checklist

- [ ] Added task type to `wavespeed.profiles.<profile>.<task_type>` in config.yaml (all 3 profiles)
- [ ] Added to `SUPPORTED_TASK_TYPES` in lib/wavespeed_config.py
- [ ] Implemented tool class (inherits BaseTool, calls run_wavespeed_generation)
- [ ] Added unit test for profile resolution
- [ ] (Optional) Implemented selector for multi-provider scoring
- [ ] Updated this WAVESPEED.md with new task type in "Supported Task Types"
- [ ] Added example command in "Example Commands" section
- [ ] Tested with `python -m pytest tests/tools/test_wavespeed.py::test_<new_type>_profile_resolution -v`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Missing API key | Set `WAVESPEED_API_KEY` in `.env` or shell |
| Missing model ID | Configure `config.yaml wavespeed.profiles.<profile>.<task_type>.model_id` |
| Wrong profile | Verify `wavespeed.active_profile` in `config.yaml` or use explicit `--model-id` override |
| HTTP 401/403 | Verify API key validity and account access |
| Timeout | Increase `WAVESPEED_MAX_WAIT_SECONDS` or inspect metadata sidecar for task ID |
| No output URLs | Check metadata sidecar for raw WaveSpeed response; model may return different output shape |
| Task not found | Verify task ID in metadata; WaveSpeed may have garbage-collected old results

## Cost And Safety

Generation commands can spend credits. Ask for confirmation before large batches, respect `WAVESPEED_MAX_TASKS_PER_RUN`, and never run paid generation in setup, CI, unit tests, or doctor targets.
