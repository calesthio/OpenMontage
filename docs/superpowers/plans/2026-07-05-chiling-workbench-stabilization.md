# Chiling Workbench Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize the current 赤灵AI运营工作台 work so the Web/Worker prototype is green, behaviorally consistent, visually verified, and ready for the next production feature.

**Architecture:** Keep the current no-build static frontend (`web/chiling-workbench`) and local Python Worker. Treat Worker mode as the source of truth for production safety; static mock mode may remain for UI previews but must not contradict the controlled production flow.

**Tech Stack:** Plain HTML/CSS/JS, Python `http.server`, pytest, node syntax checks, OpenMontage project scripts.

---

### Task 1: Finish The Red Frontend Contract

**Files:**
- Modify: `web/chiling-workbench/styles.css`
- Test: `tests/scripts/test_chiling_frontend_queue_contract.py`

- [x] **Step 1: Confirm current red test**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py::test_chiling_frontend_exposes_production_queue_contract -q
```

Expected: FAIL on missing `.task-detail-drawer__head .button`.

- [x] **Step 2: Add no-wrap drawer button CSS**

Add this near the existing `.task-detail-drawer__head` block:

```css
.task-detail-drawer__head .button {
  flex: 0 0 auto;
  white-space: nowrap;
}
```

- [x] **Step 3: Verify frontend contract**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py::test_chiling_frontend_exposes_production_queue_contract -q
```

Expected: PASS.

### Task 2: Align Mock Mode With Worker Safety

**Files:**
- Modify: `web/chiling-workbench/api-client.js`
- Test: `tests/scripts/test_chiling_frontend_queue_contract.py`

- [x] **Step 1: Add a contract for mock mode not auto-completing**

Extend `test_chiling_frontend_exposes_production_queue_contract` with checks that the mock refresh path caps progress at 99 and requires `deliveryBackfill`:

```python
assert "const deliveryReady = task.deliveryBackfill?.status === \"delivered\"" in api_client
assert "Math.min(99" in api_client
assert "completed ? \"completed\"" not in api_client
```

- [x] **Step 2: Run the test and confirm it fails**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py::test_chiling_frontend_exposes_production_queue_contract -q
```

Expected: FAIL because `refreshMockTask()` currently completes by elapsed time.

- [x] **Step 3: Update `refreshMockTask()`**

Replace the current elapsed-completion logic with Worker-equivalent behavior:

```js
function refreshMockTask(task) {
  const deliveryReady = task.deliveryBackfill?.status === "delivered";
  if (deliveryReady || task.status === "completed") {
    return addTaskDerivedFields({
      ...task,
      status: "completed",
      progress: 100,
      completedAt: task.completedAt || Date.now(),
    });
  }

  const elapsed = Math.max(0, Date.now() - task.createdAt);
  const estimatedMs = Math.max(6000, Number(task.estimatedSeconds || 10) * 1000);
  const progress = Math.min(99, Math.max(task.progress || 0, Math.round((elapsed / estimatedMs) * 100)));

  return addTaskDerivedFields({
    ...task,
    status: progress < 16 ? "queued" : "processing",
    progress,
    updatedAt: Date.now(),
    completedAt: null,
  });
}
```

- [x] **Step 4: Verify frontend contract**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_frontend_queue_contract.py -q
```

Expected: PASS.

### Task 3: Re-run The Workbench Regression Set

**Files:**
- No code changes unless tests expose a bug.
- Test: `tests/scripts/test_chiling_pipeline_bridge.py`
- Test: `tests/scripts/test_chiling_worker_bridge.py`
- Test: `tests/scripts/test_chiling_frontend_queue_contract.py`

- [x] **Step 1: Run targeted workbench regression**

Run:

```bash
.venv/bin/python -m pytest tests/scripts/test_chiling_pipeline_bridge.py tests/scripts/test_chiling_worker_bridge.py tests/scripts/test_chiling_frontend_queue_contract.py -q
```

Expected: all pass, with local socket tests skipped only if the sandbox blocks binding.

