# Compose Director — Explainer Pipeline

## When to Use

You are the Compositor for a generated explainer video. You have `edit_decisions` with the complete edit timeline and an `asset_manifest` with all file paths. Your job is to render the final video: assemble visuals, layer audio, burn subtitles, and encode to the target format.

This is the last technical stage before the video exists as a playable file. Everything converges here.

## Runtime Routing (MANDATORY first step)

Read `edit_decisions.render_runtime` before anything else. It was locked at proposal and must not be changed silently. The rest of this skill's process steps (Remotion public/ staging, word-level caption burn, etc.) assume `render_runtime="remotion"` — the default for data-driven explainers.

- **`render_runtime="hyperframes"`** — HTML/CSS/GSAP render. Do NOT follow the Remotion-specific steps below. Instead: read `skills/core/hyperframes.md`, `.agents/skills/hyperframes/SKILL.md`, and `.agents/skills/hyperframes-cli/SKILL.md`. Call `video_compose` with the edit_decisions unchanged — it will delegate to `hyperframes_compose`, which materializes a workspace under `projects/<name>/hyperframes/` and returns the MP4. **HyperFrames gate (what `hyperframes_compose` actually runs):** a templated workspace (scaffolded from `edit_decisions`) goes `lint → validate → render`; a `validate` failure always blocks the render, but `lint` findings block it only with `strict: true` — otherwise they are logged under `steps.lint` and the render continues, so pass `strict: true` on the final render. An authored (atelier) workspace (`composition_mode: "atelier"`) goes `hyperframes check → render --strict` instead, and `check` must pass. `skip_contrast: true` is for iteration only, never for final delivery.
- **`render_runtime="ffmpeg"`** — simple concat/trim. Call `video_compose` directly; it will NOT auto-upgrade to Remotion when this runtime is explicitly locked.
- **Runtime unavailable** — surface the blocker per AGENT_GUIDE.md > "Escalate Blockers Explicitly" and get user approval (recorded as a `render_runtime_selection` decision in decision_log) before switching.

`final_review.checks.promise_preservation.render_runtime_used` must equal the runtime that actually ran; `runtime_swap_detected` must be `false` unless an approved decision authorizes the swap.

**Pass `proposal_packet` to `video_compose.execute()`** so in-tool swap detection compares against the authoritative `production_plan.render_runtime`. Without it the tool falls back to `edit_decisions.metadata.proposal_render_runtime` (the edit stage copies it there); only when both are missing is `runtime_swap_check` reported as `skipped`, and you have to rely on the reviewer skill's cross-artifact comparison instead. The delivery-promise check is separate: it reads `edit_decisions.metadata.delivery_promise`, never the proposal packet.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | `state.artifacts["edit"]["edit_decisions"]`, `state.artifacts["assets"]["asset_manifest"]` | What to render — including the approved narration and music |
| Prior artifacts | `state.artifacts["proposal"]["proposal_packet"]`, `state.artifacts["scene_plan"]["scene_plan"]` | Passed to `video_compose` for the runtime-swap and slideshow-risk checks |
| Playbook | Active style playbook | Quality targets |
| Tools | `video_compose`, `audio_mixer` | Rendering capabilities |
| Tools | `composition_validator`, `audio_probe`, `transcriber`, `frame_sampler`, `subtitle_gen` | Pre-render validation, captions, post-render review |
| Media profiles | `lib/media_profiles.py` | Output format specs (resolution, codec, bitrate) |

## Process

### Step 1: Choose Render Strategy

Based on the edit decisions, pick the rendering approach:

**Remotion render** (DEFAULT — use this unless explicitly overridden):
- Animated text cards, stat cards, chart scenes
- Complex transitions (morph, zoom, ken-burns)
- Programmatic motion graphics
- Audio embedding (narration + music with fade/volume)
- Word-level captions via CaptionOverlay component
- Best for: ALL explainer videos, both image-based and animation-heavy

