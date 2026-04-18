# ComfyUI Provider Adapter for OpenMontage

**RFC: Native ComfyUI backend for image, video, and music generation**

---

## Motivation

OpenMontage's local GPU tools (`wan_video`, `hunyuan_video`, `cogvideo_video`,
`local_diffusion`) use HuggingFace `diffusers` directly. This works on x86 +
consumer GPUs but breaks on newer hardware where the PyTorch ecosystem hasn't
caught up:

| Issue | Detail |
|-------|--------|
| **NVIDIA Blackwell (sm_121)** | No stable PyTorch wheels for aarch64 + CUDA 13.0. Requires NGC containers or nightly builds. |
| **Flash Attention** | Does not support sm_121. Must be replaced with SageAttention v3 or native SDPA. |
| **Unified Memory (GB10/DGX Spark)** | `nvidia-smi` cannot report VRAM. Diffusers' memory estimation breaks. |
| **Model format mismatch** | Diffusers expects HF repos. Production deployments use `.safetensors` checkpoints with quantized variants (NVFP4, FP8) that diffusers doesn't natively load. |

ComfyUI already solves all of these. NVIDIA ships official ComfyUI containers
for DGX Spark. The community has optimized workflows for Blackwell (SageAttention,
NVFP4 quantization, LightX2V 4-step LoRAs). Models like WAN 2.2, FLUX 2,
and ACE-Step run reliably through ComfyUI on hardware where diffusers cannot.

A ComfyUI adapter gives OpenMontage access to any model ComfyUI supports,
on any hardware ComfyUI runs on, without shipping or maintaining PyTorch builds.

---

## Design

### Architecture

```
OpenMontage Agent
    |
    v
video_selector / image_selector / music_selector
    |                                        
    v                                        
comfyui_video    comfyui_image    comfyui_music    (new tools)
    |                |                |
    v                v                v
ComfyUI REST API  (POST /prompt, GET /history, GET /view)
    |
    v
GPU (any hardware ComfyUI supports)
```

### Integration model

Three new `BaseTool` subclasses plus one shared client library:

```
tools/
  _comfyui/
    __init__.py
    client.py              # Shared ComfyUI REST client
    workflows/             # Bundled workflow templates
      flux2-txt2img.json
      wan22-t2v-4step.json
      wan22-i2v-4step.json
      ace-step-music.json
  graphics/
    comfyui_image.py       # capability="image_generation", provider="comfyui"
  video/
    comfyui_video.py       # capability="video_generation", provider="comfyui"
  audio/
    comfyui_music.py       # capability="music_generation", provider="comfyui"
```

### Zero changes to selectors or registry

The tools declare `capability` and `provider` as class attributes.
`tool_registry.discover()` picks them up automatically via `pkgutil.walk_packages`.
`video_selector`, `image_selector`, and `music_selector` find them via
`registry.get_by_capability()` -- no hardcoded references needed.

---

## Shared Client: `tools/_comfyui/client.py`

