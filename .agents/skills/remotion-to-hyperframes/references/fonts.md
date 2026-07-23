# Font translation

Fonts are the dominant non-translation noise floor. Same `font-weight: 800`
renders perceptibly bolder on HF's `chrome-headless-shell` than on
Remotion's bundled Chromium when there's no real font installed. Validation
showed this costs ~0.025 mean SSIM at the noise floor.

## Pattern: `@remotion/google-fonts/<Family>`

```tsx
import { loadFont } from "@remotion/google-fonts/Inter";
loadFont("normal", { weights: ["400", "800"] });
```

Translate to a `<link>` tag in `<head>`:

```html
<head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link
    href="https://fonts.googleapis.com/css2?family=Inter:wght@400;800&display=swap"
    rel="stylesheet"
  />
  <style>
    body {
      font-family: Inter, sans-serif;
    }
  </style>
</head>
```

Pull the family name and weights from the import path and `loadFont`
arguments. HF's compiler inlines the Google Fonts CSS at render time, so
you don't pay a network round-trip per render.

## Pattern: local fonts via `@font-face`

```tsx
import { Font } from "remotion";

Font.loadFont("/MyFont.woff2", "MyFont");
```

Translate to a `@font-face` rule:

```html
<style>
  @font-face {
    font-family: "MyFont";
    src: url("assets/MyFont.woff2") format("woff2");
    font-weight: 400;
    font-style: normal;
  }
</style>
```

Copy the font file into `hf-src/assets/` next to the HTML.

## Pattern: system font fallback (no font load)

```tsx
<div style={{ fontFamily: "Helvetica, Arial, sans-serif" }}>...</div>
```

Same string in HF — but be aware: on Linux without a real Helvetica
installed (typical CI environment), Remotion and HF fall back to
_different_ sans-serif system fonts because they bundle different
Chromium versions. This is the noise floor: ~0.025 mean SSIM cost,
visible as different stroke widths at large font weights (800+).

If matching the Remotion render exactly matters for a specific
fixture, load the same font explicitly — don't rely on system
fallback.

## When in doubt: use Inter

Inter renders identically across Chromium versions and is free.
Translate any "system sans-serif" Remotion comp to Inter when you
need to minimize font drift in the validation harness.

## Font loading and `delayRender`

Remotion uses `delayRender()` to defer the first frame until fonts
load. HF's compiler inlines Google Fonts at compile time and waits
on `@font-face` readiness via the Frame Adapter pattern — the
`delayRender` call drops in translation. See [media.md](media.md).

## Multi-weight loading

When Remotion loads multiple weights:

```tsx
loadFont("normal", { weights: ["400", "500", "700", "800"] });
```

Inline all weights in the Google Fonts URL:

```
?family=Inter:wght@400;500;700;800&display=swap
```

Translation rule: enumerate every distinct `font-weight` value
that appears in the composition's CSS (`font-weight: 800` →
weight 800 must be loaded). If the Remotion source loads weights
that aren't actually used, drop them.

## Font subsetting

Remotion's `loadFont` doesn't subset; HF's compiler doesn't either
(yet). Don't try to optimize this in translation — it's lossless to
keep the same weight set as the Remotion source.
