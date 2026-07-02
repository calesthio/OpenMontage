# Compose Director — Talking Head Pipeline

## When to Use

You have edit decisions and an asset manifest. Your job is to render the final talking-head video: apply the enhancement chain, burn subtitles, mix audio, and encode to the target profile.

## Runtime Routing (HARD CONSTRAINT — Remotion or FFmpeg only)

Phase 1 deferred from HyperFrames. `edit_decisions.render_runtime` must be `"remotion"` (preferred — uses the `TalkingHead` composition + `remotion_caption_burn`) or `"ffmpeg"` (for source-footage concat with no composition).

- If `edit_decisions.render_runtime == "hyperframes"`, stop. Re-open the idea stage and surface the constraint. Silent rewrite is a governance violation.
- Per AGENT_GUIDE.md → "Present Both Composition Runtimes (HARD RULE)": the pipeline's constraint doesn't skip the conversation. Present the constraint to the user so they know HyperFrames exists but isn't viable here. Record a `render_runtime_selection` decision with hyperframes `rejected_because: "TalkingHead + caption parity deferred on talking-head"`.
- Pass `proposal_packet`/`brief` to `video_compose.execute()` for runtime-swap detection.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Schema | `schemas/artifacts/render_report.schema.json` | Artifact validation |
| Prior artifacts | Edit decisions, Asset manifest | Render inputs |
| Tools | `video_compose`, `audio_mixer` | Rendering |
| Media profiles | `lib/media_profiles.py` | Output format |

## Process

### Step 0: Pre-flight Checks

Before rendering anything, validate the inputs and catch issues that are expensive to fix later.

1. **Silence detection** -- Run `silence_cutter` in mark mode:
   ```
   silence_cutter.execute({
       "input_path": "<raw_footage>",
       "mode": "mark",
       "silence_threshold_db": -35,
       "min_silence_duration": 0.5
   })
   ```
   - Report all gaps > 0.5s with timestamps.
   - If total silence > 5s, **recommend cutting before proceeding**. Long silences waste render time and produce dead spots in the final video.

2. **ASR confidence check** -- Scan word-level transcript for low-confidence words:
   - Flag any word with probability < 0.7.
   - List flagged words with timestamps so the user can verify correct transcription.
   - Common misrecognitions to watch for: proper nouns, brand names, domain jargon.

3. **Auto-build corrections dictionary** from common ASR error patterns:
   ```python
   corrections = {
       # Indian finance context
       "DMI": "EMI",
       "AMI": "EMI",
       # Common brand misspellings
       "open montage": "Balamonis Studio",
       "remotion": "Remotion",
       # Numbers that got split by ASR
       "4 -5": "4-5",
       "10 -15": "10-15",
   }
   ```
   Extend this dict with domain-specific corrections based on the video topic. Present the corrections to the user for review before applying.

4. **Green screen flag** -- Check if scene-director Step 0 flagged green/blue screen footage. If yes, note that Step 3c (Green Screen Composite) will be needed.

### Step 1: Run Enhancement Chain

Apply video enhancements in this exact order. **Attempt every step** if the tool is available — do not skip steps without a reason.

1. **Face enhancement** — apply `talking_head_standard` preset
2. **Eye enhancement** — under-eye dark circle removal + eye brightening
3. **Color grading** — apply a profile
4. **Audio enhancement** — noise reduction, normalization

**Eye enhancement** — always attempt this after face_enhance. It makes a visible difference on webcam/phone footage:
```
eye_enhance.execute({
    "input_path": "<face_enhanced_video>",
    "output_path": "<project>/assets/video/eye_enhanced.mp4",
    "operations": ["dark_circles", "brighten_eyes"],
    "dark_circle_intensity": 0.4,       # 0-1, subtle is better
    "eye_brighten_intensity": 0.3,
})
```
**Important:** Keep intensities low (0.2-0.5). Over-processing makes eyes look unnatural. If the tool fails (e.g. MediaPipe not installed), log the fallback and continue with the face_enhanced video.

