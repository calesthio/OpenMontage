# Video Understanding Usage for Balamonis Studio

> Sources: Balamonis Studio video_understand tool implementation, CLIP/BLIP2/LLaVA model
> documentation, OpenCV image quality metrics

## Quick Reference Card

```
DEFAULT MODE:     describe — generates captions for frames
FOR REVIEW:       quality — assesses blur, brightness, contrast
FOR Q&A:          qa mode with a query — "Is the speaker visible?" "Is the text readable?"
DEFAULT MODEL:    clip (fastest, good for classification)
FOR DETAIL:       blip2 or llava (slower, richer descriptions)
MAX FRAMES:       5 default for video — sample strategically, not exhaustively
```

## When to Use video_understand

- **Visual QA during review** — check rendered output quality before delivering
- **Footage analysis** — understand what's in user-provided footage before planning
- **Highlight extraction** — identify the most visually interesting frames
- **Quality gating** — programmatic check for blur, exposure, scene coherence
- **Scene classification** — categorize footage by content type
- **Asset validation** — verify generated images match the intended scene description

## Mode Selection

| Mode | What It Does | When to Use |
|------|-------------|-------------|
| `describe` | Generates a text description of the frame | Understanding footage content, logging |
| `qa` | Answers a specific question about the frame | Targeted checks ("Is text readable?", "Is face visible?") |
| `quality` | Measures blur, brightness, contrast numerically | Automated quality gating, comparing takes |
| `classify` | Categorizes the scene type | Sorting footage, pipeline routing |

### Quality Mode Metrics

| Metric | What It Measures | Bad | Good |
|--------|-----------------|-----|------|
| `blur_score` | Laplacian variance | Below 100 = blurry | Above 500 = sharp |
| `brightness` | Mean pixel value (0-255) | Below 50 = too dark, above 200 = overexposed | 50-200 |
| `contrast` | Pixel standard deviation | Below 30 = flat/washed out | Above 80 = good contrast |

## Model Selection

| Model | Speed | Capabilities | Best For |
|-------|-------|-------------|----------|
| `clip` | Fast | Classification, similarity matching | Quick scene categorization, batch processing |
| `blip2` | Medium | Detailed captions, visual QA | Understanding complex scenes, answering questions |
| `llava` | Slow | Most detailed understanding, reasoning | Deep analysis, subjective quality assessment |

### Model Selection Rules

- Use `clip` for batch operations and classification tasks
- Use `blip2` for describe and qa modes when detail matters
- Use `llava` only when you need the most thorough understanding

## Frame Selection for Video

- Default samples `max_frames` (5) evenly across the video
- Use `frame_indices` to target specific frames (e.g., check quality at specific timestamps)
- For quality review, sample the first frame, middle frame, and last frame minimum

## Common Workflows

### 1. Pre-Edit Footage Review

```
video_understand (describe, 10 frames) → inform scene_plan
```

Analyze user-provided footage before planning cuts or edits. Use `blip2` for detailed descriptions that inform the scene plan.

### 2. Post-Render Quality Gate

```
video_understand (quality) → pass/fail → re-render if needed
```

Run after composing the final video. Fail if any frame has blur_score < 100, brightness outside 50-200, or contrast < 30.

### 3. Highlight Selection

```
video_understand (describe, 20 frames) → rank by visual interest → select clips
```

Sample many frames, describe each, then select the most visually compelling segments for a montage or trailer.

### 4. Asset Validation

```
video_understand (qa, "Does this match: [scene description]?") → confirm or regenerate
```

After generating an image or video clip, verify it matches the intended scene description before proceeding.

### 5. Talking-Head Analysis

```
video_understand (qa, "Is the speaker's face clearly visible?") → face_enhance if needed
```

Check face visibility and framing before applying lip-sync or face restoration tools.

## Quality Checklist

- Descriptions accurately match what's in the frame
- Quality scores correlate with visual inspection (manually spot-check)
- QA answers are consistent across similar frames
- Classification categories are stable across adjacent frames
- No false positives in quality gating (good frames passing, bad frames failing)

## Applying to Balamonis Studio

When using the `video_understand` tool:

1. **Use `quality` mode as a post-render gate in the compose stage** — reject outputs below quality thresholds
2. **Use `describe` mode to analyze user-provided footage** at the start of the talking-head pipeline
3. **For batch quality checks, use `clip` model** (fastest) — switch to `blip2` only for detailed review
4. **Sample at least 3 frames for quality assessment** — beginning, middle, end
5. **Quality thresholds for passing:** blur_score > 100, brightness 50-200, contrast > 30
6. **Use `qa` mode to validate generated assets:** "Does this image show [expected content]?"
7. **In the review stage**, combine video_understand quality data with the reviewer skill's rubric
8. **Do NOT run video_understand on every frame of a long video** — sample strategically
