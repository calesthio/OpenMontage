# OpenMontage Architecture

> Last updated: 2026-10-25 | Derived from code exploration, not prior documentation. Counts are snapshots; the tool registry (`registry.discover()`) is authoritative for what exists.

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
│   ├── config_model.py     # Pydantic config: LLM, budget, checkpoint, output
│   ├── checkpoint.py       # Pipeline state persistence & stage transitions
│   ├── pipeline_loader.py  # YAML manifest loading & validation
│   ├── media_profiles.py   # Platform-specific render profiles (YouTube, TikTok, etc.)
│   ├── env_loader.py       # .env variable management
│   ├── asset_cache.py, corpus.py, clip_embedder.py, scoring.py   # retrieval-first corpus + clip ranking
│   ├── delivery_promise.py, source_media_review.py, events.py    # brief contracts, user-media intake, board events
│   └── providers/          # (Reserved for future provider abstractions)
│
├── tools/                  # 181 Python tool modules, auto-discovered by the registry
│   ├── base_tool.py        # Abstract base class — the tool contract
│   ├── tool_registry.py    # Auto-discovery singleton registry
│   ├── cost_tracker.py     # Budget governance (estimate → reserve → reconcile)
│   ├── analysis/           # Transcription, scene detection, frame sampling, video understanding
│   ├── audio/              # 18 TTS providers + tts_selector, 6 music generators + search/library, mixing, enhancement
│   ├── avatar/             # Talking head animation, lip sync (HeyGen, Kling, SadTalker, Wav2Lip)
│   ├── capture/            # Screen recording (native recorder, Cap, selector)
│   ├── character/          # Local character animation (specs, SVG rigs, poses, timelines, QA)
│   ├── enhancement/        # Upscale, bg removal, face enhance/restore, color grading
│   ├── graphics/           # 29 image gen providers + image_selector, 3D (Three.js worlds, Blender, Atlas/fal 3D), stock, diagrams, code snippets, math animation
│   ├── provider_contracts/ # JSON model/pricing refresh contracts per provider
│   ├── publishers/         # Export bundle packaging
│   ├── subtitle/           # SRT/VTT generation from timestamps
│   └── video/              # 33 video gen providers + video_selector, composition (Remotion / HyperFrames / FFmpeg), stitching, trimming, clip retrieval, stock_sources/ (17 free archives)
│
├── pipeline_defs/          # YAML pipeline manifests
├── schemas/                # JSON Schema definitions for validation
│   ├── artifacts/          # 20 artifact schemas (brief → publish_log, plus review, decision, character and 3D artifacts)
│   ├── checkpoints/        # Checkpoint state schema
│   ├── pipelines/          # Pipeline manifest schema
│   ├── styles/             # Style playbook schema
│   └── tools/              # Tool-specific schemas
│
├── skills/                 # Layer 2: OpenMontage-specific agent instructions
│   ├── core/               # FFmpeg, Remotion, WhisperX, color grading skills
│   ├── creative/           # Video editing, enhancement, data viz, prompt engineering
│   ├── meta/               # reviewer, checkpoint-protocol, onboarding, taste-direction, bespoke-composition, ...
│   └── pipelines/          # Per-pipeline stage-director skills
│
├── .agents/skills/         # Layer 3: external technology skills (FFmpeg, HyperFrames, GSAP, etc.)
├── styles/                 # Visual style playbooks (YAML) + loader
├── remotion-composer/      # Node.js/React — Remotion video composition renderer
├── backlot/                # Local living-storyboard board (FastAPI + SSE) that watches projects/
├── ink-theater/            # Hand-drawn ink animation engine + Ink Puppet mocap (JS, HyperFrames runtime)
├── scripts/                # Dev scripts: atelier scaffolds, Backlot simulators, provider smoke runs
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
| `atlas_image` / `atlas_video` | Atlas Cloud generation | Exposes exact per-model route catalogs for image generation/editing and text/image/reference/video-edit generation |

Selectors route based on: user preference when explicitly set, then scored ranking across available providers. They adapt input schemas between providers transparently.

### Tool Inventory by Category

Module counts per package as of 2026-10-25 (private helpers and `__init__.py` excluded). Do not treat this as a tool list — run `registry.capability_catalog()` or `registry.provider_catalog()` for the live grouping.

