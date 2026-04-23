# OpenMontage Architecture

> Last updated: 2026-03-28 | Derived from code exploration, not prior documentation.

OpenMontage is an **agent-orchestrated video production platform**. An LLM coding assistant (Claude Code, Cursor, Copilot, etc.) acts as the orchestrator — reading pipeline manifests, following skill instructions, calling Python tools, and checkpointing state. There is no runtime Python orchestrator; the agent _is_ the control plane.

---

## High-Level Flow

```
User gives topic/idea
        |
        v
Agent reads pipeline manifest (YAML)
        |
        v
For each stage:
   1. Agent reads stage-director skill (Markdown)
   2. Agent calls Python tools via tool registry
   3. Agent writes checkpoint (JSON) with artifacts
   4. Agent self-reviews using meta/reviewer skill
   5. Human approval gate (if configured)
        |
        v
Final video output
```

---

## Repository Layout

```
OpenMontage/
├── lib/                    # Core runtime infrastructure (Python)
│   ├── config_model.py     # Pydantic config: LLM, budget, checkpoint, output, paths
│   ├── checkpoint.py       # Pipeline state persistence & stage transitions
│   ├── pipeline_loader.py  # YAML manifest loading & validation
│   ├── media_profiles.py   # Platform-specific render profiles (YouTube, TikTok, etc.)
│   ├── env_loader.py       # .env variable management
│   └── providers/          # (Reserved for future provider abstractions)
│
├── tools/                  # 57+ Python tool implementations
│   ├── base_tool.py        # Abstract base class — the tool contract
│   ├── tool_registry.py    # Auto-discovery singleton registry
│   ├── cost_tracker.py     # Budget governance (estimate → reserve → reconcile)
│   ├── analysis/           # Transcription, scene detection, frame sampling, video understanding
│   ├── audio/              # TTS (ElevenLabs, OpenAI, Piper), music gen, mixing, enhancement
│   ├── avatar/             # Talking head animation, lip sync
│   ├── enhancement/        # Upscale, bg removal, face enhance/restore, color grading
│   ├── graphics/           # Image gen (FLUX, DALL-E, Recraft, local diffusion), stock, diagrams, code snippets, math animation
│   ├── publishers/         # (Reserved)
│   ├── subtitle/           # SRT/VTT generation from timestamps
│   └── video/              # 13 video gen providers, composition, stitching, trimming
│
├── pipeline_defs/          # 11 YAML pipeline manifests
├── schemas/                # JSON Schema definitions for validation
│   ├── artifacts/          # 11 artifact schemas (brief → publish_log)
│   ├── checkpoints/        # Checkpoint state schema
│   ├── pipelines/          # Pipeline manifest schema
│   ├── styles/             # Style playbook schema
│   └── tools/              # Tool-specific schemas
│
├── skills/                 # Layer 2: OpenMontage-specific agent instructions
│   ├── core/               # FFmpeg, Remotion, WhisperX, color grading skills
│   ├── creative/           # Video editing, enhancement, data viz, prompt engineering
│   ├── meta/               # reviewer, checkpoint-protocol, skill-creator
│   └── pipelines/          # Per-pipeline stage-director skills (10 pipelines)
│
├── .agents/skills/         # Layer 3: 47 external technology skills (FFmpeg, ElevenLabs, FLUX, etc.)
├── styles/                 # Visual style playbooks (YAML) + loader
├── remotion-composer/      # Node.js/React — Remotion video composition renderer
├── tests/                  # Contract tests, QA integration tests, eval harness
├── docs/                   # Best-practices guides, session handoffs, audits
└── config.yaml             # Global runtime configuration
```

---

## Core Architectural Principles

### 1. Agent-First Orchestration

There is **no Python orchestrator**. The LLM agent:
- Reads the pipeline manifest to know the stage order
- Reads each stage-director skill for detailed instructions
- Calls tools, evaluates results, makes creative decisions
- Writes checkpoints to persist state between stages

Python provides **tools and persistence only**. All intelligence lives in skill instructions (Markdown) and pipeline manifests (YAML).

### 2. No LLM API Key in Runtime

OpenMontage does not call LLM APIs at runtime. The coding assistant running in the user's IDE _is_ the LLM. Tools that need generation (images, video, TTS) call domain-specific APIs directly (ElevenLabs, fal.ai, HeyGen, etc.), not general-purpose LLM endpoints.

