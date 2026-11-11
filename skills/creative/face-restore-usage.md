# Face Restoration Usage for OpenMontage

> Sources: CodeFormer paper (Zhou et al. 2022), GFPGAN documentation, Real-ESRGAN upsampling docs,
> existing Layer 2 skill at `skills/creative/enhancement-strategy.md`

## Quick Reference Card

```
DEFAULT MODEL:    GFPGAN (model="GFPGAN" — the tool default and the only model that runs)
NOT AVAILABLE:    CodeFormer — model="CodeFormer" returns success=false (not supported by the gfpgan backend)
FIDELITY:         CodeFormer-only parameter — it has NO effect with GFPGAN, do not tune it
INPUT:            ONE image per call (a photo or one extracted video frame) — never a video file
UPSCALE:          upscale=2 (default face upscale factor)
BG UPSAMPLER:     Enable to also upscale the background (Real-ESRGAN)
PROCESSING ORDER: face_restore BEFORE face_enhance — restore first, polish second
```

## CRITICAL DISTINCTION — face_restore vs face_enhance

| Tool | What It Does | When to Use |
|------|-------------|-------------|
| `face_enhance` | FFmpeg filter chains — skin smoothing, color balance, sharpening | Good-quality footage that needs polish |
| `face_restore` | AI model reconstruction — rebuilds degraded face detail, one image at a time | A bad-quality photo or extracted frame with blur, compression, low-res faces |

**Decision rule:** If the face is recognizable and just needs polish, use `face_enhance`. If the face is degraded, blurry, or compressed beyond recognition, use `face_restore`.

## Model Selection

| Model | Status in `face_restore` | Fidelity Control |
|-------|--------------------------|------------------|
| GFPGAN | **Works — the default.** Good baseline restoration (GFPGAN v1.3) | No |
| CodeFormer | **Not available.** The schema lists it, but the call returns `success=false` ("not supported by the gfpgan backend") | — |

Always call `face_restore` with `model="GFPGAN"` (or omit `model`).

### Fidelity

The `fidelity` input (default 0.5) only applies to CodeFormer, which does not run. With GFPGAN it is
ignored — there is no restoration-strength control. The only tuning inputs that do something are
`upscale` (face upscale factor, default 2) and `bg_upsampler`. If the result alters the identity too
much, keep the original image instead of trying another fidelity value.

### Images Only

`face_restore` reads `input_path` as a single image. Passing a video file fails with
"Failed to read image". For footage, extract frames first (`frame_sampler`), restore the frames you
need, and treat frame-by-frame restoration of a whole video as a manual, slow process.

## Common Workflows

### 1. Old Photo / Archival Frame Restoration

```
(frame_sampler →) face_restore → compose
```

Restoration for archival/vintage stills, or frames extracted from old footage, where faces are significantly degraded.

### 2. Webcam Still Cleanup

```
frame_sampler → face_restore → compose
```

Restore a low-quality webcam frame used as a still. For polishing the webcam *video* itself, use
`face_enhance` (talking_head_standard) on the video — `face_restore` cannot process it.

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
- [ ] If several extracted frames were restored, they look consistent with each other — no jump between restored/unrestored quality

## Applying to OpenMontage

When using the `face_restore` tool:

1. **Use face_restore BEFORE face_enhance** in the processing chain — restore first, polish second
2. **Use the default `model="GFPGAN"`** — do not pass `model="CodeFormer"` (it fails) and do not tune `fidelity` (ignored by GFPGAN)
3. **For talking-head pipelines with a poor source photo or frame**, apply face_restore to that image in the assets stage
4. **Enable `bg_upsampler` only when both face AND background need improvement**
5. **NEVER use face_restore on already-good footage** — it can introduce subtle artifacts
6. **Compare input and output side-by-side** — the face should be recognizably the same person
7. **`input_path` must be an image** — for video, extract frames with `frame_sampler` and restore those; the tool does not read video files
