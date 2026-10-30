---
name: mlx-movie-director
description: Use when routing image generation to mlx_image OR video generation to mlx_video (Apple-Silicon-native MLX via the sibling mlx-movie-director repo). Covers image pipeline choice (zimage/flux2-klein/lens), ControlNet, i2i, LoRA, faceswap, video LTX-2.3 i2v/t2v/t2i2v, availability gating, and the MLX_MOVIE_DIRECTOR_DIR / MLX_VENV_PYTHON environment contract.
---

# MLX Movie Director (run.py) in OpenMontage

Use this skill before calling `mlx_image` (image) or `mlx_video` (motion), and
whenever a brief wants a local, `$0` Apple-Silicon path for ControlNet, true
image-to-image, LoRA conditioning, BFS face/head swap, or native LTX-2.3 i2v/t2v
— surfaces no other OpenMontage provider covers on Apple Silicon (only
`grok_image`'s edit mode partially overlaps on the image side).

## Environment Contract

`mlx_image` shells out to the sibling MLX repo. Two env vars wire it up (set
them in the OpenMontage deployment environment, not per-call):

- **`MLX_MOVIE_DIRECTOR_DIR`** — repo root containing
  `python/mlx-movie-director/run.py`. Without this the tool is UNAVAILABLE.
- **`MLX_VENV_PYTHON`** — the MLX venv interpreter. Defaults to
  `<MLX_MOVIE_DIRECTOR_DIR>/python/venv/bin/python`. **This venv is per-machine
  and NOT auto-created** (per the MLX repo's CLAUDE.md). On a fresh clone or
  after `git clean` it is absent; recreate it:
  ```
  uv venv python/venv --python 3.12
  uv pip install -r python/mlx-movie-director/requirements.txt --python python/venv/bin/python
  ```
  Two runtime deps are not yet in that requirements.txt (tracked as an upstream
  MLX-repo gap) — install them into the same venv after the requirements
  install: `opencv-python` (the image-quality command imports `cv2`) and
  `mflux` (the Z-Image VAE loader).

Apple Silicon (`arm64`) is required. The provider's `get_status()` returns
UNAVAILABLE with the exact recreate command when the venv is missing — surface
that reason to the user; do not retry silently.

## Choosing a Pipeline

The `pipeline` input selects the MLX model family (the `--pipeline` flag passed
through to `run.py image`):

- **`zimage`** (default) — Moody 12.6 DPO turbo. ~1.5 s/step, 9 steps default.
  Best for portraits and general T2I. CFG is opt-in (the model was distilled at
  guidance 0.0; set `cfg_scale` > 1.0 only for an experimental dual-forward).
- **`flux2-klein`** — Klein 9B (or 4B). ~10 s/step, 4 steps. Better for
  consistent characters; the edit-class backend for angle / i2i / faceswap /
  profile. Distilled — CFG inert for T2I.
- **`lens`** — Microsoft Lens 3.8B, pure MLX, high-res. ~0.4 s/step, 20 steps,
  1024² default. `cfg_scale` default 4.0. No LoRA / ControlNet / i2i.

Resolution: omit `width`/`height` to use the per-pipeline model-optimal default
(zimage/klein 640×960, lens 1024²). Pass `resolution` for a named tier
(`model` / `benchmark` / `large`) or explicit `WxH` (snapped to a multiple of
16) — useful for QA / self-learning at larger sizes.

## ControlNet, i2i, and Faceswap

These are the capabilities that justify choosing `mlx_image` over cloud
providers. The provider infers the `run.py image` action from the inputs:

| Inputs present | run.py action | Notes |
|---|---|---|
| `image`/`image_path` + `face` | `faceswap` | BFS face/head swap (Flux2 Klein + BFS LoRA). Set `face_mode`: `face` (face only) or `head` (head + hair). |
| `image` + `controlnet_type` or `controlnet_strength` | `controlnet` | Z-Image native ControlNet. `controlnet_type` e.g. `pose`. |
| `image` only | `i2i` | Image-to-image. Set `denoise_strength` (0–1; higher = more change). Optional `reference_image` for pose/style conditioning. |
| neither | `t2i` | Text-to-image. |

For i2i and controlnet, `image`/`image_path` maps to run.py's `--input-image`
(not `--input`). For faceswap it maps to `--input` (the body) and `face` to
`--face` (the source). The provider handles this mapping; callers just pass
`image`/`image_path` and `face`.

## LoRA Stacks

Pass `lora_path` (list of `.safetensors` paths) and a paired `lora_scale` list
(same order, one per path). The provider emits `--lora-path`/`--lora-scale`
pairs. If a single scale is given it is broadcast to the first path only —
prefer explicit per-path scales. LoRAs apply to the zimage and flux2-klein
pipelines (lens has no LoRA story).

## What mlx_image Does NOT Support

- **No `negative_prompt`** — run.py image T2I has no `--negative-prompt` flag
  (Z-Image handles negatives internally). Do not pass one; the selector strips
  it.
- **No CUDA / non-Apple-Silicon** — the MLX runtime is MPS-only. On a CUDA box
  prefer `comfyui_image` (which bundles FLUX2 NVFP4 for Blackwell/DGX Spark).
- **No `custom_workflow`** — `mlx_image` is not a ComfyUI-graph backend. For an
  arbitrary ComfyUI workflow, route to `comfyui_image` instead (the selector's
  `_filter_candidates` handles this when `workflow_json`/`workflow_path` +
  `output_node` are present).

## Provenance

Each result carries `provider: "mlx"`, `model: "mlx-<pipeline>"` (or
`mlx-<pipeline>/<transformer>` when a transformer is named), `pipeline`,
`action`, `seed`, and `mlx_run_py` (the exact `run.py` path invoked). Treat
seed + pipeline + transformer + prompt as the reproducibility contract; MLX
generation is byte-deterministic for a fixed seed on the same stack.

## When to Pick mlx_image

- A brief asks for ControlNet-conditioned generation, true i2i edit, LoRA
  character/style conditioning, or face/head swap — and the box is Apple Silicon.
- Cost matters (every cloud provider charges per image; mlx_image is `$0`).
- Offline / air-gapped generation is required.
- The scorer ranks it highly: it advertises the full `control` surface
  (controlnet/img2img/reference_image/faceswap/lora), so it wins the `control`
  and `cost_efficiency` dimensions decisively.

---

# Video (mlx_video)

`mlx_video` wraps LTX-2.3 22B (`run.py video generate` / `video t2i2v`). It is
the **Apple-Silicon-native** motion path: OM's other local i2v providers
(wan/hunyuan/ltx/cogvideo) need CUDA `diffusers` and don't run on MPS.

## Action Routing

| Inputs | run.py action | Mode | Notes |
|---|---|---|---|
| prompt only | `video t2i2v` | T2V | The 3-stage ZImage T2I → VLM prompt → LTX-2.3 dasiwa animate pipeline (MLX's headline path). Richer, slower. |
| `reference_image`/`image_path` present | `video generate` | I2V | Direct LTX-2.3 image-to-video with `--input-image`. Faster. |
| explicit `action: "generate"` (no image) | `video generate` | T2V | Direct LTX-2.3 text-to-video. |
| explicit `action: "t2i2v"` + image | `video t2i2v` | I2V | t2i2v with a keyframe; otherwise generates the keyframe from the prompt. |

Frame count must be `8k+1` (25, 33, 41, 49, 57, 65, …, default 97 ≈ 4 s @ 24 fps).
Dimensions auto-snap to a multiple of 64 (default 704×448).

## Honest Surface — What mlx_video Is NOT

`mlx_video` deliberately does NOT advertise `cinematic_quality`, `lip_sync`,
`multi_shot`, `native_audio`, or `dialogue_generation`. Those are premium cloud
flags (seedance / veo / kling / runway). LTX-2.3 local is a **free offline
default** — the right pick when cost or offline operation matters, NOT a
replacement for premium cinematic delivery. The `best_for` / `not_good_for`
fields steer the scorer accordingly.

## Motion-Required Governance

For a `motion_required=true` brief, the locked `render_runtime`
(FFmpeg / Remotion / HyperFrames) is a **compose-stage** commitment.
`mlx_video` is a *generation* provider — it produces a clip, it does not
satisfy or substitute for the compose runtime, and a silent runtime swap
remains a CRITICAL violation (see `AGENT_GUIDE.md` "Motion-Required Requests").
`mlx_video`'s `fallback_tools` deliberately excludes `image_selector` so a
motion-required brief can never silently degrade to a still image.

## When to Pick mlx_video

- An image-led scene needs motion on Apple Silicon without a cloud call.
- Cost matters (cloud motion providers charge per second; mlx_video is `$0`).
- Offline / air-gapped motion generation.
- Preflight draft motion before spending on a premium seedance/veo render.
