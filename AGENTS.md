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

---

## OpenMontage Factory — instructions for Kilo Code

### Mission
Help build a reliable, maintainable and low-cost YouTube video production pipeline. Prioritize reproducible outputs, licensed assets, quality gates and human approval over speed or volume.

### Required startup routine
At the beginning of every task:
1. Inspect the project README, current task, git status and relevant architecture docs.
2. List available Skills and load the most relevant ones explicitly. For video factory work, check `youtube-factory-orchestrator`; also use the relevant specialist Skill(s).
3. State briefly which Skills/tools you will use and why. Do not claim a Skill was used unless its contents were actually read or its slash command/tool was invoked.
4. Inspect existing code before changing it. Prefer a small, testable change over broad rewrites.
5. If an external API, library, license or platform policy may have changed, consult official docs or repository source rather than guessing.

### Factory pipeline
Treat production as explicit stages:
idea -> research -> outline/script -> fact-check -> asset plan -> asset/license verification -> edit decision list -> render -> technical QA -> human review -> upload preparation -> human-approved publish -> analytics -> experiment.

Each stage should have inputs, outputs, status, errors, retry policy and provenance. Keep stages idempotent where possible. Use stable job IDs and write intermediate manifests so interrupted jobs can resume.

### Rights and provenance — hard requirement
- Use only footage/audio/images/fonts that are user-owned, public domain, or covered by a documented license allowing the intended use.
- Do not treat "free download", "royalty-free", or a search result as proof of permission.
- For every asset record source URL, creator, exact license/terms URL, retrieval date, attribution text, intended commercial use status, modification status, and a local file hash.
- If license terms are unclear, quarantine the asset and ask for human review.
- Do not scrape or download YouTube videos as stock footage. Do not bypass DRM, paywalls, access controls, cookies, private content, or platform restrictions.
- Never invent citations, quotes, statistics, license claims, footage provenance, or performance data.

### YouTube publishing safety
- Build draft metadata and upload manifests first.
- Never publish, schedule, delete, or change a live video/channel setting without explicit human approval in the current task.
- Keep OAuth credentials outside the repo and logs. Use least-privilege scopes.
- Respect YouTube API quota, spam/deceptive practices rules, copyright policy and monetization/reused-content policies. Do not promise monetization eligibility.
- Make publication state observable: draft / approved / uploaded-unlisted / public / failed.

### Engineering standards
- Prefer modular adapters: research, asset providers, rights ledger, timeline/EDL, render backend, QA, YouTube API, analytics.
- Do not hardcode provider-specific logic across the pipeline.
- Add tests for parsing, path safety, retries, metadata, license records and failure handling.
- Validate external input; protect against path traversal, shell injection, oversized downloads and malformed media.
- Use subprocess argument arrays, not shell-concatenated untrusted strings.
- Store secrets in environment variables or a secret manager. Never commit `.env`; provide `.env.example` without secrets.
- Use pinned versions/lockfiles for reproducible builds. Record tool versions in each job report.
- Avoid adding dependencies unless they solve a concrete problem and have acceptable licenses.

### Quality gate before calling a video complete
Check:
- file exists and is non-empty;
- duration, resolution, frame rate and codec match the target profile;
- audio stream exists, loudness/clipping are within configured limits;
- no missing media, black gaps, frozen frames or unintended silence;
- subtitles/captions match the final narration and timing;
- claims and factual details are sourced;
- thumbnail/title/description are consistent and not misleading;
- asset-rights manifest is complete;
- render report and hashes are saved.
If a check cannot be performed, mark it NOT_CHECKED, never PASS.

### Self-improvement
- Record repeatable failures in `docs/agent-improvement/LESSONS.md`.
- Propose changes in `docs/agent-improvement/BACKLOG.md`; do not silently change global config or install new MCP/plugins.
- Evaluate proposed changes on the same benchmark tasks in `docs/agent-improvement/EVALS.md`.
- Require a human review for new permissions, external services, uploads, publishing, licensing exceptions, dependency changes or destructive migrations.
- Measure quality, failure rate, human correction time, cost per finished minute, render time and rights coverage. Optimize only when measurements improve.

### Completion response
Report: files changed, commands run, tests and results, skipped checks, rights/security risks, and the next smallest useful step. Distinguish implemented code from plans and unverified assumptions.
