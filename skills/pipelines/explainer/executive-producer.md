# Executive Producer — Explainer Pipeline

## When to Use

You are the **Executive Producer (EP)** for a generated explainer video. You orchestrate the entire pipeline serially: spawning each stage director, reviewing their output, and either passing it forward or sending it back for revision. You are the stateful brain; the directors are stateless workers.

**You replace the default parallel/sequential execution model.** Instead of running all stages blindly, you exercise judgment at every gate.

## Why This Exists

The parallel pipeline produces "technically correct" but low-quality videos because:
- No feedback loop when TTS narration is too long for the video duration
- No style consistency enforcement across image generation calls
- No A/V sync validation before the final render
- No budget reallocation when early stages overspend
- No ability to send a single stage back without re-running everything

The EP solves all of these by maintaining cumulative state and applying judgment at each gate.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/animated-explainer.yaml` | Stage definitions, review focus, success criteria |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution knowledge |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |
| Tools | Full tool registry | Available capabilities |

## Cumulative State

The EP maintains a running state object that flows through the entire pipeline:

```
EP_STATE:
  pipeline: animated-explainer
  playbook: <selected playbook name>
  target_duration_seconds: <from proposal_packet.selected_concept>
  budget_total_usd: <from proposal_packet.approval.approved_budget_usd or configured limit>
  budget_spent_usd: 0.0
  budget_remaining_usd: <budget_total>

  # Accumulated from each stage (8 stages)
  artifacts:
    research: null      # → research_brief
    proposal: null      # → proposal_packet (includes approval gate)
    script: null        # → script
    scene_plan: null    # → scene_plan
    assets: null        # → asset_manifest
    edit: null          # → edit_decisions
    compose: null       # → render_report
    publish: null       # → publish_log

  # Pre-production context (carried forward from research + proposal)
  research_brief: null         # full research_brief artifact — available to all downstream stages
  selected_concept: null       # the approved concept from proposal_packet
  production_plan: null        # the approved tool/provider plan
  approved_budget_usd: null    # explicit user-approved spend cap

  # Cross-stage tracking
  narration_durations: {}    # section_id → actual_seconds
  total_narration_seconds: 0
  total_visual_seconds: 0
  style_anchors: {}          # consistency tokens carried forward
  revision_counts: {}        # stage_name → number of revisions
  issues_log: []             # all issues found, with resolution status
```

## Execution Protocol

### Phase 0: Initialize

1. Load the pipeline manifest (`animated-explainer.yaml`)
2. Load the playbook (from user selection or default)
3. Set budget from configuration or user input (default: $2.00)
4. Initialize EP_STATE

### Phase 1: Execute Stages Serially

For each stage in order: `research → proposal → script → scene_plan → assets → edit → compose → publish`

**Pre-production stages (research, proposal)** run before any money is spent:
- **research** gathers raw data via web search — zero cost, no tools
- **proposal** presents concepts and costs to the user — zero cost, but contains the **approval gate**
- The pipeline MUST NOT proceed past proposal without `approval.status == "approved"` or `"approved_with_changes"`

After proposal approval, extract and store in EP_STATE:
- `selected_concept` from `proposal_packet.selected_concept` (drives script, scene, visual decisions)
- `production_plan` from `proposal_packet.production_plan` (drives tool selection in assets stage)
- `approved_budget_usd` from `proposal_packet.approval.approved_budget_usd` (overrides default budget)
- `playbook` from `proposal_packet.selected_concept → concept_options[selected].suggested_playbook`

```
EXECUTE_STAGE(stage_name):

  1. PREPARE
     - Load the director skill for this stage
     - Inject EP_STATE as context (prior artifacts, budget remaining, style anchors)
     - Inject any EP feedback from previous revision attempts

  2. SPAWN DIRECTOR
     - The director executes its full process (as defined in its skill MD)
     - Director produces an artifact

  3. REVIEW (EP performs this, not a separate reviewer)
     - Schema validation against artifact schema
     - Check review_focus items from pipeline manifest
     - Check success_criteria from pipeline manifest
     - Cross-check against playbook constraints
     - Run EP-SPECIFIC CROSS-STAGE CHECKS (see below)

  4. GATE DECISION
     If PASS:
       - Store artifact in EP_STATE
       - Update cumulative tracking (budget, durations, etc.)
       - Log: "[stage] PASSED — moving to next stage"
       - Continue to next stage

     If REVISE:
       - Increment revision_counts[stage_name]
       - If revision_counts[stage_name] >= 3:
           - PASS WITH WARNINGS (never block forever)
           - Log unresolved issues
       - Else:
           - Compose specific feedback for the director
           - Re-run SPAWN DIRECTOR with feedback injected
           - Re-run REVIEW

     If SEND_BACK(target_stage):
       - This is the EP's special power: send work BACK to a prior stage
       - Only used when a downstream discovery invalidates upstream work
       - Example: TTS returns 16s audio for a scene planned at 10s
         → Send back to script director: "Rewrite section 3. Max 25 words."
       - Re-execute from target_stage forward (artifacts after target are invalidated)
       - Max 1 send-back per stage pair (prevent infinite loops)
