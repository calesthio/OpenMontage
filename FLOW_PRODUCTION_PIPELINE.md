# FLOW_PRODUCTION_PIPELINE.md

Google Flow Production Pipeline — OpenMontage
=============================================

A production-ready system for preparing, validating, and managing Google Flow
generation jobs.  Zero credits are spent by the automated pipeline: it stops
at `READY_FOR_APPROVAL` and waits for explicit manual human approval before
any submission to Google Flow.

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     OpenMontage Repository                      │
├─────────────────────────────────────────────────────────────────┤
│  lib/flow_job_manager.py   ← Core job manager (this document)   │
│  lib/shot_prompt_builder.py ← Prompt construction (reused)      │
│  lib/zero_cost_gate.py     ← Zero-cost enforcement (reused)     │
│  jobs/                     ← Job definitions (JSON)              │
│  flow_queue/               ← Queue state (SQLite)               │
│  flow_results/             ← Results by project/scene           │
│  flow_audit/               ← Audit log                          │
│  tests/test_flow_job_manager.py ← Test suite (26 tests)         │
├─────────────────────────────────────────────────────────────────┤
│  MCP Integrations (read-only, no spend):                        │
│    • gflow MCP       → auth, projects, models, credits          │
│    • browser-use MCP → navigate, state, screenshot, extract     │
└─────────────────────────────────────────────────────────────────┘
```

### Job lifecycle state machine

```
DRAFT → VALIDATED → READY_FOR_APPROVAL → APPROVED → SUBMITTED → COMPLETED / FAILED
```

| State | Meaning | Who transitions |
|-------|---------|-----------------|
| DRAFT | Job created, not yet validated | `add_job()` |
| VALIDATED | Prompt, references, input files verified | `validate_job()` |
| READY_FOR_APPROVAL | Ready for human review | `ready_for_approval()` |
| APPROVED | Human-approved for submission | `approve()` (manual) |
| SUBMITTED | Submitted to Google Flow | `submit()` (manual) |
| COMPLETED | Generation finished successfully | `complete()` |
| FAILED | Generation or validation failed | `fail()` |

**The automated system stops at `READY_FOR_APPROVAL`.**  Transition to
`APPROVED` requires explicit manual human approval.

---

## 2. File structure

```
/workspaces/OpenMontage/
├── lib/
│   ├── flow_job_manager.py      # Core job manager (new)
│   ├── shot_prompt_builder.py   # Prompt construction (existing, reused)
│   └── zero_cost_gate.py        # Zero-cost enforcement (existing, reused)
├── jobs/
│   ├── demo_jobs.json           # 10 demo jobs (new)
│   └── *.json                   # Individual job files (created by add_job)
├── flow_queue/
│   └── queue.db                 # SQLite queue state (created on first run)
├── flow_results/
│   └── <project>/<scene>/       # Results organized by project/scene
├── flow_audit/
│   └── flow_audit.log           # Audit log (append-only)
├── tests/
│   └── test_flow_job_manager.py # Test suite (26 tests, new)
└── FLOW_PRODUCTION_PIPELINE.md  # This document
```

---

## 3. MCP integration (read-only only)

### gflow MCP tools used (read-only)

| Tool | Purpose |
|------|---------|
| `gflow_auth_status` | Verify Flow session authentication (profile: flow_remote) |
| `gflow_list_projects` | List available Flow projects |
| `gflow_list_models` | List available generation models |
| `gflow_get_credits` | Read credit balance (no spend) |

**Generation tools (`gflow_generate_image`, `gflow_generate_video`) are NOT
registered** because `GFLOW_MCP_NO_SPEND=1` and `--no-spend` are enforced.

### Browser Use MCP tools used (read-only)

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Open Google Flow page |
| `browser_get_state` | Read page state and DOM |
| `browser_screenshot` | Capture page screenshot |
| `browser_extract_content` | Extract text from page |
| `browser_list_tabs` | List open tabs |

**Forbidden actions** (never used by this pipeline):
- `browser_click` — could trigger generation
- `browser_type` — could submit forms
- `browser_scroll` — could reveal generation buttons

---

## 4. Zero-cost protection

The following safeguards are in place and **must not be disabled**:

1. **`GFLOW_MCP_NO_SPEND=1`** — set in kilo.jsonc env block
2. **`--no-spend`** — passed to `gflow mcp run`
3. **Read-only gflow tools only** — generation tools are not in the permitted set
4. **Browser Use forbidden actions** — `browser_click`, `browser_type`, `browser_scroll` are blocked
5. **Pipeline stops at READY_FOR_APPROVAL** — no automated submission

### Manual generation approval (future)

A separate manual mechanism for authorizing generation will be added in a
future update. By default it is **disabled**.  To enable (future):

```
export GFLOW_MCP_ALLOW_GENERATION=1
# Then use a separate approval flow, not this pipeline
```

---

## 5. Adding jobs

### Single job via Python API

```python
from lib.flow_job_manager import get_manager

