# Face Restoration Usage for Balamonis Studio

> Sources: CodeFormer paper (Zhou et al. 2022), GFPGAN documentation, Real-ESRGAN upsampling docs,
> existing Layer 2 skill at `skills/creative/enhancement-strategy.md`

## Quick Reference Card

```
DEFAULT MODEL:    CodeFormer with fidelity 0.5
ALTERNATIVE:      GFPGAN (faster, less controllable)
FIDELITY RANGE:   0 = max quality enhancement, 1 = max faithfulness to input
BG UPSAMPLER:     Enable to also upscale the background (Real-ESRGAN)
PROCESSING ORDER: face_restore BEFORE face_enhance — restore first, polish second
```

## CRITICAL DISTINCTION — face_restore vs face_enhance

| Tool | What It Does | When to Use |
|------|-------------|-------------|
| `face_enhance` | FFmpeg filter chains — skin smoothing, color balance, sharpening | Good-quality footage that needs polish |
| `face_restore` | AI model reconstruction — rebuilds degraded face detail | Bad-quality footage with blur, compression, low-res faces |

**Decision rule:** If the face is recognizable and just needs polish, use `face_enhance`. If the face is degraded, blurry, or compressed beyond recognition, use `face_restore`.

## Model Selection

| Model | Strengths | Fidelity Control | Speed |
|-------|----------|------------------|-------|
| CodeFormer | Better quality, identity preservation, controllable | Yes (0-1 slider) | Slower |
| GFPGAN | Good baseline, simpler | No | Faster |

### Fidelity Tuning (CodeFormer Only)

| Fidelity | Effect | Use Case |
|----------|--------|----------|
| 0.0 | Maximum enhancement — best visual quality but may alter identity | Unrecognizable faces, artistic use |
| 0.3 | Strong restoration — good for very degraded faces | Old footage, heavy compression artifacts |
| 0.5 | Balanced (default) — restoration + identity preservation | General-purpose restoration |
| 0.7 | Conservative — mild cleanup, strong identity preservation | Webcam footage, light degradation |
| 1.0 | Minimal change — essentially passthrough | Testing, comparison baseline |

## Common Workflows

### 1. Old Footage Restoration

```
face_restore (fidelity 0.3) → color_grade → compose
```

Heavy restoration for archival/vintage footage where faces are significantly degraded.

### 2. Webcam Cleanup

```
face_restore (fidelity 0.7) → face_enhance (talking_head_standard) → compose
```

Light restoration followed by polish — best for modern but low-quality webcam footage.

### 3. Low-Res Face + Background Upscale

```
face_restore (bg_upsampler=true) → compose
```

Single-step restoration when both face and background need improvement.

### 4. Archival Photo for Talking Head

```
face_restore → talking_head tool (SadTalker)
```

Restore the source face image before feeding into the talking-head animation pipeline.

## Quality Checklist

Before accepting face_restore output, verify:

- [ ] Restored face is sharper and cleaner than input
- [ ] Identity is preserved — the person is still recognizable
- [ ] No hallucinated features (extra eyes, wrong skin texture, teeth artifacts)
- [ ] Skin texture looks natural, not plastic/over-smoothed
- [ ] Consistent across frames (for video) — no flickering between restored/unrestored quality

## Applying to Balamonis Studio

When using the `face_restore` tool:

1. **Use face_restore BEFORE face_enhance** in the processing chain — restore first, polish second
2. **Start with fidelity 0.5** and adjust based on visual inspection
3. **For talking-head pipelines with poor source footage**, apply face_restore in the assets stage
4. **Enable `bg_upsampler` only when both face AND background need improvement**
5. **NEVER use face_restore on already-good footage** — it can introduce subtle artifacts
6. **Compare input and output side-by-side** — the face should be recognizably the same person
7. **For video, extract key frames and test face_restore settings** before processing full video
