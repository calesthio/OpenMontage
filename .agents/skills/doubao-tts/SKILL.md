---
name: doubao-tts
description: Generate Mandarin and multilingual narration with Volcengine Doubao Speech 2.0. Use when creating Chinese voiceovers, when the user prefers Doubao/Volcengine/火山引擎/豆包 TTS, or when narration needs character-level timestamp metadata for subtitles.
---

# Doubao TTS

Requires `DOUBAO_SPEECH_API_KEY` in `.env`.
Set `DOUBAO_SPEECH_VOICE_TYPE` for the default voice, or pass `voice_id` to the tool.

## Current API

Use the new-console API key flow:

```text
X-Api-Key: ${DOUBAO_SPEECH_API_KEY}
X-Api-Resource-Id: seed-tts-2.0
```

Do not use `X-Api-App-Id` and `X-Api-Access-Key` with a new-console API Key. If the API returns `load grant: requested grant not found`, the key type or auth header is probably wrong.

For long-form video narration, prefer the async endpoint:

```text
POST https://openspeech.bytedance.com/api/v3/tts/submit
POST https://openspeech.bytedance.com/api/v3/tts/query
```

This returns `audio_url` plus `sentences[].words[]` timing metadata that can be used to build subtitles.

## OpenMontage Usage

Generate with the TTS selector:

```python
from tools.audio.tts_selector import TTSSelector

result = TTSSelector().execute({
    "preferred_provider": "doubao",
    "text": "如果 AI 真的会改变未来，普通人到底该怎么参与？",
    "voice_id": "zh_female_vv_uranus_bigtts",
    "output_path": "projects/my-video/assets/audio/narration.mp3",
    "speech_rate": 0,
    "emotion": "neutral",
    "emotion_scale": 1,
    "enable_timestamp": True,
})
```

Or call the provider directly:

```python
from tools.audio.doubao_tts import DoubaoTTS

result = DoubaoTTS().execute({
    "text": "短样本试听文本。",
    "voice_id": "zh_female_vv_uranus_bigtts",
    "output_path": "projects/my-video/assets/audio/doubao_sample.mp3",
})
```

The provider writes:

- `output_path`: downloaded audio file
- `metadata_path`: full query response JSON, defaulting to `<output_path>.json`

## Recommended Workflow

1. Generate a 10-15 second sample before a full paid narration.
2. Ask the user to approve voice naturalness, accent, and speed.
3. Generate the full narration only after approval.
4. Keep the query JSON. It is the source of truth for subtitle timing.
5. Build captions from `sentences[].words[]`, not from estimated text length.
6. Group captions by Chinese semantic phrases before applying timestamps. Do not split only by fixed character count; it can break phrases like "在不押单个公司的情况下" or "可能会被慢慢稀释" and hurt comprehension.
7. Let the video duration follow the approved voice rhythm unless the user explicitly asks to match a prior runtime.

## Parameters

- `voice_id`: Doubao `speaker` / voice type. Defaults to `DOUBAO_SPEECH_VOICE_TYPE`.
- `resource_id`: use `seed-tts-2.0` for Doubao Speech 2.0 voices.
- `model`: optional `req_params.model` for compatible voices, such as `seed-tts-2.0-expressive` or `seed-tts-2.0-standard`.
- `speech_rate`: `0` is normal, `100` is 2x, `-50` is 0.5x.
- `emotion`: optional emotion/style value. Common values include `neutral`, `happy`, `sad`, `angry`, `surprised`, `excited`, `coldness`, `tender`, `storytelling`, `news`, and `advertising`; support depends on the selected voice.
- `emotion_scale`: optional emotion intensity from `1` to `5`; use `1` for restrained narration.
- `loudness_rate`: optional loudness from `-50` to `100`.
- `post_process_pitch`: optional pitch shift from `-12` to `12`.
- `sample_rate`: default `24000`.
- `bit_rate`: optional MP3 bit rate.
- `enable_timestamp`: default `true`.
- `return_usage`: default `true`, requests usage metadata when available.
- `explicit_language`: optional language hint such as `zh-cn`, `en`, or `crosslingual`. Leave unset unless needed.
- `context_texts`: optional list of context/style strings, when supported by the endpoint and voice.
- `silence_duration`: optional trailing silence in milliseconds.
- `enable_language_detector`, `disable_emoji_filter`, `max_length_to_filter_parenthesis`, `unsupported_char_ratio_thresh`: optional provider additions.
- `mute_cut_threshold` and `mute_cut_remain_ms`: optional mute-cut controls.
- `extra_audio_params` and `extra_additions`: advanced escape hatches for newly documented Doubao fields. Use these only when the field is in the current Volcengine docs.

Do not pass `additions.explicit_language` by default. Some endpoint/key combinations reject `zh-cn` with `unsupported additions explicit language zh-cn`.

For calm Mandarin explainers, start with `speech_rate: 0`. If the result is too long for the approved format, make a short comparison sample with `speech_rate: 25` or `50` before regenerating the full narration. Do not speed up only to match a previous provider's duration if the user prefers Doubao's natural pace.

For production narration where Doubao sounds too theatrical, keep the line in the script and adjust controls before rewriting:

```python
result = DoubaoTTS().execute({
    "text": "大家好，我是 Ray 的 AI 助理。有一天，Ray 发来一段很长的安装指令。",
    "voice_id": "zh_female_vv_uranus_bigtts",
    "speech_rate": 8,
    "emotion": "neutral",
    "emotion_scale": 1,
    "post_process_pitch": 2,
    "output_path": "projects/my-video/assets/audio/tone_test.mp3",
})
```

## Troubleshooting

- `load grant: requested grant not found`: wrong key type or wrong auth header. Use `X-Api-Key` for new-console API Keys.
- `speaker permission denied`: voice id is wrong or not authorized for the selected resource.
- `quota exceeded`: quota, lifetime characters, or concurrency exceeded.
- Missing timestamps: verify `enable_timestamp: true`, keep the query JSON, and confirm the selected endpoint returned `sentences`.

## Safety

Never print or write the API key to logs, metadata, patches, or project artifacts. `.env.example` should contain only empty variable names.
