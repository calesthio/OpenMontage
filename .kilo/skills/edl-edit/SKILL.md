---
name: edl-edit
source: https://github.com/agamm/video-agent
pinned_commit: cc00d2815869cbf2d708426a5082612f0c3b4dbf
license: MIT (Agam More, 2026) — upstream LICENSE read verbatim
adaptation: Linux port — no `uv run video-agent` CLI (guidance only), no h264_videotoolbox (use libx264), EDL maps to OpenMontage `edit_decisions` artifact (`schemas/artifacts/edit_decisions.schema.json`).
---

# EDL edit (Linux adaptation of agamm/video-agent edl-edit)

Build a multi-clip edit as an auditable JSON "edit decision list" (EDL) — a list of clips with
source/in/out and a written rationale per pick — that renders to a finished video. Use whenever
stitching several cuts/takes/segments into one video and wanting the edit to be reviewable,
diffable, and re-runnable instead of a throwaway ffmpeg filtergraph. Covers the schema, the
rationale discipline, multicam cutaways, and verifying the output by re-transcribing it.

## The edit is a JSON file

Don't hand-author a one-off `filter_complex` for a multi-cut edit and throw it away. Write the
edit as `edit_decisions` (`schemas/artifacts/edit_decisions.schema.json`) — a list of cuts with
`source`, `in_seconds`, `out_seconds`, and a written `reason` — and let one render execute it.

Why: the edit becomes text you can read, diff, and re-render. A revision is "change two numbers
and re-run," not "reconstruct the filtergraph." The `reason` field forces you to write down why
each cut was made — better decisions and an inspectable trail.

## Schema mapping (our real timeline schema: edit_decisions)

| EDL field | OpenMontage `edit_decisions` field |
|---|---|
| clip `src` | `cuts[].source` (path or asset-manifest ID) |
| clip `start`/`end` (seconds, float) | `cuts[].in_seconds` / `cuts[].out_seconds` |
| clip `rationale` | `cuts[].reason` |
| clip `audio_lead` (J/L split) | `cuts[].reason` + `transition_in`/`transition_out` |
| clip `punch` (slow push) | `cuts[].transform.animation` |
| clip `transition_in`/`transition_out` | `cuts[].transition_in` / `cuts[].transition_out` |
| clip `transition_duration` | `cuts[].transition_duration` |
| music `src`/`gain_db`/`duck`/`fade_in`/`fade_out` | `audio.music` (`asset_id`, `volume`, `ducking`, `fade_in_seconds`, `fade_out_seconds`) |
| `audio_fix` filter chain | `audio` (normalize/ducking) |
| `seam_fade` | not represented; use 15 ms audio boundary fade convention in rationale |

- `in_seconds`/`out_seconds` are seconds (floats) on the source timeline. Cuts are quantized to
  the frame grid at render so picture can't drift against sound.
- `reason`, `first_words`, `candidate_takes` equivalents are documentation/humans-only; always
  fill `reason`.
- Every segment is normalized to the project width×height at the project fps, so clips of
  different resolutions/fps concat cleanly.
- `audio_lead` makes the cut a split edit (+ = J-cut, − = L-cut). Video and audio are
  concatenated as independent chains so a lead never desyncs downstream.
- `seam_fade` convention: 15 ms audio boundary fade at every internal cut (click-killing,
  inaudible).

## Multicam cutaways

A cut can take audio from `source` but picture from a different camera/source (`vsrc` upstream).
Map: `cuts[].layer = "overlay"` for the cutaway picture while `audio` stays on the primary
narration track. The audio timeline stays continuous; only the video switches. A cutaway picture
must match the length of the audio it covers.

## Get cut points from the transcript, not by scrubbing

Build the EDL from text: transcript word timestamps for what's said, speech/silence segments for
frame-accurate silence edges. Grep the transcript for the line you want and write its start/end
into `edit_decisions.cuts`. Never eyeball a timeline.

## Check the pacing before you render

Run the pacing review (`cutting-rhythm` skill; upstream `edl --report --dry-run`) on
`edit_decisions.cuts` before rendering — free, catches monotony invisible in JSON: uniform shot
length, butt cuts, full-length pauses.

## Verify by re-transcribing the OUTPUT

Transcribe what you actually rendered and compare to intent: right words, no fillers, nothing
dropped, no clipped/repeated words at cuts. Fix the offending clip's `in_seconds`/`out_seconds`
and re-run. Internal verification only — show the user the finished video, not the checks.

## Gotchas

- One re-encode: the whole EDL renders in a single pass; don't post-process with stream-copy
  concat afterward (freezes at non-keyframe seams; re-encode audio to kill drift).
- Linux ffmpeg: use `libx264` + `aac`, not `h264_videotoolbox`.
- `audio_lead` needs source material to reach into (a J-cut borrows audio from before the
  in-point). Ignored on clip 0.

## Network / env / writes (observed from upstream SKILL.md)

- Network calls: none (local ffmpeg render).
- Env vars: none required.
- Writes: `edit_decisions.json` in `projects/<run>/artifacts/`; rendered video in
  `projects/<run>/renders/`.
