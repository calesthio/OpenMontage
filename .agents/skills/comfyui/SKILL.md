---
name: comfyui
description: Use when working with ComfyUI workflows in OpenMontage, including comfyui_image/comfyui_video/comfyui_music, custom workflow_json/workflow_path inputs, output_node selection, missing model setup, LoRAs, low-VRAM workflow choices, and community workflow imports.
---

# ComfyUI Workflows in OpenMontage

Use this skill before calling `comfyui_image`, `comfyui_video`, or `comfyui_music`, and when converting a community ComfyUI workflow into an OpenMontage tool call.

## Server Contract

- ComfyUI must be running before the tool can generate. The default server is `http://localhost:8188`; override it with `COMFYUI_SERVER_URL`.
- Running separate ComfyUI instances per capability (different GPU, different model set)? `COMFYUI_IMAGE_SERVER_URL` / `COMFYUI_VIDEO_SERVER_URL` / `COMFYUI_MUSIC_SERVER_URL` each override `COMFYUI_SERVER_URL` for that one tool only. Optional -- a single-server setup needs none of these.
- Health and hardware status come from `GET /system_stats`.
- Jobs are submitted to `POST /prompt`, completed outputs are read from `GET /history/{prompt_id}`, and artifact bytes are downloaded with `GET /view`.
- Long waits (video, music) prefer ComfyUI's websocket feed for immediate completion/error detection and transparently fall back to REST polling if `websocket-client` isn't installed. Either way, a timeout is recoverable: pass the error's `prompt_id` back in as `resume_prompt_id` to resume waiting on the same job instead of resubmitting it.
- Export workflows with ComfyUI's API-format JSON, not the UI layout format. If a downloaded workflow will not submit, re-export it from ComfyUI with API format enabled.

### Partner Nodes are hosted

- `gemini_omni_flash`, `seedance_2.5`, and `minimax_h3_api` in
  `comfyui_video` are official ComfyUI Partner Nodes. They call hosted APIs and
  require network access, a logged-in Comfy account, and prepaid credits.
- Do not describe Partner Nodes as local, offline, or free merely because the
  graph runs in a local ComfyUI process.
- `minimax_h3_local` is a separate open-weight path that runs locally. It uses a
  bundled T2V/I2V workflow (20-step base mode, native stereo audio) once the four
  model files in `get_info()["bundled_model_stacks"]["minimax_h3_local"]` are
  installed. Pass `workflow_path`/`workflow_json` + `output_node` only to
  override it. See "Bundled open-weight workflows" below for limits and licences.

## Bundled open-weight workflows

- **MiniMax H3 (`comfyui_video`, `model_family: "minimax_h3_local"`)**
  - `duration` is 4-15 s and snaps up to the `17k + 5` frame grid at 24 fps (5 s = 124 frames). `steps` defaults to 20.
  - Canvas: 1344x768 (16:9) or 768x1344 (9:16), long edge <= 1344 and short edge <= 768, multiples of 32. Larger sizes (including the 1.0 MP preset, which gives a 1376 px edge) are rejected. Local H3 is 768p only; 2K regeneration is API-only.
  - Image-to-video stretches the first frame to the canvas, so an unspecified canvas follows the reference image's aspect ratio. Keep the reference close to 16:9 or 9:16.
  - The weights are heavy on host RAM as well as VRAM. The bundled graph has no Turbo LoRA; use a custom workflow for 8-step drafts.
  - Licence: not authorised in the EU, UK, South Korea or the US, outputs included (`get_info()["license_notes"]`). Tell the user before using it.