**FFmpeg pipeline** (FALLBACK — only when Remotion is unavailable):
- Static images with Ken Burns
- Audio layering
- SRT subtitle burn-in
- Best for: environments without Node.js/Remotion installed

**IMPORTANT: When using Remotion, ALL of these go through Remotion — not FFmpeg:**
- Audio → Remotion `audio` prop: the narration track plus a music bed. The `Explainer` composition ducks the bed under the word `captions` when `audio.music.ducking` is set (`audio_mix_plan: "composition"`); otherwise pre-mix with `audio_mixer` and hand the mix to `video_compose` as `audio_path` (Step 5)
- Subtitles → Remotion `captions` prop (word-level), NOT SRT burn via FFmpeg
- Text overlays (CTA, titles) → Remotion `text_card` cut type, NOT AI-generated images

### Step 2: Collect the Approved Audio (Narration, Music, Subtitles)

The narration script, the voice, every narration take, and the background music were produced and approved in earlier stages (script-director; asset-director Step 2b sample approval, Step 3 narration via `tts_selector`, Step 5 music). **Compose consumes them. It does not write a new narration script, choose a voice, call a TTS provider, or fetch new music.**

If something is missing or unusable — a narration section has no audio, the narration runs longer than the video, the manifest records `metadata.music_status: "unavailable"` — stop and report it. The fix is a send-back to the assets (or script) stage, and nothing is regenerated without the user's approval: the voice and the music are approved samples, and silently replacing them here breaks that gate.

1. **Narration** — take the narration assets from `asset_manifest` (`type: "narration"`, or `type: "audio"` with `subtype: "narration"`) in the order and at the `start_seconds` given by `edit_decisions.audio.narration.segments`. The Remotion composition plays ONE narration file, so join several takes into `projects/<project>/assets/audio/narration_full.wav` with `audio_mixer` (`operation: "mix"`, one `role: "speech"` track per take with its `start_seconds`).

2. **Music** — the asset named by `edit_decisions.audio.music.asset_id`. Check its length against the video with `audio_probe`; a track shorter than the video can loop (`"loop": true`).

3. **Subtitles** — word-level captions come from transcribing that narration file with the `transcriber` tool (Step 5b has the call and the conversion to Remotion caption format: `[{ "word": "Hello", "startMs": 0, "endMs": 340 }, ...]`).

4. **Assemble the Remotion composition JSON** — `edit_decisions` is a closed schema, so everything only the Remotion `Explainer` composition understands lives in a second file, `projects/<project>/artifacts/remotion_composition.json`. Start from a copy of the `edit_decisions` artifact (keep `render_runtime`, `renderer_family`, and `metadata`), then:
   - replace each cut's `source` asset id with that asset's real file path;
   - add the Remotion-only props the edit stage named in each cut's `reason` / `metadata.remotion_cuts`: `type` (`text_card`, `stat_card`, `bar_chart`, ...) and that template's props (see `remotion-composer/SCENE_TYPES.md`);
   - add Remotion `overlays`, `captions`, and the `audio` block:
   ```json
   {
     "audio": {
       "narration": { "src": "projects/<project>/assets/audio/narration_full.wav", "volume": 1 },
       "music": { "src": "projects/<project>/assets/music/background_music.mp3", "volume": 0.1, "fadeInSeconds": 2, "fadeOutSeconds": 3 }
     },
     "captions": [ ... word-level captions from the transcriber ... ]
   }
   ```
   This object — not the canonical artifact — is what you pass as `edit_decisions` to `video_compose` on the Remotion path (Step 4) and what `composition_validator` reads (Step 5c). The canonical `edit_decisions` artifact is not modified.

### Step 3: Prepare Render Inputs

For each cut in the edit decisions:
1. Verify the source asset exists at its declared path
2. Check asset dimensions/duration match expectations
3. Prepare transform parameters (scale, position, crop)

