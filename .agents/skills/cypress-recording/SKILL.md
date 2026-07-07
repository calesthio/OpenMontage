---
name: cypress-recording
description: Turn a Cypress spec into a polished tutorial video of a real web app. Use when the user wants to record a walkthrough of an app they already drive with Cypress, add AI voiceover + captions + intro/outro, and (optionally) render it on a k8s worker. Analogous to playwright-recording but authored in Cypress spec language, with narration reused from an existing ttsd sidecar.
---

# Cypress → tutorial video

Author the walkthrough as a Cypress `*.tutorial.cy.js` spec; the pipeline records
it cleanly, narrates it, captions it, and assembles a finished MP4. Two phases:

- **Author (local, once per tutorial):** write the spec + a `*.tutorial.json`
  recipe, then run `author_tutorial.py` to generate the committed `*.timings.json`
  (per-step narration durations, so the capture holds long enough for each line).
- **Render (repeatable, no LLM):** `render_tutorial.py` re-captures with Cypress
  and assembles the video deterministically. This is exactly what the k8s worker
  runs; because narration is content-addressed cached, re-renders are free/stable.

## Components

| Piece | Where | Role |
|---|---|---|
| `cypress.tutorial.config.js` | client repo | video-on config; writes a step manifest sidecar; hides the Command Log; forces 1:1 pixels |
| `cypress/support/tutorial.js` | client repo | `cy.tutorialStep()` — pacing, synthetic cursor, drift marker, bbox capture |
| `*.tutorial.cy.js` / `*.tutorial.json` | client repo | the walkthrough + its render recipe |
| `ttsd` sidecar | circuit-bid | `POST /render {lang,text} → wav + X-Duration-Ms`, reusing the ElevenLabs narration core |
| `author_tutorial.py` | OpenMontage | collect steps → TTS durations → `*.timings.json` |
| `render_tutorial.py` | OpenMontage | capture → normalize → narrate → caption → cards → `renders/final.mp4` |
| `tools/capture/cypress_bridge.py` | OpenMontage | run spec, `normalize_capture` (marker anchor + crop/pad), seed |
| `tools/audio/narration_client.py` | OpenMontage | ttsd HTTP client |
| `lib/tutorial.py` | OpenMontage | steps, synthetic caption segments, title cards, edit_decisions |

## Recipe (end to end)

1. **Prereqs.** A **dedicated, resettable demo environment** (recording mutates
   state and the dev-only test-token route must not exist on production) and the
   **`ttsd`** sidecar running (`ddev` compose locally; a pod sidecar in k8s).
   Reset/seed with the client's `npm run cy:seed`.
2. **Author the spec** in `cypress/e2e-tutorials/<area>/<name>.tutorial.cy.js`.
   Wrap each viewer-visible beat in `cy.tutorialStep(narration, {target, action})`
   before the real command. Reuse `cy.loginWithToken()`, `cy.visitState()`,
   `data-testid`/`#state-*`. Add a `<name>.tutorial.json` recipe
   (`title`, `lang`, `intro_text`, `outro_text`, `music_track`, `subtitle_style`).
   Prefer read-only tours first.
3. **Generate timings:**
   `python author_tutorial.py --tutorial <name> --client-dir <client> [--base-url <demo>]`
   → writes `<name>.timings.json` (commit it).
4. **Render:**
   `python render_tutorial.py --tutorial <name> --client-dir <client> --base-url <demo> --project-id <id>`
   → `projects/<id>/renders/final.mp4`. Use `--offline-narration` to assemble with
   silent placeholder audio (no ttsd) when validating the visual/assembly path.
5. **Inspect** the render on the Backlot board or with `ffprobe` (1920×1080,
   duration ≈ intro + body + outro).

## How timing stays in sync (important)

- Cypress records via CDP screencast at **variable FPS**, so wall-clock → video
  time drifts. `cy.tutorialStep` flashes a thin magenta **drift marker** at the
  top of the app on each step; `normalize_capture` re-encodes to constant FPS,
  finds each marker's true video time, then **crops the marker strip away** and
  letterboxes to 1080p. Narration and captions are placed at those recovered
  times. If markers can't be read, it falls back to the manifest `t_ms` (less
  precise — validate on a 3–5 min spec).
- Each step is **held** for `max(pacingBeat, tts_duration + margin)` using the
  committed `timings.json`, so narration never overruns into the next step.

## Notes / gotchas

- Set `CYPRESS_NO_COMMAND_LOG=1` (the `cy:tutorial*` npm scripts do) so the frame
  is app-only. The ffmpeg crop in `normalize_capture` is a fallback if the
  reporter still appears.
- Captions are built from the **authored narration text + per-step duration**
  (synthetic word timings) — no transcriber/Whisper/torch. The ttsd narration core
  emits no word timestamps.
- Two render runtimes (`render_tutorial.py --render-runtime`):
  - `remotion` (worker default) — the `screencast_scene` Explainer composition:
    animated callouts/zoom tracking each step, word-highlight captions, hero
    intro/outro. Needs `remotion-composer/node_modules` (`npm install`, or the
    worker image built with `INSTALL_REMOTION=true`).
  - `ffmpeg` — a self-contained assembly (reusing `subtitle_gen` for the SRT and
    `audio_mixer` for ducking): clean body + burned captions between title cards.
    No Node needed; the always-works fallback.
  Both emit `artifacts/remotion_props.json` + a schema-valid `edit_decisions`.
- This is a deliberate deterministic re-render of a locked recipe (see the Rule
  Zero note in the plan); the creative pipeline still runs through the agent when
  authoring.