### Step 1b: Speed Adjustment (if requested)

If the user wants the video sped up or slowed down, use `video_trimmer`:
```
video_trimmer.execute({
    "operation": "speed",
    "input_path": "<enhanced_video>",
    "output_path": "<project>/assets/video/speed_adjusted.mp4",
    "speed_factor": 1.25    # 0.5x (slow), 1.25x, 1.5x, 2x (fast)
})
```

Common speed factors:
| Factor | Use Case |
|--------|----------|
| `0.5` | Slow-mo for dramatic effect |
| `1.0` | Normal (no change) |
| `1.25` | Slightly faster — tighter pacing without sounding unnatural |
| `1.5` | Noticeably faster — good for recaps or condensed content |
| `2.0` | Double speed — time-lapse effect |

Apply speed AFTER enhancements, BEFORE reframing.

### Step 2: Auto-Reframe (if target platform requires it)

If the target platform requires a different aspect ratio (e.g. Instagram Reels = 9:16), use `auto_reframe`:

```
auto_reframe.execute({
    "input_path": "<enhanced_video>",
    "output_path": "<project>/renders/reframed.mp4",
    "target_aspect": "portrait",       # 9:16 for Reels/TikTok/Shorts
    "smoothing_window": 15,            # smooth camera pan
    "face_padding": 0.4,              # 40% padding around face
})
```

**Aspect ratio presets:**
| Preset | Ratio | Platform |
|--------|-------|----------|
| `portrait` | 9:16 | Instagram Reels, TikTok, YouTube Shorts |
| `square` | 1:1 | Instagram Feed |
| `landscape` | 16:9 | YouTube, LinkedIn |
| `vertical_4_5` | 4:5 | Instagram portrait post |

The tool automatically runs face detection and keeps the speaker centered. If MediaPipe is not installed, falls back to center-crop.

**Important:** Run auto_reframe AFTER face_enhance and color_grade but BEFORE burning subtitles. Subtitles need to be positioned for the final aspect ratio.

### Step 2b: Build ASR Corrections Dictionary

Before burning captions, scan the transcript for likely ASR misrecognitions. Common issues:
- Product/brand names: "cloud" → "Claude", "co-pilot" → "Copilot", "remotion" → "Remotion"
- Technical terms: "pythonic" misheard as "pathonic", "API" as "a pie"
- Speaker's name or company name
- Domain-specific jargon

Build a corrections dict:
```python
corrections = {
    "cloud": "Claude",
    "co pilot": "Copilot",
    "open montage": "Balamonis Studio",
}
```

Pass this dict to both `subtitle_gen` (if generating SRT) and `remotion_caption_burn` (if using Remotion captions). Even if you find zero corrections needed, explicitly pass an empty dict `{}` to confirm you checked.

### Step 3: Burn Subtitles

**ALWAYS use Remotion TikTok-style captions** (word-by-word highlighting). This is the default and preferred method. Do NOT fall back to FFmpeg ASS subtitles unless Remotion is completely unavailable.

**Remotion caption requirements:**
- **Auto-detect video dimensions** -- do NOT hardcode width/height. Use `visual_qa` probe or ffprobe to get actual dimensions, then pass them to the render.
- **Set `--frames` based on actual video duration** -- calculate from probe: `frames = duration_seconds * fps`. Never use a hardcoded frame count.
- Word-by-word highlighting with active word color (`highlight_color`).
- Captions positioned at the bottom of frame, away from the face.

```
remotion_caption_burn.execute({
    "input_path": "<reframed_or_enhanced_video>",
    "output_path": "<project>/assets/video/captioned.mp4",
    "segments": <transcript_segments_from_asset_manifest>,
    "corrections": {"cloud": "Claude", "co-pilot": "Copilot"},
    "words_per_page": 4,
    "font_size": 52,
    "highlight_color": "<theme_accent>",
})
```

