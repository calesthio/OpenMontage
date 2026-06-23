# Asset Director — Explainer Pipeline

## When to Use

You are the Asset Producer for a generated explainer video. You have a `scene_plan` with required assets and a `script` with narration text. Your job is to generate every asset needed: narration audio, images, diagrams, code snippets, and background music. Every file must exist on disk before you finish.

This is where plans become real files. A missing or low-quality asset will torpedo the final video.

## Animation authoring — which runtime

Before authoring any animated Remotion component for this pipeline, read **`skills/meta/animation-runtime-selector.md`**. It's the routing authority for deciding between Remotion primitives and GSAP plugins.

Quick routing for common explainer needs:

| Scene type | Recommended approach |
|---|---|
| Title card, fade, slide, scale | Remotion primitives — `interpolate()` + `spring()` |
| Word-level caption highlight synced to narration | Existing `CaptionOverlay` component (already in `remotion-composer/src/components/`) |
| Per-character kinetic typography ("words explode in one letter at a time") | GSAP SplitText — read `.agents/skills/gsap-plugins/SKILL.md` |
| Multi-step choreography across 4+ tweens | GSAP timeline — read `.agents/skills/gsap-timeline/SKILL.md` |
| Logo build (line drawing, stroke reveal) | GSAP DrawSVG — read `.agents/skills/gsap-plugins/SKILL.md` |
| Data chart (bar/line/pie/KPI) | Remotion built-in chart components — see `remotion-composer/SCENE_TYPES.md` |
| Terminal or CLI demo | Remotion TerminalScene — read `.agents/skills/synthetic-screen-recording/SKILL.md` |

**The keep-it-simple bias:** if Remotion primitives solve a scene in ≤ 20 lines, use them. Only pull in GSAP when the plugin genuinely earns its bundle weight.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["proposal"]["proposal_packet"]` | What to produce |
| Playbook | Active style playbook | Image prompts, diagram style, audio preferences |
| Tools | `tts_segment_lab`, `tts_selector`, `image_selector`, `video_selector`, `diagram_gen`, `code_snippet`, `music_gen` — selectors auto-discover all available providers from the registry | Audition and generation capabilities |
| Cost tracker | `tools/cost_tracker.py` | Budget governance |

## Process

### Step 1: Inventory Required Assets

Walk every scene in the scene plan. For each `required_assets` entry, create an asset task:

```
Asset Task:
  scene_id: scene-3
  type: diagram
  description: "Mermaid flowchart: query -> encode -> search -> rank -> return"
  source: generate
  tool: diagram_gen
  estimated_cost: $0.00
