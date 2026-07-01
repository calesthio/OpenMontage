# WaveSpeed Smoke Test

Use this guide to verify WaveSpeed setup without accidentally spending credits.

## Dry Checks

These do not submit paid generation tasks.

Check config and env:

```bash
make wavespeed-doctor
```

Check registry discovery:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_catalog().get('wavespeed', []), indent=2))"
```

Check selectors in rank mode:

```bash
python -c "from tools.graphics.image_selector import ImageSelector; import json; r=ImageSelector().execute({'prompt':'test','operation':'rank'}); print(json.dumps(r.data, indent=2))"
```

## Paid Smoke Commands

The following commands submit WaveSpeed generation tasks and may spend credits. Run only after confirming the active profile has verified model IDs.

### Text To Image

```bash
python -m tools.graphics.wavespeed_text_to_image \
  --prompt "A simple product launch storyboard frame, clean lighting, no text" \
  --output-dir projects/wavespeed-smoke/assets/images \
  --params '{"aspect_ratio":"16:9"}'
```

Expected result:

- One image file in `projects/wavespeed-smoke/assets/images`
- One metadata JSON sidecar
- JSON printed to stdout with `provider: wavespeed`, `task_type: text_to_image`, and `status: completed`

### Text To Video

```bash
python -m tools.video.wavespeed_text_to_video \
  --prompt "A 3 to 5 second cinematic slow push toward a glowing server rack, controlled camera motion" \
  --output-dir projects/wavespeed-smoke/assets/video \
  --params '{"duration":5,"aspect_ratio":"16:9"}'
```

Expected result:

- One video file in `projects/wavespeed-smoke/assets/video`
- One metadata JSON sidecar
- JSON printed to stdout with `provider: wavespeed`, `task_type: text_to_video`, and `status: completed`

### Image To Video

Use an image generated above or another local reference image:

```bash
python -m tools.video.wavespeed_image_to_video \
  --prompt "Subtle parallax and slow dolly-in, preserve the original composition" \
  --image-path projects/wavespeed-smoke/assets/images/reference.png \
  --output-dir projects/wavespeed-smoke/assets/video \
  --params '{"duration":5,"aspect_ratio":"16:9"}'
```

Expected result:

- One video file in `projects/wavespeed-smoke/assets/video`
- Metadata includes `input_reference`
- JSON printed to stdout with `provider: wavespeed`, `task_type: image_to_video`, and `status: completed`

## Failure Checks

These are expected to fail without spending credits:

- Empty model ID in config: tools stop before submit and ask for configuration.
- Missing `WAVESPEED_API_KEY`: tools stop before submit.
- `make wavespeed-doctor` with empty placeholders: prints next steps and does not call WaveSpeed.

## Do Not Run In CI

Do not add paid smoke commands to CI. Unit tests must mock HTTP calls and must not require a real WaveSpeed API key.
