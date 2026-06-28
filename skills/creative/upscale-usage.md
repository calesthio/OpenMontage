# Upscaling Usage for Balamonis Studio

> Sources: Real-ESRGAN documentation, GFPGAN face enhancement docs, Real-ESRGAN paper
> (Wang et al., 2021), practical upscaling benchmarks

## Quick Reference Card

```
DEFAULT MODEL:    RealESRGAN_x4plus — real-world photos and video frames
DEFAULT SCALE:    4x (480p→1080p, 720p→4K)
ANIME MODEL:     RealESRGAN_x4plus_anime_6B — flat color areas, illustrations
FACE ENHANCE:    Enable face_enhance for footage with people (uses GFPGAN)
DENOISE:         0.5 default, raise to 0.8 for very noisy inputs
```

## When to Upscale

| Situation | Upscale? | Notes |
|-----------|----------|-------|
| User-provided footage is 480p or 720p, target is 1080p/4K | Yes | Most common use case |
| Generated images need higher resolution for video frames | Yes | AI image output is often 512-1024px |
| Thumbnail or still frames need crisp detail | Yes | Single-frame upscale is fast |
| Old/archival footage restoration | Yes | Combine with higher denoise_strength |
| Source is already 1080p+ and target is 1080p | **No** | Wastes compute, can introduce artifacts |
| Source is already 4K | **No** | Over-sharpening degrades quality |

## Model Selection

| Model | Best For | Notes |
|-------|----------|-------|
| `RealESRGAN_x4plus` | Real-world photos, video frames | Default choice |
| `RealESRGAN_x4plus_anime_6B` | Anime, illustrations, motion graphics | Preserves flat color areas |
| `RealESRNet_x4plus` | Fastest option, slightly lower quality | When speed matters |

## Scale Factor Guidance

| Scale | Use Case | Example |
|-------|----------|---------|
| 4x | Standard upscale for low-res sources | 480p→1080p, 720p→4K |
| 2x | Moderate upscale when 4x is overkill | 720p→1080p |

- **4x** is the most common choice. Use it for 480p sources targeting 1080p, or 720p targeting 4K.
- **2x** is appropriate when the source is already 720p and the target is 1080p — avoids unnecessary processing and potential artifacts.
- **Never upscale beyond 4x in a single pass.** Quality degrades sharply, and hallucinated details become obvious.

## Face Enhancement

- Enable `face_enhance` when the video contains human faces
- Uses GFPGAN internally to enhance face regions while Real-ESRGAN handles the rest
- Particularly valuable for webcam footage and old video
- Do NOT enable for content without faces — adds processing time with no benefit

## Denoising Strength

| Source Quality | denoise_strength | Rationale |
|---------------|-----------------|-----------|
| Clean digital source | 0.5 (default) | Minimal denoising needed |
| Slight compression artifacts | 0.6 | Light cleanup without over-smoothing |
| Old/noisy footage | 0.7-0.8 | Aggressive denoising for archival content |
| Very noisy / low-light footage | 0.8 | Maximum practical denoising |

Do not exceed 0.8 — higher values destroy legitimate detail.

## Video Upscaling Notes

- Video upscaling extracts frames, upscales each, reassembles
- This is **SLOW** — budget 5-10x real-time on GPU
- For long videos, consider upscaling only key scenes/clips rather than the full video
- Audio is preserved from the original
- Output file size will be significantly larger (~16x for 4x upscale)

## Common Workflows

### Workflow 1 — User-Provided Low-Res Footage

```
1. Assess source resolution (e.g., 480p webcam recording)
2. Choose scale factor: 4x for 480p→1080p, 2x for 720p→1080p
3. Enable face_enhance if footage contains people
4. Set denoise_strength based on source quality
5. Upscale → inspect output → proceed to compose stage
```

### Workflow 2 — AI-Generated Image Frames

```
1. Generate images at native model resolution (512-1024px)
2. Upscale with RealESRGAN_x4plus to target video resolution
3. Keep denoise_strength at 0.5 — AI output is clean
4. Do NOT enable face_enhance unless faces are prominent
```

### Workflow 3 — Manim / Motion Graphics Frames

```
1. Render Manim at default resolution
2. Upscale with RealESRGAN_x4plus_anime_6B (preserves flat colors)
3. Keep denoise_strength at 0.5
4. Verify text and line art remain sharp
```

### Workflow 4 — Archival Footage Restoration

```
1. Assess noise level and resolution
2. Set denoise_strength to 0.7-0.8
3. Enable face_enhance for footage with people
4. Use RealESRGAN_x4plus at 4x
5. Carefully inspect output for hallucinated details
```

## Quality Checklist

- [ ] Upscaled output is sharp without visible artifacts
- [ ] Faces look natural (no over-smoothing or distortion)
- [ ] Text/UI elements in screen recordings remain readable
- [ ] No hallucinated details in flat color areas
- [ ] File size is reasonable (4x upscale = ~16x file size)

## Applying to Balamonis Studio

When using the `upscale` tool in the asset stage:

1. **Upscale BEFORE the compose stage** — it is an asset-prep step, not a post-processing step
2. **Use `face_enhance=true` for any talking-head footage** — GFPGAN dramatically improves face quality
3. **Use `RealESRGAN_x4plus_anime_6B` model for Manim outputs** or flat illustration frames — preserves clean edges and flat color areas
4. **For budget-conscious pipelines**, upscale only hero shots and thumbnails rather than every frame
5. **Set `denoise_strength` to 0.7-0.8 for old/noisy footage**, keep at 0.5 for clean digital sources
6. **Check upscaled output for artifacts** — over-sharpening, hallucinated texture, face distortion
7. **Prefer 2x over 4x when the source is already 720p and target is 1080p** — less compute, fewer artifacts
