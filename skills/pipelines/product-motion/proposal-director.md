# Proposal Director — Product-Motion Pipeline

## When to Use

Second stage. `design_system` + `ui_inventory` are approved. You produce the
`proposal_packet` the user green-lights before any creative writing or
spending: concepts, runtime, authoring mode, taste profile, music/SFX plan,
and itemized cost.

## Prerequisites

Read first: `skills/meta/taste-direction.md` (the taste_profile travels from
here), `skills/meta/bespoke-composition.md` (atelier contract),
`skills/core/hyperframes.md` (runtime decision matrix).

## Process

### 1. Concepts (2-3, differentiated)

Each concept picks 3-5 approved flagship screens and a narrative arc (e.g.
"problem → the dashboard answers it → the form that gets you there → close").
Concepts must feature screens from `ui_inventory` — a concept that needs a
surface the product doesn't have is invalid. Tie each concept to
`design_system.summary`: the product's own visual language leads; glass
staging intensity is a dial set per the glass-ui-motion skill.

### 2. Composition runtime — Present both (HARD RULE)

Check availability (`video_compose.get_info()["render_engines"]`), then
**present both runtimes** with per-brief tradeoffs before locking
`render_runtime`. For this pipeline the honest framing is:

- **Remotion** — recommended for **React/Next repos**: replicas are near-1:1
  ports of the actual JSX; native `spring()` choreography; frame-accurate
  in-composition SFX via `<Audio>`; atelier precedents exist. Tradeoff:
  Vue/Svelte templates must be translated to React, one more fidelity risk.
- **HyperFrames** — the genuine alternative for **Vue/Nuxt or Tailwind-heavy
  markup**: HTML/CSS replicas can reuse the repo's template markup and
  Tailwind classes nearly verbatim (arguably *more* truthful there); GSAP
  timelines for assembly. Tradeoff: SFX cueing is post-mix territory and the
  glass-ui-motion Remotion mechanics don't transfer 1:1.

Let `design_system.source.framework` drive your recommendation, recommend one
with rationale, and wait for the user's choice. If only one runtime is
installed, say so explicitly and record the other as
`rejected_because: "runtime not available on this machine"`.

Log `decision_log` entry `category: "render_runtime_selection"`, subject
"Composition runtime", with BOTH runtimes (plus ffmpeg where it applied) in
`options_considered`. Lock the choice in
`proposal_packet.production_plan.render_runtime` — compose must carry it
unchanged; a silent swap (e.g. to `render_runtime="hyperframes"` or back) is
a CRITICAL governance violation.

### 3. Authoring mode — atelier by default

This pipeline's replicas are inherently per-product, so **atelier** is the
default `composition_mode`. Disclose the tradeoff (more tokens/iteration than
templated; that's the price of a bespoke, truthful piece) and log
`decision_log` `category: "composition_mode"`, subject "Composition authoring
mode", with `templated` in `options_considered` and why it was rejected
(stock scene types cannot be faithful to this product's UI).

### 4. Taste profile

Run `skills/meta/taste-direction.md`; carry the resulting `taste_profile`
into `production_plan.taste_profile`. `design_read` comes straight from
`design_system.summary`. Typical product-motion dials: motion_intensity 4-6
(weighted, calm), information_density 3-5, palette_discipline strict (the
product's tokens only).

### 5. Music + SFX plan (mandatory)

Per AGENT_GUIDE's Music Plan: check `music_library/`, then
`registry.get_by_capability("music_generation")`, present the explicit
choices (library track / user-supplied / generate / none). For SFX: check
`sfx_gen` availability; if unavailable, the "with sound effects" promise
degrades — present the 1-minute env-var fix (read `install_instructions`)
and let the user choose. Record both in the proposal.

### 6. Cost + production plan

Itemize: narration TTS (chars × provider rate), music (1 track), SFX (4-6
effects × ~$0.03), render (local, $0). State per-stage plan and gates. Then
checkpoint `awaiting_human`, present, **end your turn**.
