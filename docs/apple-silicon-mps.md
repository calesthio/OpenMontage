# Apple Silicon (MPS) Support

OpenMontage supports Apple Silicon Macs (M1/M2/M3/M4/M5) via PyTorch's
Metal Performance Shaders (MPS) backend. Local GPU tools — video generation,
upscaling, and face restoration — automatically detect and use MPS when
available.

## Requirements

- macOS 12.3 (Monterey) or later
- Apple Silicon Mac (M-series chip)
- Python 3.10+

## Quick Setup

```bash
# Enable local generation
export VIDEO_GEN_LOCAL_ENABLED=true

# Install dependencies — MPS support is included in the default torch wheel
uv pip install diffusers transformers accelerate torch pillow requests

# For upscaling and face restoration
uv pip install realesrgan gfpgan
```

No special CUDA build or separate MPS package is needed — `uv pip install torch`
on macOS automatically includes MPS support.

## How It Works

The `get_torch_device()` helper in `tools/video/_shared.py` detects the best
available device:

1. **CUDA** (NVIDIA GPU) — used when available; fastest for diffusion models
2. **MPS** (Apple Silicon Metal) — used on M-series Macs; good performance
3. **CPU** — fallback, always available but significantly slower

Device selection is automatic. All local GPU tools (`upscale`, `face_restore`,
`ltx_video_local`, `wan_video_local`, etc.) route through this helper.

## Known Limitations

- **VRAM**: Apple Silicon uses unified memory. Models that require >16 GB VRAM
  may not fit on 16 GB Macs. Check the tool's `resource_profile.vram_mb`.
- **bfloat16**: Not supported on MPS. The pipeline automatically uses float16
  on MPS and float32 on CPU.
- **CPU offloading**: `enable_model_cpu_offload()` is CUDA-only. On MPS, the
  pipeline falls back to direct device placement.
- **Half-precision in Real-ESRGAN**: fp16 can produce NaN artifacts on MPS, so
  upscaling automatically uses fp32 on non-CUDA devices.

## Verifying MPS Is Active

```python
from tools.video._shared import get_torch_device
print(get_torch_device())  # Should print "mps" on Apple Silicon
```

If this prints `"cpu"` on an Apple Silicon Mac, verify:
- macOS version is 12.3+
- PyTorch is installed (`uv pip install torch`)
- You're running native ARM Python (not Rosetta x86)
