# Edit Director — Explainer Pipeline

## When to Use

You are the Editor for a generated explainer video. You have an `asset_manifest` with all generated files, a `scene_plan` with visual structure, and a `script` with timing. Your job is to assemble the edit decision list (EDL): what plays when, how elements layer, where subtitles go, and how music and narration interact.

This is where raw assets become a coherent video. Good editing makes average assets shine; bad editing wastes great assets.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/edit_decisions.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["assets"]["asset_manifest"]`, `state.artifacts["scene_plan"]["scene_plan"]`, `state.artifacts["script"]["script"]` | Assets, visual plan, timing |
| Playbook | Active style playbook | Transitions, pacing rules, overlay styles |

## Process

### Step 1: Map Assets to Timeline

For each scene in the scene plan:
1. Find the matching assets from the asset manifest (by `scene_id`)
2. Find the matching narration audio (by script section)
3. Note the scene's timing (`start_seconds`, `end_seconds`)

Build a timeline map:
```
0s-10s: scene-1 (talking_head) | narration-s1 | img-intro.png
10s-18s: scene-2 (diagram) | narration-s2 | diagram-flow.svg
18s-22s: scene-3 (text_card) | narration-s3 | [text overlay]
...
```

### Step 1b: Runtime Carry-Forward (REQUIRED)

The schema rejects `edit_decisions` without `version`, `cuts`, and `render_runtime`, and `video_compose` refuses to render when `render_runtime` or `renderer_family` is missing. Both were locked at proposal — copy them from the approved `proposal_packet.production_plan`; never choose or default them here:

```json
{
  "version": "1.0",
  "render_runtime": "remotion",
  "renderer_family": "explainer-data",
  "metadata": {
    "proposal_render_runtime": "remotion",
    "delivery_promise": {
      "promise_type": "data_explainer",
      "motion_required": false,
      "tone_mode": "educational",
      "quality_floor": "presentable"
    }
  }
}
```

- `render_runtime` — exactly `production_plan.render_runtime` (`remotion`, `hyperframes`, or `ffmpeg`). A different value needs user approval and a `render_runtime_selection` entry in `decision_log`.
- `renderer_family` — exactly `production_plan.renderer_family`. Copy `composition_mode` as well when the proposal set it.
- `metadata.proposal_render_runtime` — the same locked runtime again. `video_compose` falls back to it for runtime-swap detection when it is not handed the `proposal_packet`.
- `metadata.delivery_promise` — a verbatim copy of `production_plan.delivery_promise` (keep `promise_type`). `video_compose` checks the cuts against it before rendering and again in `final_review`; without it the promise check is skipped with a warning.

### Step 2: Define Cuts

Each cut defines what visual is shown and when:

```json
{
  "id": "cut-1",
  "source": "img-scene-1",
  "in_seconds": 0,
  "out_seconds": 10,
  "layer": "primary",
  "transform": {
    "scale": 1.0,
    "position": "center",
    "animation": "ken-burns-slow-zoom"
  },
  "transition_in": "fade",
  "transition_out": "dissolve",
  "transition_duration": 0.4
}
```

**Layering rules:**
- `primary` — main visual (one at a time)
- `overlay` — text cards, stat cards, key terms (on top of primary)
- `background` — solid color or texture behind everything

**Cuts hold schema fields only.** `cuts[]` is closed: besides the fields above only `speed`, `transform.crop`, `backgroundColor`, and `reason` exist. The props the Remotion `Explainer` composition needs — `type` (`text_card`, `stat_card`, `bar_chart`, ...), that template's own props (`stat`, `backgroundVideo`, chart data), Remotion `overlays`, `captions`, `audio.narration.src` — have no place in this artifact and fail the checkpoint if you add them. Name the intended render template in the cut's `reason` (and, when you need structure, under `metadata.remotion_cuts` keyed by cut id). The Compose stage writes those props into a second file, `artifacts/remotion_composition.json`, which is the object actually handed to `video_compose` (compose-director Step 2).

### Step 3: Configure Subtitles

Subtitles are mandatory for all explainer content:

```json
{
  "subtitles": {
    "enabled": true,
    "style": "word-by-word",
    "font": "Inter",
    "font_size": 48,
    "color": "#FFFFFF",
    "background": "#00000088",
    "position": "bottom-center",
    "max_words_per_line": 8
  }
}
```

**Subtitle timing**: Derive from narration audio timestamps. Each word should highlight as it's spoken (word-by-word style) or display in phrase chunks (phrase style).

Use the playbook's typography for font choices.

### Step 4: Configure Audio Layers

```json
{
  "audio": {
    "narration": {
      "segments": [
        { "asset_id": "narration-s1", "start_seconds": 0 },
        { "asset_id": "narration-s2", "start_seconds": 10 }
      ]
    },
    "music": {
      "asset_id": "music-bg",
      "volume": 0.08,
      "fade_in_seconds": 2,
      "fade_out_seconds": 3,
      "ducking": {
        "enabled": true,
        "threshold_db": -3,
        "reduction_db": -8,
        "attack_ms": 200,
        "release_ms": 500
      }
    },
    "sfx": []
  }
}
```

**Music ducking — what actually happens**: `audio.music.ducking` records the intent (use the playbook's `audio.ducking_threshold_db` for `threshold_db`); whether the music really dips depends on the render path:

- `audio_mixer` (`operation: "full_mix"`) is the only tool that ducks. It sidechains the music under the narration and honours `enabled`, `attack_ms`, and `release_ms`; the depth comes from its own `music_volume_during_speech` (default 0.15), not from `threshold_db`/`reduction_db`.
- The Remotion `Explainer` composition never ducks. It plays the music at one flat `volume` with a fade in and out and ignores `ducking` entirely.

So decide the mix here and record it in `metadata.audio_mix_plan`:

- `"premix"` (**recommended whenever narration and music play together**) — keep `ducking.enabled: true`. The Compose stage mixes narration + music with `audio_mixer` and passes the mixed track to `video_compose` as `audio_path`.
- `"flat"` — set `"ducking": {"enabled": false}` and keep `volume` low (0.08–0.12) so the bed never competes with the voice. Honest for music-light pieces; say so in the gate summary.

### Step 5: Apply Pacing Rules

Check the playbook's `motion.pacing_rules`:
- No cut shorter than `min_scene_hold_seconds`
- No cut longer than `max_scene_hold_seconds`
- Text cards hold for `text_card_hold_seconds`
- Transitions use `transition_duration_seconds`

Adjust cut timing if any violates these rules.

### Step 6: Verify Edit Completeness

**Timeline coverage:**
- [ ] Cuts span full video duration (no black frames)
- [ ] No overlapping primary cuts
- [ ] Every scene in scene_plan has at least one corresponding cut

**Asset references:**
- [ ] Every cut's `source` references a valid asset_id from the manifest
- [ ] Every narration segment references a valid audio asset
- [ ] Music asset exists

**Render locks:**
- [ ] `version`, `render_runtime`, and `renderer_family` are set and equal the proposal's locked values
- [ ] `metadata.proposal_render_runtime` and `metadata.delivery_promise` are copied from the proposal

**Audio sync:**
- [ ] Narration segments are ordered and non-overlapping
- [ ] Narration timing aligns with corresponding visual cuts
- [ ] Music ducking is configured and `metadata.audio_mix_plan` says who performs it (`premix`) or that the bed is flat (`flat`)

**Subtitles:**
- [ ] Subtitles enabled
- [ ] Subtitle style uses playbook-compatible fonts and colors

### Step 7: Self-Evaluate

Score (1-5):

| Criterion | Question |
|-----------|----------|
| **Continuity** | Does every second of the video have a visual? |
| **Pacing** | Do cuts follow the playbook's timing rules? |
| **Audio-visual sync** | Does what you see match what you hear at every moment? |
| **Subtitle quality** | Are subtitles readable and correctly timed? |
| **Transition coherence** | Do transitions follow the playbook's allowed set? |

If any dimension scores below 3, revise.

### Step 8: Submit

Validate the edit_decisions artifact against the schema and persist via checkpoint.

## Common Pitfalls

- **Forgetting gaps**: If scene-1 ends at 10s and scene-2 starts at 10.5s, there's a 0.5s black frame. Check for gaps.
- **Audio drift**: Narration audio may be slightly longer/shorter than planned. Adjust visual cuts to match actual narration durations, not planned durations.
- **No ducking**: Music playing at full volume under narration makes the video unwatchable. Always decide how the music sits under the voice — and remember that writing `ducking` into the artifact does nothing on the Remotion path by itself: either the Compose stage pre-mixes with `audio_mixer` (`premix`) or the music stays flat and low (`flat`).
- **Same transition everywhere**: Varying transitions creates rhythm. Use the playbook's allowed set, but don't use the same one for every cut.
- **Subtitle font mismatch**: Subtitles should use the playbook's body font, not a random default.
