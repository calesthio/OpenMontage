---
name: lyria
description: Generate and validate music with Google Lyria 3 through the Gemini Interactions API. Use before calling OpenMontage `google_music`, designing Lyria 3 Clip or Pro prompts, using image-to-music or custom lyrics, choosing between Lyria 3 and Lyria RealTime, diagnosing Google music-generation failures, or preparing exact-duration music for a video.
---

# Google Lyria 3

Use Lyria 3 as a single-turn music generator. Keep it distinct from Lyria RealTime, which is an experimental WebSocket model for continuously steered instrumental performance.

Read [references/api-and-prompting.md](references/api-and-prompting.md) when choosing a model, designing vocals or custom lyrics, using image inputs, debugging the response, or checking current limits and pricing.

## Required Workflow

1. Confirm the intended role: underscore, loop, instrumental cue, or full song.
2. Confirm vocals, language, target duration, musical structure, and delivery format.
3. Announce the provider, exact model, estimated per-request cost, and whether the call is exploratory or final.
4. Write one structured prompt using the contract below.
5. Make one approved generation call. Treat a retry as another potentially billable stochastic generation.
6. Preserve the returned provider source unchanged.
7. Probe the actual file and listen before recording duration, format, or approval metadata.
8. Derive a separate production master when the edit requires an exact duration.

## Choose The Model Deliberately

| Need | Model | Contract |
|---|---|---|
| Prompt iteration, preview, loop, exact 30-second source | `lyria-3-clip-preview` | Always generates a 30-second MP3; currently $0.04/request |
| Full song, vocals, longer structure, image-conditioned score | `lyria-3-pro-preview` | Prompt-influenced duration up to roughly three minutes; currently $0.08/request |
| Live, continuously steered instrumental performance | `lyria-realtime-exp` | Separate WebSocket workflow; do not route through `google_music` |

The current OpenMontage `google_music` adapter is locked to `lyria-3-pro-preview`. It does not expose Clip, WAV response selection, multiple images, or RealTime controls. Surface that limitation rather than implying those options are available through the adapter.

Do not change models silently. For a 30-second video, either obtain approval for Pro plus exact-duration mastering or use Clip through an explicitly supported path.

## Build The Prompt

Specify, in this order:

1. **Purpose and duration** — what the music supports and the requested length.
2. **Genre and era** — use musical vocabulary, not a living artist imitation.
3. **Tempo and harmony** — BPM or tempo range, meter, key or tonal center.
4. **Instrumentation and texture** — name lead, rhythm, bass, and ambient layers.
5. **Structure** — timestamped sections or `[Intro]`, `[Verse]`, `[Chorus]`, `[Bridge]`, `[Outro]`.
6. **Dynamics and synchronization** — entrances, rests, builds, hits, and holds tied to edit times.
7. **Vocal policy** — instrumental-only constraints, a vocal profile, or clearly separated custom lyrics.
8. **Mix and ending** — density, foreground/background role, headroom character, and final decay.
9. **Exclusions** — unwanted vocals, instruments, gestures, clichés, abrupt endings, or copyrighted material.

For video underscore, use timestamp windows that cover the full requested duration. Ask for one primary change per window and identify the exact synchronization moment.

For instrumental-only output, say all of the following when they matter:

```text
Instrumental only. No lead or backing vocals, speech, choir, humming,
vocal chops, spoken samples, lyrical fragments, or recognizable quotations.
```

For custom lyrics, put performance direction before a separate `Lyrics:` block and use section labels. Prompt in the language the singer should use.

## Direct Vocals Deliberately

When vocals are requested, define these before writing the prompt:

1. **Vocal role** — solo lead, duet, call-and-response, backing ensemble, or vocal texture.
2. **Language and script** — name the sung language and keep the custom lyrics in one intentional script; do not silently transliterate or code-switch.
3. **Singer profile** — voice type or range, timbre, intensity, diction, ornamentation, and emotional distance. Do not imitate a named artist.
4. **Section behavior** — state where the lead enters, where harmonies or echoes appear, and which sections remain instrumental.
5. **Lyric contract** — separate directions from a `Lyrics:` block, use `[Verse]`, `[Chorus]`, `[Bridge]`, and `[Outro]`, and reserve parentheses for intentional backing-vocal echoes.

Treat the returned vocal as untrusted until auditioned. Check lyric adherence, language drift, pronunciation, intelligibility, unwanted backing vocals, vocal/instrument balance, and whether the performance follows the requested emotional arc. A technically valid file with poor diction or altered lyrics is not an approved vocal result.

## Treat Duration As Untrusted Until Probed

Lyria 3 Pro duration is controlled through prompt instructions and timestamps, not an exact API parameter. The OpenMontage adapter appends a target-duration instruction, but its returned `duration_seconds` field is the request, not a media probe.

Always inspect the generated file:

```bash
ffprobe -v error -show_entries \
  format=duration,format_name,bit_rate:stream=codec_name,sample_rate,channels \
  -of json output.mp3
```

If exact duration is required:

- keep the provider source untouched;
- record requested and measured durations separately;
- derive a new master by trimming at a musically sensible boundary and applying a short fade;
- do not stretch, loop, or regenerate without the approved production plan;
- record the derivation and probe the master again.

## Authenticate And Diagnose Safely

The Gemini API commonly uses `GEMINI_API_KEY`. OpenMontage also supports `GOOGLE_API_KEY` and Vertex service-account credentials.

- Use one known credential path per run.
- Never print keys or edit credential files while debugging.
- Do not assume a rejected first key will fall through to a second configured key.
- In the current OpenMontage resolver, `GOOGLE_API_KEY` takes precedence over `GEMINI_API_KEY` when both are non-empty.
- Treat `403`, `API_KEY_SERVICE_BLOCKED`, and project/service restrictions as authentication or Google-project configuration failures, not prompt-quality failures.
- Do not spend retries on permission failures. Resolve the credential/project path first.
- Retry only transient rate-limit or timeout failures within the approved retry and budget policy.

## Parse And Record The Result

Prefer `interaction.output_audio`. For interleaved responses, traverse `model_output` steps and select the audio block; capture output text separately if lyrics or a structure description are relevant.

Record:

- provider and exact model;
- original prompt and any image provenance;
- requested duration and probed duration;
- actual codec, sample rate, channels, and file path;
- cost per call and total attempts;
- whether vocals were requested and whether any were detected by listening;
- the provider source and any separately derived production master.

## Quality Checklist

- The prompt states purpose, tempo, instruments, structure, dynamics, vocal policy, and ending.
- Timestamp windows cover the intended runtime without contradictions.
- No artist impersonation or copyrighted lyrics are requested.
- The output file exists, is non-empty, decodes, and contains an audio stream.
- Actual duration and technical properties come from a probe, not request metadata.
- Instrumental output is checked for accidental vocal material.
- The opening, synchronization moments, transitions, and ending are auditioned.
- The untouched source is preserved and any production master has explicit provenance.
- SynthID watermarking and preview-model instability are acknowledged where provenance matters.
