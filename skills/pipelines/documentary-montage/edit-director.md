# Edit Director - Documentary Montage Pipeline

## When To Use

Every slot has a clip. You now have to turn a pile of clips into a
piece. This stage decides in-points, out-points, transitions, music
sync, and the order the clips actually run. The output is an
`edit_decisions` artifact with a concrete timeline.

This is where documentary technique lives. If the asset director did
its job, you have the raw material. The edit is the thinking.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifact | `state.artifacts["assets"]["asset_manifest"]` | Picked clips + music bed |
| Prior artifact | `state.artifacts["scene_plan"]["scene_plan"]` | Slot order, hero flags, target holds |
| Prior artifact | `state.artifacts["idea"]["brief"]` | Tone register, duration, shape |
| Tool (optional) | `video_analyzer` | Probe a clip's motion if you need to re-check |

## Mental Model

Documentary montage lives in four dimensions you have to balance:

1. **Rhythm** — how long each hold lasts and how the holds relate.
2. **Juxtaposition** — which image follows which, and what it means.
3. **Music sync** — cuts landing on beats, dropouts earning weight.
4. **Continuity of register** — the grain, color, and era don't swing
   wildly unless the swing is the point.

The enemy is "slideshow" — a sequence of clips played back-to-back
with the same hold length and no sound design. If it feels like a
slideshow, the edit has failed, regardless of how good the clips are.

This stage also locks the render grammar. For documentary montage,
set `renderer_family` to `documentary-montage` so compose stays on the
approved Remotion-first path.

## Process

### 0. Guardrails — No Silent Major Changes

Before touching the timeline, re-read the brief. If any of these are
true, STOP and surface to the user per the Decision Communication
Contract:

- The brief approved "no narration" but the edit feels like it needs
  voice-over. Narration is a MAJOR change.
- The brief approved a music track that the edit director now wants
  to replace. Music swap is a MAJOR change.
- The brief approved a 90s duration but the natural cut wants 2m30s.
  Duration stretch is a MAJOR change.

Fix the edit, don't paper over it. If the edit genuinely needs
one of these, ask.

### 1. Set The Rhythm Grid

Read `brief.tone` and `brief.duration_seconds`. Compute the hold
table from the scene director's tone chart:

| Tone | Base hold | Min hold | Max hold |
|------|-----------|----------|----------|
| elegiac | 4.0s | 2.5s | 7.0s |
| reverent | 3.5s | 2.0s | 6.0s |
| dreamlike | 3.0s | 1.5s | 5.5s |
| wry | 2.0s | 1.0s | 4.0s |
| urgent | 1.2s | 0.5s | 2.5s |

**Hero slots get max hold.** Mid-sequence cutaways get base. Quick
transitions get min.

Total hold time must sum to within ±10% of `brief.duration_seconds`.
If you overshoot, compress non-hero holds first — never cut heroes
short to fit duration.

### 2. Arrange By Narrative Beat, Not By Score

The scene director gave you a slot order. That order is the intent.
Don't rearrange it by CLIP score, motion score, or resolution.

You MAY reorder slots when:

- The music bed has a downbeat at a known timestamp and reordering
  two slots lands a hero on the beat (see step 4).
- Two adjacent slots are visually identical and swapping one breaks
  the monotony (but see step 7 — diversify should have caught this
  already).
- The final image isn't landing. The last 5-10s carries
  disproportionate weight; if the scene director's choice dies, move
  a stronger candidate to the tail.

Always log the reorder in `edit_decisions.metadata.reorder_notes`
with the reason.

### 3. Trim Each Clip To Its Beat

For every picked clip, decide `in_seconds` and `out_seconds`. Three
rules:

- **Find the best sub-window, not the whole clip.** A 12-second Pexels
  clip usually contains one 3-second moment that earns the hold and
  9 seconds of setup/settle. Find the moment.
- **Cut BEFORE the action's natural end.** End on a look, not on a
  move-off. The cut feels intentional instead of exhausted.
- **Leave a handle at both ends.** 4-6 frames of headroom so the
  composer can apply a fade or dissolve without clipping the moment.

If a clip is too short to fill its target hold, either:

- slow it down (speed 0.5-0.75, fine on static-ish footage, bad on
  anything with sync motion or faces talking),
- let it cut early and borrow the remaining duration from the next
  slot's hold,
- or swap to the #2 candidate from the rejected-picks log.

Do NOT hold on the last frozen frame. A freeze-frame in a doc montage
reads as a technical mistake.

### 4. Sync To The Music Bed

Read `asset_manifest` for the music asset and load its duration.
Documentary montages earn their emotional weight from cuts landing
on musical events. Three sync moves:

- **Downbeat cuts.** If you have bars and beats metadata (from a
  provided track) or can hear them, place hero cuts on downbeats.
  If not, evenly-spaced cuts on 4s intervals for a 60bpm bed are a
  safe default.
- **One held silence.** Drop the music out for ~2s at the piece's
  emotional center. Silence is a tool. Use it once. Use it hard.
- **Tail fade.** Music fades under the last 3-5s so the final image
  can breathe without a musical resolution fighting it.

Record the music config in `edit_decisions.audio.music` with:

```json
{
  "asset_id": "asset_music_bed",
  "volume": 0.7,
  "fade_in_seconds": 1.0,
  "fade_out_seconds": 4.0,
  "ducking": false
}
```

`ducking: false` is the default for this pipeline — there's no
narration to duck under. If the user approved a narration track, set
ducking to true and let it dip during segments.

### 5. Choose Transitions From A Small Vocabulary

Documentary montage uses maybe four transitions total across the
entire piece:

| Transition | Use |
|------------|-----|
| `cut` (hard) | Default. Most cuts are hard cuts. |
| `dissolve` (0.5-1.0s) | Emotional sibling clips, time passage |
| `fade_to_black` (0.5s, then back up) | Act breaks in 3-act shape, or once near the end |
| `fade_in` (first shot) / `fade_out` (last shot) | 0.5-1.0s bookends |

**Do not use:**

- wipes,
- push/slide transitions,
- zoom blurs,
- RGB splits,
- light leaks,
- glitch effects.

These read as social-media edit language and will break the
documentary register. If the piece is getting boring, fix the clip
choices or the pacing, don't add transition flash.

Record each cut's `transition_in` / `transition_out` per the schema.
Default `transition_in: "cut"` on most cuts.

### 6. Apply Register Continuity

Mixed-era corpora look wildly different. Pexels 2023 is clean, sharp,
color-graded. Prelinger 1962 is grainy, warm, squared-off aspect.
NASA archival is often low-res with text overlays. If you mash them
together raw, the piece looks like a Wikipedia article.

You have two tools to smooth this:

1. **Crop to a uniform aspect ratio.** Pick one: 16:9 cinematic
   (`2.35:1` letterbox on top/bottom) for hero pieces, 9:16 for
   social. Enforce in the `transform.crop` field of each cut.
2. **Flag the piece for a uniform color grade at compose time.** Put
   a `grade_profile` hint in `edit_decisions.metadata`. The compose
   director will apply a LUT across the whole timeline.

Don't try to color-grade individual clips here. That's the compose
stage. Your job is to flag the need.

### 7. Enforce Adjacent Diversity One More Time

Walk the timeline in pairs. For each consecutive (cut_n, cut_n+1):

- Are they the same subject at the same scale? If yes, you have a
  slideshow moment. Swap one for a clip at a different scale (wide
  vs close).
- Are they the same color palette (two night-blue clips back to
  back)? If yes, break the pattern at least every 4 cuts.
- Are they the same motion direction (two left-to-right pans)? If
  yes, flip the second's horizontal axis or reorder.

Log any swaps you made in `metadata.diversity_swaps`.

### 8. The L-Cut Move (Optional But Powerful)

For any transition between two clips where the outgoing clip has
strong ambient audio (rain, footsteps, traffic), carry the audio
under the incoming clip for 0.5-1.5s. This is an L-cut and it
welds two shots together more tightly than any visual transition.

Implement via the schema by using a short `dissolve` transition OR
by layering the outgoing clip's audio as an SFX entry in
`edit_decisions.audio.sfx` with a delayed end.

Documentary montages with L-cuts feel 50% more coherent than ones
without. Use them on the 3-4 hardest transitions in the piece.

### 8b. Place The End-Tag Overlay

If `brief.metadata.end_tag_plan.mode == "overlay"` (the default), the
end-tag will be composited on top of the final body footage at compose
time. The edit director's job is to decide **when** the tag appears.

