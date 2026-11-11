# Scene Director - Animation Pipeline

## When To Use

You are converting the script into a feasible animation plan. This is the stage that decides whether the project feels designed or chaotic.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/scene_plan.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["script"]["script"]`, `state.artifacts["proposal"]["proposal_packet"]` | Beat map and tool path |
| Playbook | Active style playbook | Palette, typography, motion consistency |

## Process

### 1. Make An Animatic-Minded Plan

For each scene, define:

- what appears first,
- what changes,
- what is held,
- how the scene exits.

### 2. Limit Transition Families

Choose a small set of transition meanings:

- cut,
- fade,
- slide,
- transform.

### 3. Match Scene Type To Tool Path

Use:

- `diagram` scenes for structured explanation,
- `animation` scenes for motion-first sequences,
- `text_card` for clean high-impact copy moments,
- `generated` only where needed.

**For `image_animation` approach (anime/illustration style):**

Give each scene `"type": "animation"` in the scene plan — the scene `type` enum is `talking_head`, `broll`, `animation`, `character_scene`, `diagram`, `text_card`, `transition`, `generated`, `screen_recording`, and `anime_scene` is not one of them. `anime_scene` is the Remotion **cut** type the Compose stage writes into its composition JSON (`remotion-composer/SCENE_TYPES.md`, `skills/core/remotion.md`). Record the intent per scene in `scene_plan.metadata.tool_path_map` (see section 4) as `"remotion_cut_type": "anime_scene"` together with the plan below, and the camera move in the scene's `shot_language.camera_movement` (schema values such as `zoom_in`, `pan_right`, `static`). Plan:

- **Images per scene**: 2-3 images built from the same visual system and nearby seeds for crossfade effect
- **Camera motion**: choose from `zoom-in`, `zoom-out`, `pan-left`, `pan-right`, `ken-burns`, `drift-up`, `drift-down`, `parallax`, `static` — vary per scene to prevent monotony
- **Particle type**: choose from `fireflies`, `petals`, `sparkles`, `mist`, `light-rays` — match to scene mood
- **Lighting**: optional `lightingFrom`/`lightingTo` gradient for atmospheric shifts within the scene
- **Vignette**: `true` for cinematic framing (default), `false` for bright/open scenes
- **Scene duration**: 4-7 seconds per scene. Longer scenes need more images for crossfade variety.

**Scene variety rules for image_animation:**
- Don't use the same camera motion for consecutive scenes
- Alternate between warm and cool particle types
- Mix close-up and wide establishing shots
- Use overlays (`hero_title`, `section_title`) to add narrative structure — describe them in the scene's `overlay_notes` string

**JSON prop name mapping** (the exact field names the Compose stage uses in the Remotion composition JSON — use them as the keys of each scene's `tool_path_map` entry so the mapping is mechanical; they are not scene fields):

| Concept | JSON Field | Example Values |
|---------|-----------|----------------|
| Camera motion | `animation` | `"zoom-in"`, `"pan-right"`, `"ken-burns"` |
| Particle effect | `particles` | `"fireflies"`, `"sparkles"`, `"mist"` |
| Particle color | `particleColor` | `"#FFE082"` |
| Particle density | `particleCount` | `20` (range: 1-50) |
| Particle brightness | `particleIntensity` | `0.5` (range: 0-1) |
| Lighting start | `lightingFrom` | `"rgba(255,200,100,0.15)"` or `"transparent"` |
| Lighting end | `lightingTo` | `"rgba(255,107,157,0.08)"` or `"transparent"` |
| Cinematic edge darken | `vignette` | `true` / `false` |
| Scene background | `backgroundColor` | theme-derived value such as `"#0A0A1A"` or `"#F6F1E8"` |

### 4. Use Metadata For Timing Rules

Recommended metadata keys (top-level `scene_plan.metadata` — each scene is closed in the schema and has no `metadata` of its own):

- `animatic_rules`
- `transition_rules`
- `hold_rules`
- `tool_path_map` — keyed by scene `id`: that scene's `animation_mode` (one of `image_animation`, `clip_video`, `manim`, `remotion_dataviz`, `diagram_stills`), its tool, and for `image_animation` scenes the Remotion plan, e.g. `{"scene-1": {"animation_mode": "image_animation", "tool": "image_selector", "remotion_cut_type": "anime_scene", "image_count": 3, "animation": "zoom-in", "particles": "fireflies", "vignette": true}}`
- `reusable_motifs`

### 5. 5-Aspect Scene-Plan Checklist

> Every scene must specify all five aspects, BUT the load shifts with the scene's `animation_mode`. Manim and other diagrammatic/programmatic scenes care most about **Subject** and **Spatial Framing** — Camera and Subject Motion in the cinematographic sense often map to N/A or to abstract equivalents. AI-video / `image_animation` / `anime_scene` scenes care about all five and behave like cinematic shots. Marking an aspect as N/A is allowed but must be explicit per scene; silent omission is forbidden.
>
> 1. **Subject** — type + key visual attributes; for Manim, the equation/object/graph being foregrounded; for `anime_scene`, the character or environment in focus.
> 2. **Subject Motion** — for Manim, the order of `Create`/`Transform`/`FadeIn` and what each animation conveys; for AI-video, the actions and interactions in temporal order.
> 3. **Scene** — overlays (separately!) + POV + setting + time of day + scene dynamics. For Manim, "setting" is the canvas background + axis style; for `anime_scene`, the environment + lighting gradient.
> 4. **Spatial Framing** — shot size + position-in-frame + depth (FG/MG/BG) + camera-height-relative; and how those CHANGE. Manim cares about layout grid + element positions; AI-video cares about full cinematographic framing.
> 5. **Camera** — playback speed → lens distortion → height → angle → focus/DoF → steadiness → movement. For Manim and pure motion-graphics, default to N/A unless using a virtual camera move (`MoveCamera`, `self.frame`). For `anime_scene` and AI-video, specify fully.
>
> Tie this back to the scene's `animation_mode` in `scene_plan.metadata.tool_path_map` (scenes have no metadata of their own): a Manim scene that lists Camera fully is over-specified; an AI-video scene that omits Camera is under-specified. See `skills/creative/video-gen-prompting.md` for the primitive vocabulary.

> **Overlays callout.** Overlays (titles, subtitles, HUD, watermarks, framing graphics, lower-thirds, `hero_title`, `section_title`, `provider_chip`) are NOT part of the scene's foreground/midground/background depth axis. List them separately in the scene's `overlay_notes` string with content and placement (scenes are closed in the schema — there is no scene-level `overlays` or `metadata` key; a structured list, if you need one, goes in `scene_plan.metadata.overlays` keyed by scene `id`). Never describe an overlay as "in the foreground" — that confuses both downstream tools and any video-understanding model that re-analyzes the output.

### 6. Quality Gate

- every scene has a clear timing intent,
- the 5-aspect checklist is satisfied for the scene's `animation_mode` (with explicit N/A where appropriate),
- overlays live in `overlay_notes`, never inside the framing description,
- the transition system is limited and meaningful,
- the tool path is explicit,
- the sequence feels like one designed system.

## Common Pitfalls

- Adding a new transition idea in every scene.
- Planning scenes that have no realistic production path.
- Overanimating text-heavy scenes.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
