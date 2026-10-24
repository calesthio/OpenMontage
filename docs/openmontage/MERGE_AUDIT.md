# MERGE_AUDIT — M1 selective merge of KILO_CODE_YOUTUBE_FACTORY_MASTER.md

**Source reference:** `KILO_CODE_YOUTUBE_FACTORY_MASTER.md` (git commit `36e6595`, 1782 lines, retrieved from git history; not present in working tree). Treated as reference only — no bootstrap run, no install scripts, no vertical slice, no `docs/architecture/current-state.md`/`target-state.md` creation.

**Authoritative local sources of truth (conflicts resolved in their favor):**
- `docs/openmontage/RIGHTS_MODEL.md` (rights/provenance)
- `docs/openmontage/QA_SPEC.md` (QA statuses PASS|REVIEW|BLOCKED|FAILED)
- `AGENTS.md` (project instructions, publishing safety, pipeline stages, self-improvement)
- `docs/OPENMONTAGE_PLAN_V3_2.md` (plan v3.2: max 3 runtime repos/engines, zero-secrets rule for v1, HyperFrames + ffmpeg stack)
- `tools/qa/qc.py` (QA implementation)

**Mode:** AUDIT-AND-RECONCILE. Installed skills and docs/agent-improvement already exist; compare, do not overwrite; propose, do not apply AGENTS.md changes.

---

## Table A — Master file's 9 skills vs our installed skills/tools/docs

| master item | our equivalent (path or NONE) | verdict | decision | reason |
|---|---|---|---|---|
| `kilo-self-improvement` | `.kilo/skills/kilo-self-improvement/SKILL.md` | OVERLAP | MERGE-IDEAS-ONLY | Already installed; name/description match master exactly. Adapt to reference our `docs/agent-improvement/EVALS.md` and never touch global config/permissions/skills automatically. |
| `youtube-factory-orchestrator` | `.kilo/skills/youtube-factory-orchestrator/SKILL.md` | OVERLAP | SKIP | Already installed; matches master name/description. Duplicates project routine already in `AGENTS.md` §Required startup routine. |
| `youtube-research-and-scripting` | `.kilo/skills/youtube-research-and-scripting/SKILL.md` | OVERLAP | SKIP | Already installed; matches master name/description. |
| `licensed-footage-audit` | `.kilo/skills/licensed-footage-audit/SKILL.md` | OVERLAP | SKIP | Already installed; matches master name/description. `RIGHTS_MODEL.md` is the source of truth for rights classification (fail-closed, `rights_basis` enum). |
| `video-pipeline-ffmpeg` | `.kilo/skills/video-pipeline-ffmpeg/SKILL.md` | OVERLAP | SKIP | Already installed; matches master name/description. FFmpeg is our render backend per plan v3.2. |
| `video-rendering-remotion` | `.kilo/skills/video-rendering-remotion/SKILL.md` | OVERLAP | SKIP | Already installed but render stack = ffmpeg + HyperFrames per plan v3.2 (HyperFrames Apache-2.0). Remotion optional only, license-checked. See CONFLICT #1. |
| `youtube-quality-gate` | `.kilo/skills/youtube-quality-gate/SKILL.md` | OVERLAP | SKIP | Already installed; matches master name/description. `QA_SPEC.md` + `tools/qa/qc.py` are our QA implementation. |
| `youtube-publishing-analytics` | `.kilo/skills/youtube-publishing-analytics/SKILL.md` (installed) + `docs/openmontage/` stub | OVERLAP | SKIP | Already installed but per M1 = stub only in `docs/openmontage/`, not an active skill. No OAuth, no active installs now. See CONFLICT #2. |
| `youtube-factory-self-improvement` | `.kilo/skills/youtube-factory-self-improvement/SKILL.md` | OVERLAP | SKIP | Already installed; matches master name/description. Project self-improvement already in `AGENTS.md` §Self-improvement. |

**Ideas to port (extracted from master checklists, owner review):**
- Master `youtube-factory-orchestrator` item 6: stable job IDs, structured logs, manifests — partially covered by `video-job-manifest.json` template in master; not yet materialized locally.
- Master `licensed-footage-audit`: SHA-256 checksum + evidence path per asset — covered by `RIGHTS_MODEL.md` evidence recording but `asset-rights-ledger.csv` template not yet materialized locally.
- Master `youtube-publishing-analytics`: publication states DRAFT/QA_PASSED/AWAITING_APPROVAL/UPLOADING/UPLOADED_UNLISTED/PUBLIC_APPROVED/FAILED — not yet implemented; stub only.
- Master `youtube-quality-gate` editorial checks (title/thumbnail match, synthetic content disclosures) — not yet in `QA_SPEC.md` check table.
- Master `kilo-self-improvement` step 9: document date/issue/evidence/change/result/rollback — seeded into `LESSONS.md` below.

---

## Table B — Master rule blocks vs our docs

