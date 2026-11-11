# OpenMontage - Agent Guide

Start here. This is the operating contract for OpenMontage: the rules that bind every session, and the map of what to read when a task needs more.

For architecture, key files, and conventions see [`PROJECT_CONTEXT.md`](PROJECT_CONTEXT.md).

## How To Use This Guide

This file is read before every reply, so it is kept short: it states every binding rule, and it routes. The procedures behind the rules live in five section files. **Read a section in full before the step that needs it** — a rule you have only seen summarised here is not one you can follow yet.

| Before you… | Read in full |
|---|---|
| run preflight, present the capability menu, choose tools, or plan anything whose promise depends on motion | [`docs/agent-guide/preflight.md`](docs/agent-guide/preflight.md) — Mandatory Preflight, Provider Menu, Setup Offer Protocol, Composition Runtimes, Motion-Required Requests, Capability Discovery, Tool Families |
| reach the proposal or idea stage, or change a provider, model, runtime, voice, music or composition choice mid-run | [`docs/agent-guide/decisions.md`](docs/agent-guide/decisions.md) — the Decision Communication Contract with every procedure |
| present concepts, the production plan, the music plan or a style playbook | [`docs/agent-guide/planning.md`](docs/agent-guide/planning.md) — Planning Protocol, Music Plan, Music Library, Style Playbooks, Ink Theater |
| create a project, write an artifact or a checkpoint, or resume a run | [`docs/agent-guide/workspace-and-contracts.md`](docs/agent-guide/workspace-and-contracts.md) — project layout, stage artifacts, primary files, manifest and tool rules |
| call a generation tool, or look for the skill that covers a task | [`docs/agent-guide/layers.md`](docs/agent-guide/layers.md) — the three layers, Layer 3 skills by category, quick lookup |

Not producing a video — a question, a code change, a review? This file is enough.

## First Interaction — Onboarding

When the user's first message is vague, exploratory, or asks what you can do ("make me a video", "what can you do?", "help me create something", "I want to make content"), read the onboarding skill **before** doing anything else:

**Read:** `skills/meta/onboarding.md`

This skill teaches you to run discovery, classify the user's setup, present capabilities in plain language, and offer starter prompts tailored to their available tools. The goal: get the user from "curious" to "making a video" in under 60 seconds.

**Skip onboarding** when the user arrives with a specific, actionable request (e.g., "Make a 60-second explainer about black holes"). Go directly to Rule Zero.

## Reference Video Entry Point

When the user provides a **video URL or local video file as inspiration** — for example:

- "Can you make a video like this?"
- "I love this YouTube Short. Make me something similar."
- "Use this Reel as a reference."

— do **not** treat this as a generic web-search or prompt-writing request.

This is a first-class workflow in OpenMontage.

### Required behavior

1. **Read:** `skills/meta/video-reference-analyst.md`
2. **Run the reference analysis workflow** using the local analysis tools (`video_analyzer`, transcript extraction, scene detection, frame sampling)
3. **Produce a grounded summary** of what the reference is doing:
   - content
   - pacing
   - structure
   - style
   - what makes it work
4. **Then** run normal capability audit and pipeline selection
5. Present **2-3 differentiated concepts** for the user's version — not a carbon copy

### Important distinction

- **Reference-driven request:** "make me something like this" -> use `video-reference-analyst.md`
- **Source-footage request:** "edit this footage" / "cut this into clips" -> use `source_media_review` and the appropriate footage-led pipeline

If a model misses this distinction, it will often fall back to plain search + guesswork. That is incorrect for OpenMontage.

## Rule Zero — All Production Goes Through a Pipeline

**Every video production request MUST go through the pipeline system. No exceptions.**

When the user asks to make, create, produce, or generate any video content — a trailer, explainer, clip, animation, or any other video — the agent must:

1. **Identify the pipeline.** Match the request to one of the pipelines in `pipeline_defs/`. If unclear, ask the user.
2. **Read the pipeline manifest.** `pipeline_defs/<pipeline>.yaml` — know the stages, tools, and quality gates.
3. **Run preflight.** Discover available tools via the registry. Present the capability menu.
4. **Execute stage by stage.** For EACH stage, read the stage director skill (`skills/pipelines/<pipeline>/<stage>-director.md`) BEFORE doing any work in that stage.
5. **Read Layer 3 skills before calling tools.** Before using any tool with an `agent_skills` field, read the referenced skill in `.agents/skills/`. These contain provider-specific prompting guidance, parameter optimization, and quality techniques that dramatically improve output.

