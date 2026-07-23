# Data Visualization Strategy Skill

## When to Use

Apply this skill when a scene requires presenting data visually: statistics, comparisons,
trends, compositions, or key metrics. This skill guides chart type selection, animation
sequencing, label placement, data density, and color usage to produce charts that are
clear, accurate, and effective in video.

## Tools

| Tool | Role |
|------|------|
| `diagram_gen` | Generate charts via Mermaid or D3 |
| `image_selector` | Generate stylized chart illustrations (FLUX/GPT Image) |
| Remotion | Animated chart components (bar grow, line draw, pie fill) |
| Manim | Mathematical plots, coordinate systems, function graphs |

## Chart Type Decision Tree

Follow this tree top-to-bottom. Stop at the first match.

```
Is there data to visualize?
  NO  -> Use a text card or stat card instead
  YES -> How many data points?
           < 3 -> Use text or stat card (charts look empty with 1-2 points)
           3-9 -> Continue to "What story does the data tell?"
           > 12 -> Simplify first: aggregate into top-N + "Other", then continue

What story does the data tell?
  |
  |-- Comparing quantities across categories?
  |     -> BAR CHART (horizontal if labels are long)
  |
  |-- Showing a trend over time?
  |     -> LINE CHART (area chart if showing volume)
  |
  |-- Showing parts of a whole?
  |     -> PIE / DONUT CHART (max 5-6 slices)
  |     (If > 6 categories, aggregate smallest into "Other")
  |
  |-- Showing key metrics / KPIs?
  |     -> KPI GRID (3-6 stat cards in a grid layout)
  |
  |-- Showing ranking or ordered list?
  |     -> HORIZONTAL BAR CHART (sorted descending)
  |
  |-- Showing before/after or change?
  |     -> PAIRED BAR CHART or STAT CARD with delta arrow
  |
  |-- Showing correlation between two variables?
  |     -> LINE CHART with dual series (avoid scatter in video -- too dense)
  |
  |-- None of the above?
  |     -> Default to BAR CHART (most universally readable)
```

### When NOT to Use a Chart

| Situation | Do This Instead |
|-----------|----------------|
| Fewer than 3 data points | Stat card or text overlay: "Revenue grew 40% to $2.1M" |
| More than 12 categories | Aggregate into top 5-7 + "Other", then chart |
| Single number to emphasize | Full-screen stat card with impact animation |
| Qualitative comparison | Side-by-side images or text table |
| Data requires 30+ seconds to read | Split into multiple simpler charts across scenes |

## Animation Sequencing

Every chart in video should be animated. Static charts feel like slides, not video.

### Pattern: Build-Up (Default)

Show empty axes/frame, then animate data in.

```
Frame 0.0s: Empty chart frame (axes, title, gridlines visible)
Frame 0.3s: First data element begins animating in
Frame 2.0s: All data elements fully rendered
Frame 2.0-5.0s: Hold for readability
```

- **Bar charts:** Bars grow upward from baseline (stagger left-to-right, 0.1s delay each)
- **Line charts:** Line draws left-to-right following the data path
- **Pie/donut charts:** Slices fill clockwise from 12 o'clock, largest slice first
- **KPI grid:** Numbers count up from 0 to final value (odometer effect)

### Pattern: Narrative Highlight

Highlight one element at a time as narration mentions it.

```
Frame 0.0s: Full chart visible but all elements at 30% opacity (desaturated)
Frame 0.5s: First highlighted element goes full color + slight scale-up
Frame 3.0s: First element returns to normal, second element highlights
...continue for each narrated point
```

Use when the narrator walks through specific data points. Keeps viewer focus synchronized
with the voiceover.

### Pattern: Comparison Reveal

Show baseline, then animate the change.

```
Frame 0.0s: Baseline data visible (e.g., "Before" bars)
Frame 2.0s: Hold baseline for comprehension
Frame 2.5s: Animate change (bars grow/shrink to "After" values)
Frame 3.5s: Delta labels appear (+40%, -15%, etc.)
Frame 3.5-7.0s: Hold for readability
```

Use for before/after, year-over-year, or A/B comparisons.

### Timing Rules

| Element | Animation Duration | Hold Duration |
|---------|-------------------|---------------|
| Chart build-up | 2-4 seconds | 3-5 seconds |
| Single element highlight | 0.3-0.5 seconds | 2-3 seconds |
| Comparison transition | 1-2 seconds | 3-5 seconds |
| KPI counter | 1.5-2 seconds | 2-3 seconds |
| Label/annotation appear | 0.2-0.3 seconds | Remains on screen |

