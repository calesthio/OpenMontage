# Editing Doctrine — OpenMontage (Milestone D1)

**Status:** doctrine ported from upstream `agamm/video-agent` (MIT, pinned commit
`cc00d2815869cbf2d708426a5082612f0c3b4dbf`), read-only, not installed. Adapted for Linux
(`libx264` + `aac`, local CPU transcription — no `h264_videotoolbox`, no mlx-whisper, no
`uv run video-agent` CLI). Skills copied into `.kilo/skills/`: `cutting-rhythm`,
`edl-edit`, `audio-edit` (pinned, MIT).

**Source SKILL.md files read (read-only, no code copied):** `editor`, `edl-edit`,
`cutting-rhythm`, `audio-edit`, `video-transitions`, `captions`. Upstream network/env/write
profile summarized in §8.

---

## 1. Timeline schema — the single source of truth

All edits are authored as `edit_decisions` (`schemas/artifacts/edit_decisions.schema.json`),
not as throwaway `filter_complex` graphs. A revision is "change two numbers and re-run," never
"reconstruct the filtergraph."

Relevant fields (from our schema):

- `cuts[].id`, `cuts[].source` (path or asset-manifest ID), `cuts[].in_seconds`,
  `cuts[].out_seconds` (seconds, float; quantized to frame grid at render).
- `cuts[].reason` — **required written rationale per cut** (which take won, why others lost,
  why the cut point sits where it does). Humans-only, renderer-ignored; always fill it.
- `cuts[].transition_in` / `cuts[].transition_out` — cut type entering/leaving (cut, fade,
  dissolve, wipe …).
- `cuts[].transition_duration` — overlap length in seconds (typically 0.3–1.0 s).
- `cuts[].transform.animation` — slow push/ken-burns for static shots (`punch` equivalent).
- `cuts[].layer` — `primary` / `overlay` (multicam cutaway picture) / `background`.
- `audio.music` — `asset_id`, `volume` (0–1), `ducking` (bool or object with
  `enabled`/`threshold_db`/`reduction_db`/`attack_ms`/`release_ms`), `fade_in_seconds`,
  `fade_out_seconds`.
- `audio.narration.segments[]` — `asset_id`, `start_seconds`, `end_seconds`.
- `audio.sfx[]` — `asset_id`, `start_seconds`, `volume`.
- `overlays[]` — text/logo/graphics with `position` + `opacity` (+ `animation`).
- `subtitles` — `enabled`, `style` (sentence / word-by-word / karaoke), `source` (srt/vtt path
  or asset ID), `font_size`, `color`, `position`.
- `render_runtime` — `remotion` / `hyperframes` / `ffmpeg`; locked at proposal, carried
  forward unless a logged `render_runtime_selection` decision overrides it.
- `composition_mode` — `templated` / `atelier`; locked at proposal.

## 2. Rules to port (mapped to our schema)

### EDL with per-cut rationale (from `edl-edit`)

Every `cuts[]` entry carries `source`, `in_seconds`, `out_seconds`, and a non-empty `reason`.
Rationale is the audit trail — it is what makes the edit diffable and re-runnable. Never ship a
multi-clip cut without a reason on every cut.

### Split edits / J–L cuts (from `cutting-rhythm`, `edl-edit`)

A cut where picture and sound change on the same frame is a butt cut and reads as robotic.
Stagger them:

- **J-cut** — next clip's sound arrives before its picture (positive lead). Use on almost every
  dialogue/interview cut.
- **L-cut** — current clip's sound continues over the next picture (negative lead / lag). Use
  for cutaways, B-roll, reactions.

Map: express lead/lag in `cuts[].reason` and mark `transition_in`/`transition_out` as split.
Typical amounts (INITIAL GUESSES — tune after human review):

| Context | Lead/lag |
|---|---|
| Conversational | 0.2–0.5 s |
| Documentary cutaway | 0.5–1.0 s |
| B-roll under continuing narration | up to ~2.0 s |
| Below | ~0.15 s (inaudible — skip) |

Do **not** split a cut meant to be a hard break (scene change, chapter boundary, trailer
button). `audio_lead` needs source material to reach into (a clip starting near 0 can't borrow
a large lead); clip 0 gets no lead.

### Pacing lint (from `cutting-rhythm`)

Run a pacing review on `edit_decisions.cuts` **before** rendering (free; catches monotony
invisible in JSON). Three failure modes:

1. **Uniform shot length** — if shot-length variation is under ~15% (INITIAL GUESS), the cut
   list is monotone. Vary holds; accelerate toward the climax; hold the last shot (at or above
   the mean, never the tightest).
2. **No split edits** — every cut moving picture and sound together → add leads so cuts stop
   slamming.
3. **Full-length pauses** — collapse dead air to a beat, but **do not tighten uniformly**. A
   pause after a punchline/reveal is doing work — widen those back out by hand.

Pause targets (INITIAL GUESSES — tune after human review):

| Feel | target gap | min gap |
|---|---|---|
| Snappy / social / explainer | 0.25–0.35 s | 0.6 s |
| Talking head, vlog, tutorial | 0.4–0.6 s | 1.0 s |
| Documentary — let it breathe | 0.7–1.0 s | 1.5 s |