- **Qwen-Image-2.1 (`comfyui_image`, `model_family: "qwen_image_2.1"`)**
  - Text-to-image only. Defaults: 40 steps (the model card's setting; 25 is faster but fixed fewer prompt-adherence errors in our eval), CFG 1.0 (base Qwen-Image-2.1 runs at CFG 1, so `negative_prompt` has little effect). Do not reuse FLUX's guidance 3.5. Each side must be a multiple of 32 within 256-2752 and the area at most 2400x1792.
  - Edit, multi-reference and the prompt enhancer are not bundled; use a custom workflow.
  - Licence: Qwen Research License, non-commercial only (`get_info()["license_notes"]`). Tell the user before using it.
- Both bundled graphs were written by hand in API format from the official Comfy-Org templates and checked against the node schemas and by contract tests. The Qwen-Image-2.1 graph matches one that has been run on a rented RTX 4090; the MiniMax H3 T2V/I2V graphs have **not been run end-to-end on a GPU yet** (they reuse the loader/sampler/decode chain of H3 graphs that have). Treat the first H3 generation on a new server as the real validation and report any `/prompt` validation error verbatim.

## Choosing a Workflow

- Use bundled workflows when the requested operation matches and the local machine has the required models and VRAM.
- Use a custom `workflow_json` or `workflow_path` when the user needs a community recipe, a lower-VRAM model, a different style family, or custom nodes.
- For 8GB-12GB GPUs, prefer lower-footprint workflows such as Wan 2.1 1.3B, LTXV FP8 or quantized workflows, or Wan 2.2 GGUF/quantized community workflows. The bundled Wan 2.2 14B FP8 video workflows are a 16GB-class path, not a provider-wide floor.
- Do not promise that arbitrary custom workflows will fit a machine. The workflow, quantization, resolution, frame count, and offload settings determine the real resource envelope.

## Output Node Contract

- Custom workflows must pass `output_node`.
- Pick the node that writes the artifact, usually `SaveImage`, `SaveVideo`, `VHS_VideoCombine`, or another terminal saver node.
- Pass the node ID as a string, for example `"108"`. Do not pass the class name.
- If a workflow has multiple savers, choose the final deliverable node, not previews or intermediates.

## Templated vs Fixed Nodes

- Identify templated nodes before execution: prompt text, seed, dimensions, frame count, source image, sampler settings, and output filename prefix.
- Fixed nodes are model loaders, VAEs, text encoders, LoRA loaders, schedulers, and graph wiring. Do not mutate those unless the workflow author intended that customization.
- For community workflows, inspect each loader node and note every required model or custom node before running. Missing models should be handled through the tool's structured `missing_models` payload when available.

### Video workflows need a temporal latent

- A video workflow's empty-latent node must be a **video** latent -- `EmptyHunyuanLatentVideo` for Wan 2.2 t2v, `Wan22ImageToVideoLatent` or `WanImageToVideo` for the image-conditioned variants. The frame count goes in `length`; `batch_size` is how many separate clips to generate and stays at `1`.
- `EmptyLatentImage` with `batch_size` set to the frame count is a trap: it asks for N unrelated images, and the resulting MP4 has the right frame count, duration and codec and passes `ffprobe` cleanly -- it just strobes. Check the latent node before running any unfamiliar video workflow.

## Model and LoRA Setup

- Use ComfyUI Manager or the workflow author's model links when available, and respect model licenses.
- Place models in the folders expected by the loader nodes: diffusion models under `ComfyUI/models/diffusion_models/`, text encoders under `ComfyUI/models/text_encoders/`, VAEs under `ComfyUI/models/vae/`, and LoRAs under `ComfyUI/models/loras/`.
- For LoRA stacks, use `LoraLoader` or `LoraLoaderModelOnly` chains in the workflow. Record each LoRA name plus `strength_model` and `strength_clip` when applicable.
- The current ComfyUI tools do not inject LoRAs into arbitrary graphs. To use LoRAs, provide a workflow that already contains the LoRA loader chain and pass model-stack provenance.

## Provenance

- For custom workflows, provide `workflow_name` and `workflow_model` when known.
- Provide `workflow_model_stack` for reproducibility when the workflow is not bundled. Include base checkpoint or diffusion model, quantization, text encoder, VAE, LoRAs and strengths, sampler or scheduler, steps, and guidance if the workflow exposes them.
- The tools record the final workflow hash. Treat that hash plus the model stack, seed, dimensions, and prompt as the reproducibility contract.

## Failure Handling

- If the server is unavailable, surface the structured setup offer. Starting ComfyUI or setting `COMFYUI_SERVER_URL` is the first fix.
- If models are missing, read `data.missing_models[]`; each item should include the file name, role, destination hint, and download URL when OpenMontage knows it.
- If custom nodes are missing, ask the user to install them through ComfyUI Manager or the workflow author's documented install path, then restart ComfyUI.
- If a long render times out locally, check ComfyUI history before retrying from scratch; the server may still have completed the prompt -- or just call again with `resume_prompt_id` set to the `prompt_id` from the timeout error.

## Music (`comfyui_music`)

- Bundled default is ACE-Step v1 (3.5B) text-to-audio, built from ComfyUI's *native* `TextEncodeAceStepAudio`/`EmptyAceStepLatentAudio` nodes (core, not a third-party pack) -- unlike ACE-Step 1.5 or other custom node packs, v1's interface is standardized enough to bundle safely.
- `prompt` maps to the bundled workflow's `tags` field (style/genre/mood, e.g. `"upbeat electronic pop, female vocals"`), matching the same "prompt = music description" convention `suno_music` uses. `lyrics` is a separate optional field -- leave empty for instrumental, or use `[verse]`/`[chorus]`/`[bridge]` structure tags and `[zh]`/`[ja]`/`[ko]`-style language-code prefixes for non-English lines.
- `duration_seconds`, `steps`, `cfg`, `lyrics_strength`, and `seed` are patchable on the bundled workflow. Missing `ace_step_v1_3.5b.safetensors` surfaces through the same `data.missing_models[]` contract as image/video.
- Need ACE-Step 1.5, a different node pack, or a non-ACE-Step audio model? Fall back to `workflow_json`/`workflow_path` + `output_node`, exactly like a custom image/video workflow -- in that mode `prompt` becomes provenance/logging only again and must already be baked into the graph.
- `output_node` (bundled or custom) should be the node that writes the final audio -- the bundled workflow's is `SaveAudioMP3`. The client reads artifacts from that node's `"audio"` output key (parallel to `"images"` for image/video savers).
- For custom workflows, provide `workflow_name`/`workflow_model`/`workflow_model_stack` for provenance exactly as you would for a custom image/video workflow.
