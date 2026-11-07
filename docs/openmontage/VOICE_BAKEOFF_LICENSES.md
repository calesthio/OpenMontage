# Voice Bake-off License Evidence — OpenMontage MASTER RUN P1

**Status:** docs only. P1 of MASTER RUN. Thresholds marked INITIAL GUESSES.
**Source rule:** evidence recorded only from official repo/model-card files (GitHub repo LICENSE, Hugging Face model-card metadata `license`, official README). No memory-derived license claims. A candidate without verified permissive code+weights evidence is EXCLUDED from the bake-off.
**Access date:** 2026-10-17.

## Candidate preference order (chosen for P1)
1. Chatterbox Turbo (Resemble AI) — fall back to base Chatterbox if Turbo unavailable
2. Maya1 (Maya Research)
3. Kokoro-82M (hexgrad)

## License evidence table

| Candidate | Code license | Evidence URL | Weights license | Evidence URL | Commercial use | Training-data statement | Watermarking | Reference audio clip required? | VRAM need | License gate |
|---|---|---|---|---|---|---|---|---|---|---|
| Chatterbox Turbo / base Chatterbox (Resemble AI) | MIT | https://github.com/resemble-ai/chatterbox/blob/master/LICENSE | MIT | https://huggingface.co/ResembleAI/chatterbox (model-card metadata `license: mit`) | Permitted (MIT) | "Trained on 0.5M hours of cleaned data" (HF Key Details); disclaimer: "Prompts are sourced from freely available data on the internet" | YES — built-in Perth (Perceptual Threshold) watermarker; every generated file watermarked, ~100% detection accuracy | OPTIONAL — `model.generate(text)` works without; `audio_prompt_path` only needed for voice cloning/custom voice. Not required for plain TTS. | Turbo 350M lower VRAM; base 500M (0.5B Llama backbone); Nano 110M CPU | PASS |
| Maya1 (Maya Research) | Apache 2.0 | https://huggingface.co/maya-research/maya1 (model-card metadata `license: apache-2.0`) | Apache 2.0 | https://huggingface.co/maya-research/maya1 | Permitted (Apache 2.0; HF FAQ: "Build products, deploy services, monetize freely") | "Proprietary curated + Internet-scale pretraining" (HF model metadata) | Not stated in official README/model card | NOT required — voice design via natural-language text description, no reference clip | 3B params; single GPU 16GB+ VRAM recommended (RTX 4090 / A100 / H100); int8/int4 quantization available | PASS |
| Kokoro-82M (hexgrad) | Apache 2.0 | https://huggingface.co/hexgrad/Kokoro-82M (LICENSE file) | Apache 2.0 | https://huggingface.co/hexgrad/Kokoro-82M (LICENSE file) | Permitted at weights level (Apache 2.0) | Public domain + Apache/MIT audio + synthetic data from closed TTS models; CC BY items (Koniwa `tnc` <1 h CC BY 3.0; SIWIS <11 h CC BY 4.0); synthetic-data origin UNKNOWN | None stated | NOT required | 82M params, small | PASS (weights); training-data caveats require owner sign-off |

## License gate result

All three candidates PASS the license gate (each has verified permissive code AND weights licenses). None is excluded.

- **Chatterbox Turbo / base:** PASSES. Watermarked output (Perth). Reference audio optional (not required for plain TTS); if voice cloning is ever used, only a self-generated reference clip may be used (no third-party/person cloning).
- **Maya1:** PASSES. 3B model needs 16GB+ VRAM single GPU — tight on Kaggle T4 (16GB); quantization (int8/int4) available.
- **Kokoro-82M:** PASSES at weights level. Training-data caveats (CC BY attribution items; synthetic-data origin UNKNOWN) require owner sign-off before publication. Already smoke-tested on CPU in Milestone V.

## ASR checker license (for WER / word-timestamp transcription in P3)

| Component | License | Evidence URL | Notes |
|---|---|---|---|
| faster-whisper (code) | MIT (SYSTRAN 2023) | https://raw.githubusercontent.com/guillaumekln/faster-whisper/master/LICENSE | ASR transcription library |
| openai-whisper (code) | MIT (OpenAI 2022) | https://raw.githubusercontent.com/openai/whisper/main/LICENSE | Reference Whisper implementation |
| Whisper model weights (base/small/medium/large) | NOT explicitly licensed in repo | https://github.com/openai/whisper (repo LICENSE is MIT for code only) | Weights downloaded separately from OpenAI; weights license not separately declared in the repo — mark owner confirmation needed if weights are distributed |

## Exclusions

None — all three candidates have verified permissive code+weights licenses. No research-only or non-commercial license found for any candidate.

## Notes for P3 (bake-off)
- Chatterbox output is watermarked (Perth) — record as residual risk, not an exclusion.
- Kokoro-82M training-data caveats (CC BY items, synthetic origin UNKNOWN) — owner sign-off required; record as residual risk.
- Maya1 3B on Kaggle T4 (16GB VRAM) is the tightest fit; confirm GPU/internet availability before starting the P3 job (else P3 = BLOCKED).
- No voice cloning of any third-party or real person's voice; only self-generated reference audio if cloning is ever used.