**Do NOT:**
- Write ad-hoc Python scripts to call tools directly
- Skip the pipeline and go straight to API calls
- Generate assets without reading the stage director skill first
- Use a tool without checking its Layer 3 skill for prompting guidance
- Bypass preflight, checkpoints, or review

The intelligence is in the skills, not in improvised code. An agent that reads the director skills and Layer 3 knowledge will produce significantly better output than one that calls tools directly with generic prompts.

## What OpenMontage Is

OpenMontage is an instruction-driven video production system. The AI agent IS the intelligence — it reads instructions (pipeline manifests + stage director skills + meta skills) and drives the pipeline using tools.

```
Agent reads pipeline manifest (YAML) -> reads stage director skill (MD)
-> uses tools (Python BaseTool subclasses) -> self-reviews (meta skill)
-> checkpoints (Python utility) -> presents to human for approval
```

**Python = tools + persistence.** No orchestration logic, creative decisions, review logic, or checkpoint policy in Python code. The agent makes those decisions guided by instructions.

Core loop:

1. Select a pipeline.
2. Run preflight.
3. Discover real tools from the registry.
4. Present the user with concepts, tool plan, production plan, and cost.
5. Execute stage by stage with checkpoints.

## Decision Communication Contract

For any meaningful production decision, the agent must communicate the decision before acting. The user should never have to infer which provider, model, or render path was chosen after the fact.

**Read [`docs/agent-guide/decisions.md`](docs/agent-guide/decisions.md) in full before the proposal or idea stage and before changing any choice mid-run.** The rules, in brief:

### Announce Before Execution

Before any paid or consequential generation call, state:

- the exact tool name,
- the provider,
- the model or provider variant,
- the reason it was chosen,
- whether it is a sample or a batch run.

### Ask Before Major Changes

The agent must ask the user before changing any major production choice, including:

- switching provider,
- switching model family or provider variant,
- switching from video-led to still-led treatment,
- switching composition engine when that changes the output character,
- dropping narration, music, or other approved creative elements,
- changing from sample mode to batch mode.

Minor prompt refinements inside an already approved provider/model path do not require separate approval unless they materially change the creative direction.

### Re-log Changed Decisions (Binding)

The `decision_log` is the board's Decisions rail and the run's audit trail. It is **append-only history, not a scratchpad.** When a choice you already logged changes mid-run, you MUST **append a new `decision_log` entry** for the new choice, reusing the **same `category` AND the same `subject`** — never silently mutate the old one or reword the subject. The checkpoint writer enforces it: a re-used `decision_id` whose `selected` changed is rejected. What to put in the new entry and why the pair is the key: `docs/agent-guide/decisions.md`.

### Present Both Composition Runtimes (HARD RULE)

When both Remotion and HyperFrames are available on the machine (check `video_compose.get_info()["render_engines"]`), the agent **MUST present both options to the user** before locking `render_runtime` at the proposal stage. The agent MAY recommend one with rationale — but silently picking a "default" is forbidden even when the pipeline manifest or a director skill suggests one.

What the presentation must include for each runtime, how to record it (`render_runtime_selection` with BOTH runtimes in `options_considered`), and the exception when only one runtime is installed are in `docs/agent-guide/decisions.md`. This rule applies to every pipeline that invokes `video_compose`.

### Composition Authoring Mode — Templated vs Atelier

Orthogonal to *runtime* is *authoring mode*: **how** the composition is built. Present it as its own proposal decision and log it in `decision_log` (`category: "composition_mode"`). **Default to atelier for hero work**, and before building route through **`skills/meta/taste-direction.md`**, then **`skills/meta/bespoke-composition.md`**. Definitions, the off-limits list and the cost tradeoff: `docs/agent-guide/decisions.md`.

### Escalate Blockers Explicitly

When a blocker occurs, the agent must surface it immediately using this structure:

1. What was attempted
2. What failed
3. Whether the issue is auth, provider access, tool bug, or prompt/design quality
4. What options exist next
5. Which option the agent recommends, with reasoning

Do not continue with a substitute path until the user approves.

### Recommendation Style

When asking the user to choose, do not just list options. The agent should:

- provide the shortlist,
- explain the tradeoffs briefly,
- recommend one option,
- wait for approval before proceeding.

### No Unilateral Substitutions

