# HTML Scene Studio (H2F2V) Usage for OpenMontage

> Sources: `tools/graphics/html_frame_studio.py` (tool contract),
> Layer 3 skill at `.agents/skills/html-frame-studio/SKILL.md`

## What it is

HTML-to-Frames-to-Video: the agent authors a **self-contained HTML scene**
(inline CSS/JS, no build step), declares an ordered list of **visual steps**,
and the tool captures one deterministic PNG per step in headless Chromium —
plus a timing manifest and a ready ffmpeg concat file. It is the standardized
path for scenes that are easiest to express as markup: grids, tables, boards,
timelines, dashboards, diagram reveals, typography toys.

This is deliberately **Excel-agnostic**: a spreadsheet-grid scene is just one
template. Anything you can lay out in HTML can become a frame-exact video.

## When to choose it

| Need | Reach for |
|---|---|
| Grid/table/board/diagram scenes with step-wise highlights | **html_frame_studio** |
| React catalog scenes (text cards, charts, callouts) + spring motion | Remotion (`video_compose`) |
| GSAP kinetic typography / promo pages | HyperFrames |
| Photoreal moving footage | video generation providers |
| Recording a real interactive app | `screen_recorder` / playwright-recording |

Rule of thumb: if you would start by drawing a `<table>`/CSS grid and toggling
classes, H2F2V is the shortest path; if you would start by importing a React
component, stay in Remotion.

## Pipeline position

- **assets stage**: write the scene HTML into the project workspace (e.g.
  `projects/<id>/assets/html/scene.html`), run `html_frame_studio` with
  `output_dir` under `projects/<id>/assets/frames/`. Record outputs in the
  `asset_manifest` like any other generated frames (provenance: provider
  `playwright`, list the steps).
- **edit/compose stage**: assemble with the existing video tooling —
  `frames.txt` is an ffmpeg concat-demuxer file (`ffmpeg -f concat -i
  frames.txt -vsync vfr out.mp4`), or feed the frame list to
  `video_compose`/`video_stitch` with per-frame durations from
  `frames_manifest.json` when mixing with narration timing.
- Pair with TTS narration by setting each step's `duration` from the matching
  narration segment length (the manifest is the single source of timing truth).

## Contract snapshot

```python
HtmlFrameStudio().execute({
    "html_path": ".../scene.html",       # self-contained scene
    "output_dir": ".../assets/frames/",
    "steps": [
        {"name": "intro",     "data_step": 1, "duration": 2.5},
        {"name": "highlight", "data_step": 2, "duration": 3.0},
        {"name": "reveal",    "evaluate": "document.getElementById('x').classList.add('show')", "duration": 2.0},
    ],
    "viewport": {"width": 1080, "height": 1920},   # vertical Short
    "device_scale_factor": 2,                       # retina-sharp
})
# -> frame_0001.png ... + frames_manifest.json + frames.txt
```

Read `.agents/skills/html-frame-studio/SKILL.md` (Layer 3) BEFORE authoring
the scene HTML — it covers the `body[data-step]` state pattern, settle
semantics, fonts, and viewport/DPR guidance.
