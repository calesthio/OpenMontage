# OpenMontage - Shared Project Context

This is the single source of truth for project architecture and conventions. All platform-specific agent files (CLAUDE.md, CODEX.md, CURSOR.md, COPILOT.md) should point here instead of duplicating this content.

## Identity

OpenMontage is an open-source, AI-orchestrated video production platform.

## Architecture: Instruction-Driven (Agent-First)

The AI agent IS the intelligence. Python exists only for tools and persistence. Everything else — orchestration, creative decisions, review, stage transitions — lives in instructions (YAML manifests + markdown skills) the agent follows.

```
Agent reads pipeline manifest (YAML) → reads stage director skill (MD)
→ uses tools (Python BaseTool) → self-reviews (meta skill)
→ checkpoints (Python utility) → presents to human for approval
```

**No Python orchestrator, no Python reviewer, no Python handlers.** The agent drives the pipeline.

## Source of Truth

- **Agent guide & contract:** `AGENT_GUIDE.md` (tool inventory, pipeline selection, stage agents, protocols)
- **Skill index:** `skills/INDEX.md`
- **Tool registry:** `tools/tool_registry.py`
- **Pipeline manifests:** `pipeline_defs/`
- **Artifact schemas:** `schemas/artifacts/`
- **Style playbooks:** `styles/*.yaml` (schema: `schemas/styles/playbook.schema.json`)
- **Stage director skills:** `skills/pipelines/<pipeline>/<stage>-director.md`
- **Meta skills:** `skills/meta/*.md` (reviewer, checkpoint-protocol, skill-creator)
- **Architecture deep-dive:** `docs/ARCHITECTURE.md`

## Knowledge Architecture (3 Layers)

```
Layer 1: tools/tool_registry.py     → "What tools exist" (runtime capabilities, status, cost)
Layer 2: skills/                    → "How OpenMontage uses them" (project conventions)
Layer 3: .agents/skills/            → "How the technology works" (generic API rules, skills.sh)
```

Each tool's `agent_skills[]` field bridges Layer 1 → Layer 3. See `skills/INDEX.md` for the full mapping.

## Key Patterns

- **Pipeline state machine:** `idea -> script -> scene_plan -> assets -> edit -> compose -> publish`
- **Instruction-driven stages:** Each stage has a director skill (MD) that teaches the agent HOW
- **Pipeline manifests:** Declarative YAML defining stages, skills, tools, review focus, approval gates
- **Capability-first tool design:** Each major family should expose a selector tool plus explicit provider tools
  - Example: `tts_selector` + `elevenlabs_tts` / `google_tts` / `openai_tts` / `piper_tts`
  - Example: `video_selector` + `heygen_video` / `heygen_browser_video` / `google_flow_video` / `magic_hour_video` / `wan_video` / etc.
- **Browser subscription tools:** `heygen_browser_video` and `google_flow_video` use Playwright to automate the provider web UI, consuming subscription plan credits instead of API credits. Session cookies are persisted at `~/.openmontage/`.
- **Resilient execution via `execute_safe()`:** All `BaseTool` subclasses inherit `execute_safe(inputs)`. It enforces a wall-clock timeout of `max(30s, min(estimate_runtime × 2, 600s))` and auto-escalates to the first available fallback tool on timeout. Always prefer `execute_safe()` for cloud generation calls.
- **Style playbooks:** YAML defining visual language, typography, motion, audio, asset generation constraints
- **Artifacts are canonical:** `brief`, `script`, `scene_plan`, `asset_manifest`, `edit_decisions`, `render_report`, `publish_log`
- **Every tool inherits from `tools/base_tool.py`** (ToolContract)
- **Checkpoint policy** lives in pipeline manifest (`human_approval_default` per stage) + `skills/meta/checkpoint-protocol.md`
- **Reviewer** is a meta skill (`skills/meta/reviewer.md`), advisory, max 2 rounds
- **Cost tracker** (`tools/cost_tracker.py`) manages budget: estimate -> reserve -> reconcile
- **Canonical artifacts** validated against JSON schemas in `schemas/artifacts/`