mgr = get_manager()
job = mgr.add_job(
    job_id="my-job-001",
    project="my-project",
    scene="opening-shot",
    prompt="Cinematic wide shot of a rocket launching, golden hour lighting, photorealistic, 35mm lens",
    aspect_ratio="16:9",
    resolution="1920x1080",
    references=["assets/references/rocket.png"],
    input_files=[],
    generation_params={},
)
print(f"Job {job.job_id} created in state {job.state}")
```

### Bulk import from JSON

```python
created = mgr.add_jobs_from_json("jobs/demo_jobs.json")
print(f"Imported {len(created)} jobs")
```

### Job JSON format

```json
{
  "job_id": "my-job-001",
  "project": "my-project",
  "scene": "opening-shot",
  "prompt": "Your generation prompt here",
  "aspect_ratio": "16:9",
  "resolution": "1920x1080",
  "references": [],
  "input_files": [],
  "generation_params": {}
}
```

---

## 6. Validating jobs

```python
# Validate a single job
job = mgr.validate_job("my-job-001")
print(f"State: {job.state}")  # VALIDATED or DRAFT (with error)

# Check validation errors
if job.error:
    print(f"Validation failed: {job.error}")
```

Validation checks:
- Prompt is non-empty, 10-2000 characters
- All reference files exist
- All input files exist
- gflow MCP is accessible (auth, projects, models)

Jobs with missing references or invalid prompts stay in `DRAFT` with an error
message.  MCP connection failures are recorded as warnings but do not block
local validation.

---

## 7. Queue management

```python
# List all jobs
jobs = mgr.list_jobs()

# Filter by state
validated = mgr.list_jobs(state="VALIDATED")

# Filter by project
project_jobs = mgr.list_jobs(project="my-project")

# Queue summary
summary = mgr.queue_summary()
print(summary)
# {'total': 10, 'by_state': {'DRAFT': 2, 'VALIDATED': 8}, ...}
```

### Move to READY_FOR_APPROVAL

```python
job = mgr.ready_for_approval("my-job-001")
# State is now READY_FOR_APPROVAL — automated system stops here
```

### Manual approval (human action)

```python
# Requires explicit human approval — NOT automated
job = mgr.approve("my-job-001")       # READY_FOR_APPROVAL → APPROVED
job = mgr.submit("my-job-001")         # APPROVED → SUBMITTED
job = mgr.complete("my-job-001")        # SUBMITTED → COMPLETED
job = mgr.fail("my-job-001", "error")  # Any state → FAILED
```

---

## 8. Editing prompts

Prompts can be edited without recreating the job.  Each edit increments the
prompt version.

```python
job = mgr.edit_prompt("my-job-001", "New prompt text here")
print(f"Prompt version: {job.prompt_version}")  # 2, 3, ...
```

Prompt editing is allowed in `DRAFT` and `VALIDATED` states only.

---

## 9. Results organization

Results are stored by project and scene:

```python
result_dir = mgr.result_dir("my-project", "opening-shot")
# → flow_results/my-project/opening-shot/
```

This directory is created on demand and is where generation results would be
stored after manual submission and completion.

---

## 10. Queue recovery after restart

Jobs persist to individual JSON files in `jobs/` and to the SQLite queue in
`flow_queue/queue.db`.  On restart, `FlowJobManager()` automatically reloads
all jobs from disk:

```python
mgr = FlowJobManager()  # Loads all existing jobs
job = mgr.get_job("my-job-001")  # Retrieved from disk
```

---

## 11. Running tests

```bash
# Run the full test suite (26 tests)
/usr/local/py-utils/bin/pytest tests/test_flow_job_manager.py -v