For audio:
1. Verify narration duration fits within video duration (use `audio_probe`)
2. Verify music duration covers video duration
3. Read the mix plan from edit decisions (`audio.music.ducking`, `metadata.audio_mix_plan`) — Step 5 says what each render path does with it

### Step 3: Determine Output Profile

Read the target platform from the approved concept (`proposal_packet.concept_options[]` entry whose `id` equals `selected_concept.concept_id` → `target_platform`). Map to a media profile:

| Platform | Profile | Resolution | Notes |
|----------|---------|-----------|-------|
| YouTube | `youtube_landscape` | 1920x1080 | Default for most explainers |
| TikTok/Reels | `tiktok` | 1080x1920 | Vertical, needs reframing |
| Twitter/X | `generic_hd` | 1920x1080 | No dedicated X profile exists in `lib/media_profiles.py` (`get_profile` raises on unknown names); `generic_hd` is the 16:9 fallback |
| LinkedIn | `linkedin` | 1920x1080 | Professional context |

Get the exact encoding parameters via `ffmpeg_output_args(get_profile(name))`. The valid names are `youtube_landscape`, `youtube_4k`, `youtube_shorts`, `instagram_reels`, `instagram_feed`, `tiktok`, `linkedin`, `cinematic`, `generic_hd`.

### Step 4: Render Video

Call the `video_compose` tool with:
```
{
  "operation": "render",
  "edit_decisions": <Remotion path: the remotion_composition.json object from Step 2; hyperframes/ffmpeg: the edit_decisions artifact>,
  "asset_manifest": <asset_manifest artifact>,
  "proposal_packet": <proposal_packet artifact>,
  "scene_plan": <scene_plan.scenes — the list, not the whole artifact>,
  "output_profile": "youtube_landscape",
  "output_path": "renders/output.mp4",
  "audio_path": "<pre-mixed narration+music track — only for the premix plan, see Step 5>",
  "narration_transcript_path": "<word-level transcript JSON from the transcriber>",
  "script_text": "<the narration script>",
  "options": {
    "subtitle_burn": true
  }
}
```

`options.subtitle_burn` is the only render option the tool reads, and only on the FFmpeg path (Remotion draws captions from the `captions` prop). There is no `audio_normalize` option — loudness normalization belongs to `audio_mixer` (`normalize`, `loudnorm_target`) — and `two_pass_encode` is declared in the tool schema but not implemented.

If using Remotion for animated segments:
1. Generate Remotion composition data from edit decisions
2. Call `video_compose` with `operation: "remotion_render"` for animated segments
3. Assemble Remotion outputs with remaining segments via FFmpeg

**Zero-key Remotion render (component-only videos):**
When all scenes are Remotion component types (hero_title, stat_card, bar_chart, line_chart,
pie_chart, kpi_grid, comparison, callout, progress_bar, text_card), render the entire video
as a single Remotion composition using the Explainer entry point. No FFmpeg assembly needed.
The `remotion_composition.json` cuts array maps directly to Remotion props. See `skills/core/remotion.md`
for the proven formula — especially the all-dark-background rule for visual consistency.

### Step 5: Audio Post-Processing

**Remotion path (DEFAULT):** Remotion plays audio natively via `<Audio>` components — the
narration track, and ONE music track with a fade in and out. The `Explainer` composition ducks
that track only when `remotion_composition.json` sets `audio.music.ducking`. Follow the plan the
edit stage recorded in `edit_decisions.metadata.audio_mix_plan`:

- **`composition` — recommended when the composition carries word `captions`.** Add
  `"ducking": true` (or `{"duckedGain": 0.35, "attackSeconds": 0.15, "releaseSeconds": 0.4,
  "mergeGapSeconds": 0.6}`) to `audio.music` in `remotion_composition.json`, with the music at
  its normal bed `volume` (e.g. 0.3). The music dips under each spoken phrase (speech timing
  comes from `captions`) and recovers in pauses. Without captions the whole video counts as
  speech, which is just a lower constant level — use `premix` instead.

