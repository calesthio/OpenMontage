# VIDEO_PREPRODUCTION_SYSTEM.md

# OpenMontage — Intelligent Video Preproduction System

Architecture, modules, subagents, commands, input/output formats, and usage
for the end-to-end preproduction pipeline for scientific YouTube videos.

**Zero-cost by design:** no image/video generation, no Google Flow credits
spent, no MCP calls that trigger paid operations.  All work is local,
structural, and stops at `READY_FOR_APPROVAL` awaiting human sign-off.

---

## 1. Architecture

The pipeline transforms a spoken script into production-ready Flow jobs
through seven sequential stages:

```
┌─────────────────────────────────────────────────────────────────────┐
│  INPUT: Script + Title + Duration + Characters + Visual Style        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  1. Script Analyzer (lib/script_analyzer.py)                         │
│     • Splits script into meaning blocks                              │
│     • Detects scientific claims                                      │
│     • Flags repetition                                               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  2. Scene Planner (lib/scene_planner.py)                             │
│     • Maps blocks → scenes                                           │
│     • Assigns shot size, movement, lens, lighting, composition       │
│     • Chains scenes with transitions                                 │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  3. Visual Director (lib/visual_director.py)                         │
│     • Enforces shot variety                                          │
│     • Reserves caption space                                         │
│     • Reports variety score                                          │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  4. Character Consistency Manager (lib/character_consistency_.py)   │
│     • Registers character anatomy                                    │
│     • Validates scenes against design                                │
│     • Detects contradictions                                         │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  5. Prompt Engineer (lib/prompt_engineer.py)                         │
│     • Builds main prompt + negative prompt                           │
│     • Applies visual foundation (bold ink illustration style)        │
│     • Prohibits text/captions/watermarks inside images               │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  6. Quality Control (lib/quality_control.py)                         │
│     • 9 per-scene criteria                                           │
│     • Human review flagged for scientific claims                     │
│     • Blocks duplicates, anatomy errors, contradictions              │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  7. Flow Integration (lib/flow_integration.py)                       │
│     • Creates Flow Job Manager jobs                                  │
│     • Validates → READY_FOR_APPROVAL                                 │
│     • Stops before any credit-spending submission                    │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     HUMAN APPROVAL (manual)
                              │
                              ▼
                     SUBMITTED → COMPLETED / FAILED
```

---

## 2. Modules

### 2.1 Script Analyzer (`lib/script_analyzer.py`)

**Input:** script text, title, target duration, character list, visual style.

**Output:** `ScriptAnalysis` with:
- `blocks[]` — meaning blocks (id, text, type, word count, est. seconds)
- `visual_moments[]` — timestamped visual change points
- `scientific_claims[]` — factual assertions needing visual backing
- `characters_mentioned[]` — characters referenced in script
- `repetition_flags[]` — near-duplicate block warnings

**Key logic:**
- Sentence-boundary splitting via regex
- Block classification: `exposition` | `claim` | `transition` | `conclusion`
- Claim detection: numbers, units, claim-marker verbs
- Repetition detection: normalized text deduplication

### 2.2 Scene Planner (`lib/scene_planner.py`)

**Input:** analysed blocks, characters, visual style, optional hero index.

**Output:** `ScenePlanOutput` with ordered `scenes[]`. Each `ScenePlan` has:

| Field | Description |
|-------|-------------|
| `scene_id` | Unique identifier (`{run_id}-scene-NNN`) |
| `script_section_id` | Source block id |
| `visual_idea` | Scene description |
| `shot_purpose` | Narrative role (establish_context, deliver_payload, etc.) |
| `framing` | Shot size (wide, medium, close_up, etc.) |
| `camera_movement` | static, dolly_in, zoom_in, pan_right, etc. |
| `lens_mm` | Focal length (14–85mm) |
| `lighting_key` | natural, high_key, low_key |
| `composition` | Shot composition description |
| `required_objects[]` | Props and characters needed |
| `duration_seconds` | Planned screen time |
| `transition_to_next` | How to move to next scene |
| `shot_size`, `shot_intent`, `narrative_role` | Metadata |
| `hero_moment` | Boolean — hero scene flag |

**State flow:** DRAFT → VALIDATED → READY_FOR_APPROVAL → APPROVED → SUBMITTED → COMPLETED/FAILED.
Automated system stops at **READY_FOR_APPROVAL**.

### 2.3 Visual Director (`lib/visual_director.py`)

**Input:** scene list, characters.

**Output:** `VisualDirectionReport` with:
- Per-scene `VisualDirective` (shot size, movement, lens, lighting, composition, hero space, character placement, environment)
- `shot_size_distribution`, `movement_distribution`, `lighting_distribution`
- `variety_score` (0–5, lower = more varied)
- `issues[]` and `passed` flag