# Run with coverage
/usr/local/py-utils/bin/pytest tests/test_flow_job_manager.py -v --cov=lib.flow_job_manager
```

All tests are zero-cost: no generation, no credit spending, no generation
button clicks.  Two MCP tests are skipped if the gflow browser-based checks
cannot launch in the test environment.

---

## 12. Actions requiring manual human approval

| Action | Method | Why manual |
|--------|--------|------------|
| READY_FOR_APPROVAL → APPROVED | `approve()` | Human must review prompt and parameters |
| APPROVED → SUBMITTED | `submit()` | Human must authorize credit spending |
| Any generation button click | — | Forbidden in this pipeline (read-only only) |
| Enabling GFLOW_MCP_ALLOW_GENERATION | — | Future feature, disabled by default |

---

## 13. Reused OpenMontage components

| Component | Path | Use |
|-----------|------|-----|
| Shot prompt builder | `lib/shot_prompt_builder.py` | Converts structured shot language to generation prompts |
| Zero-cost gate | `lib/zero_cost_gate.py` | Enforces strict zero-cost mode |
| Pipeline loader | `lib/pipeline_loader.py` | Loads pipeline manifests (for future integration) |
| Provider jobs | `tools/provider_jobs.py` | HTTP primitives for media adapters (for future integration) |

---

## 14. Quick start

```bash
# 1. Ensure Chrome is running on CDP 9223 with flow-mobile profile
# (see FLOW_FINAL_STABILITY_REPORT.md)

# 2. Import demo jobs
/usr/local/py-utils/bin/python3 -c "
from lib.flow_job_manager import get_manager
mgr = get_manager()
created = mgr.add_jobs_from_json('jobs/demo_jobs.json')
print(f'Imported {len(created)} jobs')
"

# 3. Validate all jobs
/usr/local/py-utils/bin/python3 -c "
from lib.flow_job_manager import get_manager
mgr = get_manager()
for job in mgr.list_jobs(state='DRAFT'):
    mgr.validate_job(job.job_id)
print('All jobs validated')
"

# 4. View queue
/usr/local/py-utils/bin/python3 -c "
from lib.flow_job_manager import get_manager
mgr = get_manager()
print(mgr.queue_summary())
"

# 5. Run tests
/usr/local/py-utils/bin/pytest tests/test_flow_job_manager.py -v
```

---

## 15. Safety summary

| Safeguard | Status |
|-----------|--------|
| GFLOW_MCP_NO_SPEND=1 | ✅ Enforced |
| --no-spend flag | ✅ Enforced |
| No generation tools registered | ✅ Confirmed (0 generate tools in MCP list) |
| Browser Use click/type/scroll blocked | ✅ Forbidden set defined |
| Pipeline stops at READY_FOR_APPROVAL | ✅ State machine enforced |
| Duplicate job prevention | ✅ By job_id and by content hash |
| Audit logging | ✅ flow_audit/flow_audit.log |
| Queue recovery | ✅ JSON + SQLite persistence |
