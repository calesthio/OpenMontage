# Animation Runtime Selector

Meta-skill that answers two questions:

1. **Which composition runtime should this video use?** — Remotion, HyperFrames, or FFmpeg.
2. **Which animation library / Layer 3 skills should this scene reach for?** — Remotion primitives, GSAP plugins, framer-motion, Lottie, Manim, D3.

Read this before authoring any animated component or composition, and whenever you're choosing `render_runtime` at proposal time. It routes you to the right Layer 3 skill so you don't waste time hand-rolling what a plugin already solves.

> **Authoring mode comes first.** Before runtime or library, decide *how* the composition is
> built: **templated** (assemble stock `cut.type` scenes) vs **atelier** (hand-author from
> scratch). Default to atelier for hero work and follow `skills/meta/bespoke-composition.md`.
> The routing below applies within either mode — but in atelier mode the stock scene-types and
> registry blocks are off-limits; you write your own. "Does a stock cut-type fit?" is **not** a
> valid shortcut for a hero piece. See `AGENT_GUIDE.md` → "Composition Authoring Mode".

## When to use this skill

Apply when:
- **Proposal stage** needs to lock `render_runtime` (remotion / hyperframes / ffmpeg)
- A stage director (asset, edit, compose) needs to author an animated component
- An agent is about to write Remotion JSX for a scene that involves text reveals, SVG motion, curved camera paths, shape morphs, or multi-stage choreography
- An agent is asked to build a HyperFrames composition
- An agent is uncertain whether to reach for a GSAP plugin vs inline `interpolate()`/`spring()`

## Runtime choice (Remotion vs HyperFrames vs FFmpeg)

OpenMontage separates creative grammar (`renderer_family`) from technical
engine (`render_runtime`). Both are locked at proposal and carried through
`edit_decisions` unchanged. Silent runtime swaps at compose time are a
contract violation.

### HARD RULE — present both runtimes, don't silently default

When both Remotion AND HyperFrames are available on the machine (check
`video_compose.get_info()["render_engines"]`), the agent MUST present both
options to the user before locking `render_runtime`. The decision matrix
below is the agent's input for the conversation, NOT a license to silently
pick the "default" entry. See `AGENT_GUIDE.md` → "Present Both Composition
Runtimes" for the full contract.

Concretely, at the proposal stage:

1. Query `video_compose.get_info()["render_engines"]` to find which
   runtimes are available on this machine.
2. If both Remotion and HyperFrames are available, present both to the
   user with: one-line description tailored to the brief, one-line
   honest tradeoff, agent's recommendation with reason.
3. Wait for explicit user approval.
4. Log the decision in `decision_log` with category
   `render_runtime_selection` and both runtimes in `options_considered`.
5. Only then write `render_runtime` into `proposal_packet.production_plan`.

A `render_runtime_selection` decision with only one option considered
when both were available is a CRITICAL reviewer finding.

| Brief characteristic | `render_runtime` | Read |
|---|---|---|
| Existing React scene stack (text_card, stat_card, chart, caption overlay, TalkingHead, CinematicRenderer) | **remotion** | `skills/core/remotion.md` |
| Word-level caption burn / karaoke captions | **remotion** | `skills/core/remotion.md` |
| Avatar / lip-sync / presenter | **remotion** | `skills/core/remotion.md` |
| Kinetic typography, HTML/GSAP-native motion, product promo, launch reel | **hyperframes** | `skills/core/hyperframes.md` + `.agents/skills/hyperframes/SKILL.md` (router) → `hyperframes-core` (contract), `hyperframes-creative` (palette/type), `hyperframes-animation` (motion) |
| Website → video, UI-driven composition | **hyperframes** | `.agents/skills/website-to-video/SKILL.md` (renamed from website-to-hyperframes in 0.7) |
| Registry block needed (data-chart, grain-overlay, shader transitions, etc.) | **hyperframes** | `.agents/skills/hyperframes-registry/SKILL.md` |
| Beat-synced music video (audio drives scene timing) | **hyperframes** | `.agents/skills/music-to-video/SKILL.md` — uses `hyperframes beats` to detect drops, lays out frames on the beat grid |
| Porting an existing Remotion composition to HyperFrames | **hyperframes** | `.agents/skills/remotion-to-hyperframes/SKILL.md` — migration guidance, ONLY for explicit port requests |
| BGM / SFX / image / icon resolution (any pipeline, any runtime) | n/a | `.agents/skills/media-use/SKILL.md` — `resolve` verb against project cache + global cache + HeyGen catalog |
| Short design-led motion graphic (lower-third, stat reveal, logo sting, headline) | **hyperframes** | `.agents/skills/motion-graphics/SKILL.md` |
| Pure concat / trim of source clips, no composition needed | **ffmpeg** | `skills/core/ffmpeg.md` |
| Selected runtime is unavailable | **escalate** — do not substitute silently | `AGENT_GUIDE.md` → Escalate Blockers |

Read `skills/core/hyperframes.md` for the full Remotion-vs-HyperFrames
decision matrix and the list of features that stay Remotion-only in Phase 1.

## Animation library decision matrix

