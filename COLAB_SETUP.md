Colab Free PoC — OpenMontage

Goal

Run a fully free proof-of-concept on Google Colab (no paid APIs or paid endpoints). This uses free/open assets and local Python libraries Colab can install.

What this provides

- A zero-API, zero-paid path that builds a short video from free images (Wikimedia Commons) + free TTS (gTTS) + assembles with moviepy/ffmpeg.
- Optional notes for using local GPU-based model generation if the user wants to run local diffusion models (requires additional model downloads; optional and not required).

Quick start (Colab)

1. Open Google Colab and click File → Upload notebook, then upload `notebooks/colab_free_poc.ipynb` from this repo, or open it in Colab via GitHub (Open in Colab).
2. Runtime → Change runtime type → Hardware accelerator: GPU (recommended but not required for the zero-API path).
3. Run cells in order. The notebook installs needed packages, downloads free images, generates narration with gTTS, and assembles a final MP4 in `/content/output/final.mp4`.
4. Download the produced `final.mp4` from the Colab Files panel or via the notebook link shown after rendering.

Why this is free

- Uses Wikimedia Commons media (public domain / free reuse) for visuals — no API keys required.
- Uses gTTS (Google Translate TTS) for narration — free library with no paid API key required.
- Uses moviepy + ffmpeg (installed via apt) for video assembly — all free and runs on Colab.

Optional: local model generation

- The notebook includes commented cells and notes describing how to swap the image download step for diffusion image generation via `diffusers` if the user provides a HuggingFace token and wants to run local models on GPU. This is optional and not required for the PoC.

Files added

- notebooks/colab_free_poc.ipynb — runnable Colab notebook with step-by-step cells.
- COLAB_SETUP.md — short step-by-step instructions and rationale.

If you want, commit these files and I can also add a minimal example Python script (colab/colab_run.py) to run the same steps non-interactively.

GPU / Local video generation (optional)

To follow the README note about "Have a GPU? Unlock free local video generation":

1. Install GPU/deps (Colab):

   - Use the project's Makefile equivalent from Colab (no sudo):
     - pip install -r requirements-gpu.txt
     - pip install diffusers transformers accelerate

   - In Colab a safer, minimal sequence (recommended):
     - Check preinstalled torch + CUDA: run `import torch; print(torch.__version__, torch.cuda.is_available())`.
     - If CUDA-enabled torch is missing, install a matching wheel (Colab often has a working torch; installing a mismatched wheel can break CUDA).
     - Then install the diffusers stack: `pip install -q diffusers transformers accelerate safetensors huggingface_hub`

2. Enable local video generation in the environment used by the notebook: set

   - `VIDEO_GEN_LOCAL_ENABLED=true`
   - `VIDEO_GEN_LOCAL_MODEL=wan2.1-1.3b`  # or wan2.1-14b, hunyuan-1.5, ltx2-local, cogvideo-5b

   Example in Colab cell:

   ```python
   import os
   os.environ['VIDEO_GEN_LOCAL_ENABLED'] = 'true'
   os.environ['VIDEO_GEN_LOCAL_MODEL'] = 'wan2.1-1.3b'
   ```

3. Status check (safe, no model download): run the repo's availability probe to confirm the local stack is reachable. In Colab, after installing dependencies and cloning the repo, run:

   ```python
   from tools.video.wan_video import WanVideo
   print('WanVideo status:', WanVideo().get_status())
   ```

   - If status reports UNAVAILABLE, the notebook will show the install instructions and missing packages.
   - If status is AVAILABLE, generating will still download model weights the first time and requires a HuggingFace token for some models. Model downloads can be large (GBs) and may exceed Colab storage or runtime limits.

4. Running a small local test (cautious):

   - If you have a HuggingFace token and sufficient disk/VRAM, set `HF_TOKEN` in Colab and run a one-shot generate with a short prompt using the `wan_video` tool. This step is optional and may take minutes and substantial memory.

Notes and recommendations

- The repository's Makefile target `make install-gpu` maps to `pip install -r requirements-gpu.txt` + `pip install diffusers transformers accelerate` — the notebook's optional GPU cells follow that.
- On Colab prefer not to pip-reinstall torch unless you know the correct CUDA wheel; trust Colab's preinstalled torch when possible.
- WAN / Hunyuan / LTX models are large; for a safe Colab demo prefer the image-based diffusers -> moviepy path already in the notebook. If you want, I can add optional notebook cells that perform the `make install-gpu` steps and a commented example of running `wan_video.execute()` so you can opt-in and run it manually.

Would you like me to add those optional GPU cells to the Colab notebook now? (They will be commented and opt-in to avoid accidental large downloads.)