- **`premix` — recommended whenever narration and music play together.** Call `audio_mixer`
  with `operation: "full_mix"`: each narration take as a `role: "speech"` track with its
  `start_seconds`, the music as a `role: "music"` track, `ducking: {"enabled": true,
  "music_volume_during_speech": 0.15, "attack_ms": 200, "release_ms": 500}`, `target_duration`
  set to the video length, and `normalize: true`. (`audio_mixer` does not read `threshold_db` or
  `reduction_db`; the dip depth is `music_volume_during_speech`.) Pass the mixed file to
  `video_compose` as `audio_path` — the tool replaces the rendered video's audio track with it.
  Leave `audio.music` out of `remotion_composition.json` so the bed is not described twice.
  A music track takes `offset_seconds` (its in-point, e.g. past a quiet intro) and
  `"loop": true` for a bed shorter than the video; a looped track plays to `target_duration`
  (required with `loop`) and its `fade_out_seconds` lands at that end.
- **`flat` — no ducking.** Skip external mixing and pass both sources in the composition props,
  with the music low enough (0.08–0.12) that it never competes with the voice:
```json
{
  "audio": {
    "narration": { "src": "project/narration.mp3", "volume": 1.0 },
    "music": { "src": "project/music.mp3", "volume": 0.12, "fadeInSeconds": 1.5, "fadeOutSeconds": 2.5 }
  }
}
```
  Remotion renders audio and video in a single pass — no external muxing needed. Note in the
  render report that the bed is flat, not ducked.

**FFmpeg fallback (ONLY when Remotion is unavailable):**
Call the `audio_mixer` tool to:
1. Layer narration segments in order
2. Mix background music at playbook volume
3. Apply ducking (music dips during narration)
4. Normalize overall audio levels
5. Output the final mixed audio track
The video_compose tool will mux this with the video.

### Step 5b: Generate Subtitles (Mandatory)

Subtitles are mandatory for all explainer content. Generate them from the narration audio — do NOT skip this step.

**Remotion path (DEFAULT — when using Remotion render):**

1. **Transcribe** the full narration using the `transcriber` tool (whisperx):
   ```python
   from tools.analysis.transcriber import Transcriber
   result = Transcriber().execute({
       'input_path': 'projects/<project>/assets/audio/narration_full.mp3',
       'model_size': 'base',
       'language': 'en',
       'output_dir': 'projects/<project>/assets/audio'
   })
   # result.data contains segments with word-level timestamps
   ```

2. **Convert to Remotion WordCaption format** (NOT SRT):
   ```python
   captions = []
   for segment in result.data['segments']:
       for word_info in segment.get('words', []):
           captions.append({
               'word': word_info['word'],
               'startMs': int(word_info['start'] * 1000),
               'endMs': int(word_info['end'] * 1000),
           })
   ```

3. **Add captions to composition props** — they go in the `captions` array alongside `cuts` and `audio`:
   ```json
   {
     "cuts": [...],
     "audio": {...},
     "captions": [
       { "word": "Root", "startMs": 120, "endMs": 340 },
       { "word": "canals", "startMs": 340, "endMs": 680 }
     ]
   }
   ```

   Remotion's CaptionOverlay renders these as word-by-word highlighted captions with the theme's
   `captionHighlightColor` and `captionBackgroundColor`. This is superior to FFmpeg SRT burn because
   it produces animated word-level highlighting synchronized to narration.

**FFmpeg fallback (ONLY when Remotion is unavailable):**

If Remotion is not available, fall back to SRT generation + FFmpeg burn:
   ```python
   from tools.subtitle.subtitle_gen import SubtitleGen
   SubtitleGen().execute({
       'segments': transcription_data['segments'],
       'format': 'srt',
       'output_path': 'projects/<project>/assets/subtitles.srt',
       'max_words_per_cue': 8,
       'max_chars_per_line': 42
   })
   # Then burn with video_compose operation='burn_subtitles'
   ```

