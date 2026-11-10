---
name: uberllm-video
description: |
  Generate video through UberLLM (`uberllm_video`): Seedance 2.0, Wan 2.7, Kling 3 Standard, Veo 3.1 Fast, LTX 2.3 Fast, Hailuo 02 and Vidu Q3 Turbo on one UberLLM key, for text-to-video, image-to-video (first frame) and reference-to-video. Covers picking a model family, the fixed clip lengths each model takes, the free exact price check, billing, and resume after a polling timeout.
---

# UberLLM video

`uberllm_video` sends video jobs to UberLLM (`https://api.uberllm.dev`). One
`UBERLLM_API_KEY` reaches several video model families, and the same key and
prepaid balance also serve UberLLM's image, music and speech models, so a
production that needs more than video does not need another account.

## Route and billing

| Item | Value |
|------|-------|
| Tool | `uberllm_video` |
| Credential | `UBERLLM_API_KEY` (starts with `ull_`) from https://uberllm.dev/signup |
| Billing | Prepaid credit, pay as you go from $5. Failed, canceled and expired jobs cost nothing. A finished job is billed what the provider charged, never more than `data.max_cost_usd`. |
| Prices | Live per-model prices at https://uberllm.dev/models. Pinned per-second rates in `tools/provider_contracts/uberllm_video.json` are for preflight estimates only. |
| Cost reporting | `cost_usd` is the job's `usage.cost_usd`. `data.cost_status` is `settled` or `pending` (the exact charge usually arrives within 30 seconds of the file; until then the listed price is reported). |

Set `dry_run: true` to have UberLLM check the request (model, length, picture)
and return its exact quote without generating or charging. Set `max_cost_usd`
to have a job refused at no charge when it could cost more than that.

OpenMontage's default budget policy asks the user before any single action over
$0.50 and the first time a new paid tool is used.

## Choosing a model

Pass a family as `model`; the operation picks its text, image or reference
route. An exact UberLLM model id also works (see `get_info()["model_catalog"]`).

| Family | Operations | Good for |
|--------|------------|----------|
| `seedance-2.0` (default) | text, image, reference | Cinematic clips, the only family here with all three routes |
| `wan-2.7` | text, image, reference | Reference-guided clips at 720p/1080p, with a sound setting on reference-to-video |
| `kling-3-standard` | text, image | 3 to 15 second clips in 1 second steps, sound on unless `generate_audio: false` |
| `veo-3.1-fast` | text, image | 4, 6 or 8 second clips up to 4k, sound on unless `generate_audio: false` |
| `ltx-2.3-fast` | text, image | 1080p to 2160p clips of 6, 8 or 10 seconds |
| `hailuo-02-standard` | text, image | Low-cost 6 or 10 second clips |
| `vidu-q3-turbo` | text, image | Drafts: 1 to 16 seconds at 360p/540p for a few cents |

Draft on a low-cost family, then rerun the approved take on a premium one.

## Operations

| Operation | Inputs |
|-----------|--------|
| `text_to_video` | `prompt` |
| `image_to_video` | `prompt` + `reference_image_url` (https://) or `reference_image_path` (uploaded to UberLLM, kept 24 hours) |
| `reference_to_video` | `prompt` + up to 8 `reference_image_urls` / `reference_image_paths` |

Operation is inferred from the inputs when omitted. Pictures with
`operation: "text_to_video"` are an error, not a silent downgrade.

## Shared parameters

- `duration`: whole seconds. Each model makes fixed lengths (Seedance 2.0 text:
  5 to 15; Veo 3.1 Fast: 4, 6, 8). Omitted: the model's shortest. A length the
  model does not make is refused before anything is sent.
- `resolution`, `aspect_ratio`, `generate_audio`: sent only to models that have
  the setting. Asking a model for a setting it lacks is refused with the list of
  families that offer it, rather than ignored.
- `provider_params`: extra request fields, checked against the model's pinned
  schema.

## Failure handling

- `insufficient_balance`: add credit at https://uberllm.dev/dashboard/credits.
  Do not switch provider silently.
- A busy moment is retried by UberLLM itself (same job, same price ceiling);
  `failed` means every try failed, and it costs nothing.
- Poll timeout: the result carries `data.resume_job`. Call `uberllm_video` again
  with that object (and a longer `poll_timeout`) to keep waiting on the same job
  instead of paying for a new one. Set `job_path` to persist the checkpoint.
- The tool never retries a paid submission on its own. Finished files are kept
  about 3 hours, so the tool downloads them as soon as the job ends.

## Provenance

Every result records `data.request` (the payload sent, inline pictures
redacted), `data.job_id`, `data.usage`, `data.estimated_cost_usd`,
`data.max_cost_usd` and `data.resume_job`.
