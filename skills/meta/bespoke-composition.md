# Bespoke Composition (Atelier Mode)

Meta-skill for **hand-authoring a composition from scratch** instead of assembling stock
scene-types. This is the "hand-stitched every time" path: for hero pieces, every pixel of the
look is written fresh so no two videos share a visual language.

Read this whenever you've chosen **atelier mode** for a piece (see "When to use"). It does not
hand you components — it routes you to the *principles, engine mechanics, and tool wiring* you
need so that what you build is correct, and distinct.

> The single rule that governs everything below: **reuse engine knowledge, never creative
> components.** How Remotion resolves an asset is engine knowledge — reuse it freely. How a
> previous video looked is a creative decision — never reuse it.

## When to use this skill (authoring mode is a proposal decision)

OpenMontage separates three orthogonal axes, all locked at proposal:

- `renderer_family` — creative grammar
- `render_runtime` — technical engine (remotion / hyperframes / ffmpeg)
- **`composition_mode`** — **templated** (assemble stock `cut.type` scenes) **vs. atelier** (hand-author)

Pick **atelier** by default for: marketing, launches, explainers that must impress, brand
pieces, anything single-deliverable where quality is the point. Pick **templated** for: batch
output, localization variants, quick drafts, low-stakes internal clips — places where reliable
sameness is fine and bespoke cost is unjustified. Present the choice to the user at proposal and
log it in `decision_log` (`category: "composition_mode"`), the same way you present runtime.

### Atelier and the two runtimes

The two runtimes treat "bespoke" differently — read this before assuming the doctrine maps the same way to both:

- **Remotion** ships a `cut.type` registry of stock scenes (`text_card`, `stat_card`, `bar_chart`, …) dispatched by the `Explainer`/`CinematicRenderer` compositions. That's the templated default. **Atelier mode is the escape hatch** — `composition_mode: "atelier"` routes the render to `_render_via_atelier` and bypasses the registry entirely, so the agent hand-writes its own React composition under `projects/<slug>/`.
- **HyperFrames is inherently atelier.** There is no cut-schema in HF — every composition is a hand-authored `index.html` with `data-*` timing attributes and a GSAP timeline you wrote. The registry (`hyperframes add`) is a *block* registry (grain overlays, transitions) — it's optional inputs to your composition, not a scene catalog dispatching the whole render. **When `render_runtime: "hyperframes"` is chosen, the piece is already atelier-style; `composition_mode: "atelier"` is implicit.** The principles in this skill (art direction, scene distinctness, no hero-component spine, distinctness review) apply equally. Render via `hyperframes_compose` (or `npx hyperframes render` for hand-authored compositions — see section 5).

So: if `render_runtime == "remotion"` and the piece is hero work, log a `composition_mode: "atelier"` decision. If `render_runtime == "hyperframes"`, atelier is the default behavior and you don't need to argue for it; this skill still routes you through the same principles before you write the composition.

If atelier is in play (either runtime), the stock Remotion `cut.type` catalog, `hyperframes-registry` finished blocks consumed as scenes (vs as raw inputs), fixtures, and any pre-baked creative component are **off-limits** — they are frozen looks and reintroduce sameness.

## The construction route

Author in this order. Each step routes you to existing knowledge — do not skip the first one.

### 1. Commit to an art direction *for this subject* — the divergence engine
Before writing any component, decide a visual language that fits **this** topic and no other.
Read **`skills/meta/taste-direction.md`** first and write the `taste_profile`: the design read,
`visual_variance`, `motion_intensity`, `information_density`, reference strategy, and
anti-patterns. Then use the **`visual-style`** Layer 3 skill (CREATE mode) to lock: palette, type personality,
motion character, layout system, and **one signature device** unique to this piece. Difference
between videos is guaranteed here — not by withholding components, but by forcing a fresh
direction each time. Write it down (a short `art-direction.md` in the project) and build to it.

Ask yourself: *what visual metaphor belongs to this subject that I have not used before?* If the
answer resembles a past piece, you haven't found the direction yet.

### 1.5 Plan each scene as its own composition — no hero-component spine
The most insidious form of templating sneaks back in at the *scene* level: pick one striking
visual (a candle, a browser frame, a score ring), then re-use it every scene with different
text underneath. The piece feels custom because the hero is custom — but every scene is
mechanically the same composition. That's branded slides, not a film. **Don't do that.**

The signature device named in your art-direction is meant to appear in **one or at most two
beats** — typically the climactic moment — not as the visual scaffolding of every scene. It
earns its weight by being scarce.

For each scene in the plan, answer concretely *before* writing code:

