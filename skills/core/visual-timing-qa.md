# Visual Timing QA

## When to Use

Use `visual_timing_qa` after a video has been rendered and before publish
approval. It is a post-render review helper for checking whether key visual
states line up with narration or script cues.

It is strongest for:

- narration-led explainers;
- animated UI walkthroughs;
- process diagrams and node reveals;
- text or card reveals that must match spoken lines;
- product demos where a specific screen state should appear at a specific line.

Skip it when the video is mostly live-action footage, a human-recorded interview,
music/SFX-led, or when there are no explicit visual timing cues. For general
technical quality checks, use `visual_qa` and `frame_sampler` instead.

Decision rule: run the tool only when a human reviewer can answer a concrete
question such as "when this line is spoken, is the right visual state on screen?"

## Tool

| Tool | Capability |
|------|------------|
| `visual_timing_qa` | Extract cue windows and build review sheets |
| `visual_qa` | Probe and sample general video quality |
| `frame_sampler` | Extract representative or timestamp frames |

## Workflow

1. Mark high-risk visual timing cues during script, scene, or edit planning.
2. Optionally run `suggest_cues` on captions or script JSON to draft candidate
   cues. Confirm or edit `expected_state` before review.
3. Render the final video, or a review render with the final timing.
4. Create a manifest with `video_path`, `output_dir`, and confirmed `cues`.
5. Run `dry_run` to verify cue timestamps and frame windows.
6. Run `review` to extract before/at/after frames and contact sheets.
7. Inspect `review.html` for visual review, or `review.md` for text-first review.
8. Run `annotate` after the agent or reviewer has made an initial decision.
   This writes `review_notes.json`, `review_annotated.md`, and
   `review_annotated.html`.
9. If `annotate` returns `next_operation=revise_and_rerun_review`, send work
   back to edit, compose, scene, or asset generation depending on the cause,
   then render again and run `review` on the revised video.
10. Repeat `review` -> `annotate` until `review_complete=true`. Do not treat a
    partially reviewed page or a page with pending cue fixes as final approval.

## Cue Suggestions

Use `suggest_cues` when a project has captions or a timestamped script but no
confirmed QA manifest yet. The first version is rule-based and local-only; it
does not call a visual model or judge the video automatically.

```json
{
  "operation": "suggest_cues",
  "captions_path": "projects/my-explainer/artifacts/captions.json",
  "output_dir": "projects/my-explainer/reviews/visual-timing/cue-draft",
  "project": "my-explainer",
  "run_id": "cue-draft",
  "speed_multiplier": 1.25,
  "max_cues": 12
}
```

The tool looks for timing-sensitive language such as installation, upgrade,
self-check, real system interfaces, feedback, next-version flow,
ecosystem/asset connections, and question hooks. It writes:

- `suggested_cues.json`: structured candidates;
- `suggested_cues.md`: table plus a manifest draft.

Review the draft before running `review`; fill in `expected_state` using the
approved creative direction.

## Minimal Manifest

```json
{
  "project": "my-explainer",
  "run_id": "final-render-v1",
  "video_path": "projects/my-explainer/renders/final.mp4",
  "output_dir": "projects/my-explainer/reviews/visual-timing/final-render-v1",
  "offsets_seconds": [-0.5, 0, 0.5],
  "tolerance_seconds": 0.5,
  "cues": [
    {
      "id": "feedback-flow",
      "section_id": "s6",
      "label": "Feedback flow reveal",
      "timestamp_seconds": 126.4,
      "narration": "The user reports the issue, and the platform prepares the next Skill version.",
      "expected_state": "The feedback pipeline is visible and the next-version node is highlighted.",
      "risk": "Node reveal may run ahead of the narration.",
      "review_questions": [
        "Is the next-version node visible by the target frame?",
        "Does any label overlap the frame edge?"
      ]
    }
  ]
}
```

For fast checks, use three frames such as `[-0.5, 0, 0.5]`. For animations
that need more temporal context, use a wider five-frame window such as
`[-1.2, -0.6, 0, 0.6, 1.2]`.

## Review

The tool writes:

- `results.json`: cue metadata, frame paths, and contact sheet paths;
- `review.md`: human-readable cue checklist with before/at/after frames;
- `review.html`: browser review page with cue cards, contact sheets, extracted
  frames, initial auto-review status, and reviewer status;
- per-cue frame images and contact sheets.

`review` also runs a conservative local initial review. It does not perform
semantic video understanding, but it flags obvious risks that should not be
left for the user to discover from raw screenshots:

- frame extraction failures;
- little or no visible change around a reveal/highlight cue;
- visual change concentrated before the target frame, suggesting an early
  reveal;
- visual change concentrated after the target frame, suggesting a late reveal;
- subtitle/caption cues whose lower-frame band appears visually empty.

Initial review writes `cue.initial_review` and adds an "Initial auto-review
queue" to both `review.md` and `review.html`. Treat `NEEDS_REVIEW` as a blocker
for agent handoff until the contact sheet has been inspected and either fixed or
explicitly accepted.

This is still human-in-the-loop. Do not treat a local `PASS` as semantic
approval; it only means the conservative heuristics did not find an obvious
timing/layout risk. A reviewer still decides whether the visual state is
correct, crowded, or inconsistent with the line.

## Annotation

Use `annotate` after inspecting the contact sheets. The operation records the
initial reviewer decision without regenerating frames. When the interactive
page submits `unreviewed_policy=PASS`, cues the reviewer did not touch are
recorded as `PASS`; otherwise missing cue decisions keep the review incomplete.

```json
{
  "operation": "annotate",
  "results_path": "projects/my-explainer/reviews/visual-timing/final-render-v1/results.json",
  "annotations": {
    "feedback-flow": {
      "decision": "NEEDS_REVIEW",
      "reviewer": "agent",
      "confidence": "medium",
      "issue_category": "scene_expectation",
      "notes": "The cue appears visually stable, but the expected state mentions a process diagram while the approved ending uses a title card.",
      "fix_target": "Update the cue expectation or ask the user to confirm the approved ending.",
      "requires_user_review": true,
      "user_decision": "DEFERRED",
      "user_notes": "The reviewer will confirm the approved ending direction."
    }
  }
}
```

Decision values:

- `PASS`: timing and visible state match the cue;
- `NEEDS_REVIEW`: likely acceptable or fixable, but needs a human decision;
- `WRONG_EXPECTATION`: the cue expectation is outdated or does not match the
  approved creative direction.

Recommended `issue_category` values:

- `edit_timing`: cue timing or cut timing is early/late;
- `compose_animation`: rendered animation timing needs adjustment;
- `scene_expectation`: cue expectation or scene plan is wrong/outdated;
- `asset_layout`: overlap, cropping, text, or visual layout issue;
- `script_caption_timing`: narration/caption timestamp mismatch;
- `approved`: no fix needed.

Optional `user_decision` values:

- `APPROVED`: user accepts the cue;
- `FIX_REQUESTED`: user wants a revision;
- `DEFERRED`: user will decide later;
- `REJECTED`: user rejects the current visual state.

`annotate` also writes completion fields for iterative review:

- `review_complete=true` and `next_operation=complete`: all cues are reviewed
  and no cue requires changes.
- `review_complete=false` and `next_operation=revise_and_rerun_review`: at
  least one cue needs timing, layout, expectation, or render changes. Fix the
  video, run `review` again, and ask the user to review the new page.
- `review_complete=false` and `next_operation=annotate`: one or more cues are
  still missing a reviewer decision.

Continue this loop until the user has passed every cue on the current rendered
video.