**Fallback ONLY if Remotion is completely unavailable:** Use `video_compose` with `burn_subtitles` operation. This is a degraded experience -- warn the user that word-by-word highlighting won't be available.

**CRITICAL: Caption positioning for 9:16 vertical video (FFmpeg fallback only).**
Captions MUST be in the lower 20% of the frame. On a 1920-high frame, that means `MarginV=160` or higher. The default FFmpeg subtitle position is center -- this WILL occlude the face. You MUST override it.

FFmpeg subtitle style string for vertical talking-head:
```
"FontName=Arial,FontSize=22,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2,Shadow=0,MarginV=160,Alignment=2"
```

**Never** use the default subtitle position. **Never** position subtitles in the center or upper half of the frame. If you see captions on the face during visual QA, the video must be re-rendered with corrected positioning.

### Step 3b: Burn Overlay Graphics (if scene plan includes overlays)

If the scene plan includes overlay scenes (text_cards, stat_cards, charts, comparisons, callouts), pass them to `remotion_caption_burn` alongside captions. **Both captions and overlays render in a single Remotion pass** — no separate FFmpeg compositing needed.

**How it works:** The TalkingHead Remotion composition renders three layers:
1. **Video** (bottom) — the talking-head footage
2. **Overlays** (middle) — positioned charts, stats, callouts with fade in/out
3. **Captions** (top) — word-by-word highlighting, always visible

**Combine Step 3 and 3b into one `remotion_caption_burn` call:**
```
remotion_caption_burn.execute({
    "input_path": "<reframed_or_enhanced_video>",
    "output_path": "<project>/assets/video/captioned.mp4",
    "segments": <transcript_segments>,
    "corrections": {"cloud": "Claude"},
    "words_per_page": 4,
    "font_size": 52,
    "highlight_color": "<theme_accent>",
    "overlays": [
        {
            "id": "term-agentic-ai",
            "type": "callout",
            "text": "Agentic AI: software that acts autonomously toward goals",
            "callout_type": "info",
            "in_seconds": 22.0,
            "out_seconds": 26.0,
            "position": "lower_third",
            "backgroundColor": "<theme_background>",
            "accentColor": "<theme_accent>"
        },
        {
            "id": "stat-market-size",
            "type": "stat_card",
            "stat": "$4.8B",
            "subtitle": "Global AI Agent Market (2026)",
            "in_seconds": 35.0,
            "out_seconds": 39.0,
            "position": "upper_third",
            "accentColor": "<theme_secondary_accent>"
        },
        {
            "id": "chart-growth",
            "type": "bar_chart",
            "chartData": [
                {"label": "2023", "value": 1.2},
                {"label": "2024", "value": 2.1},
                {"label": "2025", "value": 3.5},
                {"label": "2026", "value": 4.8}
            ],
            "title": "AI Agent Market ($B)",
            "in_seconds": 40.0,
            "out_seconds": 45.0,
            "position": "lower_third",
            "chartColors": ["<theme_accent>", "<theme_secondary_accent>", "<theme_tertiary_accent>", "<theme_supporting_accent>"]
        }
    ]
})
```

**Overlay position options:**
- `lower_third` → bottom area, above captions (default — safest for most overlays)
- `upper_third` → top area (good for stats while speaker is center/lower)
- `left_panel` → left 45% of frame (side-by-side with speaker)
- `right_panel` → right 45% of frame
- `full_overlay` → full frame with dark backdrop (use sparingly, 1-2s max)

**Overlay type → required props** (same as asset-director mapping):

