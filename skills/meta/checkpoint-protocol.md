# Checkpoint Protocol — Meta Skill

## When to Use

After completing a stage's work AND passing review. This skill teaches you when and how to checkpoint, and when to ask the human for approval. It replaces the Python `checkpoint_policy.py` with an instruction-driven protocol.

Checkpoints are the save points of a pipeline. They enable resume-from-failure, human oversight, and audit trails.

## Protocol

### Step 1: Check Effective Manifest Policy

Read the current stage's configuration from the pipeline manifest:

```yaml
- name: idea
  checkpoint_required: true      # Must we checkpoint?
  human_approval_default: true   # Must we ask the human?
```

| `checkpoint_required` | effective approval | Action |
|----------------------|------------------------|--------|
| true | true | Checkpoint + present to human for approval |
| true | false | Checkpoint + proceed automatically |
| false | * | Skip checkpoint entirely (rare) |

The default remains binding unless `project.json` selects a named
`approval_profile` declared by this same pipeline manifest. Profiles are
opt-in per project and only override stages listed in their
`stage_overrides`; an unknown profile fails closed. This consolidates reviews
without weakening the default policy for any other run.

### Step 2: Prepare Checkpoint Data

Gather everything needed for the checkpoint:

1. **Stage name** — which stage just completed
2. **Status** — `"completed"` (or `"awaiting_human"` if approval needed)
3. **Artifacts** — the canonical artifact(s) produced by this stage
4. **Metadata** — review findings, cost snapshot, timing info

### Step 3: Write Checkpoint

Call the checkpoint utility:

```python
write_checkpoint(
    pipeline_dir,      # Project working directory
    project_name,      # Project identifier
    stage_name,        # e.g., "idea"
    status,            # "completed" or "awaiting_human"
    artifacts,         # {"brief": {...}} — the stage's output
)
```

The checkpoint utility will:
- Validate the artifact against its schema
- Enforce the approval gate (a gated stage cannot be written `completed` without `human_approved=True`)
- Archive any superseded checkpoint to `projects/<id>/history/` (stage versions and gate transitions are never destroyed)
- Write the checkpoint JSON to disk
- Include timestamp and stage metadata

Canonical location: `projects/<project_id>/checkpoint_<stage>.json` — always
pass the repo's `projects/` directory as `pipeline_dir` (or use
`lib.checkpoint.PROJECTS_DIR`). Always pass `pipeline_type` — gate enforcement
reads the manifest through it.

At pipeline initialization (before any stage), call `init_project()`:

```python
from lib.checkpoint import init_project
init_project("my-project", title="My Project", pipeline_type="cinematic")
```

This creates the canonical directory layout and writes `project.json` — the
marker the Backlot board needs to show the project before its first
checkpoint. Then launch the board: `python -m backlot open my-project`
(non-fatal if unavailable — the board is an observer, never a blocker).

Persist an explicitly selected manifest profile at initialization:

```python
init_project(
    "my-project",
    title="My Project",
    pipeline_type="avatar-spokesperson",
    approval_profile="preview_then_avatar",
)
```

### Step 4: Intra-Stage Checkpointing (Resume Support + Liveness)

**On entering any stage, write an `in_progress` checkpoint first.** This is
what tells the user (via the Backlot board) that the stage is live rather
than stalled — certainty matters more than speed.

Long-running stages (like `assets` or `compose` loops) can fail midway due to API errors, rate limits, or session interruptions. To allow resuming from the exact point of failure (e.g., Scene 4):

