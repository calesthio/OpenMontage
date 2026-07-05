# Idea Director - Cinematic Pipeline

## When To Use

Use this pipeline for trailers, brand films, dramatic montages, or mood-led short videos where rhythm, atmosphere, and emotional escalation matter more than direct explanation.

Do not use this pipeline just because the user said "make it look cinematic." If the project is really a screen demo, explainer, or repurposing job, route it there instead.

## Reference Inputs

- `docs/cinematic-best-practices.md`
- `skills/creative/cinematic.md`
- `skills/creative/storytelling.md`

## Process

### 1. Classify The Source Reality

Capture the source mode:

- `footage_only`
- `footage_plus_stills`
- `still_led`
- `generated_support`
- `mixed_montage`

Also classify whether the requested delivery is motion-required. Store this as a boolean in `brief.metadata.motion_required`.

Set `motion_required = true` when the promise of the video depends on moving shots or animated compositions rather than static frames. This includes:

- sci-fi trailers,
- cinematic teasers,
- action or hype edits,
- agent/avatar outputs,
- any concept whose quality depends on generated video clips.

Do not assume stock, generated b-roll, or music exists unless the user has provided it or the environment can actually make it.

### 2. Define The Emotional Arc

Choose the arc in plain language:

- tension -> reveal
- wonder -> scale
- intimacy -> payoff
- urgency -> resolution
- mystery -> CTA

The brief should tell later stages what the video is trying to make the viewer feel, not just what it is about.

### 3. Pick The Delivery Shape

Common output shapes:

- `teaser`
- `trailer`
- `hero_brand_film`
- `mood_cut`
- `social_cutdown`

Store longer planning detail in `brief.metadata`.

Recommended metadata keys:

- `source_mode`
- `motion_required`
- `delivery_shape`
- `emotional_arc`
- `anchor_assets`
- `music_strategy`
- `generated_support_level`
- `aspect_ratio_plan`
- `rights_constraints`

### 4. Reality Check The Treatment

If the user has weak source media and no generation path, say so. A cinematic result still needs enough visual or audio material to carry mood.

If `motion_required = true`, be explicit about the motion path:

- confirm the planned clip-generation providers,
- confirm whether Remotion is required for the intended composition,
- if either is unavailable or unstable, mark the treatment as blocked rather than silently redesigning it around still images.

### 5. Music Plan (Mandatory)

Cinematic videos live and die by their audio. **Surface the music situation before the user approves the brief.**

Check availability in this order:

1. **User music library (`music_library/`):** Check if this folder exists and contains tracks. List available tracks with durations and moods. Let the user choose.
2. **Music generation APIs:** Check `registry.get_by_capability("music_generation")`. Report status, quota, and cost per track.
3. **Royalty-free sources:** Note that the user can provide a track from YouTube Audio Library, Jamendo, or other free sources by dropping it in `music_library/`.

Present explicit options:

```
MUSIC PLAN
├── Your music library: [N tracks / empty]
├── AI generation: [provider] — [AVAILABLE/UNAVAILABLE] [cost]
└── Bring your own: Drop a track in music_library/ before asset stage

Options:
  (a) Use a library track (which one?)
  (b) Provide your own track
  (c) Generate via API (if available)
  (d) Proceed without music (not recommended for cinematic)
```

Record the decision in `brief.metadata.music_strategy` with the chosen source and path/prompt.

### 6. Quality Gate

- the source truth is explicit,
- the brief says whether motion is a hard requirement,
- the emotional arc is specific,
- the output shape fits the available assets,
- the music plan is resolved (source chosen or explicitly deferred),
- the treatment is cinematic for a reason, not by label only.

## Common Pitfalls

- Calling something cinematic when it is really just a normal edit with black bars.
- Assuming generated inserts are available without checking tools.
- Quietly turning a motion-led brief into a still-led teaser.
- Planning a trailer shape with no reveal or payoff.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
