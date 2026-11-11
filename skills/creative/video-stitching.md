# Video Stitching Strategy Skill

## When to Use

Apply this skill when assembling multiple video clips into a unified output:
sequential narrative assembly, multi-take compilation, AI-generated clip chaining
(e.g., LTX-2 produces max ~8s per clip), or spatial compositions like side-by-side
comparisons and picture-in-picture commentary.

## Tools

| Tool | Role |
|------|------|
| `video_trimmer` | Cut segments to precise in/out points, concatenate clips (`concat` operation) |
| `video_stitch` | Join clips with a transition (`stitch`: `transition` = `cut` \| `crossfade` \| `fade`), check clip compatibility (`validate`), and build two-clip spatial layouts (`spatial`: `layout` = `side_by_side` \| `vertical_stack` \| `picture_in_picture`) |
| `video_compose` | Full composition from `edit_decisions` (its `render` operation hands cuts with `transition_in` / `transition_out` to Remotion), subtitles, audio mux, positioned overlays (`overlay` operation) — it has no FFmpeg `xfade`, `hstack`, `vstack` or `xstack` path |
| `frame_sampler` | Inspect frames at stitch boundaries for visual continuity |
| `audio_mixer` | Mix, duck, and crossfade audio tracks across stitch points |
| `scene_detect` | Find natural scene boundaries in source footage |

## When to Stitch — Decision Tree

```
Do you have multiple clips that need to become one video?
├── YES: Are they sequential (play one after another)?
│   ├── YES: Are they from the same shoot / same scene?
│   │   ├── YES → Multi-take assembly (pick best takes, stitch)
│   │   └── NO → Sequential narrative (match cuts, handle transitions)
│   └── NO: Do clips need to appear simultaneously on screen?
│       ├── YES → Spatial composition (side-by-side, PIP, stack)
│       └── MIXED → Hybrid (sequential with spatial inserts)
├── AI-generated clips (LTX-2, CogVideo)?
│   └── YES → AI clip chaining (handle 8s boundaries, maintain continuity)
└── NO → No stitching needed. Use video_trimmer for single-clip edits.
```

## Stitch Strategies

### 1. Sequential Stitching

Clips play one after another in timeline order. This is the most common strategy.

**When:** Narrative videos, multi-section explainers, compiled takes.

**Process:**
1. Order clips by narrative sequence (not filename)
2. Trim each clip to precise in/out points via `video_trimmer` (operation: `cut`)
3. Select transition type for each junction (see Transition Selection below)
4. Concatenate via `video_trimmer` (operation: `concat`) for hard cuts, or `video_stitch` (operation: `stitch`) for transitions requiring filters. `video_stitch` applies ONE `transition` and `transition_duration` to every junction in the call — for mixed transitions, stitch in groups (hard-cut groups first, then join the groups)
5. Verify audio continuity across all stitch points

**Audio continuity rules:**
- Match audio levels across clips before stitching (normalize to -16 LUFS)
- If background music spans multiple clips, mix it as a single track via `audio_mixer` and mux post-concat
- Never let music cut abruptly at a stitch point — crossfade or duck instead

### 2. Spatial Stitching

Multiple clips visible simultaneously on screen.

**When:** Reactions, comparisons, commentary, multi-angle coverage.

All three layouts are `video_stitch` with `operation: "spatial"` and `clips: [first, second]`.

| Layout | `video_stitch` `layout` | FFmpeg Filter | Use Case |
|--------|-------------------------|---------------|----------|
| Side-by-side (duet) | `side_by_side` | `hstack` | Reaction videos, before/after |
| Vertical stack | `vertical_stack` | `vstack` | Comparison (top vs bottom) |
| Picture-in-picture (PIP) | `picture_in_picture` (or `video_compose` `overlay` operation for exact x/y/size) | `overlay` | Commentary, webcam + screen |
| Grid (2x2, 3x3) | — not available | `xstack` — no tool builds it | Multi-angle, compilation |

**Tool limits:** `spatial` uses the first two clips only. There is no grid layout and no
split-ratio control: `side_by_side` scales both clips to 480px height, `vertical_stack` scales both
to 540px width, so the output size is fixed by the tool.

**Spatial layout decision tree:**
```
What relationship do the clips have?
├── Reaction / response → Side-by-side (duet) — equal split only; use PIP when the main clip must dominate
├── Before / after → Side-by-side, equal 50/50 split
├── Comparison (A vs B) → Vertical stack or side-by-side depending on aspect ratio
├── Commentary over content → PIP, speaker in corner (20-25% frame size)
├── Multi-angle same event → Grid is not available — cut between angles, or show two at a time side-by-side
└── Screen recording + face → PIP, face cam in bottom-right corner
```

