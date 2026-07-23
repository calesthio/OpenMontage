# Transitions translation: @remotion/transitions → HF crossfades / shader-transitions

The `@remotion/transitions` package is Remotion's library of pre-built
scene-to-scene transitions. HF has two paths to translate them:

1. **Manual GSAP crossfade** — for simple opacity/transform transitions. Free, no extra package.
2. **HF shader-transitions package** — for visually-rich transitions that match the @remotion/transitions presets.

## Pattern: `<TransitionSeries>` is `<Series>` with overlap

```tsx
<TransitionSeries>
  <TransitionSeries.Sequence durationInFrames={60}>
    <SceneA />
  </TransitionSeries.Sequence>
  <TransitionSeries.Transition
    presentation={fade()}
    timing={linearTiming({ durationInFrames: 15 })}
  />
  <TransitionSeries.Sequence durationInFrames={60}>
    <SceneB />
  </TransitionSeries.Sequence>
</TransitionSeries>
```

Translates to scenes that overlap by the transition duration:

- SceneA: [0, 60] = `data-start="0" data-duration="2"`
- SceneB: [60-15, 60-15+60] = `data-start="1.5" data-duration="2"` (the transition window overlaps the end of A and start of B)

Then drive the transition with GSAP:

```js
// Manual fade (presentation={fade()})
tl.to(sceneA, { opacity: 0, duration: 0.5, ease: "none" }, 1.5);
tl.fromTo(sceneB, { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "none" }, 1.5);
```

## Presentation table

| Remotion `presentation`            | HF translation                                                                            |
| ---------------------------------- | ----------------------------------------------------------------------------------------- |
| `fade()`                           | manual `gsap.to(opacity)` crossfade                                                       |
| `slide({direction: "from-right"})` | `gsap.fromTo(translateX: "100%" → 0)` on incoming + `to(translateX: "-100%")` on outgoing |
| `wipe({direction: "from-left"})`   | `gsap.fromTo(clip-path: inset(0 100% 0 0) → inset(0 0 0 0))` on incoming                  |
| `clockWipe()`                      | use HF's `sdf-iris` shader-transition (`npx hyperframes add sdf-iris`)                    |
| `flip()`                           | `gsap.to(rotateY)` 180° split between scenes                                              |
| `cube()`                           | use HF's `cinematic-zoom` or build manually with `rotateY` + `transform-origin`           |
| `iris()`                           | use HF's `sdf-iris` shader-transition                                                     |
| `none()`                           | no transition; hard cut at the boundary                                                   |

## Timing translations

```tsx
linearTiming({durationInFrames: 15})              → ease: "none"
linearTiming({durationInFrames: 15, easing: ...}) → ease per the easing table in timing.md
springTiming({config: {damping: 12}})             → ease: "back.out(1.4)" (~0.7 s)
```

Convert `durationInFrames` to seconds (`/fps`).

## When to use HF shader-transitions

For transitions Remotion presets that have visually-rich GLSL equivalents
(iris, ripple, zoom, glitch), use HF's [shader-transitions](https://hyperframes.heygen.com/catalog/blocks)
package. They produce richer output than manual GSAP transforms.

```bash
npx hyperframes add sdf-iris
```

Then in the composition:

```html
<div id="iris-transition" class="hf-shader-transition" data-start="1.5" data-duration="0.5">
  <!-- bound scenes via the shader-transition's data-from / data-to -->
</div>
```

Each shader-transition has its own data attributes; see the catalog page
for the specific block.

## When the source uses a custom Presentation

Remotion supports custom `presentation` implementations:

```tsx
const customPresentation: PresentationComponent = ({
  children,
  presentationProgress,
  presentationDirection,
}) => {
  return (
    <div
      style={
        {
          /* compute transform from progress */
        }
      }
    >
      {children}
    </div>
  );
};
```

Translation: extract the math from the `style={...}` block and emit
equivalent GSAP tweens. Specifically the transform formula maps directly
to a `gsap.to(target, { transform: ... })` parameterized by `progress`.

If the custom presentation uses `useCurrentFrame()` internally to
animate something _outside_ the simple progress curve, treat the source
as untranslatable and bow out to the runtime interop pattern (see
[escape-hatch.md](escape-hatch.md)).
