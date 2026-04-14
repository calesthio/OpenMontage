# Google Flow Tools — Capability Map

Browser-automated tools for [Google Flow](https://labs.google/fx/tools/flow).
Uses Playwright + your saved Chrome profile. No per-call API cost (subscription credits).

## Setup (one-time)

```bash
python3 -m tools.video.google_flow_setup          # log in and save session
```

---

## `google_flow_video` — Video Generation

```
BEFORE GENERATION
─────────────────────────────────────────────────────
  prompt         (required)  Text prompt
  model          veo_fast* | veo_lite
  aspect_ratio   16:9* | 9:16
  quantity       x1* | x2 | x3 | x4   ← batch count, all downloaded
  download_quality  720p* | 270p(GIF) | 1080p | 4k

  ── EITHER frames ──────────────────────────────────
  first_frame    local image path → Start slot in prompt bar
  last_frame     local image path → End slot in prompt bar

  ── OR ingredients (max 5) ─────────────────────────
  ingredients[]  local image/video paths → + button reference

  (frames and ingredients are mutually exclusive)

AFTER GENERATION (optional)
─────────────────────────────────────────────────────
  camera_motion  none* | dolly_in | dolly_out
                 orbit_left | orbit_up | dolly_out_zoom

  continue_prompt  extend the clip with "What happens next?"
```

### Example

```python
from tools.video.google_flow_video import GoogleFlowVideo

result = GoogleFlowVideo().execute({
    "prompt": "A futuristic city at golden hour, neon reflections on wet streets",
    "model": "veo_fast",
    "aspect_ratio": "16:9",
    "quantity": "x2",            # generate 2 clips, both downloaded
    "download_quality": "720p",
    "camera_motion": "dolly_in",
})
# result.artifacts = ["output_1.mp4", "output_2.mp4"]
```

---

## `google_flow_image` — Image Generation

```
BEFORE GENERATION
─────────────────────────────────────────────────────
  prompt         (required)  Text prompt
  model          nano_banana_pro* | nano_banana | imagen_4
  aspect_ratio   1:1* | 16:9 | 9:16 | 4:3 | 3:4
  quantity       x1* | x2 | x3 | x4   ← batch count, all downloaded
                 (extra images don't cost extra credits)

  ingredients[]  local image/video paths → + button reference (max 5)

DOWNLOAD
─────────────────────────────────────────────────────
  Always "Original size" (full-res PNG) — no quality option for images
```

### Model Guide

| Model | Best For |
|-------|----------|
| `nano_banana_pro` | Text-in-image, posters, CTAs, typography |
| `nano_banana` | General high-quality photorealistic images |
| `imagen_4` | Google Imagen 4 — alternative base model |

### Example

```python
from tools.video.google_flow_image import GoogleFlowImage

result = GoogleFlowImage().execute({
    "prompt": "A minimalist poster for a jazz festival, bold typography, dark background",
    "model": "nano_banana_pro",
    "aspect_ratio": "9:16",
    "quantity": "x4",   # generate 4 options, all downloaded free
})
# result.artifacts = ["output_1.png", "output_2.png", "output_3.png", "output_4.png"]
```

---

## Post-Generation Actions (from recorded session)

After an image or video is generated, the tile's `more_vert` menu exposes:

| Action | How | Available on |
|--------|-----|--------------|
| Download | `role=button name="download Download"` → quality menuitem | image + video |
| Save to Project | `role=menuitem name="library_add Save to Project"` | image + video |
| Add to Scenebuilder | `role=menuitem name="play_movies Add to Scene"` | video |
| Save Frame | `role=button name="add_photo_alternate Save Frame"` | video |

### Scenebuilder (manual / future tool)

`role=button name="play_movies Scenebuilder"` opens a timeline editor:
- Drag clips from library → timeline
- Trim with `Drag to change the start/end of the video clip` handles
- `role=button name="flex_no_wrap Arrange"` — auto-arrange
- `role=button name="Done"` — finalize

---

## File Layout

```
tools/video/
├── _google_flow_base.py      shared helpers (browser, settings, download)
├── google_flow_image.py      GoogleFlowImage tool
├── google_flow_video.py      GoogleFlowVideo tool
├── google_flow_setup.py      one-time login setup
└── GOOGLE_FLOW_TOOLS.md      ← this file
```

## Session / Auth

- Profile stored at `~/.openmontage/google_flow_profile/` (persistent Chrome)
- Cookies cached at `~/.openmontage/google_flow_session.json`
- Re-run setup if session expires: `python3 -m tools.video.google_flow_setup`
- Project URL hardcoded in `_google_flow_base.py → DEFAULT_FLOW_URL`
