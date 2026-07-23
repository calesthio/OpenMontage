---
name: text-to-speech
description: |
  Generate speech audio from text using HeyGen's Starfish TTS model. Use when: (1) Generating standalone speech audio files from text, (2) Converting text to speech with voice selection, speed, and pitch control, (3) Creating audio for voiceovers, narration, or podcasts, (4) Working with HeyGen's /v1/audio endpoints, (5) Listing available TTS voices by language or gender.
allowed-tools: mcp__heygen__*
metadata:
  openclaw:
    requires:
      env:
        - HEYGEN_API_KEY
    primaryEnv: HEYGEN_API_KEY
---

# Text-to-Speech (HeyGen Starfish)

Generate speech audio files from text using HeyGen's in-house Starfish TTS model. This skill is for standalone audio generation — separate from video creation.

## Authentication

All requests require the `X-Api-Key` header. Set the `HEYGEN_API_KEY` environment variable.

```bash
curl -X GET "https://api.heygen.com/v1/audio/voices" \
  -H "X-Api-Key: $HEYGEN_API_KEY"
```

## Tool Selection

If HeyGen MCP tools are available (`mcp__heygen__*`), **prefer them** over direct HTTP API calls.

| Task | MCP Tool | Fallback (Direct API) |
|------|----------|----------------------|
| List TTS voices | `mcp__heygen__list_audio_voices` | `GET /v1/audio/voices` |
| Generate speech audio | `mcp__heygen__text_to_speech` | `POST /v1/audio/text_to_speech` |

## Default Workflow

1. List voices with `mcp__heygen__list_audio_voices` (or `GET /v1/audio/voices`)
2. Pick a voice matching desired language, gender, and features
3. Call `mcp__heygen__text_to_speech` (or `POST /v1/audio/text_to_speech`) with text and voice_id
4. Use the returned `audio_url` to download or play the audio

## List TTS Voices

Retrieve voices compatible with the Starfish TTS model.

> **Note:** This uses `GET /v1/audio/voices` — a different endpoint from the video voices API (`GET /v2/voices`). Not all video voices support Starfish TTS.

### curl

```bash
curl -X GET "https://api.heygen.com/v1/audio/voices" \
  -H "X-Api-Key: $HEYGEN_API_KEY"
```

### TypeScript

```typescript
interface TTSVoice {
  voice_id: string;
  language: string;
  gender: "female" | "male" | "unknown";
  name: string;
  preview_audio_url: string | null;
  support_pause: boolean;
  support_locale: boolean;
  type: string;
}

interface TTSVoicesResponse {
  error: null | string;
  data: {
    voices: TTSVoice[];
  };
}

async function listTTSVoices(): Promise<TTSVoice[]> {
  const response = await fetch("https://api.heygen.com/v1/audio/voices", {
    headers: { "X-Api-Key": process.env.HEYGEN_API_KEY! },
  });

  const json: TTSVoicesResponse = await response.json();

  if (json.error) {
    throw new Error(json.error);
  }

  return json.data.voices;
}
```

### Python

```python
import requests
import os

def list_tts_voices() -> list:
    response = requests.get(
        "https://api.heygen.com/v1/audio/voices",
        headers={"X-Api-Key": os.environ["HEYGEN_API_KEY"]}
    )

    data = response.json()
    if data.get("error"):
        raise Exception(data["error"])

    return data["data"]["voices"]
```

### Response Format

```json
{
  "error": null,
  "data": {
    "voices": [
      {
        "voice_id": "f38a635bee7a4d1f9b0a654a31d050d2",
        "name": "Chill Brian",
        "language": "English",
        "gender": "male",
        "preview_audio_url": "https://resource.heygen.ai/text_to_speech/WpSDQvmLGXEqXZVZQiVeg6.mp3",
        "support_pause": true,
        "support_locale": false,
        "type": "public"
      }
    ]
  }
}
```

## Generate Speech Audio

Convert text to speech audio using a specified voice.

### Endpoint

`POST https://api.heygen.com/v1/audio/text_to_speech`

### Request Fields

| Field | Type | Req | Description |
|-------|------|:---:|-------------|
| `text` | string | Y | Text content to convert to speech |
| `voice_id` | string | Y | Voice ID from `GET /v1/audio/voices` |
| `speed` | number | | Speech speed, 0.5-1.5 (default: 1) |
| `pitch` | integer | | Voice pitch, -50 to 50 (default: 0) |
| `locale` | string | | Accent/locale for multilingual voices (e.g., `en-US`, `pt-BR`) |
| `elevenlabs_settings` | object | | Advanced settings for ElevenLabs voices |

### ElevenLabs Settings (optional)

| Field | Type | Description |
|-------|------|-------------|
| `model` | string | Model selection (`eleven_v3`, `eleven_turbo_v2_5`, etc.) |
| `similarity_boost` | number | Voice similarity, 0.0-1.0 |
| `stability` | number | Output consistency, 0.0-1.0 |
| `style` | number | Style intensity, 0.0-1.0 |

### curl