### 3. Dual-Provider Support

Every capability must support both **API providers** (cloud, paid) and **local/open-source alternatives** (free, GPU-dependent). The selector pattern enforces this by routing to whatever is available.

---

## The Tool System

### BaseTool Contract

All tools inherit from `BaseTool` (ABC) and declare:

| Field | Purpose |
|-------|---------|
| `name`, `version` | Identity |
| `tier` | CORE, VOICE, ENHANCE, GENERATE, SOURCE, ANALYZE, PUBLISH |
| `capability` | What it does (e.g., `tts`, `image_generation`, `video_post`) |
| `provider` | Which service (e.g., `elevenlabs`, `ffmpeg`, `selector`) |
| `runtime` | LOCAL, LOCAL_GPU, API, HYBRID |
| `stability` | EXPERIMENTAL, BETA, PRODUCTION |
| `dependencies` | Required binaries (`cmd:ffmpeg`), env vars (`env:ELEVENLABS_API_KEY`), Python packages (`python:torch`) |
| `input_schema`, `output_schema` | JSON Schema for inputs/outputs |
| `fallback_tools` | Ordered fallback chain |
| `agent_skills` | Links to Layer 3 knowledge skills |
| `resource_profile` | CPU, RAM, VRAM, disk, network requirements |
| `retry_policy` | Max retries, backoff strategy |

**Required method:** `execute(inputs) -> ToolResult`

`ToolResult` carries: `success`, `data`, `artifacts` (file paths), `error`, `cost_usd`, `duration_seconds`, `seed`, `model`.

### Tool Registry

`ToolRegistry` is a singleton that auto-discovers all `BaseTool` subclasses via `pkgutil.walk_packages()`. No manual registration.

Key queries:
- `get_by_capability("tts")` — all TTS tools
- `get_by_provider("elevenlabs")` — all ElevenLabs tools
- `get_available()` — tools whose dependencies are satisfied
- `find_fallback("elevenlabs_tts")` — resolve fallback chain
- `support_envelope()` — full capability report for agent consumption
- `gpu_required_tools()`, `network_required_tools()`

### Selector Pattern

Three selector tools abstract multi-provider capabilities:

| Selector | Capability | How selection works |
|----------|-----------|---------------------|
| `tts_selector` | Text-to-speech | Ranks discovered providers by task fit, quality, control, reliability, cost, latency, and continuity |
| `image_selector` | Image generation | Ranks discovered providers from the live registry; no hardcoded provider order |
| `video_selector` | Video generation | Ranks discovered providers from the live registry; user preference is respected when explicitly provided |

Selectors route based on: user preference when explicitly set, then scored ranking across available providers. They adapt input schemas between providers transparently.

### Tool Inventory by Category

**Analysis (4):** transcriber (WhisperX), scene_detect, frame_sampler, video_understand (CLIP/BLIP-2)

**Audio (8):** elevenlabs_tts, google_tts, openai_tts, piper_tts, tts_selector, music_gen, audio_mixer, audio_enhance

**Avatar (2):** talking_head (SadTalker/MuseTalk), lip_sync (Wav2Lip)

**Enhancement (5):** upscale (Real-ESRGAN), bg_remove (rembg/U2Net), face_enhance, face_restore (CodeFormer/GFPGAN), color_grade (FFmpeg LUTs)

**Graphics (13):** flux_image, grok_image, google_imagen, openai_image, recraft_image, local_diffusion, pexels_image, pixabay_image, image_selector, code_snippet, diagram_gen, math_animate (ManimCE), image_gen (deprecated)

**Subtitle (1):** subtitle_gen

**Video (18):** grok_video, heygen_video, higgsfield_video, veo_video, kling_video, runway_video, minimax_video, wan_video, hunyuan_video, cogvideo_video, ltx_video_local, ltx_video_modal, pexels_video, pixabay_video, video_selector, video_compose (FFmpeg), video_stitch, video_trimmer

---

## Pipeline System

### Pipeline Manifests

Each pipeline is a YAML file in `pipeline_defs/` defining:

```yaml
name: animated-explainer
version: "2.0"
category: generated          # talking_head | generated | hybrid | screen_recording | animation | cinematic | custom
default_checkpoint_policy: guided

orchestration:
  mode: executive-producer
  skill: pipelines/explainer/executive-producer
  budget_default_usd: 2.00
  max_revisions_per_stage: 3

compatible_playbooks:
  - clean-professional
  - flat-motion-graphics

stages:
  - name: research
    skill: pipelines/explainer/research-director
    produces: [research_brief]
    tools_available: []
    checkpoint_required: false
    human_approval_default: false
    review_focus: [...]
    success_criteria: [...]
  # ... through publish
```

### Available Pipelines (11)

| Pipeline | Category | Description |
|----------|----------|-------------|
| `animated-explainer` | generated | AI-produced explainer with research, narration, visuals, music |
| `animation` | animation | Motion graphics, kinetic typography |
| `avatar-spokesperson` | talking_head | Avatar-driven presenter videos |
| `cinematic` | cinematic | Trailer, teaser, mood-driven edits |
| `clip-factory` | custom | Batch short-form clips from long source |
| `hybrid` | hybrid | Source footage + AI-generated support visuals |
| `localization-dub` | custom | Subtitle, dub, and translate existing video |
| `podcast-repurpose` | hybrid | Podcast highlights to video |
| `screen-demo` | screen_recording | Software screen recordings and walkthroughs |
| `talking-head` | talking_head | Footage-led speaker videos |
| `framework-smoke` | custom | Minimal smoke test for framework validation |

### Standard Stage Progression

All production pipelines follow a canonical 8-stage flow:

```
research → proposal → script → scene_plan → assets → edit → compose → publish
```

Each stage:
1. Has a **stage-director skill** (Markdown instructions for the agent)
2. Declares **tools_available** (what the agent can call)
3. **Produces** one or more canonical artifacts
4. Has **review_focus** criteria and **success_criteria**
5. Can require **human approval** before proceeding

---

## Checkpoint System

Checkpoints persist pipeline state as JSON in the project's `pipeline/` directory.

```json
{
  "version": "1.0",
  "project_id": "my-video",
  "stage": "script",
  "status": "completed",
  "timestamp": "2026-03-28T10:00:00Z",
  "checkpoint_policy": "guided",
  "human_approval_required": false,
  "human_approved": true,
  "artifacts": { "script": { ... } },
  "review": { ... },
  "cost_snapshot": { ... }
}
```

**Status values:** `pending` | `in_progress` | `awaiting_human` | `completed` | `failed`

**Checkpoint policies:**
- `guided` — checkpoint at key creative stages, auto-proceed on mechanical ones
- `manual_all` — human approval at every stage
- `auto_noncreative` — auto-proceed unless stage is creative (assets, edit)

**Functions:** `write_checkpoint()`, `read_checkpoint()`, `get_latest_checkpoint()`, `get_completed_stages()`, `get_next_stage()`

### Canonical Artifacts (11 types, all JSON-schema validated)

| Artifact | Stage | Contains |
|----------|-------|----------|
| `research_brief` | research | Landscape analysis, data points, audience insights, angles |
| `proposal_packet` | proposal | Concept options, production plan, cost estimates, approval gate |
| `brief` | idea | Title, hook, key points, tone, style, platform, duration |
| `script` | script | Timestamped sections with enhancement cues, pronunciation guides |
| `scene_plan` | scene_plan | Scene definitions with type, description, timing |
| `asset_manifest` | assets | Generated assets with path, source tool, scene association |
| `edit_decisions` | edit | Editorial cuts with in/out timings |
| `render_report` | compose | Output metadata (format, resolution, duration) |
| `publish_log` | publish | Platform publication entries with status |
| `review` | (any) | Reviewer feedback and approval records |
| `cost_log` | (any) | Budget tracking entries |

---

## Budget Governance

The `CostTracker` enforces spending controls across the pipeline.

### Lifecycle

```
estimate(tool, operation, $) → entry_id
        |
reserve(entry_id)          # locks budget
        |
reconcile(entry_id, $)     # records actual spend
```

### Budget Modes

| Mode | Behavior |
|------|----------|
| `observe` | Track costs, no enforcement |
| `warn` | Log warnings on overruns, allow execution |
| `cap` | Reject operations that exceed remaining budget |

