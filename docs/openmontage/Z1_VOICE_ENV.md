# Z1 pinned environment (isolated venv, not system Python 3.14.2)

Venv: /tmp/kilo/z1_venv (python3.12.3, created with python3.12-venv; outside the repo, never committed)
Interpreter: /tmp/kilo/z1_venv/bin/python
HF_HOME (weights cache): /tmp/kilo/hf_cache (gitignored, outside the repo)
PIP_CACHE_DIR: /tmp/kilo/pip_cache

Pinned packages (pip freeze subset, exact versions installed):
  kokoro==0.2.2
  misaki==0.7.17
  soundfile==0.14.0
  numpy==2.5.4
  torch==2.6.0+cpu   (installed via --extra-index-url https://download.pytorch.org/whl/cpu)
  en-core-web-sm==3.8.0 (spacy model pulled in by misaki/kokoro)

Weights (downloaded once on first KPipeline run, keyless HF Hub, hexgrad/Kokoro-82M):
  kokoro-v1_0.pth (~313 MB)
  voices/af_heart.pt
Cache location: /tmp/kilo/hf_cache/hub/

Verification (10 s sample, 2026-10-19):
  - Text: "OpenMontage voice environment check. Kokoro eight two M running on CPU ..." (~55 words)
  - Raw wav: /tmp/kilo/z1_sample_raw.wav, pcm_s16le 24000 Hz mono, 14.625 s, 702 044 bytes, RTF 1.38 on CPU
  - finish_audio: PASS (loudnorm measured I=-25.66 -> target I=-14.0, TP <= -1.5; output pcm_s16le 44100 Hz stereo, 14.625 s)
  - tools/qa/qc.py on finished wav:
      ffprobe_streams FAILED (audio-only sample: no video stream — expected; full video QC runs in Z2)
      full_decode PASS, blackdetect PASS, freezedetect PASS, silencedetect PASS, ebur128 PASS (I=-15.2 LUFS +/- 2.0 of -14 target; TP -4.5 <= -1.5)
      duration_vs_script/subtitle_sync/credits_complete/claim_ids/claim_ids_resolve/rights_basis/added_value NOT_RUN (no video/manifest inputs)
  - espeak-3 not installed: EspeakFallback warning only, non-fatal (misaki G2P covers in-dictionary words)

Notes:
  - kokoro 0.2.2 requires transformers, which needs torch >= 2.6 (torch 2.5.1+cpu failed import; 2.6.0+cpu works).
  - kokoro 0.2.2 requires MToken.prespace, removed in misaki 0.9.x; misaki 0.7.17 pinned.
  - Zero-cost: PyPI + Hugging Face Hub are keyless/free; no paid routes; no secrets.
