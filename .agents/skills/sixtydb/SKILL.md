---
name: sixtydb
description: Generate voiceover audio using the 60db.ai TTS API. Use for narration, dialogue, and multilingual speech (English + 9 Indic languages — Hindi, Bengali, Gujarati, Kannada, Malayalam, Marathi, Punjabi, Tamil, Telugu). Triggers include generating voiceovers when ElevenLabs is unavailable, Indic-language narration, low-cost TTS, audio with built-in enhancement, or streaming/WebSocket TTS scenarios.
---

# 60db.ai Audio Generation

Requires `SIXTYDB_API_KEY` in `.env`.

## When to pick 60db over ElevenLabs

- **Indic languages** — native, auto-detected from input text.
- **Cost** — $0.00002/char (~30× cheaper than ElevenLabs' default rate).
- **Built-in audio enhancement** — `enhance=true` runs server-side quality pass; no post-processing needed.
- **Lightweight responses** — REST returns JSON with base64 audio (no need to manage binary streams for short clips).

Pick ElevenLabs when you need voice cloning, the `eleven_v3` expressive model, or fine-grained voice style control beyond stability/similarity.

## REST: synchronous synthesis (used by `sixtydb_tts` tool)

```python
import requests, base64, os

resp = requests.post(
    "https://api.60db.ai/tts-synthesize",
    headers={
        "Authorization": f"Bearer {os.environ['SIXTYDB_API_KEY']}",
        "Content-Type": "application/json",
    },
    json={
        "text": "Welcome to my video!",
        "voice_id": "fbb75ed2-975a-40c7-9e06-38e30524a9a1",
        "speed": 1.0,
        "stability": 50,          # 0..100  (lower = expressive)
        "similarity": 75,         # 0..100  (voice match fidelity)
        "enhance": True,
        "output_format": "mp3",   # mp3 | wav | ogg | flac
    },
    timeout=120,
)
resp.raise_for_status()
body = resp.json()
# body = {success, message, audio_base64, sample_rate, duration_seconds, encoding, output_format}
with open("voiceover.mp3", "wb") as f:
    f.write(base64.b64decode(body["audio_base64"]))
```

**Limits:** 5000 characters per request. For longer narration, split on sentence/paragraph boundaries and concatenate with ffmpeg.

## REST: streaming (NDJSON)

`POST https://api.60db.ai/tts-stream` — same body, chunked transfer encoding. Each line is one of:

```json
{"type": "chunk", "result": {"audioContent": "<base64>"}}
{"type": "complete"}
{"type": "error", "message": "..."}
```

Use for lower time-to-first-audio on long passages. Decode each `chunk` and write to a single open file handle, then close on `complete`.

## WebSocket: incremental synthesis

`wss://api.60db.ai/ws/tts?apiKey=sk_live_…`

Stateful protocol:

1. Connect → server sends `{connection_established: {…credit_balance, user_id}}`.
2. Client sends `create_context` with `context_id`, `voice_id`, `audio_config{audio_encoding, sample_rate_hertz}`, `speed`, `stability`, `similarity`.
3. Client sends one or more `send_text` (max 50,000 cumulative chars per context).
4. Client sends `flush_context` to trigger synthesis → server replies with `audio_chunk` messages (base64) then `flush_completed`.
5. `close_context` ends the session.

| Encoding | Sample rates | Concatenatable |
|---|---|---|
| `LINEAR16` / `PCM` | 8000, 16000, 24000, 48000 | Yes |
| `MULAW` / `ULAW` | 8000 | Yes (telephony) |
| `OGG_OPUS` | 24000 | No (each chunk is a self-contained Ogg) |

Use the WebSocket only when you need: reusable voice context across multiple text segments in one TCP connection, OR sub-second incremental delivery for live agents. For batch narration the REST endpoint is simpler.

## Voice Settings

| Style | speed | stability | similarity |
|---|---|---|---|
| Natural / professional | 1.0 | 70–85 | 85–95 |
| Conversational | 0.95–1.0 | 50–60 | 75–85 |
| Expressive / narrative | 1.0–1.1 | 30–50 | 70–80 |

`stability` low → more emotional variation; high → flatter, more consistent.

## Pricing

- $0.00002 per character (~$0.02 per 1000 chars).
- $0.01 minimum per WebSocket context.

## Inside OpenMontage

Call through `tts_selector` rather than directly — the selector auto-discovers `sixtydb_tts` and ranks it against `elevenlabs_tts`, `openai_tts`, `google_tts`, `piper_tts`, `doubao_tts`. To force it:

```python
tts_selector.execute({
    "text": "Your script here",
    "preferred_provider": "sixtydb",
    "voice_id": "fbb75ed2-975a-40c7-9e06-38e30524a9a1",
    "output_path": "public/audio/scene-01.mp3",
})
```

The selector schema uses **0..1** ranges for `stability` / `similarity_boost` for cross-provider parity. The `sixtydb_tts` tool rescales to 0..100 internally before calling the API. `model_id` and `style` are accepted for parity and silently ignored — 60db has no equivalent.

## Output Format Mapping

| Caller passes | Sent to 60db |
|---|---|
| `mp3_44100_128`, `mp3_44100_192` | `mp3` |
| `pcm_16000`, `pcm_24000` | `wav` |
| `mp3` / `wav` / `ogg` / `flac` | passthrough |
| anything else | `mp3` |

## Remotion Wiring

Identical to ElevenLabs — write MP3s to `public/audio/scenes/scene-NN.mp3`, build `manifest.json` with `{file, duration}`, and consume in `<Audio src={staticFile(...)}>` inside `<Series.Sequence>`. See `.agents/skills/elevenlabs/SKILL.md` for the full Remotion pattern.