| Animation need | Recommended runtime | Read first |
|---|---|---|
| Simple fade / slide / scale / spring | Remotion primitives (no plugin) | `.agents/skills/remotion` |
| Two-state spring with physics | Remotion `spring()` | `.agents/skills/remotion` |
| Multi-step sequence with offsets | Remotion `Sequence` + `interpolate()` **or** GSAP timeline | `.agents/skills/remotion` + optionally `.agents/skills/gsap-timeline` |
| Per-word text reveal synced to narration | Remotion `interpolate` driven by word-level transcript (existing `CaptionOverlay` pattern) | `.agents/skills/remotion` |
| Per-character kinetic typography (SplitText style) | GSAP SplitText inside Remotion | `.agents/skills/gsap-plugins` (SplitText), `.agents/skills/gsap-react` |
| SVG shape morph between two paths | GSAP MorphSVG inside Remotion | `.agents/skills/gsap-plugins` (MorphSVG) |
| Curved camera / object motion along a custom path | GSAP MotionPath inside Remotion | `.agents/skills/gsap-plugins` (MotionPath) |
| SVG line drawing / stroke reveal | GSAP DrawSVG | `.agents/skills/gsap-plugins` (DrawSVG) |
| Bespoke bezier / elastic / stutter easing | GSAP CustomEase / EasePack / CustomWiggle | `.agents/skills/gsap-plugins` |
| Layout-to-layout transition (FLIP) | GSAP Flip inside Remotion | `.agents/skills/gsap-plugins` (Flip) |
| Disney's 12 animation principles for UI motion | framer-motion + Lottie | `.agents/skills/framer-motion`, `.agents/skills/lottie-bodymovin` |
| Lottie export from After Effects / Figma | Lottie | `.agents/skills/lottie-bodymovin` |
| Synthetic terminal / CLI demo | Remotion TerminalScene | `.agents/skills/synthetic-screen-recording` |
| Mathematical / scientific visualization | Manim | `.agents/skills/manim-composer`, `.agents/skills/manimce-best-practices` |
| D3 data-driven visualization | D3 | `.agents/skills/d3-viz` |
| Data chart (bar/line/pie/KPI) | Remotion built-in chart components | `remotion-composer/SCENE_TYPES.md` |
| HyperFrames composition — animation knowledge (rules, blueprints, transitions, runtime adapters) | HyperFrames + GSAP default | `.agents/skills/hyperframes-animation` (consolidated motion skill) + `.agents/skills/gsap-core`, `.agents/skills/gsap-timeline` |
| HyperFrames composition structure (data-* timing, tracks, sub-compositions) | HyperFrames | `.agents/skills/hyperframes-core` |
| HyperFrames creative direction (palette, type, narration, beat planning) | HyperFrames | `.agents/skills/hyperframes-creative` |
| HyperFrames audio/media (TTS, BGM, SFX, transcription, captions, bg-removal) | HyperFrames | `.agents/skills/hyperframes-media` |
| HyperFrames composition CLI work (lint/validate/inspect/snapshot/benchmark/render/lambda) | HyperFrames CLI 0.7+ | `.agents/skills/hyperframes-cli` |
| HyperFrames registry block install (`hyperframes add ...`) | HyperFrames registry | `.agents/skills/hyperframes-registry` |

## The "keep it simple" bias

Before reaching for GSAP, ask: **does Remotion's primitive API solve this in ≤ 20 lines?**

- Fade/slide/scale/rotate → `interpolate(frame, [inFrame, outFrame], [from, to])`
- Natural "bouncy" motion → `spring({ frame, fps, config: { damping, stiffness } })`
- Word-level caption highlight → iterate transcript, filter by `frame / fps`

If yes, use Remotion primitives. If no, that's your signal to escalate to a GSAP plugin.

GSAP is a powerful escape hatch, not the default. Every plugin adds bundle weight, registration boilerplate, and another skill to read.

## Running GSAP deterministically inside Remotion

Standard GSAP runs on `requestAnimationFrame` — not deterministic, not Remotion-compatible out of the box. Three patterns that ARE Remotion-safe:

```jsx
// Pattern 1: paused timeline, seek by progress
const tl = useRef(gsap.timeline({ paused: true })).current;
useEffect(() => {
  tl.to('.x', { x: 500 }).to('.y', { opacity: 0 });
}, []);
tl.progress(frame / durationInFrames);

// Pattern 2: paused timeline, seek by time
tl.seek(frame / fps);

// Pattern 3: GSAP as value calculator only
const easeFn = gsap.parseEase('power2.out');
const t = frame / durationInFrames;
const easedValue = easeFn(t);
```

For the full breakdown, read `.agents/skills/gsap-react/SKILL.md`.

## Check against the pipeline's stage director

Every pipeline's asset-director has animation-specific guidance. If you're in:
- **animated-explainer** → read `skills/pipelines/explainer/asset-director.md` — it references the text/SVG options for kinetic typography
- **animation** → read `skills/pipelines/animation/asset-director.md` — it references MorphSVG and MotionPath for logo/motion-graphics work
- **cinematic** → read `skills/pipelines/cinematic/asset-director.md` — it references MotionPath for cinematic camera moves

The asset-director tells you *what* to build in the context of this pipeline. This selector tells you *how*.

## Never do

- ❌ Pull GSAP into a scene that needs only fade/slide — use Remotion primitives.
- ❌ Use GSAP with `requestAnimationFrame` inside Remotion — render will be non-deterministic.
- ❌ Skip reading the matching Layer 3 skill when a plugin is indicated — per-plugin prompting guidance matters.
- ❌ Register GSAP plugins inside a component body — register once at module scope or app entry.