If the approved path is blocked, the agent may investigate and prepare alternatives, but may not execute those alternatives without user approval.

This applies especially to:

- provider swaps,
- model swaps,
- fallback tools,
- prompt-only substitutes for reference-driven generation,
- still-image animatics in place of true motion.

## Orchestrator

The agent itself orchestrates the production state machine:

`research -> proposal -> script -> scene_plan -> assets -> edit -> compose`

The agent:

1. Reads the pipeline manifest (`pipeline_defs/*.yaml`) to know the process
2. Calls `checkpoint.get_next_stage(PROJECTS_DIR, project_id, pipeline_type)` to find where to resume, and `checkpoint.get_stale_stages(...)` to see whether an earlier stage was re-run after later ones finished
3. Reads the stage's director skill (`skills/pipelines/<pipeline>/<stage>-director.md`) to know HOW
4. Uses tools (`tools/`) for concrete capabilities
5. Self-reviews using the reviewer meta skill (`skills/meta/reviewer.md`)
6. Checkpoints via the checkpoint protocol (`skills/meta/checkpoint-protocol.md`)
7. Presents to human for approval when `human_approval_default: true`

Infrastructure files:

- `lib/checkpoint.py` — read/write checkpoints, stage validation
- `tools/cost_tracker.py` — budget governance
- `lib/pipeline_loader.py` — manifest loading and helpers

## Project Directory Convention

Every production run creates a project workspace under `projects/` (gitignored): `projects/<project-name>/` with `artifacts/`, `assets/` (`images/`, `video/`, `audio/`, `music/`) and `renders/`. Use kebab-case derived from the video title. Full layout: `docs/agent-guide/workspace-and-contracts.md`.

At pipeline initialization, before any stage runs:

1. **Initialize the workspace**: `python -c "from lib.checkpoint import init_project; init_project('<project-id>', title='<Title>', pipeline_type='<pipeline>')"` — creates the layout above and writes `project.json` (the marker the Backlot board reads).
2. **Open the board**: run `python -m backlot open <project-id>`. This starts the Backlot server if needed and opens the user's browser at the project's live board. If the command fails, continue the production — the board is an observer, never a blocker. This is the agent's ONLY board duty; the board derives everything else from disk.

All tools and agents must write outputs to these paths — **always pass an explicit `output_path` under `projects/<project-id>/`**. Assets written to the repo root, cwd, or temp dirs are invisible to the user's board and violate the workspace contract.

**This applies to atelier and HyperFrames-skill runs too**: hand-authored compositions still write the canonical artifacts they have (script or beats-plan, scene_plan-equivalent, asset manifest) plus checkpoints into `projects/<project-id>/`. The board is runtime-agnostic; only runs that skip the artifacts get a degraded board.

## Available Pipelines

| Pipeline | Best For | Stability |
|----------|----------|-----------|
| `animated-explainer` | Topic to fully generated explainer | production |
| `talking-head` | Footage-led speaker videos | beta |
| `screen-demo` | Screen recordings and walkthroughs | production |
| `clip-factory` | Many clips from one long source | beta |
| `podcast-repurpose` | Podcast highlights and derivatives | beta |
| `cinematic` | Trailer, teaser, and mood-led edits | production |
| `documentary-montage` | Retrieval-first montage of real footage from free stock and open archives | beta |
| `animation` | Motion-graphics and animation-first videos | production |
| `character-animation` | Local rigged cartoon characters and reusable character acting | beta |
| `hybrid` | Source footage plus support visuals | production |
| `avatar-spokesperson` | Presenter-led avatar or lip-sync videos | production |
| `localization-dub` | Subtitle, dub, and translated variants | beta |
| `framework-smoke` | Test: minimal 2-stage smoke test | test |

> **Beta pipelines** have not been fully audited. They work, but expect rough edges. Mention this when the user selects one.

## Mandatory Preflight

Do this before any creative work. **Use `provider_menu_summary()` first — it's the human-ready rollup.**

```bash
python -c "
from tools.tool_registry import registry
import json
registry.discover()
print(json.dumps(registry.provider_menu_summary(compact=True), indent=2))
"
```

Then present the result to the user as a capability menu — "X of Y configured" per capability, what they can do now, what they could unlock — check the selected manifest's tools against the registry, and report one of `passed`, `degraded`, or `blocked`. Do not start production until the user understands the real capability envelope.

