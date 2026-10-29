---
name: html-frame-studio
description: |
  Deterministic HTML-to-frames-to-video capture via headless Chromium
  (Playwright). Use when: (1) Building step-wise animated scenes authored as
  HTML/CSS (grids, tables, boards, timelines, dashboards, diagram reveals),
  (2) You need one PNG per named visual state with exact hold durations,
  (3) You want a ready ffmpeg concat file for assembly, (4) Frame-exact
  reproducibility matters more than photoreal motion.
metadata:
  openclaw:
    requires:
      env: []
    primaryEnv: PLAYWRIGHT_BROWSERS_PATH
---

# HTML Frame Studio (H2F2V)

Author an HTML scene once, declare its visual states as steps, capture
deterministic PNGs. Tool: `tools/graphics/html_frame_studio.py`
(`html_frame_studio`, capability `graphics`, provider `playwright`).

## Setup

```bash
pip install playwright
playwright install chromium
```

## The scene file

Self-contained HTML: inline `<style>`/`<script>`, no external build step.
Local `file://` assets only (fonts embedded or system; no CDN dependency
unless you accept network flakiness). Design at the capture viewport size.

## State pattern (declarative, preferred)

Drive every visual change from `<body data-step="N">`; the tool sets the
attribute, your CSS reacts:

```html
<style>
  .cell { transition: background .2s, transform .2s; }
  body[data-step="1"] .intro            { opacity: 1; }
  body[data-step="2"] #B1               { background: gold; transform: scale(1.08); }
  body[data-step="2"] .col-B, body[data-step="2"] .row-1 { background: rgba(255,215,0,.25); }
  body[data-step="3"] .found            { color: #2e7d32; font-weight: 700; }
</style>
```

Advantages: the scene documents itself, steps are pure data (no JS blobs),
and reordering steps in the tool input just works.

## Imperative escape hatch

For DOM surgery CSS cannot express, pass `evaluate` JS per step (runs after
`data_step` is applied):

```json
{"name": "move-piece", "evaluate": "swap('B1','C1')", "duration": 2.0}
```

## Step semantics (determinism)

Per step: apply `data_step` -> run `evaluate` -> flush two rAFs -> wait
`wait_ms` (default 150) -> screenshot `frame_NNNN.png`. Consequences:

- CSS transitions triggered by the state change get ~1 frame + wait_ms to
  settle; raise `wait_ms` (300–500) for long transitions, or design states
  transition-free when you want frame-exact stills.
- Wall-clock animations (`@keyframes` loops) are captured wherever they
  happen to be — drive motion from `data-step` styles instead.

## Timing and assembly

- `duration` (seconds, default 2.0) is the hold time recorded per frame in
  `frames_manifest.json` and `frames.txt`.
- `frames.txt` follows the ffmpeg concat demuxer:
  `ffmpeg -f concat -i frames.txt -vsync vfr -pix_fmt yuv420p out.mp4`
- With narration: set each step's `duration` to the matching TTS segment
  length; the manifest stays the single timing source for the edit stage.

## Viewport / DPR guidance

| Target | viewport | device_scale_factor |
|---|---|---|
| 1080p landscape | 1920x1080 | 1 |
| 4K landscape | 1920x1080 | 2 |
| Vertical Short (1080x1920) | 1080x1920 | 1–2 |
| Half-res draft | 960x540 | 1 |

Use `transparent: true` (omit_background) only when compositing frames over
another track, and ensure the scene paints no body background.

## Working example (generic grid highlight)

```html
<!doctype html><html><head><meta charset="utf-8"><style>
  body { margin:0; height:100vh; display:grid; place-items:center; background:#0f172a;
         font-family:system-ui; color:#e2e8f0; }
  .grid { display:grid; grid-template-columns:repeat(6,120px); gap:8px; }
  .cell { height:120px; border-radius:12px; background:#1e293b;
          display:grid; place-items:center; font-size:44px;
          transition:background .25s, transform .25s; }
  body[data-step="2"] .c3 { background:#f59e0b; transform:scale(1.1); }
  body[data-step="3"] .hit { background:#22c55e; }
  body[data-step="4"] #banner { opacity:1; transform:translateY(0); }
  #banner { opacity:0; transform:translateY(24px); transition:all .4s;
            position:absolute; bottom:8vh; font-size:64px; font-weight:800; }
</style></head><body>
  <div class="grid">
    <div class="cell">A1</div><div class="cell c3">B1</div><div class="cell hit">C1</div>...
  </div>
  <div id="banner">MATCH FOUND</div>
</body></html>
```

```json
{"html_path":"grid.html","output_dir":"frames/","viewport":{"width":1920,"height":1080},
 "steps":[
   {"name":"blank grid","data_step":1,"duration":2.0},
   {"name":"scan B1","data_step":2,"duration":2.5},
   {"name":"hit C1","data_step":3,"duration":2.5},
   {"name":"banner","data_step":4,"duration":2.0}]}
```

The same pattern covers spreadsheet-formula walks, chess puzzles, seat maps,
timeline reveals, and dashboard build-ups — swap the grid for any markup.
