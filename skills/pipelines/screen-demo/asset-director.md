# Asset Director - Screen Demo Pipeline

## When To Use

This stage produces the minimal but high-leverage assets that make a screen demo easier to follow: subtitles, audio cleanup, reusable overlays, masks, and optional light-weight support cards.

## Two production modes — pick before generating assets

**Read the brief's `production_mode` field.** If `idea` didn't set one, decide here:

| Mode | When | Asset production looks like |
|---|---|---|
| **`real_capture`** | Real app UI (browser, design tool, IDE with plugins); live behavior; user asked for their own screen recorded | Clean audio + subtitles + callout overlays (arrows, highlight masks) applied on top of the captured MP4 |
| **`synthetic_terminal`** | CLI, terminal, install flow, make targets, git/npm commands, `.env` config — anything scriptable | **No capture at all.** Author a `terminal_scene` cut for `video_compose` (Remotion). Commands type char-by-char, output scrolls, pills announce completions. See `.agents/skills/synthetic-screen-recording/SKILL.md`. |

**Mode selection heuristic:** *"Can I predict every command and its output before shooting?"* If yes → synthetic. If no → real capture.

For synthetic mode, the asset stage produces:
- **narration (tts_selector)** aligned to the exact video-time each command should type
- **a `steps` list** (cmd/out/pause/pill primitives) that paces with narration cues
- **a pacing verification** via `lib.verify_scene_pacing.assert_alignment(...)` — must pass before render
- **no** screen-recorder footage, no callout arrows, no zoom-crop regions (those are real-capture concepts)

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | What to produce |
| Tools | `subtitle_gen`, `audio_enhance`, `tts_selector`, `image_selector`, `diagram_gen` — selectors auto-discover all available providers from the registry | Generation capabilities |
| Playbook | Active style playbook | Typography and overlay styling |

## Process

### 1. Prioritize Utility Over Decoration

Screen demos do not need a large asset pile. They need the right few assets:

- mandatory: subtitles
- usually mandatory: cleaned primary audio
- usually helpful: reusable highlight box, arrow, step label, blur mask kit
- optional: one intro card, one outro card, sparse diagram overlays
- optional only if preflight allows it: generated narration for silent recordings

### 1b. Hero Scene Sample (Mandatory)

Before batch asset generation:
1. Identify the hero scene (the most important step or interaction in the demo)
2. Generate ONE sample asset for that scene (subtitle style, highlight overlay, or intro card)
3. Present it: "This is the visual direction for the most important step. Does this match what you're imagining? I'll generate the rest in this style."
4. Wait for approval before proceeding to batch generation

This prevents the most expensive mistake: generating 10+ assets in a direction the user doesn't like.

### 2. Generate Subtitles First

Rules:

- high contrast over unknown UI backgrounds,
- never cover the text the viewer needs to read,
- prefer phrase-level chunks unless word-by-word highlighting materially helps,
- prepare position override notes in `asset_manifest.metadata.subtitle_zones`.

### 3. Build A Reusable Overlay Kit

Do not generate bespoke assets for every click. Build a small shared kit:

- `highlight_box_primary`
- `arrow_primary`
- `step_label_primary`
- `keystroke_badge_primary`
- `blur_mask_template`

These should be reusable across scenes, with timing and placement handled downstream.

### 4. Clean Or Generate Audio Pragmatically

Goals:

- remove distracting keyboard and room noise,
- normalize speech,
- preserve timing,
- do not over-process into robotic audio.

If the recording is silent:

- only generate narration if TTS passed preflight,
- otherwise keep the asset plan text-led and note the limitation in metadata.

### 5. Only Generate Supplementary Visuals When They Earn It

Use `image_selector` or `diagram_gen` only for:

- a short opening card,
- a step transition card,
- a simple diagram that clarifies a hidden process,
- an outro card.

Do not create decorative artwork for a workflow the screen already explains.

### 6. Build The Asset Manifest Cleanly

Every asset must have a valid schema type and `scene_id`.

Use `asset_manifest.metadata` for details like:

- `subtitle_zones`
- `overlay_kit`
- `audio_settings`
- `narration_mode`
- `sensitive_regions`

### 7. Quality Gate

**Existence check:**
- [ ] Subtitle file exists at declared path and parses without errors
- [ ] Cleaned audio file exists and has the expected duration
- [ ] Reusable overlay kit exists and covers planned callout types
- [ ] All supplementary visuals exist at declared paths

**Timing check:**
- [ ] Subtitle timestamps align with script section timestamps
- [ ] If narration was generated, timing matches section duration closely enough for editing

**Quality check:**
- [ ] Subtitles are readable at output resolution
- [ ] Cleaned audio has no remaining distracting noise
- [ ] Callout colors have sufficient contrast
- [ ] Blur masks fully cover the sensitive content

### Mid-Production Fact Verification

If you encounter uncertainty during asset generation:
- Use `web_search` to verify visual accuracy of subjects (e.g. what does this building actually look like?)
- Use `web_search` to find reference images before generating illustrations
- Log verification in the decision log: `category="visual_accuracy_check"`

Visual accuracy matters. If the script mentions a specific place, person, or object,
verify what it actually looks like before generating images. Don't rely on
the AI model's training data — it may be wrong or outdated.

## Common Pitfalls

- Generating too many one-off overlay files instead of a reusable kit.
- Using subtitles that sit directly on top of terminal output or bottom navigation.
- Assuming silent recordings will magically gain narration without checking TTS.
- Spending image generation budget on visuals the raw screen already provides.


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