**Variety rules:**
- No more than 2 consecutive scenes with the same shot size
- Shot size variety enforced by rotating to alternative sizes
- Bottom third always reserved for editor-added captions
- Character placement varies by shot size

### 2.4 Character Consistency Manager (`lib/character_consistency_manager.py`)

**Input:** character anatomy, references, scene descriptions.

**Output:** `ConsistencyReport` with per-scene issues.

**Character anatomy fields:**
- `character_id`, `display_name`, `role`, `body_type`
- `limb_count` (e.g., 4 for humanoid)
- `distinguishing_features[]` (e.g., "gold-coated hexagonal mirror segments")
- `silhouette_notes`, `color_palette[]`, `clothing_notes`
- `required_views[]`, `required_emotions[]`, `required_actions[]`, `props[]`

**Checks:**
- Limb count match
- Distinguishing features present
- Clothing consistency
- Unknown character detection
- Cross-scene contradiction detection

**Important:** Characters are not limited to portraits — they appear organically in environments.

### 2.5 Prompt Engineer (`lib/prompt_engineer.py`)

**Input:** scene plan, visual directive, character anatomy, references.

**Output:** `ScenePromptPacket` with:

| Field | Description |
|-------|-------------|
| `main_prompt` | Full generation prompt |
| `negative_prompt` | Prohibitions (text, captions, watermarks, etc.) |
| `composition_description` | Shot size, lens, movement, lighting, DOF |
| `style` | Visual style (bold ink illustration, etc.) |
| `character_description` | Character anatomy + placement |
| `environment_description` | Setting details |
| `references[]` | Reference IDs |
| `image_format` | "1920x1080, ink illustration" |
| `aspect_ratio` | e.g. "16:9" |
| `generation_params` | Model parameters |

**Visual foundation (applied to every scene):**
- Positive: bold ink illustration, crisp black outlines, flat expressive colour fills, scientific-documentary composition, expressive lighting, varied surrounding environments
- Negative: text, caption, watermark, logo, signature, title, subtitle, lettering, typography, AI-generated gibberish text, distorted text, blurry text, template repetition, generic stock look, airbrushed, 3d render, plastic, gradient mesh, photorealistic photograph

**Never:** text, captions, watermarks, or logos inside images.

### 2.6 Quality Control (`lib/quality_control.py`)

**Nine per-scene criteria:**

| Criterion | What it checks | Human review? |
|-----------|---------------|---------------|
| `script_alignment` | Scene serves the script section | No |
| `scientific_accuracy` | Visual matches claim domain | **Yes** (always) |
| `character_reference` | Depiction matches character design | No |
| `duplicate_frames` | Not near-duplicate of another scene | No |
| `anatomy_errors` | Correct limb count, no feature drift | No |
| `prompt_contradictions` | Main vs negative prompt don't conflict | No |
| `composition_variety` | Composition distinct from neighbours | No |
| `no_text_in_image` | No text/caption/watermark instructions | No |
| `technical_suitability` | Format/aspect ratio valid for Flow | No |

**Scoring:** Each criterion 0.0–1.0. Overall = mean. Blocking issues prevent queueing.

### 2.7 Flow Integration (`lib/flow_integration.py`)

**Input:** scene plans, prompt packets, QC reports, references.

**Output:** `FlowIntegrationOutput` with jobs in `READY_FOR_APPROVAL` state.

**Key behavior:**
- Only scenes that pass QC are queued
- Failed scenes are recorded as `FAILED` jobs with blocking reasons
- All jobs stop at `READY_FOR_APPROVAL` — no automated submission
- `skip_mcp=True` used during preproduction (MCP checks are slow browser subprocesses)
- Zero credits spent — `--no-spend` enforced

---

## 3. Subagent Architecture

The system supports five specialized subagent roles. Existing Kilo subagents are reused where applicable; new roles are organized as independent agents with clear zones of responsibility.

| Subagent | Responsibility | Existing Kilo Agent? |
|----------|---------------|---------------------|
| `script-analyst` | Script analysis, block splitting, claim detection | No — new role |
| `storyboard-director` | Scene planning, visual direction, shot variety | No — new role |
| `visual-prompt-engineer` | Prompt engineering, negative prompts, visual foundation | No — new role |
| `character-consistency-reviewer` | Character anatomy, references, cross-scene consistency | No — new role |
| `quality-control-reviewer` | QC criteria, blocking decisions, human review flags | No — new role |

**Zone of responsibility:** Each subagent owns exactly one pipeline stage. No overlap. No subagent creates duplicates of another's output.

**Activation:** Subagents are invoked via Kilo's `@agent` mechanism when their stage is reached. They produce structured output consumed by the next stage.

---

## 4. Commands

### 4.1 Run the full pipeline (Python)