### Where the cut goes (from `cutting-rhythm`)

- Cut **in the silence**, not on the word — silence boundary is truth (whisper word times jitter
  ±0.3–0.7 s). Get *what* from transcript word timestamps, *where* from speech/silence segments.
- **Leave the breath** — the intake before a sentence belongs to that sentence.
- **Cut on motion**, not around it — cut just after a gesture starts or just before it lands,
  never on the peak.
- Match outgoing and incoming energy.

### Cutting on the beat (from `cutting-rhythm`)

Snap each cut so it lands on a beat in the **output** timeline (cumulative running time) —
snapping source timestamps to beats is meaningless. Cuts with no beat inside tolerance are left
alone.

### Transitions (from `video-transitions`)

Use a visible transition (`xfade`-family: fade, dissolve, pixelize, wipe, slide, circle) only
when a deliberate effect is wanted. For an abrupt-but-shouldn't-be cut, use a split edit
(§2.2) — reaching for a dissolve to soften a choppy dialogue cut is the wrong fix. For a
seamless join with no visible effect, use a near-zero crossfade seam.

Gotchas (Linux): both inputs must share resolution/fps/pixel format; `xfade` re-encodes
(`libx264`); `offset` = duration of preceding clip − transition duration (read real duration,
never guess the nominal length).

### Captions (from `captions`)

Always transcribe with `--clean` for captions (viewers don't want "um/uh" on screen). Burn
captions on the **final-resolution** video (font size/wrapping follow the output frame) — so
reframe **first**, caption **last**. Style: `--size` px, `--color`, `--position`
(bottom/top/center), `--no-box` to drop the legibility box. Word-level karaoke is not built in;
approximate via transcript `--words` grouping into short `.srt` segments.

### Audio ducking (from `audio-edit`, mapped to `audio.music.ducking`)

Music bed ducked under narration: louder speech → more music attenuation. Tune `reduction_db`
(duck depth), `attack_ms`, `release_ms`. Default ducking `enabled: true` per our schema. If
mixing outside the EDL, use ffmpeg `sidechaincompress` music-by-speech + `amix`, then
`-shortest`, then `loudnorm`. Always re-encode audio to `aac` after a filter.

### Universal order of operations (from `editor`)

Do not reorder — getting it wrong forces re-renders:

1. content cuts (trim, filler-removal, highlight-select)
2. rhythm (tighten, split edits, beat-snap) ← run `cutting-rhythm` pacing lint here
3. structure (transitions)
4. reframe
5. audio (normalize, music bed)
6. overlays/captions **LAST** (burn at final resolution)
7. single final encode

Verify by **re-transcribing the OUTPUT** and comparing to intent (right words, no fillers,
nothing dropped/clipped at cuts). Internal verification only — show the user the finished
video, never a partial render.

## 3. Thresholds marked INITIAL GUESS

All numeric pacing targets in §2 (15% variation, 0.2–0.5 s leads, pause gaps, transition
durations 0.3–1.0 s, beat-snap tolerance) are INITIAL GUESSES to tune after human review. None
are enforced in code.

## 4. Not ported (out of scope for D1)

- Upstream `uv run video-agent` CLI (`tighten`, `snap`, `beats`, `info`, `detect`) — not
  installed; commands are conceptual examples to map onto OpenMontage ffmpeg/pipeline tools.
- `scipy.signal.correlate` multicam audio cross-correlation sync — not wired; manual sync only.
- `grok-video-edit` generative VFX (needs `XAI_API_KEY`, non-deterministic) — not ported.
- `remotion-graphics` / Remotion — not ported (Remotion runtime not available on this machine).
- `yt-dl` / YouTube download — not used.
- Word-level karaoke captions — not built in.

## 5. Observed upstream profile (network / env / writes)

Read from the six upstream SKILL.md files (no code executed):

| Skill | Network calls | Env vars | Writes |
|---|---|---|---|
| `editor` | none (core); optional `grok-video-edit` generative VFX needs `XAI_API_KEY` | `XAI_API_KEY` (optional VFX only) | `edit_decisions`, intermediates under `projects/<run>/` |
| `edl-edit` | none | none | `edit_decisions.json` + rendered video |
| `cutting-rhythm` | none | none | guidance only; produced `edit_decisions` artifacts |
| `audio-edit` | none (plain ffmpeg) | none | output mp4, mixes under `projects/<run>/assets/audio/` |
| `video-transitions` | none | none | output mp4 (re-encoded) |
| `captions` | mlx-whisper model download (~1.5 GB, first use, Apple Silicon only; no key) | none | `.srt`/`.vtt` sidecar + burned captioned video |

On this Linux machine the relevant path is local ffmpeg + local CPU transcription; no network
calls are required for the ported editing skills.

## 6. Review gate

Before any multi-clip render, the `edit_decisions` artifact must:
- validate against `schemas/artifacts/edit_decisions.schema.json`,
- carry a non-empty `reason` on every `cuts[]`,
- carry `render_runtime` matching the locked proposal runtime,
- pass the pacing lint (shot-length variation ≥ ~15%, split edits present, no uniform pauses),
- have `audio.music.ducking` set when a music bed is present.

Thresholds in this section are INITIAL GUESSES — record any tuning as a decision-log entry.
