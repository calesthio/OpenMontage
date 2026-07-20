# Asset Director - Animation Pipeline

## When To Use

This stage prepares the actual animated ingredients: narration, diagrams, math renders, motion backgrounds, code visuals, and reusable type or layout systems.

## Animation authoring — which runtime

Before authoring motion-graphics components, read **`skills/meta/animation-runtime-selector.md`** for runtime routing. Animation is the pipeline most likely to justify GSAP plugins — logo morphs, curved camera paths, kinetic type, FLIP transitions.

Quick routing for common animation-pipeline needs:

| Motion type | Recommended approach |
|---|---|
| SVG logo morph between two shapes | GSAP MorphSVG — read `.agents/skills/gsap-plugins/SKILL.md` |
| Line drawing / stroke reveal on SVG | GSAP DrawSVG — read `.agents/skills/gsap-plugins/SKILL.md` |
| Object following a curved path | GSAP MotionPath — read `.agents/skills/gsap-plugins/SKILL.md` |
| Per-character / per-word title reveals | GSAP SplitText — read `.agents/skills/gsap-plugins/SKILL.md` |
| Custom bezier or elastic easing | GSAP CustomEase — read `.agents/skills/gsap-plugins/SKILL.md` |
| Layout-to-layout element flight (FLIP) | GSAP Flip — read `.agents/skills/gsap-plugins/SKILL.md` |
| Multi-step sequence across many elements | GSAP timeline — read `.agents/skills/gsap-timeline/SKILL.md` |
| Particle overlay / background motion | Remotion `ParticleOverlay` component (already exists) |
| Mathematical animation (graphs, equations) | Manim — read `.agents/skills/manim-composer`, `.agents/skills/manimce-best-practices` |
| Ghibli / anime-style still-driven scene | Remotion `AnimeScene` component + FLUX image gen |

**Remotion determinism rule:** every GSAP use inside a Remotion component must drive timeline progress from `useCurrentFrame()` — never `requestAnimationFrame`. Pattern examples in `.agents/skills/gsap-react/SKILL.md`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["proposal"]["proposal_packet"]` | Tool path and beat map |
| Tools | `tts_selector`, `image_selector`, `video_selector`, `math_animate`, `diagram_gen`, `code_snippet`, `music_gen` — selectors auto-discover all available providers from the registry | Asset production options |
| Playbook | Active style playbook | Visual consistency |

## Process

### 1. Start With Deterministic Assets

Prefer the lowest-variance useful path:

- `diagram_gen` before generic image generation for structured diagrams,
- `code_snippet` for code scenes,
- `math_animate` for real math motion,
- provided artwork before new generation.

### 1b. Sample Preview (Prevents Wasted Spend)

Before batch-generating assets, produce one sample of each expensive type and show the user:

1. **TTS sample** (if narration-led): Generate `script.voice_performance.sample_section_id` when present; otherwise choose the section with the strongest emotional or pacing change. Confirm voice, pace, pauses, emphasis, and tone before batching.
2. **Visual sample**: Generate one representative scene visual (diagram, illustration, or motion background). Confirm style and quality before batching the rest.

If rejected, adjust parameters and retry (max 3 iterations). Do not batch until approved.

### 1c. Multi-Image Generation for Image-Based Animation (Approach A)

When `animation_mode == "image_animation"`, each scene needs **2-3 images** for crossfade animation. This is what makes stills look like movement.

**Image generation workflow:**

1. **Define a VISUAL SYSTEM** — a reusable set of anchors used across all images in the project. This ensures visual coherence without flattening every shot into the same prompt. Store it as reusable metadata.
   ```
   Example: "Hand-painted nature fantasy, warm moss-and-amber palette,
   soft diffused light, painterly foliage textures, gentle wonder."
   ```
   Then adapt it per scene:
   - Scene 1: wide establishing forest valley, mist, sunrise
   - Scene 2: close character beat, lantern glow, drifting spores
   - Scene 3: abstract magical energy reveal, brighter accent contrast

2. **Use seed management** — for each scene, use nearby seed values (e.g., seed 100 and 101) for the A/B variants. Same prompt + different seed = same composition with subtle differences = natural crossfade motion.

3. **Generate one test image first** — render a single scene to verify the visual system produces good results at 1920×1080 before batch generating all images.

4. **Batch generation** — generate all scene images. Skip any that already exist on disk (idempotent).

5. **Composition JSON** — each scene gets `type: "anime_scene"` with `images: ["path/a.png", "path/b.png"]` plus camera motion, particle type, and lighting config.

**Cost estimation:** 2-3 images per scene × $0.03-0.13/image depending on provider.

**Reference:** See `projects/mori-no-seishin/generate_images.py` for the proven batch generation pattern.

6. **Copy to Remotion public directory** — After generating all images, copy them to `remotion-composer/public/<project-name>/` so Remotion can access them via `staticFile()`. Image paths in the composition JSON are relative to this directory:
   ```
   remotion-composer/public/<project-name>/scene1-a.png   ← Remotion reads from here
   remotion-composer/public/<project-name>/ambient-music.mp3  ← Music too
   ```
   **If you skip this step, the render will fail with missing file errors.** This is the #1 cause of render failures for new projects.

### 2. Build Reusable Systems

Create once:

- typography treatments,
- lower-third or label styles,
- repeated motif assets,
- background containers.

### 3. Narration Is Optional, But The Plan Must Be Explicit

If the project is narration-led, produce or source narration. Read
`skills/meta/voice-performance-director.md`, then apply `script.voice_performance`
and each section's `delivery_cues` when building TTS requests. Use
`provider_text` when present, map cues to provider controls, and record the
applied settings on each narration asset. If it is text-led or music-led, say so
clearly in metadata.

### 4. Use Metadata For Feasibility Truth

Recommended metadata keys:

- `tool_path_map`
- `reusable_assets`
- `narration_assets`
- `voice_performance`: sample approval path, provider settings, and whether delivery cues were applied
- `scene_asset_index`
- `blocked_assets`

### 5. Quality Gate

- the asset path is explicit per scene,
- reusable assets are actually reused,
- missing capabilities are surfaced honestly,
- every referenced file exists,
- narration-led assets apply the approved voice-performance settings.

### Mid-Production Fact Verification

If you encounter uncertainty during asset generation:
- Use `web_search` to verify visual accuracy of subjects (e.g. what does this building actually look like?)
- Use `web_search` to find reference images before generating illustrations
- Log verification in the decision log: `category="visual_accuracy_check"`

Visual accuracy matters. If the script mentions a specific place, person, or object,
verify what it actually looks like before generating images. Don't rely on
the AI model's training data — it may be wrong or outdated.

## Common Pitfalls

- Using high-variance generation when a deterministic asset would work better.
- Rebuilding the same title or label system repeatedly.
- Hiding failed asset paths instead of reporting them.
- Treating TTS as raw text-to-audio. Narration-led animation needs pauses,
  emphasis, and pace cues carried from the script into the generated audio.
- Treating "consistency" as "same prompt every time." Good animation keeps a recognizable world while still letting each beat feel fresh.


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
