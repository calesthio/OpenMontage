# Pre-render Narration Sync Gate

## When to Use

Use `pre_render_narration_sync_gate` after final narration is locked and before
rendering the final video.

It checks whether the planned video is still aligned with the actual narration:

- caption text matches the locked narration text;
- on-screen text is still related to the narration segment;
- visual cue timestamps are close to the narration anchor;
- terminology rules are respected, such as using `TraceID` instead of `TID`.

This is a pre-render gate. It does not inspect rendered frames. Use
`visual_timing_qa` after rendering when you need frame-level review.

## Workflow

1. Lock final TTS narration and segment timings.
2. Prepare captions, screen text, and planned visual cue timings.
3. Run `pre_render_narration_sync_gate`.
4. If `recommended_next_action=revise_before_render`, fix the deterministic
   mismatch and rerun the gate before rendering.
5. If `recommended_next_action=agent_review_required`, inspect the review page.
   Ask the user only when the remaining question is semantic or creative.
6. If `recommended_next_action=ready_to_render`, proceed to render.

## Minimal Manifest

```json
{
  "project": "my-explainer",
  "run_id": "pre-render-sync-v1",
  "output_dir": "projects/my-explainer/reviews/pre-render-sync-v1",
  "tolerance_seconds": 0.4,
  "narration_segments": [
    {
      "id": "s1",
      "section_id": "s1",
      "text": "Use TraceID to follow the request across systems.",
      "start_seconds": 1.0,
      "end_seconds": 4.0
    }
  ],
  "captions": [
    {
      "section_id": "s1",
      "text": "Use TraceID to follow the request across systems.",
      "start_seconds": 1.0,
      "end_seconds": 4.0
    }
  ],
  "visual_cues": [
    {
      "id": "traceid-query",
      "section_id": "s1",
      "timestamp_seconds": 1.2,
      "narration_anchor": "TraceID",
      "expected_state": "TraceID query field is highlighted."
    }
  ],
  "term_rules": [
    {
      "required": "TraceID",
      "forbidden": ["TID"]
    }
  ]
}
```

The tool also accepts `tts_selection_path`, `captions_path`,
`subtitles_path`, `screen_texts_path`, and `visual_cues_path` when those
artifacts already exist as JSON files.

## Outputs

- `results.json`: machine-readable sync findings and route.
- `review.md`: text-first summary.
- `review.html`: compact browser review page.

`status=needs-revision` means the issue is deterministic and should be fixed
before render. `status=needs-agent-review` means the agent should inspect the
warning before deciding whether to ask the user. `status=passed` means this
gate found no pre-render sync issues.
