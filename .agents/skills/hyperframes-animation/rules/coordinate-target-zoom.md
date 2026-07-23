---
name: coordinate-target-zoom
description: Zoom into a specific non-centered element by combining scale with counter-translation — target ends at viewport center after the zoom completes.
metadata:
  tags: camera, zoom, scale, translate, target, off-center, focus
---

# Coordinate Target Zoom

A simple `scale > 1` on a wrapper pushes off-center content OFF the visible canvas. To zoom _into_ a specific non-centered element, apply scale AND an inverse translation in lockstep so the target lands at viewport center.

## How It Works

Two nested wrappers, separated concerns:

1. **Outer wrapper** applies `scale` (the zoom)
2. **Inner wrapper** applies `translate(x, y)` (the counter-shift)

The translate is the **negation** of the target's offset from center. The inner translate moves the target back to the outer's transform-origin BEFORE the outer scale fires, so the scale around center maps the target to 0.

```
T = -offset
```

Derivation (outer scales the inner-translated content):

1. Inner translate moves target by T in pre-scale units → target at `offset + T`
2. Outer scale S (around center 0,0) maps that to `S × (offset + T)`
3. For target to land at viewport center: `S × (offset + T) = 0` → **`T = -offset`**

Note: the formula does NOT depend on S. The translate amount is the same whether you zoom 1.5×, 2×, or 3× — as long as the OUTER is the scale and the INNER is the translate, and scale uses `transform-origin: 50% 50%`.

## Getting the offset

`T = -offset` is only as good as `offset`. The #1 way this pattern ships broken is hand-computing `offset` from a layout formula, getting the **sign** or magnitude wrong, and letting the zoom amplify a small error off-screen. **Default to measuring the target's real laid-out center; reserve the formula for symmetric rows.**

### Default — measure the target's actual center (works for ANY layout)

Read where the target actually is, once, at setup. This is immune to sign errors because it's derived from the rendered DOM, not a mental model:

```js
await document.fonts.ready; // metrics final; fallback fonts are 10–30px off → tens of px after a 3×+ zoom
const W = 1920,
  H = 1080;
const r = document.getElementById("target-card").getBoundingClientRect();
const TARGET_OFFSET_X = r.left + r.width / 2 - W / 2;
const TARGET_OFFSET_Y = r.top + r.height / 2 - H / 2;
// bake these; feed counterX/Y = -TARGET_OFFSET_X/Y to the inner tween
```

