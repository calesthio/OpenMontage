# Asset Director - Podcast Repurpose Pipeline

## When To Use

This stage builds the reusable kit for podcast-derived video assets: subtitles, speaker cards, quote cards, optional topic art, and optional music support.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Deliverable plan and transcript truth |
| Tools | `subtitle_gen`, `image_selector`, `diagram_gen`, `music_gen`, `audio_enhance` | Asset generation |
| Playbook | Active style playbook | Brand consistency |

## Process

### 1. Start With Mandatory Assets

Highest priority:

- subtitles for every clip,
- clean audio where needed,
- speaker attribution assets if multiple speakers appear,
- quote-card templates for quote-led outputs.

### 1b. Hero Scene Sample (Mandatory)

Before batch asset generation:
1. Identify the hero clip (the most important or impactful clip in the batch)
2. Generate ONE sample asset for that clip (subtitle style, speaker card, or quote card)
3. Present it: "This is the visual direction for the most important clip. Does this match what you're imagining? I'll generate the rest in this style."
4. Wait for approval before proceeding to batch generation

This prevents the most expensive mistake: generating 10+ assets in a direction the user doesn't like.

### 2. Treat Topic Graphics As Optional

Generated graphics should support the batch, not dominate it. Use them only when:

- the topic truly benefits from a clarifying image,
- the episode companion needs chapter separation,
- the budget can support consistent outputs.

### 3. Use Templates, Not Reinvention

Prefer reusable templates for:

- speaker cards,
- quote cards,
- end cards,
- brand containers.

### 4. Store Rich Asset Truth In Metadata

Recommended metadata keys:

- `speaker_assets`
- `subtitle_assets`
- `quote_card_assets`
- `topic_graphics`
- `music_assets`

### 5. Quality Gate

- all clips have subtitle assets,
- speaker identity is visually consistent,
- quote-card text remains mobile-readable,
- optional generated art stays within budget and style constraints.

### Mid-Production Fact Verification

If you encounter uncertainty during asset generation:
- Use `web_search` to verify visual accuracy of subjects (e.g. what does this building actually look like?)
- Use `web_search` to find reference images before generating illustrations
- Log verification in the decision log: `category="visual_accuracy_check"`

Visual accuracy matters. If the script mentions a specific place, person, or object,
verify what it actually looks like before generating images. Don't rely on
the AI model's training data — it may be wrong or outdated.

## Common Pitfalls

- Spending budget on optional art before subtitles and attribution assets are complete.
- Creating inconsistent speaker cards across the same episode.
- Overproducing topic graphics for long-form companion videos.


## When You Do Not Know How

If you encounter a generation technique, provider behavior, or prompting pattern you are unsure about:

1. **Search the web** for current best practices — models and APIs change frequently, and the agent's training data may be stale
2. **Check `.agents/skills/`** for existing Layer 3 knowledge (provider-specific prompting guides, API patterns)
3. **If neither helps**, write a project-scoped skill at `projects/<project-name>/skills/<name>.md` documenting what you learned
4. **Reference source URLs** in the skill so the knowledge is traceable
5. **Log it** in the decision log: `category: "capability_extension"`, `subject: "learned technique: <name>"`

This is especially important for:
- **Video generation prompting** — models respond to specific vocabularies that change with each version
- **Image model parameters** — optimal settings for FLUX, GPT Image, Imagen differ and evolve
- **Audio provider quirks** — voice cloning, music generation, and TTS each have model-specific best practices
- **Remotion component patterns** — new composition techniques emerge as the framework evolves

Do not rely on stale knowledge. When in doubt, search first.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