1. **Write partial progress**: Every time you successfully generate a significant item (e.g., one scene's assets, one clip), write an `in_progress` checkpoint.

   `in_progress` checkpoints may omit the stage's canonical artifact, but any artifact stored under a known artifact name is still schema-validated. If the partial data is not yet a valid canonical artifact, store it under `metadata.partial_progress` instead of `artifacts`.
   ```python
   write_checkpoint(
       pipeline_dir, project_name,
       stage="assets",
       status="in_progress",
       artifacts={},  # no incomplete canonical artifact yet
       metadata={
           "partial_progress": {
               "asset_manifest_draft": partial_manifest_dict,
               "completed_scene_ids": completed_scene_ids,
           }
       },
   )
   ```
   If the partial artifact already satisfies its schema (for example, an `asset_manifest` with `version: "1.0"` and valid `assets[]` entries), it may be stored in `artifacts` directly.
2. **Resume from partial progress**: When starting a stage, ALWAYS check if an `in_progress` checkpoint exists for it. See Step 7 (Resume Protocol) for how to handle it.

### Step 5: Human Approval (If Required)

**The effective manifest policy is binding.** `human_approval_default`, plus
an explicitly selected manifest-defined `approval_profile`, is the source of
truth for whether a stage gates. This skill never invents ad-hoc exceptions.
(`lib/checkpoint.py` enforces this: writing `status="completed"` for a gated
stage without `human_approved=True` raises a `GATE VIOLATION` error.)

When effective approval is `true`:

1. **Write the checkpoint with `status="awaiting_human"`** (not `completed`).

2. **Present a summary** to the human:
   ```
   ## Stage Complete: [stage_name] — awaiting your approval

   ### Artifact Summary
   [Key details from the artifact — title, duration, key decisions]
   [If the Backlot board is running, point to it: the artifact renders there]

   ### Review Findings
   [Summary from reviewer: N critical (all fixed), N suggestions]

   ### Cost So Far
   [Budget spent / total, breakdown by tool]

   ### Action Required
   Please review and approve to continue, or provide feedback for revision.
   ```

3. **END YOUR TURN.** Performing any further pipeline work in the same
   response is a gate violation. "Present and continue" is not waiting —
   the turn must end with the question, and the next pipeline action must
   be caused by the user's reply.

4. **On the user's response:**
   - **Approved** → re-write the checkpoint with `status="completed"`,
     `human_approved=True`, then proceed to the next stage
   - **Revision requested** → go back to the stage director skill with the
     human's feedback, produce revised artifacts, re-review, re-checkpoint
     (the superseded checkpoint is preserved automatically in `history/`)
   - **Abort** → stop the pipeline

5. **Approval is per-gate.** A prior approval, however broad ("looks great,
   go ahead and make the whole thing"), never covers a later gate. If the
   user explicitly pre-authorizes the full run, record that as a
   `decision_log` entry (`category: "approval_policy"`) at the moment they
   say it — absent that entry, stop at every gate.

6. **The default assets gate reviews the storyboard — before any draft render.**
   `assets` now gates in every pipeline: present the generated assets
   scene-by-scene (the Backlot board's filmstrip is the natural review
   surface), including spend so far and the projected compose cost. A bad
   asset caught here saves a full re-render.

   **Do not render a draft/full composition to earn this review.** The review
   surface is the filmstrip populated with per-scene assets — stock picks,
   generated stills, narration waveforms — *not* a rendered video. For scenes
   whose "asset" is a bespoke/atelier composition (no thumbnailable file), the
   agent writes one **per-scene review still** to
   `projects/<id>/snapshots/<scene_id>.png` (a `remotion still` at a
   representative frame — see `skills/meta/bespoke-composition.md`); the board
   shows those on the filmstrip. Refresh `metadata.partial_progress` as stills
   land, then STOP at the gate. The draft/final render is the **compose**
   stage — it runs only after the assets gate is approved. Rendering a full
   draft inside the assets stage jumps the gate the user is meant to hold.

   `preview_then_avatar` is an explicit manifest-defined exception: the first
   assets pass contains only cheap/free assets and an avatar placeholder;
   edit/compose creates the complete structure preview; `compose` then waits
   for approval. No paid avatar asset may exist before that checkpoint is
   approved.

### Step 6: Determine Next Stage

After checkpoint is written and approved (if needed):

```python
next_stage = get_next_stage(pipeline_dir, project_name)
```

This reads all existing checkpoints and returns the next stage that needs to run, or `None` if the pipeline is complete.

### Step 7: Resume Protocol

At the START of any pipeline run (not just after a stage), always check for existing progress:

```python
next_stage = get_next_stage(pipeline_dir, project_name)
```

If `next_stage` is not the first stage:
1. Inform the human: "Found existing progress. Resuming from stage: [next_stage]"
2. **Check for partial progress**: Read the checkpoint for `next_stage`:
   ```python
   current_cp = read_checkpoint(pipeline_dir, project_name, next_stage)
   ```
   If `current_cp` exists and its status is `"in_progress"`, inform the human you are resuming from the middle of the stage.
3. **Load artifacts**: Load prior artifacts from checkpoints for context. If resuming from `"in_progress"`, first load any schema-valid partial artifact from `current_cp["artifacts"]`. If the partial data is stored in `current_cp["metadata"]["partial_progress"]`, use that draft data and its completion markers (such as `completed_scene_ids`) to skip sub-tasks that are already done.
4. **Continue**: Continue generation from the next successful step, appending to the partial artifact.

If a checkpoint exists with status `"awaiting_human"`:
1. Inform the human: "Stage [name] is awaiting your approval"
2. Present the checkpoint data for review
3. Wait for approval before proceeding

### Deterministic run-until-checkpoint + resume

Use one transition sequence; do not improvise a second runner or render path:

1. `init_project(...)` once, including the selected `approval_profile`.
2. Call `get_next_stage(...)`, run the declared stage director/tool, and write
   its schema-valid checkpoint. Repeat until the effective gate writes
   `awaiting_human`.
3. Return immediately with project id, stage and
   `checkpoint_resume_token(checkpoint)`.
4. On the next turn, call `record_checkpoint_approval(...)`. Evidence must
   include `decision`, `source_message_id`, and a timezone-qualified ISO-8601
   `timestamp`.
5. Immediately before any paid provider call, invoke
   `assert_checkpoint_approved_for_resume(..., expected_resume_token=...,
   expected_decision=...)`. A stale token, ambiguous command, or missing
   original checkpoint fails closed.
6. Run the paid and downstream stages, then write their final checkpoints.

For `preview_then_avatar`, the cheap run ends at `compose` with the complete
placeholder preview. The post-approval transition is machine-enforced, not a
convention: when `record_checkpoint_approval(...)` succeeds, the completed
placeholder checkpoints for the stages listed in the profile's
`post_approval_rerun` (`assets`, `edit`) are archived to `history/` and
removed, so the **same** `get_next_stage(...)` loop resumes at `assets` and
the paid avatar pass replaces the placeholder. The approved `compose`
checkpoint stays `awaiting_human` — it carries the resume token that
`assert_checkpoint_approved_for_resume(...)` verifies immediately before the
first paid avatar call. There is no second creative gate in this profile, and
no second runner.

This workspace evidence is tamper-evident, not a security boundary against a
process with root write access. Malice-resistant deployments must isolate paid
provider and publisher credentials behind validated adapters.

### Sample Checkpoint (Reference-Driven Productions)

When a production is reference-driven (VideoAnalysisBrief exists), there is an
additional checkpoint between proposal approval and full production:

| Stage | checkpoint_required | human_approval_default | Notes |
|-------|--------------------|-----------------------|-------|
| `sample` | true | true | Always requires human approval |

The sample checkpoint:
1. Presents: rendered sample clip (10-15 seconds)
2. Cost: sample cost vs. projected full-video cost
3. Action: approve (→ proceed to script), revise (→ re-generate sample), abort

The sample checkpoint is NOT a pipeline stage — it's a sub-checkpoint within the
proposal stage. It does not produce a canonical artifact. It produces a rendered
preview clip stored at `projects/<name>/assets/sample/sample_v{N}.mp4`.

**Presentation format:**
```
## Sample Preview Ready

**Sample clip:** [path to sample_v1.mp4]
- Duration: [X] seconds (hook + 1 middle scene)
- Voice: [TTS provider + voice name]
- Visuals: [description — AI images, Remotion animations, etc.]
- Music: [source]

**Sample cost:** $[X.XX]
**Projected full video cost:** $[X.XX]

Does this feel right? I can adjust: voice, visual style, pacing, music, colors.
```

## Key Principles

1. **Always checkpoint completed work.** Even if `checkpoint_required: false`, consider checkpointing anyway if the stage took significant time or cost. Losing work is worse than an extra file on disk.

2. **Honor the effective approval policy.** Defaults review creative stages individually; an explicit profile may consolidate them into a later preview but may not remove its paid-operation gate.

3. **Include cost snapshots.** The human should know how much has been spent and how much remains before approving expensive downstream stages (assets, compose).

4. **Checkpoints enable resume.** If the pipeline crashes at `compose`, the human can restart and it picks up from `compose` — not from `idea`. This is the whole point.

5. **Be transparent in approval requests.** Don't just show the artifact — show the review findings, the cost, and any concerns. Help the human make an informed decision.
