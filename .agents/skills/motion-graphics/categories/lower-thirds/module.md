# lower-thirds — category module

**Name/title bars, callouts, social overlays** — graphics meant to sit over other footage. Asset-free (+ optional logo). Usually `export: alpha-overlay` (transparent). ~3–6s (or loop/hold).

## Plan (Director)

`content`: `{ name, role, position (lower-left / lower-third / corner), brand_colors[] }`. Default `export: alpha-overlay`.

## Vocabulary / leans on

- Blocks: `caption-*` (pill-karaoke, neon-accent, editorial-emphasis) + registry **overlay** blocks (`instagram-follow`, `tiktok-follow`, `yt-lower-third`, `x-post`, `spotify-card`, `macos-notification`).
- Primitives: slide/wipe-in · bar reveal · `glow` · fade/slide-out.

## Build (reuse-first)

Reuse the closest overlay/caption block + set name / role / handle / brand colors / position; **or** hand-author a bar that wipes in (`scaleX` from 0, `transform-origin:left`) with text sliding up behind it, hold, slide out. **Transparent background** (`export: alpha-overlay` → `render --format webm/mov`) so it composites over footage. Keep it in the title-safe lower band.
