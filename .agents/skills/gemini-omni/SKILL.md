---
name: gemini-omni
description: |
  Generate and conversationally edit short videos with stable Google Gemini Omni Flash (`gemini-omni-1.1-flash`). Use when: (1) iterating on a clip with natural-language edits instead of regenerating ("make the phone invisible, keep everything else the same"), (2) generating 3-10s 720p clips with synthesized audio, rendered on-screen text, or timecoded beats, (3) binding reference images to roles with <FIRST_FRAME>/<IMAGE_REF_N> prompt tags, (4) editing an existing uploaded video. Accessed via the `gemini_omni_video` tool using the project's GEMINI_API_KEY/GOOGLE_API_KEY — the same key as Imagen and Google TTS.
allowed-tools: Bash, Read, Write
metadata:
  openclaw:
    requires:
      env_any:
        - GEMINI_API_KEY
        - GOOGLE_API_KEY
---

# Gemini Omni Flash (Google DeepMind)

Gemini Omni is Google DeepMind's video generation **and editing** model family. The OpenMontage direct adapter uses the generally available **Gemini Omni 1.1 Flash** model (`gemini-omni-1.1-flash`) through the Gemini **Interactions API**. Its implemented baseline generates 3–10 second clips at 720p/24fps with synthesized audio. Its differentiator in the OpenMontage fleet is **stateful conversational editing**: each stored generation returns an `interaction_id`, and a follow-up call with `previous_interaction_id` edits that video in place — no other wrapped provider can refine a clip without regenerating it.

OpenMontage wraps it as `gemini_omni_video` (native Gemini API, no gateway). It shares `GOOGLE_API_KEY`/`GEMINI_API_KEY` with `google_imagen` and `google_tts` — one key, three capabilities. Paid tier only: ~$0.10 per second of output video (exactly 5,792 output tokens/sec at $17.50/1M, before input and any text/thought output).

Other documented routes are available when the direct Google key is not the
chosen provider:

| Route | OpenMontage call | Important limitation |
|-------|------------------|----------------------|
| fal.ai | `gemini_omni_fal` | T2V, I2V, reference video, and edit endpoints; no Google interaction ID is returned |
| Runway | `runway_video`, `model: "gemini_omni_flash"` | T2V/I2V/V2V; video edits accept up to five image references |
| ComfyUI Partner Node | Not a stable 1.1 fallback in this adapter | The existing `GeminiVideoOmni` mapping targets the legacy preview node; migrate it separately to `GeminiVideoOmniV2` before claiming Omni 1.1 support |

Use the direct `gemini_omni_video` route for stateful conversational editing.
Gateway routes return ordinary provider tasks and cannot preserve Google's
`previous_interaction_id` workflow. The fal edit endpoint can still be iterated
by feeding each output video URL into the next edit call.

## When to pick it (and when not)

| Use it for | Prefer another provider for |
|---|---|
| Iterative refinement — generate, review, then edit the same clip in layers | One-shot cinematic hero clips (→ Seedance 2.0, see `seedance-2-0`) |
| Editing an existing/uploaded clip (restyle, add/remove objects, change text) | Clips longer than 10s or above 720p |
| On-screen rendered text and word-by-word text beats | Seed-reproducible generations (no seed support) |
| Reference-image-bound subjects/styles via prompt tags | First/last-frame interpolation (→ `veo_video`) |
| Timecode-scheduled multi-beat clips from one prompt | Non-English narration (English only fully supported) |

Route through `video_selector` for generation operations. **Editing (`edit_video`) is a direct-tool operation** — call `gemini_omni_video` from the registry, because the multi-turn interaction state lives outside the selector's model.

## Billing and duration hints

- `duration` is only a planning/prompt hint for the caller. The adapter does not send it to Google; express timing in the prompt or timecodes, and let the model choose the actual length. It does not cap billing.
- `ToolResult.cost_usd` uses valid response `usage` when available: input tokens are $1.50/1M for every modality, output text is $9.00/1M, and output video is $17.50/1M. Unknown/unclassified output and separately reported thought tokens use the higher $17.50/1M rate so the result cannot underreport.
- Without valid usage, the fallback assumes the maximum 10-second output: `10 × 5,792 × $17.50/1M = $1.0136`, plus a conservative upper estimate for prompt and available media input tokens. A short `duration` hint never reduces this fallback.

## Generation prompting

Describe **scene + camera + lighting + motion + audio**. Official example:

> Continuous, unbroken handheld shot of a fluffy tabby cat sitting on a sunny windowsill, looking out into a leafy garden. The cat's tail twitches slowly, and its ears rotate slightly toward ambient noises. Sunbeams illuminate dust motes in the air.