**PIP placement rules:**
- Default position: bottom-right (`pip_position: "bottom_right"`, the tool default) with 20px padding — pass `pip_margin: 20`; the tool default is `pip_margin: 10`
- Size: 20-25% of frame width for commentary, 30-35% for equal importance — pass `pip_scale: 0.2`-`0.25` or `0.3`-`0.35`; the tool default is `pip_scale: 0.3` (allowed 0.1-0.5)
- `pip_scale` multiplies the PIP clip's own size, so it equals a share of the frame only when both clips have the same resolution
- `clips[0]` is the full-screen base, `clips[1]` is the PIP; only the base clip's audio is kept
- Always ensure PIP does not cover critical content (subtitles, key visuals)
- `video_stitch` draws no border or shadow around the PIP — rely on placement and contrast to separate it from the background

### 3. AI Clip Chaining (LTX-2 / CogVideo)

AI video generators produce short clips (LTX-2: ~8 seconds max). Stitching them
into longer sequences requires special care to maintain visual continuity.

**Process:**
1. Generate clips with overlapping prompts — last frame description of clip N should match first frame description of clip N+1
2. Use `frame_sampler` to extract the last frame of clip N and first frame of clip N+1
3. Visually inspect the pair for continuity breaks (color shift, subject position, background change)
4. If discontinuity is minor → use a 0.5-1.0s crossfade to smooth the junction
5. If discontinuity is major → insert a fade-through-black (0.5s out + 0.5s in) to signal scene transition
6. After stitching, apply a global color grade to unify the visual tone across clips

**AI clip chaining pitfalls:**
- AI clips may have inconsistent FPS — normalize all clips to the same FPS before stitching
- Color temperature often shifts between generations — apply consistent color grade post-stitch
- Motion direction may not match — review last/first frames for jarring movement reversals
- Audio (if any) will not be continuous — strip AI audio and use a single music/narration track

### 4. Hybrid Stitching

Sequential flow with spatial inserts at specific moments.

**When:** Explainer that switches to side-by-side for comparisons, tutorial that
shows PIP during demonstrations, documentary with occasional split-screen.

**Process:**
1. Plan the timeline: mark which segments are sequential and which are spatial
2. Render each spatial segment as a standalone composed clip via `video_stitch` (operation: `spatial`) or `video_compose` (overlay operation)
3. Treat the rendered spatial clips as regular clips in the sequential stitch
4. Concatenate everything in order using the sequential stitching process

## Transition Selection

### Decision Tree

```
What is the relationship between clip N and clip N+1?
│
├── Same scene, continuous action?
│   └── HARD CUT (0ms)
│
├── Same topic, different angle or take?
│   └── HARD CUT (0ms) — use J-cut or L-cut for audio smoothing
│
├── Topic change or new section?
│   └── CROSSFADE (0.5-1.0s)
│
├── Time passage or mood shift?
│   └── CROSSFADE (1.0-1.5s)
│
├── Major section break (intro→body, body→outro)?
│   └── FADE THROUGH BLACK (0.5-1.0s)
│
├── Dialogue transition between speakers?
│   └── L-CUT or J-CUT (audio leads or trails by 0.3-0.5s)
│
└── AI clip boundary (LTX-2 chain)?
    ├── Continuity is good → HARD CUT or short CROSSFADE (0.3-0.5s)
    └── Continuity is broken → FADE THROUGH BLACK (0.5s)
```

### Transition Reference

| Transition | Duration | Implementation | Best For |
|-----------|----------|----------------|----------|
| Hard cut | 0ms | `video_trimmer` concat (codec: copy), or `video_stitch` with `transition: "cut"` | Same scene, fast pace, continuation |
| Crossfade | 0.5-1.5s | `video_stitch` — `operation: "stitch"`, `transition: "crossfade"`, `transition_duration` (uses the `xfade` filter) | Topic change, time passage, mood shift |
| Fade through black | 0.5-1.0s each | `video_stitch` — `transition: "fade"` (`xfade` fadeblack); `transition_duration` is the total out + in time | Major section break, intro/outro |
| L-cut | 0.3-0.5s | Audio from clip N continues into clip N+1's video | Smooth dialogue exit, lingering emotion |
| J-cut | 0.3-0.5s | Audio from clip N+1 starts under clip N's video | Dialogue anticipation, building tension |

### Transition Duration by Content Pace

| Pacing | Crossfade | Fade Through Black |
|--------|-----------|-------------------|
| Fast (short-form, < 60s) | 0.3-0.5s | 0.3-0.5s |
| Medium (1-10 min) | 0.5-1.0s | 0.5-0.8s |
| Slow (documentary, > 10 min) | 1.0-1.5s | 0.8-1.0s |

## Audio Coordination

### Audio at Stitch Points

```
What audio exists at the stitch boundary?
│
├── Both clips have narration/dialogue?
│   ├── Hard cut → Ensure no audio pop (cut at zero-crossing or apply 5ms fade)
│   ├── Crossfade → Duck outgoing audio -6dB during overlap, bring in incoming
│   └── L-cut/J-cut → Blend: outgoing audio fades -∞dB over 0.3-0.5s
│
├── Music spans the stitch?
│   ├── Same track continues → Do not re-encode audio; use stream copy
│   ├── Track changes → Crossfade music 1.0-2.0s centered on the cut point
│   └── Music + narration → Duck music 18-20 dB under narration at all times (`audio_mixer` `duck_level: -18` to `-20`; the tool default is -12)
│
├── One clip has audio, the other is silent?
│   └── Add a 0.3s fade-in/fade-out to avoid abrupt silence transitions
│
└── No audio on either clip?
    └── No audio coordination needed. Add music/narration as a single track post-stitch.
```