```

Also create tasks for:
- **Narration audio** — one per script section (reuse `tts_segment_lab` selections when present; otherwise use `tts_selector` or a concrete TTS provider)
- **Background music** — one track for the whole video (use `music_gen` or select from library)
- **Sound effects** — per playbook's `sfx_style` (optional, use `music_gen` or stock)

### Step 2: Check Budget

Before generating anything:
1. Sum all estimated costs from the asset tasks
2. Compare against the cost tracker's remaining budget
3. If over budget:
  - Switch expensive tools to cheaper alternatives (use `tts_selector` with `preferred_provider` to route to cheaper TTS; use `image_selector` to route to cheaper image providers)
   - Reduce image count (combine similar scenes)
   - Skip optional assets (SFX, B-roll)
4. Get cost approval via cost tracker before proceeding

### Step 2b: Sample Preview (Prevents Wasted Spend)

Before batch-generating assets, produce one sample of each expensive asset type and present them to the user for approval:

1. **TTS audition**: If the project is generated-narration-led and the script contains TTS audition cues or voice-sensitive sections, run `tts_segment_lab` first. Compare provider/voice/parameter variants, write `review.md`, optionally run `analyze` for duration/energy/timing-hint checks, ask the user to review `compare.html`, then run `annotate` with their submitted review. If `next_operation=apply_review`, generate a follow-up audition page and ask the user to review that page. Repeat this loop as many times as needed until `review_complete=true` and the final `selection.json` exists.
2. **TTS sample**: If no audition is needed, generate narration for the first script section only. Play it for the user. Confirm voice, pace, and tone are acceptable before generating the rest.
3. **Image sample**: Generate one image for the most representative scene. Show it to the user. Confirm the style, quality, and prompt approach before batch-generating all images.
4. **Music sample** (if using `music_gen`): Generate one short clip. Confirm mood and energy before committing.

Do not run `tts_segment_lab` blindly. Skip it when the voice is source footage,
human-recorded, already approved, or when the video is mostly music/SFX-led.
Use it only when a user-visible choice between TTS providers, voices, or
delivery parameters is still useful.

If the user rejects a sample:
- Adjust the parameters (voice, prompt style, provider) and regenerate the sample.
- For TTS Segment Lab reviews, prefer `apply_review` so the original review is
  preserved and the next `compare.html` shows what changed. Keep iterating
  until the user has approved one candidate for every reviewed segment; do not
  use partial or pending-review selections as production narration.
- Do not batch-generate until the sample is approved.
- Max 3 sample iterations per non-TTS asset type before escalating to the user
  for a decision.

This step typically costs $0.03–0.08 total and prevents $1–3 of wasted generation.

### Step 3: Generate Narration

Before generating narration, check whether a `tts_segment_lab` `selection.json`
exists for this project. If it exists, reuse the selected audio for matching
sections and include those files in the asset manifest. For sections without a
selection, generate narration normally.

For each script section that still needs narration:
1. Extract the narration text
2. Apply speaker directions from the script (pace, emphasis, emotion)
3. Apply the playbook's `audio.voice_style`
4. Generate using `tts_selector` — it auto-routes to the best available TTS provider based on user preference and availability. Check the registry's `best_for` fields to understand each provider's strengths.
5. Verify the audio file exists and duration matches expected timing (±15%)

**Pronunciation guide**: If the script contains technical terms, jargon, or names with non-obvious pronunciation, include a pronunciation map in the TTS request.

### Step 4: Generate Visual Assets

Process asset tasks grouped by tool for efficiency:

**Images (`image_selector`)**:
1. Build the prompt from the scene's actual purpose:
   - scene-specific shot/lighting/texture cues from `shot_language`, `shot_intent`, and `texture_keywords`
   - an adapted visual anchor from the playbook or custom identity
   - the concrete subject/action/environment
   Use `lib/shot_prompt_builder.py` when helpful.
2. Add negative prompt from playbook
3. Include consistency anchors (same character/world/palette family), but do NOT reuse the exact same phrasing for every image
4. Generate and verify the file exists
5. If the result doesn't match expectations, refine the prompt and regenerate (max 2 retries)

**Diagrams (`diagram_gen`)**:
1. Convert the scene description into valid Mermaid syntax
2. Apply playbook's `asset_generation.diagram_style`
3. Generate SVG/PNG
4. Verify all nodes and edges are present

**Code snippets (`code_snippet`)**:
1. Extract language and code from the scene description
2. Apply syntax highlighting theme from playbook's overlay styles
3. Generate highlighted image or Remotion-compatible data

### Step 5: Generate Music

1. Read playbook's `audio.music_mood` and `audio.music_volume`
2. Check the music decision from `proposal_packet.production_plan.music_source` (set by the Proposal Director)
3. Source the background track in this priority order:
   - **User-selected library track**: If the proposal specified a track from `music_library/`, copy it to `projects/<project>/assets/music/background_music.mp3`
   - **User music library (`music_library/`)**: If the folder exists and has tracks, pick the best match for the playbook's `audio.music_mood`. List candidates by filename and let the EP decide.
   - **Music generation API**: Use `music_gen` (ElevenLabs) or `suno_music` if available. Check status via registry first — if the tool is unavailable or quota-exhausted, skip immediately (do NOT attempt and fail silently).
   - **No music available**: Log this clearly in the asset manifest as `"music_status": "unavailable"` with the reason. Do NOT silently produce a video without music — the EP and user should know.
4. Duration should be at least as long as total video duration. If shorter, it can be looped by the compose stage.
5. Verify the audio file exists at `projects/<project>/assets/music/background_music.mp3`

**Critical:** If music generation fails or is unavailable, report it immediately in the asset manifest — do not defer the problem to the compose stage.

### Step 6: Build Asset Manifest

Assemble all generated assets into the manifest:

```json
{
  "version": "1.0",
  "assets": [
    {
      "id": "narration-s1",
      "type": "audio",
      "subtype": "narration",
      "path": "assets/narration/s1.mp3",
      "source_tool": "tts_selector",
      "scene_id": "scene-1",
      "duration_seconds": 8.2,
      "cost_usd": 0.003
    },
    {
      "id": "img-scene-3",
      "type": "image",
      "path": "assets/images/scene-3-diagram.png",
      "source_tool": "diagram_gen",
      "scene_id": "scene-3",
      "cost_usd": 0.00
    },
    {
      "id": "music-bg",
      "type": "audio",
      "subtype": "music",
      "path": "assets/music/background.mp3",
      "source_tool": "music_gen",
      "duration_seconds": 62,
      "cost_usd": 0.05
    }
  ],
  "total_cost_usd": 0.053,
  "generation_summary": {
    "narration_sections": 5,
    "images_generated": 8,
    "diagrams_generated": 2,
    "music_tracks": 1
  }
}
```

### Pre/Post Self-Review for Generation Prompts

> Before sending a prompt to any generation tool — `image_selector`, `diagram_gen`, `video_selector`, even `code_snippet` styling prompts — run a three-step self-review modeled on the CHAI oversight loop ("Building a Precise Video Language with Human-AI Oversight", arXiv 2604.21718v2). Cost is small (no extra tool calls); benefit is large (avoids wasted generations). This applies just as strongly to `diagram_gen` Mermaid prompts and `image_selector` illustration prompts as it does to video generation — bad explainer visuals fail in the same way: missing subject, missing framing, vague "make it look educational."
>
> **Step 1 — Pre-caption pass.** Write the prompt the way you'd write it today. Do not over-edit; aim for a complete first draft.
>
> **Step 2 — Critique pass.** Score the draft against the 5-aspect checklist (Subject / Subject Motion / Scene / Spatial Framing / Camera). For each aspect:
> - Is it specified? If not, is the omission deliberate (e.g., "Camera N/A — Remotion native scene", "no subject motion — static diagram") or accidental?
> - Are confusable terms disambiguated? (dolly vs zoom, pan vs truck, bird's-eye vs aerial, fisheye vs barrel, full shot vs close-up; for diagrams: flowchart vs sequence vs state diagram, top-down vs left-right)
> - Are emotional adjectives ("clean", "professional", "modern") replaced with their visual causes (sans-serif typography, generous whitespace, monochromatic palette with one accent)?
> - For multi-shot prompts: is identity anchored verbatim across shots? For `image_selector` prompts that recur (a character or world appearing in multiple scenes), are consistency anchors specified verbatim?
>
> **Step 3 — Post-caption pass.** Rewrite filling the missing aspects, fixing confusable terms, and replacing subjective language. The post-caption is what gets sent to the generation tool.
>
> Log the (pre, critique, post) triplet in the asset metadata for traceability. This mirrors the CHAI workflow and creates a record the reviewer can audit.

### Step 7: Verify All Assets

**Existence check:**
- [ ] Every asset `path` exists on disk
- [ ] Every narration section has a corresponding audio file
- [ ] Every scene with `required_assets` has all assets generated
- [ ] Background music file exists

**Quality check:**
- [ ] Narration durations within ±15% of expected timing
- [ ] Images match the playbook's style (review consistency anchors)
- [ ] Diagrams are legible and complete
- [ ] Total cost within budget

### Step 8: Self-Evaluate

Score (1-5):

| Criterion | Question |
|-----------|----------|
| **Completeness** | Does every scene have all required assets? |
| **Audio quality** | Does narration sound natural with correct pacing? |
| **Visual consistency** | Do all images look like they belong to the same video? |
| **Budget adherence** | Is total cost within the approved budget? |
| **Playbook fidelity** | Do assets match the playbook's style guide? |

If any dimension scores below 3, fix before proceeding.

### Step 9: Submit

Validate the asset_manifest against the schema and persist via checkpoint.

### Mid-Production Fact Verification

If you encounter uncertainty during asset generation:
- Use `web_search` to verify visual accuracy of subjects (e.g. what does this building actually look like?)
- Use `web_search` to find reference images before generating illustrations
- Log verification in the decision log: `category="visual_accuracy_check"`

Visual accuracy matters. If the script mentions a specific place, person, or object,
verify what it actually looks like before generating images. Don't rely on
the AI model's training data — it may be wrong or outdated.

## Common Pitfalls

- **Generating before checking budget**: Always estimate total cost first. A 60-second video with 15 images can burn $3+ quickly.
- **Inconsistent image style**: Each image_selector call is independent. Use consistent anchors, but adapt them per scene. If you paste the same style prefix into every prompt, the video will feel machine-made and repetitive.
- **Ignoring narration timing**: If TTS produces 12s of audio for a 10s section, the edit phase will struggle. Check durations.
- **Missing pronunciation guide**: "PostgreSQL" or "Kubernetes" will be mispronounced without explicit guidance.
- **One retry then give up**: If an image doesn't match, refine the prompt specifically — don't just retry the same prompt.
- **AI-generating images with exact text (CTA, business names, contact info)**: AI image models frequently hallucinate wrong text — wrong business name, wrong phone number, misspelled words. **Never use AI image generation for scenes where text must be verbatim.** Use Remotion `text_card` type instead. This applies to: CTA screens, title cards with business names, contact info overlays, legal disclaimers. If a scene's `type` is `text_card` in the scene plan, do NOT generate an image for it — skip it and let the compose stage render it natively in Remotion.


## When You Do Not Know How

If you encounter a generation technique, provider behavior, or prompting pattern you are unsure about:

1. **Search the web** for current best practices — models and APIs change frequently, and the agent's training data may be stale
2. **Check `.agents/skills/`** for existing Layer 3 knowledge (provider-specific prompting guides, API patterns)
3. **If neither helps**, write a project-scoped skill at `projects/<project-name>/skills/<name>.md` documenting what you learned
4. **Reference source URLs** in the skill so the knowledge is traceable
5. **Log it** in the decision log: `category: "capability_extension"`, `subject: "learned technique: <name>"`

This is especially important for:
- **Video generation prompting** — models respond to specific vocabularies that change with each version
- **Image model parameters** — optimal settings for FLUX, DALL-E, Imagen differ and evolve
- **Audio provider quirks** — voice cloning, music generation, and TTS each have model-specific best practices
- **Remotion component patterns** — new composition techniques emerge as the framework evolves

Do not rely on stale knowledge. When in doubt, search first.
