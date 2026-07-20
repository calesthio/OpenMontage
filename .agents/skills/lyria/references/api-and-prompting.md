# Lyria 3 API and Prompting Reference

Last verified: 2026-07-18.

## Provider Families

### Lyria 3 Clip

- Model: `lyria-3-clip-preview`
- Best for: prompt iteration, previews, loops, short cues
- Input: text or images
- Output: MP3 audio plus text containing lyrics or song structure
- Duration: always 30 seconds
- Gemini Developer API price: $0.04 per request; no free tier

### Lyria 3 Pro

- Model: `lyria-3-pro-preview`
- Best for: full songs, vocals, verses, choruses, bridges, longer scores
- Input: text or up to 10 images through the underlying API
- Output: MP3 by default; the underlying Pro API can request audio/WAV response format
- Duration: prompt-influenced, up to roughly three minutes; not an exact media contract
- Gemini Developer API price: $0.08 per request; no free tier

### Lyria RealTime

- Model: `lyria-realtime-exp`
- Experimental, instrumental, persistent WebSocket session
- Supports continuous steering of BPM, scale, density, brightness, and guidance
- Not the Interactions API and not the model used by OpenMontage `google_music`

## Interactions API Shape

Python:

```python
from google import genai

client = genai.Client()
interaction = client.interactions.create(
    model="lyria-3-pro-preview",
    input="A structured instrumental score ...",
)

audio = interaction.output_audio
text = interaction.output_text
```

The convenience properties are preferred for ordinary responses. For interleaved responses, iterate `interaction.steps`; inspect `model_output` content blocks and keep `audio` and `text` blocks separate.

The OpenMontage adapter currently:

- sends a list containing one text block and optionally one image block;
- appends `[Target Duration: N seconds]` to the text;
- calls `client.interactions.create()` with `lyria-3-pro-preview`;
- extracts audio through `output_audio`, then legacy outputs, then step traversal;
- writes MP3 and reports the requested duration without probing the result.

## Prompt Template: Video Underscore

```text
Create an original instrumental background score for [purpose], target [N] seconds.

Style: [genre/blend/era], [mood], [foreground or background role].
Tempo and harmony: [BPM], [meter], [key/scale or tonal behavior].
Instrumentation: [lead], [rhythm], [bass], [texture].

[0:00-0:06] [one musical state and entrance rule].
[0:06-0:12] [one development].
[0:12-0:15] [build or reduction that prepares the sync point].
[0:15-0:18] [exact synchronization event and required hold].
[0:18-0:30] [release and ending behavior].

Mix: [density, space, transient character, dynamic range].
Ending: [tail, final resonance, no abrupt cutoff].
Instrumental only. No vocals, speech, choir, humming, vocal chops,
spoken samples, lyrical fragments, or recognizable quotations.
Avoid: [unwanted instruments, clichés, oversized hits, abrupt fade].
```

Use timestamps as structural instructions, not as proof that Pro will return an exact-length file.

## Prompt Template: Song With Custom Lyrics

```text
Create a [duration] [genre] song in [key] at [BPM].
Vocal profile: [range, tone, delivery, language].
Instrumentation and production: [details].
Structure: [Intro], [Verse], [Chorus], [Bridge], [Outro].

Lyrics:
[Verse 1]
...

[Chorus]
...
```

Separate lyrics from production direction. Use round brackets only when backing-vocal echoes are desired.

## Vocals And Custom Lyrics

Lyria generates vocals and lyrics unless the prompt clearly requests an instrumental. Google recommends a detailed singer profile covering voice type or gender presentation, timbre, and vocal range. The model generates lyrics in the language of the prompt, and an explicit language instruction can override that default.

For a vocal song, specify:

- **Role:** solo lead, duet, call-and-response, backing ensemble, or wordless texture.
- **Profile:** range, timbre, delivery, diction, intensity, ornamentation, and register changes.
- **Language:** the sung language, intended register, and whether any code-switching is allowed.
- **Section map:** where vocals begin, where harmonies enter, which passage is instrumental, and how the vocal exits.
- **Backing policy:** use parentheses only for intentional echoes or backing singers.
- **Exclusions:** unwanted choir, spoken phrases, ad-libs, humming, vocal chops, or named-artist imitation.

