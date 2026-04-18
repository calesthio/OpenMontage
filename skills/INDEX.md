# OpenMontage â€" Skill Index

> For the full agent onboarding guide, see [`AGENT_GUIDE.md`](../AGENT_GUIDE.md) in the project root.

This file lists all available Layer 2 skills and documents the 3-layer knowledge architecture.

## Knowledge Architecture

```
Layer 1: tools/tool_registry.py          "What tools exist and what they can do"
         tools/base_tool.py               Each tool declares: capabilities, tier, status,
                                          dependencies, cost, and agent_skills[]

         â†" agent_skills[] points to â†"

Layer 2: skills/                          "How OpenMontage uses these tools"
         Project-specific conventions:     Pipeline integration, artifact mappings,
         {core,creative,meta,pipelines}/   enhancement chain order, quality checklists

         â†" references underlying tech in â†"

Layer 3: .agents/skills/                  "How the technology itself works"
         Generic API knowledge from        Correct import paths, code patterns,
         skills.sh (47 installed skills)   constraints, parameters â€" tech-agnostic
```

**How the agent uses this:**
1. The orchestrator queries Layer 1 (`tool_registry.support_envelope()`) to see what's available
2. Each tool's `agent_skills[]` field names the Layer 3 skills it relies on
3. Layer 2 skills (this directory) teach the agent OpenMontage-specific conventions
4. Layer 3 skills (`.agents/skills/`) provide generic API knowledge, loaded on-demand

## Capability Families & Tool Discovery

Every tool declares a `capability` (what it does) and a `provider` (who/what powers it). The registry groups tools by capability so agents can discover all options for a given task.

### Selector / Provider Pattern

For capability families with multiple providers (TTS, video generation), the architecture uses:
- **Selector tool** (`tts_selector`, `video_selector`, `image_selector`) — routes to the best available provider based on requirements, API key availability, and cost. Selectors auto-discover providers from the registry. Agents should default to selectors when the user hasn't specified a provider.
- **Provider tools** — call a specific provider directly. Agents use these when the user explicitly requests a provider or when the selector's routing isn't appropriate.

### Capability Family Reference

