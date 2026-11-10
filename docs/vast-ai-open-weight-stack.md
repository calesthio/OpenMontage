# Open-weight stack on one vast.ai GPU (RTX PRO 6000 96 GB)

How to rent one vast.ai machine, put the open-weight models OpenMontage can drive
on it, and connect OpenMontage to it from your laptop.

**Last checked: 2026-11-06.** Live prices, file sizes and licences below were read
that day. Re-check anything marked *snapshot* before you rent.

## What is verified and what is not

| Claim | Status |
| --- | --- |
| vast.ai offers, prices, regions, CUDA versions | Read live on 2026-11-06 (snapshot, section 2) |
| Hugging Face repos, file names and sizes | Read live on 2026-11-06 |
| MiniMax H3 and Qwen-Image-2.1 licence terms | Read from the licence files on 2026-11-06 |
| Instance setup steps (ComfyUI upgrade, cu130 PyTorch, SageAttention) | Taken from a setup script used on RTX 5090 instances in 2026-09/10. **Not re-run on an RTX PRO 6000.** |
| Qwen-Image-2.1 bundled graph | Same nodes and inputs as a graph run on a rented RTX 4090 |
| **MiniMax H3 bundled T2V/I2V graphs** | **Not yet run on a GPU.** Section 6 is the first-run checklist. |
| Drama 3 and Nemotron serving commands | Copied from vendor docs and research notes. Not run by us. OpenMontage has no tool for them. |
| H3 time on an RTX PRO 6000 | **Not measured.** See section 7. |

## 1. What runs on the machine

| Capability | Model | Served by | OpenMontage today | Download |
| --- | --- | --- | --- | --- |
| Video + audio | MiniMax H3 (FL2VA, INT8) | ComfyUI | `comfyui_video`, `model_family: "minimax_h3_local"`, bundled T2V/I2V | 42.5 GB |
| Image | Qwen-Image-2.1 (INT8) | ComfyUI | `comfyui_image`, `model_family: "qwen_image_2.1"`, text-to-image | 17.3 GB |
| Music with vocals | YuE2-3B, or ACE-Step 1.5 XL | ComfyUI | Custom workflow only (the bundled music workflow is ACE-Step **v1**) | 5.4 GB / ~19 GB |
| Instrumental music | Stable Audio 3 Medium | ComfyUI | Custom workflow only | 10.4 GB |
| Speech (TTS) | Fish Audio Drama 3 (int4) | SGLang-Omni (separate server) | **No tool.** `fish_audio_tts` calls the hosted API only. | 24.0 GB |
| Speech to text | Nemotron 3.5 Transcribe (FP8) | vLLM (separate server) | **No tool.** | 34.7 GB |

Everything under "ComfyUI" shares one server and one port. Drama 3 and Nemotron are
separate processes. With no OpenMontage tool, they are useful only if you call them
yourself or write a tool for them.

The 96 GB card does not hold every model at once. ComfyUI offloads between runs, but
a vLLM or SGLang server keeps its weights resident. Run one workload at a time and
stop the other servers first.

### Licences

Using the open weights is not the same as being free to ship the output. Read the
licence before commercial use. This is not legal advice.

