---
name: agnes-video
description: |
  Agnes AI video generation with Sapiens AI models. Use when: (1) Generating video via agnes-video-v2.0, (2) Cost-free video generation, (3) Keyframe animation, (4) Multi-image video compositing, (5) Budget-constrained cinematic content.
allowed-tools: Bash, Read, Write
metadata:
  author: Sapiens AI
  version: "1.0.0"
  tags: agnes, sapiens, video-generation, t2v, i2v, keyframes
---

# Agnes Video V2.0

## When to Use

- Cost-free video generation (currently $0/second, standard price $0.005/second)
- Keyframe animation — smooth transitions between visual states
- Multi-image video compositing — combine reference images into video
- Budget-constrained cinematic b-roll and short clips
- Social media video content (Reels, Shorts, TikTok)

## Model

- **`agnes-video-v2.0`** — asynchronous task-based generation

## API Pattern (Async)

1. **Create task**: `POST https://apihub.agnes-ai.com/v1/videos`
2. **Poll result**: `GET https://apihub.agnes-ai.com/agnesapi?video_id=<VIDEO_ID>`
3. **Download**: fetch from `remixed_from_video_id` field when status is `completed`

Task statuses: `queued` → `in_progress` → `completed` / `failed`

## Operations

| Operation | Required Input | Description |
|-----------|---------------|-------------|
| `text_to_video` | prompt | Generate from text description |
| `image_to_video` | prompt + image_url | Animate a single image |
| `multi_image_to_video` | prompt + image_urls | Combine multiple reference images |
| `keyframe_animation` | prompt + image_urls + mode=keyframes | Smooth transition between keyframes |

## Duration Control

```
seconds = num_frames / frame_rate
```

- `num_frames` must follow the **8n + 1** rule (e.g. 81, 121, 161, 241, 441)
- `num_frames` maximum: **441**
- `frame_rate`: 1–60 (24 or 30 recommended for smooth playback)

| Target Duration | num_frames | frame_rate |
|----------------|------------|------------|
| ~3 seconds | 81 | 24 |
| ~5 seconds | 121 | 24 |
| ~10 seconds | 241 | 24 |
| ~18 seconds | 441 | 24 |

## Aspect Ratios

| Ratio | Width x Height | Best For |
|-------|---------------|----------|
| 16:9 | 1152 x 768 | YouTube, landscape, product demos |
| 9:16 | 768 x 1152 | TikTok, Reels, Shorts |
| 1:1 | 768 x 768 | Social feeds, product showcases |
| 4:3 | 1024 x 768 | Presentations, general content |
| 3:4 | 768 x 1024 | Portrait content, product-focused |

## Prompt Structure

### Text-to-Video

```
[Subject] + [Action] + [Scene] + [Camera Movement] + [Lighting] + [Style]
```

Example:
```
A young astronaut walking across a red desert planet, dust blowing in the wind,
slow cinematic tracking shot, dramatic sunset lighting, realistic sci-fi style
```

### Image-to-Video

Describe what should move and what should stay stable:

```
Animate the character with subtle breathing motion, hair moving gently in the
wind, background lights flickering softly, while keeping the face and outfit
consistent
```

### Multi-Image Video

Describe the relationship between input images and how the scene should transition:

```
Use the first image as the starting scene and the second image as the target
scene. Create a smooth transformation with consistent lighting, natural motion,
and cinematic pacing
```

### Keyframe Animation

Clearly describe the transition between keyframes:

```
Create a smooth transition from the first keyframe to the second keyframe,
maintaining character identity, consistent camera angle, and natural motion
between scenes
```

## Parameter Normalization

The Agnes API normalizes width/height to the nearest standard resolution (480p, 720p, 1080p). The requested dimensions may not exactly match the output. Use the `size` and `seconds` fields from the response as the source of truth.

**Important: Image-to-video resolution behavior.** When using I2V with a source image, the API may normalize the output to a different aspect ratio than the source image (e.g., a portrait image may produce a landscape video). This can cause cropping — especially cutting off the head in portrait-to-landscape conversions. **For character-consistent portrait/9:16 videos, prefer T2V with a detailed character description in the prompt** rather than I2V, as T2V reliably respects the `aspect_ratio` parameter.

**Local image upload.** When `image_path` is provided instead of `image_url`, the tool relays the image through the Agnes images API to obtain a public URL (Agnes video API requires publicly accessible URLs). The relay preserves the original image dimensions and content. Fallback: fal.ai upload (if `FAL_KEY` is set), then data URI base64 (may fail for large images).

## Key Differences from Other Providers

| Aspect | Agnes Video | fal.ai (Seedance/Kling) |
|--------|-------------|------------------------|
| API pattern | Async: POST then GET poll | Async: queue POST then poll status_url |
| Task ID | `video_id` (recommended) | `request_id` via status_url |
| Result field | `remixed_from_video_id` | `video.url` |
| Duration control | `num_frames` + `frame_rate` | `duration` string |
| Reference images | In `extra_body.image` top-level or array | `image_url` or `reference_image_urls` |
| Pricing | Currently free | Paid per second |

## Calling via OpenMontage

Always go through `video_selector`:

```python
from tools.tool_registry import registry
registry.ensure_discovered()
selector = registry.get("video_selector")
result = selector.execute({
    "prompt": PROMPT,
    "preferred_provider": "agnes",
    "operation": "text_to_video",
    "aspect_ratio": "16:9",
    "output_path": "projects/<proj>/assets/video/clip_01.mp4",
})
```

Direct call to the provider tool:

```python
agnes = registry.get("agnes_video")
result = agnes.execute({
    "prompt": PROMPT,
    "operation": "text_to_video",
    "aspect_ratio": "16:9",
    "num_frames": 121,
    "frame_rate": 24,
    "seed": 12345,
    "output_path": "output.mp4",
})
```

## Integration Checklist

- Video generation is **asynchronous** — always create task then poll
- Use `video_id` (not `task_id`) for polling — it is the recommended ID
- Set `extra_body.mode: "keyframes"` for keyframe animation
- Use publicly accessible image URLs for all reference images
- Poll every 5s with exponential backoff (max 30s interval, 600s total timeout)
- Use response `size` and `seconds` as source of truth after normalization
- `negative_prompt` supported — use to avoid unwanted content
