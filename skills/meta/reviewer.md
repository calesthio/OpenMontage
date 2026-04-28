# Reviewer — Meta Skill

## When to Use

After completing any pipeline stage's work — before checkpointing. You are the quality gate between "work done" and "work accepted." This skill replaces the Python reviewer class with an instruction-driven self-review protocol.

Every stage gets reviewed. No exceptions. The review quality determines whether the final video is worth watching.

## Critique Quality (CHAI Rules)

> Findings ≠ critiques. A finding identifies a problem; a critique tells the next stage how to fix it. The CMU/Harvard CHAI study ("Building a Precise Video Language with Human-AI Oversight", arXiv 2604.21718v2) showed that critique quality, measured on three axes, directly governs downstream output quality. Apply all three to every reviewer pass.
>
> **Accurate.** Every finding must reference a concrete artifact field, line number, or visible asset frame. Forbid hallucinated criticism — if you cannot point to where the problem is, you are guessing.
>
> **Complete.** A reviewer pass that catches one mistake while missing a second is worse than scoring "needs another pass" and continuing. If you find one critical issue, scan for the rest of the same class before returning. Pattern-match: where else in this artifact could the same mistake be hiding?
>
> **Constructive.** Every "critical" finding MUST propose a concrete fix, not just identify the problem. "Caption is wrong" → "Caption says 'man on the right'; the man is on the left of the frame. Replace with 'the man on the left of the frame.'" If you cannot propose a fix, label the finding as "investigation" not "critical."
>
> Removing any of these three properties measurably hurts pipeline output. The reviewer is the choke point — be rigorous.

## Protocol

### Step 1: Load Review Context

Before reviewing, gather:
1. **Review focus items** from the pipeline manifest for this stage (`review_focus` field)
2. **Success criteria** from the manifest for this stage (`success_criteria` field)
3. **Active playbook** quality rules
4. **The artifact** produced by the stage

### Step 2: Schema Validation

First, the non-negotiable check:
- Validate the artifact against its JSON schema (`schemas/artifacts/<name>.schema.json`)
- If schema validation fails, this is a **critical** finding — fix immediately, do not proceed

### Step 3: Review Against Focus Items

For each `review_focus` item from the manifest:
1. Evaluate the artifact against this specific criterion
2. Assign a severity:
   - **critical** — Must fix before proceeding. The artifact is broken, incomplete, or dangerously wrong. **Per CHAI rules, every critical finding MUST carry a `proposed_fix` (concrete replacement text, exact field value, or specific corrective action). A critical finding without a proposed fix is downgraded to `investigation`.**
   - **suggestion** — Should fix. Improves quality significantly but doesn't block progress. **Suggestions MUST carry a `proposed_change` describing how to improve.**
   - **nitpick** — Could fix. Minor polish that's nice-to-have. May stand alone without a proposed change.
   - **investigation** — A real concern but you cannot pinpoint the fix. Surface it for the next round; do not block on it.
3. Write a specific, actionable finding (not vague)

**Good finding:** "Section 3 narration is 180 words for a 10-second window — that's 1080 wpm, impossible to speak. Cut to 25 words."
**Bad finding:** "Script might be too long."

### Step 4: Cross-Check Against Playbook

If a style playbook is active, verify:
- [ ] Color references match playbook palette
- [ ] Transition types are in the playbook's allowed set
- [ ] Pacing rules are respected (min/max durations)
- [ ] Asset descriptions include playbook style cues
- [ ] Quality rules are not violated

Each violation is a **suggestion** severity finding.

### Step 5: Evaluate Success Criteria

For each `success_criteria` item from the manifest:
- Is the criterion met? (yes/no/partial)
- If not met, create a **critical** finding

### Step 6: Make a Decision

Count findings by severity:

| Scenario | Action |
|----------|--------|
| 0 critical, any suggestions/nitpicks | **Pass** — proceed to checkpoint. Note suggestions for the record. |
| 1+ critical findings | **Revise** — fix all critical findings, then re-review (max 2 rounds). |
| After 2 revision rounds, still critical | **Pass with warnings** — proceed anyway, note unresolved issues. Never block indefinitely. |

### Step 7: Record Review

Structure your review as:

```
## Review: [stage_name] — Round [N]

**Decision:** PASS / REVISE / PASS_WITH_WARNINGS

### Findings

1. [CRITICAL] Title of finding
   - Description: What's wrong
   - Action: What to fix
   - Status: pending / fixed / accepted / deferred

2. [SUGGESTION] Title of finding
   - Description: What could be better
   - Action: How to improve
   - Status: pending / accepted / deferred

### Summary
- Critical: N (N fixed)
- Suggestions: N
- Nitpicks: N
- Playbook violations: N
- Success criteria met: N/M
```

## Key Principles

1. **Be specific, not vague.** "The hook is weak" is useless. "The hook asks a question but doesn't create urgency — try leading with the surprising stat from key_point #2" is actionable.

2. **Critical means critical.** Don't inflate severity. A missing schema field is critical. A slightly wordy paragraph is a suggestion. A comma splice is a nitpick.

3. **Two rounds max.** The goal is shipping, not perfection. After two revision rounds, pass with warnings and move on. Perfectionism kills pipelines.

4. **Review the artifact, not the process.** You're checking the output, not how it was produced. If the brief is compelling, it doesn't matter if the agent used an unusual approach.

5. **Playbook is law.** If the playbook says "no more than 3 colors on screen," that's not a suggestion — it's a constraint. Violations are always flagged.

## Stage-Specific Review Guidance

| Stage | What matters most |
|-------|-----------------|
| research | Source diversity, claim verifiability, visual reference quality |
| proposal | Delivery promise clarity, renderer family AND render runtime selection, music/voice plan, decision log started |
| idea | Hook uniqueness, research depth, angle diversity |
| script | Timing accuracy, narrative arc, enhancement cue density |
| scene_plan | Full coverage, visual variety, asset feasibility, slideshow risk score |
| assets | File existence, style consistency, budget adherence |
| edit | Timeline coverage, audio sync, subtitle presence, delivery promise compliance |
| compose | Playability, duration accuracy, audio quality, pre-compose validation pass |
| publish | SEO quality, metadata completeness, export packaging |

## Reference Alignment Review

Run at **every stage** when a VideoAnalysisBrief exists (reference-driven production).

### Checks:

1. **Grounding check:** Does the output reference specific findings from the
   VideoAnalysisBrief, or is it making things up about the reference?
   - Proposal mentions "fast pacing" but reference pacing_style is "slow_contemplative" → **CRITICAL**
   - Script claims reference has narration but VideoAnalysisBrief shows no narration → **CRITICAL**

2. **Differentiation check:** Does each concept/scene have a clear creative
   difference from the reference, or is it a copy?
   - Proposal is a carbon copy of the reference (same topic, same structure, same treatment) → **CRITICAL**
   - At least one element per concept MUST differ from the reference → **SUGGESTION** if weak
   - Creative differentiation seeds from the brief should be reflected in proposals

3. **Promise preservation:** Are the elements the user said they loved about the
   reference still present in the output?
   - User said "I love the pacing" but scene_plan has 2x longer scenes → **SUGGESTION**
   - User said "keep the hook style" but script uses a different hook → **SUGGESTION**

4. **Cost alignment:** Is the cost estimate still accurate, or has scope crept?
   - If actual spend exceeds estimate by >30% without user re-approval → **CRITICAL**
   - If new assets were added beyond the approved proposal → **SUGGESTION**

### Severity:
- Factual errors about the reference video: **CRITICAL**
- Carbon copy with no differentiation: **CRITICAL**
- Weak differentiation (surface-level changes only): **SUGGESTION**
- User preference not honored: **SUGGESTION**
- Cost drift >30%: **CRITICAL**

## Slideshow Risk Review

Run at **scene_plan** and **edit** stages. Use `lib/slideshow_risk.py` to compute the score.

### At scene_plan stage:
1. Compute `score_slideshow_risk(scenes, renderer_family=renderer_family)`
2. If verdict is **"fail"** (average ≥ 4.0): **CRITICAL** — scene plan must be revised before proceeding
3. If verdict is **"revise"** (average ≥ 3.0): **SUGGESTION** — flag specific dimensions scoring ≥ 3.5
4. If verdict is **"strong"** or **"acceptable"**: note in review summary, no finding needed

