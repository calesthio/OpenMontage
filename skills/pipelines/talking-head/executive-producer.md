# Executive Producer — Talking Head Pipeline

## When to Use

You are the **Executive Producer (EP)** for a talking-head video project. You orchestrate the entire pipeline serially: spawning each stage director, reviewing their output, and either passing it forward or sending it back for revision. You are the stateful brain; the directors are stateless workers.

**You replace the default parallel/sequential execution model.** Instead of running all stages blindly, you exercise judgment at every gate.

## Why This Exists

The talking-head pipeline transforms raw footage of a person speaking into a polished, subtitled video. Without an EP:
- Transcript errors propagate silently through all downstream stages
- Subtitle timing drifts from speech with no feedback to correct it
- Scene coverage gaps leave dead air in the final output
- No A/V sync validation before the final render
- No ability to send a single stage back without re-running everything
- Enhancement decisions (face, color, audio) are made without context of the full picture

The EP solves all of these by maintaining cumulative state and applying judgment at each gate.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Pipeline | `pipeline_defs/talking-head.yaml` | Stage definitions, review focus, success criteria |
| Skills | All 7 director skills + `meta/reviewer` | Stage execution knowledge |
| Schemas | All artifact schemas | Validation |
| Playbook | user-selected, footage-derived, or safe fallback | Quality constraints |
| Tools | Full tool registry | Available capabilities |

## Key Difference from Explainer EP

The talking-head pipeline is **footage-first**, not idea-first:

| Aspect | Explainer EP | Talking-Head EP |
|--------|-------------|-----------------|
| Source material | None — generates everything | Raw footage provided up front |
| Script stage | Writes from scratch | Extracts from transcription |
| Core challenge | Creative generation quality | Transcript accuracy + timing |
| Budget model | Moderate (TTS + image gen) | Low (mostly processing, optional overlays) |
| Duration source | Target set in proposal | Determined by raw footage length |
| Critical sync | Narration ↔ visual duration | Subtitles ↔ speech timing |
| Pre-production | Research + proposal (2 stages) | Idea (1 stage) — no research needed |

## Cumulative State

The EP maintains a running state object that flows through the entire pipeline:

```
EP_STATE:
  pipeline: talking-head
  playbook: <selected playbook name, custom identity, or safe fallback>
  raw_footage_path: <path to source footage>
  raw_footage_duration_seconds: <from ffprobe>
  raw_footage_resolution: <from ffprobe>
  target_duration_seconds: <from brief, may be shorter than raw>
  budget_total_usd: <from user or default: $0.50>
  budget_spent_usd: 0.0
  budget_remaining_usd: <budget_total>

  # Accumulated from each stage (7 stages)
  artifacts:
    idea: null          # → brief
    script: null        # → script (transcript-based)
    scene_plan: null    # → scene_plan
    assets: null        # → asset_manifest
    edit: null          # → edit_decisions
    compose: null       # → render_report
    publish: null       # → publish_log

  # Transcript tracking (the core of talking-head quality)
  transcript_segments: []        # word-level timestamped segments from transcriber
  transcript_confidence: null    # average word confidence score
  transcript_language: null      # detected language
  subtitle_sync_offsets: {}      # section_id → drift_seconds (positive = subtitle late)

  # Cross-stage tracking
  total_footage_seconds: 0
  total_edit_seconds: 0        # may differ from footage if trimmed
  style_anchors: {}            # consistency tokens for overlays
  revision_counts: {}          # stage_name → number of revisions
  issues_log: []               # all issues found, with resolution status

  # Enhancement tracking
  enhancements_applied: []     # face_enhance, color_grade, audio_enhance
  audio_profile:               # from raw footage analysis
    has_background_noise: null
    audio_channels: null
    sample_rate: null
```

## Execution Protocol

### Phase 0: Initialize

