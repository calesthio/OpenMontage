---
name: relay-providers
description: How to use OpenMontage relay (中转站 / third-party API gateway) tools for image, video and TTS generation — exact routing by preferred_tool / hosting_provider / model, local first frames, async resume without double billing, budget, and live-billing gates. Read before calling any tool named relay_*.
---

# Relay providers (中转站)

Relay tools are generated from `relay_providers.yaml` — **one tool per configured model**,
named `relay_<relay>_<model>`. They are normal registry tools: `video_selector`,
`image_selector` and `tts_selector` route to them, and `provider_menu_summary()` lists them.

## 1. Discover before planning

```bash
python -m tools.relay check   # config + env vars + live switch (no network, no secrets printed)
python -m tools.relay list    # every relay tool, its model, supports{} and unsupported capabilities
```

Read each tool's `get_info()["relay"]`: `limits` (allowed durations / sizes / aspect ratios),
`defaults`, `pricing`, `image_input`, `unsupported_capabilities`, `billing_enabled`.
**Plan shots only with capabilities a tool declares.** A model without `image_to_video`
cannot animate a first frame; a model without `first_last_frame` cannot take an end frame.
Calls outside the declaration are refused (`error_code: unsupported_capability`) — never
work around that by dropping the image; propose another declared model to the user.

## 2. Route exactly

Always pin the approved tool once the user approves a provider/model:

```python
video_selector.execute({
    "preferred_tool": "relay_myrelay_kling_v2_1",   # exact tool; never falls back
    # or: "hosting_provider": "myrelay", "model": "kling-v2-1"
    "operation": "image_to_video",
    "prompt": "...",
    "reference_image_path": "projects/<id>/assets/images/scene_03.png",  # local first frame
    "duration": 5, "aspect_ratio": "16:9",
    "output_path": "projects/<id>/assets/video/scene_03.mp4",
    "scene_id": "scene_03",
})
```

- `routing.paid_provider_policy: relay_only` (recommended) makes selectors consider only
  relay tools plus free/local tools. Another paid vendor needs the user's explicit OK and
  `allow_non_relay_paid: true` — then log a `provider_selection` decision.
- A missing key, wrong model, or unsupported operation returns an error that says so.
  It never silently switches tool, model, or vendor. Surface it with the blocker protocol.

## 3. First frames and reference images

- Pass **local paths** (`reference_image_path` / `first_frame_path`, `last_frame_path`,
  `reference_image_paths`). The tool encodes them per the model's `image_input`
  (`data_uri`, `base64`, or `multipart` upload). Nothing is uploaded to third-party hosts.
- `image_input: url` models need a public URL; a local file is refused with an explanation.
- Typical flow for "make these photos move": user photo → (optional `image_selector`
  edit for style/aspect) → `video_selector` `image_to_video` with that file as first frame.

## 4. Async jobs — never pay twice

Every call writes `<output_path>.relay-job.json` **before** submitting.

| Result | Meaning | What you do |
|---|---|---|
| `success: true` | file downloaded to `output_path` | use the local file (relay URLs expire) |
| `status: pending`, `recovery_action: resume` | polling stopped, task still running | call the **same tool with the same inputs/output_path** again, or pass `resume_job` from the result, or `python -m tools.relay resume <job_path>` |
| `error_code: submit_unknown` | submit may have been billed | tell the user; check the relay dashboard; only with their OK pass `confirm_resubmit: true` |
| `error_code: previous_failure` / task failed | relay reported failure | report the relay's reason; a retry is a new paid request → needs approval + `confirm_resubmit: true` |
| `error_code: job_conflict` | output_path already used by another request | choose a new output_path (one file per shot/take) |

Re-calling a completed job returns the local file for free (`cost_usd: 0`).
Use a distinct `output_path` per take (`scene_03_take2.mp4`) when the user wants variations.

## 5. Budget

- `estimate_cost(inputs)` comes from `pricing` in the config (USD; CNY converted).
  No pricing → `PriceQuoteRequired`; execution is refused unless the user approves and
  you pass `allow_unpriced: true`.
- Follow the normal cost_tracker flow: `estimate → reserve → execute → reconcile(result.cost_usd)`.
  A pending call reports `cost_usd: 0` and `committed_cost_usd`; the resumed call that
  finishes reports the cost once.
- `dry_run: true` shows the exact request body, path, files and estimated cost without sending.
  Use it to show the user the parameter mapping before the first paid sample.

## 6. Live switch

`live: false` (default) refuses real billable calls with `error_code: live_disabled`.
Loopback relays (the mock) always run. Do not edit `live` yourself — ask the user to enable
it after `python -m pytest tests/tools/test_relay_providers.py tests/tools/test_relay_e2e.py` passes.

## 7. Prompting

Relay tools forward prompts unchanged to the upstream model. Read the model family's own
Layer 3 skill when one exists (listed in the tool's `agent_skills`, e.g. `seedance-2-0`,
`ai-video-gen`) for prompt structure, camera language and duration guidance.
