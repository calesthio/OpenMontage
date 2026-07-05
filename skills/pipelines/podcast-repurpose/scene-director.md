# Scene Director - Podcast Repurpose Pipeline

## When To Use

You are deciding how each podcast deliverable should look based on the actual source mode. This is where you prevent "fake richness" and choose honest, effective treatments.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Highlight set and source truth |
| Tools | `frame_sampler` | Optional visual inspection for video-podcast sources |
| Playbook | Active style playbook | Brand consistency |

## Process

### 1. Pick The Right Treatment Per Deliverable

Prefer a source-faithful hierarchy:

- if video podcast footage exists, use speaker-led scenes first,
- if only audio exists, use audiogram or quote-led layouts,
- if branding assets are limited, keep the visual system simple and repeatable.

### 2. Avoid Pretend Complexity

Do not plan a full episode with endless generated topic art unless the budget and tools support it. A clean branded companion layout is better than a noisy, underpowered pseudo-production.

### 3. Define Scene Families

Useful schema scene types:

- `talking_head` for source video speaker shots
- `text_card` for quote cards and chapter cards
- `generated` for optional topic art
- `diagram` for the rare cases where the discussion needs a graphic
- `transition` for chapter moves

### 4. Use Metadata For Layout Strategy

Recommended `scene_plan.metadata` keys:

- `deliverable_layouts`
- `speaker_card_rules`
- `quote_card_rules`
- `audiogram_rules`
- `full_episode_companion_rules`

### 5. Plan Safe Zones And Attribution

Every layout should clearly preserve:

- speaker attribution,
- subtitle zone,
- show branding,
- CTA or episode reference area if needed.

### 6. Quality Gate

- each deliverable has a treatment that matches the actual source,
- source video is used when it exists instead of being hidden behind generic graphics,
- audio-only assets remain visually simple and readable,
- long-form companion visuals are achievable.

## Common Pitfalls

- Planning speaker-centric layouts for audio-only episodes.
- Turning every clip into the same waveform-plus-logo composition.
- Using generated graphics to cover weak editorial choices.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
