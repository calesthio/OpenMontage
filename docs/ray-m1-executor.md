# Ray M1 Hosted Executor Skeleton

Status: M1 implementation. The executor now enforces the hosted guardrails in
code and runs planning stages through the loaded pipeline manifest, stage
director skills, artifact schemas, and checkpoint writer.

## Goal

Hosted Ray must be a thin transport in front of OpenMontage. The worker executes
the same pipeline contract an interactive agent follows:

1. Load `pipeline_defs/<pipeline>.yaml`.
2. Resolve next stage through `lib.checkpoint.get_next_stage`.
3. Read the stage director skill from `skills/pipelines/<pipeline>/`.
4. Read `skills/meta/checkpoint-protocol.md` and `skills/meta/reviewer.md`.
5. Discover tools through `tools.tool_registry.registry`.
6. Let the director LLM call only tools declared for that stage.
7. Validate the canonical artifact and write checkpoints through `lib.checkpoint`.

No creative planning prompt belongs in the hosted wrapper.

## Module Layout

- `hosted_pipeline/executor.py`
  - `StageExecutor`: pipeline-agnostic stage runner with enforced budgets,
    failed checkpoints, schema repair loop, final checkpoint writes, and
    idempotency ledger.
  - `StageRunRequest`: project, pipeline, stage, caps, limits.
  - `LoopLimits`: max LLM iterations, max tool calls, wall-clock timeout.
  - `BudgetCaps`: total, LLM, media, and sample caps.
  - `paid_call_idempotency_key`: `project/stage/scene/attempt/tool/hash`.
- `hosted_pipeline/director_client.py`
  - OpenRouter/OpenAI chat-completions adapter for director model calls.
- `hosted_pipeline/worker.py`
  - Fly worker process entrypoint.
  - Boots provider preflight and stays ready for M1 queue wiring.
- `scripts/remotion_smoke_render.py`
  - M0 render smoke with progress watchdog.

## Checkpoint Flow

For every stage:

1. `init_project(project_id, title, pipeline_type)` ensures canonical workspace.
2. `write_checkpoint(..., status="in_progress")` records:
   - `repo_sha`
   - executor name
   - loop limits
   - budget caps
3. Director loop runs.
4. On success, the canonical artifact is validated by `write_checkpoint`.
5. If `human_approval_default=true`, checkpoint is `awaiting_human`.
6. If blocked, checkpoint is `failed` with a structured blocker.

Gated stages are never marked `completed` without `human_approved=True`.

## Tool-Call Loop Guards

Each stage has hard limits:

- `RAY_STAGE_MAX_LLM_ITERATIONS`, default `8`
- `RAY_STAGE_MAX_TOOL_CALLS`, default `24`
- `RAY_STAGE_WALL_CLOCK_TIMEOUT_SECONDS`, default `900`

Every paid provider call receives an idempotency key:

```text
<project_id>:<stage>:<scene_id|stage>:attempt-<n>:<tool_name>:<args_sha>
```

M1 persists those keys before paid tool execution, then reconciles provider
output. A resumed job reuses the recorded result or blocks on unsafe pending /
failed ledger entries; it does not buy the same clip twice.

## M1 Signoff Enforcement Gates

These are now code-enforced, not metadata-only.

1. Every guard trip writes a `failed` checkpoint. No loop-limit, timeout,
   schema, provider, or runtime failure may escape as an uncaught exception.
2. Budget caps block before provider calls. The executor must read accumulated
   `cost_log.json` state and refuse a call that would exceed total, LLM, media,
   or sample cap.
3. The executor owns an idempotency ledger. Before any paid tool executes, the
   executor checks the key; on hit it returns the cached result without calling
   the provider.
4. `final_artifact` responses are schema-validated and written as the canonical
   artifact in a completed or awaiting-human checkpoint according to the
   manifest gate.
5. Skill files are read from the pinned job SHA. If the hosted runtime cannot
   identify a pinned SHA, production execution is blocked with
   `skills_not_pinned`.

Hosted research now exposes a no-key `web_search` registry tool. The executor
marks research as `web_search` only when that tool is discovered and available;
otherwise directors must mark `metadata.research_execution_mode` as
`recorded_only_no_web_search_tool` and must not claim live searches ran.

## Failure Policy

- Missing director model: fail closed with `director_model_client_not_wired`.
- Unknown pipeline/stage: fail closed through manifest/checkpoint validation.
- Tool unavailable: structured blocker, no substitute provider.
- Runtime unavailable: structured blocker, no render-runtime swap.
- Schema invalid after repair: failed checkpoint.
- Budget cap exceeded: blocked before provider call.
- Worker restart: resume from checkpoints and idempotency records.

## Fly State Model

M0 uses one 8GB Fly machine so `/data` is machine-local and internally
consistent. Before reintroducing separate MCP and worker machines, cross-process
state must move through R2 or another shared durable store; Fly volumes are
per-machine and cannot be treated as shared.

Before M2, add worker autostop/autostart policy for render workers so idle
8GB machines do not sit running between generation jobs.

## M1 Demo Scope

The first demo is the saree job through:

```text
research -> proposal -> script -> scene_plan
```

No paid media generation in M1. The demo packet must include:

- project `project.json`
- all stage checkpoints
- canonical artifacts for completed/awaiting-human stages
- `decision_log.json` where applicable
- repo SHA in every checkpoint metadata block
- stage schema references used for validation
