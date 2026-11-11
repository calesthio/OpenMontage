# Image Generation Usage for OpenMontage

> Sources: OpenAI GPT Image documentation, FLUX/BFL API documentation, existing Layer 3 skills
> at `.agents/skills/flux-best-practices/` and `.agents/skills/bfl-api/`

## Quick Reference Card

```
FLUX RESOLUTION:  1920x1088 (16:9) | 1088x1920 (9:16) — must be multiples of 16
MAX TOTAL:        4 megapixels (width x height)
CONSISTENCY:      Use hero image as a reference — generation_mode="edit" + image_path (edit-capable provider)
STYLE SYSTEM:     Derive from subject + audience + tone, then adapt per scene
BATCH STRATEGY:   Hero with flux-pro/v1.1 → iterate with flux/dev → final pass with flux-pro/v1.1
```

## FLUX Tools That Exist

| Tool | `model` | Cost | `seed` / `negative_prompt` | Reference images |
|------|---------|------|----------------------------|------------------|
| `flux_image` (fal.ai) | `flux-pro/v1.1` (default), `flux-pro` | $0.05/image | Yes | No — text-to-image only |
| `flux_image` (fal.ai) | `flux/dev` | $0.03/image | Yes | No — text-to-image only |
| `bfl_image` (BFL direct, FLUX 3) | `flux-3-image` | No fixed price — `estimate_cost` raises `PriceQuoteRequired`; get a current quote first | **Rejected** — the call fails if you pass `seed`, `negative_prompt` or `input_image` | Yes — up to 10 |
| `flux3_fal_image`, `flux3_replicate_image` (FLUX 3) | `flux-3-image` | Price quote required | No such inputs | Yes — up to 10 |

No OpenMontage tool exposes FLUX.2 [max] / [klein] / [pro]. The Layer 3 FLUX skills describe those
tiers, but do not pass them as a `model` — the values above are the only ones the tools accept.

## Resolution for Video Frames

All FLUX dimensions **must be multiples of 16**. Maximum total is 4MP.

| Target | FLUX Resolution | Cost (`flux_image`) |
|--------|----------------|---------------------|
| YouTube 16:9 | `1920x1088` | $0.05/image (`flux-pro/v1.1`) or $0.03 (`flux/dev`) |
| YouTube 4K | `3840x2160` | Over the 4MP limit — use `bfl_image` (`resolution: "4k"`, `aspect_ratio: "16:9"`, price quote required) or generate `1920x1088` and upscale |
| TikTok/Reels 9:16 | `1088x1920` | $0.05/image (`flux-pro/v1.1`) or $0.03 (`flux/dev`) |
| Square 1:1 | `1024x1024` | $0.05/image (`flux-pro/v1.1`) or $0.03 (`flux/dev`) |
| Thumbnail | `1280x720` | $0.05/image (`flux-pro/v1.1`) or $0.03 (`flux/dev`) |

`flux_image` is priced per image, not per size. Its default size is `1024x1024` — always pass `width` and `height` for video frames.

## Maintaining Visual Consistency

The biggest challenge: making 8-12 generated images look like they belong in the same video.

### Strategy 1 — Shared Visual System (Always Use)

Define a shared visual system for the project first, then adapt it per scene.
Capture the project's:

- dominant mood and texture,
- palette direction,
- lighting bias,
- rendering medium,
- character/environment consistency anchors.

The playbook's `image_prompt_prefix` is source material, not something to paste
verbatim into every prompt. Distill it into a shorter scene-appropriate anchor.

### Strategy 2 — Hero Reference Image (Recommended)

1. Generate one "hero" image at maximum quality (`flux_image`, default `flux-pro/v1.1`, $0.05)
2. Use it as the reference for all subsequent frames — call `image_selector` with
   `generation_mode: "edit"` and `image_path: "hero.png"` (several references: `image_paths`;
   remote images: `image_url` / `image_urls`). There is no `input_image` key:

```
Frame 1: T2I with detailed prompt → hero.png
Frame 2: I2I with hero.png + "Same style, camera pans right to show..."
Frame 3: I2I with hero.png + "Same style, zoomed in on..."
```

`flux_image` cannot take a reference image, so an edit request routes to an edit-capable provider
instead (FLUX 3 via `bfl_image` / `flux3_fal_image` / `flux3_replicate_image`, or `grok_image`,
`openai_image`). FLUX 3 supports up to 10 references. Reference by number: "The character from image 1 in the environment from image 2."

### Strategy 3 — Seed Locking

Use the same `seed` parameter across generations with similar prompts. Produces similar compositions but is fragile to prompt changes — use as supplement, not primary strategy.

Only providers that list `seed` in their input schema honor it (`flux_image`, `local_diffusion`).
The FLUX 3 tools do not: `bfl_image` rejects `seed`, and `image_selector` silently drops `seed`
(log warning only) for any provider that lacks it — so seed locking and the hero-reference
strategy cannot be combined on FLUX.

## Prompt Construction — 3-Part Contextual Approach

**Do NOT copy the playbook's `image_prompt_prefix` verbatim into every prompt.** That's what makes all scenes look the same. Instead, build each prompt from 3 contextual layers:

### Part 1: Scene-Specific Style Direction (from shot_language + texture_keywords)

