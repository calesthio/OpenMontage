# Authoring `ui_inventory` from repo sources

How to turn the scanner's `screen_candidates` / `components_index` into the
`ui_inventory` artifact. The contract: **every screen listed was actually
read** (`reviewed: true`), and every `ui_elements[].label` is the element's
real text from the source.

## Walking screens

- **Next app router** (`app/**/page.tsx`): the scanner derived the route from
  the directory. Read the page *and* the components it imports — the page file
  is often just a shell; the real UI lives one import away. Add those files to
  `source_files` too.
- **Next pages router / Vue pages**: same, route from file path.
- **Non-routed roots** (`src/views`, `src/screens`, `src/features`): treat
  each top-level view as a screen; leave `route` unset unless a router config
  says otherwise.
- Skip auth walls, error pages, and legal pages unless the brief asks for
  them — they are rarely flagship surfaces.

## Recording ui_elements

For each screen list the elements that would *assemble* in an animation —
forms, inputs, buttons, cards, tables, charts, navs, badges, avatars, toggles,
tabs, modals. Rules:

- `label` is the **visible text in the source**: the button's children, the
  input's label/placeholder, the card's title. Copy exactly (`"Create
  workspace"`, not "CTA button").
- `source_file` is where the element's markup lives (the component file, not
  the page that imports it, when they differ).
- Dynamic content (`{user.name}`, mapped rows): describe the shape —
  `label: "invoice rows (date, amount, status badge)"`.
- 5–12 elements per screen is the useful range. The elements you list become
  the build-order beats in scene planning — inventory what would animate, not
  every div.

## Shared components (`components`)

Promote a component out of a screen into `components[]` when it appears on
multiple screens or is individually animation-worthy (a stat card, a nav item,
a form field group). `used_by_screens` links it back.

## Flagship scoring

Score each screen for `flagship_recommendations` on:

1. **Visual richness** — number and variety of animatable elements.
2. **Story value** — does it show the product's core promise (the dashboard,
   the editor), or is it plumbing (settings)?
3. **Form presence** — the brief wants forms/UI assembling; a screen with a
   real form (labels, fields, a submit) is a strong candidate.
4. **Replica feasibility** — a screen of custom canvas/WebGL is hard to
   replicate truthfully; prefer DOM-built surfaces.

Recommend 3–5 screens with one-line `why` each. The user picks at the
repo_analysis gate — recommendations are input, not decisions.

## planning_implications

Concrete, actionable, ≥1. Good examples:

- "Dashboard uses a 3-column card grid — the hero scene should assemble cards
  into that grid, not invent a new layout."
- "All CTAs are `--primary` filled buttons with 8px radius — replicas must not
  use outline buttons."
- "The onboarding form at /signup has 4 fields + OAuth buttons — natural
  assembly sequence for the form scene."
- "Product ships dark mode by default (`.dark` on html) — the video should be
  dark-first."