| Package | Modules | What lives there |
|---------|---------|------------------|
| `tools/analysis/` | 15 | Transcription (Whisper, Azure, Mistral, DashScope), scene detection, frame sampling, video analysis/understanding, visual QA, face tracking, audio probes, composition validator |
| `tools/audio/` | 32 | 18 TTS providers + `tts_selector`, 6 music generators plus royalty-free search and the local `music_library`, `audio_mixer`, `audio_enhance`, realtime audio |
| `tools/avatar/` | 5 | HeyGen and Kling avatars, Kling lip sync, local `lip_sync` (Wav2Lip) and `talking_head` (SadTalker) |
| `tools/capture/` | 3 | `screen_recorder`, `cap_recorder`, `screen_capture_selector` |
| `tools/character/` | 1 | `character_animation` — specs, SVG rig plans, pose libraries, action timelines, QA |
| `tools/enhancement/` | 6 | `upscale`, `bg_remove`, `face_enhance`, `face_restore`, `eye_enhance`, `color_grade` |
| `tools/graphics/` | 38 | 29 image generation providers + `image_selector`, 3D (`threejs_world`, `threejs_asset_catalog`, `blender_world`, `atlas_3d`, `fal_3d`), `diagram_gen`, `code_snippet`, `math_animate` |
| `tools/publishers/` | 1 | `export_bundle` |
| `tools/subtitle/` | 1 | `subtitle_gen` |
| `tools/video/` | 50 + 17 stock sources | 33 video generation providers + `video_selector`, `video_compose` (routes to Remotion / HyperFrames / FFmpeg), `hyperframes_compose`, `video_stitch`, `video_trimmer`, clip retrieval and corpus tools, `silence_cutter`, `auto_reframe`, `stock_sources/` (Pexels, Pixabay, Archive.org, NASA, Wikimedia, Unsplash and more) |

---

## Pipeline System

### Pipeline Manifests

Each pipeline is a YAML file in `pipeline_defs/` defining:

```yaml
name: animated-explainer
version: "2.0"
category: generated          # talking_head | generated | hybrid | screen_recording | animation | cinematic | documentary | custom
default_checkpoint_policy: guided

orchestration:
  mode: executive-producer
  skill: pipelines/explainer/executive-producer
  budget_default_usd: 2.00       # the run's default budget (tools.cost_tracker.resolve_budget_usd)
  max_revisions_per_stage: 3     # the executive-producer skill reads these three limits
  max_send_backs: 3
  max_wall_time_minutes: 20

compatible_playbooks:
  - clean-professional
  - flat-motion-graphics

stages:
  - name: research
    skill: pipelines/explainer/research-director
    produces: [research_brief]
    tools_available: []
    checkpoint_required: true
    human_approval_default: false
    review_focus: [...]
    success_criteria: [...]
  # ... through publish
```

### Available Pipelines

| Pipeline | Category | Description |
|----------|----------|-------------|
| `animated-explainer` | generated | AI-produced explainer with research, narration, visuals, music |
| `animation` | animation | Motion graphics, kinetic typography |
| `avatar-spokesperson` | talking_head | Avatar-driven presenter videos |
| `character-animation` | animation | Local rigged cartoon characters with SVG rigs, pose libraries, GSAP timelines, and HyperFrames rendering |
| `cinematic` | cinematic | Trailer, teaser, mood-driven edits |
| `clip-factory` | custom | Batch short-form clips from long source |
| `documentary-montage` | documentary | Retrieval-first thematic montage from a CLIP-indexed corpus of free stock footage and open archives (beta) |
| `hybrid` | hybrid | Source footage + AI-generated support visuals |
| `localization-dub` | custom | Subtitle, dub, and translate existing video |
| `podcast-repurpose` | hybrid | Podcast highlights to video |
| `screen-demo` | screen_recording | Software screen recordings and walkthroughs |
| `talking-head` | talking_head | Footage-led speaker videos |
| `framework-smoke` | custom | Minimal smoke test for framework validation |

### Standard Stage Progression

Most production pipelines follow a canonical 8-stage flow:

```
research → proposal → script → scene_plan → assets → edit → compose → publish
```

Each stage:
1. Has a **stage-director skill** (Markdown instructions for the agent)
2. Declares **tools_available** (what the agent can call)
3. **Produces** one or more canonical artifacts
4. Has **review_focus** criteria and **success_criteria**
5. Can require **human approval** before proceeding

Specialized pipelines may insert domain-specific stages. For example,
`character-animation` adds `character_design` and `rig_plan` before
`scene_plan`, then emits a HyperFrames workspace and final deliverable at
`projects/<project-name>/renders/final.mp4`.

---

## Checkpoint System

Checkpoints persist pipeline state as JSON in the project workspace: `projects/<project_id>/checkpoint_<stage>.json`.

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

**Checkpoint policies** (`lib.checkpoint.resolve_checkpoint_policy` — the strictest of the caller's argument, `checkpoint.policy` in `config.yaml`, and the manifest's `default_checkpoint_policy`):
- `guided` — stop for approval at the stages the manifest gates (`human_approval_default: true`)
- `manual_all` — stop for approval at every stage; set it in `config.yaml` to gate every pipeline
- `auto_noncreative` — accepted, but a manifest gate is binding, so it cannot skip one and behaves as `guided`