### At edit stage:
1. Recompute with full edit_decisions: `score_slideshow_risk(scenes, edit_decisions, renderer_family)`
2. Same thresholds apply — if the edit stage made things worse (higher score than scene_plan), flag it

### What to flag per dimension:
| Dimension | What to say when score ≥ 3.0 |
|-----------|------------------------------|
| repetition | "X scenes use the same layout/shot size — vary the visual grammar" |
| decorative_visuals | "X scenes have no stated purpose (no information_role or shot_intent)" |
| weak_motion | "Camera movement exists but lacks narrative justification" |
| weak_shot_intent | "X scenes are missing shot_intent — why does this frame exist?" |
| typography_overreliance | "X% of scenes are text/stat cards — video feels like animated slides" |
| unsupported_cinematic_claims | "Claiming cinematic but missing hero moments / lighting / movement" |

## Decision Log Review

Run at **every stage** after proposal. The decision log (`schemas/artifacts/decision_log.schema.json`) is a cumulative audit trail.

### Checks:
1. **Existence**: Does the checkpoint reference a `decision_log_ref`? If not after proposal stage, flag as **SUGGESTION**.
2. **Coverage**: Does every major choice have an entry? Key decisions that MUST be logged:
   - Provider selection (which image/video/audio tool and why)
   - Style/playbook selection
   - Music track selection
   - Voice selection
   - Renderer family selection
   - Any fallback or downgrade (e.g., motion → still)
3. **Quality**: Each decision should have:
   - At least 2 `options_considered` (not just the one picked)
   - A `reason` that isn't boilerplate ("best option" is not a reason)
   - Correct `confidence` (0.0–1.0) — flag if everything is 1.0 (unrealistic)
4. **User visibility**: Decisions marked `user_visible: true` should be ones the user would actually care about (not internal routing)

### Severity:
- Missing decision log after proposal: **SUGGESTION** (first time), **CRITICAL** (if still missing at edit stage)
- Decision with only 1 option considered: **SUGGESTION** — "Log rejected alternatives for auditability"
- All decisions at confidence 1.0: **SUGGESTION** — "Unrealistic confidence — at least provider selection involves tradeoffs"

## Creative Differentiation Review

Run at **scene_plan** and **edit** stages. Prevents the "every video looks the same" failure mode.

### Checks:
1. **Variation check** (scene_plan only): Use `lib/variation_checker.py` → `check_scene_variation(scenes)`.
   - If verdict is "poor" (score ≤ 2): **CRITICAL** — "Scene plan lacks variety: [list violations]"
   - If verdict is "fair" (score ≤ 3): **SUGGESTION** — note specific suggestions from the checker

2. **Playbook alignment**: Is the active playbook appropriate for this content?
   - Cinematic trailer using "clean-professional" theme → flag mismatch
   - Educational explainer using "anime-ghibli" theme without user request → flag

3. **Shot language completeness** (scene_plan):
   - Every scene should have at least `shot_size` and `shot_intent`
   - Hero moments should have full shot_language (all 6 fields)
   - Flag scenes with empty shot_language as **SUGGESTION**

4. **Renderer family match** (edit stage):
   - Does `renderer_family` in edit_decisions match what was set at proposal?
   - If changed without documented reason in decision log → **CRITICAL**

5. **Render runtime match** (edit and compose stages):
   - `render_runtime` in edit_decisions must match proposal_packet.production_plan.render_runtime
   - If changed without a `render_runtime_selection` decision logged in decision_log → **CRITICAL**
   - At compose stage, `final_review.checks.promise_preservation.runtime_swap_detected` must be `false`. If `true` without an approved `render_runtime_selection` decision → **CRITICAL**
   - Runtime unavailable at compose time is not an excuse for silent swap — the correct behavior is to escalate, get approval, log a decision, then run.

6. **Runtime selection presented both options** (proposal stage, MANDATORY):
   - Query `video_compose.get_info()["render_engines"]`. If both `remotion` and `hyperframes` show `True`, the `render_runtime_selection` decision in `decision_log` MUST have BOTH runtimes in `options_considered`.
   - A `render_runtime_selection` with only one runtime in `options_considered` when both were available on the machine → **CRITICAL**. The agent silently defaulted; the user was not presented the alternative. Re-open the proposal stage and present both.
   - If only one runtime was available, `options_considered` must still list the unavailable one with `rejected_because: "runtime not available on this machine"` — otherwise the audit trail loses the fact that the choice was constrained, not discretionary.
   - Per AGENT_GUIDE.md > "Present Both Composition Runtimes (HARD RULE)": the pipeline's suggested "default" runtime is NOT a license to skip the conversation with the user.