```python
from lib.script_analyzer import ScriptAnalyzer
from lib.scene_planner import ScenePlanner, to_dict as scene_plan_to_dict
from lib.visual_director import VisualDirector
from lib.character_consistency_manager import CharacterConsistencyManager
from lib.prompt_engineer import PromptEngineer
from lib.quality_control import QualityControl
from lib.flow_integration import FlowIntegration
from lib.flow_job_manager import get_manager

# 1. Analyze script
analyzer = ScriptAnalyzer()
analysis = analyzer.analyze(
    title="My Video",
    script="...spoken script...",
    target_duration_seconds=600.0,
    characters=["Narrator", "Subject"],
    visual_style="bold ink illustration",
)
analysis_dict = analyzer.to_dict(analysis)

# 2. Plan scenes
planner = ScenePlanner()
plan = planner.plan(
    run_id="run-001",
    analysis_blocks=analysis_dict["blocks"],
    characters=["Narrator", "Subject"],
    visual_style="bold ink illustration",
)
plan_dict = scene_plan_to_dict(plan)

# 3. Visual direction
director = VisualDirector()
direction = director.direct(plan_dict["scenes"])
direction_dict = director.to_dict(direction)

# 4. Character consistency
ccm = CharacterConsistencyManager()
ccm.register_character(character_id="Narrator", display_name="Narrator", ...)
ccm.validate_all_scenes(scene_char_map, scene_descs)

# 5. Engineer prompts
engineer = PromptEngineer()
prompts = engineer.build_all(
    scene_plans=plan_dict["scenes"],
    visual_directives={d["scene_id"]: d for d in direction_dict["directives"]},
    character_anatomy={...},
    references_by_scene={...},
)

# 6. Quality control
qc = QualityControl()
qc_batch = qc.check_batch(...)

# 7. Integrate with Flow Job Manager
manager = get_manager()
integration = FlowIntegration(manager=manager)
flow_output = integration.integrate(
    run_id="run-001",
    project="my-video",
    scene_plans=plan_dict["scenes"],
    prompt_packets=prompts_dict["packets"],
    quality_reports=qc_dict["reports"],
)
```

### 4.2 Run tests

```bash
# All preproduction tests (21 tests)
/usr/local/py-utils/bin/pytest tests/test_video_preproduction_system.py -v

# All test suites (71 tests, 2 skipped)
/usr/local/py-utils/bin/pytest tests/ -v -m "not integration"

# Including integration tests (requires Chrome on CDP 9223)
/usr/local/py-utils/bin/pytest tests/ -v
```

### 4.3 Run load testing

```bash
python3 tests/test_flow_load.py
```

Tests 100 jobs, duplicate content, restart recovery, parallel addition, malformed JSON.

---

## 5. Input/Output Formats

### 5.1 Script Analysis Input

```json
{
  "title": "How Webb Sees First Galaxies",
  "script": "Full spoken script text...",
  "target_duration_seconds": 600.0,
  "characters": ["James Webb Space Telescope", "Astronomer"],
  "visual_style": "bold ink illustration"
}
```

### 5.2 Scene Plan Output (per scene)

```json
{
  "scene_id": "run-001-scene-000",
  "script_section_id": "block-000",
  "visual_idea": "The James Webb Space Telescope... — medium shot; ...",
  "shot_purpose": "establish_context",
  "framing": "wide shot",
  "camera_movement": "static",
  "lens_mm": 24,
  "lighting_key": "natural",
  "composition": "subject small in frame, environment dominates; wide; ...",
  "required_objects": [],
  "duration_seconds": 6.0,
  "transition_to_next": "cut to",
  "shot_size": "wide",
  "shot_intent": "Serves establish_context for section block-000",
  "narrative_role": "establish_context",
  "hero_moment": false
}
```

### 5.3 Prompt Packet Output (per scene)

```json
{
  "scene_id": "run-001-scene-000",
  "main_prompt": "The James Webb Space Telescope... . wide shot; ...",
  "negative_prompt": "text, caption, watermark, logo, ...",
  "composition_description": "wide shot, 24mm lens, static camera, ...",
  "style": "bold ink illustration; crisp black outlines; ...",
  "character_description": "James Webb Space Telescope; hexagonal mirror...",
  "environment_description": "interior laboratory",
  "references": ["webb-ref-001"],
  "image_format": "1920x1080, ink illustration",
  "aspect_ratio": "16:9",
  "generation_params": {"model": "flow", "steps": 20}
}
```

### 5.4 Flow Job Output

```json
{
  "scene_id": "run-001-scene-000",
  "job_id": "run-001-job-run-001-scene-000",
  "state": "READY_FOR_APPROVAL",
  "prompt_packet": { ... },
  "quality_report": { ... },
  "references": ["webb-ref-001"],
  "project": "my-video",
  "scene": "run-001-scene-000"
}
```

