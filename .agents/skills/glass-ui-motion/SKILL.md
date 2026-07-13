---
name: glass-ui-motion
description: Author polished-SaaS product UI animations in Remotion — faithful replicas of a product's real components assembling on glassmorphic surfaces with spring motion and frame-accurate sound effects. Use in the product-motion pipeline's assets/edit stages, or for any atelier composition that animates a real product's UI. Knowledge only — ships no reusable components (atelier doctrine).
license: MIT
compatibility: Remotion via remotion-composer/ (atelier path). SFX generation needs sfx_gen (ELEVENLABS_API_KEY).
metadata: {"openclaw": {"requires": {"env": []}}}
---

# Glass UI Motion

The craft knowledge for **product-motion** atelier compositions: rebuild a
product's real UI as Remotion React components, stage it on glass surfaces,
assemble it element-by-element with spring choreography, and land sound
effects on the exact settle frames.

This skill carries **knowledge, never components** — per atelier doctrine
("reuse engine knowledge, never creative components"), every run hand-authors
its own scene components under `projects/<slug>/`. Read
`skills/meta/bespoke-composition.md` first for the atelier construction
sequence; this skill is the product-UI specialization of its step 2–4.

## 1. The truthful-replica method

The replica's authority is the repo, flowing through the `design_system` and
`ui_inventory` artifacts from the repo_analysis stage:

1. **Read the actual component source before authoring each replica.** The
   `ui_inventory` entry lists `source_files` — open them. Port the real
   structure: field order, label text, button copy, icon placement. If the
   source says `Create workspace`, the replica says `Create workspace`.
2. **Style exclusively from `design_system` tokens.** Define the tokens once
   as a `tokens.ts` module in the project generated from the artifact, and
   import from it everywhere. **No hex/size literal in a scene file that is
   not in the artifact** — this is grep-auditable and reviewed at the compose
   stage.
3. **Record provenance per asset.** Every scene snapshot registered in the
   asset_manifest carries `provenance.source_files` (the repo files it
   replicates) and `provenance.design_tokens` (the token names it draws
   from). Deviations go in `provenance.notes` with the reason.
4. **Simplify by omission, never by substitution.** A replica may drop a
   toolbar the scene doesn't need; it may not restyle one it keeps.

## 2. Glass surface recipes

The staging language: the product's UI sits on (or is framed by) frosted
panels themed from its own palette (`design_system.tokens.glass`).

```tsx
// Composed from the design_system glass spec — values from the artifact.
const glassPanel: React.CSSProperties = {
  background: glass.background,            // primary/surface at 6–12% alpha
  backdropFilter: `blur(${glass.backdrop_blur})`,
  WebkitBackdropFilter: `blur(${glass.backdrop_blur})`,
  border: glass.border,                    // 1px, white/text at 10–16% alpha
  borderRadius: tokens.radii.card,         // the PRODUCT's radius, not a generic 24px
  boxShadow: "0 24px 64px rgba(0,0,0,0.35)",
};
```

- Layer order back-to-front: ambient background (subtle gradient from the
  product's background token, optional slow drift) → glass panel(s) → the UI
  replica → highlight strokes.
- Top-edge highlight: a 1px inset gradient stroke at ~2x border alpha sells
  the glass without skeuomorphism.
- `backdropFilter` only blurs what is *behind* the panel — give it something
  to blur (gradient blobs, oversized blurred type) or it reads as flat tint.
  In-repo precedent for a working backdropFilter treatment:
  `remotion-composer/src/components/ProviderChip.tsx` (read as mechanics, do
  not import — stock imports fail the atelier guardrail).
- **Respect the product's own register.** Glass intensity is a dial, not a
  default: a dense, bordered, light-mode product wants restrained glass (low
  blur, near-opaque panels); a dark gradient-heavy product can carry more.
  When `design_system.summary` and glassmorphism disagree, the product wins.

## 3. Assembly choreography

Read `references/assembly-choreography.md` for build order, spring presets,
stagger math, and settle-frame calculation. The one-line rules:

- Build order is semantic: **container → chrome → fields → content → focus**.
- One spring vocabulary per video (2–3 presets max), stagger 4–7 frames.
- Every element's **settle frame** is computed, not eyeballed — it is where
  the SFX cue lands.
- Restraint: one thing assembling at a time is a story; twelve is noise.

## 4. SFX cueing

Read `references/sfx-cues.md` for the cue taxonomy, derivation rules, and
generation prompts. Summary:

- Generate short effects with the `sfx_gen` tool (ElevenLabs
  sound-generation); register them in the asset_manifest as `type: "sfx"`.
- Cues live **in-composition** as `<Audio>` sequences at exact settle frames
  (atelier compositions may use `<Audio>` freely — narration/music stay on
  the `audio_mixer` post-mix path).
- The cue sheet (scene → element → frame → sfx asset) lives in the atelier
  `props.json`, derived by the edit director from the scene plan's assembly
  beats.
- Density cap ≈ 1 cue per 0.7s; conservative gain (`volume={0.35}`-ish) since
  post-mix loudnorm applies to the whole mix.

## 5. Remotion mechanics that bite here

- Frame-accurate audio: `<Sequence from={settleFrame}><Audio src={staticFile("sfx/tick.mp3")} volume={0.35}/></Sequence>`.
  `<Audio>` rejects `file://` URLs — route SFX through the project's
  `public_dir` and `staticFile()`.
- Determinism: any randomness (gradient blob positions, particle drift) uses
  Remotion's `random(seed)`, never `Math.random()`.
- Fonts: load the product's real fonts (from the repo's font files or
  next/font equivalents) at module scope via `@remotion/fonts`; a replica in
  the wrong typeface fails the fidelity gate.
- Per-scene `durationInFrames` must cover the last settle + a 12–18 frame
  hold; nothing should still be moving at the cut.
- Snapshot stills for the assets gate: `scripts/atelier_snapshots.py` renders
  one PNG per scene at its most-assembled frame.

## Distinctness check (before compose)

Atelier's closing question, product-flavored: *could this composition be any
other product's video?* If the palette, radii, type, and the UI itself don't
answer "no" on sight, the replica isn't grounded enough — go back to the
design_system.