**Functions:** `write_checkpoint()`, `read_checkpoint()`, `get_latest_checkpoint()`, `get_completed_stages()`, `get_next_stage()`, `get_stale_stages()`, `get_unreviewed_stages()`, `append_decisions()`, `read_decision_log()`, `decision_log_drift()`

**What `write_checkpoint` fills in by itself:** the checkpoint policy (above); `cost_snapshot` from the spend the tools reported (`tools.cost_tracker.project_cost_snapshot`); `review` from the `awaiting_human` checkpoint being approved (marked `carried_from`); and any decision that was saved to `artifacts/decision_log.json` instead of the project decision log. A stage written `completed`/`awaiting_human` with no review is logged, shows on the board as `NO REVIEW`, and is listed by `get_unreviewed_stages()`.

**One decision log:** `projects/<project_id>/decision_log.json`. Decisions reach it through a checkpoint's `decision_log` artifact or `append_decisions()`. A stage that the manifest adds beyond the nine canonical ones (`character_design`, `rig_plan`) must hand over the first artifact of its `produces` list, the same way a canonical stage hands over its canonical artifact.

### Canonical Artifacts (20 schemas in `schemas/artifacts/`, all JSON-schema validated)

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
| `decision_log` | (any) | Append-only audit trail of every meaningful production choice (the Backlot Decisions rail) |
| `final_review` | compose | Structured self-review of the rendered output |
| `source_media_review` | (pre-idea) | Review of user-supplied media, written before the first planning stage |
| `video_analysis_brief` | (pre-idea) | Structured analysis of a reference video from `video_analyzer` |
| `character_design` | character-animation | Character definitions for local rigged animation |
| `rig_plan` | character-animation | Rig parts, pivots, layers, constraints, views |
| `pose_library` | character-animation | Named reusable poses, expressions, transition hints |
| `action_timeline` | character-animation | Timed character actions and poses compiled for rendering |
| `character_qa_report` | character-animation | Rig integrity, motion, and render-readiness review |

---

## Budget Governance

The `CostTracker` enforces spending controls across the pipeline.

### Lifecycle

```
tracker = CostTracker.for_project(PROJECTS_DIR / project_id)   # one budget (below), projects/<id>/cost_log.json
        |
estimate(tool, operation, $) → entry_id
        |
reserve(entry_id)          # locks budget; raises ApprovalRequiredError when the user must be asked first
reserve(entry_id, approved=True)   # ...then this, once the user has approved that action
        |
reconcile(entry_id, $)     # records actual spend
```

Spend is recorded even when nobody runs that lifecycle:

- Every tool call reports its cost into `projects/<id>/events.jsonl` (the `BaseTool` instrumentation). `CostTracker.sync_tool_events()` turns those reports into ledger entries, keyed by `call_id`, and matches a call that was also reconciled by hand instead of counting it twice.
- `write_checkpoint` calls `project_cost_snapshot()` when no `cost_snapshot` is passed, so every checkpoint carries the recorded spend. Pass an explicit snapshot only to override it.
- Cost no tool reports — rented GPU time, a licence — goes in through `record_rental()` / `record_spend()`, or from the shell:

```bash
python -m tools.cost_tracker record <project-id> --tool vastai_gpu --hours 0.52 --rate 0.40 --details "assets stage"
python -m tools.cost_tracker budget <project-id> --usd 0.64      # the amount approved at proposal
python -m tools.cost_tracker show   <project-id>
```

### One budget

`tools.cost_tracker.resolve_budget_usd()` is the only place a run's budget is decided:

1. the amount the user approved at proposal (`proposal_packet.approval.approved_budget_usd` → `set_budget()`);
2. else the pipeline's `orchestration.budget_default_usd`, capped by `budget.total_usd` in `config.yaml`;
3. else `budget.total_usd`.

The source is stored in the cost log (`metadata.budget_source`).

### Budget Modes

| Mode | Behavior |
|------|----------|
| `observe` | Track costs, no enforcement |
| `warn` | Log warnings on overruns, allow execution |
| `cap` | Reject operations that exceed remaining budget — in `reserve()`, and in the tool layer itself: a paid call attributed to a project that does not fit in what is left returns `BUDGET CAP` without reaching the provider |

### Controls
- **Total budget** — see "One budget" above (`config.yaml` ceiling: $10.00)
- **Reserve holdback** (default: 10%) — kept as safety margin
- **Single-action approval threshold** (default: $0.50) — pause for approval above this
- **New paid tool approval** — first-time use of any paid tool requires confirmation
- Persists to `cost_log.json` per project (written atomically; schema: `schemas/artifacts/cost_log.schema.json`)
- The log's recorded budget is authoritative once it exists — change it with `set_budget()`, not the constructor

---

## 3-Layer Knowledge Architecture

