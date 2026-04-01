# Asset Director - Animation Pipeline

## When To Use

This stage prepares the actual animated ingredients: narration, diagrams, math renders, motion backgrounds, code visuals, and reusable type or layout systems.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["idea"]["brief"]` | Tool path and beat map |
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

1. **TTS sample** (if narration-led): Generate one section. Confirm voice and tone before batching.
2. **Visual sample**: Generate one representative scene visual (diagram, illustration, or motion background). Confirm style and quality before batching the rest.

If rejected, adjust parameters and retry (max 3 iterations). Do not batch until approved.

### 1c. Multi-Image Generation for Image-Based Animation (Approach A)

When `animation_mode == "image_animation"`, each scene needs **2-3 images** for crossfade animation. This is what makes stills look like movement.

**Image generation workflow:**

1. **Define a STYLE_PREFIX** — a consistent prompt prefix used across ALL images in the project. This ensures visual coherence. Store it as a reusable asset.
   ```
   Example: "Studio Ghibli anime style, hand-painted watercolor aesthetic,
   soft diffused lighting, lush natural environment, warm color palette,
   painterly brushstrokes visible, high detail..."
   ```

2. **Use seed management** — for each scene, use nearby seed values (e.g., seed 100 and 101) for the A/B variants. Same prompt + different seed = same composition with subtle differences = natural crossfade motion.

3. **Generate one test image first** — render a single scene to verify the style prefix produces good results at 1920×1080 before batch generating all images.

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

If the project is narration-led, produce or source narration. If it is text-led or music-led, say so clearly in metadata.

### 4. Use Metadata For Feasibility Truth

Recommended metadata keys:

- `tool_path_map`
- `reusable_assets`
- `narration_assets`
- `scene_asset_index`
- `blocked_assets`

### 5. Quality Gate

- the asset path is explicit per scene,
- reusable assets are actually reused,
- missing capabilities are surfaced honestly,
- every referenced file exists.

## Common Pitfalls

- Using high-variance generation when a deterministic asset would work better.
- Rebuilding the same title or label system repeatedly.
- Hiding failed asset paths instead of reporting them.
