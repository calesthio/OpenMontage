# GSAP Skills in OpenMontage

> **Scope:** This directory has no `SKILL.md` — it is **not** a loadable skill. This file is a navigation map for the eight loadable `gsap-*` skills that live in sibling directories (`gsap-core`, `gsap-timeline`, …). Read it to find the right `gsap-*` skill; the agent loads those, not this README.

Eight Layer 3 skills teaching the agent correct GSAP (GreenSock Animation Platform) usage. Sourced from [greensock/gsap-skills](https://github.com/greensock/gsap-skills), MIT licensed.

## Why GSAP is in this repo

OpenMontage doesn't use GSAP directly today — Remotion compositions are driven by `useCurrentFrame()` + `interpolate()` + `spring()`. GSAP becomes relevant in two concrete scenarios:

1. **Advanced text / SVG / motion-path animation inside a Remotion component.** GSAP's plugin family (SplitText, MorphSVG, DrawSVG, MotionPath, CustomEase) solves problems that are painful to hand-roll with primitive `interpolate()` calls. When you need per-character reveals, curved camera paths over SVG, or morphing between two arbitrary shapes — reach for GSAP.
2. **HyperFrames composition.** HyperFrames is a production composition runtime in OpenMontage (rendered via `hyperframes_compose`; see `skills/core/hyperframes.md` and `AGENT_GUIDE.md`). GSAP is its native animation runtime via the Frame Adapter pattern — timelines are paused and registered on `window.__timelines`, and the engine seeks them frame-by-frame. GSAP timeline authoring is a day-1 skill for HyperFrames scenes.

## When to read which

| You're doing… | Read first |
|---|---|
| Any GSAP animation, starting from zero | [`gsap-core`](../gsap-core/SKILL.md) |
| Multi-step sequence or choreography | [`gsap-timeline`](../gsap-timeline/SKILL.md) |
| Per-word or per-character text animation | [`gsap-plugins`](../gsap-plugins/SKILL.md) (SplitText section) |
| SVG shape morph | [`gsap-plugins`](../gsap-plugins/SKILL.md) (MorphSVG section) |
| Object following a curved path | [`gsap-plugins`](../gsap-plugins/SKILL.md) (MotionPath section) |
| Custom bezier easing | [`gsap-plugins`](../gsap-plugins/SKILL.md) (CustomEase section) |
| GSAP inside a React component (Remotion) | [`gsap-react`](../gsap-react/SKILL.md) |
| Math helpers (clamp, mapRange, interpolate, random) | [`gsap-utils`](../gsap-utils/SKILL.md) |
| Debugging slow animations | [`gsap-performance`](../gsap-performance/SKILL.md) |
| Scroll-driven animation (web preview only, not video render) | [`gsap-scrolltrigger`](../gsap-scrolltrigger/SKILL.md) |
| Vue / Svelte / non-React host | [`gsap-frameworks`](../gsap-frameworks/SKILL.md) |

## How to discover these from Layer 2

These skills don't fire automatically. Trigger points:

- **`skills/meta/animation-runtime-selector.md`** — the dispatcher meta skill. When authoring any animated scene, read this first; it routes you to the right Layer 3 skill based on what kind of motion you need.
- **Pipeline asset-director skills** — `animated-explainer`, `animation`, and `cinematic` pipelines reference these skills where applicable (SplitText for text, MorphSVG for logos, MotionPath for camera moves).
- **`hyperframes_compose` tool** — declares `agent_skills: ["gsap-timeline", "gsap-core"]` so the agent auto-reads them before authoring a HyperFrames composition.

## Running GSAP deterministically inside Remotion

Standard GSAP drives animations via `requestAnimationFrame` — not deterministic, not Remotion-compatible. To use GSAP inside a Remotion component:

- **Pause the timeline** on creation: `const tl = gsap.timeline({ paused: true })`
- **Drive progress from `useCurrentFrame()`**: `tl.progress(frame / durationInFrames)`
- Or **seek by time**: `tl.seek(frame / fps)` to a specific point
- Or **use GSAP as a value calculator only** — call tween math via `gsap.parseEase(...)` and `gsap.utils.interpolate(...)` to compute values without running a real animation loop

This pattern is what HyperFrames uses internally. Inside Remotion, prefer native `interpolate()` for simple cases; use GSAP when you need SplitText / MorphSVG / MotionPath / CustomEase specifically.

## Attribution

Source: https://github.com/greensock/gsap-skills
License: MIT
Copied: 2026-04-16 (at commit `{{source_commit}}` — see upstream for latest)
