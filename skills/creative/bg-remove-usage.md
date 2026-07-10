# Background Removal Usage for Balamonis Studio

> Sources: rembg library documentation, U2Net paper (Qin et al. 2020), IS-Net paper
> (Qin et al. 2022), Balamonis Studio `tools/bg_remove.py` implementation

## Quick Reference Card

```
DEFAULT MODEL:    u2net (general purpose, fast)
FOR PEOPLE:       u2net_human_seg (optimized for human silhouettes)
FINE EDGES:       Enable alpha_matting (hair, fur, leaves)
OUTPUT:           Transparent PNG by default; set bg_color for solid replacement
RUNTIME:          ~1-3s per image (CPU), <0.5s (GPU with onnxruntime-gpu)
INSTALL:          pip install rembg (CPU) | pip install rembg[gpu] (CUDA)
```

## When to Use bg_remove

Background removal is an **asset-prep** step. Use it before the compose stage.

- **Product demos / e-commerce videos** -- isolate a product on a clean background
- **Compositing** -- layer a speaker over generated backgrounds or diagrams
- **Thumbnail generation** -- clean cutouts for YouTube thumbnails
- **Green-screen replacement** -- achieve green-screen results without an actual green screen
- **B-roll preparation** -- clean up raw photos for overlay use

## Model Selection Guide

| Model | Best For | Speed | Notes |
|-------|----------|-------|-------|
| `u2net` | General objects, products, scenes | Fast | Default; good all-rounder |
| `u2net_human_seg` | People, portraits, speakers | Fast | More accurate masks for human silhouettes |
| `isnet-general-use` | Complex edges, hair, fur | Slower | Higher detail on fine boundaries |

**Decision rule:** If the subject is a person, use `u2net_human_seg`. If the subject has intricate edges (hair, fur, foliage) and you need maximum quality, use `isnet-general-use`. Otherwise, use the default `u2net`.

## Alpha Matting

Alpha matting refines the edge mask by computing soft transparency at boundaries. It produces more natural edges but costs approximately 2x processing time.

| Subject Type | Alpha Matting | Reason |
|-------------|---------------|--------|
| Hair, fur, feathers | Enable | Fine semi-transparent strands need soft edges |
| Leaves, trees, grass | Enable | Irregular organic boundaries benefit from matting |
| Products, devices | Disable | Clean geometric edges; matting adds no value |
| Text, logos, shapes | Disable | Hard edges are correct for these subjects |

## Common Workflows

### 1. Speaker Cutout for Compositing

Extract a speaker from their background and layer over a diagram or slide.

```
bg_remove(input_path="speaker.png", model="u2net_human_seg")
  --> speaker_nobg.png (transparent)
  --> compose over diagram/slide in compose stage
```

### 2. Product Isolation

Isolate a product and optionally place on a brand-colored background.

```
bg_remove(input_path="product.jpg", model="u2net")
  --> product_nobg.png (transparent)

# Or with brand background:
bg_remove(input_path="product.jpg", model="u2net", bg_color="#FFFFFF")
  --> product_nobg.png (white background)
```

### 3. Thumbnail Prep

Remove background, upscale, then compose with text overlays.

```
bg_remove(input_path="subject.png", model="u2net_human_seg", alpha_matting=True)
  --> subject_nobg.png
  --> upscale --> compose with text overlays in compose stage
```

### 4. Batch Frame Processing

When preparing multiple frames for a compositing sequence, process all source frames before entering the compose stage.

```
for each source frame:
    bg_remove(input_path=frame, model="u2net_human_seg")
    --> frame_nobg.png
then: compose all transparent frames over background sequence
```

## Quality Checklist

Before moving to the compose stage, verify each bg_remove output:

- [ ] **Edge quality is clean** -- no halo artifacts around the subject
- [ ] **Fine details preserved** -- hair, fingers, and thin features are intact
- [ ] **Transparency is complete** -- no residual background bleed in transparent areas
- [ ] **Subject integrity** -- no parts of the subject were incorrectly removed
- [ ] **Compositing test** -- when layered over the target background, the subject blends naturally

## Applying to Balamonis Studio

When using the `bg_remove` tool in asset preparation:

1. **Use `u2net_human_seg` for any frame containing people** -- it produces tighter masks around human silhouettes than the general model
2. **Enable `alpha_matting` only for subjects with complex edges** like hair, fur, or foliage -- skip it for clean-edged subjects to save processing time
3. **For compositing workflows, output transparent PNG** (omit `bg_color`) and layer in the compose stage -- this preserves maximum flexibility
4. **For solid-background replacements, set `bg_color`** to match the playbook's background color token -- keeps outputs consistent with the project style
5. **Process source frames BEFORE the compose stage** -- bg_remove is an asset-prep step, not a compose-time operation
6. **Check output edges at full resolution before compositing** -- halo artifacts and edge bleed are visible in final video and must be caught early