---

## 6. Quality Control Criteria (detailed)

Each criterion produces a `QCResult` with `passed`, `score` (0.0–1.0), `detail`, and `requires_human_review`.

**Scientific accuracy** always sets `requires_human_review=True` — the system never certifies factual correctness, only notes whether visual illustration references the claim domain.

**Duplicate detection** uses Jaccard similarity on scene description words (>0.85 = duplicate).

**Composition variety** uses Jaccard similarity on composition strings (>0.8 = too similar).

**No text in image** checks for positive text instructions in the main prompt and prohibitions in the negative prompt.

---

## 7. Safety & Constraints

| Constraint | Enforcement |
|------------|-------------|
| No image/video generation | Pipeline stops at READY_FOR_APPROVAL; no generation calls |
| No Google Flow credits spent | `GFLOW_MCP_NO_SPEND=1`; `--no-spend` flag; generate tools hidden |
| No Google account changes | Profiles `flow_remote` / `flow-mobile` untouched |
| No existing MCP removal | All 7 MCP servers preserved |
| No existing module replacement | New modules added alongside existing ones |
| No text/watermarks in images | Negative prompt prohibits; QC checks |
| No AI-template repetition | Visual foundation includes "no visual AI-template repetition" |

---

## 8. Recovery & Resilience

- **Queue persistence:** Jobs stored as individual JSON files in `jobs/` and in SQLite at `flow_queue/queue.db`
- **Atomic saves:** JSON written to `.part` temp file, then SQLite commit, then rename — rollback on SQLite failure
- **Restart recovery:** `FlowJobManager()` auto-loads all jobs from disk on instantiation
- **Duplicate prevention:** By `job_id` AND by content hash (SHA-256 of project+scene+prompt+parameters)
- **WAL mode:** SQLite uses `journal_mode=WAL` with 30s busy timeout for concurrent access

---

## 9. Test Results

| Test Suite | Tests | Passed | Skipped | Failed |
|------------|-------|--------|---------|--------|
| test_video_preproduction_system.py | 21 | 21 | 0 | 0 |
| test_flow_job_manager.py | 24 | 23 | 2 | 0 |
| test_flow_job_manager_mock.py | 8 | 8 | 0 | 0 |
| test_mcp_security_proxy.py | 13 | 13 | 0 | 0 |
| test_flow_load.py | 6 | 6 | 0 | 0 |
| **Total** | **72** | **71** | **2** | **0** |

**Load testing:** 100 jobs, duplicate content detection, restart recovery, parallel addition (10 threads), malformed JSON handling — all pass.

---

## 10. Subagent Invocation

Each subagent is invoked via Kilo's agent mechanism:

```
/@script-analyst — Analyse script, produce blocks and claims
/@storyboard-director — Plan scenes from analysed blocks
/@visual-prompt-engineer — Build per-scene prompt packets
/@character-consistency-reviewer — Validate character consistency
/@quality-control-reviewer — Run QC checks and flag blockers
```

Each subagent receives the previous stage's output and produces structured data for the next stage. No subagent modifies another's output.

---

## 11. Human Approval Points

| Action | Method | Required |
|--------|--------|----------|
| READY_FOR_APPROVAL → APPROVED | `manager.approve(job_id)` | **Yes** — human must review prompt and parameters |
| APPROVED → SUBMITTED | `manager.submit(job_id)` | **Yes** — human must authorize credit spending |
| SUBMITTED → COMPLETED | `manager.complete(job_id)` | After generation results stored |
| Any state → FAILED | `manager.fail(job_id, error)` | On error |

**The automated system never advances past READY_FOR_APPROVAL without explicit human intervention.**

---

## 12. Files Created

| File | Purpose |
|------|---------|
| `lib/script_analyzer.py` | Script analysis module |
| `lib/scene_planner.py` | Scene planning module |
| `lib/visual_director.py` | Visual direction module |
| `lib/character_consistency_manager.py` | Character consistency module |
| `lib/prompt_engineer.py` | Prompt engineering module |
| `lib/quality_control.py` | Quality control module |
| `lib/flow_integration.py` | Flow Job Manager integration |
| `tests/test_video_preproduction_system.py` | 21 end-to-end tests |
| `VIDEO_PREPRODUCTION_SYSTEM.md` | This documentation |

---

## 13. Quick Start

```bash
# Run all preproduction tests
/usr/local/py-utils/bin/pytest tests/test_video_preproduction_system.py -v

# Run full pipeline in Python
python3 -c "
from lib.script_analyzer import ScriptAnalyzer
# ... (see Commands section above)
"

# Verify no generation triggered
# All jobs should be in READY_FOR_APPROVAL state
# GFLOW_MCP_NO_SPEND=1 must remain set
```
