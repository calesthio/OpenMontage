# Executive Producer — Animation Pipeline

## When to Use

You are the **Executive Producer (EP)** for a generated animation video. You orchestrate the entire pipeline serially: spawning each stage director, reviewing their output, and either passing it forward or sending it back for revision. You are the stateful brain; the directors are stateless workers.

**You replace the default parallel/sequential execution model.** Instead of running all stages blindly, you exercise judgment at every gate.

## Why This Exists

Animation pipelines have unique failure modes that parallel execution cannot catch:

- Motion consistency breaks when scenes are generated independently
- Mathematical accuracy errors compound if not caught after script
- Animation timing requires hold times and reveals that get squeezed out without cross-stage awareness
- Reuse strategy degrades when each stage plans independently
- Budget allocation between AI-generated assets and free programmatic animation needs active management
- Text readability and diagram sharpness must be verified at compose time, not assumed

The EP solves all of these by maintaining cumulative state and applying animation-specific judgment at each gate.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/animation.yaml` | Stage definitions, review focus, success criteria |
| Skills | All 9 director skills + `meta/reviewer` | Stage execution knowledge |
| Schemas | All artifact schemas | Validation |
| Playbook | Active style playbook | Quality constraints |
| Tools | Full tool registry | Available capabilities |

## Cumulative State

The EP maintains a running state object that flows through the entire pipeline:

```
EP_STATE:
  pipeline: animation
  playbook: <selected playbook name>
  target_duration_seconds: <from proposal_packet.selected_concept>
  budget_total_usd: <from proposal_packet.approval.approved_budget_usd or configured limit>
  budget_spent_usd: 0.0
  budget_remaining_usd: <budget_total>

  # Animation-specific state
  # Approaches:
  #   image_animation  — Multi-image crossfade via Remotion (anime/Ghibli/illustration style)
  #   clip_video       — AI-generated video clips composited as a story
  #   manim            — Programmatic math/physics animation via ManimCE
  #   remotion_dataviz — Data visualization with Remotion components (zero-key capable)
  #   diagram_stills   — Diagram + image stills with Ken Burns
  #   mixed            — Combination of multiple approaches per-scene
  animation_mode: <image_animation | clip_video | manim | remotion_dataviz | diagram_stills | mixed>
  reuse_strategy:
    recurring_motifs: []
    layout_system: null
    transition_family: null
    typography_hierarchy: null
    unique_scene_count: 0
    reused_template_count: 0
  math_accuracy_notes: []      # constraints from research on what NOT to oversimplify

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
  research_brief: null         # full research_brief artifact
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

1. Load the pipeline manifest (`animation.yaml`)
2. Load the playbook (from user selection or default)
3. Set budget from configuration or user input (default: $2.00)
4. Initialize EP_STATE

### Phase 1: Execute Stages Serially

For each stage in order: `research → proposal → script → scene_plan → assets → edit → compose → publish`

**Pre-production stages (research, proposal)** run before any money is spent:
- **research** gathers topic data AND animation technique references via web search — zero cost
- **proposal** presents concepts with animation mode selection and costs to the user — zero cost, but contains the **approval gate**
- The pipeline MUST NOT proceed past proposal without `approval.status == "approved"` or `"approved_with_changes"`

After proposal approval, extract and store in EP_STATE:
- `selected_concept` from `proposal_packet.selected_concept`
- `animation_mode` from `selected_concept.animation_mode`
- `reuse_strategy` from `selected_concept.reuse_strategy`
- `production_plan` from `proposal_packet.production_plan`
- `approved_budget_usd` from `proposal_packet.approval.approved_budget_usd`
- `playbook` from `proposal_packet.selected_concept → suggested_playbook`
- `math_accuracy_notes` from research_brief (if applicable)

```
EXECUTE_STAGE(stage_name):

  1. PREPARE
     - Load the director skill for this stage
     - Inject EP_STATE as context (prior artifacts, budget remaining, style anchors, animation mode, reuse strategy)
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
       - Only used when a downstream discovery invalidates upstream work
       - Re-execute from target_stage forward (artifacts after target are invalidated)
       - Max 1 send-back per stage pair (prevent infinite loops)
```

### Phase 2: Final Quality Assurance

After all stages complete, the EP performs a holistic review:

