"""Modal deploy: self-hosted LTX-Video endpoint for OpenMontage (cheap draft/bulk video).

This is the GPU endpoint that `tools/video/ltx_video_modal.py` calls. It returns raw
MP4 bytes, matching the contract in `tools/video/_shared.py::generate_ltx_modal_video`,
which POSTs JSON:

    {prompt, width, height, num_frames, fps, steps, negative_prompt,
     seed?, input_image? (base64), input_image_url?}

and accepts either video bytes (content-type video/*) or JSON {"video_url": ...}.
This endpoint returns bytes, so no external storage is needed.

── Deploy (run locally; needs `pip install modal` + `python3 -m modal setup`) ──
    modal deploy deploy/modal_ltx_endpoint.py
Copy the printed web URL (…--generate.modal.run) and point the app at it:
    export MODAL_LTX2_ENDPOINT_URL="https://<your-workspace>--openmontage-ltx-ltx-generate.modal.run"

Cost note: LTX is light. On an L40S (~$1.95/hr serverless) a 5s clip is ~$0.03-0.05
warm; the container scales to zero when idle. Bump GPU to A100 only for big batches.
"""

import base64
import io
import os
import tempfile

import modal

APP_NAME = "openmontage-ltx"
MODEL_ID = "Lightricks/LTX-Video"  # diffusers-integrated LTX-Video (fast, ~24GB)
# LTX fits comfortably on L40S (48GB) and stretches Starter credits further than A100.
# A10G (24GB) also works for short clips with VAE tiling; A100 for large batches.
GPU = "L40S"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install(
        "torch>=2.4",
        "diffusers>=0.32.0",
        "transformers>=4.44",
        "accelerate",
        "sentencepiece",
        "imageio",
        "imageio-ffmpeg",
        "pillow",
        "hf_transfer",
        "requests",
        "fastapi[standard]",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1", "HF_HOME": "/cache/hf"})
)

app = modal.App(APP_NAME)
# Persist model weights across cold starts so they download only once.
hf_cache = modal.Volume.from_name("openmontage-hf-cache", create_if_missing=True)


@app.cls(
    image=image,
    gpu=GPU,
    volumes={"/cache": hf_cache},
    timeout=900,
    # scaledown_window is the current Modal name (older versions: container_idle_timeout).
    scaledown_window=120,
)
class LTX:
    @modal.enter()
    def load(self):
        import torch
        from diffusers import LTXPipeline

        self.torch = torch
        self.pipe = LTXPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
        self.pipe.to("cuda")
        self.pipe.vae.enable_tiling()  # memory safety on smaller GPUs
        self._i2v = None

    def _image_pipe(self):
        # Lazily build the image-to-video pipeline sharing the loaded weights.
        if self._i2v is None:
            from diffusers import LTXImageToVideoPipeline

            self._i2v = LTXImageToVideoPipeline.from_pipe(self.pipe)
        return self._i2v

    @modal.fastapi_endpoint(method="POST")
    def generate(self, payload: dict):
        from fastapi import Response
        from diffusers.utils import export_to_video

        prompt = payload["prompt"]
        width = int(payload.get("width", 1024))
        height = int(payload.get("height", 576))
        num_frames = int(payload.get("num_frames", 121))
        steps = int(payload.get("steps", 30))
        fps = int(payload.get("fps", 24))
        negative = payload.get("negative_prompt", "")

        generator = None
        if payload.get("seed") is not None:
            generator = self.torch.Generator("cuda").manual_seed(int(payload["seed"]))

        kwargs = dict(
            prompt=prompt,
            negative_prompt=negative,
            width=width,
            height=height,
            num_frames=num_frames,
            num_inference_steps=steps,
            generator=generator,
        )

        pipe = self.pipe
        ref = self._load_ref_image(payload)
        if ref is not None:
            pipe = self._image_pipe()
            kwargs["image"] = ref.resize((width, height))

        frames = pipe(**kwargs).frames[0]

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()
        try:
            export_to_video(frames, tmp.name, fps=fps)
            data = open(tmp.name, "rb").read()
        finally:
            os.remove(tmp.name)

        return Response(content=data, media_type="video/mp4")

    @staticmethod
    def _load_ref_image(payload: dict):
        """Decode the image_to_video reference (base64 or URL), or None for text_to_video."""
        from PIL import Image

        b64 = payload.get("input_image")
        url = payload.get("input_image_url")
        if b64:
            return Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
        if url:
            import requests

            resp = requests.get(url, timeout=60)
            resp.raise_for_status()
            return Image.open(io.BytesIO(resp.content)).convert("RGB")
        return None
