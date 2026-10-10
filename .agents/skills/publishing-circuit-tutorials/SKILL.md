---
name: publishing-circuit-tutorials
description: Use when asked to make, render or publish a Circuit backoffice tutorial video for a GitHub issue or PR number, add a tutorial video to the circuitauction-docs site, or add a feature with its video to the latest release notes.
---

# Publishing Circuit tutorials from an issue

One GitHub issue/PR number in → a narrated 1080p video on S3, a docs page, and a
release-note entry out. Four repos take part; nothing is invented along the way:
the video is a Cypress walkthrough of the real app, the docs embed its public URL.

**Every tutorial records against the local demo database** (ddev site with the
demo DB loaded; fake clients only). Never a production URL. For a feature that
is still on a branch, record against the ddev site that has that branch deployed.

**REQUIRED BACKGROUND:** `.agents/skills/cypress-recording/SKILL.md` (how a spec
becomes a video) and `.agents/skills/circuit-video/SKILL.md` (the MCP tools).

## Where things live

| Piece | Path |
|---|---|
| Feature source, PR | `gh pr view <n> -R Gizra/circuitauction-backoffice --json title,body,files`; `.fixer/issue-<n>-plan.md` on the branch when github-fixer wrote it |
| Tutorial spec + recipe + timings | `circuitauction-backoffice/client/cypress/e2e-tutorials/release-<X.Y>/<name>.tutorial.cy.js`, `<name>.tutorial.json`, `<name>.timings.json` (generated, committed) |
| Element ids to target | `client/app/views/**.html` (`data-testid`, `id`); the PR's own `client/cypress/e2e/**.cy.js` tests show the flow and selectors |
| Renderer / MCP | OpenMontage `mcp_servers/circuit_video` (tools `doctor`, `render_tutorial`, `upload_video`, `author_tutorial`); CLIs `author_tutorial.py`, `render_tutorial.py` |
| Video storage (public) | `s3://circuit-kubernetes/openmontage/tutorials/release-<X.Y>-<name>/final.mp4` → `https://circuit-kubernetes.s3.eu-central-1.amazonaws.com/openmontage/tutorials/release-<X.Y>-<name>/final.mp4` |
| Docs site (docsify) | `circuitauction-docs/`: pages `*.md` + `_sidebar.md` + `SUMMARY.md`; release notes `release-notes/version-<X.Y>.md` and `release-notes/README.md` |

## Recipe

1. **Read the feature.** PR title/body/files, the fixer plan, the PR's Cypress test, the views. Decide the 6–10 viewer-visible beats and the account/data they need from the demo DB (`MAINTAINING_DOCS.md` in the docs repo lists the demo fixtures: sale 792, client 12, consignment 827, staff user `staff`/`staff`). Need data the fixtures lack? Look for it first (`ddev drush sql-query "SELECT …"` on the demo site); if none exists, seed it with an idempotent statement that the spec's `TUTORIAL_PRE_RUN` runs every time (step 4), never by hand. A beat that cannot be shown on the demo site is left out of the video and covered by a release-note bullet instead.
2. **Check the environment.** MCP `doctor` must be `ready`. Two local ddev sites exist, both with the demo DB: `backoffice` (`https://backoffice.ddev.site:9010`, mainline) and `backoffice2` (`https://backoffice2.ddev.site/app`, the branch under test). `base_url` is whichever site runs the feature's code. The spec file lives in the `circuitauction-backoffice` client checkout; switch that checkout to the PR branch (`git -C circuitauction-backoffice switch <branch>`) when the spec needs the PR's `data-testid`s, and say so. Draft or unmerged PRs are fine to record from `backoffice2`; note the branch in the recipe `notes`.
3. **Write the spec** `<name>.tutorial.cy.js` next to the other `release-<X.Y>` specs. One `it()`, each beat as `cy.tutorialStep(narration, {target, action, importance})` *before* the real command. Copy `_demo.js` helpers (`loginDemo`) when the flow starts logged in; drive the real login form (`#username`, `#password`, `#login`) when the login itself is the feature. Narration = spoken line = caption: short, present tense, first line says "New in version X.Y: …", last line ends "Thanks for watching!".
4. **Make the run repeatable.** If a beat mutates the account or data (activating 2FA, creating a record), reset it in `before()` via `cy.exec(Cypress.env("TUTORIAL_PRE_RUN"))` and document the exact `ddev drush sql-query …` in the spec header; export `CYPRESS_TUTORIAL_PRE_RUN` for both the authoring and the render run. Secrets the flow needs (a TOTP code, a token) are computed in-browser or fetched from the demo site, never hardcoded from production.
5. **Write the recipe** `<name>.tutorial.json`: copy a sibling (`title`, `lang`, `intro_text` "What's new in X.Y", `intro_subtitle` = feature, `outro_text`, `subtitle_style`, `notes` with the demo account used).
6. **Author timings** (synthesizes each line once, measures durations):
   `python author_tutorial.py --tutorial <name> --client-dir <client> --base-url <base_url>`
   → `<name>.timings.json`. Re-run after any narration edit. Commit spec + recipe + timings in the client repo.
