---
name: pika-h3-flex
description: |
  Generate 3-15 second video with native synchronized audio using Pika H3 Flex through the Pika API (`pika_video`). Use for text-to-video, first/last-frame conditioning, and reference-guided generation from up to 9 images, 3 videos and 3 audio clips, with 480p/768p native output and 1080p/2k/4k upscale. Covers the prompt structure the model responds to, when to turn prompt rewriting off, reference rules, pricing and billing behavior, and resume after a polling timeout.
---

# Pika H3 Flex

Pika H3 Flex is Pika's post-trained H3 model for professional iteration: six
sampling steps, synchronized stereo audio (dialogue, ambience, music) in one
pass, and shot direction through references and prompts. `pika_video` calls
the hosted Pika API; the open weights are also published on Hugging Face for
local ComfyUI use, which is a separate, unverified path.

## Route and billing

| Item | Value |
|------|-------|
| Tool | `pika_video`, `model: "pika-h3-flex"` |
| Credential | `PIKA_API_KEY` from https://dev.pika.art (API Keys) |
| Support | support@pika.art for API, billing and key problems |
| Billing | Prepaid per output second, charged to the user's own Pika organization. Failed jobs are not charged. A job covered by a Pika promotional allowance settles at $0 and reports `data.free_generation`. |
| Price | 480p $0.01/s, 768p $0.02/s, 1080p $0.035/s, 2k $0.04/s, 4k $0.08/s. Reference-to-video: 480p $0.03/s, 768p $0.06/s, 1080p $0.075/s, 2k $0.08/s, 4k $0.10/s, plus reference video input seconds at the same rates. |
| Cost reporting | `cost_usd` is the settled charge from the job record. `data.cost_status` is `settled`, `pending` or `unavailable`; only `settled` is final. |

OpenMontage's default budget policy asks the user before any single action over
$0.50 and the first time a new paid tool is used. A 768p 15 second clip is $0.30
and runs unprompted; any 4k clip of 7 seconds or more prompts.

Set `dry_run: true` to validate the request and get the exact quoted price from
Pika's free quote endpoint without uploading or generating. For
reference-to-video with video references, pass `reference_video_seconds` so the
preflight estimate includes the input-video charge.

## Operations

| Operation | Inputs | Notes |
|-----------|--------|-------|
| `text_to_video` | `prompt` | Default when nothing else is supplied. |
| `image_to_video` | `prompt` + `image_url` or `image_path` (first frame), or `last_frame_image_url` / `last_frame_image_path` | Either frame alone is valid. `reference_image_url` / `reference_image_path` are accepted as first-frame aliases. |
| `first_last_frame_to_video` | `prompt` + both frames | Describe the motion between the two frames. |
| `reference_to_video` | `prompt` + references | `references` in Pika's native ordered shape, or `reference_image_urls` / `reference_video_urls` / `reference_audio_urls` and the `*_paths` equivalents. Local files are uploaded to Pika. |

Operation is inferred from the inputs when omitted. Supplying frames with
`operation: "text_to_video"` is an error, not a silent downgrade.

### Reference rules

- At most 9 images, 3 videos and 3 standalone audio clips, 12 files total.
- At least one image or video is required; audio alone is rejected locally.
- Each video or audio clip must be 2 to 15 seconds; combined video and combined
  standalone audio must each fit in 15 seconds. A video's own soundtrack stays
  with that video and is not counted as a standalone audio reference.
- Order matters. The per-type lists are sent as images, then videos, then audio.
  Use `references` when a different order is intended.

## Shared parameters

- `duration`: whole seconds, 3 to 15, default 5. Output rounds up to the
  model's frame grid (124 frames for a 5 second request at 24 fps), so clips run
  slightly long. Plan edits on the delivered length, not the requested one.
- `resolution`: `480p` or `768p` native; `1080p`, `2k`, `4k` are generated at
  768p and upscaled once, preserving audio and frame rate. Draft at 480p, then
  rerun the approved take at the delivery resolution.
- `aspect_ratio`: `auto`, `21:9`, `16:9`, `3:2`, `4:3`, `5:4`, `1:1`, `4:5`,
  `3:4`, `2:3`, `9:16`, `9:21`. Omitted: `auto` when rewriting, otherwise the
  first keyframe's ratio or 16:9. Keyframes are resized and center-cropped.
- `seed`: integer. Same seed and same request reproduce closely, not exactly.
- `rewrite`: default `true`. Pika improves the prompt before generation. Turn it
  off for exact prompt control, for A/B tests across seeds, or when the prompt
  already follows the structure below. `prompt_optimizer` is accepted as an alias.
- Audio is always generated. `generate_audio: false` is rejected; strip audio in
  post with `video_compose` if a silent clip is needed.

## Prompting

Write the prompt as a shot list, not a caption. The model follows explicit
structure well:

1. **Scene**: setting, time of day, lighting, lens or style in one sentence.
2. **Subjects**: who or what, with the one or two details that must hold.
3. **Action and camera**: what happens, in order, with camera moves named
   (slow push-in, orbit, handheld follow, whip pan, hard cut to).
4. **Audio**: dialogue in quotes with the speaker named, then ambience and music
   intent. Dialogue is lip-synced when the speaker is on screen.
5. **Text on screen**: exact words, placement, and when they appear, for motion
   graphics.

Multi-shot stories work in one prompt: separate shots with "Cut to:" and keep
each shot's subject and lighting consistent by repeating the locks. For
reference-guided work, say what each reference is for ("first image: the
product; video: the dance to follow; audio: the track to cut to").

Keep prompts under 8,000 characters. Describe motion that fits the duration; a
15 second request is the ceiling, not a target.

## Failure handling

- `insufficient_balance` or `cycle_limit_exceeded`: the user's Pika balance is
  empty. Point them to https://dev.pika.art. Do not switch provider silently.
- `rate_limited` (HTTP 429): honor `data.retry_after`, then submit again.
- `content_moderation` or `invalid_input`: revise the prompt or inputs; the
  message names the problem.
- Poll timeout: the result carries `data.resume_job`. Call `pika_video` again
  with that object (and a longer `poll_timeout`) to keep waiting on the same job
  instead of paying for a new one. Set `job_path` to persist the checkpoint.
- The tool never retries a paid submission on its own.

## Provenance

Every result records `data.request` (the exact payload sent), `data.job_id`,
`data.usage`, `data.billing` and `data.resume_job`. Keep these with the clip for
reproducibility and cost reconciliation.