### Audio Level Targets

| Content Type | Target LUFS | Headroom |
|-------------|-------------|----------|
| Narration / dialogue | -16 LUFS | -1 dB true peak |
| Background music (under narration) | 18-20 dB below narration (see `sound-design.md`) | -1 dB true peak |
| Music only (no narration) | -14 LUFS | -1 dB true peak |
| Sound effects | -20 LUFS | -1 dB true peak |

## Quality Checklist

Before declaring a stitch complete, verify every item:

- [ ] **Resolution match:** All input clips have the same resolution (or are scaled to match before stitching)
- [ ] **FPS match:** All input clips share the same frame rate (or are conformed with `fps` filter)
- [ ] **Aspect ratio consistency:** No mixed 16:9 / 9:16 / 4:3 unless intentional spatial layout
- [ ] **Color consistency:** No visible color temperature or exposure jumps at stitch boundaries
- [ ] **Audio level consistency:** All clips normalized to target LUFS before stitching
- [ ] **No audio pops or clicks:** Stitch points have micro-fades or are at zero-crossings
- [ ] **Transition appropriateness:** Transition type matches the content relationship (see decision tree)
- [ ] **Total duration check:** Final output duration matches expected sum (accounting for transition overlaps)
- [ ] **Codec consistency:** All clips use the same codec to allow stream copy; re-encode only if necessary
- [ ] **Playback test:** Scrub through every stitch point in the output and confirm smooth playback

## Common Pitfalls

### Codec Mismatch Causing Full Re-encode

**Problem:** Mixing clips encoded with different codecs (e.g., H.264 + H.265) or different
encoding parameters forces FFmpeg to re-encode everything during concat.

**Solution:** Before stitching, probe all clips with `ffprobe`. If codecs differ, re-encode
the minority clips to match the majority codec. This is faster than re-encoding everything.

```
Check: ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,width,height,r_frame_rate -of csv=p=0 input.mp4
```

### Audio Drift in Long Stitches

**Problem:** When concatenating many short clips (10+), tiny timing mismatches accumulate,
causing audio to drift out of sync by the end.

**Solution:**
1. Re-encode each clip with constant frame rate before concatenation (`-vsync cfr`)
2. If using a separate audio track, align it to the final video's duration post-stitch
3. For AI clip chains, use `-async 1` to resync audio on concatenation

### Aspect Ratio Mixing

**Problem:** Stitching a 16:9 clip with a 9:16 clip creates letterboxing or stretching.

**Solution:** Decide on a target aspect ratio up front. Pad non-conforming clips with black
bars (`pad` filter) or crop them (`crop` filter) — never stretch.

### Variable Frame Rate (VFR) Sources

**Problem:** Screen recordings and phone footage often use VFR, which causes
desync and stuttering when stitched with CFR content.

**Solution:** Convert VFR sources to CFR before stitching:
`ffmpeg -i vfr_input.mp4 -vsync cfr -r 30 cfr_output.mp4`

### Concatenation with Stream Copy Fails

**Problem:** `video_trimmer` concat with `codec: copy` fails or produces glitchy output
when clips have different GOP structures or encoding parameters.

**Solution:** If stream copy fails, fall back to re-encoding with consistent parameters:
`-c:v libx264 -crf 18 -preset medium -c:a aac -b:a 192k`
Use CRF 18 (near-lossless) to avoid quality loss from the re-encode.

## Stitch Planning Template

When planning a stitch, record this structure inside `edit_decisions.metadata` (as
`metadata.stitch_plan`). The `edit_decisions` schema rejects unknown top-level keys, so a
top-level `stitch_plan` fails validation:

```yaml
metadata:
  stitch_plan:
    strategy: sequential | spatial | hybrid | ai_chain
    target_resolution: "1920x1080"
    target_fps: 30
    target_codec: libx264

    clips:
      - id: clip_01
        source: "assets/intro.mp4"
        in_seconds: 0.0
        out_seconds: 5.0
        transition_out: crossfade  # video_stitch transition: cut | crossfade | fade
        transition_duration: 0.8

      - id: clip_02
        source: "assets/section_1.mp4"
        in_seconds: 0.0
        out_seconds: 8.0
        transition_out: cut

      - id: clip_03
        source: "assets/section_2.mp4"
        in_seconds: 0.0
        out_seconds: 8.0
        transition_out: fade  # fade through black
        transition_duration: 0.5

    audio:
      narration: "assets/narration_full.wav"
      music: "assets/bg_music.mp3"
      duck_level: -18  # dB under narration — audio_mixer duck (tool default -12)
      ducking: true

    spatial_inserts:  # Only for hybrid strategy
      - at_clip: clip_02
        at_seconds: 3.0
        layout: picture_in_picture  # video_stitch spatial layout
        overlay_source: "assets/webcam.mp4"
        pip_position: bottom_right
        pip_scale: 0.25
```