Use the scene's `shot_language` fields to set camera and lighting:
```
[SHOT SIZE from shot_language.shot_size, e.g., "medium close-up"].
[LIGHTING from shot_language.lighting_key, e.g., "golden hour warm light"].
[DEPTH from shot_language.depth_of_field, e.g., "shallow depth of field with bokeh"].
[TEXTURE from scene.texture_keywords, e.g., "film grain, warm tones"].
```

If the scene has no shot_language, fall back to the template below.

### Part 2: Playbook Consistency Anchor (adapted, not verbatim)

Extract the ESSENCE of the playbook's visual language — don't copy the prefix. For example:
- Playbook says "Clean, minimal illustration with soft shadows, muted color palette" → Adapt to: "muted color palette, soft shadows"
- Playbook says "Bold flat motion graphics, vibrant gradients" → Adapt to: "vibrant flat style"

The anchor keeps scenes visually coherent without making them identical.

### Part 3: Scene Description

The actual content of the scene. Be specific — replace generic words with concrete details.

**BAD:** "A person using a computer in a modern office"
**GOOD:** "Software developer in a dimly lit home office, blue monitor glow reflecting off glasses, desk cluttered with energy drinks and sticky notes"

### Full Prompt Example (with shot_language)

```
Medium close-up, golden hour warm lighting, shallow depth of field.
Muted earth tones, soft shadows.
Beekeeper in white protective gear lifting a frame dripping with honey,
late afternoon sun catching golden droplets, lavender field blurred
in the background. Film grain, warm amber tones.
16:9 aspect ratio.
```

### Fallback Template (when no shot_language is available)

```
[ADAPTED STYLE ANCHOR from playbook — 5-10 words, not the full prefix].
[SCENE DESCRIPTION: specific subject, action, environment].
[LIGHTING: golden hour / overcast / studio softbox / dramatic side-light].
[COMPOSITION: wide shot / medium shot / close-up / overhead / isometric].
[CAMERA: Shot on [camera] with [lens] at [aperture]] (for photorealistic only).
16:9 aspect ratio.
```

### Using lib/shot_prompt_builder.py

For programmatic prompt construction, use the shot prompt builder which automates the 3-part approach:

```python
from lib.shot_prompt_builder import build_shot_prompt
prompt = build_shot_prompt(scene, style_context=playbook_data)
```

This converts the structured shot_language fields into natural-language prompts
optimized for image/video generation providers.

### Style-Specific Prompt Patterns

| Style | Prompt Pattern |
|-------|---------------|
| **Flat illustration** | "Flat vector illustration, bold colors, clean edges, no gradients, white background" |
| **Isometric** | "Isometric 3D illustration, 30-degree angle, clean geometric shapes, soft shadows" |
| **Photorealistic** | "Photorealistic, shot on Canon EOS R5 with 85mm f/1.4, shallow depth of field" |
| **Diagram-style** | "Technical diagram, labeled components, clean lines, minimal color, white background" |
| **Watercolor** | "Soft watercolor illustration, muted tones, visible brush strokes, paper texture" |

## Batch Generation Strategy

| Phase | Model | Cost/Image | Purpose |
|-------|-------|-----------|---------|
| 1. Style guide | `flux_image` — `flux-pro/v1.1` | $0.05 | One hero image, maximum quality |
| 2. Storyboard iteration | `flux_image` — `flux/dev` | $0.03 | Rapid variations during planning |
| 3. Final frames | `flux_image` — `flux-pro/v1.1` | $0.05 | Re-generate finals in the hero's style |

To re-generate finals **with the hero as a reference image**, phase 3 must use an edit-capable
provider (`generation_mode: "edit"` + `image_path`) — on FLUX that is FLUX 3 (`bfl_image`), which
has no fixed price: get a quote before budgeting.

**Rate limit:** 24 concurrent requests max on the BFL direct API (`bfl_image`). Pipeline accordingly.

**Budget for 8-image explainer:** $0.05 (hero) + $0.24 (8x `flux/dev` iterations) + $0.40 (8x `flux-pro/v1.1` finals) = ~$0.69

## Common Pitfalls

1. **Text in images** — AI image generators are unreliable with text. Never include text in prompts; add text as overlays in the compose stage
2. **Hands and fingers** — AI image models still struggle. Avoid prompts requiring detailed hand poses
3. **Inconsistent characters** — Without reference images, the same character will look different each time. Always use the hero reference strategy
4. **Over-prompting** — Long, complex prompts produce unpredictable results. Keep to 2-3 sentences
5. **Over-unifying prompts** — Forcing the exact same style phrase into every prompt makes scenes look samey. Keep the visual system consistent, but let each scene express its own subject, shot, and emotional beat.

## Applying to OpenMontage

When using the `image_selector` tool in the asset stage:

1. **Design the visual system first** from the proposal or custom playbook: mood, palette, texture, motion energy
2. **Generate a hero image first** at highest quality, use as reference for all others (`generation_mode: "edit"` + `image_path`, never `input_image`)
3. **Use `1920x1088`** for 16:9 video frames (FLUX multiple-of-16 requirement)
4. **Never request text in images** — add text overlays in the compose stage
5. **Budget check** — estimate total image cost before generating; switch to local diffusers if over budget
6. **Iterate with `model: "flux/dev"`** during planning, finalize with `flux-pro/v1.1`
7. **Keep prompts to 2-3 sentences** — scene-specific camera/lighting + adapted visual anchor + concrete subject
8. **Match the scene plan** — each image maps to a specific scene in the script