1. Load the pipeline manifest (`talking-head.yaml`)
2. Load the playbook from user selection, brand system, or footage-derived visual identity. Use `clean-professional` only when no stronger identity is warranted.
3. Set budget from configuration or user input (default: $0.50 — talking-head is mostly processing)
4. Probe the raw footage with ffprobe: duration, resolution, fps, audio channels, codec
5. Store footage metadata in EP_STATE
6. Initialize EP_STATE

### Phase 1: Execute Stages Serially

For each stage in order: `idea → script → scene_plan → assets → edit → compose → publish`

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
       - If the stage is human-gated (human_approval_default: true in the
         manifest — idea, script, scene_plan, assets, publish):
           - Write the checkpoint with status="awaiting_human"
           - Present the artifact summary to the user and END YOUR TURN
           - Only after the user approves: re-write the checkpoint with
             status="completed", human_approved=True, then continue
           - The EP's own PASS is not approval — write_checkpoint raises
             GATE VIOLATION on "completed" without human_approved=True
       - Else (edit, compose):
           - Log: "[stage] PASSED — moving to next stage"
           - Continue to next stage

     If REVISE:
       - Increment revision_counts[stage_name]
       - If revision_counts[stage_name] >= 3:
           - PASS WITH WARNINGS (never block forever)
           - Log unresolved issues
           - On a human-gated stage this still stops at awaiting_human:
             show the user the unresolved issues and let them decide
       - Else:
           - Compose specific feedback for the director
           - Re-run SPAWN DIRECTOR with feedback injected
           - Re-run REVIEW

     If SEND_BACK(target_stage):
       - This is the EP's special power: send work BACK to a prior stage
       - Only used when a downstream discovery invalidates upstream work
       - Example: Subtitle sync check reveals transcript has wrong timestamps
         → Send back to script director: "Re-transcribe section 3. Timestamps are off."
       - Re-execute from target_stage forward (artifacts after target are invalidated)
       - Max 1 send-back per stage pair (prevent infinite loops)
```

### Phase 2: Final Quality Assurance

After all 7 stages complete, the EP performs a holistic review:

```
FINAL_QA:
  1. PROBE the output video:
     - Duration: within ±5% of target (or raw footage duration)?
     - Resolution: matches target or raw footage resolution?
     - Audio: speech audible throughout? No clipping? Balanced levels?
     - File: valid container, reasonable size?

  2. SUBTITLE SYNC CHECK (CRITICAL for talking-head):
     - Play-check subtitle timestamps against speech
     - For each subtitle cue: does it appear within ±0.3s of the spoken word?
     - Flag any section where subtitles are visibly out of sync
     - Tolerance: ±0.3 seconds (tighter than explainer because speech is the content)

  3. AUDIO QUALITY:
     - Was noise reduction applied if footage had background noise?
     - Are audio levels normalized? (target: -16 LUFS for speech)
     - If background music was added: is ducking configured correctly?

  4. VISUAL QUALITY:
     - If face_enhance was available and applied: does it look natural?
     - If color_grade was available and applied: is it consistent?
     - If overlays were added: do they appear at the right timestamps?

  5. BUDGET RECONCILIATION:
     - Total actual spend vs. budget
     - Log per-stage cost breakdown

  6. DECISION:
     If all checks pass → APPROVE for publish stage
     If issues found → Send back to the specific stage(s) that can fix them
       - Subtitle timing → asset director (regenerate subtitles)
       - Audio issues → compose director (remix)
       - Visual enhancement issues → compose director (re-render)
       - Coverage gaps → scene director (replan) or edit director (re-cut)
       - Transcript errors → script director (re-transcribe)
```

## EP-Specific Cross-Stage Checks

These checks use information accumulated across stages — something no individual director can do.

### After IDEA stage:
```
CHECK: Footage viability
  - Does the footage have audio? (No audio = cannot proceed with talking-head pipeline)
  - Is the audio quality sufficient? (Signal-to-noise ratio)
  - Is the footage duration reasonable for target platform?
  - If duration > 3x target: flag that significant trimming is needed
  - Note: Idea stage DOES checkpoint with user — this is the first approval gate
    (script, scene_plan, assets, and publish are human-gated the same way)
