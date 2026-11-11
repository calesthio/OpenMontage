# Diagram Generation Usage for OpenMontage

> Sources: Mermaid.js documentation, existing Layer 3 skill at `.agents/skills/beautiful-mermaid/`,
> Mermaid-Sonar complexity analysis research, Mermaid GitHub issues #651 (scaling), #3029 (animation)

## Quick Reference Card

```
MAX NODES (1080p):  15-20 nodes, 20-25 edges
MAX NODES (4K):     25-35 nodes, 35-45 edges
MAX NODES (vert):   10-12 nodes, 12-15 edges
MIN FONT SIZE:      16px at 1080p, 14px at 4K
RENDER WIDTH:       Minimum 1200px (the `width` default) — raise `width` for high-res PNG export
RENDER VIEWPORT:    Not settable — for Mermaid only `width` reaches the renderer
THEME (dark bg):    dark (default)
THEME (light bg):   light
THEME VALUES:       dark | light | neutral — nothing else
```

## Diagram Type Selection

| Type | Video Suitability | Best For |
|------|------------------|----------|
| **Flowchart (TD)** | Excellent | Process flows, decision trees, algorithms |
| **Sequence diagram** | Good | API calls, user interactions, message flows |
| **State diagram** | Good | State machines, lifecycle, workflow status |
| **Class diagram** | Fair | Architecture (limit to 3-5 classes) |
| **ER diagram** | Poor for video | Too dense — simplify to key entities only |
| **Gantt chart** | Fair | Timelines, project phases |
| **Mindmap** | Good | Concept overviews, topic breakdowns |

**Default:** Use flowcharts (top-down `TD`) unless the content specifically requires another type. They read naturally and build well step by step.

## Complexity Limits for Video

Video is transient — viewers can't zoom or scroll. Cut complexity in half compared to static documentation.

| Target Resolution | Max Nodes | Max Edges | Min Font Size (CSS) |
|------------------|-----------|-----------|---------------------|
| 1920x1080 (HD) | 15-20 | 20-25 | 16px |
| 3840x2160 (4K) | 25-35 | 35-45 | 14px |
| 1080x1920 (vertical) | 10-12 | 12-15 | 18px |

**If your diagram exceeds these limits:** Split it into multiple frames, each showing a subset. This also creates a natural "building" animation for the video.

## Color Themes for Video

| Use Case | Theme | Why |
|----------|-------|-----|
| Dark video background | `dark` (default) | High contrast, readable |
| Light video background | `light` | Soft, professional |
| Code/developer content | `dark` | Familiar to dev audience |
| No color bias | `neutral` | Neutral, no color bias |
| Corporate/presentation | `light` or `neutral` | Calm, professional |

`diagram_gen`'s `theme` accepts only `dark`, `light` and `neutral`. The named palettes in the
Layer 3 `beautiful-mermaid` skill (`tokyo-night`, `dracula`, `github-light`, `nord-light`, ...) are
**not** `diagram_gen` themes. They are not rejected either: box/flowchart diagrams silently render
with the `neutral` palette, and Mermaid has no theme by those names — so you do not get the look
you asked for.

**Match the playbook:** The diagram theme should complement the style playbook's color palette. Pick the closest of the three themes and set exact playbook colors inside the definition with `classDef` (see below).

## Progressive Building for Video

Mermaid doesn't animate natively. Use progressive rendering to create a "building" effect:

### Approach: Multi-Stage Renders

1. Render diagram in stages — first 2 nodes, then 4, then full diagram
2. Each stage is a separate Mermaid render → SVG → PNG
3. Crossfade or cut between stages in FFmpeg
4. Viewers follow the logic step by step

### Highlighting Current Step

Use `classDef` to highlight the active node and dim completed ones:

```mermaid
graph TD
    A[Input Data]:::completed --> B[Process]:::highlight
    B --> C[Output]:::dimmed
    classDef highlight fill:#f96,stroke:#333,stroke-width:3px
    classDef completed fill:#6c6,stroke:#333,stroke-width:1px
    classDef dimmed fill:#555,stroke:#333,opacity:0.5
```

Generate one PNG per step with different `classDef` assignments, then sequence them in the compose stage.

## Styling for Video Readability

### Node Sizing
- Minimum node width: 150px at 1080p
- Padding inside nodes: 15-20px
- Keep text to 3-5 words per node — use abbreviations if needed

### Edge Labels
- Keep to 1-2 words maximum
- Use edge labels only when the relationship isn't obvious from context
- Prefer labeled nodes over labeled edges

### Layout Direction
- **Top-down (TD):** Best for processes, hierarchies, flows
- **Left-right (LR):** Best for timelines, sequences, pipelines
- Avoid bottom-up (BT) — counterintuitive for most viewers

## Applying to OpenMontage

When using the `diagram_gen` tool:

1. **Check complexity** — max 15-20 nodes at 1080p. Split larger diagrams into multiple frames
2. **Choose theme** (`dark`, `light` or `neutral`) to match the video's style playbook and background
3. **Use progressive building** — render stages and crossfade for "building" effect in video
4. **Highlight with classDef** — show the current step in orange/red, completed in green, upcoming in grey
5. **Keep text minimal** — 3-5 words per node, 1-2 words per edge label
6. **Default to flowchart TD** unless the content specifically requires another diagram type — pass every Mermaid diagram (flowcharts included) as `diagram_type: "mermaid"` + `definition`. `diagram_type: "flowchart"` is NOT Mermaid: like `boxes`, it draws the `boxes` / `connections` arrays with Pillow
7. **Render wide** — pass a larger `width` (default 1200) for 1080p/4K output. A 3840x2160 viewport cannot be requested: for Mermaid, `width` is the only size input that reaches the renderer (`height` applies to `flowchart` / `boxes` only). Check the PNG's real pixel size before composing
8. **Test readability** — view the rendered PNG at actual video frame size before composing
