# Scene Director - Localization Dub Pipeline

## When To Use

Plan how each localized deliverable will handle timing, visible speech, subtitles, and on-screen text. This is where the pipeline decides whether to preserve the original cut, cover mouth-visible sections, or attempt lip sync.

## Reference Inputs

- `docs/localization-dubbing-best-practices.md`
- `skills/creative/video-editing.md`

## Process

### 1. Choose The Dub Mode Per Deliverable

Use one of:

- `subtitle_only`
- `dub_audio_only`
- `lip_synced`
- `hybrid_covered`

`hybrid_covered` means using B-roll, graphics, or text coverage during sections where visible mouth mismatch would be distracting.

### 2. Map Timing Risk

Identify scenes likely to drift because of:

- fast speech,
- dense legal copy,
- multiple speakers,
- fast cuts,
- visible close-up mouths.

### 3. Note On-Screen Language Dependencies

Record scenes that contain:

- UI text,
- lower thirds,
- title cards,
- baked-in subtitles,
- charts or labels that may need replacement or coverage.

### 4. Use Metadata For Variant Planning

Recommended metadata keys:

- `dub_mode_map`
- `timing_risk_map`
- `on_screen_text_replacement_map`
- `language_variant_notes`

### 5. Quality Gate

- every deliverable has a defined localization treatment,
- timing risks are mapped,
- lip-sync usage is selective,
- text replacement needs are not hidden.

## Common Pitfalls

- Assuming dubbed audio will fit the source timing exactly.
- Choosing lip sync for every shot instead of only the shots that justify it.
- Forgetting about baked-in text until compose time.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