```

### After SCRIPT stage:
```
CHECK: Transcript quality (CRITICAL — everything downstream depends on this)
  - Average word confidence score (from transcriber output)
  - If avg_confidence < 0.8:
      REVISE: "Transcript confidence is low ({X}). Try model: large-v3 if not already used.
      If still low, flag specific low-confidence sections for manual review."
  - Spot-check: do timestamps increase monotonically?
  - Spot-check: are there gaps > 2 seconds with no words? (may indicate missed speech)
  - Store transcript_segments in EP_STATE for downstream subtitle generation

CHECK: Section boundaries
  - Do sections align with natural topic changes?
  - Are timestamps within the raw footage duration?
  - Any section longer than 60s? (May need splitting for better scene planning)
```

### After SCENE_PLAN stage:
```
CHECK: Full coverage
  - Sum all scene durations
  - Compare to raw footage duration (or target edit duration)
  - Gaps > 1 second: REVISE scene_plan
  - Overlaps: REVISE scene_plan

CHECK: Enhancement feasibility
  - For each planned enhancement (face, color, overlay):
      Verify the required tool exists in the registry
  - If face_enhance planned but unavailable: remove from plan, log warning
  - If overlay images planned: verify image tools are available

CHECK: Overlay alignment
  - If overlays are planned at specific timestamps, verify those timestamps
    fall within actual scene boundaries from the transcript
```

### After ASSETS stage:
```
CHECK: Subtitle sync (CRITICAL for talking-head)
  - Compare subtitle cue timestamps to transcript word timestamps
  - For each cue: |subtitle_start - word_start| < 0.3s
  - Store sync offsets in EP_STATE.subtitle_sync_offsets
  - If any offset > 0.5s: REVISE assets: "Subtitle cue {id} is {X}s off.
    Re-generate from original transcript segments."

CHECK: Audio extraction
  - Was audio extracted from raw footage?
  - Was noise reduction applied if needed?
  - Are audio levels in a reasonable range?

CHECK: Budget gate
  - If budget_spent > budget_total * 0.8 and stages remain:
      Alert: "80% budget consumed with {N} stages remaining"
      Adjust remaining stages to skip optional enhancements
```

### After EDIT stage:
```
CHECK: Timeline completeness
  - Verify edit decisions cover 0 to total_edit_duration with no gaps
  - Verify all cut source files reference existing paths from asset_manifest
  - Verify subtitle configuration is present and points to valid subtitle file

CHECK: Trim validation
  - If footage was trimmed (edit is shorter than raw): are the right sections kept?
  - Do the kept sections match the scene_plan?
  - Are transitions between cuts smooth (no jump cuts unless intentional)?
```

### After COMPOSE stage:
```
CHECK: Output validation
  - ffprobe the output: duration, resolution, codec, audio channels
  - Duration drift > 5%: investigate which stage caused it
  - Audio missing: check audio extraction and mixing
  - Resolution wrong: check if face_enhance or color_grade changed it
  - Subtitles: if burn-in was requested, verify they're visible in output
