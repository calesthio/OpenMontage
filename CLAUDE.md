# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Two modes — know which one you're in

This repo is used two completely different ways. Decide which before acting:

1. **Operating the product (making a video).** The user wants a trailer, explainer, clip,
   animation, etc. This goes through the agent-first pipeline system.
   → **MANDATORY: Read [`AGENT_GUIDE.md`](AGENT_GUIDE.md) first.** It contains routing rules
   (onboarding, reference-video entry point, Rule Zero) that determine your first action.
   Skipping it WILL cause the wrong action. Do not improvise scripts to call tools directly.

2. **Developing the codebase (writing tools, pipelines, skills, fixing the framework).**
   That's what the rest of this file covers. `AGENT_GUIDE.md` is about *running* the product,
   not *building* it — the developer commands below are not in that guide.

When in doubt about a production request, default to mode 1 and read `AGENT_GUIDE.md`.

## Architecture in one paragraph

OpenMontage is **instruction-driven**: the AI agent is the orchestrator, and Python exists
only for tools and persistence. There is **no Python orchestrator, reviewer, or stage handler** —
orchestration, creative decisions, review, and stage transitions all live in instructions
(YAML pipeline manifests + markdown skills) that the agent reads and follows. The production
state machine is `idea → script → scene_plan → assets → edit → compose → publish`; each stage
emits one canonical JSON artifact (validated against `schemas/artifacts/`) that becomes the
contract for the next stage. See [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md) and
`docs/ARCHITECTURE.md` for the full picture.

### Three knowledge layers (don't conflate them)

- **Layer 1 — `tools/`** (Python `BaseTool` subclasses): *what* exists, availability, cost, runtime.
  Discovered at runtime through `tools/tool_registry.py` — never hardcode tool lists.
- **Layer 2 — `skills/`** (markdown): *how OpenMontage* uses those tools in a pipeline stage
  (`skills/pipelines/<pipeline>/<stage>-director.md`) and meta policy (`skills/meta/`).
- **Layer 3 — `.agents/skills/`** (markdown): *how the vendor technology works* — provider-specific
  prompting and parameters. Each tool's `agent_skills[]` field bridges Layer 1 → Layer 3.

### Things that bite if you don't know them

- **Tool classes use PascalCase with NO `Tool` suffix** (`VideoCompose`, not `VideoComposeTool`).
  Verify with `grep "^class " tools/<path>.py`.
- **Tools are invoked via `.execute(params_dict)`**, returning a `ToolResult` (`.success`,
  `.data`, `.error`) — not `.run()`.
- **Selector pattern**: `tts_selector` / `image_selector` / `video_selector` auto-discover
  providers from the registry by capability. Add a provider tool and it's available through the
  selector with no selector code change.
- **`video_compose` has three render runtimes** — FFmpeg, Remotion, HyperFrames — chosen at
  proposal and locked in `edit_decisions.render_runtime`. Routing is automatic on that field;
  silent runtime swaps are forbidden (see `AGENT_GUIDE.md`).
- **`projects/`, `pipelines/`, and `music_library/` are gitignored** — all generated assets and
  checkpoints are regenerable; never commit them.

## Developer commands

```bash
make setup            # full install: pip deps + remotion-composer npm + Piper TTS + HyperFrames cache-warm
make install          # python deps only (requirements.txt)
make install-dev      # adds pytest + pytest-asyncio
make install-gpu      # local-GPU video/image generation deps

make test             # python -m pytest tests/ -v   (whole suite)
make test-contracts   # contract tests only — the stage-artifact contracts
make lint             # py_compile sanity check on core framework files
make clean            # remove __pycache__ / *.pyc

make preflight        # dump registry provider_menu() — what's configured/available
make demo             # render zero-key Remotion demo videos (no API keys needed)
make hyperframes-doctor   # validate the HyperFrames runtime (node/ffmpeg/npx)
```

Run a single test:

```bash
python -m pytest tests/contracts/test_phase1_contracts.py -v          # one file
python -m pytest tests/contracts/test_phase1_contracts.py::test_name -v # one test
python -m pytest tests/ -k "runtime_presentation" -v                   # by keyword
```

Test layout: `tests/contracts/` (stage-artifact contracts), `tests/tools/`, `tests/pipelines/`,
`tests/styles/`, `tests/eval/`, `tests/qa/` (per-tool output inspection).

## Extending the system

- **New tool**: inherit `tools/base_tool.py` `BaseTool`, place it in the right capability package
  (`tools/audio/`, `tools/video/`, `tools/analysis/`, …), set every contract field
  (`capability`, `provider`, `supports`, `fallback_tools`, `agent_skills`, …), implement
  `execute()` → `ToolResult`. Discovery is automatic via the registry; prefer the
  selector-plus-provider pattern. Full checklist in `PROJECT_CONTEXT.md`.
- **New pipeline**: add a YAML manifest in `pipeline_defs/` (validated by
  `schemas/pipelines/pipeline_manifest.schema.json`) plus a director skill per stage under
  `skills/pipelines/<name>/`, then contract tests in `tests/contracts/`.
- **All code, comments, commits, and docs are English-only** (per the engineering standards).
  User-facing video/UI strings are the only exception.
