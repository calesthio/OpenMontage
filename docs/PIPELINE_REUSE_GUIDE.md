# Pipeline reuse guide (future episodes)

The channel is a series, not a one-off. This doc records what is reused
automatically, what must be changed by hand for a new topic, and how to
spin up a new episode folder.

## Reused automatically (no per-topic edits)

- `lib/color_match.py` — `profile_for(source_type, scene_id, ...)` accepts
  overridable `dark_space`/`bright_ice`/`deep_sea` scene sets (pilot
  first_video defaults preserved). Call `grade(input, output, filter)` for
  any frame/video.
- `lib/footage_sourcing.py` — `search_nasa`/`search_archive_org`/
  `search_wikimedia`/`search_pexels`/`search_pixabay` take a free-text
  query; `write_manifest(entries, path)` writes any rights manifest.
- `tools/qa/qc.py` — thresholds come from `config/qc_thresholds.json` plus
  `DEFAULT_THRESHOLDS`; fail-closed, no pilot file names hardcoded.
- `scripts/new_episode_scaffold.py` — creates `projects/pilot/<slug>/`
  with `images/`, `audio/`, `qc/`, `manifests/`, `script/`, `footage/`,
  `prompts/` modeled on `projects/pilot/first_video/`.

## Must be changed by hand per new topic

- Topic, title, description, tags, category, language — `metadata.json`.
- Narration script with S-codes — `script/<episode_script>.md`.
- Subtitles with timecodes — `subtitles_*.srt` (compact, bottom-placed).
- Per-scene image prompts — `prompts/S###.txt` + `prompts.json`.
- AI-disclosure corner splash text and subtitle styling — set in the
  per-episode assemble script (`scripts/assemble_pilot_final*.py` passes
  metadata/subtitle paths as arguments; not yet a single shared template).
- Background music track + license — `assets/music/` + `manifest.json`.
- QC threshold tuning for the new topic's loudness/duration profile.

## New episode workflow

```
python scripts/new_episode_scaffold.py "<topic>"   # creates projects/pilot/<slug>/
# add images/, audio/, script/, prompts/, manifests/ by hand per topic
# render via the per-episode assemble script
# run: pytest tests/ -q   and   python tools/qa/qc.py <video>
```

## Status

- Automated: color_match grading, footage sourcing + manifest, QC thresholds, scaffold.
- Semi-automated: assemble/render, AI splash, subtitles (parameter args exist; no shared template yet).
- Manual: topic copy, script, subtitles, music, metadata.
