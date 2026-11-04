# Relay Providers in OpenMontage Pipelines

Layer 2 conventions for third-party API relays (中转站). Layer 3 usage details
(routing fields, async resume, error codes) live in
`.agents/skills/relay-providers/SKILL.md` — read it before the first relay call.

## When this applies

The registry contains tools named `relay_<relay>_<model>` (built from
`relay_providers.yaml`). They are ordinary providers for `video_generation`,
`image_generation` and `tts`, reached through the normal selectors.

## Preflight

1. `python -m tools.relay check` — config valid? key env vars set? `live` on?
   Report problems verbatim (they never contain key values).
2. `registry.provider_menu_summary()` as usual; relay tools appear under their
   relay name as provider.
3. If `paid_provider_policy` is `relay_only`, say so in the capability menu:
   "paid generation runs only through your relays; other vendors are off".
4. If a relay has `live: false`, tell the user real generation is disabled
   until they enable it — do not plan paid samples on it.

## Proposal

- Build the shot plan from **declared** capabilities (`python -m tools.relay list`
  shows supports and unsupported capabilities per model). A shot needing a
  first frame goes to a model with `image_to_video`; first+last frame needs
  `first_last_frame`.
- Log one `provider_selection` decision per capability with `subject` naming
  the capability (e.g. "Shot video generation"), the chosen tool, and the
  other relay models in `options_considered`.
- Show cost per shot from `estimate_cost` (config pricing). Unpriced models
  must be flagged to the user before approval.

## Assets stage

- Call through the selector with `preferred_tool` set to the approved tool
  (or `hosting_provider` + `model`). Never rely on auto-ranking once a model
  is approved.
- Sample first: one shot, show it, then batch (`sample` → `batch` mode change
  needs approval as usual).
- `output_path` must be under `projects/<id>/assets/...`, one file per shot
  and take. Keep the `.relay-job.json` next to it — it is the receipt that
  prevents double billing.
- A `pending` result is not a failure: re-call with the same inputs before
  moving on; update `metadata.partial_progress` in the in-progress checkpoint.
- Record `provider` (relay), `model`, `source_tool`, `cost_usd` per asset in
  the `asset_manifest`; use the local file path, never the relay URL.
- `submit_unknown` / task failure → blocker protocol (what, why, options,
  recommendation). Retrying is a new paid call → approval + `confirm_resubmit`.

## Compose

Relay outputs are plain local files; `video_compose`, `video_stitch`,
`audio_mixer`, subtitles, and review work unchanged.
