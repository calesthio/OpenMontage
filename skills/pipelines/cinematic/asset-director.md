# Asset Director - Cinematic Pipeline

## When To Use

This stage prepares the usable media for the final cinematic edit: source selects, title-card assets, optional support inserts, music, ambience, and subtitle assets when needed.

## Animation authoring for cinematic titles and overlays

Before authoring title cards, name plates, or SVG overlays, read **`skills/meta/animation-runtime-selector.md`** for runtime routing. Cinematic pieces lean on a handful of high-craft motion patterns:

| Cinematic need | Recommended approach |
|---|---|
| Hero title with subtle reveal | Remotion `HeroTitle` component (existing) |
| Logo build / cinematic sting on SVG | GSAP DrawSVG + MotionPath — read `.agents/skills/gsap-plugins/SKILL.md` |
| Curved camera move across a wide still or overlay | GSAP MotionPath — read `.agents/skills/gsap-plugins/SKILL.md` |
| Per-character title reveal (prestige / trailer style) | GSAP SplitText — read `.agents/skills/gsap-plugins/SKILL.md` |
| Cinematic easings (Unreal-style, stuttering, weighted) | GSAP CustomEase / EasePack — read `.agents/skills/gsap-plugins/SKILL.md` |
| Name plate lower-third with elastic settle | Remotion `spring()` is usually enough; GSAP CustomEase if you need stutter |
| Film grain / particle overlay | Remotion `ParticleOverlay` (existing) |
| Color grade / LUT | `tools/enhancement/color_grade.py` (not an animation concern) |

**Cinematic is where GSAP earns its weight most often** — the genre rewards crafted easings and precise curved motion that primitive `interpolate()` struggles to express cleanly. Don't over-use it either: for a fade-in title, Remotion `spring()` still beats a whole GSAP dependency.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/asset_manifest.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]`, `state.artifacts["proposal"]["proposal_packet"]` | Scene intent and beat plan |
| Tools | `subtitle_gen`, `audio_enhance`, `image_selector`, `video_selector`, `pixabay_music` (free, default), `freesound_music` (free), `music_gen` (ElevenLabs, paid) — selectors auto-discover all available providers from the registry. **Default to `pixabay_music` before reaching for `music_gen`.** | Optional support asset creation |
| Playbook | Active style playbook | Brand and typography consistency |

## Process

### 1. Prioritize Source Selects

Start with:

- source footage selects,
- stills,
- title-card backgrounds,
- any approved provided music or ambient beds.

These are the primary materials. Everything else is support.

If `proposal_packet.metadata.motion_required = true`, actual moving footage or generated video clips are mandatory. In that case:

- stills may be used only as reference material or backing elements inside a larger motion composition,
- stills may not replace the planned motion shots,
- a still-image teaser is not an acceptable fallback unless the user explicitly approves an animatic.

### 1b. Sample Preview (Prevents Wasted Spend)

Before batch-generating support assets, produce one sample of each expensive generated type and show the user:

1. **Generated insert sample** (if using `image_selector` or `video_selector`): Generate one representative visual. Confirm it complements the source footage before batching.
2. **Music sample** (try `pixabay_music` first — free, searchable by mood/BPM; fall back to `freesound_music` for cues and ambience; only reach for `music_gen` when the search tools miss the brief): sample or retrieve a short clip. Confirm mood and energy match the beat plan.

If `motion_required = true`, the representative visual must be a video clip sample, not a still image sample.

If rejected, adjust parameters and retry (max 3 iterations). Do not batch until approved.

Before the sample is generated, tell the user exactly which generation path will be used:

- tool,
- provider,
- model or variant,
- generation mode,
- why it was selected.

If that path fails, stop and ask before trying a different provider, model, or generation mode.

### 2. Generate Support Assets Only Where Needed

Optional generated assets should fill clear gaps:

- missing transitional b-roll,
- concept-led inserts,
- texture or atmosphere cards,
- simple textural motion backgrounds.

For motion-required jobs, use `video_selector` first for generated shots. `image_selector` may support look development, concept frames, or embedded design layers, but it does not satisfy the motion requirement by itself.

### 3. Prepare A Real Audio Plan

Store:

- chosen music track or prompt,
- ambience layers,
- impact or transition sounds,
- subtitle assets if dialogue or narration is present.

### 4. Use Metadata For Rights And Intent

Recommended metadata keys:

- `source_selects`
- `music_plan`
- `ambience_plan`
- `title_assets`
- `generated_support_assets`
- `rights_notes`

### Pre/Post Self-Review for Generation Prompts

> Before sending a prompt to any image or video generation tool, run a three-step self-review modeled on the CHAI oversight loop ("Building a Precise Video Language with Human-AI Oversight", arXiv 2604.21718v2). Cost is small (no extra tool calls); benefit is large (avoids wasted generations). For cinematic, this matters most for **hero-frame prompts** — one bad hero frame ruins the piece, and hero frames are the most expensive shots to regenerate.
>
> **Step 1 — Pre-caption pass.** Write the prompt the way you'd write it today. Do not over-edit; aim for a complete first draft.
>
> **Step 2 — Critique pass.** Score the draft against the 5-aspect checklist (Subject / Subject Motion / Scene / Spatial Framing / Camera). For each aspect:
> - Is it specified? If not, is the omission deliberate (e.g., "no subject — scenery shot") or accidental?
> - Are confusable terms disambiguated? (dolly vs zoom, pan vs truck, bird's-eye vs aerial, fisheye vs barrel, full shot vs close-up)
> - Are emotional adjectives ("epic", "moody", "cinematic") replaced with their visual causes (low-key lighting, slow push-in, anamorphic flare, deep shadows)?
> - For multi-shot prompts and identity-anchored hero frames: is identity anchored verbatim across shots?
>
> **Step 3 — Post-caption pass.** Rewrite filling the missing aspects, fixing confusable terms, and replacing subjective language. The post-caption is what gets sent to the generation tool.
>
> Log the (pre, critique, post) triplet in the asset metadata for traceability. This mirrors the CHAI workflow and creates a record the reviewer can audit.

### 5. Quality Gate

- source and support assets are clearly distinguished,
- generated inserts are limited and purposeful,
- audio plan matches the beat map,
- every referenced file exists.
- if motion is required, the asset set contains actual video clips for the motion-led beats.

### Mid-Production Fact Verification

If you encounter uncertainty during asset generation:
- Use `web_search` to verify visual accuracy of subjects (e.g. what does this building actually look like?)
- Use `web_search` to find reference images before generating illustrations
- Log verification in the decision log: `category="visual_accuracy_check"`

Visual accuracy matters. If the script mentions a specific place, person, or object,
verify what it actually looks like before generating images. Don't rely on
the AI model's training data — it may be wrong or outdated.

## Common Pitfalls

- Generating extra shots before proving the source edit works.
- Treating music as a single loop instead of a beat-aware element.
- Forgetting rights or provenance notes for supplied assets.
- Quietly downgrading from video clips to still images because one provider or renderer failed.
- Quietly switching providers or models after the user approved a generation path.


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