```bash
curl -X POST "https://api.heygen.com/v1/audio/text_to_speech" \
  -H "X-Api-Key: $HEYGEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello! Welcome to our product demo.",
    "voice_id": "YOUR_VOICE_ID",
    "speed": 1.0
  }'
```

### TypeScript

```typescript
interface TTSRequest {
  text: string;
  voice_id: string;
  speed?: number;
  pitch?: number;
  locale?: string;
  elevenlabs_settings?: {
    model?: string;
    similarity_boost?: number;
    stability?: number;
    style?: number;
  };
}

interface WordTimestamp {
  word: string;
  start: number;
  end: number;
}

interface TTSResponse {
  error: null | string;
  data: {
    audio_url: string;
    duration: number;
    request_id: string;
    word_timestamps: WordTimestamp[];
  };
}

async function textToSpeech(request: TTSRequest): Promise<TTSResponse["data"]> {
  const response = await fetch(
    "https://api.heygen.com/v1/audio/text_to_speech",
    {
      method: "POST",
      headers: {
        "X-Api-Key": process.env.HEYGEN_API_KEY!,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
    }
  );

  const json: TTSResponse = await response.json();

  if (json.error) {
    throw new Error(json.error);
  }

  return json.data;
}
```

### Python

```python
import requests
import os

def text_to_speech(
    text: str,
    voice_id: str,
    speed: float = 1.0,
    pitch: int = 0,
    locale: str | None = None,
) -> dict:
    payload = {
        "text": text,
        "voice_id": voice_id,
        "speed": speed,
        "pitch": pitch,
    }

    if locale:
        payload["locale"] = locale

    response = requests.post(
        "https://api.heygen.com/v1/audio/text_to_speech",
        headers={
            "X-Api-Key": os.environ["HEYGEN_API_KEY"],
            "Content-Type": "application/json",
        },
        json=payload,
    )

    data = response.json()
    if data.get("error"):
        raise Exception(data["error"])

    return data["data"]
```

### Response Format

```json
{
  "error": null,
  "data": {
    "audio_url": "https://resource2.heygen.ai/text_to_speech/.../id=365d46bb.wav",
    "duration": 5.526,
    "request_id": "p38QJ52hfgNlsYKZZmd9",
    "word_timestamps": [
      { "word": "<start>", "start": 0.0, "end": 0.0 },
      { "word": "Hey", "start": 0.079, "end": 0.219 },
      { "word": "there,", "start": 0.239, "end": 0.459 },
      { "word": "<end>", "start": 5.526, "end": 5.526 }
    ]
  }
}
```

## Usage Examples

### Basic TTS

```typescript
const result = await textToSpeech({
  text: "Welcome to our quarterly earnings call.",
  voice_id: "YOUR_VOICE_ID",
});

console.log(`Audio URL: ${result.audio_url}`);
console.log(`Duration: ${result.duration}s`);
```

### With Speed Adjustment

```typescript
const result = await textToSpeech({
  text: "We're thrilled to announce our newest feature!",
  voice_id: "YOUR_VOICE_ID",
  speed: 1.1,
});
```

### With Locale for Multilingual Voices

```typescript
const result = await textToSpeech({
  text: "Bem-vindo ao nosso produto.",
  voice_id: "MULTILINGUAL_VOICE_ID",
  locale: "pt-BR",
});
```

### Find a Voice and Generate Audio

```typescript
async function generateSpeech(text: string, language: string): Promise<string> {
  const voices = await listTTSVoices();
  const voice = voices.find(
    (v) => v.language.toLowerCase().includes(language.toLowerCase())
  );

  if (!voice) {
    throw new Error(`No TTS voice found for language: ${language}`);
  }

  const result = await textToSpeech({
    text,
    voice_id: voice.voice_id,
  });

  return result.audio_url;
}

const audioUrl = await generateSpeech("Hello and welcome!", "english");
```

## Pauses with Break Tags

Use SSML-style break tags in your text for pauses:

```
word <break time="1s"/> word
```

Rules:
- Use seconds with `s` suffix: `<break time="1.5s"/>`
- Must have spaces before and after the tag
- Self-closing tag format

## Expressive Voice Direction

For narration, create a short voice-performance plan before generating audio:

- narrator persona and emotional intent
- pacing profile
- energy curve across the script
- where pauses should land
- words or phrases that need emphasis

Use concrete cues, not generic instructions. "Warm but decisive; pause before
the contrast; slow down on the final sentence" is useful. "Sound natural" is
not.

When the selected voice supports pauses, put the most important pauses directly
in the text with break tags. Generate a sample from the most performance-heavy
section first, and do not batch-generate the rest if the sample sounds flat,
rushed, or ignores the intended breaks.

## Best Practices

1. **Use `GET /v1/audio/voices`** to find compatible voices — not all voices from `GET /v2/voices` support Starfish TTS
2. **Check `support_locale`** before setting a `locale` — only multilingual voices support locale selection
3. **Keep speed between 0.8-1.2** for natural-sounding output
4. **Preview voices** using the `preview_audio_url` before generating (may be null for some voices)
5. **Use `word_timestamps`** in the response for caption syncing or timed text overlays
6. **Use SSML break tags** in your text for pauses: `word <break time="1s"/> word`
