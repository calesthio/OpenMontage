# Intent Analyst — Meta Skill

## When to Use

Run on **every NEW production-initiating request**, at Rule Zero step 1, *before* you
identify a pipeline. It decomposes the request into explicit + implicit sub-intents and
produces an informal `intent_map` that routes the request.

**Do NOT run intent-analyst for:**

- **Refinement requests during an in-flight pipeline** ("change the music", "make it
  longer", "swap that clip"). The active stage handles these — never re-route a
  production that's already underway.
- **Exploratory / capability questions** ("what can you do?", "show me an example").
  Those go to `onboarding`, not here.
- **Non-production utilities** (pure transcript fetch, "just download this video").

This skill is the universal *router*: it does the thinking, but never interrogates the user and never generates creative concepts.

## Role Boundary (do not duplicate these skills)

| Skill | Answers | When |
|-------|---------|------|
| `onboarding` | "What can this setup do?" | First contact / vague exploratory |
| `video-reference-analyst` | "What is this reference video doing?" | A reference URL/file is given |
| **`intent-analyst`** (this) | **"Which pipeline(s) + capabilities does this request need?"** | **Every new actionable request** |
| `creative-intake` | "What's missing from the brief?" | After routing, before research |

**Hard rule:** intent-analyst **never asks the user a question**. Unknowns go into
`open_ambiguities`; `creative-intake` resolves them later. Do not pre-empt its job.

## The `intent_map`

Informal context (like `creative-intake`'s `intake_brief`) — **not** a schema-validated
artifact. Six fields:

- `explicit_intents` — what the user stated outright.
- `implicit_intents` — what's implied (platform → aspect ratio, hook, music, duration
  norms, narration yes/no, tone).
- `routed_pipelines` — 1 pipeline normally; `[]` when nothing fits (see No-Match).
- `capability_needs` — capability families likely required (tts, image_generation,
  video_generation, music_generation, …). **Provisional only.**
- `open_ambiguities` — gaps for `creative-intake` to close. Never ask them here.
- `confidence` — `high` | `medium` | `low` (see Confidence).

## Protocol

1. **Explicit intents** — read the request literally. Works in any language; the user's
   default is **Vietnamese** — parse VI directly and map to the English pipeline names.
2. **Implicit intents** — infer the unstated: platform → aspect ratio + duration norm,
   need for a hook, narration, music, tone.
3. **Route** — match against the **"Available Pipelines" / "Best For" table in
   `AGENT_GUIDE.md`, read at runtime**. Do not rely on memory or any list baked into this
   file — pipelines change. Pick the single best-fit pipeline.
4. **Capability needs** — list the capability families the pipeline will likely use.
   **These are provisional** — intent-analyst never promises a capability is available;
   preflight (Rule Zero step 4) is the authoritative check. Do not claim a pipeline will
   run before preflight confirms it.
5. **Open ambiguities** — note what's unclear (topic depth, exact duration, narration).
   Hand to `creative-intake`; do not ask.
6. **Confidence** — set per the rule below.

## Confidence + Fast-Path

`confidence: high` means **exactly one pipeline fits AND platform, duration, and visual
treatment are all clear.** Anything less is `medium` or `low`.

- **high →** state the route in one line and proceed straight to pipeline selection. No
  question.
- **medium / low →** present the route briefly and fold a single confirmation into the
  same turn that transitions to `creative-intake`. **One turn, not two rounds of Q&A.**

## No-Match

If no pipeline fits (e.g. audio-only podcast with no video, a meme GIF, a still image),
set `routed_pipelines: []`, say so plainly, and suggest the closest pipeline or state that
OpenMontage doesn't cover it. **Never force-fit a wrong pipeline.**

## Compound Requests (v1 = detect + suggest)

When the request implies **2+ independent deliverables** (e.g. "a long-form video AND 3
shorts cut from it"):

- **Detect** it and **suggest running the pipelines sequentially as separate runs** — each
  its own full Rule Zero, reusing the same `projects/<name>/`.
- **Always confirm with the user**, regardless of confidence.
- intent-analyst does **NOT** auto-orchestrate a chain. Automated cross-pipeline chaining
  is out of scope for v1.

## Handoff

Pass the `intent_map` to pipeline selection and to `creative-intake`. `creative-intake`
consumes `open_ambiguities` and must **not** re-decompose intent.

## Examples (illustrative only — real routing reads the AGENT_GUIDE table)

**Fast-path (high confidence):** *"Make a 60s animated explainer about black holes for
YouTube."*
```
explicit_intents: [60s explainer, topic=black holes, platform=YouTube]
implicit_intents: [16:9, hook in first 3s, narration, light bg music]
routed_pipelines:  [animated-explainer]
capability_needs:  [tts, image_generation|video_generation, music_generation]  # provisional
open_ambiguities:  [visual style preference]
confidence: high
```

**Compound (always confirm):** *"Làm video thiền 10 phút có nhạc nền, rồi cắt 3 short cho TikTok."*
```
explicit_intents: [10-min meditation video + music, then 3 TikTok shorts]
implicit_intents: [long-form 16:9 + narration + ambient music; shorts 9:16 from the long-form]
routed_pipelines:  [animated-explainer-or-animation, then clip-factory]  # SUGGEST sequential
capability_needs:  [tts, music_generation, image_generation|video_generation]  # provisional
open_ambiguities:  [meditation script source, voice choice]
confidence: medium   # compound → confirm regardless
```

## Anti-Patterns

- Don't interrogate the user (that's `creative-intake`) or generate concepts (that's the `idea`/proposal stage).
- Don't hardcode or trust a baked-in pipeline list — read the AGENT_GUIDE table at runtime.
- Don't slow down a clear request — high confidence means proceed.
- Don't promise a capability before preflight verifies it.
- Don't re-route a production that's already running.
