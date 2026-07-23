# Scene Director - Avatar Spokesperson Pipeline

## When To Use

Plan the visual system for the presenter-led cut. This stage decides how the speaker sits in frame, what support layers appear, and which aspect ratios are actually worth building.

## Reference Inputs

- `docs/avatar-spokesperson-best-practices.md`
- `skills/creative/typography.md`

## Process

### 1. Lock The Presenter Layout

Choose a primary layout:

- full presenter center frame,
- presenter plus side panel,
- presenter plus lower-third system,
- presenter over branded background.

Keep the hero layout simple and reusable.

### 2. Choose Background Discipline

Use one family:

- clean solid or gradient background,
- branded office or set,
- product UI or image plate,
- transparent-avatar composite plan.

Background changes should mark real section changes, not compensate for weak copy.

### 3. Map Support Layers

For each scene, decide whether the support layer is:

- none,
- subtitle only,
- lower third,
- product image,
- side-panel proof point,
- CTA card.

### 4. Plan Variants Late

Default to one hero cut first. Only plan vertical or square variants if the presenter layout and text system can survive the crop.

### 5. Quality Gate

- the presenter remains primary,
- support layers solve specific communication needs,
- the background system is consistent,
- variant ambition stays realistic.

## Narration-Over-Graphics Fallback

When the EP triggers a no-avatar pivot (no `talking_head` or `lip_sync` available), redesign the visual system to carry the story with graphics and voice-over instead of a presenter:

### Layout changes:
- **Primary frame**: full-screen visual (background, image, diagram, or motion graphic) with voice-over narration underneath.
- **Support layers**: key-point text cards, lower-third stats, illustrated diagrams, product screenshots.
- **CTA scene**: dedicated end card with clear CTA text, no presenter needed.

### What stays the same:
- The script and scene breaks are unchanged — the narration drives pacing.
- Subtitle planning is unchanged.
- Background discipline still applies (consistent family, not random).

### What changes:
- No presenter framing decisions (center, left-third, etc.) — replaced with full-frame visual compositions.
- Each scene needs a **primary visual** that reinforces the spoken content, since there's no face to anchor attention.
- Plan more visual variety per scene — without a presenter, static backgrounds feel empty.

## Common Pitfalls

- Switching backgrounds every few seconds.
- Filling empty space with decorative panels.
- Assuming a landscape presenter layout will survive a vertical crop untouched.
- (Fallback mode) Producing a wall of text on screen to compensate for no presenter — let the narration carry the content.

---

## Gate Reminder (Binding)

This stage gates on human approval (`human_approval_default: true`). After review passes:
checkpoint with `status="awaiting_human"`, present the summary (the Backlot board renders
the artifact), and **END YOUR TURN**. Do not start the next stage in the same response.
Approval is per-gate — an earlier "go ahead" does not cover this gate.