- [x] **Step 2: Run syntax checks**

Run:

```bash
node --check web/chiling-workbench/app.js
node --check web/chiling-workbench/api-client.js
.venv/bin/python -m py_compile web/chiling-workbench/worker.py web/chiling-workbench/pipeline_bridge.py
```

Expected: no output and exit code 0 for each command.

- [x] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code 0.

### Task 4: Visual Smoke The Drawer

**Files:**
- Update only if visual QA finds a real issue: `web/chiling-workbench/styles.css`
- Optional evidence: `design-qa.md`

- [x] **Step 1: Start the Worker**

Run:

```bash
.venv/bin/python web/chiling-workbench/worker.py --port 5180
```

Expected: Worker serves `http://127.0.0.1:5180`.

- [x] **Step 2: Create or reuse a demo task**

Use the UI or HTTP smoke flow to create a task with queue/detail data.

Expected: the Works page, backend queue, or production queue has a `查看详情` action.

- [x] **Step 3: Open the drawer**

Click `查看详情`.

Expected: the task detail drawer opens, the `关闭` button stays on one line, and sections do not overlap at desktop width.

- [x] **Step 4: Capture QA evidence**

If browser tooling is available, save a screenshot under:

```text
web/chiling-workbench/qa-screenshots/task-detail-drawer.png
```

Update `design-qa.md` with one sentence stating the drawer was checked after the nowrap fix.

### Task 5: Prepare The Worktree For Continued Development

**Files:**
- No code changes required.

- [x] **Step 1: Group the current changes**

Run:

```bash
git status --short
```

Expected: understand which files belong to:
- reference-video pipeline/tooling
- subtitle/compose quality fixes
- chiling workbench Web/Worker
- design mockups/QA evidence

- [x] **Step 2: Decide split strategy before committing**

Recommended split:

```text
1. reference-video pipeline and production tooling
2. subtitle, compose, and final delivery quality fixes
3. chiling workbench Web/Worker prototype
4. UI mockups and design QA artifacts
```

Observed split from `git status --short` on 2026-07-05:

```text
1. Reference/video pipeline core
   - pipeline_defs/reference-video-analysis.yaml
   - skills/pipelines/reference-video-analysis/
   - scripts/analyze_reference_video.py
   - scripts/reverse_reference_prompts.py
   - scripts/reference_* except chiling UI smoke-only pieces
   - tools/analysis/reference_*.py
   - tests/scripts/test_reference_*.py
   - tests/tools/test_reference_*.py

2. Production, Seedance, subtitle, compose, and delivery quality
   - scripts/prepare_reference_production.py
   - scripts/approve_reference_package.py
   - scripts/plan_seedance_batch.py
   - scripts/preview_reference_seedance.py
   - scripts/preview_reference_final_edit.py
   - scripts/compose_reference_final.py
   - scripts/polish_reference_subtitles.py
   - scripts/review_reference_final.py
   - scripts/export_reference_delivery.py
   - tools/video/runninghub_seedance_video.py
   - tools/video/seedance_batch.py
   - tools/video/seedance_constraints.py
   - tools/subtitle/oral_subtitle_planner.py
   - tools/subtitle/doubao_subtitle_polish.py
   - tools/video/video_compose.py
   - related tests in tests/scripts/ and tests/tools/

3. Chiling workbench Web/Worker prototype
   - web/chiling-workbench/
   - design-qa.md
   - tests/scripts/test_chiling_pipeline_bridge.py
   - tests/scripts/test_chiling_worker_bridge.py
   - tests/scripts/test_chiling_frontend_queue_contract.py

4. Product UI mockups and design artifacts
   - docs/ui-mockups/
   - scripts/render_chiling_ui_mockups.py
   - scripts/render_chiling_ui_v4_mockups.py
   - scripts/render_chiling_ui_v5_mockups.py

5. Pipeline/plugin planning material
   - pipeline_defs/creator-video.yaml
   - skills/pipelines/creator-video/
   - tests/contracts/test_creator_video_pipeline.py
   - docs/superpowers/plans/
   - docs/superpowers/specs/

6. Local tooling artifacts to avoid committing
   - .playwright-cli/
```

