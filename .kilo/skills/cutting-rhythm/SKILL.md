---
name: cutting-rhythm
source: https://github.com/agamm/video-agent
pinned_commit: cc00d2815869cbf2d708426a5082612f0c3b4dbf
license: MIT (Agam More, 2026) — upstream LICENSE read verbatim
adaptation: Linux port — no mlx-whisper (use local transcriber/whisper), no h264_videotoolbox (use libx264 via ffmpeg), no `uv run video-agent` CLI (guidance only; map commands to OpenMontage ffmpeg/pipeline tools).
---

# Cutting rhythm (Linux adaptation of agamm/video-agent cutting-rhythm)

Make an edit feel flowing, natural and snappy rather than merely accurate — split edits (J/L
cuts), where to place a cut relative to speech and motion, how long to hold a shot, collapsing
dead air, and cutting on the beat. Use whenever an edit is technically correct but feels choppy,
abrupt, draggy, monotone or "AI-edited", when the user asks to tighten/pace/smooth a cut, or
before finalizing any multi-clip edit. Complements our `edit_decisions` cut list
(`schemas/artifacts/edit_decisions.schema.json`) with the timing decisions that make it
watchable.

## 1. Split edits (J/L cuts) — the single biggest flow win

A cut where picture and sound change on the same frame is a butt cut. It announces itself. Real
edits stagger the two so the viewer's ear carries them across the visual change.

- **J-cut** — the next clip's sound arrives before its picture. Use on almost every
  dialogue/interview cut.
- **L-cut** — the current clip's sound continues over the next picture. Use for cutaways,
  B-roll, reactions.

Map to our `edit_decisions.cuts[].reason` + a per-cut lead/lag field (the schema's
`reason` carries the rationale; `transition_in`/`transition_out` carry cut type). Typical
amounts: 0.2–0.5 s conversational, 0.5–1.0 s documentary cutaway, up to ~2 s for B-roll under
continuing narration. Below ~0.15 s is inaudible.

**Do not** split a cut meant to be a hard break (scene change, chapter boundary, trailer
button).

## 2. Where the cut actually goes

- **Cut in the silence, not on the word.** Get the *what* from transcript word timestamps and
  the *where* from speech/silence segments; the silence boundary is the truth (whisper word
  times jitter ±0.3–0.7 s).
- **Leave the breath.** The intake before a sentence belongs to that sentence. Cutting it off
  makes the read sound rushed and airless.
- **Cut on motion, not around it.** A cut placed while a subject is moving hides itself; a cut
  between two still moments exposes itself. Never cut on the peak of a gesture.
- **Match outgoing and incoming energy.**

## 3. Pause grammar — natural, not dead

"Tighten this up" almost never means cut content; it means shorten the gaps. Conservative
targets (INITIAL GUESSES — tune after human review):

| Feel | target gap | min gap |
|---|---|---|
| Snappy / social / explainer | 0.25–0.35 s | 0.6 s |
| Talking head, vlog, tutorial | 0.4–0.6 s | 1.0 s |
| Documentary — let it breathe | 0.7–1.0 s | 1.5 s |

Do **not** tighten uniformly. A pause after a punchline or reveal is doing work — widen those
back out by hand. Uniform pacing is what makes an edit sound machine-made.

## 4. Shot length — the snap

- Vary the holds. If shot-length variation is under ~15%, the cut list is monotone.
- Accelerate toward the climax (trailer/montage: shot lengths shorten as they build).
- Hold the last shot — endings want air.
- Hold after a hit (punchline/reveal) so it lands.

Trailer structure: hook (≤2 s) → build → turn → climax (fastest cutting) → button (one held
shot + title).

## 5. Cutting on the beat

Snap each cut so it lands on a beat in the output timeline (cumulative running time) —
snapping source timestamps to beats is meaningless. Cuts with no beat inside tolerance are left
alone.

## 6. Review loop (INITIAL GUESSES)

```
edl --report --dry-run   # pacing, no render   (map: review edit_decisions cuts)
draft render             # fast check
final render             # deliverable
```

Read `--report` before rendering — it catches uniform shot length, butt cuts (no split edit),
and full-length pauses.

## Linux adaptations vs upstream

- Upstream references `uv run video-agent tighten/snap/edl` and `h264_videotoolbox` + mlx-whisper.
- On this machine: render via ffmpeg (`libx264`, always available), transcript via local
  `transcriber`/whisper (CPU). `uv run video-agent` CLI is not installed and is not part of
  this port; treat those command lines as conceptual examples to map onto our pipeline tools.
- No `scipy.signal.correlate` multicam sync is wired in our repo — manual sync only.

## Network / env / writes (observed from upstream SKILL.md)

- Network calls: none for the core cutting-rhythm guidance (optional upstream `grok-video-edit`
  generative VFX needs `XAI_API_KEY` — out of scope, not ported).
- Env vars: none required for this skill.
- Writes: none by the skill itself (guidance only); produced `edit_decisions` artifacts live in
  `projects/<run>/artifacts/edit_decisions.json`.
