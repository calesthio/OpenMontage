# Ink Theater examples

## `mocap-figure/` — the canonical runnable example

A self-contained HyperFrames composition: a pencil line **draws itself into a
stick figure**, which then walks / runs / dances / kicks / sits / waves using
**real CMU motion capture** (zero hand-tuning) via `InkPuppet.choreograph(...)`.

It bundles everything it needs (`ink-theater.js`, `ink-puppet.js`, `clips.js`,
`assets/patrickhand.ttf`), so lint and render it directly:

```bash
npx hyperframes lint ink-theater/examples/mocap-figure
```

> Point the linter at a **composition directory** (one that contains an
> `index.html`), not at `examples/` itself — the linter looks for `index.html`
> and there is none at the `examples/` root.

To reuse the engine in your own project, copy `ink-theater.js` (+ `ink-puppet.js`
and `mocap/clips.js` for characters, `assets/patrickhand.ttf` for handwriting)
into the project root — see `../README.md`.