**Do not maintain a hardcoded tool list.** The registry is the single source of truth. Query it at runtime:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
```

Key capability families to look for in the output:

| Capability | Selector | Discovery |
|---|---|---|
| `tts` | `tts_selector` | Auto-discovers all `capability="tts"` tools |
| `video_generation` | `video_selector` | Auto-discovers all `capability="video_generation"` tools |
| `image_generation` | `image_selector` | Auto-discovers all `capability="image_generation"` tools |
| `audio_processing` | — | FFmpeg-based local tools |
| `enhancement` | — | Mixed providers |
| `analysis` | — | Mixed providers |
| `graphics` | — | Local rendering tools |
| `music_generation` | — | Single-provider |
| `subtitle` | — | Pure Python |
| `avatar` | — | Local GPU models |
| `video_post` | — | FFmpeg-based local tools |
| `social_publishing` | — | Upload-Post API (11 platforms) |

### Adding New Tools

1. Place the tool in the correct capability folder (or create a new one under `tools/`)
2. Set `capability` and `provider` in the class definition
3. If joining a multi-provider family, the existing selector discovers it automatically
4. Attach relevant Layer 2 and Layer 3 skills via `agent_skills[]`
5. The registry discovers tools automatically — no manual registration needed
6. **No other files need updating** — selectors, manifests, and instructions all derive from the registry

## Core Skills

| Skill | File | Trigger | Agent Skills (Layer 3) |
|-------|------|---------|----------------------|
| FFmpeg | `core/ffmpeg.md` | Video encoding, filtering, composition | `ffmpeg`, `video_toolkit` |
| Remotion | `core/remotion.md` | React-based composition, Phase 3+ | `remotion-best-practices`, `remotion` |
| WhisperX | `core/whisperx.md` | Transcription with word-level timestamps | `speech-to-text` |
| Subtitle Sync | `core/subtitle-sync.md` | Subtitle timing and alignment | `remotion-best-practices` |
| Color Grading | `core/color-grading.md` | FFmpeg color profiles, LUT workflow, accessibility | `ffmpeg` |
| Social Publishing | `core/social-publishing.md` | Publish to 11 social platforms via Upload-Post API | — |

## Creative Skills

| Skill | File | Trigger | Agent Skills (Layer 3) |
|-------|------|---------|----------------------|
| Video Editing | `creative/video-editing.md` | Cut decisions, pacing, rhythm | `ffmpeg`, `video_toolkit` |
| Enhancement Strategy | `creative/enhancement-strategy.md` | Overlay placement and density | `ffmpeg` |
| Data Visualization | `creative/data-visualization.md` | Chart type selection, animation, label placement | `d3-viz`, `remotion-best-practices` |
| Video Stitching | `creative/video-stitching.md` | Multi-clip assembly, AI clip chaining, spatial composition | `ffmpeg`, `video_toolkit` |
| Video Gen Prompting | `creative/video-gen-prompting.md` | Universal video generation prompt vocabulary | `ai-video-gen`, `ltx2`, `create-video` |
| â†³ Seedance Prompting | `creative/prompting/seedance-prompting.md` | **Preferred premium default.** Seedance 2.0 8-component structure, multi-shot, lip-sync, reference-to-video | `seedance-2-0`, `ai-video-gen` |
| â†³ Grok Prompting | `creative/prompting/grok-prompting.md` | Grok image/video prompting, edit flows, reference-image video | `grok-media` |
| â†³ Sora Prompting | `creative/prompting/sora-prompting.md` | Sora 2 structured template, advanced fields | `ai-video-gen` |
| â†³ VEO Prompting | `creative/prompting/veo-prompting.md` | VEO 3.1 14-component structure, art movements | `ai-video-gen` |
| â†³ LTX Prompting | `creative/prompting/ltx-prompting.md` | LTX-2 6-element structure, audio prompting | `ltx2` |
| â†³ HunyuanVideo Prompting | `creative/prompting/hunyuan-prompting.md` | HunyuanVideo formula, I2V best practices | â€" |
| Storytelling | `creative/storytelling.md` | Narrative structure, hooks, pacing, Mayer's principles | â€" |
| Sound Design | `creative/sound-design.md` | Audio ducking, LUFS targets, SFX timing, AI TTS mixing | `elevenlabs` |
| Typography | `creative/typography.md` | Font selection, text sizing, safe zones, caption styling | â€" |
| ManimCE Usage | `creative/manim-usage.md` | Scene composition, animation timing, color usage | `manimce-best-practices` |
| Image Gen Usage | `creative/image-gen-usage.md` | Prompt consistency, hero reference, batch strategy | `flux-best-practices`, `bfl-api` |
| Image Provider Usage | `creative/image-provider-usage.md` | Provider selection (FLUX/Grok/OpenAI/Recraft/stock), cost-quality tradeoffs | `flux-best-practices`, `bfl-api`, `grok-media` |
| B-Roll Planning | `creative/broll-planning.md` | Stock vs. generated decision, query construction, footage evaluation | — |
| Stock Sourcing Usage | `creative/stock-sourcing-usage.md` | Pexels/Pixabay usage, parameters, licensing, integration | — |
| Scene Detect Usage | `creative/scene-detect-usage.md` | Threshold tuning, algorithm selection, content presets | â€" |
| Diagram Gen Usage | `creative/diagram-gen-usage.md` | Complexity limits, progressive building, themes | `beautiful-mermaid` |
| Music Gen Usage | `creative/music-gen-usage.md` | BPM selection, prompt engineering, duration matching | `music`, `elevenlabs` |
| Background Removal | `creative/bg-remove-usage.md` | Model selection, alpha matting, compositing workflows | â€" |
| Upscaling | `creative/upscale-usage.md` | Scale factor, model selection, face-aware upscaling | â€" |
| Face Restoration | `creative/face-restore-usage.md` | CodeFormer/GFPGAN selection, fidelity tuning, vs face_enhance | â€" |
| Lip Sync | `creative/lip-sync-usage.md` | Wav2Lip model selection, dubbing workflows, input requirements | `faceswap` |
| Talking Head Gen | `creative/talking-head-gen-usage.md` | SadTalker/MuseTalk, photo-to-video, expression tuning | `avatar-video` |
| Video Understanding | `creative/video-understand-usage.md` | Visual QA, quality gating, scene classification | `video-understand` |

## Pipeline Type Skills

Pipeline type skills provide production guidance for specific video formats, independent of the animated-explainer or talking-head pipeline.

| Skill | File | When to Use |
|-------|------|-------------|
| Short-Form | `creative/short-form.md` | TikTok, Reels, Shorts â€" vertical 9:16, under 60s |
| Long-Form | `creative/long-form.md` | YouTube 10+ min â€" chapters, retention, end screens |
| Screen Recording | `creative/screen-recording.md` | Code walkthroughs, tutorials, software demos |
| Animation Pipeline | `creative/animation-pipeline.md` | Motion graphics, easing, transitions, composition |
| Cinematic | `creative/cinematic.md` | Letterbox, film pacing, layered audio, color grading |

## Pipeline Stage Director Skills

Stage director skills teach the agent HOW to execute each pipeline stage. Each skill is a detailed markdown file with process steps, quality rubrics, and self-evaluation criteria.

### Animated Explainer Pipeline (`pipelines/explainer/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/explainer/executive-producer.md` | `all` | **8-stage serial orchestration, quality gates, cross-stage checks, send-back** |
| **Research Director** | `pipelines/explainer/research-director.md` | `research` | **Web research methodology, 5 search batches, landscape/trending/data/audience/expert analysis** |
| **Proposal Director** | `pipelines/explainer/proposal-director.md` | `proposal` | **Concept options from research, production plan, cost estimate, approval gate** |
| Script Director | `pipelines/explainer/script-director.md` | `script` | Narrative architecture, timing, enhancement cues, research integration |
| Scene Director | `pipelines/explainer/scene-director.md` | `scene_plan` | Visual planning, technique library, feasibility |
| Asset Director | `pipelines/explainer/asset-director.md` | `assets` | TTS, image gen, diagram gen, music, budget |
| Edit Director | `pipelines/explainer/edit-director.md` | `edit` | Timeline assembly, subtitles, audio ducking |
| Compose Director | `pipelines/explainer/compose-director.md` | `compose` | FFmpeg/Remotion render, audio mixing |
| Publish Director | `pipelines/explainer/publish-director.md` | `publish` | SEO metadata, chapters, export packaging |

> **Note:** The old `idea-director.md` still exists for reference but is superseded by the research + proposal two-stage flow in v2.0. The talking-head pipeline continues to use its own `idea-director`.

### Talking Head Pipeline (`pipelines/talking-head/`)

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| Idea Director | `pipelines/talking-head/idea-director.md` | `idea` | Footage inspection, content assessment |
| Script Director | `pipelines/talking-head/script-director.md` | `script` | Transcription, section segmentation |
| Scene Director | `pipelines/talking-head/scene-director.md` | `scene_plan` | Enhancement planning, overlay placement |
| Asset Director | `pipelines/talking-head/asset-director.md` | `assets` | Subtitle gen, audio extraction |
| Edit Director | `pipelines/talking-head/edit-director.md` | `edit` | Cut assembly, subtitle config |
| Compose Director | `pipelines/talking-head/compose-director.md` | `compose` | Enhancement chain, render |
| Publish Director | `pipelines/talking-head/publish-director.md` | `publish` | Metadata, export packaging |

### Screen Demo Pipeline (`pipelines/screen-demo/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/screen-demo/executive-producer.md` | `all` | **7-stage serial orchestration, legibility gates, audio clarity, pacing checks** |
| Idea Director | `pipelines/screen-demo/idea-director.md` | `idea` | Workflow scoping, UI density assessment, output-shape choice |
| Script Director | `pipelines/screen-demo/script-director.md` | `script` | Action mapping, procedural narration, speed planning |
| Scene Director | `pipelines/screen-demo/scene-director.md` | `scene_plan` | Crop planning, callout restraint, aspect-ratio viability |
| Asset Director | `pipelines/screen-demo/asset-director.md` | `assets` | Subtitle-first asset kit, audio cleanup, reusable overlays |
| Edit Director | `pipelines/screen-demo/edit-director.md` | `edit` | Tight timeline planning, speed notes, subtitle zone control |
| Compose Director | `pipelines/screen-demo/compose-director.md` | `compose` | Legibility-first render, crisp screen output, verification |
| Publish Director | `pipelines/screen-demo/publish-director.md` | `publish` | Searchable metadata, chapter packaging, thumbnail concepts |

### Clip Factory Pipeline (`pipelines/clip-factory/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/clip-factory/executive-producer.md` | `all` | **7-stage serial orchestration, clip selection gates, batch consistency, hook placement** |
| Idea Director | `pipelines/clip-factory/idea-director.md` | `idea` | Batch strategy, clip families, yield planning |
| Script Director | `pipelines/clip-factory/script-director.md` | `script` | Transcript mining, ranking, standalone validation |
| Scene Director | `pipelines/clip-factory/scene-director.md` | `scene_plan` | Platform framing, safe zones, crop-viability planning |
| Asset Director | `pipelines/clip-factory/asset-director.md` | `assets` | Shared brand kit, rebased subtitles, batch audio consistency |
| Edit Director | `pipelines/clip-factory/edit-director.md` | `edit` | Hook-first mini-edits, series consistency |
| Compose Director | `pipelines/clip-factory/compose-director.md` | `compose` | Multi-job rendering, batch resilience, per-output verification |
| Publish Director | `pipelines/clip-factory/publish-director.md` | `publish` | Posting order, platform copy, batch cataloging |

### Podcast Repurpose Pipeline (`pipelines/podcast-repurpose/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/podcast-repurpose/executive-producer.md` | `all` | **7-stage serial orchestration, audio preservation gates, clip quality, multi-deliverable** |
| Idea Director | `pipelines/podcast-repurpose/idea-director.md` | `idea` | Deliverable mix by source mode, realistic long-form planning |
| Script Director | `pipelines/podcast-repurpose/script-director.md` | `script` | Diarized transcript truth, highlight ranking, chapter mapping |
| Scene Director | `pipelines/podcast-repurpose/scene-director.md` | `scene_plan` | Source-faithful treatments, audiogram vs quote vs companion planning |
| Asset Director | `pipelines/podcast-repurpose/asset-director.md` | `assets` | Subtitle-first packaging, speaker assets, optional topic art |
| Edit Director | `pipelines/podcast-repurpose/edit-director.md` | `edit` | Hook-led podcast clips, quote hold time, companion simplicity |
| Compose Director | `pipelines/podcast-repurpose/compose-director.md` | `compose` | Audio-first rendering, deliverable prioritization |
| Publish Director | `pipelines/podcast-repurpose/publish-director.md` | `publish` | Episode cross-linking, guest attribution, staggered release logic |

### Cinematic Pipeline (`pipelines/cinematic/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/cinematic/executive-producer.md` | `all` | **7-stage serial orchestration, emotional pacing gates, color consistency, audio dynamics** |
| Idea Director | `pipelines/cinematic/idea-director.md` | `idea` | Emotional arc selection, source truth, delivery-shape planning |
| Script Director | `pipelines/cinematic/script-director.md` | `script` | Beat mapping, dialogue selects, title-card restraint |
| Scene Director | `pipelines/cinematic/scene-director.md` | `scene_plan` | Hero-frame planning, reveal structure, transition limits |
| Asset Director | `pipelines/cinematic/asset-director.md` | `assets` | Source selects, support-insert discipline, music/ambience planning |
| Edit Director | `pipelines/cinematic/edit-director.md` | `edit` | Emotion-first pacing, reveal timing, audio-driven rhythm |
| Compose Director | `pipelines/cinematic/compose-director.md` | `compose` | Grade and mix finishing, frame-treatment judgment |
| Publish Director | `pipelines/cinematic/publish-director.md` | `publish` | Hero vs teaser packaging, poster-frame concepts |

### Animation Pipeline (`pipelines/animation/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/animation/executive-producer.md` | `all` | **8-stage serial orchestration, quality gates, motion consistency, math accuracy checks** |
| **Research Director** | `pipelines/animation/research-director.md` | `research` | **Topic + animation technique research, visual reference scan, mode-informed angles** |
| **Proposal Director** | `pipelines/animation/proposal-director.md` | `proposal` | **Animation mode selection (Manim/Remotion/AI/diagram), reuse strategy, cost estimate, approval gate** |
| Script Director | `pipelines/animation/script-director.md` | `script` | Animation-ready beats, text restraint, research integration, mode-aware writing |
| Scene Director | `pipelines/animation/scene-director.md` | `scene_plan` | Animatic planning, transition systems, tool-path mapping |
| Asset Director | `pipelines/animation/asset-director.md` | `assets` | Deterministic asset choice, reusable motifs, feasibility truth |
| Edit Director | `pipelines/animation/edit-director.md` | `edit` | Hold timing, stagger rules, readable motion planning |
| Compose Director | `pipelines/animation/compose-director.md` | `compose` | Sharp render output, timing integrity, safe-zone checks |
| Publish Director | `pipelines/animation/publish-director.md` | `publish` | Animation-mode packaging, thumbnail-system alignment |

> **Note:** The old `idea-director.md` still exists for reference but is superseded by the research + proposal two-stage flow in v2.0.

### Hybrid Pipeline (`pipelines/hybrid/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/hybrid/executive-producer.md` | `all` | **7-stage serial orchestration, source/support balance gates, overlay density, coherence** |
| Idea Director | `pipelines/hybrid/idea-director.md` | `idea` | Anchor-medium selection, support-layer planning, fallback visibility |
| Script Director | `pipelines/hybrid/script-director.md` | `script` | Source-vs-support beat mapping, dialogue retention, support justification |
| Scene Director | `pipelines/hybrid/scene-director.md` | `scene_plan` | Source-primary layout rules, overlay density control, variant-safe planning |
| Asset Director | `pipelines/hybrid/asset-director.md` | `assets` | Shared support kits, source-vs-generated asset tracking |
| Edit Director | `pipelines/hybrid/edit-director.md` | `edit` | Anchor-cut-first workflow, layered support timing, readable variants |
| Compose Director | `pipelines/hybrid/compose-director.md` | `compose` | Source/support balance checks, variant verification, coherent mix |
| Publish Director | `pipelines/hybrid/publish-director.md` | `publish` | Master-vs-derivative packaging, source-mix metadata |

### Avatar Spokesperson Pipeline (`pipelines/avatar-spokesperson/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/avatar-spokesperson/executive-producer.md` | `all` | **7-stage serial orchestration, lip-sync quality gates, presenter framing, CTA landing** |
| Idea Director | `pipelines/avatar-spokesperson/idea-director.md` | `idea` | Avatar-path classification, CTA scoping, capability truth |
| Script Director | `pipelines/avatar-spokesperson/script-director.md` | `script` | Spoken-copy shaping, scene-safe pacing, text restraint |
| Scene Director | `pipelines/avatar-spokesperson/scene-director.md` | `scene_plan` | Presenter layout, background discipline, variant realism |
| Asset Director | `pipelines/avatar-spokesperson/asset-director.md` | `assets` | Avatar-path locking, narration resolution, minimal support kits |
| Edit Director | `pipelines/avatar-spokesperson/edit-director.md` | `edit` | Presenter-first cut planning, overlay timing, CTA landing |
| Compose Director | `pipelines/avatar-spokesperson/compose-director.md` | `compose` | Lip-sync verification, subtitle-safe framing, clean render checks |
| Publish Director | `pipelines/avatar-spokesperson/publish-director.md` | `publish` | Audience-led packaging, presenter-first thumbnail concepts |

### Localization Dub Pipeline (`pipelines/localization-dub/`) — v2.0

| Skill | File | Stage | Key Capabilities |
|-------|------|-------|-----------------|
| **Executive Producer** | `pipelines/localization-dub/executive-producer.md` | `all` | **7-stage serial orchestration, translation accuracy gates, timing preservation, per-locale QA** |
| Idea Director | `pipelines/localization-dub/idea-director.md` | `idea` | Scope definition, locale planning, glossary and review capture |
| Script Director | `pipelines/localization-dub/script-director.md` | `script` | Transcript truth, translated script packaging, term preservation |
| Scene Director | `pipelines/localization-dub/scene-director.md` | `scene_plan` | Dub-mode selection, timing-risk mapping, on-screen text planning |
| Asset Director | `pipelines/localization-dub/asset-director.md` | `assets` | Subtitle-first localization kit, dubbed audio generation, optional lip sync |
| Edit Director | `pipelines/localization-dub/edit-director.md` | `edit` | Locale-specific timelines, coverage planning, timing adjustments |
| Compose Director | `pipelines/localization-dub/compose-director.md` | `compose` | Per-locale rendering, subtitle-fit checks, output labeling |
| Publish Director | `pipelines/localization-dub/publish-director.md` | `publish` | Locale packaging, metadata precision, QA-note retention |

## Meta Skills

Cross-cutting skills that apply to all pipelines:

| Skill | File | Purpose |
|-------|------|---------|
| Onboarding | `meta/onboarding.md` | First-interaction greeting, capability discovery, starter prompts |
| Reviewer | `meta/reviewer.md` | Self-review protocol after every stage |
| Checkpoint Protocol | `meta/checkpoint-protocol.md` | When/how to checkpoint and request human approval |
| Skill Creator | `meta/skill-creator.md` | Dynamically create new skills during pipeline runs |

## Style Playbooks

Style playbooks (`styles/*.yaml`) define visual language, typography, motion, audio, and asset generation constraints. They are validated against `schemas/styles/playbook.schema.json`.

| Playbook | Category | Mood | Best For |
|----------|----------|------|----------|
| `clean-professional` | motion-graphics | polished, trustworthy | Corporate, educational, SaaS |
| `flat-motion-graphics` | motion-graphics | energetic, bold | Social media, TikTok, startups |
| `minimalist-diagram` | whiteboard | focused, technical | Technical deep-dives, architecture |

Load via `styles/playbook_loader.py`: `load_playbook("clean-professional")`

## Installed Agent Skills (Layer 3)

All agent skills live in `.agents/skills/` and are managed via `npx skills add`.
Claude Code accesses them via symlinks in `.claude/skills/`.

| Category | Installed Skills | Source |
|----------|-----------------|--------|
| **Video Composition** | `remotion-best-practices`, `remotion` | `remotion-dev/skills`, `digitalsamba/claude-code-video-toolkit` |
| **Video Processing** | `ffmpeg`, `video_toolkit` | `digitalsamba/claude-code-video-toolkit` |
| **TTS & Audio** | `text-to-speech`, `speech-to-text`, `music`, `sound-effects`, `elevenlabs`, `agents`, `setup-api-key` | `elevenlabs/skills`, `digitalsamba/claude-code-video-toolkit` |
| **Image Generation** | `flux-best-practices`, `bfl-api`, `grok-media` | `black-forest-labs/skills`, local OpenMontage skill |
| **Math Animation** | `manimce-best-practices`, `manimgl-best-practices`, `manim-composer` | `adithya-s-k/manim_skill` |
| **3D Graphics** | `threejs-animation`, `threejs-fundamentals`, `threejs-geometry`, `threejs-interaction`, `threejs-lighting`, `threejs-loaders`, `threejs-materials`, `threejs-postprocessing`, `threejs-shaders`, `threejs-textures` | `cloudai-x/threejs-skills` |
| **Diagrams** | `beautiful-mermaid`, `d3-viz` | `intellectronica/agent-skills`, `davila7/claude-code-templates` |
| **Animation** | `framer-motion`, `lottie-bodymovin` | `pproenca/dot-skills`, `dylantarre/animation-principles` |
| **Design** | `tailwind-design-system`, `web-design-guidelines`, `vercel-react-best-practices`, `vercel-composition-patterns` | `wshobson/agents`, `vercel-labs/agent-skills` |
| **AI Video (HeyGen)** | `heygen`, `avatar-video`, `create-video`, `faceswap`, `ai-video-gen`, `video-download`, `video-edit`, `video-translate`, `video-understand`, `visual-style` | `heygen-com/skills` |
| **AI Video (Premium)** | `seedance-2-0` — preferred premium default (cinematic, trailer, multi-shot, lip-sync, synced audio); accessed via `seedance_video` (fal.ai) or `heygen_video` Avatar Shots | Local OpenMontage skill |
| **Infrastructure** | `acestep`, `ltx2`, `playwright-recording` | `digitalsamba/claude-code-video-toolkit` |
