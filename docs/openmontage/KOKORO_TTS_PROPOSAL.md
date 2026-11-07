# Kokoro TTS Integration Proposal — OpenMontage (next milestone after V)

**Status:** proposal only. No pipeline code changed in Milestone V.
**Prepared:** 2026-10-17.

## Proposed file

`tools/audio/kokoro_tts.py` — new `BaseTool` subclass `KokoroTTSTool` (capability
`text_to_speech`, provider `kokoro`, dependencies `cmd:ffmpeg` optional for re-wrap,
`import kokoro`/`import torch`/`import misaki`).

## Proposed function

`KokoroTTSTool.execute(inputs) -> ToolResult`

Inputs:
- `text` (required, str) — narration text
- `output_path` (required, str) — pcm_s16le wav at 24000 Hz
- `voice` (optional, str, default `af_heart`) — Kokoro voice id
- `lang_code` (optional, str, default `a`) — American English
- `speed` (optional, float, default `1.0`)

Behavior:
1. Lazy-import `kokoro.KPipeline` (import at call time so the package is optional).
2. `pipeline = KPipeline(lang_code=lang_code)` — downloads/caches `config.json` +
   `kokoro-v1_0.pth` from `hexgrad/Kokoro-82M` into `HF_HOME` (default
   `~/.cache/huggingface`; operator may set to a gitignored cache dir).
3. `generator = pipeline(text, voice=voice, speed=speed)`; concatenate yielded audio.
4. Write `pcm_s16le` 24000 Hz mono wav to `output_path` (soundfile or scipy.io.wavfile).
5. Return `ToolResult(success=True, data={...}, artifacts=[output_path])`.

Fail-closed: if `kokoro`/`torch`/`misaki` not importable → `BLOCKED`; if weight download
fails → `BLOCKED` (never silent success).

## Integration point (EDITING_DOCTRINE §3 universal order of operations)

Audio finishing is **step 5 (audio — normalize, music bed)**. Kokoro TTS sits **before**
finishing, right after content cuts/rhythm/structure/reframe and before `finish_audio`:

1. content cuts
2. rhythm (split edits, beat-snap)
3. structure (transitions)
4. reframe
5. **audio (Kokoro TTS → narration wav; music bed; finish_audio normalize/duck/limit)**
6. overlays/captions LAST (burn at final resolution)
7. single final encode

`finish_audio` (Milestone D2) consumes the Kokoro wav as `input_path`, applies two-pass
loudnorm + limiter (+ optional sidechain ducking if a MUSIC_POLICY-cleared music bed is
present), and emits the finished audio fed into the final mux (native `aac` encoder —
verified working in Milestone V).

## Voice license gate (precondition)

Do not ship Kokoro narration in a published/monetized video until the owner signs off on
the training-data caveats (CC BY items Koniwa `tnc` + SIWIS; synthetic-data origin
UNKNOWN) per `docs/openmontage/VOICE_DECISION.md` §4. Piper `en_US-lessac-medium` remains
blocked (voice license UNKNOWN).

## Files not changed in V

No pipeline code, no `tools/` changes, no `.kilo/skills/` changes, no lock/process
changes in Milestone V. Only docs: `VOICE_DECISION.md`, `TOOLING_DECISIONS.md` (§12.2,
§14), this proposal, and the work log.