**Critical rule:** The chart must be fully built and held for at least 3 seconds before the
scene transitions. Viewers need time to read. If the narration moves on before the chart is
readable, either extend the scene or simplify the chart.

## Label Placement Rules

### Bar Charts

```
Vertical bars:
  - Value labels: ABOVE each bar (or INSIDE if bar is tall enough for legible text)
  - Category labels: Below on x-axis, horizontal text
  - If labels overlap: rotate 45 degrees or use horizontal bars instead
  - Y-axis: include gridlines, omit axis label if title makes it obvious

Horizontal bars:
  - Value labels: TO THE RIGHT of each bar
  - Category labels: Left-aligned on y-axis
  - Preferred when category names are longer than 2 words
```

### Line Charts

```
  - Endpoint labels: Show value at the last data point (right end)
  - Start label: Show value at the first data point (left end) for context
  - Dense data (>7 points): Label only start, end, and notable peaks/valleys
  - Avoid: Labels on every point (creates clutter in video)
  - Legend: Top-right or inline (label next to the line) for multi-series
```

### Pie / Donut Charts

```
  - Large slices (>= 10%): Label INSIDE the slice (percentage + category)
  - Small slices (< 10%): Label OUTSIDE with leader line connecting to slice
  - Center of donut: Use for total value or key metric label
  - Maximum: 5-6 slices. Combine anything under 5% into "Other"
  - Always show percentages, not just raw values
```

### KPI Grid

```
  - Large number: Center of each card, using stat_card font (3-4x body size)
  - Label: Below the number, smaller font, describes the metric
  - Delta indicator: Small arrow + percentage showing change (green up, red down)
  - Grid: 2x2 or 3x2 layout, evenly spaced, consistent card sizing
```

### Universal Label Rules

- **Title visible:** Every chart must have a clear title (top-left or top-center)
- **Source citation:** If data is from an external source, show "Source: [name]" in small text at bottom
- **Units:** Always show units (%, $, seconds, etc.) either in the title or on the axis
- **No orphan labels:** Every visual element must be labeled or explained by the narration

## Data Density vs Readability

### The Video Rule: Less Is More

Video is not a spreadsheet. The viewer cannot pause, scroll, or zoom. Every data point
competes for attention in a 5-7 second window.

```
Ideal data points per chart type:
  Bar chart:     5-7 bars (max 9)
  Line chart:    5-12 points (max 15, but label sparsely)
  Pie chart:     3-5 slices (max 6)
  KPI grid:      3-6 metrics (max 6)
```

### Simplification Strategies

| Problem | Solution |
|---------|----------|
| Too many categories (>9) | Show top 5-7, aggregate rest into "Other" |
| Too many time periods | Aggregate (monthly -> quarterly, daily -> weekly) |
| Multiple metrics to show | Split into separate charts across scenes |
| Wide value ranges | Use normalized/percentage view instead of absolute |
| Decimal precision | Round aggressively: $1,234,567 -> $1.2M |

### Font Size Minimums (at 1080p)

These are non-negotiable for readability on screens including mobile:

| Element | Minimum Size | Recommended |
|---------|-------------|-------------|
| Chart title | 32px | 36-40px |
| Axis labels | 24px | 28px |
| Value labels | 24px | 28px |
| Annotations | 20px | 24px |
| Source citation | 16px | 18px |

**Scaling rule:** For 4K output, multiply by 2x. For 720p, these minimums still apply
(they are the floor).

## Color Usage

### Deriving Chart Colors from the Playbook

Charts must look like they belong to the video. Always derive colors from the active
style playbook.

```
Color derivation priority:
  1. playbook.visual_language.color_palette.chart_palette  (if the playbook defines one)
  2. Derive from primary + accent colors:
       - Bar/slice 1: primary[0]
       - Bar/slice 2: accent[0]
       - Bar/slice 3: primary[1]
       - Bar/slice 4: accent[1]
       - Bar/slice 5+: generate by adjusting lightness of primary[0]
  3. Background: use playbook background color
  4. Text/labels: use playbook text color
  5. Gridlines: use playbook muted color at 50% opacity
```

### Highlight and Focus

```
Highlighting strategy:
  - KEY data point:    Full saturation of accent[0], slight scale-up (1.05x)
  - FOCUS data points: Full saturation of their assigned color
  - NON-FOCUS points:  Desaturate to 30% opacity or use muted color
  - BASELINE/CONTEXT:  Dashed lines using muted color
```

### Accessibility Rules

Never rely on color alone to convey meaning:

- **Add patterns:** Use hatching, dots, or stripes on bars/slices in addition to color
- **Add labels:** Every bar/slice/line must have a text label, not just a legend
- **Contrast:** Minimum 3:1 contrast ratio between adjacent chart elements
- **Colorblind-safe:** Avoid red-green as the only differentiator. Prefer blue-orange or
  blue-yellow pairings when showing positive/negative

## Common Pitfalls

### Misleading Charts

| Pitfall | Why It Misleads | Fix |
|---------|----------------|-----|
| Truncated y-axis (not starting at 0) | Small differences look enormous | Always start bar chart y-axis at 0 |
| 3D charts | Perspective distorts size perception | Always use 2D flat charts |
| Dual y-axes with different scales | Implies false correlation | Use two separate charts side by side |
| Cherry-picked time range | Hides broader context | Show full relevant range or acknowledge truncation |
| Pie chart with too many slices | Impossible to compare small angles | Max 5-6 slices, aggregate rest |

### Animation Mistakes

| Pitfall | Fix |
|---------|-----|
| Animation too fast (< 1.5s) | Viewers cannot track what appeared. Minimum 2s build-up |
| No hold time after animation | Scene cuts away before chart is readable. Hold 3-5s minimum |
| All elements appear at once | Loses the narrative. Stagger element entrance |
| Gratuitous bouncing/spinning | Distracts from data. Use clean ease-in-out per playbook |

### Design Mistakes

| Pitfall | Fix |
|---------|-----|
| Too many colors (>5 in one chart) | Limit to 4-5 distinct colors. Aggregate or split charts |
| Missing title | Every chart needs a title. Viewers have no other context |
| Tiny font on mobile | Enforce minimums: 32px title, 24px labels at 1080p |
| Decorative gridlines | Use light gridlines or none. They should aid reading, not decorate |
| Dark text on dark background | Use playbook text color on playbook background. Check contrast |

## Integration with Scene Director

When the Scene Director identifies a data visualization need, apply this skill as follows:

1. **Determine chart type** using the decision tree above
2. **Specify animation pattern** in the scene's `movement` field (e.g., "build-up: bars grow from baseline over 2s, hold 4s")
3. **Include label specifications** in `overlay_notes` (e.g., "value labels above bars, title top-left, source bottom-right")
4. **Reference playbook colors** in `required_assets` description (e.g., "bar chart using primary[0] #2563EB for main bars, accent[0] #F59E0B for highlight bar")
5. **Set scene duration** to accommodate animation (2-4s) + hold (3-5s) = minimum 5s per chart scene

### Example Scene Specification

```json
{
  "id": "scene-7",
  "type": "animation",
  "description": "Horizontal bar chart comparing response times: Traditional DB 450ms, Vector DB 12ms, Cached 3ms. Bars grow left-to-right with stagger. Vector DB bar highlighted in accent color. Hold for readability.",
  "start_seconds": 32,
  "end_seconds": 40,
  "script_section_id": "s5",
  "framing": "full-screen chart, centered with generous padding",
  "movement": "build-up: bars grow from left over 2.5s with 0.3s stagger, hold 5s",
  "transition_in": "fade",
  "transition_out": "dissolve",
  "overlay_notes": "Title: 'Query Response Time Comparison'. Value labels right of bars (ms units). Source: 'Benchmark 2024' bottom-right 16px. Vector DB bar uses accent[0], others use primary[0] at 50% opacity.",
  "required_assets": [
    {
      "type": "chart_data",
      "description": "Horizontal bar chart data: Traditional DB 450ms, Vector DB 12ms, Cached 3ms. Use playbook primary #2563EB at 50% for context bars, accent #F59E0B for Vector DB highlight bar.",
      "source": "generate"
    }
  ]
}
```

## Quality Checklist

- [ ] Chart type matches the data story (not just "default to bar chart")
- [ ] Data points within limits: 5-7 bars, 3-5 pie slices, 5-12 line points
- [ ] Animation duration: 2-4s build, 3-5s hold minimum
- [ ] All text meets size minimums: 32px title, 24px labels at 1080p
- [ ] Colors derived from active playbook palette
- [ ] Key data point has visual emphasis (highlight color, scale, or annotation)
- [ ] No reliance on color alone for meaning (labels + patterns for accessibility)
- [ ] Y-axis starts at 0 for bar charts
- [ ] No 3D effects or perspective distortion
- [ ] Title is visible and descriptive
- [ ] Source cited if using external data
- [ ] Chart is readable when paused at any frame during the hold period