- **Force a single shot** explicitly: "In a single continuous shot," / "No scene cuts." Otherwise the model may cut between scenes.
- **Negatives go in prose** — there is no `negative_prompt` parameter: "No dialogue," "No extra sound effects."
- **No sampler controls**: system instructions, temperature, top_p, and seeds are all unsupported. The prompt is the only lever.
- **Meta-prompt for quality**: "Consider micro-detail, expression and timing to create a very rich, detailed but entirely natural scene."

### Timecode syntax

Schedule beats with bracketed ranges or natural language — this maps directly onto OpenMontage scene-plan timings:

```
[0-3s] A person is walking [3-6s] They stop and turn around
```

> "After 3 seconds, a woman enters the scene." / "At 5s the chorus starts in the background audio."

### Audio and on-screen text

Audio is synthesized automatically; direct it in the prompt: "Include calm background music," "The audio is a low tinny radio broadcast in the background." Rendered text works and can be timed:

> One word on the screen at a time: 'did, you, know, that, Omni, can, do, awesome, text?' Each word appears for 1s.

## Reference images (`<FIRST_FRAME>` / `<IMAGE_REF_N>` tags)

Pass local images via `reference_image_paths` (they are sent in order), then bind them to roles **inside the prompt** with tags. `<IMAGE_REF_N>` indexes from 0 in the order supplied:

```
in the style of <IMAGE_REF_0> a woman <IMAGE_REF_1> is walking
```

```
[0-3s] A studio fashion sequence. Starting with woman <IMAGE_REF_0>, she is
holding <IMAGE_REF_1> [3-6s] Then we see the man <IMAGE_REF_2> holding <IMAGE_REF_3>
```

- `<FIRST_FRAME>` makes an image the opening frame: `<FIRST_FRAME> a woman is walking`.
- Use high-resolution images; describe the intended motion specifically rather than "make it move."
- Say what each image *is* (product / character / style / background reference) — the model decides usage from context.

## Conversational editing (the differentiator)

**Editing prompts are the opposite of generation prompts: short and surgical.** Overly descriptive edit prompts cause unintended changes.

1. Generate the base clip (subject + scene + motion). The tool returns `interaction_id` in its result data.
2. Pass it back as `previous_interaction_id` with `operation="edit_video"` and describe **only the delta**.
3. Append **"Keep everything else the same."** to pin unmentioned elements.
4. Refine in layers — one turn for lighting, one for camera, one for action, one for audio.

Official good/bad pairs:

| Avoid | Instead |
|---|---|
| "In the video of the man sitting on the sofa, please add a small black cat..." | "Add a cat that jumps onto his lap, he begins to pet it. Keep everything else the same." |
| "Please remove the cell phone... and fill in the background so it looks like..." | "Make the phone invisible. Keep everything else the same." |

Other working edit prompts: "Make this video anime" / "Put a fashionable hat on this person" / "Change the lighting to be more dramatic" / "Change the text on the sign to say 'Omni Flash'".

**Gotcha — `store`:** editing via `previous_interaction_id` only works if the *prior* call kept the interaction server-side (`store` defaults to true in `gemini_omni_video`). Set `store=false` only for one-shot generations you will never edit.

**Download recovery:** after an accepted paid generation, a Files API poll or download can still fail. In that case the tool returns `output_uri`, the usage-based charged cost when valid usage was returned (otherwise the conservative fallback), and a `resume_download` payload. Pass that payload back to `gemini_omni_video` to retry only the existing file's GET/poll flow; it must not submit another paid generation.

**Editing uploaded videos:** pass `input_video_path` instead of `previous_interaction_id`; the tool uploads it via the Files API. Unavailable in the EEA, Switzerland, and the UK (editing *generated* videos works everywhere).

## Current adapter limitations (stable model)

- Output: 3-10s, 720p, 24fps, MP4 with audio; aspect ratio `16:9` or `9:16`. All output carries an invisible SynthID watermark.
- No seed, negative prompt, temperature, top_p, or system instructions.
- The stable Google model supports video extension, first/last-frame interpolation, and additional resolutions, but this OpenMontage adapter has not implemented those controls. Do not advertise them as working direct-tool features. No voice editing.
- Audio reference inputs unsupported. Video references ≤3s are accepted by the schema but **not processed correctly** — don't rely on them.
- Multi-video prompting unsupported; may degrade output.
- English fully supported; other languages untested.
- Images of minors (EEA/CH/UK) and certain recognizable people are blocked for upload/editing.

## Sources

- Generation & editing guide: https://ai.google.dev/gemini-api/docs/omni
- Model card: https://ai.google.dev/gemini-api/docs/models/gemini-omni-flash
- Pricing: https://ai.google.dev/gemini-api/docs/pricing
- Announcement: https://blog.google/innovation-and-ai/models-and-research/gemini-models/gemini-omni/