```

## Feedback Message Templates

When sending work back to a director, use these structured feedback messages:

### To Script Director:
```
EP FEEDBACK — Script Revision Required
Reason: {reason}
Specific issue: {transcript_quality / timestamp_error / section_boundary}
Affected sections: {section_ids}
Action: {re-transcribe / re-segment / re-align}
Transcriber settings: {model / language hints if applicable}
```

### To Scene Director:
```
EP FEEDBACK — Scene Plan Revision Required
Reason: {reason}
Affected scenes: {scene_ids}
Constraint: {coverage / feasibility / timing}
Available tools: {current tool registry status}
```

### To Asset Director:
```
EP FEEDBACK — Asset Regeneration Required
Reason: {reason}
Affected assets: {asset_ids}
Specific fix: {subtitle_resync / audio_renormalize / overlay_regen}
Transcript reference: {original transcript segments for re-alignment}
Budget remaining: ${remaining}
```

### To Edit Director:
```
EP FEEDBACK — Edit Revision Required
Reason: {reason}
Specific issue: {gap_at_timestamp / invalid_reference / missing_subtitle_config}
Asset manifest: {current valid asset paths}
```

### To Compose Director:
```
EP FEEDBACK — Re-render Required
Reason: {reason}
Specific issue: {subtitle_sync / audio_quality / resolution / duration}
Expected: {what the output should be}
Actual: {what was produced}
Enhancement adjustments: {skip/add face_enhance, color_grade, etc.}
```

## Quality Gates Summary

| Gate | After Stage | What's Checked | Fail Action |
|------|-------------|---------------|-------------|
| G1 | idea | Footage viability, audio presence, user approval | Revise brief OR stop pipeline |
| G2 | script | Transcript confidence, timestamps, section boundaries | Revise script (re-transcribe) |
| G3 | scene_plan | Full coverage, enhancement feasibility, overlay alignment | Revise scene_plan |
| G4 | assets | Subtitle sync, audio extraction, budget | Revise assets OR send-back to script |
| G5 | edit | Timeline completeness, trim validation, subtitle config | Revise edit |
| G6 | compose | Output probe, duration, audio, subtitle burn-in | Revise compose OR send-back to edit/assets |
| G7 | publish | Metadata, packaging | Revise publish |
| FINAL | all | Subtitle sync, audio quality, visual quality | Send-back to specific stage |

## Execution Limits (Anti-Loop Protection)

| Limit | Value | Rationale |
|-------|-------|-----------|
| Max revisions per stage | manifest `orchestration.max_revisions_per_stage` | Prevent perfectionism loops |
| Max send-backs per stage pair | 1 (guidance; no manifest field) | Prevent ping-pong between stages |
| Max total send-backs | manifest `orchestration.max_send_backs` | Cap total pipeline re-work |
| Max total budget | The run budget from `tools/cost_tracker.py::resolve_budget_usd`: the amount the user approved (record it with `python -m tools.cost_tracker budget <project-id> --usd <amount>`), else manifest `orchestration.budget_default_usd` capped at `config.yaml` `budget.total_usd` | Enforcement follows `config.yaml` `budget.mode`: `observe` records only, `warn` records and flags overruns, `cap` refuses a paid call that does not fit the remaining budget |
| Max total wall-time | manifest `orchestration.max_wall_time_minutes` | Timeout for entire pipeline (less generation than explainer) |

Read the manifest-backed values from `pipeline_defs/talking-head.yaml` at the start of the run; never substitute numbers of your own.

After any limit is hit: **proceed with warnings**, never block indefinitely. A limit never approves a human-gated stage (idea, script, scene_plan, assets, publish): write `awaiting_human` with the warnings attached, end the turn, and let the user decide.

## Integration with Existing Skills

The EP doesn't replace any director skill — it wraps them. Each director skill continues to work exactly as documented. The EP adds:

1. **Context injection**: Directors receive EP_STATE with cross-stage information they couldn't access before
2. **Feedback injection**: Directors receive specific revision instructions when sent back
3. **Budget awareness**: Directors receive remaining budget and can adjust tool choices accordingly
4. **Transcript continuity**: The EP carries transcript data forward, ensuring subtitle generation and edit decisions use the same source of truth

## Example EP Run (Abbreviated)

The user-approval stops are omitted for brevity: after idea, script, scene_plan, assets, and publish the EP writes `awaiting_human`, ends the turn, and resumes only once the user approves.

```
[EP] Starting pipeline: talking-head v2.0
[EP] Default budget: $0.50 | Playbook: footage-derived identity (or safe fallback)

[EP] Probing raw footage: interview_raw.mp4
[EP] → Duration: 4m22s | Resolution: 1920x1080 | FPS: 30 | Audio: stereo AAC
[EP] Footage looks viable. Audio present. Proceeding.

