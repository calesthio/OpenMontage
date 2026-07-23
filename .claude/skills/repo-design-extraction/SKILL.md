---
name: repo-design-extraction
description: Extract a design system and UI inventory from a product's source-code repository (React/Next/Vue/Tailwind web frontends). Use in the product-motion pipeline's repo_analysis stage, or whenever a video must be grounded in a repo's real design tokens rather than a live URL. Produces the schema-validated design_system and ui_inventory artifacts with per-token provenance.
license: MIT
compatibility: No API keys. Optional `node` on PATH improves tailwind config evaluation.
metadata: {"openclaw": {"requires": {"env": []}}}
---

# Repo Design Extraction

Turn a product's **source repository** into two grounded artifacts:

1. **`design_system`** (`schemas/artifacts/design_system.schema.json`) — tokens
   (colors, typography, spacing, radii, shadows, glass) where **every value
   cites the repo file it was read from**.
2. **`ui_inventory`** (`schemas/artifacts/ui_inventory.schema.json`) — the
   screens and components that exist, each with `source_files` and
   `reviewed: true` (the inspected-not-assumed contract).

This is the source-code sibling of `website-to-video`'s URL capture
(`step-1-design.md`): same brand-truth goal, but grounded in the repo's own
configs and component source instead of computed CSS from a live page.

## The governing rule — read, don't invent

A value goes in `tokens` only if you **read it in the repo**. Anything you
derive (a glass spec composed from the palette, a spacing scale inferred from
usage) is marked honestly: glass gets `derived: true` + `rationale`; everything
else goes in `gaps[]` with `how_inferred`. A design_system whose tokens can't
be spot-checked against their cited files is a defect, not a draft.

## Process

### Step 1 — Run the scanner first

```python
from tools.tool_registry import registry
registry.discover()
scan = registry._tools["repo_design_extractor"].execute({
    "repo_path": "/path/to/product-repo",
    "output_path": "projects/<project-id>/artifacts/repo_scan_report.json",
})
```

The scan report gives you: `framework`, `styling_systems`, `candidate_files`
(tailwind configs, `:root`/`@theme` CSS, theme modules, app shells),
`css_custom_properties` (name/value/**file/line**), `tailwind_theme` (JS
configs evaluated via node; `null` for TS configs — read those yourself),
`fonts`, `screen_candidates` (with routes), and `components_index`.

If `truncated: true`, say so — a partial scan silently presented as complete
violates the no-silent-caps rule.

### Step 2 — Read the flagged files

The scanner locates; you interpret. Read every `candidate_files` entry plus the
top screen candidates. Framework-specific guides:
**`references/design-system-authoring.md`** (tokens) and
**`references/ui-inventory-authoring.md`** (screens/components).

### Step 3 — Author `design_system`

- Assign **semantic roles** (primary / surface / text-muted / card-radius…)
  from how tokens are *used* in components, not from name guessing.
- Copy hex/size values **verbatim** — no rounding, no "close enough".
- Provenance: prefer the scanner's file+line for CSS vars; for tailwind config
  values use `key` (e.g. `theme.extend.colors.brand`).
- Record the repo's `git_commit` (`git -C <repo> rev-parse HEAD`) when available.
- Derive the glass spec last (see the authoring reference) — it is almost
  always `derived: true`.

### Step 4 — Author `ui_inventory`

Walk `screen_candidates`, read each screen's source, list its real
`ui_elements` **with their actual label text from the JSX/template**. Score
flagship candidates (see reference) and write `flagship_recommendations` —
these are what the user approves at the repo_analysis gate.

### Step 5 — Validate and checkpoint

```python
from schemas.artifacts import validate_artifact
validate_artifact("design_system", design_system)
validate_artifact("ui_inventory", ui_inventory)
```

Write both into the `repo_analysis` checkpoint (`design_system` is canonical,
`ui_inventory` supplementary) and present: the design read in one paragraph,
the token table with provenance, the flagship screen recommendations, and the
`gaps[]` ledger — then wait for approval.

## Anti-patterns

- Filling a palette from the product's marketing site instead of the repo
  (that's `website-to-video` — a different grounding; never mix silently).
- Inventing tokens "every design system has" (a warning color the repo lacks).
- `ui_elements` labels like "Submit button" when the source says `Create
  workspace` — labels are evidence, copy them exactly.
- Listing a screen without having opened its source file (`reviewed: true` is
  a contract, not a formality).
- Hiding a thin design system. If the repo has 4 CSS vars and default Tailwind,
  the design_system is *small* — say so and lean on `component_styles` +
  `gaps[]`, don't pad it.
