# OpenMontage Factory — current state

Generated during KILO_CODE_YOUTUBE_FACTORY_MASTER.md bootstrap (2026-10-17).

## Repository
- Root: `/workspaces/OpenMontage`
- Branch: `factory/business-documentary-pilot`
- Git status: clean (no uncommitted changes)
- Last commit: `21903ee feat(milestone-k1): Kaggle bridge code (test-first) + live hello CPU job`

## Languages and runtimes
- Python 3.14.2
- Node.js v24.21.0
- ffmpeg 6.1.1 / ffprobe 6.1.1 (available)

## Tool inventory (from registry scan)
- `tools/tool_registry.py` — registry with provider_menu_summary, capability_catalog, provider_catalog
- `tools/qa/qc.py` — technical QA (ffprobe, blackdetect, freezedetect, silencedetect, ebur128, SRT sanity)
- Multiple tool families under `tools/`: audio, video, subtitle, avatar, analysis, capture, enhancement, graphics, publishers

## Pipelines
- `pipeline_defs/` — YAML manifests for animated-explainer, talking-head, screen-demo, clip-factory, podcast-repurpose, cinematic, animation, character-animation, hybrid, avatar-spokesperson, localization-dub, framework-smoke

## Skills (project `.kilo/skills/`)
- Existing: audio-edit, cutting-rhythm, edl-edit, systematic-debugging, test-driven-development, verification-before-completion, yt-chapters, yt-package, yt-script, yt-seo
- Added: kilo-self-improvement, youtube-factory-orchestrator, youtube-research-and-scripting, licensed-footage-audit, video-pipeline-ffmpeg, video-rendering-remotion, youtube-quality-gate, youtube-publishing-analytics, youtube-factory-self-improvement

## Agents (project `.kilo/agents/`)
- editor, qa-reviewer, evidence-checker, footage-sc

## Config
- No `kilo.json` / `kilo.jsonc` in repository root
- `config/qc_thresholds.json` — QA thresholds
- `.env.example` — env variable template (no secrets committed)

## Tests
- `tests/` — backlot, contracts, eval, factory, fixtures, lib, pipelines, qa, styles, tools subdirectories
- `requirements.txt`, `requirements-dev.txt`, `requirements-gpu.txt` — dependency files
- `Makefile` — build/test targets

## Status summary
| Area | implemented | partial | missing | broken | not verified |
|---|---|---|---|---|---|
| Tool registry | yes | | | | |
| QA tooling | yes | | | | |
| Pipeline manifests | yes | | | | |
| Project Skills (9 new) | yes | | | | |
| Global AGENTS.md merge | yes | | | | |
| docs/agent-improvement | yes | | | | |
| docs/architecture | yes | | | | |
| templates | yes | | | | |
| First vertical slice (MP4 render) | | | yes | | |
| YouTube publishing integration | | | yes | | |