**Read [`docs/agent-guide/preflight.md`](docs/agent-guide/preflight.md) in full before running preflight.** It holds the field guide for the summary, the Provider Menu format, the Setup Offer Protocol, the three composition runtimes inside `video_compose`, Capability Discovery and Tool Families.

### Composition Runtimes (Inside video_compose)

`video_compose` has **three** render engines / runtimes — FFmpeg, Remotion and HyperFrames. They are parallel, not ranked — the choice is made at proposal and locked in `edit_decisions.render_runtime`. `video_compose` routes based on this field; silent runtime swaps are forbidden. How to check which are available and what each requires: `docs/agent-guide/preflight.md`.

### Critical Rule: Motion-Required Requests

For any request where the deliverable inherently depends on motion rather than static coverage, treat motion as a hard requirement. Still-image fallback is forbidden. FFmpeg-only fallback is forbidden when it changes the approved deliverable from motion-led video to still-led video. **Silent runtime swap is forbidden** — surface the blocker, propose options, get user approval, log a `render_runtime_selection` decision, then proceed. The full rule and the Remotion/HyperFrames availability cases: `docs/agent-guide/preflight.md`.

## User-Facing Planning Protocol

Before committing to execution, present:

1. `4-5` concept directions when the brief is still open.
2. Recommended pipeline.
3. Recommended tool path.
4. Alternative tool paths that are actually available.
5. Cost estimate and quality tradeoffs.
6. **Music plan** — mandatory for every pipeline that has audio. See below.
7. Production plan by stage.
8. Approval gate before asset generation.

If a user prefers a specific vendor and that tool is available, surface it directly. Do not hide provider choice.

**Music plan (mandatory).** Surface the music situation to the user at proposal/idea time, checking in this order: `registry.get_by_capability("music_library")` and the `music_library/` folder, `registry.get_by_capability("music_search")`, `registry.get_by_capability("music_generation")`, then a track the user brings. Always present explicit choices, including proceeding without music; if no music source is available, tell the user explicitly.

**Style.** For custom, atelier, brand, launch, or hero work, read `skills/meta/taste-direction.md` before choosing a playbook. A hand-drawn ink doodle brief uses Ink Theater (`skills/creative/ink-theater.md`).

Read [`docs/agent-guide/planning.md`](docs/agent-guide/planning.md) in full before presenting the plan.

## Stage Agents

Each stage produces one canonical artifact that becomes the contract for the next stage. The stage director skill teaches the agent HOW to produce it. The stage → artifact → quality-bar table is in `docs/agent-guide/workspace-and-contracts.md`.

Stage contract rules:

- A completed or awaiting-human checkpoint must include the stage's canonical artifact.
- Canonical artifacts must validate against the JSON schema in `schemas/artifacts/`.
- Non-canonical outputs such as media files belong in stage-specific directories.
- Tools should record seeds/model versions for reproducibility.

## Reviewer Protocol

The reviewer is a meta skill (`skills/meta/reviewer.md`) — advisory, never directly blocks progression.

- Self-review after every stage execution, before checkpointing.
- Load `review_focus` items from the pipeline manifest for the current stage.
- Maximum two review rounds. After that, pass with warnings and move on.
- Findings categorized: critical (must fix), suggestion (should fix), nitpick (nice-to-have).
- Critical findings -> fix and re-review. Suggestions -> note and proceed.
- Check playbook `quality_rules` as constraints, not suggestions.

## Human Checkpoint Protocol

The checkpoint protocol meta skill (`skills/meta/checkpoint-protocol.md`) teaches the agent when to pause:

