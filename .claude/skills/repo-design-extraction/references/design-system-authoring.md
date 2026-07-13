# Authoring `design_system` from repo sources

Framework-specific reading guides and token-distillation rules. The scanner
(`repo_design_extractor`) has already located the files; this is how to read
them.

## Where tokens live, by styling system

### Tailwind v3 (`tailwind.config.{js,ts,cjs,mjs}`)

- Scanner evaluates JS configs into `tailwind_theme`; **TS configs come back
  `null` — read the file yourself** and extract `theme` / `theme.extend`.
- `theme.extend.*` **extends** defaults; a color under `extend.colors` is a
  brand token. A full `theme.colors` (no extend) **replaces** defaults — then
  the listed palette is the entire palette.
- Values referencing CSS vars (`"hsl(var(--primary))"`, common in shadcn/ui)
  mean the *real* value lives in the CSS `:root` block — resolve through and
  cite the CSS file+line as provenance, noting the tailwind key in `role`.
- Provenance for config values: `{file: "tailwind.config.ts", key: "theme.extend.colors.brand"}`.

### Tailwind v4 (CSS-first `@theme`)

- No JS config. Tokens are CSS custom properties inside `@theme { ... }`
  blocks (scanner flags these files as `theme_css` and parses the vars).
- Namespaced conventions: `--color-*`, `--font-*`, `--radius-*`, `--shadow-*`,
  `--spacing-*` — the namespace gives you the token category for free.

### Plain CSS custom properties (`:root`)

- The scanner's `css_custom_properties` list is authoritative (file+line).
- Watch for **dark-mode duplicates** (`.dark { --background: ... }`,
  `@media (prefers-color-scheme: dark)`): record both values when present —
  the video should match the mode the product actually ships as default.

### styled-components / Emotion

- Look for a `ThemeProvider` theme object (scanner flags `theme_source` files
  by name; also grep for `createGlobalStyle` and `ThemeProvider`).
- The theme object's keys are your token names; provenance `key` is the object
  path (e.g. `theme.colors.primary`).

### Vue / Nuxt SFCs

- Global tokens usually live in `assets/css/*.css` or a `styles/` dir
  (`:root` vars — scanner catches these).
- Component-scoped `<style scoped>` blocks hold per-component styling — use
  them for `component_styles`, not global tokens.

## Typography

- **next/font imports** (scanner's `fonts` with `source: "next/font"`) are the
  ground truth for Next apps — include weights from the import options if
  specified in the source.
- `@font-face` families: cite the CSS file; note the font *files* exist in the
  repo (the replica build can reference them via `public_dir`).
- Type scale: read the heading/body styles actually used on flagship screens
  (Tailwind classes like `text-4xl font-semibold tracking-tight` are scale
  evidence — resolve them to concrete values via the Tailwind defaults or the
  config overrides, and cite the component file that uses them).

## Component styles

For each button/input/card variant on a flagship screen, record a
`css_summary` condensed from the actual classes/styles, e.g.:

```json
{
  "variant": "primary button",
  "css_summary": "bg --primary, text white, radius 8px (rounded-lg), px-4 py-2, shadow-sm, hover:bg-primary/90, text-sm font-medium",
  "provenance": {"file": "components/ui/button.tsx", "line": 12}
}
```

Copy class lists faithfully — they are what the replica must reproduce.

## Deriving the glass spec (`tokens.glass`)

Most products have no frosted surfaces; the glass panels are the *video's*
staging device, themed by the product's palette. Standard derivation:

- `background`: the primary or surface color at 6–12% alpha
  (`rgba(99,102,241,0.08)`)
- `backdrop_blur`: 16–28px
- `border`: `1px solid` white (dark video bg) or the text color (light bg) at
  10–16% alpha
- `highlight`: optional 1px top-edge stroke at ~2x the border alpha
- Set `derived: true` and write the `rationale` ("composed from --primary and
  --background; product has no glass surfaces").
- If the product *does* use `backdrop-filter` anywhere, that's real
  provenance — cite it and set `derived: false`.

Every derived value that isn't the glass spec goes in `gaps[]`:

```json
{"token": "spacing scale", "how_inferred": "no explicit scale; inferred 4/8/12/16/24 from usage frequency in app/page.tsx"}
```