```

### Phase 2: Final Quality Assurance

After all 7 stages complete, the EP performs a holistic review:

```
FINAL_QA:
  1. PROBE the output video:
     - Duration: within ±5% of target?
     - Resolution: matches media profile?
     - Audio: narration audible throughout? Music balanced?
     - File: valid container, reasonable size?

  2. A/V SYNC CHECK:
     - Compare narration timestamps to visual cut points
     - Flag any section where narration plays over the wrong visual
     - Tolerance: ±0.5 seconds
     - If the project is generated-narration-led and contains visual timing
       cues, run `visual_timing_qa` on the rendered video and inspect
       `review.md` contact sheets before publish approval

  3. STYLE CONSISTENCY:
     - Review all generated images: do they look like the same video?
     - Check color palette adherence
     - Check typography consistency

  4. BUDGET RECONCILIATION:
     - Total actual spend vs. budget
     - Log per-stage cost breakdown

  5. DECISION:
     If all checks pass → APPROVE for publish stage
     If issues found → Send back to the specific stage(s) that can fix them
       - Audio issues → compose director
       - Visual issues → asset director (regenerate) or scene director (replan)
       - Duration issues → script director (rewrite)
       - Sync issues → edit director (re-cut)
```

## EP-Specific Cross-Stage Checks

These checks use information accumulated across stages — something no individual director can do.

### After RESEARCH stage:
```
CHECK: Research depth
  - At least 3 data_points with source URLs?
  - At least 3 angles_discovered with grounded_in references?
  - At least 5 sources cited?
  - If any minimum not met: REVISE research
  - Note: Do NOT checkpoint with user — research is informational, not a decision point
```

### After PROPOSAL stage:
```
CHECK: Approval gate (CRITICAL — the entire point of pre-production)
  - Is approval.status == "approved" or "approved_with_changes"?
  - If "pending" or "rejected": STOP. Present to user and wait.
  - If "approved_with_changes": apply modifications to selected_concept before proceeding
  - Extract: target_duration_seconds, playbook, budget, tool selections
  - Initialize budget from approved_budget_usd (not default)

CHECK: Production feasibility
  - Does the production plan reference tools that are actually available?
  - Cross-check production_plan.stages[].tools[].available against registry
  - If any required tool is unavailable: alert user, offer alternatives
```

### After SCRIPT stage:
```
CHECK: Word count vs. duration target
  - Calculate: total_words / 150 = estimated_minutes (at 150 WPM speaking rate)
  - If estimated_minutes > target_duration * 1.15:
      REVISE script: "Script is {X} words. At 150 WPM, that's {Y} minutes.
      Target is {Z} minutes. Cut {N} words."
  - If estimated_minutes < target_duration * 0.7:
      REVISE script: "Script is too short. Add {N} words of content."
```

### After SCENE_PLAN stage:
```
CHECK: Total scene duration covers full script
  - Sum all scene durations
  - Compare to script's total duration
  - If gaps > 1 second: REVISE scene_plan
  - If overlaps: REVISE scene_plan

CHECK: Visual variety
  - Count consecutive same-type scenes
  - If > 3 consecutive: REVISE scene_plan

