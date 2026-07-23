# locate — find "X" in an image (no detector API assumed)

The single contract every consumer (asset-fusion ring, webpage highlight, future
explainer/recut overlays) uses:

```
locate(image, target-description) → { box: [x0,y0,x1,y1], center: [cx,cy] }   # normalized 0..1
```

## Why this exists

Author models are unreliable at **regressing pixel coordinates** on a cluttered
full image (measured: weak vision models ~16–24% center error → rings land off-target)
but reliable at **picking a numbered strip** (~3–4% with the loop below). So:
never eyeball coordinates; localize by discrete choice. (RSVP, ACL 2025.)

## Routing — pick the cheapest path that's actually available

1. **A strong detector is available** (e.g. `GEMINI_API_KEY` in env) →
   `node grounding/locate.mjs auto <img> "<target>"` — one call, done.
   **Never assume the key exists.** No key → path 2.
2. **No detector (the normal case)** → YOU are the localizer; run the grid loop.

## The grid loop (you read images between steps)

```
node grounding/locate.mjs overlay <img> --out /tmp/g
  → READ /tmp/g/gv.png (vertical strips 1-9) and gh.png (horizontal 1-9);
    decide which strip numbers the target spans (list EVERY strip it touches).
node grounding/locate.mjs region <img> --vids 4,5 --hids 6,7 --out /tmp/g
  → READ /tmp/g/gc.png (the region cropped + upscaled, finer 6×6 grid);
    pick the finer strips. (Pick strips again — do NOT switch to estimating
    coordinates; discrete choice is the whole point, at BOTH stages.)
node grounding/locate.mjs final <img> --region <from step 2> --vids 3,4 --hids 3,4
  → the final {box, center}.
node grounding/locate.mjs mark <img> --box <final box> --out /tmp/g/check.png
  → VERIFY: READ check.png. Red box ON the target → done. Off → redo
    region/final with corrected strips (you now know which direction). Never
    skip this step; it converts silent misses into one cheap retry.
```

## Ambiguity — resolve BEFORE localizing

If the target description can match several instances ("a drum" when the scene
has five), no geometry will save you. First make the reference unique
("the right-most drum", "the drum on the front boat"), asking the user if
needed — then run the loop.

## Degradation path (if locate.mjs itself is unavailable)

The idea is 5 lines — reproduce it with any image tool:
draw a numbered 9×9 grid → pick the strips the target spans → crop that region
(+pad ~0.4 strip) and upscale → draw a finer 6×6 grid → pick again → map back
(`global = region_origin + local × region_size`) → draw the box and LOOK at it.

## Notes

- Geometry is frozen in `locate.mjs` (node + ffmpeg, zero npm deps — both
  already required by hyperframes). Don't re-implement it ad hoc; the measured
  accuracy holds for THIS implementation.
- Consumers: `samples/asset-fusion/_ref-circle-highlight.html` takes `CFG.box`
  directly from `final`/`auto` output.
- Measured end-to-end (same agent, same template, only the localization step
  differs): eyeballing 6.5% avg center error → this protocol 2.3%, no case worse.
