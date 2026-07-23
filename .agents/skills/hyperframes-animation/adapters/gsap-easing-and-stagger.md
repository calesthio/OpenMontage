# Easing, Stagger, and Function-Based Values

## Easing

Built-in eases: `power1`, `power2`, `power3`, `power4`, `back`, `bounce`, `circ`, `elastic`, `expo`, `sine`, `none`.

Each has `.in`, `.out`, `.inOut` variants.

| Ease                       | Use for                                                                 |
| -------------------------- | ----------------------------------------------------------------------- |
| `power1.out`, `power2.out` | Standard UI motion. Default for most entrances.                         |
| `power3.out`, `power4.out` | Punchier deceleration. Title cards, hero reveals.                       |
| `sine.inOut`               | Long, slow, calm motion. Crossfades, ambient drift.                     |
| `back.out(1.7)`            | Slight overshoot. Playful entrances. The arg controls overshoot amount. |
| `elastic.out(1, 0.3)`      | Springy bounce. First arg = amplitude, second = period.                 |
| `expo.inOut`               | Snappy, dramatic. Quick transitions between hero scenes.                |
| `none` (linear)            | Camera moves with timed counterpoint, mechanical motion.                |

Pick `.out` for entrances, `.in` for exits, `.inOut` for symmetric moves and continuous motion.

## Easing Vocabulary (character & mood)

Easings are tone of voice: a video that only whispers is boring; one that varies between whisper, normal, and punch is engaging. Every composition should use at least 3 different easings — `power2.out` for everything produces flat, monotonous motion.

The full palette by character (each family has `.in`, `.out`, `.inOut` variants):

| Family               | Character                                                                    | Typical use                                                                                        |
| -------------------- | ---------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| `power1`–`power4`    | Gentle (1) to aggressive (4) acceleration curves                             | General purpose. power2 is the workhorse, power4 for dramatic snaps                                |
| `back(N)`            | Overshoot then settle. N controls how far past the target (1=subtle, 4=wild) | Logo reveals, badge pops, card entrances. `back.out(2.5)` for playful, `back.out(1.2)` for elegant |
| `elastic(amp, freq)` | Spring bounce. amp=magnitude, freq=oscillation speed                         | Panel scatter, energetic drops, fun reveals                                                        |
| `bounce`             | Ball-drop bouncing                                                           | Physical interactions, icons landing, score counters                                               |
| `expo`               | Extreme acceleration curve (much steeper than power4)                        | Premium/luxury reveals, dramatic entrances                                                         |
| `sine`               | Smooth, organic, no hard edges                                               | Ambient float, breathing, Ken Burns, anything that loops. `.inOut` for yoyo motion                 |
| `circ`               | Circular acceleration (starts very fast, ends very gentle or vice versa)     | Camera moves, scene transitions, orbital motion                                                    |
| `steps(N)`           | Discrete N-step jumps, no interpolation                                      | Typing effects, cursor blink, counter ticks, retro/digital aesthetics                              |

**Mood mapping:** Match easing character to the beat's emotional content. Smooth/organic easings (`sine`, `power1`) feel contemplative and drifting. Aggressive deceleration (`power4.out`, `expo.out`) feels snappy and confident. Spring overshoot (`back.out`) feels bouncy and physical. The storyboard's mood description should guide which character fits — not a formula.

## Defaults

```javascript
const tl = gsap.timeline({
  paused: true,
  defaults: { duration: 0.6, ease: "power2.out" },
});
```

Or globally:

```javascript
gsap.defaults({ duration: 0.6, ease: "power2.out" });
```

Setting defaults at timeline scope is preferred — it documents the motion language of that composition in one place.

## Stagger

```javascript
gsap.fromTo(".item", { y: 24, opacity: 0 }, { y: 0, opacity: 1, duration: 0.5, stagger: 0.08 });
```

Object form:

```javascript
gsap.fromTo(
  ".item",
  { y: 24, opacity: 0 },
  {
    y: 0,
    opacity: 1,
    stagger: {
      each: 0.08, // delay between each
      from: "center", // "start" | "end" | "center" | "edges" | "random" | index
      amount: 0.6, // total stagger time (overrides each if both set)
      grid: "auto", // for 2D stagger
      axis: "x" | "y",
    },
  },
);
```

Prefer `stagger` over N separate tweens with manual delays — it stays correct when the target count or order changes. Use `fromTo()` rather than `from()` so the start state is explicit (see `gsap-timeline-and-labels.md` → sub-composition entrances).

## Function-Based Values

Any var can be a function `(index, target, targets) => value`:

```javascript
gsap.to(".item", {
  x: (i, target, targets) => i * 50,
  rotation: (i) => (i % 2 === 0 ? 5 : -5),
  stagger: 0.1,
});
```

Use this for per-element values that depend on index, attributes, or measured size. Cheaper and more idiomatic than building tweens in a loop.

## gsap.matchMedia (preview only)

`matchMedia` runs setup only when a media query matches and auto-reverts when it stops matching. It is useful for **preview** in the browser at different viewport sizes, and for `prefers-reduced-motion`. It is **not** a substitute for rendering at the composition's actual `data-width`/`data-height` — HyperFrames renders at a fixed viewport.

```javascript
let mm = gsap.matchMedia();
mm.add(
  {
    isDesktop: "(min-width: 800px)",
    reduceMotion: "(prefers-reduced-motion: reduce)",
  },
  (context) => {
    const { isDesktop, reduceMotion } = context.conditions;
    gsap.to(".box", {
      rotation: isDesktop ? 360 : 180,
      duration: reduceMotion ? 0 : 2,
    });
  },
);
```