**The final deliverable MUST have subtitles** — either via Remotion captions or FFmpeg burn.

### Step 5c: Pre-Render Validation (Mandatory)

**Always run the composition validator before rendering.** This catches problems that waste render time.

```python
from tools.analysis.composition_validator import CompositionValidator
result = CompositionValidator().execute({
    'composition_path': 'projects/<project>/artifacts/remotion_composition.json',
    # The directory the composition's relative paths resolve against:
    # '.' (repo root) for paths like projects/<project>/assets/...,
    # 'remotion-composer/public' for files you staged there.
    'assets_root': '.',
})
# result.data['valid'] MUST be True before proceeding to render
# If False: fix the reported errors first (missing assets, audio-video mismatch, etc.)
```

Common catches:
- Narration audio longer than video (would be cut off)
- Missing files for `cuts[].source`, `cuts[].backgroundImage`, `audio.narration.src`, and `audio.music.src` (render would fail). Other media props — `backgroundVideo`, `images[]`, overlay sources — are not checked; confirm those files yourself
- Music shorter than video (silence at end)

The validator reads the file as written: a cut `source` must be a real file path there, not an asset id, or it reports "Missing asset".

**Do not skip this step.** If validation fails, fix the issue and re-validate before rendering.

### Step 6: Post-Render Self-Review (Mandatory — ALL steps required)

After rendering, the agent **must review its own output** before presenting to the user. This catches issues the validator can't see (visual quality, audio sync, subtitle readability).

**CRITICAL: You MUST complete ALL of steps 6a through 6e. Do NOT skip any step.
The most common agent failure is doing 6a (frames) and 6c (visual) while skipping
6b (audio transcription) — which misses catastrophic issues like missing audio entirely.**

**6a. Probe rendered file (FIRST — gate for all other checks):**
```bash
ffprobe -v quiet -print_format json -show_format -show_streams rendered_video.mp4
```
Verify:
- Video stream exists (codec_type: "video") with correct resolution
- **Audio stream exists (codec_type: "audio")** — if NO audio stream, STOP and fix immediately
- Duration is within ±5% of target
- File size is reasonable (not 0 bytes)

**If audio stream is missing: the render did not embed audio. Do NOT proceed to present
the video to the user. Fix the audio configuration and re-render.**

**6b. Extract review frames:**
```python
from tools.analysis.frame_sampler import FrameSampler
midpoints = [(cut['in_seconds'] + cut['out_seconds']) / 2 for cut in cuts]
FrameSampler().execute({
    'input_path': 'path/to/rendered_video.mp4',
    'strategy': 'timestamps',
    'timestamps': midpoints,
    'output_dir': 'path/to/review-frames',
    'format': 'png',
})
```

**6c. Transcribe rendered audio (MANDATORY — do NOT skip):**
```python
from tools.analysis.transcriber import Transcriber
result = Transcriber().execute({
    'input_path': 'path/to/rendered_video.mp4',
    'model_size': 'base',
    'language': 'en',
    'output_dir': 'path/to/review-frames',
})
# If result returns 0 words: audio is silent/missing — STOP and fix
# If word count < 80% of script word count: audio is cut off — investigate
```

**6d. Visual inspection — review each frame:**
- Does the background color/gradient match intent? (watch for white backgrounds on dark-themed videos)
- Are images rendering correctly? (not blank, not stretched)
- Are subtitles/captions visible and properly spaced?
- Are overlays (section titles, stat reveals) positioned correctly?
- Is the opening scene visually strong? (important for social media thumbnails)
- Does the CTA/closing screen show correct text? (AI-generated text in images frequently hallucinates — use Remotion text_card for any text that must be exact)

**6e. Audio inspection — check transcript against script:**
- Is the full narration captured? (compare last transcribed word to last scripted word)
- Any words cut off at the end? (narration exceeding video duration)
- Timing alignment — do narration segments roughly match their intended scenes?
- Is background music audible? (transcriber may not capture music, but ffprobe confirms audio stream)