```
FINAL_QA:
  1. PROBE the output video:
     - Duration: within ±5% of target?
     - Resolution: matches media profile?
     - Audio: narration audible throughout? Music balanced?
     - File: valid container, reasonable size?

  2. TEXT AND DIAGRAM SHARPNESS (ANIMATION-SPECIFIC):
     - Are text elements readable at target resolution?
     - Are diagram lines crisp, not blurry from scaling?
     - Are mathematical symbols rendered correctly?
     - Is typography hierarchy maintained across scenes?

  3. MOTION CONSISTENCY:
     - Do transitions follow the declared transition family?
     - Are hold times preserved (not squeezed by timing)?
     - Do staggered reveals play correctly?
     - Is the pacing animation-friendly (not rushed)?

  4. STYLE CONSISTENCY:
     - Do all scenes follow the reuse strategy?
     - Is the color palette consistent?
     - Do recurring motifs appear correctly across scenes?

  5. MATHEMATICAL ACCURACY (if applicable):
     - Do animated formulas/diagrams match the research brief's accuracy notes?
     - Are any simplifications flagged in the research still correct?

  6. BUDGET RECONCILIATION:
     - Total actual spend vs. budget
     - Log per-stage cost breakdown

  7. DECISION:
     If all checks pass → APPROVE for publish stage
     If issues found → Send back to the specific stage(s) that can fix them
       - Text/diagram issues → compose director (re-render) or asset director (regenerate)
       - Motion issues → edit director (re-time) or scene director (replan)
       - Audio issues → compose director
       - Duration issues → script director (rewrite)
       - Math errors → script director (fix content) then cascade forward
```

## EP-Specific Cross-Stage Checks

These checks use information accumulated across stages — something no individual director can do.

### After RESEARCH stage:
```
CHECK: Research depth
  - At least 3 data_points with source URLs?
  - At least 3 angles_discovered with grounded_in references?
  - At least 2 animation technique references?
  - At least 5 sources cited?
  - If any minimum not met: REVISE research
  - Note: Do NOT checkpoint with user — research is informational, not a decision point
```

### After PROPOSAL stage:
```
CHECK: Approval gate (CRITICAL)
  - Is approval.status == "approved" or "approved_with_changes"?
  - If "pending" or "rejected": STOP. Present to user and wait.
  - If "approved_with_changes": apply modifications before proceeding
  - Extract: animation_mode, reuse_strategy, target_duration, playbook, budget, tool selections

CHECK: Animation approach feasibility
  - Does the selected animation approach's required tools exist in the registry?
  - If image_animation selected: is image_selector available? Which providers? Is Remotion available?
  - If clip_video selected: is video_selector available? Which providers?
  - If manim selected: is math_animate (ManimCE) available?
  - If remotion_dataviz selected: is video_compose (Remotion) available?
  - If diagram_stills selected: is diagram_gen + image_selector available?
  - If any required tool is unavailable: alert user, offer alternatives with specific setup instructions
  - NEVER silently downgrade — if an approach needs a key the user doesn't have, STOP and tell them

CHECK: Reuse strategy validity
  - Does the reuse strategy define recurring motifs?
  - Is the unique-to-template ratio reasonable (aim for ≤ 3:1)?
```

### After SCRIPT stage:
```
CHECK: Word count vs. duration target
  - Calculate: total_words / 150 = estimated_minutes
  - If estimated_minutes > target_duration * 1.15:
      REVISE script: "Script is {X} words → {Y}min. Target: {Z}min. Cut {N} words."
  - If estimated_minutes < target_duration * 0.7:
      REVISE script: "Script is too short. Add {N} words."

CHECK: Animation beat structure
  - Does each section express ONE clear visual idea?
  - Are hold times budgeted (not every second filled with new information)?
  - Is on-screen text concise (phrases, not paragraphs)?

CHECK: Mathematical accuracy (if applicable)
  - Does the script's explanation match the research brief's accuracy notes?
  - Are any simplifications technically defensible?
  - If inaccurate: REVISE script with specific correction from research
```

### After SCENE_PLAN stage:
```
CHECK: Total scene duration covers full script
  - Sum all scene durations
  - Compare to script's total duration
  - If gaps > 1 second: REVISE scene_plan
  - If overlaps: REVISE scene_plan

CHECK: Animation mode adherence
  - Does every scene specify which animation mode/tool it uses?
  - Are mode choices consistent with the proposal's selected mode?
  - If mixed mode: are transitions between modes planned?

CHECK: Reuse strategy enforcement
  - Does the scene plan reference the recurring motifs from the proposal?
  - Are templates reused where specified?
  - If every scene is unique: flag as potential over-complexity

CHECK: Visual variety within constraints
  - Count consecutive same-type scenes
  - If > 3 consecutive: REVISE scene_plan
```

### After ASSETS stage:
```
CHECK: Narration duration feedback loop (CRITICAL)
  - For each TTS audio file, probe actual duration
  - Store in EP_STATE.narration_durations
  - For each section:
      If actual_duration > planned_duration * 1.15:
        Option A: SEND_BACK to script director
        Option B (within 25% over): Adjust scene_plan durations
  - Update EP_STATE.total_narration_seconds

CHECK: Budget gate
  - If budget_spent > budget_total * 0.9 and stages remain:
      Alert: "90% budget consumed with {N} stages remaining"
      Adjust remaining stages to free/cheap alternatives

CHECK: Style consistency
  - Compare visual styles across all generated assets
  - Are recurring motifs visually consistent?
  - Store style_anchors for downstream use

CHECK: Programmatic asset integrity (if Manim/Remotion)
  - Did math_animate or video_compose succeed without errors?
  - Are output files valid and correctly sized?
```

