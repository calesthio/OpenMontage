# Final Render Review Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only final render review package before delivery export.

**Architecture:** A new `scripts/review_reference_final.py` validates the final render report, probes the final MP4 when possible, and writes JSON/Markdown review artifacts under `artifacts/reference-final-review/`. Existing status and snapshot scripts expose this review step before the guarded delivery export command.

**Tech Stack:** Python standard library, `ffprobe` when available, pytest.

---

### Task 1: Review Script Contract

**Files:**
- Create: `tests/scripts/test_review_reference_final.py`
- Create: `scripts/review_reference_final.py`

- [ ] Write failing tests for generating JSON and Markdown review artifacts from a rendered non-dry-run report.
- [ ] Run `.venv/bin/python -m pytest tests/scripts/test_review_reference_final.py -q` and confirm the script is missing.
- [ ] Implement report discovery, validation, media probing fallback, checklist, and CLI output.
- [ ] Re-run `.venv/bin/python -m pytest tests/scripts/test_review_reference_final.py -q`.

### Task 2: Status Integration

**Files:**
- Modify: `tests/scripts/test_reference_project_status.py`
- Modify: `scripts/reference_project_status.py`

- [ ] Update the final-render-ready test so the first next command is `scripts/review_reference_final.py`.
- [ ] Add coverage for an existing final review report exposing export as the next guarded step.
- [ ] Run the status tests and confirm the changed expectations fail.
- [ ] Add `final_review_report` discovery and status handling without bypassing `APPROVE FINAL DELIVERY`.
- [ ] Re-run the status tests.

### Task 3: Snapshot Integration

**Files:**
- Modify: `tests/scripts/test_reference_project_snapshot.py`
- Modify: `scripts/reference_project_snapshot.py`

- [ ] Update snapshot tests to include `final_review_report` and a local review UI action.
- [ ] Run the snapshot tests and confirm the changed expectations fail.
- [ ] Add artifact mapping, phase mapping if needed, and UI action risk metadata.
- [ ] Re-run the snapshot tests.

### Task 4: Verification

**Files:**
- Check: all changed files

- [ ] Run targeted script tests for review, status, and snapshot.
- [ ] Run `git diff --check`.
- [ ] Run the review script against `projects/reference-f64e5145` to produce the local review package.
- [ ] Re-run project status and report the next safe step.
