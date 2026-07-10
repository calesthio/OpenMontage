# Animation & Motion Graphics Pipeline

> Sources: School of Motion curriculum, After Effects documentation, Remotion documentation,
> HyperFrames documentation, Disney's 12 Principles of Animation (Frank Thomas & Ollie
> Johnston), Motion Design School, The Animator's Survival Kit (Richard Williams)

## Runtime Choice — Remotion vs HyperFrames

Animation work in Balamonis Studio runs on one of two composition runtimes. Both
are first-class; the choice is creative, not a fallback:

- **Remotion (React-based)** — when the scene is a React component, uses the
  existing chart/text-card/comparison/kpi stack, or needs pixel-accurate
  frame-level interpolation through `useCurrentFrame()` + `interpolate()`.
  Default for data-heavy explainers.
- **HyperFrames (HTML/GSAP)** — when the motion is expressed naturally as
  CSS + GSAP timelines: kinetic typography, product promos, launch reels,
  website/UI-driven compositions, registry-block-driven scenes. Default
  when the brief is motion-graphics-led and the scene library in
  `remotion-composer/` doesn't already cover the look.

See `skills/core/hyperframes.md` and `skills/meta/animation-runtime-selector.md`
for the full decision matrix. Whichever runtime is chosen at proposal must
be locked in `edit_decisions.render_runtime` and preserved through compose.

## Quick Reference Card

```
FRAME RATE:       30fps for web video | 24fps for cinematic feel | 60fps for UI/smooth motion
EASE DEFAULT:     easeInOutCubic (0.65, 0, 0.35, 1) — never use linear
TRANSITION:       0.5-1.0s between scenes
ANTICIPATION:     2-3 frames before main action
OVERSHOOT:        10-15% past target, settle back in 3-5 frames
HOLD FRAMES:      6-12 frames (0.2-0.4s) on key poses
COLOR:            Max 5 colors from playbook palette
EXPORT:           H.264 CRF 18-20 for web, ProRes 422 for editing
```

## Frame Rate Selection

| Style | FPS | When to Use |
|-------|-----|-------------|
| **Cinematic animation** | 24 | Film-like feel, character animation, organic motion |
| **Web/explainer standard** | 30 | Default for YouTube/web video. Balamonis Studio default. |
| **Smooth UI animation** | 60 | Software demos, UI transitions, scrolling |
| **Stylized/limited** | 12-15 on 2s/3s | Deliberately choppy, artistic choice |

**Balamonis Studio default:** 30fps. Render Manim at 60fps and transcode to 30fps for smoother motion at delivery frame rate.

## Timing Principles (Applied to Motion Graphics)

### The 4 Most Important Principles

| Principle | Application | Timing |
|-----------|------------|--------|
| **Ease In/Out** | Every movement starts slow, ends slow | Use cubic or quart easing, never linear |
| **Anticipation** | Brief movement opposite to the main action | 2-3 frames (66-100ms at 30fps) |
| **Overshoot** | Object passes target, bounces back | 10-15% past target, settle in 3-5 frames |
| **Staging** | Only one thing moves at a time | Stagger animations by 3-6 frames |

### Easing Curves

| Curve | Cubic Bezier | Use For |
|-------|-------------|---------|
| **easeOutCubic** | `(0.33, 1, 0.68, 1)` | Objects entering the scene |
| **easeInCubic** | `(0.32, 0, 0.67, 0)` | Objects leaving the scene |
| **easeInOutCubic** | `(0.65, 0, 0.35, 1)` | Position changes within scene |
| **easeOutBack** | `(0.34, 1.56, 0.64, 1)` | Bouncy pop-in (playful) |
| **easeOutElastic** | spring simulation | Attention-grabbing reveals |
| **linear** | `(0, 0, 1, 1)` | **NEVER for motion** — only for opacity or color |

### Hold Frames

After a movement completes, **hold the pose** before the next animation:

| Context | Hold Duration |
|---------|--------------|
| Key information on screen | 1.0-2.0s (narration dependent) |
| Between animation beats | 0.3-0.5s (8-15 frames at 30fps) |
| After a reveal | 1.5-3.0s (let it register) |
| Quick transition | 0.1-0.2s (3-6 frames) |

## Scene Transitions

| Transition | Duration | When to Use |
|-----------|----------|-------------|
| **Hard cut** | Instant | Same topic, different angle/zoom |
| **Crossfade** | 0.5-1.0s | Topic change, gentle shift |
| **Wipe/slide** | 0.5-0.8s | Sequential steps, progression |
| **Zoom in** | 0.8-1.2s | Diving deeper into detail |
| **Zoom out** | 0.8-1.2s | Revealing bigger picture |
| **Match cut** | Instant | Same shape/position, different content |
| **Morph/transform** | 1.0-2.0s | Concept evolution, before/after |

### Transition Rules

1. **Consistent transitions** — pick 2-3 types and stick with them throughout the video
2. **Transition = meaning** — a wipe means "next step," a zoom means "deeper detail"
3. **Don't over-transition** — a hard cut is the most invisible and most professional transition
4. **Audio leads visual** — start transition sound 10-20ms before the visual change

## Composition for Motion Graphics

### Layout

- **Rule of thirds** — place focal elements on intersection points
- **Visual hierarchy** — largest/brightest element = most important
- **White space** — minimum 10% margin on all sides (within title-safe)
- **Direction of motion** — left-to-right = forward/progress, right-to-left = reverse/back

### Color

- **Max 5 colors** from the style playbook palette
- **1 accent color** for emphasis — used sparingly
- **Background** should be the least saturated color
- **Contrast** between foreground elements and background: minimum 3:1

### Stagger and Choreography

When multiple elements enter:
- Stagger entry by **3-6 frames** (100-200ms) between elements
- Enter from the same direction for grouped elements
- Use `LaggedStart` (Manim) or staggered `delay` (Remotion) with `lag_ratio=0.1-0.2`

## Export Settings

| Target | Codec | Settings |
|--------|-------|----------|
| YouTube/web final | H.264 | CRF 18-20, `-pix_fmt yuv420p`, `-movflags +faststart` |
| Editing intermediate | ProRes 422 | For further editing/compositing |
| Transparent overlay | ProRes 4444 | When compositing over other footage |
| GIF preview | GIF | 480px wide, 15fps, 256 colors |

## Applying to Balamonis Studio

When building animation/motion graphics content:

1. **Render at 30fps** (Balamonis Studio default) — Manim at 60fps, transcode down
2. **Never use linear easing** — default to `easeInOutCubic` for all motion
3. **Stagger multi-element entrances** by 100-200ms — don't reveal everything at once
4. **Hold key frames** for 1.0-2.0s after reveals (synced to narration)
5. **Use 2-3 transition types** consistently — hard cut + crossfade covers most needs
6. **Audio leads visual** — SFX starts 10-20ms before transition (see sound-design.md)
7. **Max 5 palette colors** — enforce from the style playbook
8. **Anticipation + overshoot** on important movements for polish
9. **Export H.264 CRF 18-20** for final output via `video_compose`