This `getBoundingClientRect` runs **once at setup**, before timeline registration — NOT per-frame (per-frame DOM reads desync under the renderer's parallel sampling; see SKILL universal constraints). Because the measurement is async (`fonts.ready`), build and register the timeline inside the same `async` setup so the baked offset is ready before `window.__timelines[id]` is published.

### Shortcut — symmetric equal-width row ONLY

If (and only if) the target is one of N **equal-width** cards in a centered row with uniform gaps, you may skip measurement:

```js
const index_offset = targetIndex - (N - 1) / 2;
const TARGET_OFFSET_X = index_offset * (CARD_WIDTH + CARD_GAP);
```

⚠️ This assumes every sibling is the **same width**. The moment the row is asymmetric — a wide companion label beside a narrow chip, a wordmark flanked by unequal elements — it gives the wrong answer, often the wrong **sign**: the heavier side shifts the centered target the _opposite_ way you'd guess. (A real example: `companion(220) + gap + wordmark + gap + chip(110)` puts the wordmark ~55px **right** of center, but the "chip − companion" intuition says left.) For anything but equal cards, **measure**.

### Headroom budget — cap the scale from the measured size

A zoom multiplies any centering error, so leave margin. Keep the target ≤ ~88% of the canvas at peak; derive the cap from the measured size instead of picking a round number by feel:

```js
const maxScale = Math.min((0.88 * W) / r.width, (0.88 * H) / r.height);
const ZOOM_SCALE = Math.min(DESIRED_SCALE, maxScale);
```

A target that fills 97%+ of the frame reads as cut-off the instant its center is even slightly off — and a hand-baked offset always is. (The perception gate flags this as `primary-offscreen`, and `data-layout-allow-overflow` does **not** exempt it.)

## HTML

```html
<div
  class="scene"
  id="zoom-scene"
  data-composition-id="zoom-scene"
  data-start="0"
  data-duration="5"
  data-track-index="0"
>
  <div class="zoom-outer" id="zoom-outer">
    <div class="zoom-inner" id="zoom-inner">
      <div class="content">
        <!-- Several layout elements; one is the "target" -->
        <div class="card other">
          <div class="label">{label1}</div>
          <div class="price">{price1}</div>
        </div>
        <div class="card other">
          <div class="label">{label2}</div>
          <div class="price">{price2}</div>
        </div>
        <div class="card target" id="target-card">
          <div class="label">{targetLabel}</div>
          <div class="price">{targetPrice}</div>
          <div class="tag">{targetTagline}</div>
        </div>
        <div class="card other">
          <div class="label">{label4}</div>
          <div class="price">{price4}</div>
        </div>
      </div>
    </div>
  </div>
</div>
```

## CSS

```css
.scene {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;        /* REQUIRED — see Critical Constraints */
  background: {bgGradient};
}
.zoom-outer {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  transform-origin: 50% 50%;
  will-change: transform;
}
.zoom-inner {
  display: grid;
  place-items: center;
  will-change: transform;
}
.content {
  display: flex;
  gap: CARD_GAP;
}
.card {
  width: CARD_WIDTH;
  padding: CARD_PADDING;
  border-radius: CARD_RADIUS;
  background: {cardBg};
  border: 1px solid {cardBorder};
  text-align: center;
  font-family: {font};
}
.card.target {
  background: {targetCardBg};       /* slightly brighter than .card */
  border: 2px solid {targetBorder};
  box-shadow: {targetGlow};
}
.label {
  font-size: LABEL_FONT_SIZE;
  font-weight: 800;
  letter-spacing: 6px;
  text-transform: uppercase;
  color: {labelColor};
}
.price {
  font-size: PRICE_FONT_SIZE;
  font-weight: 900;
  color: {textColor};
  margin: 16px 0;
  font-variant-numeric: tabular-nums;
}
.tag {
  font-size: TAG_FONT_SIZE;
  font-weight: 700;
  letter-spacing: 4px;
  color: {accentColor};
  opacity: 0;
}
```

## GSAP Timeline

```html
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script>
  window.__timelines = window.__timelines || {};
  const tl = gsap.timeline({ paused: true });

  // TARGET_OFFSET_X / TARGET_OFFSET_Y and ZOOM_SCALE come from the "Getting the
  // offset" section above — MEASURED at setup (after fonts.ready) and baked. Do NOT
  // hand-derive the offset for a non-symmetric layout (wrong sign → the zoom shoves
  // the target off-frame). For a measured target, build the timeline inside that
  // async setup so the offset is ready before window.__timelines[id] is published.

  // Counter-translation = -offset (inner translate cancels target offset BEFORE outer scales)
  const counterX = -TARGET_OFFSET_X;
  const counterY = -TARGET_OFFSET_Y;

  // Phase 1 — cards reveal
  tl.from(
    ".card",
    { opacity: 0, y: REVEAL_Y, stagger: REVEAL_STAGGER, duration: REVEAL_DUR, ease: "power3.out" },
    REVEAL_START,
  );

  // Phase 2 — pause to let viewer scan the layout

  // Phase 3 — zoom into target
  tl.to(
    "#zoom-outer",
    {
      scale: ZOOM_SCALE,
      duration: ZOOM_DUR,
      ease: "power3.inOut",
    },
    ZOOM_START,
  );
  tl.to(
    "#zoom-inner",
    {
      x: counterX,
      y: counterY,
      duration: ZOOM_DUR,
      ease: "power3.inOut",
    },
    ZOOM_START,
  );

  // Phase 4 — target "tag" reveals inside the zoomed-in target
  tl.to(
    ".target .tag",
    { opacity: 1, duration: TAG_REVEAL_DUR, ease: "power2.out" },
    TAG_REVEAL_START,
  );

  // Phase 5 — climax dwell — viewer reads the target content
  // (no additional motion; the zoomed-in state holds for DWELL_DUR seconds)

  window.__timelines["zoom-scene"] = tl;
</script>
```

## Variations

### Dynamic target lookup via `getBoundingClientRect`

This is now the **default**, not a variation — see [Getting the offset](#getting-the-offset). Always `await document.fonts.ready` before measuring (fallback-font metrics are off by 10–30px, which a 3×+ zoom magnifies into tens of visible px) and measure **once at setup**, never per-frame.

### Zoom out (target → wide view)

Reverse the phases — start at zoomed-in, then `scale: 1` + `x: 0, y: 0` to pull back. The "reveal" beat is the panorama.

### Multi-target zoom sequence

Chain multiple zooms: target A (1.5-2.5s) → pause → target B (3-4s) → pull back (4.5-5s). Each segment needs its own counter-translation pair.

## How to Choose Values

### Layout

- **CARD_WIDTH / CARD_GAP / CARD_PADDING / CARD_RADIUS** — geometric layout.
  - Constraints: `N × CARD_WIDTH + (N-1) × CARD_GAP < viewportWidth` so all cards fit pre-zoom
  - Effects: smaller cards → more siblings on screen → busier composition; larger cards → fewer siblings, more emphasis per card
- **LABEL_FONT_SIZE / PRICE_FONT_SIZE / TAG_FONT_SIZE** — typographic hierarchy.
  - Range: tag < label < price (price is the focal element after zoom; sizing it largest reinforces this)

### Reveal phase

- **REVEAL_START** — when the cards begin fading in.
  - Constraints: typically a small offset (~0.2s) for a beat of black before content appears
- **REVEAL_DUR** — per-card fade-up duration.
  - Range: 0.4-0.8s
- **REVEAL_Y** — initial vertical offset of each card before fade-up (in px).
  - Range: 16-48 px; bigger feels "thrown in," smaller feels gentle
- **REVEAL_STAGGER** — delay between consecutive card reveals.
  - Range: 0.06-0.15s; calibrated so all cards finish before `ZOOM_START`

### Zoom phase

- **ZOOM_START** — when the zoom begins.
  - Constraints: `≥ REVEAL_START + REVEAL_DUR + (N-1) × REVEAL_STAGGER + viewer-scan-time` (give viewer 0.5-1.5s to read the layout before zooming)
- **ZOOM_DUR** — duration of the zoom tween.
  - Range: 1.0-2.0s; under 0.8s feels like a teleport, over 2.5s drags
  - Constraints: scale tween + counter-translate tween MUST share this duration AND ease
- **ZOOM_SCALE** — final magnification.
  - Range: 1.5× (modest emphasis) → 3× (dominant focus) → 5×+ (cinematic extreme)
  - Constraints: card content must remain crisp at this scale; raster source media needs `sourceResolution ≥ rendered × ZOOM_SCALE`
  - **Headroom budget**: cap from the measured target size so the target stays ≤ ~88% of the canvas at peak — `ZOOM_SCALE = Math.min(DESIRED, 0.88×W/r.width, 0.88×H/r.height)`. Picking a round number by feel (e.g. 3.2× on a 585px wordmark → 1872px = 97% of 1920) leaves no margin, so any centering slop cuts the text off.

### Target reveal + dwell

- **TAG_REVEAL_START** — when the target's hidden tag fades in.
  - Constraints: `≥ ZOOM_START + ZOOM_DUR` (only reveal after the zoom settles, so viewer's eye is already on the target)
- **TAG_REVEAL_DUR** — tag fade-in duration.
  - Range: 0.3-0.6s
- **DWELL_DUR** — post-zoom hold so the viewer reads the target.
  - Range: ≥ 1.0s after tag reveals (see "Climax dwell" in Key Principles)

### Color tokens

- **{bgGradient}** — typically a dark radial gradient to vignette the cards
- **{cardBg} / {cardBorder}** — non-target cards (subtle, recessive)
- **{targetCardBg} / {targetBorder} / {targetGlow}** — target card visually brighter / haloed so the eye lands there before the zoom even fires
- **{labelColor} / {textColor} / {accentColor}** — hierarchical text colors; `{accentColor}` reserved for the tag (pops on reveal)

## Key Principles

- **Measure the offset, don't hand-derive it** — for any layout that isn't a symmetric equal-width row, read the target's real center with `getBoundingClientRect` at setup (after `fonts.ready`) and bake it (see [Getting the offset](#getting-the-offset)). Hand-computed offsets silently get the **sign** wrong on asymmetric layouts, and the zoom amplifies the error off-screen — the single most common way this pattern ships broken.
- **Transform order — outer scales, inner translates** — DO NOT put scale and translate on the SAME element. The transform math becomes tangled (`translate * scale` ≠ `scale * translate` in CSS transform composition). Nested wrappers cleanly separate concerns.
- **Counter-translate = -offset** — independent of scale. Derive from: outer scale around center maps `(offset + T)` to `S × (offset + T)`. Setting that to zero gives `T = -offset`. A common wrong intuition is `T = -offset × (S - 1)` — it happens to give the same answer at S=2 but is wrong for any other S.
- **`transform-origin: 50% 50%` on outer wrapper** — non-center origin causes unpredictable inner offset; always center.
- **`overflow: hidden` on `.scene` REQUIRED** — at zoom > 1, the outer-scaled content can leak beyond the 1920×1080 frame.
- **Tween scale and counter-translate together** — they MUST share `duration` and `ease`. Otherwise the target drifts mid-zoom (visible "wandering"). Easiest: pass identical params to both tweens at the same time position.
- **❗ Climax dwell ≥1s after zoom completes** — see SKILL universal constraints. If zoom ends at t=3.0 in a 3.5s comp, viewer barely sees the target; aim for 1.5-2s post-zoom dwell.

## Critical Constraints

- **Timeline must be paused**: `gsap.timeline({ paused: true })`
- **Registry key = `data-composition-id`**
- **No CSS `transition` on `.zoom-outer` or `.zoom-inner`** — competes with GSAP
- **`will-change: transform`** on both wrappers — the transforms update every frame during the zoom phase
- **`transform-origin: 50% 50%` on `.zoom-outer`** — center-based scaling is what the counter-translate math assumes
- **Target offset baked once, at setup, from measurement** — measure the target center after `fonts.ready` and bake (see [Getting the offset](#getting-the-offset)); never recompute per-frame in onUpdate, and never hand-estimate the offset for a non-symmetric layout
- **Scale within the headroom budget** — keep the target ≤ ~88% of the canvas at peak, derived from the measured size (`maxScale = 0.88 × W / measuredWidth`); a target that fills the frame is cut off the instant the center is slightly off

## Combinations

- [multi-phase-camera.md](multi-phase-camera.md) — multi-phase camera that includes a coordinate-target-zoom phase
- [sine-wave-loop.md](sine-wave-loop.md) — idle breathing on the target AFTER zoom settles
- [discrete-text-sequence.md](discrete-text-sequence.md) — text assembly in the target BEFORE zoom completes

## Pairs with HF skills

- `/hyperframes-animation` — two coordinated tweens
- `/hyperframes-core` — composition wiring
- `/hyperframes-cli` — `hyperframes lint`