Encapsulates the ComfyUI REST API pattern proven in production (used by the
Bard project's Airflow DAGs for thousands of generations):

```python
class ComfyUIClient:
    """Thin client for the ComfyUI REST API."""

    def __init__(self, server_url: str | None = None):
        self.server_url = server_url or os.environ.get(
            "COMFYUI_SERVER_URL", "http://localhost:8188"
        )

    def is_available(self) -> bool:
        """Health check -- can we reach the server?"""

    def submit(self, workflow: dict) -> str:
        """POST /prompt. Returns prompt_id. Raises on node_errors."""

    def poll(self, prompt_id: str, timeout: int = 600, interval: int = 5) -> dict:
        """GET /history/{prompt_id} until complete. Returns outputs dict."""

    def download(self, filename: str, subfolder: str, dest: Path) -> Path:
        """GET /view?filename=...&type=output. Writes bytes to dest."""

    def upload_image(self, local_path: Path, name: str) -> str:
        """POST /upload/image. Returns server-side filename for LoadImage nodes."""

    def generate(self, workflow: dict, output_node: str, dest: Path,
                 timeout: int = 600) -> Path:
        """Full cycle: submit -> poll -> download. Returns artifact path."""
```

**Why a shared client?** The submit/poll/download cycle is identical across
image, video, and music generation. The only differences are: which workflow
template, which nodes to customize, and which output node to read from.

---

## Tool Specifications

### `comfyui_image` -- Image Generation

| Field | Value |
|-------|-------|
| capability | `image_generation` |
| provider | `comfyui` |
| runtime | `LOCAL_GPU` |
| tier | `GENERATE` |
| stability | `EXPERIMENTAL` |
| capabilities | `text_to_image`, `image_to_image` |
| dependencies | (runtime: ComfyUI server reachable) |
| fallback_tools | `flux_image`, `local_diffusion`, `openai_image` |
| cost | `$0.00` (local compute) |

**Bundled workflow:** `flux2-txt2img.json`

Loads FLUX 2 Dev (NVFP4) with Mistral text encoder. Templated nodes:

| Node | Class | Templated field |
|------|-------|-----------------|
| 4 | CLIPTextEncode | `text` (prompt) |
| 6 | EmptyFlux2LatentImage | `width`, `height` |
| 7 | RandomNoise | `noise_seed` |
| 10 | Flux2Scheduler | `steps` |
| 13 | SaveImage | `filename_prefix` |

**Input schema:**

```yaml
prompt:        string    # required
width:         integer   # default 1024
height:        integer   # default 1024
steps:         integer   # default 20
seed:          integer   # optional (random if omitted)
guidance:      number    # default 3.5
output_path:   string    # where to save the image
workflow_json: string    # optional override (full custom workflow)
```

**get_status():** Pings ComfyUI server. Returns `AVAILABLE` if reachable, `UNAVAILABLE` otherwise.

**execute() flow:**
1. Deep-copy workflow template
2. Inject prompt, seed, dimensions, steps into templated nodes
3. `client.generate(workflow, output_node="13", dest=output_path)`
4. Return `ToolResult` with artifact path, seed, model info

---

### `comfyui_video` -- Video Generation

| Field | Value |
|-------|-------|
| capability | `video_generation` |
| provider | `comfyui` |
| runtime | `LOCAL_GPU` |
| tier | `GENERATE` |
| stability | `EXPERIMENTAL` |
| capabilities | `text_to_video`, `image_to_video` |
| dependencies | (runtime: ComfyUI server reachable) |
| fallback_tools | `wan_video`, `hunyuan_video`, `ltx_video_local` |
| cost | `$0.00` (local compute) |

**Bundled workflows:**

1. **`wan22-i2v-4step.json`** -- Image-to-video (WAN 2.2 14B, fp8, 4-step LightX2V LoRA)
2. **`wan22-t2v-4step.json`** -- Text-to-video (WAN 2.2 14B, fp8, 4-step LightX2V LoRA)

**I2V workflow -- templated nodes:**

| Node | Class | Templated field |
|------|-------|-----------------|
| 93 | CLIPTextEncode | `text` (positive prompt) |
| 97 | LoadImage | `image` (server filename from upload) |
| 98 | WanImageToVideo | `width`, `height`, `length` |
| 86 | KSamplerAdvanced | `noise_seed` |
| 108 | SaveVideo | `filename_prefix` |

**Input schema:**

```yaml
prompt:               string    # required
operation:            string    # "text_to_video" | "image_to_video" (default: t2v)
reference_image_path: string    # local path (for i2v)
reference_image_url:  string    # URL (for i2v, downloaded first)
width:                integer   # default 640
height:               integer   # default 640
num_frames:           integer   # default 81 (5s at 16fps)
seed:                 integer   # optional
output_path:          string    # where to save the video
workflow_json:        string    # optional override
```

**execute() flow (i2v):**
1. Upload reference image via `client.upload_image()`
2. Deep-copy i2v workflow template
3. Inject prompt, uploaded image name, seed, dimensions
4. `client.generate(workflow, output_node="108", dest=output_path, timeout=900)`
5. Return `ToolResult`

**execute() flow (t2v):**
1. Deep-copy t2v workflow template
2. Inject prompt, seed, dimensions
3. `client.generate(workflow, output_node="108", dest=output_path, timeout=900)`
4. Return `ToolResult`

---

### `comfyui_music` -- Music Generation (not shipped)

We explored adding a `comfyui_music` tool using the ACE-Step 3.5B model.
The model runs well in ComfyUI, but the ComfyUI node interface for
ACE-Step is not standardized -- there are multiple custom node packs with
different class names (`AceStepModelLoader` vs native `TextEncodeAceStepAudio`,
etc.).  Shipping a workflow that only works with one specific custom node
pack would break for most users.

**Future path:** Once a stable, widely-adopted ACE-Step node interface
emerges, or if ComfyUI adds native audio generation support, a
`comfyui_music` tool can be added following the same pattern as the image
and video tools.  Users who have ACE-Step working can already use the
`workflow_json` override on any tool to run custom workflows.

---

## Workflow Override Mechanism

Every tool accepts an optional `workflow_json` input. When provided, it
replaces the bundled template entirely. This enables:

- Using newer model checkpoints without code changes
- Custom sampling strategies (different schedulers, step counts, LoRAs)
- Community workflows dropped in as-is
- A/B testing different generation approaches

The agent can also read workflow files from `tools/_comfyui/workflows/` and
modify them programmatically before passing to `execute()`.

---

## Configuration

**Environment variables:**

```bash
# .env
COMFYUI_SERVER_URL=http://localhost:8188    # ComfyUI API endpoint
COMFYUI_POLL_INTERVAL=5                     # seconds between status checks
COMFYUI_POLL_TIMEOUT=600                    # max wait for image gen
COMFYUI_VIDEO_TIMEOUT=900                   # max wait for video gen
```

**For Docker Compose setups** (ComfyUI in a container):

```bash
COMFYUI_SERVER_URL=http://host.docker.internal:8188
# or
COMFYUI_SERVER_URL=http://comfyui:8188      # if on same docker network
```

---

## Provider Selection Behavior

When the adapter is available, selectors will rank it alongside other providers
using OpenMontage's 7-dimension scoring:

| Dimension | ComfyUI score | Rationale |
|-----------|---------------|-----------|
| Task fit | High | Supports t2i, i2v, t2v |
| Quality | High | Latest models (FLUX 2, WAN 2.2 14B) |
| Control | Highest | Full workflow customization |
| Reliability | High | Proven in production |
| Cost | $0 | Local compute |
| Latency | Medium | GPU-bound, no network round-trip |
| Continuity | High | Deterministic with seeds |

When ComfyUI is unavailable (server down), the selector falls through to
`fallback_tools` automatically -- API providers like FLUX via fal.ai or
HeyGen take over transparently.

---

## What This Unlocks

### Immediate (with existing models)

- **FLUX 2 Dev NVFP4** image generation -- Blackwell-optimized, ~60s per image
- **WAN 2.2 14B** i2v with 4-step acceleration -- ~3.5 min per 5s clip
- **WAN 2.2 14B** t2v (models downloaded, workflow included)

### Future (add models to ComfyUI, no code changes to OpenMontage)

- Newer checkpoints (WAN 3.x, FLUX 3, etc.) -- just update workflow JSON
- ControlNet, IP-Adapter, AnimateDiff -- supported via ComfyUI custom nodes
- Upscaling, inpainting, outpainting -- ComfyUI nodes exist
- Any model the ComfyUI ecosystem supports

### Hardware portability

The same adapter works on:
- NVIDIA DGX Spark (GB10, aarch64, CUDA 13.0)
- Consumer GPUs (RTX 3090/4090, x86)
- Cloud instances (A100, H100)
- Multi-GPU setups (ComfyUI handles device placement)

No PyTorch version pinning, no architecture-specific wheels, no CUDA
compatibility matrices. ComfyUI is the abstraction layer.

---

## Implementation Scope

| Component | Files | Estimated size |
|-----------|-------|----------------|
| Shared client | `tools/_comfyui/client.py` | ~180 lines |
| Image tool | `tools/graphics/comfyui_image.py` | ~140 lines |
| Video tool | `tools/video/comfyui_video.py` | ~190 lines |
| Workflow templates | `tools/_comfyui/workflows/*.json` | 3 files |
| Tests | `tests/contracts/test_comfyui_tools.py` | ~200 lines |
| Docs | `docs/comfyui-adapter-plan.md` | This file |

**Total:** ~500 lines of Python + 3 workflow JSONs.

No changes to: `base_tool.py`, `tool_registry.py`, any selector, any
existing tool, any pipeline definition, or any schema.

---

## Open Questions

1. **Workflow versioning:** Should workflow JSONs live in the repo or be
   user-provided via a config directory? Bundling gives reproducibility;
   external gives flexibility.

2. **Async generation:** ComfyUI supports websocket connections for real-time
   progress. Worth implementing for long video generations, or is polling
   sufficient?

3. **Multi-server:** Should the adapter support multiple ComfyUI instances
   (e.g., one for images, one for video) via per-capability URLs?

4. **Music generation:** ACE-Step works in ComfyUI but the node interface
   isn't standardized across custom node packs. Need to either wait for
   convergence or find a portable workflow pattern. See the `comfyui_music`
   section above for details.