7. **Render + upload** via the MCP: `render_tutorial(tutorial=<name>, base_url=<base_url>, project_id="release-<X.Y>-<name>", upload=true)`. The S3 key is derived from `project_id`, so the id **is** the public URL. (If a render used another id, re-publish with `upload_video(file_path, key="openmontage/tutorials/release-<X.Y>-<name>/final.mp4")`.) Verify `curl -I` on the public URL returns 200.
8. **Verify the video** before touching docs: `ffprobe` duration ≈ intro 3 s + sum of timings + outro 3 s; extract 3–4 frames (`ffmpeg -ss <t> -frames:v 1`) at the manifest step times and look at them: right page, captions readable, no error toast, no login screen where a feature page should be.
9. **Docs page.** New `<topic>.md` in the sidebar section the feature belongs to (`client/`, `items/`, `sale/`, `consignment/`, `bids/`, `data-migration/`, `website/`; top level for login, tasks and system-wide topics), opening with one paragraph, then the embed:
   `<video class="release-video" controls preload="metadata" playsinline src="<public URL>">Your browser does not support the video tag. <a href="<public URL>">Download the video</a>.</video>`
   then numbered steps mirroring the narration, a "For administrators" section when there is a setting, and a *See also* link. Add the page to **both** `_sidebar.md` and `SUMMARY.md` next to its neighbours; cross-link from the related existing page.
10. **Release notes.** In `release-notes/version-<X.Y>.md` add `### <Feature>` under the `##` area of the page the user opens to use it (Reports & Statistics / Invoices & Emails / Tasks & Support / Sales & Bids / System; a feature touching several areas goes under the one shown in the video) with the same `<video>` embed, 3–5 bullets, and a link to the docs page; mention the feature in the version's intro sentence and in the one-line summary in `release-notes/README.md`. "Latest release notes" = the highest `version-*.md`, marked *upcoming* until released.
11. **Commit** in each repo (client: spec/recipe/timings; docs: page + nav + notes). Pushing the docs repo publishes the site: say so and let the user push.

## Quick checks

- `doctor` not ready → fix `.env` (`TUTORIAL_CLIENT_DIR`, `TUTORIAL_BASE_URL`, narration keys) before anything else.
- Second recording shows a different screen than the first (e.g. a code prompt instead of the setup page) → the flow mutated state; add the `TUTORIAL_PRE_RUN` reset.
- Narration ahead of the picture by more than ~2 s → put the `cy.get(...).should("be.visible")` wait *before* the `tutorialStep` that describes that screen.
- Video URL 403 → the object is outside `openmontage/tutorials/` or the key is not `release-<X.Y>-<name>`; re-upload with `upload_video(key=…)`.
- Other languages: `get_tutorial_text` → `save_tutorial_translation` → `author_tutorial(lang)` → `render_tutorial(lang)`; the docs page then embeds `release-<X.Y>-<name>-<lang>` only if rendered with that `project_id`.

## Common mistakes

- Writing the spec from the PR description alone: open the views and the PR's test for real selectors.
- Rendering before `author_tutorial.py`: the capture is then not paced to the narration (steps cut off).
- Using a presigned URL from the render result in the docs: it expires in 24 h; use the public URL pattern.
- Forgetting `SUMMARY.md` (sidebar only) or the README one-liner in release notes.
- Leaving the demo account mutated (2FA activated, records created) without a documented reset.
