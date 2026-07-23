# When to bow out: the runtime interop pattern

Some Remotion compositions can't be translated cleanly. The skill should
recognize them upfront and recommend the **runtime interop pattern** from
[PR #214](https://github.com/heygen-com/hyperframes/pull/214) instead of
producing broken HTML.

## When to recommend interop

Run `scripts/lint_source.py` first. If it returns any blocker, recommend
interop. The blockers are:

| Rule                        | What it catches                                                |
| --------------------------- | -------------------------------------------------------------- |
| `r2hf/use-state`            | useState driving animation                                     |
| `r2hf/use-reducer`          | useReducer driving animation                                   |
| `r2hf/use-effect-deps`      | useEffect/useLayoutEffect with non-empty deps (side effects)   |
| `r2hf/async-metadata`       | calculateMetadata returns a Promise                            |
| `r2hf/third-party-react-ui` | Imports from MUI, Chakra, Mantine, antd, shadcn, Radix, NextUI |

Each of these breaks the seek-driven, deterministic-frame model that HF
relies on. Translating them produces silently-wrong output.

## What the interop pattern actually does

Per [PR #214](https://github.com/heygen-com/hyperframes/pull/214), the
runtime adapter:

1. Bundles the user's Remotion code with React + `@remotion/player` via esbuild.
2. Mounts a Remotion `<Player>` inside an HF composition's HTML.
3. Pauses the player on mount.
4. Registers the player on `window.__hfRemotion` with `seekTo(frame)`,
   `pause()`, `durationInFrames`, `fps`.
5. HF's render loop seeks the player frame-by-frame via `seekTo(frame)`.

Result: Remotion's React tree renders at HF's deterministic frame ticks.
Custom hooks, useState, useEffect, MUI components — all work because
Remotion's React reconciler is doing the rendering.

## The recommendation message

When the skill detects a blocker, output something like:

> The Remotion source uses `useState` (and others), which can't be
> translated to HF's seek-driven HTML model. The recommended path is the
> **runtime interop pattern**: bundle your Remotion code with `@remotion/player`
> and let HF drive it frame-by-frame.
>
> See https://github.com/heygen-com/hyperframes/pull/214 for the full
> implementation. Quick summary:
>
> 1. Bundle `entry.tsx` with esbuild: `npx esbuild entry.tsx --bundle --outfile=dist/bundle.js --format=iife --jsx=automatic`
> 2. Mount the Player and register on `window.__hfRemotion`:
>
>    ```tsx
>    const playerRef = useRef<PlayerRef>(null);
>    useEffect(() => {
>      playerRef.current?.pause();
>      window.__hfRemotion = window.__hfRemotion || [];
>      window.__hfRemotion.push({
>        seekTo: (f) => playerRef.current?.seekTo(f),
>        pause: () => playerRef.current?.pause(),
>        durationInFrames,
>        fps,
>      });
>    }, []);
>    ```
>
> 3. Reference the bundle from your HF `index.html` and render normally:
>    `<script src="dist/bundle.js"></script>`

## The lint output already includes recommendations

`lint_source.py` emits a `recommendation` field per finding. Surface those
verbatim — they're tuned per blocker rule:

```json
{
  "rule": "r2hf/use-state",
  "message": "useState detected — Remotion compositions that drive animation via React state are not deterministic frame-capture targets in HyperFrames",
  "recommendation": "Use the runtime interop pattern from PR #214 instead of attempting a translation"
}
```

## When NOT to bow out: warnings only

Some patterns produce warnings, not blockers — translate after dropping
the wrappers:

| Rule                      | Action                                                              |
| ------------------------- | ------------------------------------------------------------------- |
| `r2hf/lambda-import`      | drop the `@remotion/lambda` config; HF runs single-machine, log gap |
| `r2hf/delay-render`       | drop the call; HF handles asset readiness                           |
| `r2hf/use-callback`       | drop the wrapper, inline the function                               |
| `r2hf/use-memo`           | drop the wrapper, compute inline                                    |
| `r2hf/custom-hook` (pure) | inline the hook body if it's a derivation of `useCurrentFrame`      |
| `r2hf/static-file`        | replace `staticFile("x")` with `"assets/x"`                         |
| `r2hf/interpolate-colors` | translate to GSAP color tween (see [timing.md](timing.md))          |

These are documented in T4 cases 05–07.

`r2hf/lambda-import` is a warning — not a blocker — because Lambda
configuration is orthogonal to the rendered composition. Translating an
otherwise-clean Remotion comp shouldn't fail just because the author also
configured AWS Lambda for distributed rendering. The skill drops the
`@remotion/lambda` imports and `renderMediaOnLambda(...)` calls in step 3
(Generate) and writes a `TRANSLATION_NOTES.md` entry so the user knows to
set up HF rendering separately.

## When the source has BOTH blockers AND warnings

Bow out. The presence of a single blocker means the skill shouldn't
attempt translation — even if the rest of the composition is clean.
The user should use interop for the whole thing OR refactor the
blocker patterns out of their Remotion source first.