### Controls
- **Total budget** (default: $10.00)
- **Reserve holdback** (default: 10%) — kept as safety margin
- **Single-action approval threshold** (default: $0.50) — pause for approval above this
- **New paid tool approval** — first-time use of any paid tool requires confirmation
- Persists to `cost_log.json` per project

---

## 3-Layer Knowledge Architecture

```
Layer 3: .agents/skills/          External technology knowledge (47 skills)
         "How the technology works"    FFmpeg, ElevenLabs API, FLUX, Remotion, Three.js, etc.
              ^
              | agent_skills[] references
              |
Layer 2: skills/                  OpenMontage conventions
         "How this project uses the tech"  Pipeline integration, quality checklists, artifact mappings
              ^
              | stage skill references
              |
Layer 1: tools/ + pipeline_defs/  Executable capabilities + orchestration definitions
         "What exists and when to use it"  BaseTool contracts, pipeline manifests
```

Each tool's `agent_skills[]` field links Layer 1 to Layers 2 and 3. For example:
- `video_compose.agent_skills = ["remotion-best-practices", "remotion", "ffmpeg"]`
- `tts_selector.agent_skills = ["text-to-speech", "elevenlabs", "openai-docs"]`

---

## Configuration

### config.yaml

```yaml
llm:
  provider: anthropic
  temperature: 0.7
  max_tokens: 4096

budget:
  mode: warn
  total_usd: 10.00
  reserve_pct: 0.10
  single_action_approval_usd: 0.50

checkpoint:
  policy: guided
  storage_dir: pipeline

output:
  default_format: mp4
  default_codec: libx264
  default_audio_codec: aac
  default_resolution: 1920x1080
  default_fps: 30
  default_crf: 23

paths:
  pipeline_dir: pipeline
  library_dir: library
  styles_dir: styles
  skills_dir: skills
  output_dir: output
```

All config is validated via Pydantic models in `lib/config_model.py`.

### Environment Variables (.env)

| Variable | Used By | Purpose |
|----------|---------|---------|
| `ELEVENLABS_API_KEY` | elevenlabs_tts, music_gen | TTS, music, sound effects |
| `OPENAI_API_KEY` | openai_tts, openai_image | TTS fallback, DALL-E 3 |
| `XAI_API_KEY` | grok_image, grok_video | Grok image editing/generation, Grok video generation |
| `FAL_KEY` | flux_image, kling_video, veo_video, minimax_video, recraft_image | fal.ai hosted models (FLUX, Veo, Kling, MiniMax, Recraft) |
| `HEYGEN_API_KEY` | heygen_video | Multi-provider video generation |
| `PEXELS_API_KEY` | pexels_image, pexels_video | Stock media |
| `PIXABAY_API_KEY` | pixabay_image, pixabay_video | Stock media |
| `GOOGLE_API_KEY` | google_imagen, google_tts | Google Imagen images, Google Cloud TTS |
| `RUNWAY_API_KEY` | runway_video | Runway Gen-3/Gen-4 direct |
| `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET` | higgsfield_video | Higgsfield multi-model video |
| `MODAL_LTX2_ENDPOINT_URL` | ltx_video_modal | Self-hosted LTX-2 |
| `VIDEO_GEN_LOCAL_ENABLED` | local video tools | Enable local GPU generation |
| `VIDEO_GEN_LOCAL_MODEL` | wan, hunyuan, ltx, cogvideo | Select local model |

---

## Visual Style System

Style playbooks in `styles/` define visual language for pipelines:

- `clean-professional.yaml` — Corporate, polished look
- `flat-motion-graphics.yaml` — Modern flat design
- `minimalist-diagram.yaml` — Technical, minimal diagrams

Loaded by `styles/playbook_loader.py`. Each pipeline declares `compatible_playbooks` in its manifest. Validated against `schemas/styles/playbook.schema.json`.

---

## Media Profiles

Platform-specific render configurations in `lib/media_profiles.py`:

| Profile | Resolution | Aspect | Notes |
|---------|-----------|--------|-------|
| `youtube_landscape` | 1920x1080 | 16:9 | Standard YouTube |
| `youtube_4k` | 3840x2160 | 16:9 | 4K YouTube |
| `youtube_shorts` | 1080x1920 | 9:16 | Max 60s |
| `instagram_reels` | 1080x1920 | 9:16 | Max 90s |
| `instagram_feed` | 1080x1080 | 1:1 | Square |
| `tiktok` | 1080x1920 | 9:16 | Vertical |
| `linkedin` | 1920x1080 | 16:9 | Landscape |
| `cinematic` | 2560x1080 | 21:9 | Ultrawide |

