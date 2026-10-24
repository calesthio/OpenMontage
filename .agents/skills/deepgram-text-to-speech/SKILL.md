---
name: deepgram-text-to-speech
description: Generate narration audio using Deepgram Aura-2 (REST /v1/speak). Use when synthesizing voiceovers or narration in OpenMontage — especially Spanish narration with a regional accent (Argentine, Mexican, Colombian, Peninsular, Latin American). Optional cloud TTS provider — available when DEEPGRAM_API_KEY is configured; the local piper_tts remains the default offline path. Shares one key with deepgram_stt.
license: MIT
compatibility: Requires internet access and a Deepgram API key (DEEPGRAM_API_KEY).
metadata: {"openclaw": {"requires": {"env": ["DEEPGRAM_API_KEY"]}, "primaryEnv": "DEEPGRAM_API_KEY"}}
---

# Deepgram Aura — Text-to-Speech

Generate narration with **Deepgram Aura-2** — natural conversational voices in
English, Spanish (with regional accents), German, French, Dutch, Italian and
Japanese, served synchronously by the REST `/v1/speak` endpoint (JSON text in,
audio bytes out, no polling). In OpenMontage this is exposed through the
`deepgram_tts` tool (`capability=tts`, `provider=deepgram`). It is an
**optional cloud TTS provider**. The local `piper_tts` remains the **default
offline path** and the fallback; `elevenlabs_tts` remains the choice for voice
cloning and `azure_tts` for fine SSML prosody control.

> Docs: [Speak request](https://developers.deepgram.com/reference/text-to-speech/speak-request) · [Voices and languages](https://developers.deepgram.com/docs/tts-models) · [Prompting / pauses](https://developers.deepgram.com/docs/text-to-speech-prompting)

## Setup

Same key as `deepgram_stt` — **one key unlocks both directions** (STT and
TTS). Create it in the [Deepgram console](https://console.deepgram.com) under
**API Keys**. New accounts include free credit.

```bash
export DEEPGRAM_API_KEY=your_deepgram_api_key
```

`deepgram_tts` reports `AVAILABLE` once `DEEPGRAM_API_KEY` is set.

## Using it in a pipeline

Route through `tts_selector` (it auto-discovers `deepgram_tts`; pass
`preferred_provider: "deepgram"` when the user approved it), or call the
provider tool directly:

```python
from tools.tool_registry import registry
registry.discover()
tts = registry._tools["deepgram_tts"]

result = tts.execute({
    "text": "¿Estás atravesando una pérdida, un desamor, algo que todavía duele?",
    "voice": "antonia",                # alias or full Aura model name
    "speed": 0.95,                     # 0.7–1.5; omit for 1.0
    "output_path": "projects/my-video/assets/audio/seg_001.mp3",
    "output_format": "mp3",            # or "wav" (48kHz 16-bit PCM) for mixing
})
```

If `deepgram_tts` is unavailable (no key) or errors, fall back per its declared
chain: `azure_tts` → `elevenlabs_tts` → `piper_tts`. Switching provider is a
major production choice — ask the user first.

## Voice selection

The voice name encodes the language: `aura-2-<name>-<lang>`. Send text in the
voice's language. Curated aliases accepted by `voice`:

| Alias | Model | Accent | Character |
|-------|-------|--------|-----------|
| `antonia` | aura-2-antonia-es | Argentine (es-AR), feminine, adult | approachable, natural, friendly |
| `estrella` | aura-2-estrella-es | Mexican (es-MX), feminine, mature | calm, natural, expressive |
| `selena` | aura-2-selena-es | Latin American (es-419), feminine, young adult | calm, friendly, casual |
| `aquila` | aura-2-aquila-es | Latin American (es-419), masculine | expressive, confident |
| `sirio` | aura-2-sirio-es | Mexican (es-MX), masculine | calm, empathetic, baritone |
| `diana` | aura-2-diana-es | Peninsular (es-ES), feminine | storytelling, expressive |
| `nestor` | aura-2-nestor-es | Peninsular (es-ES), masculine | calm, professional |
| `thalia` | aura-2-thalia-en | American English, feminine | clear, confident (tool default) |
| `apollo` | aura-2-apollo-en | American English, masculine | comfortable, casual |

Any valid Aura model name may be passed verbatim. Check the voices page for the
full, current list before promising an accent to the user.

## Parameters that matter

- **`voice`** — the single biggest creative choice. For Spanish narration,
  match the accent to the audience (es-AR for Rioplatense audiences, es-419 for
  pan-LatAm, es-ES for Spain). Present the accent explicitly to the user.
- **`speed`** — 0.7–1.5 multiplier. Calm, intimate narration usually reads best
  around `0.9`–`0.95`. Deepgram notes speed is not yet supported in every
  language — listen to the sample to confirm it took effect.
- **`output_format`** — `mp3` for delivery, `wav` (48kHz PCM) when the segment
  feeds `audio_mixer`.
- Determinism: Aura may insert natural pauses/breaths non-deterministically, so
  re-rendering a segment can differ slightly. Regenerate whole segments, never
  splice two renders of the same line.

## Writing text for Aura (pacing)

Aura has no SSML. Pacing is controlled with punctuation:

- A comma or period yields a short natural pause.
- An ellipsis `...` yields a longer pause; groups of three dots stack
  (`......` = longer). Dots not in groups of three are not treated as pauses.
- Question marks shape rising intonation — useful for second-person hooks.
- Spell numbers and acronyms the way they should be spoken.

## Cost

Aura-2 pay-as-you-go: **$0.030 per 1k characters** (Oct 2026). A 400-character
narration segment ≈ $0.012. The tool reports per-call `cost_usd`. See
[Deepgram pricing](https://deepgram.com/pricing) for current rates.

## Limits & tips

- One `execute` call = one narration segment. Generate per script section —
  segments align cleanly to scene timings and are cheap to regenerate.
- Verify quality: generate one short sample and let the user approve voice and
  accent before batch-running the full script (Decision Communication
  Contract).
- After generating, run `deepgram_stt` (or `transcriber`) on the narration to
  get word timestamps for captions.
