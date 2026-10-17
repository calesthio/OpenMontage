# OpenMontage

**MANDATORY: Read `AGENT_GUIDE.md` before responding to ANY user message.**

Do not act on the user's request until you have read AGENT_GUIDE.md.
It contains routing rules that determine your first action based on what the user asked.
Skipping it WILL cause you to take the wrong action.

There are no instructions in this file. All instructions are in AGENT_GUIDE.md.

## Factory Sessions (OpenMontage Factory)

Permanent-work sessions follow the master plan at
`docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md`. At the start of every such
session, in this order:

1. `docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md` — the task source.
2. `docs/OPENMONTAGE_RESUME.md` — current state and the exact next action.
3. `docs/OPENMONTAGE_WORK_LOG.md` — history of completed work.
4. Repository reality (git status, code, tests) outranks stale notes.

After every verified step: update `OPENMONTAGE_RESUME.md`, append a dated
entry to `OPENMONTAGE_WORK_LOG.md`, and commit on a working branch (never
`main`, never force-push). Strict zero-cost mode is the default: an unpriced
or un-named route is BLOCKED, not free (`lib/zero_cost_gate.py`).

---

## Agent roster (Kilo 7.8.12, `.kilo/agents/`, mode: subagent)

All four are `subagent` mode. Permission rules follow the Kilo 7.8.12 schema
(YAML frontmatter `description`, `mode`, `permission:` map). Invoke by `@name`.

| Agent | Mode | Purpose | Write scope | Bash allowlist | Network |
|---|---|---|---|---|---|
| `editor` | subagent | Builds/edits timeline: EDL JSON with per-cut rationale, pacing report, audio plan (cutting-rhythm, edl-edit, audio-edit skills) | `projects/**/edit/**` + EDL/timeline files only | `ffprobe`, analysis-only `ffmpeg -f null` | deny |
| `qa-reviewer` | subagent | Independent read-only QA via `tools/qa/qc.py` (ffprobe, full decode, blackdetect, freezedetect, silencedetect, ebur128, SRT sanity); writes `qa_report.json`; thresholds in `config/qc_thresholds.json` (INITIAL GUESSES) | `qa_report.json` + `docs/openmontage/audit/**` only | `ffprobe`, `ffmpeg -f null`, `python -m json.tool`, pytest read-only | deny |
| `evidence-checker` | subagent | Claims, primary sources (NASA NTRS etc.), contradictions; maintains evidence ledger | evidence ledger file only | deny (no shell) | webfetch + websearch read |
| `footage-scout` | subagent | Runs project source adapters; classifies clips `rights_basis` + flags; unknown => not usable | asset candidate files only | adapter execution only | deny |

### Permissions summary

- **Orchestrator rule:** subagent proposes, orchestrator verifies, owner approves publishing. The orchestrator may delegate only to these four (+ existing built-ins). No two agents write the same file.
- **Fail closed:** if a check cannot run -> BLOCKED, never PASS.
- **Never claim** a command/commit/test you did not observe.
- **Output status** PASS|REVIEW|BLOCKED|FAILED on every check.
- **Read-only agents** use an explicit deny fallback and allow only trusted commands; task permissions limit which subagents an agent may call.

---

## Factory Sessions (OpenMontage Factory)

Permanent-work sessions follow the master plan at
`docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md`. At the start of every such
session, in this order:

1. `docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md` — the task source.
2. `docs/OPENMONTAGE_RESUME.md` — current state and the exact next action.
3. `docs/OPENMONTAGE_WORK_LOG.md` — history of completed work.
4. Repository reality (git status, code, tests) outranks stale notes.

After every verified step: update `OPENMONTAGE_RESUME.md`, append a dated
entry to `OPENMONTAGE_WORK_LOG.md`, and commit on a working branch (never
`main`, never force-push). Strict zero-cost mode is the default: an unpriced
or un-named route is BLOCKED, not free (`lib/zero_cost_gate.py`).
