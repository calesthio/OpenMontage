# Chiling Workbench A+ Design Spec

## Goal

Upgrade the existing Chiling Web workbench with an A+ approach: keep the current static app and Worker/API bridge stable, while making the frontend easier to extend, safer to test, and closer to the approved v5 product direction.

The outcome should be a production-friendly static Web workbench that preserves the current login, dashboard, create, review, generation feedback, delivery, queue, production service, audit, and task detail flows.

## Decision

Use A+: progressive hardening of the existing `web/chiling-workbench` implementation.

Do not rewrite to React/Vite in this phase. A rewrite would improve component ergonomics later, but it would also force the existing Worker/API state flow, QA screenshots, and local static deployment path through a larger migration. The current priority is stability plus maintainable second development.

## Current System

The current app is a static frontend:

- `web/chiling-workbench/index.html` hosts the app shell.
- `web/chiling-workbench/app.js` owns page rendering, route state, local form state, polling, review actions, production actions, and drawer state.
- `web/chiling-workbench/api-client.js` provides a remote API adapter and localStorage fallback.
- `web/chiling-workbench/styles.css` implements the v5-like visual system.
- `web/chiling-workbench/worker.py` can serve the frontend and expose local task APIs.

The app already has substantial behavior. The A+ work should preserve that behavior and reduce the risk of regressions.

## Scope

In scope:

- Preserve static deployment with no build step.
- Keep `worker.py` and the existing API route contract intact.
- Split `app.js` into focused modules for state, routing, rendering helpers, page views, actions, and polling.
- Split or organize CSS around design tokens, layout primitives, components, and page-specific sections.
- Keep the approved v5 visual direction: light system, generous spacing, quiet status feedback, low decoration, and clear hierarchy.
- Add focused tests for module behavior and API-safe UI flows where practical.
- Add browser or scriptable smoke coverage for the core workflow.
- Keep paid generation gated by existing approval and backend/worker controls.
- Keep provider names, model names, API keys, command paths, and internal pipeline details out of user-facing UI.

Out of scope:

- React/Vite migration.
- New authentication backend.
- New paid generation execution path from the browser.
- Provider credential input in the frontend.
- Large visual redesign beyond aligning the current app with v5.
- Replacing `worker.py` with a new service framework.

## Architecture

The static app should move from one large `app.js` file toward a module layout:

```text
web/chiling-workbench/
  index.html
  app.js
  api-client.js
  config.js
  styles.css
  worker.py
  src/
    state.js
    router.js
    format.js
    dom.js
    actions.js
    polling.js
    views/
      login.js
      dashboard.js
      create.js
      review.js
      generating.js
      delivery.js
      works.js
      library.js
      data.js
      detail-drawer.js
    components/
      topbar.js
      buttons.js
      panels.js
      task-list.js
      progress.js
      status.js
```

This can be implemented with browser-native ES modules, keeping the app buildless. `index.html` should load `app.js` as a module after `config.js` and `api-client.js`, or `app.js` can import modules and continue to expose only the minimum globals needed by inline event handlers until handlers are migrated.

## Data Flow

The data flow should remain intentionally boring:

1. UI event updates local state.
2. Action function calls `window.ChilingTaskApi`.
3. API client chooses remote Worker/API when configured, otherwise localStorage mock mode.
4. State refreshes from returned task/queue/detail data.
5. Render functions produce safe escaped HTML.
6. Polling updates current task progress and deliverables.

No UI module should call paid generation providers directly. UI modules may request backend/worker operations only through the existing safe action endpoints.

## Rendering Rules

- User-controlled values must pass through escaping helpers before rendering.
- Page modules should return strings or DOM fragments through shared helpers, not mutate global state directly.
- Buttons should use explicit action handlers rather than inline duplicated logic.
- Repeated UI patterns should use shared components: topbar, panels, buttons, status chips, task rows, progress rings, drawers, and section lists.
- Empty, loading, blocked, and failed states must be visible and user-readable.

## CSS System

Keep one CSS entrypoint for now, but organize it into clear sections:

1. Design tokens
2. Reset and base typography
3. Layout primitives
4. Shared components
5. Page-level views
6. Responsive rules

The v5 direction remains the target: system fonts, white/light gray surfaces, restrained red/blue/green/amber semantic color, soft borders, soft shadows, and low-motion feedback.

Cards should be purposeful panels, not nested decorative containers. Controls need stable dimensions so labels, loading states, and dynamic content do not shift layouts.

## Responsive Target

The current app has a desktop-oriented minimum width. A+ should add a clear responsive baseline:

- Desktop: maintain the current dense workbench layout.
- Tablet/small laptop: collapse side-by-side panels into two-column or stacked panels without overlap.
- Mobile: prioritize readable single-column flows for login, create, review, generating, and delivery. Production/admin data views can be compact lists rather than full dashboards.

Text must not overlap controls or media previews at any supported viewport.

## Error Handling

API and Worker errors should surface as user-readable toasts and inline blocked states.

Required states:

- Login or local app entry succeeds without backend.
- Task submit failure leaves the user on the current screen with form data intact.
- Worker/API failure shows a retryable message.
- Production service disabled/missing/ready states remain user-safe.
- Paid generation remains visibly gated and never starts from a browser-only action.

## Testing

Use focused verification before and after refactors.

Recommended tests:

- Existing `tests/scripts/test_chiling_worker_bridge.py` smoke coverage.
- JS syntax/module import checks using the available runtime.
- Unit-style checks for pure helpers such as clamping, subtitle normalization, task labels, and state derivation.
- Browser smoke for login -> create -> review -> confirm -> generating -> delivery using local mock mode where possible.
- Worker HTTP smoke when sandbox/local permissions allow binding a port.

Each module split should keep behavior green before the next split starts.

## Migration Plan Shape

Implement in small commits:

1. Add tests around current behavior and helpers.
2. Extract pure helpers with no UI changes.
3. Extract state/router/action boundaries.
4. Extract shared components.
5. Extract page views.
6. Reorganize CSS and responsive rules.
7. Run visual/browser QA against v5 mockups.

Avoid one big rewrite. Each step should leave the app runnable.

## Acceptance Criteria

- The app still runs as a static local page and through `worker.py`.
- Existing user flows remain available.
- The Worker/API contract remains compatible with current documented endpoints.
- UI does not expose provider secrets, provider names, model names, internal commands, or paid generation internals.
- The codebase has smaller, named frontend modules rather than one hard-to-extend app file.
- v5 visual direction is preserved or improved.
- Desktop and mobile screenshots show no obvious overlap, clipped controls, or unreadable text.
- Targeted tests and smoke checks pass.

## Risks

- Splitting `app.js` can accidentally break global event handlers.
- Browser-native ES modules require careful script loading order.
- A static module architecture is less ergonomic than React once state interactions become very complex.
- Mobile support may reveal layout assumptions in existing CSS.

Mitigation: split incrementally, keep compatibility wrappers during migration, and verify after each step.
