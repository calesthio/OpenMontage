# Script Director — Product-Motion Pipeline

## When to Use

Third stage. The proposal (concept, screens, runtime, taste) is approved. You
write the narration script whose beats the screen animations will land on.

## Process

1. **Structure = the approved concept's screen order.** Each script section
   narrates over exactly one screen (or the open/close). Put the screen's
   `ui_inventory` id in the section's metadata — the manifest requires every
   section to name the `screen_id` it narrates over.
2. **Assembly moments are script beats.** Where the form assembles, where the
   dashboard cards arrive, where the button gets pressed — write those as
   explicit beats with intended timing, because scene_plan converts them into
   element build orders and the SFX cue sheet hangs off them. A section that
   says "the dashboard appears" is under-written; "the usage chart draws in
   as we say 'see every request in real time'" is right.
3. **Truthful claims only.** Narration may only claim what the repo evidences
   (`ui_inventory` purposes, real labels, real flows). "Invite your team in
   two clicks" is only sayable if the invite flow exists in the inventory.
   Marketing superlatives about the product's internals are out; what the UI
   visibly does is in.
4. **Register**: polished-SaaS founder/product register — confident, calm,
   concrete. Short sentences that leave air for the assembly beats. Target
   duration from the proposal; ~140 words per minute of narration.
5. **Voice performance**: set `voice_performance` per the TTS provider chosen
   at proposal (see the provider's Layer 3 skill for parameter mapping) and
   pick the `sample_section_id` for the assets-stage sample gate.
6. Validate against `schemas/artifacts/script.schema.json`, self-review
   (review_focus in the manifest), checkpoint `awaiting_human`, present the
   script with per-section screen mapping, **end your turn**.