**6f. Compile and present review to user:**

> **Post-render review for "[Video Title]":**
>
> **File:** [duration]s, [resolution], [file size] — audio stream: [present/MISSING]
> **Audio:** [Complete/Cut off at Xs] — [N]/[M] words transcribed from rendered output
> **Visuals:** [N scenes inspected] — [issues or "all scenes rendering correctly"]
> **Captions:** [Remotion CaptionOverlay / FFmpeg SRT / MISSING] — [word-level highlight working / issues]
> **Issues found:** [list any issues with severity]
>
> **Recommendations:** [what to fix, if anything]
>
> Want me to fix these issues and re-render, or is this good to go?

**Only after user approves (or agent finds zero issues) should the video be considered final.**

### Step 6-old: File and Content Verification

**File verification:**
- [ ] Output file exists at declared path
- [ ] File size is reasonable (not 0 bytes, not suspiciously small)
- [ ] File is a valid container (ffprobe succeeds)

**Content verification:**
- [ ] Duration within ±5% of target
- [ ] Resolution matches selected profile
- [ ] Audio channels present (stereo)
- [ ] No audio clipping or silence gaps > 1s

**Quality check (covered by self-review above):**
- [ ] Visual: all scene frames inspected
- [ ] Audio: full transcription verified
- [ ] Subtitles: visible and correctly timed

### Step 7: Build Render Report

```json
{
  "version": "1.0",
  "outputs": [
    {
      "path": "renders/output.mp4",
      "format": "mp4",
      "codec": "h264",
      "audio_codec": "aac",
      "resolution": "1920x1080",
      "fps": 30,
      "duration_seconds": 62.4,
      "file_size_bytes": 47395635
    }
  ],
  "render_time_seconds": 180,
  "metadata": {
    "render_strategy": "remotion",
    "audio_channels": 2,
    "audio_mix": "premix",
    "total_cuts_rendered": 12,
    "subtitles_burned": true,
    "audio_tracks_mixed": 3,
    "target_duration_seconds": 60,
    "actual_duration_seconds": 62.4
  }
}
```

The report root and every `outputs[]` entry are closed in the schema. File size is `file_size_bytes` (an integer), render time is the top-level `render_time_seconds`, and everything the schema has no field for — render strategy, channel count, the summary counts — goes under `metadata`.

### Step 8: Self-Evaluate

Score (1-5):

| Criterion | Question |
|-----------|----------|
| **Playability** | Does the video play without errors in a standard player? |
| **Duration accuracy** | Is actual duration within ±5% of target? |
| **Audio quality** | Is narration clear, music balanced, no clipping? |
| **Visual quality** | Are images sharp, transitions smooth, no artifacts? |
| **Subtitle accuracy** | Are subtitles present, readable, and synced? |

If any dimension scores below 3, investigate and re-render.

### Step 9: Submit

Validate the render_report against the schema and persist via checkpoint.

## Common Pitfalls

- **Missing asset files**: Always verify every referenced file exists before starting the render. A missing file mid-render wastes time.
- **Audio sync drift**: Accumulated timing errors across narration segments cause audio-visual desync. Use absolute timestamps, not relative offsets.
- **Subtitle encoding**: Burn subtitles into the video (hardcoded) for maximum compatibility. Don't rely on soft subtitles for social media.
- **Expecting encode options that do not exist**: `video_compose` reads only `options.subtitle_burn` (FFmpeg path). `two_pass_encode` is declared but not implemented, and there is no `audio_normalize` — normalize loudness in `audio_mixer` and choose the output format through the media profile.
- **Regenerating approved audio**: The voice and the music were approved in the assets stage. Compose mixes and renders them; a new TTS run or a new music track needs a send-back and the user's approval.
- **Ignoring media profile**: YouTube and TikTok have very different requirements. Always check the target profile.
