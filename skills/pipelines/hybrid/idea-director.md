# Idea Director - Hybrid Pipeline

## When To Use

Use this pipeline when the project combines real source media with support visuals: interviews plus diagrams, footage plus overlays, screen recording plus branded graphics, or source-led edits with generated inserts.

Hybrid is not a catch-all. Your first job is to define what stays primary.

## Runtime Selection (MANDATORY — present both runtimes)

Before locking the production plan, decide `render_runtime` with the user. Hybrid supports BOTH Remotion and HyperFrames; neither is an auto-default. Follow the contract in AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)":

1. Query `video_compose.get_info()["render_engines"]`. If both `remotion` and `hyperframes` are `True`, present both to the user with brief-specific analysis:
   - **Remotion** — fits when source footage dominates and support layers are React scene components (chart, callout, text card). Remotion composes video clips + React overlays in one pass via `<OffthreadVideo>`.
   - **HyperFrames** — fits when support layers are HTML/GSAP-native (kinetic callouts, registry blocks, typographic overlays) and source footage is embedded as `<video class="clip">`.
2. Recommend one with rationale tied to the anchor medium and the shape of the support layer.
3. Wait for explicit user approval.
4. Log the choice in `decision_log` as a `render_runtime_selection` decision with BOTH runtimes in `options_considered`.

A `render_runtime_selection` decision with only one runtime in `options_considered` when both were available is a CRITICAL reviewer finding.

## Reference Inputs

- `docs/hybrid-video-best-practices.md`
- `skills/creative/storytelling.md`
- `skills/creative/video-editing.md`

## Process

### 1. Choose The Anchor Medium

Pick the storytelling anchor:

- `talking_head`
- `broll_footage`
- `screen_recording`
- `still_sequence`
- `narration_led_graphics`

### 2. Define Support Layers

Possible support layers:

- subtitles,
- diagrams,
- code visuals,
- stat cards,
- generated inserts,
- narration,
- music.

Each support layer should solve a specific problem, not just decorate the timeline.

### 3. Decide The Deliverable Mix

Common outputs:

- hero cut,
- vertical cutdown,
- square cutdown,
- chaptered version,
- ad variant.

### 4. Build The Brief

Recommended metadata keys:

- `anchor_medium`
- `source_inventory`
- `support_layers`
- `deliverable_mix`
- `missing_capabilities`
- `fallback_policy`

### 5. Quality Gate

- the anchor medium is explicit,
- support layers are justified,
- the deliverable mix fits the source inventory,
- missing capabilities are surfaced early.

## Common Pitfalls

- Calling everything hybrid without defining a primary medium.
- Planning support layers before understanding the source.
- Treating optional generated inserts as guaranteed.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
