# Idea Director - Documentary Montage Pipeline

## When To Use

You are turning a user prompt into the brief artifact that every
downstream stage will read. For this pipeline, the brief is the
thematic core: what the montage is ABOUT, what it should feel like,
and how long it should run.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/brief.schema.json` | Artifact validation |
| User input | Conversation history | The raw ask |
| Meta | `skills/meta/reviewer.md` | Self-review pass |

## Process

### 1. Extract The Thematic Question

A documentary montage answers a question the user could not put into
a sentence. Your job is to name that question in ONE line.

Good thematic questions:

- "What does it feel like to come home?"
- "How did the 20th century think about the future?"
- "What happens in a city at 4am?"
- "What do all the footprints on Earth look like?"

Bad thematic questions (too abstract or too concrete):

- "A video about cities" (too abstract — no feeling)
- "A montage with 8 specific shots of the moon" (too concrete — that's
  a shot list, not a theme)

### 2. Fix The Tone

Choose ONE emotional register. Write it down. Everything downstream
keys off this.

Common registers for this pipeline:

- **elegiac** — long holds, muted color, slow cuts (loss, memory, home)
- **urgent** — short cuts, hard sync, motion-heavy (crisis, cities, now)
- **reverent** — stately, symmetrical, patient (nature, ritual, scale)
- **wry** — ironic juxtaposition, cut on absurdity (consumer culture,
  politics, mid-century optimism)
- **dreamlike** — slow dissolves, repeated motifs, non-linear (childhood,
  grief, memory)

### 3. Pick A Duration And A Shape

Duration matters because it caps the number of beats.

| Duration | Beats | Use |
|----------|-------|-----|
| 30-45s | 8-12 cuts | Social/Instagram/reel — one feeling, no arc |
| 60-90s | 15-25 cuts | Standard short — mini arc with a turn |
| 2-3 min | 30-50 cuts | Proper essay montage — 3-act arc possible |

Shape options:

- **single-image expansion** — one idea, held from many angles (good
  for elegiac pieces under 60s)
- **before/after** — first half establishes, second half turns (good
  for wry or urgent registers)
- **three-act** — setup → turn → release (the Adam Curtis move, needs
  >90s)
- **list/catalogue** — "everyone who..." structure, no arc, just
  accumulation (good for reverent or elegiac)

### 4. Note Music Intent (MANDATORY)

Documentary montage is inseparable from its music bed. **Music is MANDATORY
for this pipeline.** The ONLY way out is an explicit user opt-out (e.g.
"no music, I want it silent") — which MUST be recorded as
`music_plan.source = "none"` with a `music_plan.opt_out_reason` field.

Silent-by-design briefs that feel "pure" at the idea stage regularly look
like abandoned footage at compose time. Do not assume silence will earn
itself. If the user has not mentioned music, ASSUME THEY WANT IT and pick:

- user-provided track (put path in `music_plan.source_path`),
- music library pick (list what's in `music_library/`),
- generated (name the tool and prompt seed with register),
- explicit opt-out (`source: "none"` + `opt_out_reason`).

**Warn the user if no music source is available.** Do not silently
defer this — it becomes an expensive surprise at the asset stage.

### 5. Note End-Tag Intent (MANDATORY)

Every documentary-montage film closes on a philosophical end-tag — one
short, abstract line that gives the whole thing meaning. It is rendered
as a Remotion end-card ("shining underlined tag" register — bold weight,
letter-spaced, animated underline).

**Default mode is `"overlay"`** — the tag fades in over the final scenes
of the body footage, so it feels like part of the film rather than a
separate card tacked on at the end. The alternative is `"concat"` which
appends a standalone black-card after the body. Use concat only when the
user explicitly asks for a separated title card, or when the final
footage is too visually busy for legible text overlay.

**End-tag is MANDATORY.** The ONLY way out is an explicit user opt-out
recorded as `end_tag_plan: null` with an `end_tag_opt_out_reason` field.

Propose the end-tag at the brief stage. Write 3 options and recommend one.
Expected shape:

```json
{
  "end_tag_plan": {
    "text": "WE BUILT BOTH WITH THE SAME HANDS.",
    "palette": "warm_ivory_on_black",
    "duration_seconds": 5.5,
    "render_engine": "remotion",
    "component": "EndTag",
    "mode": "overlay"
  }
}
```

Fields:
- `text` — 3-9 words. A thesis, not a summary.
- `palette` — `"cool_offwhite_on_black"` or `"warm_ivory_on_black"`.
- `duration_seconds` — total tag screen time (fade-in + hold + fade-out).
  5-8s is the sweet spot.
- `render_engine` — always `"remotion"`.
- `component` — always `"EndTag"`.
- `mode` — `"overlay"` (default) or `"concat"`.
  - **overlay**: tag rendered as ProRes 4444 with alpha → composited on
    final body footage via FFmpeg overlay filter. Tag fades appear over
    the last N seconds of live footage. The body's own fade-out and the
    tag's fade-out should align.
  - **concat**: tag rendered as opaque MP4 → appended after body via
    FFmpeg concat. Total output duration = body + tag.

### 6. Note Narration Intent (OPTIONAL)

Unlike music and end-tag, narration is OPTIONAL. Absence is fine if
visuals + music + end-tag carry the register. If narration IS used, name
the TTS provider and voice. Record `narration: "none"` explicitly if
there's no narration — don't leave the field missing.

### 7. Record The Brief

Minimum fields the brief must carry:

```json
{
  "topic": "A minute in the rain",
  "thematic_question": "What does rain show you about a city?",
  "tone": "elegiac",
  "duration_seconds": 90,
  "shape": "list",
  "sources_allowed": ["pexels", "pixabay_video", "coverr", "mixkit", "archive_org", "nara", "nasa"],
  "generated_clips_allowed": false,
  "narration": "none",
  "music_plan": {
    "source": "generated",
    "provider": "elevenlabs",
    "prompt_seed": "slow ambient drone in A minor, no percussion, 60s sustained swell, Max Richter register"
  },
  "end_tag_plan": {
    "text": "THE CITY KEEPS ITS OWN VIGIL.",
    "palette": "cool_offwhite_on_black",
    "duration_seconds": 5.5,
    "render_engine": "remotion",
    "component": "EndTag"
  },
  "era_mix": "any",
  "target_platform": "social_short"
}
```

`era_mix` is a documentary-specific field: "modern" biases toward
Pexels, "vintage" biases toward Archive.org Prelinger, "any" leaves it
open for the scene director to decide per slot.

### 8. Quality Gate

- Thematic question is ONE sentence.
- Tone is ONE register from the fixed list.
- Duration and shape are concrete numbers / enum values.
- `music_plan` is present AND either names a real source OR has
  `source: "none"` + `opt_out_reason` (explicit user decision).
- `end_tag_plan` is present AND either has a non-empty `text` OR is
  `null` with `end_tag_opt_out_reason` (explicit user decision).
- Sources list is non-empty and at least one requested source is
  `available` per `corpus_builder.source_provider_menu` surfaced in
  preflight.

## Common Pitfalls

- Stating multiple themes ("it's about cities AND technology AND loss").
  Pick one. The others become downstream associations.
- Jumping to shot lists. The brief is about MEANING. Shots come next.
- Ignoring duration. A 45s piece with 50 cuts is nausea. A 3-minute
  piece with 12 cuts is a slideshow.
- Forgetting to ask about music. The user usually has an opinion.
- Assuming silence will earn itself. It won't. Music is mandatory unless
  the user explicitly says no.
- Skipping the end-tag because "the images speak for themselves". They
  don't — the end-tag is the thesis. Propose one every time.