[EP] === STAGE 1: idea ===
[EP] Spawning idea-director... Footage: interview_raw.mp4
[EP] Brief: "Interview with CTO on API security" | Target: 3m00s (trim from 4m22s)
[EP] Platform: YouTube Shorts → wait, that's < 60s. User said LinkedIn.
[EP] G1 PASS — Brief references footage, duration target realistic, user approved.

[EP] === STAGE 2: script ===
[EP] Spawning script-director with brief...
[EP] Transcriber: WhisperX large-v3. Processing 4m22s audio...
[EP] Transcript: 612 words, avg confidence 0.91. Language: en.
[EP] 8 sections identified. Timestamps monotonic. ✓
[EP] G2 PASS — Confidence good, sections align with topic changes.

[EP] === STAGE 3: scene_plan ===
[EP] Spawning scene-director with script...
[EP] 8 scenes planned. Total duration: 3m02s (target 3m00s).
[EP] Enhancements: face_enhance on all scenes, color_grade, lower-third overlay at 0:00-0:05.
[EP] face_enhance: checking registry... AVAILABLE ✓
[EP] G3 PASS — Full coverage, enhancements feasible.

[EP] === STAGE 4: assets ===
[EP] Spawning asset-director with scene_plan + script...
[EP] Subtitles generated: 82 cues, SRT format.
[EP] Sync check: max offset 0.18s. All within 0.3s tolerance. ✓
[EP] Audio extracted and normalized to -16 LUFS. ✓
[EP] Lower-third overlay generated via recraft_image. Cost: $0.02.
[EP] Budget: $0.02 spent, $0.48 remaining.
[EP] G4 PASS — Subtitles synced, audio clean, assets on disk.

[EP] === STAGE 5: edit ===
[EP] Spawning edit-director with scene_plan + asset_manifest...
[EP] Timeline: 3m02s with 7 cuts. Subtitles enabled.
[EP] Trim: removed 0:00-0:12 (dead air) and 3:45-4:22 (off-topic).
[EP] G5 PASS — Timeline complete, all references valid.

[EP] === STAGE 6: compose ===
[EP] Spawning compose-director with edit_decisions + asset_manifest...
[EP] face_enhance applied: 8 scenes processed.
[EP] color_grade applied: unified warm tone.
[EP] audio_enhance: noise reduction applied.
[EP] video_compose: final render → output/talking-head-final.mp4
[EP] Output probe: 3m01s, 1920x1080, stereo audio, H.264. ✓
[EP] Budget: $0.18 spent (face_enhance + color_grade + overlays).
[EP] G6 PASS

[EP] === STAGE 7: publish ===
[EP] Spawning publish-director with render_report...
[EP] G7 PASS — Title, description, chapters, thumbnail configured.

[EP] === FINAL QA ===
[EP] Duration: 3m01s ✓ | Subtitle sync: max drift 0.18s ✓ | Audio: -16.2 LUFS ✓
[EP] Face enhance: natural ✓ | Color: consistent ✓ | Overlays: timed correctly ✓
[EP] Budget: $0.18 / $0.50 ✓
[EP] PIPELINE COMPLETE — 0 revisions, 0 send-backs
[EP] Output: output/talking-head-final.mp4
```

## Common Pitfalls

- **Ignoring transcript quality**: Everything downstream depends on the transcript. If confidence is low, fix it in the script stage — don't let bad timestamps propagate to subtitles and edits.
- **Over-enhancing**: Face enhance and color grade are optional. If the raw footage looks good, skip them. Don't add processing for the sake of it.
- **Subtitle style mismatch**: The subtitle style must come from the playbook. Don't let the asset director use default SRT styling when the playbook specifies font/color/position.
- **Not probing raw footage**: Always ffprobe before starting. A video with no audio track or a corrupt container will waste every downstream stage.
- **Trimming too aggressively**: The edit director may cut sections that seem off-topic but contain valuable context. The EP should verify that trimmed content is genuinely unnecessary by checking against the brief.
- **Losing transcript data**: The EP must carry `transcript_segments` from the script stage all the way to asset generation. Subtitle timing depends on the exact same word-level data the transcriber produced.