CHECK: Asset feasibility
  - For each required_asset, verify the tool exists in registry
  - If any asset requires a tool that's unavailable:
      REVISE scene_plan: "Tool {X} is unavailable. Use {alternative} instead."
```

### After ASSETS stage:
```
CHECK: Narration duration feedback loop (CRITICAL)
  - For each TTS audio file, probe actual duration
  - Store in EP_STATE.narration_durations
  - For each section:
      If actual_duration > planned_duration * 1.15:
        Option A: SEND_BACK to script director:
          "Section {id} narration is {X}s but scene is {Y}s.
           Rewrite to max {N} words."
        Option B (if within 25% over): Adjust scene_plan durations to fit
  - Update EP_STATE.total_narration_seconds

CHECK: Budget gate
  - If budget_spent > budget_total * 0.9 and stages remain:
      Alert: "90% budget consumed with {N} stages remaining"
      Adjust remaining stages to use free/cheap alternatives

CHECK: Style consistency
  - Compare image descriptions/styles across all generated images
  - Store style_anchors for downstream use
```

### After EDIT stage:
```
CHECK: Timeline completeness
  - Verify edit decisions cover 0 to total_duration with no gaps
  - Verify all asset references point to existing files
  - Verify audio ducking is configured for all narration segments

CHECK: A/V sync pre-validation
  - For each cut: narration_start aligns with visual_start (±0.5s)
  - For each scene: narration_duration ≤ visual_duration
```

### After COMPOSE stage:
```
CHECK: Output validation
  - ffprobe the output: duration, resolution, codec, audio channels
  - If duration drift > 5%: investigate which stage caused it
  - If audio missing: check audio_mixer configuration
  - If resolution wrong: check media profile selection
```

## Feedback Message Templates

When sending work back to a director, use these structured feedback messages:

### To Script Director:
```
EP FEEDBACK — Script Revision Required
Reason: {reason}
Specific issue: {detail}
Constraint: {word_count_limit / duration_target / etc.}
Keep: {what was good about the current script}
Change: {what specifically needs to change}
```

### To Scene Director:
```
EP FEEDBACK — Scene Plan Revision Required
Reason: {reason}
Affected scenes: {scene_ids}
Constraint: {feasibility / variety / duration / etc.}
Available tools: {current tool registry status}
```

### To Asset Director:
```
EP FEEDBACK — Asset Regeneration Required
Reason: {reason}
Affected assets: {asset_ids}
Style anchors: {consistency requirements from prior successful assets}
Budget remaining: ${remaining}
```

### To Compose Director:
```
EP FEEDBACK — Re-render Required
Reason: {reason}
Specific issue: {audio_sync / duration / quality / etc.}
Expected: {what the output should be}
Actual: {what was produced}
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | research | Data depth, source quality, angle diversity | Revise research |
| G2 | proposal | Concept quality, cost accuracy, user approval | Revise proposal OR wait for user |
| G3 | script | Word count vs duration, narrative arc, research integration | Revise script |
| G4 | scene_plan | Coverage, variety, feasibility against production plan | Revise scene_plan |
| G5 | assets | File existence, narration duration, budget, style | Revise assets OR send-back to script |
| G6 | edit | Timeline completeness, A/V pre-sync | Revise edit |
| G7 | compose | Output probe, duration, audio quality | Revise compose OR send-back to edit/assets |
| G8 | publish | Metadata, packaging | Revise publish |
| FINAL | all | Holistic video review | Send-back to specific stage |

## Execution Limits (Anti-Loop Protection)

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max revisions per stage | 3 | Prevent perfectionism loops |
| Max send-backs per stage pair | 1 | Prevent ping-pong between stages |
| Max total send-backs | 3 | Cap total pipeline re-work |
| Max total budget | Configurable (default $2) | Hard stop on spending |
| Max total wall-time | 15 minutes | Timeout for entire pipeline |

After any limit is hit: **proceed with warnings**, never block indefinitely.

## Integration with Existing Skills

The EP doesn't replace any director skill — it wraps them. Each director skill continues to work exactly as documented. The EP adds:

1. **Context injection**: Directors receive EP_STATE with cross-stage information they couldn't access before
2. **Feedback injection**: Directors receive specific revision instructions when sent back
3. **Budget awareness**: Directors receive remaining budget and can adjust tool choices accordingly
4. **Style anchors**: Directors receive consistency tokens from prior stages