- [x] **Step 3: Do not commit generated project assets**

Confirm `projects/` stays ignored unless the user explicitly asks to preserve a sample artifact.

Expected: generated MP4s, task data, and local queue artifacts remain out of git.

Observed: `projects/` generated assets remain ignored and did not appear in `git ls-files --others --exclude-standard`.

### Task 6: Next Feature After Stabilization

**Files:**
- Likely modify: `web/chiling-workbench/worker.py`
- Likely modify: `web/chiling-workbench/api-client.js`
- Likely modify: `web/chiling-workbench/app.js`
- Likely test: `tests/scripts/test_chiling_worker_bridge.py`
- Likely test: `tests/scripts/test_chiling_frontend_queue_contract.py`

- [x] **Step 1: Choose the next feature**

Recommended next feature: a real controlled production-service adapter behind an explicit server-side flag, still disabled by default.

- [x] **Step 2: Write the safety contract first**

Add tests proving:

```python
assert response["paidGenerationStarted"] is False
assert "provider" not in visible_payload
assert "model" not in visible_payload
```

- [x] **Step 3: Implement only the disabled/config-diagnostic path unless the user approves paid execution**

Keep UI and Worker behavior aligned with the existing rule: no paid/video provider runs from the page without explicit approval.

Implemented on 2026-07-05 as a server-side production-service preflight shell:
- Default remains disabled.
- Preflight requires service switch, connection configuration, and separate server execution approval.
- Approved preflight writes an audit artifact and returns `preflight_ready` / `等待服务端执行器接管`.
- It does not queue server execution, start an adapter, call providers, expose internal configuration, or start paid generation.

### Task 7: Prepare Chiling Workbench Staging Set

**Files to stage for the Chiling workbench change set:**
- `.gitignore` for `web/chiling-workbench/.worker-data/` and `web/chiling-workbench/qa-screenshots/` ignore rules. Note: this file also currently adds `.local-bin/`; either keep that as local tooling hygiene in the same commit or split `.gitignore` into a separate small commit.
- `web/chiling-workbench/README.md`
- `web/chiling-workbench/api-client.js`
- `web/chiling-workbench/app.js`
- `web/chiling-workbench/assets/portrait.png`
- `web/chiling-workbench/assets/reference-frame.png`
- `web/chiling-workbench/config.js`
- `web/chiling-workbench/index.html`
- `web/chiling-workbench/pipeline_bridge.py`
- `web/chiling-workbench/styles.css`
- `web/chiling-workbench/worker.py`
- `design-qa.md`
- `tests/scripts/test_chiling_pipeline_bridge.py`
- `tests/scripts/test_chiling_worker_bridge.py`
- `tests/scripts/test_chiling_frontend_queue_contract.py`
- `docs/superpowers/plans/2026-07-05-chiling-workbench-stabilization.md`

**Do not stage with this change set:**
- `.playwright-cli/` browser snapshots and logs.
- `web/chiling-workbench/.worker-data/` local Worker runtime state.
- `web/chiling-workbench/__pycache__/` Python bytecode.
- `web/chiling-workbench/qa-screenshots/` generated QA captures unless the user explicitly wants screenshot artifacts versioned.
- `docs/ui-mockups/` and `scripts/render_chiling_ui*_mockups.py`; keep UI mockups as a separate artifact/design change set.
- Reference-video pipeline/tooling files; keep them separate from the Chiling Web/Worker prototype.
- Seedance/subtitle/compose/delivery quality files; keep them as a production tooling change set.

**Last observed validation for this set:**
- Workbench regression: `23 passed, 2 skipped`.
- Frontend contract after preflight copy fix: `2 passed`.
- Syntax checks: `node --check web/chiling-workbench/app.js`, `node --check web/chiling-workbench/api-client.js`, and `py_compile` for Worker/bridge passed.
- `git diff --check` passed.