- **What is this scene's primary visual subject?** It must be *different* from the previous
  scene's. A character. A diagram. A piece of evidence. A landscape. A typographic moment. The
  signature device. A void. Each scene's primary subject is its job.
- **Why does this beat exist?** What does it do for the story that no other beat does? If you
  can collapse two scenes into one without losing meaning, you should.
- **How does it differ visually from the scene before and after?** Different composition (rule
  of thirds vs centered vs split). Different scale (intimate close vs wide field). Different
  motion register (still vs busy). Different palette emphasis. Different type treatment.
- **If you removed the signature device from this scene, would the scene still work?** If yes,
  the signature device probably doesn't belong in this scene — it's there as filler. Cut it.

The reviewer enforces this as a "scene_distinctness" check (see
`skills/meta/reviewer.md` → Composition Authoring Mode Review): a recorded inventory of
each scene's primary subject + first frame, and an explicit answer to "do any two scenes
share their primary visual subject?" Yes ⇒ CRITICAL ⇒ re-plan.

The corollary: the per-scene plan is a *first-class artifact*, not implied. Write it down
(in `art-direction.md` or a sibling `scenes.md`) before authoring `Composition.tsx`.

### 2. Decide the motion language — principles, not presets
Reach for **principle** skills, never finished animations:
- **`framer-motion`** and **`lottie-bodymovin`** — Disney's 12 principles (anticipation, staging,
  follow-through, slow-in/out, arc, timing, exaggeration, appeal). Runtime-agnostic; apply the
  *principles* in your own Remotion `spring()`/`interpolate()` code.
- The HyperFrames `references/motion-principles.md` — easing as emotion, timing as weight.

### 3. Reach for a richer vocabulary only when the concept demands it

**On Remotion** — most scenes are Remotion primitives. Escalate when the *idea* needs it, not
by default: `gsap-*` (kinetic typography via SplitText, shape morph via MorphSVG, curved
motion via MotionPath, line-draw via DrawSVG, custom easing), `threejs-*` (3D), `d3-viz`
(data-driven custom charts — build the chart by hand; do **not** drop in the stock
`bar_chart`/`line_chart`), `manim-*` (math), `canvas-procedural-animation` (particles/weather).

**On HyperFrames** — the vocabulary lives in `/hyperframes-animation`: 36+ atomic motion
**rules** (`kinetic-beat-slam`, `3d-text-depth-layers`, `motion-blur-streak`,
`physics-press-reaction`, `multi-phase-camera`, `depth-of-field-blur`, …), 15+ scene
**blueprints** (`kinetic-type-beats`, `comparison-split`, `dataviz-countup`,
`constellation-hub`, `ticker-takeover`, `device-surface-showcase`, …), 16 **transition**
families (`css-distortion`, `css-destruction`, `css-radial`, `css-light`, `css-mechanical`,
…), and **7 runtime adapters** under one composition: GSAP default, plus Lottie, Three.js,
Anime.js, CSS keyframes, WAAPI, and TypeGPU (GPU compute). The headline capability is
`adapters/html-in-canvas-patterns.md` — capture live HTML/CSS as a GPU texture and render
through WebGL/Three.js for cinematic bloom, shatter, liquid, portal effects. Use it for 1–3
hero beats per video, not every beat. **Compose 2–4 distinct atomic rules per beat** and use
**at least 3 different easings across the piece** — that's the doctrine baked into the
animation skill, not optional polish.

For HF creative direction (palette/type/narration/beat planning) read `/hyperframes-creative`.
For HF assets (TTS/BGM/SFX/transcription/background-removal) read `/hyperframes-media` or
`/media-use`. For HF CLI workflow (init/lint/validate/inspect/snapshot/beats/render) read
`/hyperframes-cli`. The `/hyperframes` router skill maps it all.

### 4. Get the engine mechanics right — the gotcha codex
This is the only place you "reuse": the engine's solved problems. These are facts about how
the framework works, not looks.

**For Remotion**, study `.agents/skills/remotion-best-practices` (19 rule files: timing,
transitions, text-animations, transparent video, fonts, audio, sequencing, measuring text).
You may also read the stock components in `remotion-composer/src/components/` **as a
mechanics codex — to learn idioms, never to import or imitate a look.**

**For HyperFrames**, the composition contract is in `/hyperframes-core` (the `data-*`
timing attributes — `data-start`, `data-duration`, `data-track-index` — plus the
mandatory `class="clip"`, `data-composition-id`, `window.__timelines` registration, sub-
composition mounts). Run `npx hyperframes lint && npx hyperframes validate` after every
change — they catch missing root attrs, missing clip ids, GSAP-target unresolved, overlapping
tweens, and contrast failures before render. Use `npx hyperframes snapshot . --at <times>`
to spot-check beats visually before committing to a full render.