| Model | Terms | Source |
| --- | --- | --- |
| MiniMax H3 | Not authorised in the EU, UK, Republic of Korea or US, outputs included. Above US$20M in commercial revenue, written authorisation from MiniMax. Commercial products must display "MiniMax H3". | [LICENSE](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE), read 2026-11-06 |
| Qwen-Image-2.1 | Qwen Research License: research and evaluation only. Commercial use needs a separate licence. | [LICENSE](https://huggingface.co/Qwen/Qwen-Image-2.1/blob/main/LICENSE), read 2026-11-06 |
| YuE2 | CC BY-NC 4.0 on the Comfy-Org repackage | [README](https://huggingface.co/Comfy-Org/YuE2), read 2026-11-06 |
| Drama 3, Stable Audio 3, ACE-Step 1.5, Nemotron | Reported in our 2026-11-05 research notes (Drama 3: commercial below US$500k a year with a "Built with Fish Audio" credit). **Re-read each licence file before relying on it.** | not re-checked |

`get_info()["license_notes"]` on `comfyui_video` and `comfyui_image` carries the H3
and Qwen terms, so the agent can tell the user before generating.

## 2. Rent the machine

### What to ask for

- 1 GPU, **RTX PRO 6000 (97.9 GB VRAM)**.
- **Host RAM at least 128 GB.** H3 is heavy on host RAM as well as VRAM.
- **Disk 300 GB**, chosen when you rent. Models alone are about 154 GB if you install
  everything; caches and the Python environment come on top. Our own full install of
  a smaller set (H3, ref2va, TTS, voice tools, Qwen) filled about 124 GB of a 150 GB
  disk, leaving less free space than our own 30 GB preflight requires. If you install
  only the two OpenMontage-driven models (60 GB of weights), 200 GB is enough.
- **CUDA 13 on the host driver.** The INT8 ConvRot and NVFP4 kernels behind these
  files need a PyTorch cu130 build, and that needs a CUDA 13 driver.
- Template: **ComfyUI (`vastai/comfy`)**.

### Search

```bash
vastai search offers \
  'gpu_name in [RTX_PRO_6000_WS,RTX_PRO_6000_S,RTX_PRO_6000] num_gpus=1 verified=true rentable=true gpu_ram>=90 cpu_ram>=120 disk_space>=300 reliability>0.97 cuda_max_good>=13.0' \
  -o 'dph' --raw
```

### Snapshot, 2026-11-06 07:44 UTC

21 offers matched (without the `cuda_max_good` filter; every one reported CUDA 13.0 to 13.4).

| | |
| --- | --- |
| Price | US$1.335 to 2.469 per hour, median 1.868 |
| Host RAM | 126 to 289 GB |
| Disk offered | 338 GB to 5.9 TB |
| Regions | US 8, FR 4, CA 3, CZ 2, IN 1, DE 1, GB 1, HU 1 |
| Download speed | median 1,423 Mb/s, lowest of the five cheapest 412 Mb/s |
| **Download price** | median US$2.60 per TB, but the cheapest-per-hour offer (India) charged **US$39.06 per TB** |

Two things in that table change which offer is cheapest:

- **Download price.** Installing 154 GB at US$39 per TB costs about US$6.00 in
  traffic, against about US$0.40 at US$2.60 per TB. Read `inet_down_cost` (`dlcost` in
  the CLI) and add it to the hourly price. The cheapest hourly offer is not
  automatically the cheapest session.
- **Region and the H3 licence.** H3 is not authorised in the US, EU, UK or South
  Korea. In this snapshot, the only offers outside those are in Canada and India. The
  licence text does not say whether a US-hosted GPU counts as use in the US, so if
  the H3 licence matters to you, filter by `geolocation` and ask MiniMax.

### Rent

```bash
# 2188dfd3... is the vast.ai "ComfyUI" (vastai/comfy) template hash our scripts used on 2026-09-28.
# If it no longer resolves, pick the ComfyUI template in the web console and copy its hash.
vastai create instance <offer id> --template_hash 2188dfd3e0a0b83691bb468ddae0a4e5 --disk 300 --raw
```

If you rent from the web console instead, pick the ComfyUI template and set the disk
to 300 GB. Your instance gets a new IP and SSH port every time; copy the SSH command
from the Instances page.

## 3. Prepare the instance

These steps come from a script used on RTX 5090 instances. Paths assume the
`vastai/comfy` template (`/workspace/ComfyUI`, Python at `/venv/main`, ComfyUI managed
by `supervisorctl`). Non-interactive SSH does not put `/venv/main/bin` on `PATH`.

```bash
ssh -p <PORT> root@<IP>
export PATH=/venv/main/bin:$PATH PY=/venv/main/bin/python COMFY=/workspace/ComfyUI MODELS=/workspace/ComfyUI/models
nvidia-smi --query-gpu=name,memory.total --format=csv   # expect RTX PRO 6000, ~97 GB
nvidia-smi | grep "CUDA Version"                        # expect 13.x
df -h /workspace                                        # expect >= 300 GB
```

If `nvidia-smi` reports no GPU, destroy the instance and rent another. Do not start a
150 GB download on it.

### 3.1 Hugging Face

```bash
hf auth login            # a read token is enough
```

Open https://huggingface.co/Comfy-Org/MiniMax-H3 once in a browser and accept the
licence with the same account. Without it, downloads fail with 401/403.

### 3.2 ComfyUI must be recent

The template can ship an old ComfyUI. One host in our sessions ran v0.18.2 from
March, which has neither the H3 nodes nor `QwenImage21Cache`. The minimums are 0.30.0
for H3 and 0.36.0 for YuE2; use the newest release.

```bash
grep -rqs MiniMaxH3ImageToVideo "$COMFY/comfy_extras" && echo "H3 nodes: ok"
grep -qs QwenImage21Cache "$COMFY/comfy_extras/nodes_qwen.py" && echo "Qwen 2.1 nodes: ok"
# If either is missing:
git -C "$COMFY" fetch -q --tags origin
git -C "$COMFY" checkout -q "$(git -C "$COMFY" tag --sort=-v:refname | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | head -1)"
$PY -m pip install -q -r "$COMFY/requirements.txt"
```

### 3.3 PyTorch built for CUDA 13

ComfyUI turns off its native INT8/FP8/NVFP4 kernels when PyTorch is a cu12x build,
and the template ships cu128. On an RTX 5090, switching to cu130 cut a talking-head
H3 shot from 144 s to 92 s. Run this only if `torch.version.cuda` is below 13 and
`nvidia-smi` shows CUDA 13:

```bash
$PY -c 'import torch; print(torch.__version__, torch.version.cuda)'
pkgs=$($PY - <<'EOF'
from importlib.metadata import version, PackageNotFoundError
out = []
for name in ("torch", "torchvision", "torchaudio", "torchcodec"):
    try:
        out.append(f"{name}=={version(name).split('+')[0]}+cu130")
    except PackageNotFoundError:
        pass
print(" ".join(out))
EOF
)
$PY -m pip install --index-url https://download.pytorch.org/whl/cu130 $pkgs
# If xformers is installed, reinstall the same version from that index with --no-deps.
$PY -c 'import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())'
```

### 3.4 Optional speed-ups

- SageAttention: add `--use-sage-attention` to `COMFYUI_ARGS` in `/etc/environment`
  (template-specific), then restart. About 20 % faster in our RTX 5090 runs.
- CPU threads: the container's CPU quota can be far below the visible core count, and
  PyTorch defaulted to too many threads (CPU-side steps ran 1.8x slower at 16 threads
  than at 8 on one host). Set `OMP_NUM_THREADS` and `MKL_NUM_THREADS` to the quota
  from `/sys/fs/cgroup/cpu.max`.

```bash
supervisorctl restart comfyui
curl -sf http://127.0.0.1:18188/system_stats | head -c 300
```

## 4. Download the models

File names and destinations come from `tools/_comfyui/metadata.py`. OpenMontage never
downloads weights for you; it only checks that the files are present.

`check_models` finds the files through ComfyUI's loader nodes, so they must sit in the
folders below.

```bash
MODELS=/workspace/ComfyUI/models
fetch() {   # fetch <repo> <path inside repo> <folder under models/>
  local repo=$1 path=$2 dest=$3 name; name=$(basename "$path")
  [ -f "$MODELS/$dest/$name" ] && { echo "have $dest/$name"; return; }
  hf download "$repo" "$path" --local-dir /workspace/dl >/dev/null
  mkdir -p "$MODELS/$dest" && mv -f "/workspace/dl/$path" "$MODELS/$dest/" && echo "ok   $dest/$name"
}
```

### 4.1 Required by the bundled workflows (59.8 GB)

MiniMax H3 (`Comfy-Org/MiniMax-H3`):

```bash
fetch Comfy-Org/MiniMax-H3 diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors diffusion_models   # 21.0 GB
fetch Comfy-Org/MiniMax-H3 text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors text_encoders             # 15.7 GB
fetch Comfy-Org/MiniMax-H3 vae/minimax_h3_video_vae_fp16.safetensors vae                                         #  5.2 GB
fetch Comfy-Org/MiniMax-H3 vae/minimax_h3_audio_vae_fp32.safetensors vae                                         #  0.6 GB
```

Qwen-Image-2.1 (`Comfy-Org/Qwen-Image-2.1`):

```bash
fetch Comfy-Org/Qwen-Image-2.1 diffusion_models/qwen_image_2.1_int8_convrot.safetensors diffusion_models   # 7.3 GB
fetch Comfy-Org/Qwen-Image-2.1 text_encoders/qwen3vl_8b_int8_convrot.safetensors text_encoders             # 9.4 GB
fetch Comfy-Org/Qwen-Image-2.1 vae/qwen_image_2.1_vae_bf16.safetensors vae                                 # 0.7 GB
```

Two choices worth knowing about:

- The INT8 diffusion model needs the cu130 kernels from section 3.3. On a cu12x
  build, use a different H3 file (for example `minimax_h3_fl2va_pruned_fp8_scaled`)
  **and** a custom workflow, because the bundled graph names the INT8 file.
- The bundled H3 graph uses the `fp16` video VAE. The official template uses
  `minimax_h3_video_vae_int8_convrot` (2.8 GB). Both exist; if you switch, edit
  `tools/_comfyui/workflows/minimax-h3-*.json` and the stack in `metadata.py`
  together. A contract test fails if they disagree.

### 4.2 Optional: music for custom ComfyUI workflows

These have no bundled OpenMontage workflow. Load the official templates in the ComfyUI
Template Library and let it list what is missing. File names below are from the repos
as of 2026-11-06.

```bash
# YuE2-3B (CC BY-NC 4.0). Templates: "YuE2: Text to Music", "YuE2: Music Cover"
fetch Comfy-Org/YuE2 checkpoints/yue2_3b_int8_convrot.safetensors checkpoints          # 4.0 GB
fetch Comfy-Org/YuE2 audio_encoders/sheetsage2_bf16.safetensors audio_encoders         # 1.4 GB (cover workflow)

# Stable Audio 3 Medium (instrumental)
fetch Comfy-Org/stable-audio-3 checkpoints/stable_audio_3_medium.safetensors checkpoints           # 9.2 GB
fetch Comfy-Org/stable-audio-3 text_encoders/t5gemma_b_b_ul2.safetensors text_encoders             # 1.2 GB

# ACE-Step 1.5 XL turbo. The XL text encoder and VAE are named by the template you load;
# these are the candidates in the repo.
fetch Comfy-Org/ACE-Step-1.5 split_files/diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors diffusion_models   # 10.0 GB
fetch Comfy-Org/ACE-Step-1.5 split_files/text_encoders/qwen_4b_ace15.safetensors text_encoders                      #  8.4 GB
fetch Comfy-Org/ACE-Step-1.5 split_files/vae/ace_1.5_vae.safetensors vae                                            #  0.3 GB
```

For YuE2, keep the generation budget at least 20 to 30 s longer than the clip you
want, or the song is truncated. Prompts are baked into a custom workflow; the
`comfyui_music` tool does not inject them.

### 4.3 Optional: separate servers (no OpenMontage tool)

```bash
hf download fishaudio/drama-3-int4 --local-dir /workspace/models/drama-3-int4                                  # 24.0 GB
hf download nvidia/NVIDIA-Nemotron-3.5-Transcribe-30B-A4B-FP8 --local-dir /workspace/models/nemotron-fp8      # 34.7 GB
```

- **Drama 3:** `sgl-omni serve --model-path fishaudio/drama-3-int4 --port 8000`, then
  `POST /v1/audio/speech`. Reported settings: temperature 1.0, top_p 0.9, top_k 30.
  Cap `max_new_tokens`, because an endless-silence bug is reported. Expect the first
  request to take about 10 s. The SGLang docs disagree about whether the text field is
  `input` or `text`; check the cookbook for your version. No word timestamps.
- **Nemotron 3.5 Transcribe:** serve with vLLM following
  [NVIDIA's guide](https://docs.nvidia.com/nemotron/nightly/nemotron/transcribe35/README.html).
  Turn the loop guardrail on (without it NVIDIA reports 7 of 451 files looping and a
  long-form WER of 12.87). Do not enable DFlash2 speculative decoding if you need word
  timestamps; it is incompatible with the CTC timestamps.

## 5. Connect OpenMontage from your laptop

ComfyUI has no authentication, and OpenMontage's client sends no credentials. Never
expose its port. On the `vastai/comfy` template, ComfyUI listens on
`127.0.0.1:18188` and a Caddy proxy on `8188` demands a password, so scripts get a 401.
Tunnel to the loopback port:

```bash
ssh -i <key> -p <PORT> -N -L 8188:127.0.0.1:18188 root@<IP>
```

Leave that running, then in the project's shell:

```bash
export COMFYUI_SERVER_URL=http://127.0.0.1:8188
curl -sf http://127.0.0.1:8188/system_stats | head -c 200
python -c "
from tools.tool_registry import registry
import json
registry.discover()
print(json.dumps(registry.provider_menu_summary(), indent=2))
"
```

Separate ComfyUI machines per capability can use `COMFYUI_VIDEO_SERVER_URL` and
`COMFYUI_IMAGE_SERVER_URL`. If the tunnel drops mid-job, the job keeps running on the
server. Reconnect and pass the `prompt_id` from the timeout error back as
`resume_prompt_id`.

Check both tools see their models. Missing files are listed with destinations and
download URLs in `data.missing_models`:

```bash
python -c "
from tools.video.comfyui_video import ComfyUIVideo
from tools.graphics.comfyui_image import ComfyUIImage
print(ComfyUIVideo().operation_statuses())
print(ComfyUIImage().get_status())
"
```

## 6. First-run checklist for the H3 graphs

The bundled H3 T2V and I2V graphs have not been run yet. Treat your first run as the
validation, and keep it small.

1. Open ComfyUI through the tunnel, load the **MiniMax H3 T2V** template from the
   Template Library, and confirm all four model files load without a missing-model
   warning. This tells you the files are right before OpenMontage is involved.
2. Run a short sample through a production pipeline, using `comfyui_video` with
   `model_family: "minimax_h3_local"`, `duration: 4`, and 1344x768. Announce it as a
   sample, as `AGENT_GUIDE.md` requires.
3. If ComfyUI rejects the graph, the tool returns the server's validation text in
   `error`. Compare the named input with the node's schema:
   `curl -s http://127.0.0.1:8188/object_info/MiniMaxH3ImageToVideo`. Report the
   exact error rather than adjusting values to make it pass.
4. Watch the first clip for lip movement against the audio, hands, and text in frame.
   Local H3 is 768p; the 2K "Regenerate" step is API-only.
5. Run an image-to-video sample. The first frame is stretched to the canvas, so use an
   image close to 16:9 or 9:16, or let the tool derive the canvas from the image.

## 7. Time and cost

| Item | Number | Source |
| --- | --- | --- |
| H3, 5 s product shot, 0.98 MP, RTX 5090, cu130 PyTorch | 120 s (133 s on cu128) | Our run, 2026-09-29 |
| H3, 5 s clip, 1344x768, 8-step Turbo LoRA, RTX 5090 | 85 s | Third-party benchmark (`yix081/vdn-minimax-h3-consumer-gpus`), cited in our 2026-09-24 notes |
| H3, 5 s clip, RTX PRO 6000, same setting | reported as the same 85 s | Same third-party benchmark, run on SGLang, not ComfyUI; not measured by us |
| H3, 5 s clip, 20 base steps | **not measured** | `estimate_runtime` extrapolates the 85 s figure linearly: about 270 s |
| Qwen-Image-2.1, 1024x1024, warm | 5.8 s at 25 steps, 9.1 s at 40 steps on one RTX 4090 host; 24 s on another RTX 4090 host (cause not found) | Our eval, 2026-10 |
| Qwen-Image-2.1 peak VRAM | 16.9 GB at 1024x1024, 20.2 GB at 2048x2048 | Same RTX 4090 tests |

A session costs the hourly price plus the download time. Install time is roughly
`154 GB x 8 / download speed`: about 15 minutes at 1,423 Mb/s, about 50 minutes at
412 Mb/s. At the median price that is US$0.50 to 1.60 before you generate anything,
plus traffic.

## 8. Stop paying

- **Destroy** deletes the disk and its contents and ends billing.
- **Stop** ends GPU billing but keeps the disk, which still bills (about US$0.07 per
  hour for 200 GB on the hosts we used), and the GPU may be rented by someone else
  before you start again. In our sessions it was only worth it for a break of a day
  or two.
- Copy your outputs first (`scp` or `rsync` from `/workspace/ComfyUI/output`). Pipeline
  outputs also land in `projects/<id>/` on your machine.
- Check your credit before a long run (`vastai show user`). An instance whose credit
  runs out stops, and can be destroyed together with its results. This happened to us
  mid-install on a host that billed downloads at US$40 per TB.

```bash
vastai show instances
vastai destroy instance <instance id>
```

Renting a new instance for each session and destroying it afterwards keeps idle cost
at zero, at the price of a full install each time. If you generate often, a stopped
instance for a day or two can be cheaper than reinstalling 154 GB.

## 9. Problems we have hit

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Node 'QwenImage21Cache' not found` or no `MiniMaxH3*` nodes | Old ComfyUI in the template image | Section 3.2 |
| H3 slower than expected, INT8/NVFP4 kernels off | PyTorch is a cu12x build | Section 3.3 |
| 401 or 403 from `hf download` on MiniMax-H3 | Licence not accepted on that account | Section 3.1 |
| `nvidia-smi` says no devices mid-session | Host GPU fell off the bus | Destroy, rent another |
| Preflight fails on free disk after a full install | 150 GB disk | Rent 300 GB, or install less |
| Tool says ComfyUI is unavailable, `curl` returns 401 | Pointed at Caddy on port 8188 | Tunnel to `127.0.0.1:18188` (section 5) |
| Install bill larger than expected | Host charges for downloads | Read `inet_down_cost` before renting |
