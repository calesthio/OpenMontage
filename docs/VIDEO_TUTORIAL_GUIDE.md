# OpenMontage Video Tutorial Guide

This guide is a companion for a public beginner-friendly walkthrough of OpenMontage.
It mirrors the project workflow from a fresh checkout through a finished generated video.

## 1. What is OpenMontage?

OpenMontage is an open-source, agent-driven video production system.
A coding assistant such as Claude Code, Cursor, Copilot, or another AI agent reads the repository, follows pipeline manifests, calls Python tools, and assembles finished videos.

OpenMontage can produce:
- AI-driven explainers and animated videos
- Real-footage documentary montages
- Avatar/talking-head videos
- Character animation and motion-graphics sequences
- Hybrid videos mixing stock footage, generated images, and narration

## 2. Prerequisites and setup

### Requirements

- Python 3.10+
- Node.js 18+
- FFmpeg installed and available on PATH
- A compatible AI coding assistant or code-aware LLM

### Clone the repo

```bash
git clone https://github.com/calesthio/OpenMontage.git
cd OpenMontage
```

## 3. Installing dependencies

Run the one-command setup:

```bash
make setup
```

This installs Python dependencies, sets up the Remotion composer, installs local Piper TTS if possible, warms the HyperFrames runtime cache, and creates a `.env` file from `.env.example`.

If you only want Python dependencies:

```bash
make install
```

If you have a GPU and want local video generation support:

```bash
make install-gpu
```

## 4. Running setup / preflight commands

After setup, verify provider availability:

```bash
make preflight
```

This prints the discovered provider menu and helps confirm what tools the current environment can use.

For HyperFrames health checks:

```bash
make hyperframes-doctor
```

## 5. Understanding which providers are configured

OpenMontage uses a runtime provider discovery system.
A provider is "configured" when the corresponding env var or dependency is available.

The most important files and commands are:
- `.env.example` — shows every optional provider key
- `.env` — your local copy where you safely add keys
- `make preflight` — checks the active provider menu
- `docs/PROVIDERS.md` — provider-specific setup and usage notes

## 6. Adding optional API keys safely via `.env`

OpenMontage does not require any API keys to run a zero-key demo.
However, optional keys make more capabilities available.

Copy `.env.example` to `.env` if `make setup` did not already do it:

```bash
cp .env.example .env
```

Then add keys you want to use.
Only add private values to `.env` and do not commit it.

Example keys in `.env.example`:

- `FAL_KEY` — image + video gateway
- `GOOGLE_API_KEY` — Google Imagen image generation and Google Cloud TTS
- `ELEVENLABS_API_KEY` — premium TTS, music, sound
- `OPENAI_API_KEY` — OpenAI fallback and image generation
- `HEGEN_API_KEY`, `RUNWAY_API_KEY` — additional video providers
- `PEXELS_API_KEY`, `PIXABAY_API_KEY`, `UNSPLASH_ACCESS_KEY` — free stock media

> `make setup` will create `.env` from `.env.example` automatically if it is missing.

## 7. Starting a simple first video request

Open the project in your AI coding assistant and give a prompt such as:

```text
Make a 45-second animated explainer about why the sky is blue.
```

Or for the real-footage path:

```text
Make a 60-second documentary montage about city life at night. Use real footage only, no narration, elegiac tone.
```

OpenMontage is designed to be driven by the agent reading the repo, not by a single CLI command.
The AI assistant should understand the pipeline manifests and produce video output automatically.

## 8. How the pipeline flow works at a high level

OpenMontage is stage-driven.
Most pipelines follow this canonical flow:

1. `research`
2. `proposal`
3. `script`
4. `scene_plan`
5. `assets`
6. `edit`
7. `compose`
8. `publish`

Each stage is defined by a YAML manifest in `pipeline_defs/` and a stage director skill in `skills/pipelines/`.
The agent reads the stage instructions, calls tools, writes checkpoint artifacts, and advances the pipeline.

## 9. Script

The `script` stage turns the chosen concept into a narrated script or storyboard.
Script output is stored as pipeline artifacts and used later for narration, timing, scene pacing, and captions.

## 10. Scene plan

The `scene_plan` stage produces a detailed plan for the video.
That plan can include:
- shot descriptions
- visual style directions
- timing and transitions
- asset requirements

## 11. Assets

The `assets` stage generates or fetches the visual elements the video needs.
This can include:
- generated images
- stock footage
- model-generated motion clips
- avatars, backgrounds, charts, diagrams

## 12. Edit

The `edit` stage assembles assets into a rough cut.
For real footage or stock-based videos, this stage chooses shots, trims clips, and sequences them.
For animated and explainers, it sequences cards, images, and captions.

## 13. Compose / Render

The final `compose` stage renders the video.
OpenMontage uses:
- Remotion for React-based video composition
- HyperFrames for HTML/GSAP motion-graphics composition
- FFmpeg for final encoding, subtitles, and mixing

The exact renderer is chosen by the pipeline and the available runtime.

## 14. How approvals / checkpoints work

OpenMontage writes checkpoint JSON files into the `pipeline/` directory.
A checkpoint records:
- current stage
- status
- artifacts
- review notes
- whether human approval is required

Checkpoint policies are configured in `config.yaml`.
The default is `guided`, which may prompt for approval before creative stages or expensive paid tools.

## 15. Where generated files are written

Common output paths:
- `pipeline/` — checkpoint state and artifacts
- `output/` — final rendered video files
- `projects/<project-name>/renders/` — pipeline-specific render output for some pipelines
- `library/` — optional downloaded stock or cached assets

After a successful run, look for `final.mp4` or `render.mp4` in the `output` or `projects/<project-name>/renders` directory.

## 16. Common troubleshooting tips

- If `make setup` fails on Node/npm, try `npx --yes npm install` in `remotion-composer`.
- If `make preflight` reports missing tools, install the missing dependency or add the corresponding key to `.env`.
- If HyperFrames doesn't run, use:
  ```bash
  make hyperframes-doctor
  ```
- If you see video generation failures, check whether provider env vars are set and whether the provider is reachable.
- For local TTS, install `piper-tts` and confirm your Python environment is active.
- Do not commit `.env` or any files containing private keys.

## 17. How to ask good prompts / briefs for better output

Good prompts are:
- clear about format: `animated explainer`, `documentary montage`, `talking head`, `character animation`
- specific about tone: `elegiac`, `playful`, `professional`, `educational`
- explicit about what to include or exclude: `use real footage only`, `no narration`, `include captions`
- concrete about duration: `45 seconds`, `60-second video`
- explicit about audience: `for kids`, `for product launch`, `for social media`

Example starter prompts:

- `Make a 45-second animated explainer about why the sky is blue.`
- `Create a 60-second documentary montage about city life at night, using only public-domain footage.`
- `Make a 30-second product launch teaser for a new AI writing tool, with upbeat music and captions.`

## 18. Recording a public tutorial

Recommended length: 8–12 minutes.

Suggested video sections:
1. Intro: What OpenMontage is and what it can do
2. Fresh checkout and install
3. Running `make setup` and `.env` safety
4. Checking provider availability with `make preflight`
5. Starting a first prompt
6. Explaining the pipeline stages
7. Showing output files and render location
8. Troubleshooting tips
9. Prompt best practices

If you want help validating this workflow before recording, the best approach is to run `make setup`, `make preflight`, and a first demo prompt with a zero-key or optional-key path and confirm the final video file location.
