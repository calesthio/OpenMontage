# ManimCE Usage for OpenMontage

> Sources: ManimCE documentation, 3Blue1Brown FAQ/conventions, Theorem of Beethoven tutorials,
> existing Layer 3 skill at `.agents/skills/manimce-best-practices/`

## Quick Reference Card

```
RENDER QUALITY:   quality="high" (1080p60) for YouTube  |  quality="medium" (720p30, the default) for drafts
BACKGROUND:       Dark (#1a1a2e or BLACK)
MAX ELEMENTS:     3-4 new visual elements revealed simultaneously
PACING:           One concept per scene, build incrementally
EQUATION WRITE:   1.5-2.0s run_time
SHAPE CREATE:     0.8-1.2s run_time
WAIT AFTER:       1.0-2.0s (longer for complex equations)
2D vs 3D:         Default to 2D. 3D only when spatial relationship IS the concept.
```

## Render Settings for OpenMontage

`math_animate` takes a `quality` name, not a Manim CLI flag:

| `quality` | Manim flag it maps to | Resolution | FPS | Use Case |
|-----------|----------------------|-----------|-----|----------|
| `low` | `-ql` | 854x480 | 15 | Development/testing |
| `medium` (default) | `-qm` | 1280x720 | 30 | Draft review |
| `high` | `-qh` | 1920x1080 | 60 | Standard YouTube upload |
| `4k` | `-qk` | 3840x2160 | 60 | 4K archival/premium |
| `preview` | `-ql --format gif` | 854x480 | 15 | Quick GIF preview |

There is no 1440p (`-qp`) preset. Omitting `quality` renders 720p30, not 1080p.

For OpenMontage's YouTube landscape profile (1920x1080/30fps), render with `quality: "high"` and transcode to 30fps. `math_animate` runs Manim from a temporary directory, so a project `manim.cfg` like the one below is not picked up by the tool — it only applies when you run the `manim` CLI yourself:

```ini
[CLI]
pixel_width = 1920
pixel_height = 1080
frame_rate = 30
```

## Animation Timing

| Animation Type | `run_time` | Rate Function | Notes |
|---------------|-----------|---------------|-------|
| Equation write (`Write`) | 1.5-2.0s | `smooth` (default) | Give viewers time to parse LaTeX |
| Equation transform | 1.5s | `smooth` | Use `TransformMatchingTex` for derivations |
| Shape creation (`Create`) | 0.8-1.2s | `smooth` | `Create()` or `DrawBorderThenFill()` |
| Color highlight | 0.5s | `smooth` | Brief attention call |
| Camera zoom | 1.5-2.0s | `ease_in_out_cubic` | Smooth entry/exit |
| Staggered reveals | `lag_ratio=0.1-0.2` | — | `LaggedStart` for grid/list reveals |
| Wait after reveal | 1.0-2.0s | — | Longer for complex equations |
| Fast cut / punctuation | 0.3-0.5s | `rush_from` | Between concepts |

## Scene Composition

### Pacing Rule (3Blue1Brown Convention)

- **One concept per scene** — build incrementally
- Show the simple version first, then `Transform` it into the complex version
- Never reveal more than **3-4 new visual elements** simultaneously
- Use `self.wait(1.5)` after every major reveal

### 2D vs 3D Decision

**Use 2D** (`Scene` or `MovingCameraScene`) for:
- Equation derivations, graph plots, number lines, matrices
- 2D vector spaces (even for "high dimensions" — project down)
- State diagrams, flowcharts, timelines

**Use 3D** (`ThreeDScene`) only when:
- Visualizing surfaces (`z = f(x,y)`), volumes, or 3D vector fields
- The spatial relationship IS the concept (cross products, surface normals)
- You need camera orbit to reveal hidden structure

**Performance:** 3D uses CPU-only Cairo rendering — 5-10x slower than 2D.

## Color Usage

| Semantic Role | Color | Manim Constant |
|--------------|-------|----------------|
| Variable being solved | Yellow | `YELLOW` |
| Matrix / operator | Red | `RED` |
| Eigenvector / result | Teal | `TEAL` |
| Known constant | Blue | `BLUE_C` |
| Annotation / label | Green | `GREEN` |
| De-emphasis / background | Grey 50% | `GREY`, `opacity=0.5` |
| Error / wrong path | Dark red | `RED_E` |

**Accessibility:** Avoid red-green only distinctions. Use brightness variation (`_A` through `_E` shades) alongside hue changes.

**Background:** Always use dark backgrounds (`BLACK` or `#1a1a2e`) for video output.

## Applying to OpenMontage

When using the `math_animate` tool:

1. **Render with `quality: "high"`** (1080p60) for final output, `"medium"` (the default) for drafts — pass the names `low` | `medium` | `high` | `4k` | `preview`, never `-qh`-style flags
2. **One concept per scene** — break complex proofs into multiple Manim scenes
3. **Use timing table above** — don't rush equations (1.5-2.0s for writes)
4. **Wait after reveals** — `self.wait(1.5)` minimum after key insights
5. **Dark background** — set `background_color=BLACK` in config
6. **Use color semantically** — yellow for unknowns, blue for knowns, red for operators
7. **Default to 2D** — only use `ThreeDScene` when 3D is essential to understanding
8. **Stagger complex reveals** — `LaggedStart` with `lag_ratio=0.15` for lists/grids
9. **Sync to narration** — the scene's total duration should match the narration segment timing from the script