Each profile specifies codec, audio codec, CRF, pixel format, max file size, max duration, and caption format. `ffmpeg_output_args(profile)` generates the corresponding FFmpeg flags.

---

## Composition Runtimes

OpenMontage has a multi-runtime composition layer. Three engines live behind `video_compose`, chosen at proposal and locked in `edit_decisions.render_runtime`:

### Remotion (React-based)

A standalone Node.js/React subproject in `remotion-composer/` using [Remotion](https://www.remotion.dev/).

- **React 18** + **Remotion 4.0** + **TypeScript 5.3**
- Handles the existing scene-component stack (`text_card`, `stat_card`, charts, captions, `TalkingHead`, `CinematicRenderer`)
- Scripts: `start` (studio), `build` (render), `upgrade`

### HyperFrames (HTML/CSS/GSAP)

Consumed via `npx hyperframes` (no monorepo checkout needed). Runtime floor: Node.js ≥ 22, FFmpeg, `npx`.

- Handles kinetic typography, product promos, launch reels, website-to-video, registry blocks
- Driver: `tools/video/hyperframes_compose.py` materializes a workspace under `projects/<name>/hyperframes/`, then runs `lint → validate → render`
- Layer 3 skills vendored at `.agents/skills/hyperframes*/`; Layer 2 guide at `skills/core/hyperframes.md`

### FFmpeg (fallback / simple cuts)

- Handles pure concat/trim when no composition is needed
- Also handles subtitle burn-in as a post-hoc operation

`video_compose` reads `edit_decisions.render_runtime` and dispatches via `_render_via_hyperframes`, `_remotion_render`, or `_render_via_ffmpeg`. Silent runtime swaps are forbidden — the tool returns a structured blocker when the chosen runtime is unavailable. See `AGENT_GUIDE.md` → "Composition Runtimes (Inside video_compose)" and `skills/core/hyperframes.md` for the full decision matrix.

---

## Test Architecture

```
tests/
├── contracts/              # Phase 0-3: tool contract validation, schema checks, registry tests
├── qa/                     # Integration tests: TTS, image gen, music, audio mix, video compose/stitch, E2E
├── eval/                   # Golden scenario replay harness for regression testing
├── pipelines/              # Pipeline-level tests
├── tools/                  # Individual tool tests
└── styles/                 # Style playbook tests
```

**Contract tests** verify every tool satisfies the `BaseTool` contract: identity fields, schemas, dependency declarations, inheritance.

**QA tests** call real tools (with real APIs/binaries) and inspect output quality.

**Eval harness** (`tests/eval/replay_harness/`) replays golden scenarios with tolerance-based comparison for stochastic outputs.

---

## System Dependencies

**Required:**
- Python >= 3.10
- FFmpeg (used by ~15 tools)

**Optional (extend capabilities):**
- Node.js (for Remotion composer)
- GPU + CUDA (for local video/image generation)
- Piper (offline TTS)
- ManimCE (math animations)
- Mermaid CLI (diagram generation)

**Python packages:** pyyaml, pydantic, jsonschema, python-dotenv (core); pytest, pytest-asyncio (dev); torch, torchvision, torchaudio (GPU)

---

## Key Design Decisions

1. **No runtime orchestrator** — The LLM agent reads YAML + Markdown and drives everything. This makes the system debuggable (just read the skill) and model-agnostic.

2. **Checkpoint-based resumption** — Any stage can fail and the pipeline resumes from the last checkpoint. No re-running completed stages.

3. **Schema-validated artifacts** — Every stage output is validated against a JSON Schema before the checkpoint is written. Prevents garbage propagation.

4. **Budget as a first-class concept** — Cost estimation before execution, budget reservation, and reconciliation. The agent cannot silently overspend.

5. **Selector pattern over hard-coded providers** — Capabilities degrade gracefully. Missing an API key? The selector falls through to the next provider or a local alternative.

6. **Skills over code for intelligence** — Creative decisions, quality checklists, review criteria, and prompt templates live in Markdown skills, not Python. This means the agent's behavior can be tuned by editing text files, not code.