```
Layer 3: .agents/skills/          External technology knowledge (92 skills)
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
  policy: guided          # guided | manual_all

output:
  default_format: mp4
  default_codec: libx264
  default_audio_codec: aac
  default_resolution: 1920x1080
  default_fps: 30
  default_crf: 23
```

All config is validated via Pydantic models in `lib/config_model.py`.

### Environment Variables (.env)

| Variable | Used By | Purpose |
|----------|---------|---------|
| `ELEVENLABS_API_KEY` | elevenlabs_tts, music_gen | TTS, music, sound effects |
| `AZURE_SPEECH_KEY` + `AZURE_SPEECH_REGION` | azure_stt, azure_tts | Azure AI Speech cloud transcription + neural TTS (one resource, both directions) |
| `OPENAI_API_KEY` | openai_tts, openai_image | TTS fallback, GPT Image 2 |
| `XAI_API_KEY` | grok_image, grok_video | Grok image editing/generation, Grok video generation |
| `FAL_KEY` | flux_image, kling_video, veo_video, minimax_video, recraft_image | fal.ai hosted models (FLUX, Veo, Kling, MiniMax, Recraft) |
| `KLING_API_KEY` | kling_official_video, kling_official_image, kling_tts, kling_avatar, kling_lip_sync | Official Kling direct API for video, image, TTS, avatar, and lip sync |
| `KLING_API_BASE_URL` | kling_official_video, kling_official_image, kling_tts, kling_avatar, kling_lip_sync | Optional official Kling API endpoint override |
| `HEYGEN_API_KEY` | heygen_video | Multi-provider video generation |
| `PEXELS_API_KEY` | pexels_image, pexels_video | Stock media |
| `PIXABAY_API_KEY` | pixabay_image, pixabay_video | Stock media |
| `GOOGLE_API_KEY` | google_imagen, google_tts | Google Imagen images, Google Cloud TTS |
| `RUNWAY_API_KEY` | runway_video | Runway Gen-3/Gen-4 direct |
| `HIGGSFIELD_API_KEY` + `HIGGSFIELD_API_SECRET` | higgsfield_video | Higgsfield multi-model video |
| `MODAL_LTX2_ENDPOINT_URL` | ltx_video_modal | Self-hosted LTX-2 |
| `VIDEO_GEN_LOCAL_ENABLED` | local video tools | Enable local GPU generation |
| `VIDEO_GEN_LOCAL_MODEL` | wan, hunyuan, ltx, cogvideo | Select local model |

Kling Official support stays inside the existing provider and capability model.
`kling_official_video` and `kling_official_image` handle Classic, Turbo, and Omni
request shapes, while Elements and Account Usage live under `tools/_kling/` as
internal helpers for element ID references and low-frequency account diagnostics;
they are not separate pipeline stages, selectors, or generated-asset capabilities.

Kling Official also adds provider tools only where OpenMontage already has a
matching capability slot: `kling_tts` for `tts`, plus `kling_avatar` and
`kling_lip_sync` for `avatar`. Official Kling audio effects and video effects are
not registered as tools because current pipelines do not define stable
`sound_effects` or `video_effects` capability routing.

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

- Handles kinetic typography, product promos, launch reels, website-to-video, registry blocks, and SVG/GSAP character rigs
- Driver: `tools/video/hyperframes_compose.py` materializes a workspace under `projects/<name>/hyperframes/`, then runs `lint → validate → render`
- Layer 3 skills vendored at `.agents/skills/hyperframes*/`; Layer 2 guide at `skills/core/hyperframes.md`
- The `character-animation` pipeline uses HyperFrames as the production render package. Browser previews are QA/debug artifacts only, not the render path.

### FFmpeg (fallback / simple cuts)

- Handles pure concat/trim when no composition is needed
- Also handles subtitle burn-in as a post-hoc operation

`video_compose` reads `edit_decisions.render_runtime` and dispatches via `_render_via_hyperframes`, `_remotion_render`, or `_render_via_ffmpeg`. Silent runtime swaps are forbidden — the tool returns a structured blocker when the chosen runtime is unavailable. See `AGENT_GUIDE.md` → "Composition Runtimes (Inside video_compose)" and `skills/core/hyperframes.md` for the full decision matrix.

---

## Test Architecture

```
tests/
├── backlot/                # Backlot board server, state derivation, UI bug-bash
├── contracts/              # Phase 0-3: tool contract validation, schema checks, registry tests
├── fixtures/               # Shared fixtures (provider payloads, sample media)
├── lib/                    # lib/ runtime tests (checkpoint, decision log, corpus, scoring)
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
- FFmpeg (used by nearly every video and audio tool)

**Optional (extend capabilities):**
- Node.js (Remotion composer; Node >= 22 for HyperFrames via `npx hyperframes`)
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
