# OpenMontage Factory — Plan v3.2

**Version:** 3.2  
**Date:** 2026-10-16  
**Supersedes:** master plan v1.0 / v3.1 (docs/OPENMONTAGE_FACTORY_MASTER_PLAN_RU (1).md)  
**Scope:** Docs/markdown only — no application code, no installs, no network except reading Kilo docs.

---

## 1. Niche

Aviation & spaceflight test history on free / public-domain archive footage.  
Linked spec: `docs/openmontage/NICHE_DECISION.md`, `docs/openmontage/NICHE_PROFILE_SPEC.md`.  
The niche is CONFIG (`niche_profile.yaml`), not hardcoded.

## 2. Stack

Maximum 3 runtime repos/engines:
1. OpenMontage (AGPL-3.0)
2. HyperFrames (Apache-2.0; original graphics layers first)
3. Kokoro-82M (model; license verified from its own files)

Everything else = pinned skills or pattern-only references. A 4th runtime repo requires owner approval.

## 3. Patterns adopted

- Fail-closed QC gates with authoritative resume.
- EDL with per-cut written rationale.
- Pacing lint (shot-length variation, J/L split edits, pause lengths).
- Idea stage: 3 topic concepts -> 1 selected.

## 4. asset_record additions

Add to every asset record:
- `rights_basis` (`explicit_license` | `source_policy_us_gov` | `unknown`)
- `identifiable_persons` (flag)
- `logo_visible` (flag)
- `third_party_credit` (flag)
- `archive_id`
- `archive_caption`

Rule: `rights_basis == unknown` => not usable (fail closed).

## 5. New stage 0 — topic viability gate

Gate (before scripting): >= 10 usable licensed video clips AND >= 3 primary documents.  
Footage-aware scripting: script only after the viability gate passes.

## 6. Go/No-Go additions

- "added value" gate (narration coverage, original diagrams per 90 s, unannotated clip limits).
- "voice license known" gate (Piper/Kokoro voice license confirmed before publish).

## 7. Publishing

Manual only. Un-audited API projects force private. No automatic publish to YouTube until explicit human approval.

## 8. Speed

- Per-stage wall time / resource logging.
- Draft-render mode.
- Contact-sheet review.
- No premature optimization.

## 9. Zero-secrets rule for v1

No secrets committed, logged, or exposed. API keys not required for the default path; paid/key-gated sources are optional extras.

## 10. Milestone order

P+ -> C1 (rights/clips) -> D1 (voice/audio/editing doctrine) -> Q (QC tool with TDD + qa_report.json) -> E (30–60 s slice) -> F (6–10 min pilot).

Milestones A, B, S done (mark with real hashes from `git log`):
- A: `dad575d` docs(milestone-a): niche reality check + aviation-spaceflight profile spec
- B: `79b2cfc` docs(milestone-b): topic viability probe 2026-10-16 (3 topics, NO-GO x3)
- S: `ff35182` docs(milestone-s): tooling audit + 7 pinned skills (.kilo/skills)

P+ (this milestone): docs + agent team + QA spec.

## 11. Open risks

- Piper voice license (commercial use unstated).
- Rights basis for NASA clips (no explicit license statement on NIX items).
- Content ID for music.
- Competition unmeasured.
- Monetization eligibility unverified.

## 12. Changelog

### v3.2 — 2026-10-16 — Milestone P+ (docs + agent team + QA spec)

- Added Plan v3.2: niche (aviation & spaceflight test history), max-3-runtime stack, fail-closed QC gates, EDL rationale, pacing lint, 3-concepts->1-selected idea stage.
- `asset_record`: added rights_basis, identifiable_persons, logo_visible, third_party_credit, archive_id, archive_caption; unknown => not usable.
- New stage 0 topic viability gate (>=10 usable licensed clips, >=3 primary docs) + footage-aware scripting.
- Go/No-Go: added "added value" gate and "voice license known" gate.
- Publishing: manual only; unaudited API projects force private.
- Speed: per-stage wall time/resource logging, draft-render mode, contact-sheet review; no premature optimization.
- Zero-secrets rule for v1.
- Milestone order: P+ -> C1 -> D1 -> Q -> E -> F. Marked A, B, S done with real git hashes.
- Open risks: Piper voice license, NASA clip rights basis, Content ID for music, competition unmeasured, monetization eligibility.
- Created `.kilo/agents/{editor, qa-reviewer, evidence-checker, footage-scout}.md` (mode: subagent, permission rules per Kilo 7.8.12 schema).
- Created `docs/openmontage/QA_SPEC.md` (hard checks, qa_report.json schema, thresholds INITIAL GUESSES, gate mapping, added-value metrics).
- No application code, no installs, no network except reading Kilo docs.