### After EDIT stage:
```
CHECK: Timeline completeness
  - Verify edit decisions cover 0 to total_duration with no gaps
  - Verify all asset references point to existing files
  - Verify audio ducking is configured for all narration segments

CHECK: Hold time preservation (ANIMATION-SPECIFIC)
  - Verify hold times from scene_plan are preserved in edit decisions
  - Verify staggered reveals are not compressed
  - Verify motion serves hierarchy, not decoration

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

CHECK: Text and diagram sharpness (ANIMATION-CRITICAL)
  - Text must be readable at target resolution
  - Diagram lines must be crisp (no scaling artifacts)
  - Mathematical symbols must render correctly
  - If any text/diagram is blurry: REVISE compose with resolution/scaling adjustments
```

## Feedback Message Templates

### To Script Director:
```
EP FEEDBACK — Script Revision Required
Reason: {reason}
Specific issue: {detail}
Constraint: {word_count_limit / duration_target / math_accuracy}
Animation mode: {current mode — affects how text and beats should be structured}
Keep: {what was good}
Change: {what specifically needs to change}
```

### To Scene Director:
```
EP FEEDBACK — Scene Plan Revision Required
Reason: {reason}
Affected scenes: {scene_ids}
Animation mode: {current mode}
Reuse strategy: {what motifs/templates should be reused}
Available tools: {current tool registry status}
```

### To Asset Director:
```
EP FEEDBACK — Asset Regeneration Required
Reason: {reason}
Affected assets: {asset_ids}
Style anchors: {consistency requirements}
Animation mode: {current mode — affects which tools to use}
Budget remaining: ${remaining}
```

### To Compose Director:
```
EP FEEDBACK — Re-render Required
Reason: {reason}
Specific issue: {text_sharpness / motion_timing / audio_sync / etc.}
Expected: {what the output should be}
Actual: {what was produced}
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | research | Data depth, technique references, angle diversity | Revise research |
| G2 | proposal | Concept quality, mode feasibility, user approval | Revise proposal OR wait for user |
| G3 | script | Word count, beat structure, math accuracy | Revise script |
| G4 | scene_plan | Coverage, mode adherence, reuse strategy, variety | Revise scene_plan |
| G5 | assets | Narration duration, budget, style, asset integrity | Revise assets OR send-back to script |
| G6 | edit | Timeline completeness, hold times, A/V pre-sync | Revise edit |
| G7 | compose | Output probe, text sharpness, motion timing | Revise compose OR send-back |
| G8 | publish | Metadata, packaging, animation-mode tags | Revise publish |
| FINAL | all | Holistic review: sharpness, motion, accuracy, style | Send-back to specific stage |

## Execution Limits (Anti-Loop Protection)

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max revisions per stage | 3 | Prevent perfectionism loops |
| Max send-backs per stage pair | 1 | Prevent ping-pong |
| Max total send-backs | 3 | Cap total re-work |
| Max total budget | Configurable (default $2) | Hard stop on spending |
| Max total wall-time | 15 minutes | Timeout for entire pipeline |

After any limit is hit: **proceed with warnings**, never block indefinitely.

## Integration with Existing Skills

The EP doesn't replace any director skill — it wraps them. Each director skill continues to work exactly as documented. The EP adds:

1. **Context injection**: Directors receive EP_STATE with cross-stage information
2. **Feedback injection**: Directors receive specific revision instructions when sent back
3. **Budget awareness**: Directors receive remaining budget and adjust tool choices
4. **Animation mode context**: Directors know the selected mode and reuse strategy
5. **Style anchors**: Directors receive consistency tokens from prior stages
6. **Math accuracy notes**: Directors receive constraints on technical accuracy

## Common Pitfalls

- **Over-revising**: A "good enough" animation in the right mode is better than a "perfect" one after 5 rounds.
- **Ignoring text sharpness**: The #1 animation quality issue. Always verify text readability at final resolution.
- **Letting reuse strategy erode**: If the proposal specified 3 templates, the scene plan should use 3 templates, not 8 unique designs.
- **Not probing outputs**: Always ffprobe the final video. Never trust metadata alone.
- **Losing animation mode context**: If the proposal selected Manim, every downstream stage should know it's a Manim project. Don't let stages default to generic image_selector when programmatic animation was approved.
- **Skipping math accuracy checks**: For technical topics, this is non-negotiable. A wrong animation is worse than no animation.