Keep production direction outside the lyric block:

```text
Create a [duration] [genre] song in [key] at [BPM].
Vocal role: [solo, duet, call-and-response, or ensemble].
Singer profile: [range], [timbre], [delivery], and [diction].
Sing in [language and intended register]. Use backing vocals only for words
shown in parentheses. No [unwanted vocal gestures or effects], and do not
imitate a named singer.

Lyrics:
[Verse 1]
[custom lyrics in the selected language and script]

[Chorus]
[lead line] ([intentional backing-vocal echo])
```

### Multilingual Work

- Name the sung language explicitly even when custom lyrics make it apparent.
- Choose the writing system or transliteration deliberately; do not convert scripts without user approval.
- Keep one script inside a lyric version so the model does not infer accidental language switches.
- Describe the intended register, dialect, formality, and any intentional code-switching.
- Preserve the approved lyric text separately from the generation prompt. Lyria may alter, omit, or repeat words, so compare the returned text and audible performance against that source.
- Treat pronunciation and language coverage as output-level QA. The API documentation says Lyria follows the prompt language, but it does not promise perfect diction for every language or regional register.

### Vocal QA

Audition and record:

1. Whether the requested lead, duet, or ensemble roles are present.
2. Whether every approved lyric line is sung, omitted, altered, or repeated.
3. Whether the language, script-derived pronunciation, and intended register remain consistent.
4. Whether the requested range, timbre, dynamics, ornamentation, and section entrances are followed.
5. Whether backing vocals appear only where requested.
6. Whether the lead remains intelligible against the arrangement without clipping or masking.
7. Whether the ending contains a complete final phrase and musically useful decay.

Do not classify a diction or lyric-adherence failure as a file-format problem. It is a stochastic prompt/adherence failure; any retry is a new paid generation and requires the approved retry policy.

## Image-To-Music

The underlying API accepts up to 10 base64-encoded images with MIME types. Prompt for the musical interpretation explicitly: mood, palette-to-timbre mapping, motion-to-rhythm mapping, and the desired structure. The current OpenMontage adapter accepts one `image_path` or one `image_url`.

## Limitations And Safety

- Generation is stochastic; identical prompts can differ.
- Lyria 3 is single-turn; generated tracks cannot currently be refined through a multi-turn edit chain.
- Safety filters may reject artist-voice imitation, copyrighted lyrics, or other restricted content.
- All generated audio contains an imperceptible SynthID watermark.
- Preview models and rate limits can change before stable release.
- Official pages currently disagree between 44.1 kHz and 48 kHz descriptions. Probe every returned file and record the observed value.

## Failure Triage

| Symptom | Class | Action |
|---|---|---|
| `401` or invalid key | Auth | Verify the selected credential without printing it |
| `403`, `API_KEY_SERVICE_BLOCKED` | Auth/project policy | Stop retries; fix the Google key, project, API enablement, or service restriction |
| `429` | Rate limit | Retry only within the approved retry/budget policy |
| Timeout | Transient/provider | Use the tool timeout policy; do not launch parallel duplicate paid calls |
| No `output_audio` | Response parsing | Traverse `model_output` step content for an `audio` block |
| Output longer/shorter than requested | Model behavior | Preserve source, probe, and create a separate exact-duration master |
| Accidental vocals | Prompt/adherence | Strengthen the full instrumental exclusion list; audition the next paid result |
| Safety rejection | Policy/prompt | Remove artist imitation or copyrighted material; do not disguise the request |

## Official Sources

- Gemini API music generation: https://ai.google.dev/gemini-api/docs/music-generation
- Gemini Interactions API: https://ai.google.dev/gemini-api/docs/interactions-overview
- Gemini Developer API pricing: https://ai.google.dev/gemini-api/docs/pricing
- Google DeepMind Lyria prompt guide: https://deepmind.google/models/lyria/prompt-guide/
- Lyria RealTime: https://ai.google.dev/gemini-api/docs/realtime-music-generation
- Google announcement for Lyria 3 Pro: https://blog.google/innovation-and-ai/technology/ai/lyria-3-pro/