## Key Files

| File | Purpose |
|------|---------|
| `config.yaml` | Global configuration |
| `lib/config_model.py` | Runtime config loader (Pydantic) |
| `lib/checkpoint.py` | Checkpoint writer/reader |
| `lib/pipeline_loader.py` | Pipeline manifest loader + helpers |
| `lib/media_profiles.py` | Platform-specific render profiles |
| `styles/playbook_loader.py` | Style playbook loader + validator + design intelligence (color/type/a11y) |
| `tools/base_tool.py` | ToolContract base class |
| `tools/tool_registry.py` | Tool discovery and reporting |
| `tools/cost_tracker.py` | Budget governance |
| `tools/video/video_stitch.py` | Multi-clip assembly (stitch, spatial, validate, preview) |
| `remotion-composer/src/components/` | 8 Remotion components (TextCard, StatCard, ProgressBar, CalloutBox, ComparisonCard + charts/) |
| `schemas/styles/playbook.schema.json` | Playbook schema v2 with design tokens (chart_palette, scale_system, weight_matrix, color_rules) |
| `tests/qa/` | Quality validation test scripts for tool-by-tool output inspection |

## Available Pipelines

| Pipeline | Manifest | Type |
|----------|----------|------|
| `talking-head` | `pipeline_defs/talking-head.yaml` | Footage-based |
| `animated-explainer` | `pipeline_defs/animated-explainer.yaml` | AI-generated |
| `screen-demo` | `pipeline_defs/screen-demo.yaml` | Screen-recording |
| `clip-factory` | `pipeline_defs/clip-factory.yaml` | Short-form batch extraction |
| `podcast-repurpose` | `pipeline_defs/podcast-repurpose.yaml` | Podcast repurposing |
| `cinematic` | `pipeline_defs/cinematic.yaml` | Cinematic edit |
| `animation` | `pipeline_defs/animation.yaml` | Animation-first |
| `hybrid` | `pipeline_defs/hybrid.yaml` | Source-plus-support hybrid |
| `avatar-spokesperson` | `pipeline_defs/avatar-spokesperson.yaml` | Avatar presenter |
| `localization-dub` | `pipeline_defs/localization-dub.yaml` | Localization and dubbing |
| `framework-smoke` | `pipeline_defs/framework-smoke.yaml` | Test harness |

## When Building New Pipelines

1. Create a YAML manifest in `pipeline_defs/` (validated by `pipeline_manifest.schema.json`)
2. Create stage director skills in `skills/pipelines/<pipeline-name>/` (7 skills: idea through publish)
3. Reference meta skills (reviewer, checkpoint-protocol) in the manifest
4. Add compatible playbooks to the manifest
5. Add contract tests in `tests/contracts/`

## When Building New Tools

1. Inherit from `tools/base_tool.py` `BaseTool`
2. Put the tool in the correct capability package (`tools/audio/`, `tools/video/`, `tools/enhancement/`, `tools/analysis/`, `tools/graphics/`, `tools/avatar/`, `tools/subtitle/`)
3. Prefer the selector-plus-provider pattern:
   - one capability router tool for agent convenience
   - one concrete tool per real provider/runtime path
4. Set all contract fields (name, version, tier, capability, provider, supports, fallback_tools, agent_skills, etc.)
5. Implement `execute()` returning a `ToolResult`
6. Override `estimate_runtime(inputs)` for any cloud/long-running tool — this drives the `execute_safe()` timeout budget
7. Let discovery happen through `tools/tool_registry.py`; do not depend on ad hoc imports
8. Add a JSON schema in `schemas/tools/` if the tool has complex I/O
9. Add tests only after the runtime path is correct

### Browser tool pattern (Playwright)

For tools that automate a web UI (subscription-based services):
- Set `runtime = ToolRuntime.HYBRID`
- Add `"cmd:playwright"` and `"env:SERVICE_EMAIL"` to `dependencies`
- Persist session cookies to `~/.openmontage/<service>_session.json`
- Handle first-run login vs. session-reuse separately
- Declare an API-based fallback in `fallback_tools` for when browser automation fails

