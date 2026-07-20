# Animated Drawing — animate a supplied drawing/photo with real mocap

> Command: `/animated-drawing` · **Path A (raster).** Sibling: `/ink-art` (vector, from scratch).
> Tool: Meta open-source **AnimatedDrawings** (github.com/facebookresearch/AnimatedDrawings — code MIT, repo archived 2025).

**When to use:** the user *has* a drawing or photo of a **humanoid** character and wants **that image** to move (dance / walk / jump / wave). Output = a raster **GIF (transparent) or MP4** of the original drawing *warped* to the motion. To **create** a vector doodle from scratch that draws itself and moves → use **`/ink-art`** instead.

**What it does:** auto-rigs the drawing (predicts a 16-joint skeleton), then retargets a BVH mocap clip onto it via As-Rigid-As-Possible mesh warp of the flat texture. It only *moves an already-complete drawing* — there is **no draw-on / self-sketching reveal** (that's `/ink-art`).

## Choose a character source — ASK FIRST (never silently reuse a bundled char)

The tool animates *whatever image you give it*, and it needs a **drawn humanoid** (head, 2 arms, 2 legs, limbs separated, plain light bg). Before building, **present the user these options** and pick one (default to *generate* when they have nothing) — this is also what stops every video looking like the same mascot:

1. **User uploads a drawing** — their own humanoid doodle. Best result; it's their character.
2. **User uploads a photo / any image** — first **doodle-ify it** (`image_selector` img2img, FLUX/Recraft: "turn this into a simple child's crayon doodle of a humanoid, full body, plain white bg") → then rig. (The "hand-drawn" look comes from this step; a raw photo warps badly.)
3. **Generate a fresh character** ⭐ (recommended default) — `image_selector` (FLUX/Imagen): *"a child's crayon drawing of a character, full body, front-facing, A-pose with arms and legs separated, plain white background, no shadow, no text."* Unique every video.
4. **Grab a stock character** — `pixabay_image` / `pexels_image`, filtered to a *drawn humanoid on a plain bg*. Hit-or-miss (most stock is photos) — prefer #3.

Bundled example characters are **demo-only** — do not ship them as the user's character. Options 1–4 all need the **auto-rig Docker service** (below); if it isn't up, say so.

## Two run modes

**A · Bundled character + preset motion — turnkey, no Docker (verified on Windows):**
```bash
git clone --depth 1 https://github.com/facebookresearch/AnimatedDrawings.git && cd AnimatedDrawings
# the repo pins Python 3.8 + old wheels; get 3.8 via uv:
uv python install 3.8 && uv venv --python 3.8 .venv
uv pip install --python .venv -e .
uv pip install --python .venv "setuptools<81"      # repo imports pkg_resources but doesn't declare it
.venv/Scripts/python -c "from animated_drawings import render; render.start('./examples/config/mvc/export_gif_example.yaml')"
```
~10–12 s/clip on CPU, no GPU/Docker/model download.

**B · Auto-rig a NEW drawing — heavy (Docker + ~670 MB models, ~16 GB RAM):**
```bash
python image_to_animation.py drawing.png out_dir    # detect → segment → rig → retarget → render
```
Needs the repo's TorchServe container (`docker/`) which downloads `drawn_humanoid_detector.mar` (311 MB) + `drawn_humanoid_pose_estimator.mar` (357 MB). Windows: run the rig stack only via that container (OpenMMLab is Linux-only in practice).

## Input requirements (auto-rig)
One clearly-drawn **humanoid**, roughly T/A-pose (limbs separated, not overlapping), on a **plain light background** (segmentation is threshold + floodfill), exactly one figure.

## Config the agent generates (all YAML)
`char_cfg.yaml` (+ `texture.png`, `mask.png`; auto-produced by `image_to_annotations.py`) · a **motion** config (bvh + frames + groundplane) · a **retarget** config (BVH-joint → rig-joint; reuse bundled `fair1_ppf` / `cmu1_pfp` unless the skeleton differs) · an **MVC** config (`controller.MODE: video_render`, `OUTPUT_VIDEO_PATH`, optional `WINDOW_DIMENSIONS` / `CLEAR_COLOR` / `BACKGROUND_IMAGE` / `CAMERA_POS`).

## Preset motions → retarget config (MUST match the BVH skeleton)
Each bundled BVH is a different skeleton family; using the wrong retarget config **crashes** (`ValueError: 'RightArm' is not in list`). Pair them:

| Motion | BVH folder | retarget config |
|---|---|---|
| `dab`, `wave_hello`, `jumping`, `zombie` | `bvh/fair1/` | `fair1_ppf` |
| `jumping_jacks` | `bvh/cmu1/` | `cmu1_pfp` |
| `jesse_dance` | `bvh/rokoko/` | `mixamo_fff` |

Any other BVH → match its skeleton (or write a retarget config). **Cap long clips** with `end_frame_idx` (`wave_hello` is 839 frames) or the render runs for minutes; ground-contact clips (`dab`, `wave_hello`) render ~8× slower.

## Character variety — animate the USER's drawing (fixes "always the same character")
Bundled characters are **demo-only**. In real use the character is whatever the user **supplies** — unique per video. For a "just make me a video" request with no drawing, **generate a fresh character** (image-gen: "a child's crayon drawing of a …" → PNG on plain light bg) and **auto-rig it** (Docker path) → a different character every time. **Never reuse a bundled char across videos**, or every output looks like the same mascot.

## Compositing into HyperFrames (the second half — required for a real video)
AnimatedDrawings only outputs the moving character. To make a *video* (background, balloons, music), composite in HyperFrames:
- **Transparent output:** `view.CLEAR_COLOR: [0,0,0,0]` in the MVC config → transparent frames.
- **A GIF FREEZES in a deterministic HyperFrames render.** Convert to **VP9 WebM w/ alpha**: `ffmpeg -i char.gif -c:v libvpx-vp9 -pix_fmt yuva420p char.webm`. (`ffprobe` misreports `yuv420p` — alpha is intact.)
- **Video contract (the linter enforces — run `npm run check`):** `<video>` must be a **direct stage child with its own `id`**, NOT nested in a timed `<div>` (nesting **freezes** it); each clip needs its own `data-track-index`; fades need a trailing hard-kill `tl.set(el,{opacity:0})`.
- Text/**balloons** = HTML overlay divs with the full `ink-theater/assets/patrickhand.ttf` (see the ink-theater font gotcha).
- **Pipeline-exempt:** `/animated-drawing` + `/ink-art` are creative entry points, not Rule-Zero pipelines — no `.yaml` manifest.

## Output & honest limits
GIF (transparent) / MP4 (H.264, `avc1`), resolution from `WINDOW_DIMENSIONS` (examples 500×500). **Raster only** (warps the drawing's pixels — zoom shows stretched texture), **humanoid-only**, **no draw-on reveal**, **crude background**. A delightful "your doodle comes to life" novelty; behind a Docker service for the auto-rig path. Not a general vector engine — for white-ink vector doodles that draw themselves, use `/ink-art`.

Sample renders from the session eval: `.tmp/animated-drawings/out/` (`char3_dab.gif`, `char1_zombie.mp4`).
