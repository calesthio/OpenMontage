# Scene Detection Usage for Balamonis Studio

> Sources: PySceneDetect documentation, FFmpeg scenedetect filter docs, PySceneDetect
> GitHub issues #187 (threshold tuning) and #226 (adaptive discussion)

## Quick Reference Card

```
DEFAULT METHOD:   content (ContentDetector) — works for most content
DEFAULT THRESH:   27.0 (range 0-255)
MIN SCENE LEN:    1.0s default, 2.0-3.0s for educational video
TUNING:           Generate stats CSV first, inspect content_val column
HARD CUTS:        Use content detector
FADE TO BLACK:    Use threshold detector
MIXED CONTENT:    Use adaptive detector
```

## Algorithm Selection

| Method | Default Threshold | Best For | How It Works |
|--------|------------------|----------|-------------|
| `content` | 27.0 | Hard cuts between shots | HSV color difference between adjacent frames (0-255) |
| `threshold` | 12.0 | Fades to/from black | Average pixel intensity; detects transitions through black |
| `adaptive` | 3.0 | Mixed content with camera motion | Rolling average of frame differences; adapts to local pace |

## Threshold Tuning Guide

### ContentDetector (Default, Start Here)

| Symptom | Action | New Threshold |
|---------|--------|---------------|
| Too many false cuts | Raise threshold | 35-45 |
| Missing real cuts | Lower threshold | 20-22 |
| Fast-paced content (music videos, action) | Raise | 35-40 |
| Slow/static content (talking heads, presentations) | Lower | 20-25 |
| Animated content (Manim, motion graphics) | Raise | 30-35 |

### AdaptiveDetector

- Multiplier on rolling average (default 3.0)
- Better than ContentDetector when there's fast camera motion causing false positives
- Good default for Balamonis Studio explainers where Manim segments are static but live-action may have motion

### ThresholdDetector

- Only for videos with deliberate fade-to-black transitions
- Most AI-generated video does NOT use fades — prefer `content` or `adaptive`

## Tuning Workflow

1. **Generate stats file first:**
   ```bash
   scenedetect -i video.mp4 --stats stats.csv detect-content
   ```

2. **Inspect `stats.csv`** — look at the `content_val` column. Peaks = scene changes.

3. **Set threshold** just below the smallest real peak.

4. **Set `min_scene_length`** to suppress micro-scenes:
   - Educational video: 2.0-3.0s minimum
   - Fast-paced content: 0.5-1.0s
   - Default: 1.0s

### Component Weights (Advanced)

ContentDetector score = weighted sum of HSV + edge differences:

```
weights = (delta_hue, delta_sat, delta_lum, delta_edges)
Default: (1.0, 1.0, 1.0, 0.0)
```

For animated content with color transitions but few actual cuts:
```
weights=(1.0, 0.5, 1.0, 0.2), threshold=32
```

## Post-Processing Detected Scenes

After detection, clean up the scene list:

1. **Merge too-short segments** — any scene under `min_scene_length` should be merged with the adjacent scene
2. **Validate boundaries** — check that scene boundaries align with narration pauses (for explainers)
3. **Label scenes** — map detected scenes to script sections for the edit stage

## Content-Type Presets

| Content Type | Method | Threshold | Min Scene Length |
|-------------|--------|-----------|-----------------|
| Talking head (single camera) | content | 22 | 3.0s |
| Talking head (multi-camera) | content | 27 | 1.0s |
| Screen recording | content | 30 | 2.0s |
| Animated explainer | adaptive | 3.0 | 2.0s |
| Fast-paced montage | content | 40 | 0.5s |
| Documentary with fades | threshold | 12 | 2.0s |

## Applying to Balamonis Studio

When using the `scene_detect` tool:

1. **Start with `content` method, threshold 27** — it works for most content
2. **For talking-head pipeline**, lower threshold to 22 and set min_scene_length to 3.0s
3. **For animated-explainer pipeline**, use `adaptive` with default threshold 3.0
4. **Always generate stats CSV first** when tuning — don't guess thresholds
5. **Set min_scene_length to 2.0s** for educational content to avoid micro-scenes
6. **Use detected scenes to inform the edit stage** — map scenes to script sections
7. **For AI-generated video clips**, use `content` not `threshold` — AI video rarely uses fade-to-black
