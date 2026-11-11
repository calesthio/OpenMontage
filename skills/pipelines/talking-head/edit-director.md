# Edit Director — Talking Head Pipeline

## When to Use

You have a scene plan and asset manifest. Your job is to assemble the edit decision list for a talking-head video: primarily keeping the full footage with subtitle overlay and optional enhancements.

## Runtime Carry-Forward (REQUIRED)

Set `edit_decisions.render_runtime` to the runtime locked at the idea stage (the `render_runtime_selection` decision in `decision_log`) — `"remotion"` or `"ffmpeg"` on this pipeline. The schema requires the field and `video_compose` refuses to render without it. Carry the locked value forward unchanged; never default it or pick a different one here.

This pipeline has no proposal stage, so there is no `proposal_packet` for compose to compare against. Also copy the same locked value into `edit_decisions.metadata.proposal_render_runtime` — that is what the `video_compose` runtime-swap check reads; without it the check reports `skipped`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | Scene plan, Asset manifest, Script | Edit inputs |
| Playbook | Active style playbook | Transition and pacing rules |

## Process

### Step 1: Apply Silence Cuts (if planned)

If the scene plan includes silence removal, run `silence_cutter` before defining cuts:

```
silence_cutter.execute({
    "input_path": "<raw_footage>",
    "mode": "remove",           # or "speed_up" for less jarring result
    "silence_threshold_db": -35,
    "min_silence_duration": 0.5,
    "padding_seconds": 0.08,    # prevents clipped words
    "output_path": "<project>/assets/video/footage_cut.mp4"
})
```

**Choosing the mode:**
- `remove` — Hard jump cuts. Best for fast-paced social content (Reels, TikTok, Shorts)
- `speed_up` — Fast-forwards through silence at 6x. Less jarring for longer-form content (YouTube, LinkedIn)

Present the result to the user: "Removed X seconds of silence (Y%) — output is now Z seconds."

Use the cut footage as the source for all subsequent steps.

### Step 2: Define Primary Cut

For talking-head, the primary cut is usually the full footage (or trimmed segments). Create cuts that:
- Reference the raw footage (or silence-cut footage) as source
- Use timestamps from the script sections
- Apply any trim decisions (cut dead air, false starts)

### Step 3: Configure Subtitles

- Enable subtitles with playbook-compatible styling
- Reference the subtitle asset from the manifest
- Set position (usually bottom-center)

### Step 4: Configure Audio

- Set narration to the raw footage audio
- If background music is desired, configure ducking
- Set music volume per playbook

### Step 5: Plan Enhancements

If the scene plan includes overlays:
- Add overlay cuts for text cards, lower thirds
- Time them to match speech content

### Step 6: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Coverage** | Do cuts span the full intended duration? |
| **Silence** | Were silence cuts applied if planned? What % was removed? |
| **Subtitles** | Are subtitles enabled and styled? |
| **Audio** | Is audio configuration complete? |

### Step 7: Submit

Validate the edit_decisions against the schema and persist via checkpoint.