- Read `human_approval_default` from the pipeline manifest per stage. **The manifest value is binding** — never re-judge it. `lib/checkpoint.py` enforces this: a gated stage cannot be written `completed` without `human_approved=True`.
- Typical gated stages: `idea`/`proposal`, `script`, `scene_plan`, **`assets`** (review the generated assets scene-by-scene — the Backlot board's filmstrip — before compose locks them in), and `publish` where the pipeline has one. Most pipelines auto-proceed on `edit` and `compose`, but not all (documentary-montage gates `edit`) — the manifest you loaded is the only authority.
- When approval is required: write the checkpoint as `awaiting_human`, present artifact summary, review findings, and cost snapshot — then **END YOUR TURN**. Doing further pipeline work in the same response is a gate violation.
- **Approval is per-gate.** An early "go ahead" never covers later gates; explicit full-run pre-authorization must be recorded as a `decision_log` entry (`category: "approval_policy"`) to count.
- Wait for human to approve, request revision, or abort.

## Communication Protocol

Agents coordinate through canonical JSON artifacts, checkpoints, pipeline manifests, and the tool registry. Primary files, pipeline manifest rules and tool rules: `docs/agent-guide/workspace-and-contracts.md`.

Checkpoint rules:

- Checkpoints live at `projects/<project_id>/checkpoint_<stage>.json` (the project workspace — this is what the Backlot board watches).
- `status` may be `completed`, `failed`, `awaiting_human`, or `in_progress`.
- Write an `in_progress` checkpoint on entering each stage; during `assets`/`compose`, refresh `metadata.partial_progress` after each completed scene/asset unit — this powers live progress on the board.
- `completed` and `awaiting_human` checkpoints must include the canonical artifact.
- A gated stage (`human_approval_default: true`) can only be written `completed` with `human_approved=True` — the writer raises a GATE VIOLATION otherwise.
- A `proposal` checkpoint can only be written `completed` when its `proposal_packet.approval.status` is `approved` or `approved_with_changes`; `human_approved=True` alone is not enough. Keep a pending proposal `awaiting_human` and leave `render_runtime` unset until the user approves and chooses a runtime.
- Superseded checkpoints are archived automatically to `projects/<project_id>/history/` — stage re-runs never destroy run history.
- Invalid checkpoints or invalid canonical artifacts are contract violations and should fail fast.
- Pass `review={...}` on every `awaiting_human`/`completed` write. A stage with no review on record is logged, listed by `checkpoint.get_unreviewed_stages(...)`, and marked NO REVIEW on the board.
- Decisions reach the audit trail only through a checkpoint's `decision_log` artifact or `checkpoint.append_decisions(...)`. The log is `projects/<project_id>/decision_log.json` — never hand-write a `decision_log.json` file anywhere.
- Leave `cost_snapshot` out: the writer fills it from the spend the tools reported. Record spend no tool reports (rented GPU time) with `python -m tools.cost_tracker record <project-id> ...`, and the budget the user approved with `python -m tools.cost_tracker budget <project-id> --usd <amount>`.

## Layer Map

OpenMontage has three instruction layers: `tools/` (what exists, what is available, cost, runtime, fallback, related skills), `skills/` (how OpenMontage wants those tools used in pipelines), and `.agents/skills/` (raw vendor or technology knowledge).

Reading order:

1. registry / tool contract — discover what's available
2. relevant pipeline or creative skill (Layer 2) — know HOW to use it in this context
3. underlying vendor skill (Layer 3) — **mandatory before calling any generation tool**

**Layer 3 is not optional.** Every generation tool (video, image, TTS, music) has an `agent_skills` field listing its Layer 3 skills. Read them before writing prompts.

**Prefer skills over source code for tool usage.** Reading the tool source is fair game for debugging, audits, and verifying the governance contract.

Layer 3 skills by category and the quick lookup table: [`docs/agent-guide/layers.md`](docs/agent-guide/layers.md).

## What Not To Do

- **Do not bypass the pipeline.** Never write ad-hoc scripts to call tools directly. All production goes through pipeline stages with director skills. See Rule Zero.
- **Do not call generation tools without reading their Layer 3 skill.** Check the tool's `agent_skills` field, read the referenced skill, then craft your prompts using that guidance.
- **Do not skip stage director skills.** Before executing any pipeline stage, read its director skill. The skill contains the quality bar, the workflow, and the review criteria.
- Do not use deleted legacy names such as `tts_cloud`, `tts_engine`, or `video_gen`.
- Do not hardcode provider names, API key names, or setup URLs. Read them from the registry's `install_instructions` and `dependencies` fields.
- Do not tell a restricted shared-installation user to add credentials manually, create a `.env`, or export a key. Surface the unavailable provider as an administrator setup request and continue only with centrally provisioned capabilities.
- Before offering a direct vendor credential, check the registry for an available wrapper through an already configured provider (for example, a partner model hosted by fal.ai).
- Do not begin asset generation before user approval on the production plan.
- Do not hide degraded paths. Record substitutions and blocked options explicitly.
- Do not present a single unavailable tool in isolation. Always show the full capability picture: "X of Y providers configured for this capability."
- Do not skip the Provider Menu at preflight. The user must see what they have AND what they could unlock.
- Do not change provider, model, or render path without telling the user first and getting approval when the change is material.
