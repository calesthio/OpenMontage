---
name: local-voice-cloning
description: Clone a permitted reference voice locally and synthesize speech on-device with OmniVoice GGUF. Use when a user asks to clone a voice locally, keep voice audio private, or create speech conditioned on a supplied voice sample without a paid voice API.
---

# Local Voice Cloning

Use this workflow when the user wants voice cloning performed on their own machine. The reference recording must stay local: never upload it to ElevenLabs, a model host, or another external service. Only download public model/runtime files when needed; do not transmit the user's audio or transcript.

OmniVoice GGUF performs zero-shot, reference-conditioned synthesis. It does **not** train or save a persistent voice identity; pass the reference WAV and its transcript for each synthesis. Get clear user permission to clone the speaker when it is not already explicit. Ask what the generated voice should say if the target text is missing.

## Workflow

1. **Inspect the local setup.** Confirm the supplied audio can be read; check its duration, available disk space, OS/architecture, existing VoiceStudio runtime, cached speech-recognition models, and any existing OmniVoice GGUF assets. Keep generated files, build tools, and weights in the workspace's ignored runtime/cache directory, not in tracked source or outside the workspace.
2. **Choose the local route.** Prefer an already installed and compatible local clone engine. For Intel macOS, VoiceStudio's Python OmniVoice stack may be incompatible with the available PyTorch wheels; OmniVoice's GGUF C++ runtime is a viable CPU path. Do not force-install unsupported PyTorch wheels or switch to a cloud provider without user approval.
3. **Prepare the reference locally.** Convert to mono 24 kHz PCM WAV using the available local audio tool. Obtain an accurate transcript of the reference audio because OmniVoice requires `--ref-text` along with `--ref-wav`. Prefer an installed local ASR model. On Intel macOS, avoid the VoiceStudio ASR backend if it triggers the known duplicate-OpenMP runtime abort; an isolated Python environment with `faster-whisper` and a cached local model worked. If the transcript is uncertain, ask the user to correct it rather than presenting it as authoritative.
4. **Build only if needed.** Pin the runtime to a known source revision and initialize its submodules. Install build tools privately in the ignored runtime directory. Configure the CPU backend with the platform's available acceleration (Apple Accelerate on macOS). On Intel macOS, if AppleClang cannot locate `<array>`, pass the active SDK's libc++ include directory as a system include, e.g. `-isystem "$(xcrun --show-sdk-path)/usr/include/c++/v1"` in `CMAKE_CXX_FLAGS`. Build `omnivoice-tts`; do not change system-wide compiler installations.
5. **Install model weights only when needed.** Use the repository/runtime's pinned model source revision and its CPU quantization mapping (typically Q4_K_M). Check exact artifact sizes and free space first; download to the ignored local model directory and verify the expected file sizes. Model downloads are external network activity, but the voice sample must never be part of those requests.
6. **Synthesize locally.** Run `omnivoice-tts` with the model and tokenizer GGUFs, reference WAV, reference transcript, target text, language, and an explicit output path. Keep the generated WAV in ignored runtime storage unless the user asks to move or export it.
7. **Verify and report.** Confirm the WAV is nonempty and has a valid sample rate, channel count, bit depth, and duration. Optionally transcribe the result using the local ASR model to check the requested words. A transcript check does not establish voice similarity; report any quality uncertainty. Give the user the full output path and note that this is reference-conditioned synthesis, not a trained persistent clone.

## OmniVoice CLI shape

```bash
printf '%s\n' 'Text to speak.' | omnivoice-tts \
  --model /path/to/omnivoice-base-Q4_K_M.gguf \
  --codec /path/to/omnivoice-tokenizer-Q4_K_M.gguf \
  --ref-wav /path/to/reference.wav \
  --ref-text /path/to/reference.txt \
  --lang English \
  --seed 42 \
  -o /path/to/output.wav
```

Never use unsafe duplicate-OpenMP workarounds such as `KMP_DUPLICATE_LIB_OK=TRUE`. If local transcription or inference fails, stop and report the blocker and safe options; do not silently upload the recording or substitute a paid provider.