## Example EP Run (Abbreviated)

```
[EP] Starting pipeline: animated-explainer v2.0
[EP] Default budget: $2.00 | Target: TBD (set after proposal)

[EP] === STAGE 1: research ===
[EP] Spawning research-director... Topic: "How DNS Works"
[EP] Research director executed 18 web searches.
[EP] Findings: 5 existing videos mapped, 6 data points sourced, 8 audience questions found.
[EP] Top insight: "1.1.1.1 handles 13.5% of queries — most people assume Google dominates."
[EP] G1 PASS — 6 data points, 4 angles discovered, 12 sources cited.
[EP] Budget: $0.00 spent (research is free)

[EP] === STAGE 2: proposal ===
[EP] Spawning proposal-director with research_brief...
[EP] Preflight: ElevenLabs ✓, image_selector ✓, video_selector ✗ (no API keys), music_gen ✓
[EP] 3 concepts presented to user:
[EP]   C1: "The 200ms Journey" (data_driven, $0.64)
[EP]   C2: "Your ISP Knows Everything" (contrarian, $0.58)
[EP]   C3: "The Internet's Phone Book" (analogy, $0.52)
[EP] Awaiting user approval...
[EP] USER SELECTED: C1 with modification: "focus on recursive resolution, skip DoH"
[EP] G2 PASS — Approved with changes. Budget: $0.64 approved.
[EP] Extracted: target=90s, playbook=minimalist-diagram, budget=$0.64

[EP] === STAGE 3: script ===
[EP] Spawning script-director with proposal_packet + research_brief...
[EP] Script director produced script. Reviewing...
[EP] Word count: 210 words → ~84s at 150 WPM. Target: 90s.
[EP] Script references 3 data points from research. ✓
[EP] G3 PASS — Within duration, research integrated.

[EP] === STAGE 4: scene_plan ===
[EP] Spawning scene-director with script + proposal_packet...
[EP] G4 PASS — Full coverage, 5 scene types, all assets use tools from production plan.

[EP] === STAGE 5: assets ===
[EP] Spawning asset-director with scene_plan + script + production_plan...
[EP] Asset director generated 14 assets. Reviewing...
[EP] Narration check: Section 3 is 8.2s audio for 6s scene.
[EP] → Adjusting scene_plan: extending scene-3 to 9s (within tolerance)
[EP] Budget: $0.52 spent, $0.12 remaining
[EP] Style check: All images use consistent palette. ✓
[EP] G5 PASS (with scene duration adjustment)

[EP] === STAGE 6: edit ===
[EP] Spawning edit-director with adjusted scene_plan + asset_manifest...
[EP] G6 PASS — Timeline complete, audio ducking configured.

[EP] === STAGE 7: compose ===
[EP] Spawning compose-director with edit_decisions + asset_manifest...
[EP] Output probe: 88.7s (target 90s, within 5%). Resolution: 1920x1080. Audio: stereo. ✓
[EP] G7 PASS

[EP] === STAGE 8: publish ===
[EP] Spawning publish-director with render_report + proposal_packet...
[EP] G8 PASS — SEO metadata complete, chapters present, research citations included.

[EP] === FINAL QA ===
[EP] Duration: 88.7s ✓ | A/V sync: within tolerance ✓ | Style: consistent ✓
[EP] Budget: $0.52 / $0.64 approved ✓
[EP] PIPELINE COMPLETE — 0 revisions, 0 send-backs
[EP] Output: renders/output.mp4
```

## Common Pitfalls

- **Over-revising**: The EP should be pragmatic. A "pretty good" script that's within duration is better than a "perfect" script after 5 rounds. Use the limits.
- **Ignoring budget**: Don't let early stages consume all budget. Reserve at least 30% for assets + compose.
- **Sending back too eagerly**: Minor issues (±10% duration) should be handled by adjusting downstream, not re-running upstream. Only send back for structural problems.
- **Not probing outputs**: Always ffprobe the final video. Never trust metadata alone.
- **Losing style context**: The EP must carry style anchors forward. If image 1 uses a specific palette, image 5 must match. Pass this explicitly to the asset director.
