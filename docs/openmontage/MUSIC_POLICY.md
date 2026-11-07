# Music Policy — OpenMontage (Milestone D1)

**Status:** policy decision, docs only. No music files added, no downloads, no keys.

## 1. Default: no music

The pilot uses **NO music unless license evidence is stored**. Silence is an acceptable and
recorded delivery (the P1 pilot shipped silence, decision d-003). A track is added to a render
only when every field in §3 is present and the license permits the intended use (commercial
inclusion + monetization, where applicable).

## 2. Allowed sources

Only sources whose license terms can be verified from the source's own license text/page are
eligible. Candidate classes (none yet cleared for this pilot):

- **YouTube Audio Library** — tracks with a clear, commercially usable license; record the
  license shown on the track page.
- **Archive.org / Wikimedia Commons / NASA media** — only items carrying an explicit license
  field; "none stated" counts as NOT licensed (fail-closed, per master plan §6 / viability
  probe §6). NASA media is generally public domain *except where the page says otherwise*
  (logos and likenesses have separate rules).
- **Openverse / ccMixter / Freesound** — only items stating a Creative Commons license; CC
  BY-NC / NC variants bar commercial derivatives and are **not** eligible unless the use is
  non-commercial.
- **Pexels / Pixabay** — free-to-use licenses (no credit required), but files may not be sold
  as-is; API access requires a key (not configured — key-gated sources are optional extras,
  not required for the default path).

A source is **not** eligible merely because it is labelled "royalty-free" — that label alone
does not mean CC0 or commercially clear.

## 3. Required record fields (per track)

Every music track used must carry a stored record with all of:

| Field | Requirement |
|---|---|
| `source_url` | Exact URL the track was obtained from |
| `license_text` | Full license text (verbatim) or a stable URL to it |
| `author` | Rights holder / creator as stated by the source |
| `download_date` | ISO-8601 date the file was retrieved |
| `sha256` | SHA-256 of the audio file as it entered the project |
| `commercial_use_allowed` | Boolean; must be `true` for a monetized YouTube delivery |
| `modification_allowed` | Boolean (editing, ducking, trimming) |
| `attribution` | Exact attribution text the license requires (or "none required") |
| `license_url` | URL of the license text / provider terms checked |

If any field is missing or unverifiable, the track is **not used** (fail-closed).

## 4. Content ID risk

**Content ID risk: UNKNOWN.** No YouTube Content ID scan was run, no claim history was
checked, and no monetization eligibility was verified. A track that is license-clear is not
necessarily Content ID-clear. Treat every added track as a potential Content ID match until
cleared by the platform.

## 5. Where the record lives

Store the per-track record alongside the audio file in `projects/<run>/assets/music/` and
reference it from `edit_decisions.audio.music.asset_id` plus `music_credit` in the publish
package (`schemas/artifacts/publish_package.schema.json`). The publish package's
`sources_credits[]` must carry `provider`, `original_url`, `license`, `author`, `attribution`
for every asset, matching the asset manifest provenance.

## 6. Decision log

The music decision (use / silence / specific track) is recorded as a decision-log entry
(`category: "music_selection"`) at proposal, and revisited at the `assets` gate. No music was
used in the P1 pilot (silence, decision d-003).
