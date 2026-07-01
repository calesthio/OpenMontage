---
name: wavespeed
description: WaveSpeed multi-model AI generation — profile-based model selection and tool usage.
---

# WaveSpeed Provider Skill

## When to use WaveSpeed

WaveSpeed is one of the AI generation providers. The image/video selectors discover it and score it alongside the other providers — pick it the same way you pick any provider. When WaveSpeed is selected, use its tools:

- `wavespeed_text_to_image`
- `wavespeed_image_to_video`
- `wavespeed_text_to_video`

## Model Selection

WaveSpeed is a multi-model gateway. `WAVESPEED_API_KEY` is only for authentication.

Do not choose a model because an API key exists. Select models in this order:

1. Decide the task type:
   - `text_to_image`
   - `image_to_video`
   - `text_to_video`
2. Read the active WaveSpeed profile from config.
3. Use that profile's `model_id` for the task type.
4. Use an explicit user-provided `model_id` only as a one-task override.

If the selected `model_id` is empty or missing, stop and ask the user to configure it. Do not guess model IDs.

## Usage Rules

- Save metadata for every generated asset.
- Keep generated files inside the project asset directory.
- Ask for user confirmation before spending many generation tasks.
- Continue the normal OpenMontage pipeline after assets are generated.

## Config Locations

- Environment secrets/runtime knobs: `.env` or shell environment.
- Model profiles and default params: `config.yaml` under `wavespeed.profiles`.

Use `make wavespeed-doctor` for a no-network configuration check. It must not submit a paid task.