Recurring mechanics that bite if you don't know them:
- **Determinism**: no `Math.random()` / `Date.now()` per frame — use Remotion `random(seed)` or a
  seeded helper, or particles/easing flicker across the render.
- **Per-scene duration**: `useVideoConfig().durationInFrames` returns the *composition* length, not
  your scene's. Drive scene-local timing from a passed `durationInFrames`/`Sequence`, not the global.
- **Asset paths**: URLs and `staticFile()` (public/) work everywhere; **`<Audio>` rejects `file://`**
  (only `<OffthreadVideo>`/`<Img>` accept absolute `file://`). Put audio/video in a per-project
  public dir and reference via `staticFile`. Mirror the `resolveAsset` helper.
- **GSAP-in-Remotion**: use a `paused` timeline and `.seek(frame/fps)` — never `requestAnimationFrame`
  — so frames render deterministically.
- **Fonts (Remotion)**: `loadFont()` from `@remotion/google-fonts/<Name>` at module scope, once.
- **HF data-* contract**: every timed element needs `data-start`, `data-duration`,
  `data-track-index`, AND `class="clip"` — without `clip` the framework won't manage
  visibility and your element will be onscreen the whole timeline. Root `<body>` needs
  `data-composition-id`, `data-start="0"`, `data-duration`, `data-width`, `data-height`.
  Every timeline must be `gsap.timeline({ paused: true })` and registered as
  `window.__timelines["<composition-id>"]`. Use stable `id` attributes on clips and on
  GSAP targets — `nth-of-type` selectors are flaky at validate time.
- **Captions vs on-screen text — pick one role, never both for the same content.** Decide
  once per piece, before authoring: are captions adding meaning the spoken words can't carry
  (a number, a name, a translation, a quote attribution), OR are they accessibility subtitles
  echoing the narration? If your scene already displays a SerifLine that reads the script
  verbatim, do NOT also emit an auto-caption with the same text — the doubled phrase looks
  amateurish even when the rest of the scene is beautiful. Empty `captions=[]` in props, or
  scope captions only to scenes where the on-screen text differs from what's being said.

### 5. Render through the runtime-appropriate bespoke path
Bespoke compositions are **throwaway and project-local** — they never enter any shared registry.

#### Remotion atelier path
- Author under `projects/<slug>/` (gitignored). The render tool auto-stages your `.tsx`/`.ts`
  source into `remotion-composer/projects/<slug>/` via mtime-skip copy so webpack can resolve
  `node_modules` — your source-of-truth stays under `projects/`.
- Scaffold with `python scripts/scaffold_atelier_project.py <slug>` — emits engine
  plumbing only (entry / Root / blank `Composition.tsx` / `art-direction.md` / props
  template / README). Zero creative content; the placeholder is a deliberately ugly black
  screen so the post-render review correctly refuses to ship the scaffold unauthored.
- Keep media in `projects/<slug>/public/` and pass that as `bespoke.public_dir`.
- Render via `video_compose` `operation="render"`:

```json
edit_decisions = {
  "render_runtime": "remotion",
  "composition_mode": "atelier",
  "bespoke": {
    "entry": "projects/<slug>/index.tsx",
    "composition_id": "<id registered in that entry's Root>",
    "props_path": "<absolute path to artifacts/props.json>",
    "public_dir": "<absolute path to projects/<slug>/public/>",
    "art_direction": "<short note or path to art-direction.md — REQUIRED>",
    "scale": 0.5,          // 0.5 for a fast draft; drop for the 1080p final
    "crf": 18,             // crisp final
    "concurrency": 8
  }
}
```

No `asset_manifest` or `cuts` are required in atelier mode — the composition owns its own assets.
The tool's `_run_atelier_checks` fails the render if any source file imports from the stock
registry (`src/components`, `src/Explainer`, etc.), and warns if `art_direction` is missing.

#### HyperFrames path
- Scaffold with `npx hyperframes init <slug>` (run from `projects/`). HF init generates
  `index.html`, `meta.json`, `package.json`, and a per-project `CLAUDE.md` that auto-routes
  the agent into `/hyperframes` — so the next session knows exactly which sub-skills to load.
- Author `index.html` by hand. Every clip needs `class="clip"` + the three `data-*` timing
  attrs + a stable `id`. Mount sub-compositions via `data-composition-src` once the timeline
  on one file grows past 4 clips (the lint catches density).