| master rule block | our equivalent | verdict | decision | reason |
|---|---|---|---|---|
| rights/provenance | `docs/openmontage/RIGHTS_MODEL.md` | OVERLAP | SKIP | `RIGHTS_MODEL.md` is more specific (NASA source policy, `rights_basis` ∈ {explicit_license, source_policy_us_gov, unknown}, fail-closed, flags). Master is general. No conflict; `RIGHTS_MODEL.md` wins. |
| publishing safety | `AGENTS.md` §YouTube publishing safety | OVERLAP | SKIP | Near-identical: draft manifests first, explicit human approval before publish/schedule/delete/channel change, OAuth outside repo/logs, least-privilege scopes, observable publication state. |
| pipeline stages | `AGENTS.md` §Factory pipeline + `docs/OPENMONTAGE_PLAN_V3_2.md` | OVERLAP | SKIP | Same 12-stage pipeline (idea→...→experiment). Plan v3.2 is authoritative for milestone ordering and stack limits. |
| definition of done | `docs/openmontage/QA_SPEC.md` + `AGENTS.md` §Quality gate | CONFLICT | SKIP | Master: mark unrun checks NOT_CHECKED, never PASS. QA_SPEC statuses are PASS\|REVIEW\|BLOCKED\|FAILED (no NOT_CHECKED; unable to run → BLOCKED). Map: master NOT_CHECKED ≈ QA_SPEC BLOCKED when check cannot run. Do NOT replace our statuses. |
| self-improvement | `AGENTS.md` §Self-improvement + `docs/agent-improvement/` (LESSONS/BACKLOG/EVALS/CHANGELOG) | OVERLAP | SKIP | Both use project-level LESSONS.md/BACKLOG.md/EVALS.md/CHANGELOG.md, evidence-based, no silent global config changes. |
| MCP/tool list | `docs/OPENMONTAGE_PLAN_V3_2.md` (§max 3 runtime, §zero-secrets) | CONFLICT | SKIP | Master lists GitHub MCP, Serena, jCodeMunch, YouTube MCP, n8n, Context7 (+Superpowers, Playwright, Exa). Plan v3.2 caps at max 3 runtime repos/engines + zero secrets in v1. Do not add any MCP. See CONFLICT #2. |
| global AGENTS/global skill paths vs project-level only | `AGENTS.md` + `.kilo/skills/` (project-level) | CONFLICT | SKIP | Master suggests `~/.config/kilo/AGENTS.md` (global) and `~/.kilo/skills/` (global). M1 is project-level only: `~/.config/kilo`, `kilo.json`/`kilo.jsonc` untouched; skills live in `.kilo/skills/`. See CONFLICT #3. |

---

## Conflicts flagged (explicit)

**CONFLICT #1 — Remotion vs our HyperFrames decision.**
Master includes `video-rendering-remotion` skill and Remotion in the recommended stack (`MCP_AND_TOOLS.md`, `IMPLEMENTATION_ROADMAP.md`). Plan v3.2 / our stack = HyperFrames (Apache-2.0) + ffmpeg; Remotion is optional and requires commercial-license check before any use. Decision: do not install/activate Remotion; render stack = ffmpeg + HyperFrames. Skill `video-rendering-remotion` remains installed but inactive (SKIP).

**CONFLICT #2 — Extra MCPs vs max 3 runtime + zero secrets in v1.**
Master `MCP_AND_TOOLS.md` / `KILO_SELF_IMPROVEMENT_PLAN.md` recommends Context7, GitHub MCP, Serena, jCodeMunch, YouTube MCP, n8n, Playwright MCP, Exa MCP, Superpowers MCP. Plan v3.2: maximum 3 runtime repos/engines, zero secrets in v1, no secrets committed/logged/exposed. Decision: do not install any MCP; no OAuth now; `youtube-publishing-analytics` is stub-only. All MCPs remain NOT_CHECKED/uninstalled.

**CONFLICT #3 — Global AGENTS/global skill paths vs project-level only.**
Master `KILO_SELF_IMPROVEMENT_PLAN.md` / `install-unix.sh` targets `~/.config/kilo/AGENTS.md` (global AGENTS.md) and `~/.kilo/skills/` (global skills). M1 constraint: project-level docs and skills only; `~/.config/kilo`, `kilo.json`/`kilo.jsonc` untouched. Decision: keep `AGENTS.md` project-level (unmodified), skills in `.kilo/skills/` only. No global writes.

**CONFLICT #4 — Master NOT_CHECKED wording vs our qa_report statuses.**
Master definition of done and QA report template use `NOT_CHECKED` for unrun checks. `QA_SPEC.md` §2 and `tools/qa/qc.py` line 46 define valid statuses as PASS|REVIEW|BLOCKED|FAILED (+NOT_RUN for optional checks whose inputs are absent); fail-closed → unable to run = BLOCKED. There is no NOT_CHECKED status in our schema. Mapping: master NOT_CHECKED ⇒ our BLOCKED (when a check cannot be performed) / NOT_RUN (when input absent). Decision: keep our statuses (PASS|REVIEW|BLOCKED|FAILED/NOT_RUN); do NOT introduce NOT_CHECKED. Map documented here for owner awareness.

---

## Table C — Skill name/description front-matter verification (observed)

All 9 installed `.kilo/skills/<name>/SKILL.md` files have `name:` equal to folder name and `description:` matching the master file's embedded resource exactly. Verified via `grep` on each file; no mismatches found.

---

## M1 decisions summary

- **Installed (adapted):** `kilo-self-improvement` — already present; adapted to reference `EVALS.md`, project-level only, no global writes.
- **Skipped (already installed, duplicates):** `youtube-factory-orchestrator`, `youtube-research-and-scripting`, `licensed-footage-audit`, `video-pipeline-ffmpeg`, `video-rendering-remotion`, `youtube-quality-gate`, `youtube-publishing-analytics`, `youtube-factory-self-improvement`.
- **Not installed:** no MCP servers (GitHub, Serena, jCodeMunch, YouTube MCP, n8n, Context7, Superpowers, Playwright, Exa); no global `~/.config/kilo` writes; no `kilo.json`/`kilo.jsonc` changes; no paid routes; no secrets.
- **Stub only:** `youtube-publishing-analytics` in `docs/openmontage/` (after first published video; manual publish only; no OAuth now).