## Delivery Promise Review

Run at **edit** and **compose** stages. Uses `lib/delivery_promise.py`.

### At edit stage:
1. Extract delivery promise from proposal packet or edit_decisions metadata
2. Run `promise.validate_cuts(cuts)` against the resolved cut list
3. If `valid` is False: **CRITICAL** — "Delivery promise violation: [violations]"
4. Check `motion_ratio`: if a motion-led promise has < 50% motion cuts, flag even if technically valid

### At compose stage:
1. The `_pre_compose_validation()` in video_compose.py enforces this automatically
2. Review should verify the validation was not bypassed (check render report for warnings)
3. If render succeeded despite low motion ratio on a motion-led promise, flag as **SUGGESTION**

## Source Understanding Review

Run at **research** and **proposal** stages when user-supplied media files exist.

### Checks:
1. **Existence**: If user-supplied files were provided to the project, does a `source_media_review` artifact exist?
   - If user media exists but no `source_media_review`: **CRITICAL** — "User supplied media but the agent did not inspect it before planning. Run `lib/source_media_review.review_source_media()` before proceeding."
2. **Actual inspection**: Does every file entry have `reviewed: true` and a non-empty `technical_probe`?
   - If `reviewed` is missing or `technical_probe` is empty: **CRITICAL** — "The source_media_review claims review but contains no probe data. The file was not actually inspected."
3. **Planning reflection**: Do the `planning_implications` appear in the proposal's production plan?
   - If quality risks were identified (e.g. low resolution, mono audio) but the proposal doesn't mention them: **SUGGESTION** — "Source media has quality risks that the proposal does not address."
4. **Content accuracy**: Does the plan rely on content that the source media does not actually contain?
   - E.g. plan assumes interview dialogue but transcript_summary shows no speech: **CRITICAL** — "Plan assumes dialogue but source media contains no speech."
5. **No hallucinated content**: The agent must not infer unsupported content from filenames alone. If `content_summary` says "interview footage" but the probe only shows 3s of silent video, flag as **CRITICAL**.

### Severity:
- Missing `source_media_review` when user files exist: **CRITICAL** at proposal stage
- Unreviewed files (no probe): **CRITICAL**
- Plan doesn't reflect quality risks: **SUGGESTION**
- Plan assumes content not in source: **CRITICAL**

## Final Self-Review Review

Run at **compose** and **publish** stages. Ensures the agent reviewed the actual rendered output.

### At compose stage:
1. **Existence**: Does a `final_review` artifact exist alongside the `render_report`?
   - If missing: **CRITICAL** — "Compose produced a render_report but no final_review. The agent must inspect the rendered output before presenting it."
2. **Status check**: What is `final_review.status`?
   - `pass` → OK, proceed
   - `revise` → The agent should have fixed issues before presenting. If the pipeline continued anyway: **CRITICAL** — "Self-review found revise-worthy issues but the agent presented anyway."
   - `fail` → The pipeline MUST NOT proceed. If it did: **CRITICAL**
3. **Check completeness**: All 5 required checks must have data:
   - `technical_probe` must show a valid container with plausible duration/resolution
   - `visual_spotcheck` must have `frames_sampled >= 4`
   - `audio_spotcheck` must report narration/music presence
   - `promise_preservation` must confirm `delivery_promise_honored`
   - `subtitle_check` must report presence/absence
   - Any check with missing data: **SUGGESTION** — "Self-review check [X] has incomplete data"
4. **Promise preservation**: If `promise_preservation.silent_downgrade_detected` is true: **CRITICAL** — "Self-review detected silent downgrade from motion-led to still-led."

### At publish stage:
1. Verify that `final_review` was passed through as a required artifact
2. If `final_review.status` is not `pass`: **CRITICAL** — "Cannot publish with a non-passing self-review"
3. If `final_review.issues_found` is non-empty and `recommended_action` is not `present_to_user`: **SUGGESTION** — "Self-review found issues; verify they were resolved before publishing"
