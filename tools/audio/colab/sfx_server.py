"""SFX / Foley inference server — runs INSIDE a Google Colab T4 notebook.

This file is not an OpenMontage tool; it is the remote half of
tools/audio/colab_sfx.py. Usage:

1. Open https://colab.research.google.com, Runtime -> Change runtime type
   -> T4 GPU.
2. First cell (text->SFX via AudioGen only):
       !pip -q install audiocraft flask pyngrok scipy
   For video->foley too, also install MMAudio per its README
   (https://github.com/hkchengrex/MMAudio) and set ENABLE_MMAUDIO=1.
3. Second cell: paste this entire file and run it. It prints:
       COLAB_SFX_URL=https://<random>.ngrok-free.app
       COLAB_SFX_TOKEN=<generated token>
4. Put both lines in OpenMontage's .env on the local machine.

An ngrok authtoken (free account, https://dashboard.ngrok.com) must be set
via the NGROK_AUTHTOKEN env var in the notebook.

Endpoints:
    GET  /health    -> {"status": "ok", "audiogen": bool, "mmaudio": bool, ...}
    POST /generate  {"prompt": str, "duration_seconds": <=30, "seed": int?}
                    -> WAV bytes (audio/wav)  [AudioGen text->SFX]
    POST /foley     multipart: video=<file>, prompt=str?, seed=int?
                    -> WAV bytes (audio/wav)  [MMAudio video->foley]

Both responses set headers X-Model / X-Device.

Security: single-token header auth (X-Auth-Token). The tunnel URL is
public — do not disable the token check.

LICENSE NOTE: AudioGen weights are CC-BY-NC 4.0; MMAudio weights carry
non-commercial training-data constraints. Outputs are gated as REVIEW by
OpenMontage's license_validator for monetized use.
"""

import io
import os
import secrets
import tempfile

AUDIOGEN_MODEL = os.environ.get("AUDIOGEN_MODEL", "facebook/audiogen-medium")
ENABLE_MMAUDIO = os.environ.get("ENABLE_MMAUDIO", "0") == "1"
MAX_SECONDS = 30.0


def main() -> None:
    # Heavy imports stay inside main() so importing this module is harmless.
    import numpy as np
    import scipy.io.wavfile
    import torch
    from flask import Flask, jsonify, request, Response
    from pyngrok import ngrok

    token = os.environ.get("SFX_TOKEN") or secrets.token_urlsafe(24)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    # ---- AudioGen (text -> SFX) ----
    print(f"Loading AudioGen {AUDIOGEN_MODEL} on {device}...")
    from audiocraft.models import AudioGen
    audiogen = AudioGen.get_pretrained(AUDIOGEN_MODEL, device=device)
    audiogen_sr = audiogen.sample_rate

    # ---- MMAudio (video -> foley), optional ----
    mmaudio = None
    if ENABLE_MMAUDIO:
        try:
            print("Loading MMAudio (video->foley)...")
            # MMAudio's own API; see https://github.com/hkchengrex/MMAudio
            from mmaudio.eval_utils import (  # type: ignore
                ModelConfig, generate, load_video, make_video,
            )
            mmaudio = {"generate": generate, "load_video": load_video}
        except Exception as e:  # pragma: no cover - notebook-side
            print(f"MMAudio unavailable ({e}); /foley disabled.")
            mmaudio = None

    def _authed() -> bool:
        return request.headers.get("X-Auth-Token") == token

    def _wav_response(wav: "np.ndarray", sr: int, model_name: str) -> "Response":
        buf = io.BytesIO()
        # Normalise float32 [-1,1] to int16 PCM.
        if wav.dtype != np.int16:
            wav = np.clip(wav, -1.0, 1.0)
            wav = (wav * 32767.0).astype(np.int16)
        scipy.io.wavfile.write(buf, sr, wav)
        buf.seek(0)
        return Response(
            buf.read(),
            mimetype="audio/wav",
            headers={"X-Model": model_name, "X-Device": device},
        )

    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "audiogen": True,
            "mmaudio": mmaudio is not None,
            "device": device,
        })

    @app.post("/generate")
    def generate_sfx():
        if not _authed():
            return jsonify({"error": "unauthorized"}), 401
        body = request.get_json(force=True)
        prompt = body["prompt"]
        seconds = min(float(body.get("duration_seconds", 3.0)), MAX_SECONDS)
        seed = body.get("seed")
        if seed is not None:
            torch.manual_seed(int(seed))
        audiogen.set_generation_params(duration=seconds)
        wav = audiogen.generate([prompt])  # (1, channels, samples)
        arr = wav[0].detach().cpu().numpy().T  # -> (samples, channels)
        return _wav_response(arr, audiogen_sr, AUDIOGEN_MODEL)

    @app.post("/foley")
    def foley():
        if not _authed():
            return jsonify({"error": "unauthorized"}), 401
        if mmaudio is None:
            return jsonify({"error": "MMAudio not enabled on this server"}), 503
        if "video" not in request.files:
            return jsonify({"error": "missing 'video' file"}), 400
        prompt = request.form.get("prompt", "")
        seed = request.form.get("seed")
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            request.files["video"].save(tmp.name)
            video_path = tmp.name
        try:
            # MMAudio call shape varies by release; adapt to the installed API.
            audio_np, sr = mmaudio["generate"](  # type: ignore
                video_path, prompt=prompt,
                seed=int(seed) if seed is not None else None,
            )
        finally:
            os.unlink(video_path)
        return _wav_response(np.asarray(audio_np), int(sr), "MMAudio")

    print("=" * 60)
    public_url = ngrok.connect(5000).public_url
    print(f"COLAB_SFX_URL={public_url}")
    print(f"COLAB_SFX_TOKEN={token}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