Compute the offset: `offset_seconds = body_duration - tag_duration`.
This makes the tag's fade-out align with the body's closing fade-out
(the last cut's `transition_out: fade_out`). If the final cut's hold
is shorter than the tag duration, start the tag earlier so it overlaps
the second-to-last cut as well — this is fine and often looks better.

Record in `edit_decisions.end_tag`:

```json
{
  "end_tag": {
    "offset_seconds": 84.5,
    "notes": "Tag starts at body_duration - tag_duration. Aligns tag fade-out with final cut fade-out."
  }
}
```

If `mode == "concat"`, omit this section — the compose-director will
append the tag after the body without needing a timing offset.

### 9. Emit The Edit Decisions

Canonical shape for this pipeline:

```json
{
  "version": "1.0",
  "renderer_family": "documentary-montage",
  "cuts": [
    {
      "id": "cut_01",
      "source": "asset_slot_01",
      "in_seconds": 1.2,
      "out_seconds": 5.2,
      "layer": "primary",
      "transform": { "scale": 1.0, "position": "center" },
      "transition_in": "fade_in",
      "transition_out": "cut",
      "transition_duration": 0.8,
      "reason": "opening hero — raindrop on asphalt, 4s hold, slow-motion streetlamp glow"
    },
    {
      "id": "cut_02",
      "source": "asset_slot_02",
      "in_seconds": 2.0,
      "out_seconds": 5.5,
      "layer": "primary",
      "transition_in": "cut",
      "transition_out": "cut",
      "reason": "umbrella opening in doorway, hard cut from raindrop → street"
    }
  ],
  "audio": {
    "music": {
      "asset_id": "asset_music_bed",
      "volume": 0.7,
      "fade_in_seconds": 1.0,
      "fade_out_seconds": 4.0,
      "ducking": false
    }
  },
  "end_tag": {
    "offset_seconds": 84.5,
    "notes": "Tag starts at body_duration - tag_duration. Aligns tag fade-out with final cut fade-out."
  },
  "metadata": {
    "pipeline": "documentary-montage",
    "tone": "elegiac",
    "shape": "list",
    "total_duration_seconds": 90.0,
    "hold_table_used": { "base": 4.0, "min": 2.5, "max": 7.0 },
    "grade_profile": "warm_film_100",
    "reorder_notes": [],
    "diversity_swaps": [
      { "at": "cut_07-cut_08", "reason": "two wide rooftops-in-rain adjacent, swapped 08 for #2 pick" }
    ],
    "silence_window": { "start_seconds": 54.0, "end_seconds": 56.0 },
    "l_cuts": [
      { "from_cut": "cut_05", "to_cut": "cut_06", "carry_seconds": 1.2, "channel": "ambient_rain" }
    ]
  }
}
```

### 10. Quality Gate

- `sum(out - in for cut in cuts)` is within ±10% of
  `brief.duration_seconds`.
- `renderer_family = "documentary-montage"` is present and unchanged.
- Hero slots have the longest holds.
- No two adjacent cuts share subject AND scale.
- The transition vocabulary is at most 4 distinct values.
- Music config exists (or brief explicitly says no music).
- At least one `silence_window` entry for pieces >= 60s.
- Every cut has a one-line `reason` — if you can't write one, the
  cut is arbitrary and should be reconsidered.
- `metadata.total_duration_seconds` matches the sum of cut durations.

## Common Pitfalls

- **Cutting by information density instead of rhythm.** A doc
  montage is not a Wikipedia article. "But I need to show this" is
  not a reason — if the image doesn't sustain a hold, it doesn't
  belong.
- **Over-using dissolves.** A dissolve on every cut says "I couldn't
  commit". Commit.
- **Ignoring the music bed until the end.** Music is not a sweetener
  you add at compose time. It is a timing grid you cut TO.
- **Letting the final image be a weak one.** The last frame is
  disproportionately remembered. If it's weak, swap it — the scene
  director's slot ordering is a strong suggestion, not a contract.
- **Freeze-frame endings.** Reads as technical error. End on a
  fade-to-black instead.
- **Silently adding a narration because the edit feels thin.** Major
  change. Ask.
- **Hiding clip provider in the cuts.** Every `cut.source` must be
  an `asset_manifest` asset_id so provenance survives.
- **Three different transition types in the first 15 seconds.**
  Readers will feel the edit working. Restraint is the brand.

## Worked Pacing Example — "A Minute in the Rain"

90 seconds, elegiac, list shape, 15 hero-flagged slots.

- Base hold 4.0s × 15 = 60s. Short by 30s.
- Add 30s across 3 hero slots (1, 11, 15) at +10s each:
  hero_1 = 5.5s, hero_11 = 6.0s, hero_15 = 7.0s.
- Tighten slots 4, 7, 13 to 3.0s each (small cutaways).
- Insert silence_window 54.0-56.0s (right before hero_11).
- L-cut slot_10 (boot in puddle) → slot_11 (lit window across
  street), carry rain-on-glass ambient 1.2s.
- First cut `fade_in` 1.0s, last cut `fade_out` 1.5s.
- All other cuts hard.
- Music fades in 1.0s, fades out 4.0s under hero_15 + black.

This gives a 90s piece with 3 breathing points (fade_in, silence,
fade_out), a clear hero arc (slots 1 → 11 → 15), and no adjacent
scale collisions.