| Type | Required Props |
|------|---------------|
| `text_card` | `text` |
| `stat_card` | `stat`, `subtitle` (optional) |
| `callout` | `text`, `callout_type` (info/warning/tip/quote) |
| `comparison` | `leftLabel`, `rightLabel`, `leftValue`, `rightValue` |
| `bar_chart` | `chartData` (array of `{label, value}`) |
| `line_chart` | `chartSeries` (array of `{name, data: number[]}`) |
| `pie_chart` | `chartData` (array of `{label, value}`) |
| `kpi_grid` | `chartData` (array of `{label, value}`) |
| `hero_title` | `text`, `subtitle` (optional) |
| `section_title` | `text`, `subtitle` (optional) |
| `stat_reveal` | `text` (the stat), `subtitle` (label) |

**Important:** After speed adjustment, recalculate overlay timestamps: `adjusted_time = original_time / speed_factor`.

**Fallback (no Remotion):** If Remotion is unavailable, `remotion_caption_burn` falls back to FFmpeg for captions only. Overlays are NOT rendered in FFmpeg fallback mode — warn the user that overlays require Remotion.

### Step 3c: Green Screen Composite (if green screen footage)

If the footage has a green/blue screen (detected in scene-director Step 0), follow this pipeline:

1. **Run `green_screen_processor` tool** to remove the green/blue screen:
   ```
   green_screen_processor.execute({
       "input_path": "<enhanced_video>",
       "output_path": "<project>/assets/video/greenscreen_removed.mp4",
       "method": "auto"
   })
   ```
   The `auto` method detects whether the background is green or blue and applies the appropriate chroma key.

2. **Render Remotion animated background** using the Explainer composition:
   ```
   # Render an AnimatedBackground clip (gradient mesh, floating orbs, subtle grid)
   # Use the Explainer composition — NOT a flat #0F172A solid color
   npx remotion render src/index.ts Explainer --props='{"duration":VIDEO_DURATION}' --output=<project>/assets/video/animated_bg.mp4
   ```
   The AnimatedBackground provides a professional gradient mesh with floating orbs and a subtle grid pattern. This is far superior to a flat solid color.

3. **Run `green_screen_composite` tool** to layer the speaker onto the animated background:
   ```
   green_screen_composite.execute({
       "foreground_path": "<greenscreen_removed_video>",
       "background_path": "<animated_bg>",
       "output_path": "<project>/assets/video/composited.mp4",
       "layout": "news_anchor"
   })
   ```
   Default layout is `news_anchor` (speaker center-bottom, background fills frame). Adjust layout based on speaker position detected in Step 0.

4. **Burn captions via Remotion TalkingHead composition** (NOT FFmpeg ASS subtitles):
   ```
   remotion_caption_burn.execute({
       "input_path": "<composited_video>",
       "output_path": "<project>/assets/video/captioned.mp4",
       "segments": <transcript_segments>,
       "corrections": <corrections_dict>,
       "words_per_page": 4,
       "font_size": 52,
        "highlight_color": "<theme_accent>",
       "overlays": <overlay_list_from_scene_plan>
   })
   ```

5. **Mix background music** (ducked at 15% volume under speech):
   ```
   audio_mixer.execute({
       "operation": "duck",
       "video_path": "<captioned_video>",
       "music_path": "<bg_music>",
       "music_volume": 0.15,
       "output_path": "<project>/assets/video/with_music.mp4"
   })
   ```

6. **Final encode** to target platform specs (see Step 6 below).

### Step 3d: Build Showcase Cards (if multi-clip reel)

If the output is a reel with showcase clips, use `showcase_card` for each:
```
showcase_card.execute({
    "input_path": "<showcase_video>",
    "output_path": "<project>/assets/video/sc_<name>.mp4",
    "title": "VIDEO TITLE",
    "subtitle": "Description | Style | Cost: $0.15",
    "background_color": "0x0A0F1A",
})
```
This creates letterboxed 9:16 cards with typography.

### Step 4: Assemble Multi-Clip (if applicable)

