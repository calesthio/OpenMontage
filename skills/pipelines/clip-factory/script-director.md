# Script Director - Clip Factory Pipeline

## When To Use

This stage converts the long-form source into a ranked candidate list and then into the final clip selections. You are mining for standout moments, not summarizing the entire source.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/script.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["idea"]["brief"]` | Batch goals and platform targets |
| Tools | `transcriber`, `scene_detect` | Transcript-first selection and visual checks |

## Process

### 1. Transcribe The Full Source

Use `transcriber` first. The transcript is the search surface for hooks, not an afterthought.

Use `scene_detect` only to sanity-check visual boundaries, speaker changes, or slide changes near promising moments.

### 2. Score Candidate Moments

Use the brief's ranking criteria and evaluate each moment on:

- `hook`
- `coherence`
- `value`
- `energy`
- `platform_fit`

This mirrors the way modern clipping products talk about virality and clip quality, while keeping the judgment transparent.

### 3. Apply The Standalone Test

Every approved clip must make sense to a cold viewer.

Reject or widen clips that contain:

- unresolved pronouns,
- references to earlier context,
- long lead-ins before the point lands,
- endings that stop before the payoff.

### 4. Select The Final Batch

Pick the smallest set that best satisfies the batch goal.

Maintain diversity across:

- source sections,
- speakers,
- clip families,
- energy levels.

### 5. Use Metadata For Ranking Truth

The script schema is small, so store the richer batch analysis in `script.metadata`.

Recommended metadata keys:

- `candidate_clips`
- `selected_clip_ids`
- `ranking_model`
- `rejected_candidates`
- `source_coverage_map`
- `platform_assignments`

Each candidate should record:

- source in/out,
- hook text,
- reason selected or rejected,
- scoring dimensions,
- likely crop viability.

### 6. Quality Gate

- the top-ranked clips are genuinely the strongest, not just the earliest found,
- every selected clip passes the standalone test,
- the set covers the source deliberately instead of clustering in one section,
- low-quality candidates are rejected honestly.

### Mid-Production Fact Verification

If you encounter uncertainty during script writing:
- Use `web_search` to verify factual claims before committing them to the script
- Use `web_search` to find reference images for visual accuracy
- Log verification in the decision log: `category="visual_accuracy_check"`

Every factual claim in the script should be traceable to the `research_brief`.
If you make a claim that isn't in the research, do additional research and
add the source. Do not invent statistics, dates, or attributions.

## Common Pitfalls

- Trusting first-pass candidate timestamps without transcript-level review.
- Selecting too many calm, same-energy clips.
- Preserving chronological order instead of ranking by quality.
- Treating transcript quality issues as minor when they affect selection accuracy.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