- For music-driven pieces, run `npx hyperframes beats .` after dropping the track in
  `assets/` — it emits `beats/<audio>.json` with `{time, strength}` per beat so the agent
  can land scenes on real drops (not guesses).
- Verify before render: `npx hyperframes lint . && npx hyperframes validate . && npx hyperframes snapshot . --at <times>`.
  Snapshot is HF's native visual-spotcheck (contact-sheet of PNG frames at chosen
  timestamps) — use it the same way an atelier `final_review.visual_spotcheck` would.
- **Render**: `npx hyperframes render . --output renders/<name>.mp4`.
  > Known gap (F13): `hyperframes_compose.render` currently requires `edit_decisions.cuts[]`
  > from the templated path. For hand-authored HF compositions it errors; call `npx` directly
  > until the tool grows a bespoke branch.

## Guardrails so this doesn't backfire

- **Distinctness review (replaces conformance review).** Before final render, ask: *could this be
  any other product's video? Does it reuse a look I've made before?* If yes, the art direction
  failed — return to step 1. This is the inverse of "does it match the reference."
- **No silent fallback to stock.** "Keep it simple" applies to *mechanics* (a 10-line spring is
  fine), never to *design* (simple ≠ reaching for `text_card`). If you catch yourself adding a
  stock `cut.type` to a hero piece, stop.
- **Cost honesty.** Atelier costs more agent tokens and iteration than templated. Say so at proposal
  so the user opts in knowingly. Quality varies more without a stock baseline — mitigate with strong
  principle skills (above) and the distinctness review, not by reintroducing reuse.
- **Checkpoint cadence.** Follow `skills/meta/checkpoint-protocol.md`: present script + scene plan
  for approval BEFORE generating assets, then the **assets gate**, then a first-render checkpoint.
  Do not batch-generate ahead of sign-off, and **do not render a draft to earn the assets review** —
  the assets gate is held *before* compose (see below).

- **Populate the filmstrip with per-scene stills at the assets gate.** A bespoke scene's "asset" is
  a `.tsx` composition — not thumbnailable — so the board can't show it until a still exists. Once
  the composition compiles, render one still per scene at a representative frame into
  `projects/<slug>/snapshots/<scene_id>.png`, so the assets-gate filmstrip shows real frames instead
  of "◆ BESPOKE" placeholders. Use Remotion's still renderer (fast — one frame each), driven off the
  scene_plan timings:

  ```bash
  # one still per scene at mid-scene frame (fps * mid_seconds), into snapshots/<scene_id>.png
  npx remotion still projects/<slug>/index.tsx <CompositionId> \
    projects/<slug>/snapshots/<scene_id>.png \
    --frame=<mid_frame> --props=<abs artifacts/props.json> --public-dir=<abs public/>
  ```

  A helper that reads the scene_plan and renders all stills is at
  `scripts/atelier_snapshots.py` (`python scripts/atelier_snapshots.py <slug>`). Then STOP at the
  assets gate. The full/draft render is the **compose** stage, after approval.

## Worked precedents (for the *workflow*, not the look)

Two reference pieces — one per runtime — to study **processes**, never visual languages:

- **Remotion atelier** — Phantom Reach explainer (`projects/phantom-reach-explainer/`):
  Playwright-captured app footage with a PII-blur layer → per-sentence TTS stitched with
  silence beats → free Pixabay music → hand-authored Remotion scenes (custom intro,
  score-ring, agentic flow, CTA) on a one-off violet theme.
  Compound Snowball (`projects/compound-snowball/`) and Library of Alexandria
  (`projects/alexandria-fire/`) are two more — three Remotion atelier pieces, three
  completely different visual languages.

- **HyperFrames** — `in-a-hurry` (`projects/in-a-hurry/`): a music-driven kinetic-typography
  piece using the new HF 0.7 `beats` command to lock scene timing to real drops. Exercises
  **5 categories** of `/hyperframes-animation`: `kinetic-beat-slam`, `3d-text-depth-layers`
  (stacked extrusion), `motion-blur-streak` (echo-ghost trails), `transitions/css-distortion`
  (chromatic-aberration RGB-split), and `adapters/html-in-canvas-patterns` (Three.js +
  UnrealBloom on a hero punchline). Each beat uses a distinct easing (`expo.out`,
  `back.out(2)`, `circ.out`, `sine.inOut`).

**Do not reproduce any of their visual languages** — the next piece must look nothing like
any of them. That is the whole point. Study only the *process* (decisions, ordering, gates,
verification).

See also: `skills/meta/animation-runtime-selector.md` (runtime + library routing),
`AGENT_GUIDE.md` → "Composition Authoring Mode", `/hyperframes` (the HF router and
capability map).