If the output has multiple segments (e.g. talking head + showcase clips), use `video_stitch`:
```
video_stitch.execute({
    "operation": "stitch",
    "clips": ["intro.mp4", "showcase1.mp4", ..., "outro.mp4"],
    "output_path": "<project>/renders/assembled.mp4",
    "transition": "crossfade",         # or "fade" for fade-through-black
    "transition_duration": 0.5,
})
```
**Transition guidance:**
- `crossfade` (fade): smooth blend between talking head and showcase
- `fade` (fade-through-black): brief dip to black between showcase clips
- Mix transition types: use `crossfade` for talk→showcase, `fade` between showcases

### Step 5: Mix Audio

Use `audio_mixer` to layer background music:

**For multi-clip reels** — use `segmented_music` to play music only during talking head sections:
```
audio_mixer.execute({
    "operation": "segmented_music",
    "video_path": "<assembled_video>",
    "music_path": "<bg_music>",
    "music_volume": 0.20,
    "segments": [
        {"start": 0, "end": 17.0},       # intro speech
        {"start": 167.0, "end": 175.0}    # outro speech
    ],
    "fade_duration": 0.5,
    "output_path": "<project>/renders/final.mp4",
})
```

**For single talking-head videos** — use `duck` or `full_mix`:
- Layer original audio with background music
- Apply ducking if music is present
- Normalize final levels

### Step 6: Final Encode — MANDATORY

**Do not skip this step.** Without a final encode, the output will be oversized and may not play correctly on the target platform.

Use `video_compose` with `encode` operation:
- Apply target media profile (youtube_landscape, tiktok, instagram_reels, etc.)
- Two-pass encoding for quality

**Target file sizes:**
| Platform | Max Duration | Target Size |
|----------|-------------|-------------|
| Instagram Reels | 90s | < 50 MB |
| TikTok | 10 min | < 100 MB |
| YouTube Shorts | 60s | < 40 MB |
| YouTube | unlimited | < 25 MB/min |

If the output exceeds the target, re-encode with a lower bitrate. A 66-second Instagram Reel at 76 MB is unacceptable — it should be under 30 MB.

```
video_compose.execute({
    "operation": "encode",
    "input_path": "<mixed_video>",
    "output_path": "<project>/renders/final.mp4",
    "media_profile": "instagram_reels",
    "video_bitrate": "4M",
    "audio_bitrate": "192k",
})
```

### Step 7: Visual QA

Use `visual_qa` to verify the output before declaring success:
```
visual_qa.execute({
    "operation": "review",
    "input_path": "<final_video>",
    "timestamps": [3.0, 10.0, 25.0, 50.0, 100.0, 170.0],
})
```
Then **read each extracted frame** to verify:
- Captions are visible and positioned at the bottom (not on the face)
- Face enhancement is applied (skin looks smooth, not over-processed)
- Transitions are clean (no artifacts at transition points)
- Showcase cards have readable typography

Also run probe validation:
```
visual_qa.execute({
    "operation": "probe",
    "input_path": "<final_video>",
    "expected": {
        "width": 1080, "height": 1920,
        "has_audio": true,
        "pixel_format": "yuv420p"
    },
})
```

And check audio levels:
```
visual_qa.execute({
    "operation": "audio_levels",
    "input_path": "<final_video>",
    "timestamps": [5.0, 50.0, 170.0],
})
```
Verify: speech sections have higher volume than showcase sections (confirms music placement).

### Step 8: Build Render Report

Document output: path, format, resolution, duration, file size, QA results.

### Step 9: Self-Evaluate

| Criterion | Question |
|-----------|----------|
| **Playability** | Does the video play without errors? |
| **Quality** | Are enhancements applied correctly? |
| **Framing** | If reframed — is the face centered? No important content cropped? |
| **Audio** | Is speech clear with balanced levels? Music only during intended segments? |
| **Subtitles** | Are captions visible at the bottom? Not occluding the face? Word highlighting working? |
| **Transitions** | Are transitions clean? Correct type (crossfade vs fadeblack)? |
| **Showcase** | Are showcase cards properly letterboxed with readable typography? |

### Step 10: Submit

Validate the render_report against the schema and persist via checkpoint.
