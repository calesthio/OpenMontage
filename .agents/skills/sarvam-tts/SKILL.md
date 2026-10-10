---
name: sarvam-tts
description: Generate Indian-language and Indian-English narration with Sarvam AI's Bulbul text-to-speech models. Use when a video is narrated in Hindi, Tamil, Telugu, Bengali, Marathi, Gujarati, Kannada, Malayalam, Punjabi or Odia, when the script is code-mixed Hinglish, or when Indian-English narration must not sound American. Optional cloud TTS provider — preferred when SARVAM_API_KEY is configured; the local piper_tts remains the default offline path.
license: MIT
compatibility: Requires internet access and a Sarvam AI API key (SARVAM_API_KEY).
metadata: {"openclaw": {"requires": {"env": ["SARVAM_API_KEY"]}, "primaryEnv": "SARVAM_API_KEY"}}
---

# Sarvam AI — Text-to-Speech (Bulbul)

Generate narration with **Sarvam Bulbul** — neural TTS built for English and
22 Indic languages, with speakers that read Devanagari, Tamil, Telugu, Bengali
and code-mixed Hinglish natively instead of approximating them through an
English phoneme set. In OpenMontage this is the `sarvam_tts` tool
(`capability=tts`, `provider=sarvam`).

**Reach for it when** the deliverable is for an Indian audience: Hindi or
regional-language narration, Indian-English brand voice, or a script that mixes
English product terms into an Indic sentence ("aapka **dashboard** ready hai").
For American/European accents or voice cloning, `elevenlabs_tts`, `google_tts`
and `azure_tts` remain better picks; `piper_tts` remains the offline default.

> Docs: [Text-to-speech API](https://docs.sarvam.ai/api-reference/text-to-speech/convert) · [Pricing](https://docs.sarvam.ai/api/getting-started/pricing) · [Dashboard](https://dashboard.sarvam.ai/)

## Setup

```bash
export SARVAM_API_KEY=your_sarvam_subscription_key
# export SARVAM_API_BASE_URL=https://api.sarvam.ai   # optional host override
# export SARVAM_INR_PER_USD=88                       # optional: cost reporting rate
```

`sarvam_tts` reports `AVAILABLE` as soon as `SARVAM_API_KEY` is set. New Sarvam
accounts include ₹100 of free credits — enough for roughly 33,000 characters of
Bulbul v3 narration.

**Network note:** the tool talks to `api.sarvam.ai`. In sandboxes or corporate
networks with an egress allowlist, that host must be allowed or every call
fails at the CONNECT stage before the key is ever checked.

## Models

| Model | Speakers | Controls | Max chars/request |
|---|---|---|---|
| `bulbul:v3` (default) | 37 — `shubh` (default), `ritu`, `priya`, `neha`, `rahul`, `kavya`, `aditya`, `pooja`, `rohan`, `simran`, `amit`, `dev`, `ishita`, `shreya`, … | `pace` 0.5–2.0, `temperature` 0.01–2.0, `dict_id` | 2500 |
| `bulbul:v2` (legacy) | 7 — female `anushka`, `manisha`, `vidya`, `arya`; male `abhilash`, `karun`, `hitesh` | `pace` 0.3–3.0, `pitch` −0.75–0.75, `loudness` 0.1–3.0, `enable_preprocessing` | 1500 |

Speaker names are **lowercase and model-specific** — a v2 speaker on v3 is a
400 from the API. `sarvam_tts` validates the pairing before spending a call and
returns the valid roster in the error.

`pitch`, `loudness` and `enable_preprocessing` exist only on v2; `temperature`
and `dict_id` only on v3. The tool drops the parameters that don't apply to the
selected model rather than letting the API reject the request.

## Using it in a pipeline

Route through `tts_selector` as usual (it auto-discovers `sarvam_tts` and maps
`voice_id` → `speaker`, `speaking_rate` → `pace`, `language_code` → 
`target_language_code`), or call the provider tool directly once the user has
approved Sarvam:

```python
from tools.tool_registry import registry
registry.discover()
tts = registry._tools["sarvam_tts"]

result = tts.execute({
    "text": "हर महीने 10,000 से ज़्यादा छात्र यही सवाल पूछते हैं।",
    "target_language_code": "hi-IN",
    "model": "bulbul:v3",
    "speaker": "ritu",
    "pace": 0.95,             # a touch slower reads as more authoritative
    "temperature": 0.5,       # steadier delivery for narration
    "output_path": "projects/my-video/assets/audio/seg_001.wav",
    "output_format": "wav",   # wav is native; mp3 is transcoded locally
})
```

Scripts longer than the model's ceiling are split on sentence boundaries,
synthesized chunk by chunk, and joined into a single lossless WAV — pass a
whole narration section and let the tool handle the limit.

## Writing scripts Bulbul reads well

- **Numbers over four digits take commas** — `10,000`, not `10000`, or the
  model reads it digit by digit.
- **Code-mixing is a feature, not a workaround.** Write English product terms
  in Latin script inside the Indic sentence; Bulbul switches registers cleanly.
  Do not transliterate English words into Devanagari to "help" it.
- **Punctuate for breath.** Bulbul has no SSML and no `<break>` tag — sentence
  breaks, commas and em dashes are the only pacing instrument. Short sentences
  land harder than `pace` tweaks.
- **Spell out what should sound spelled out.** Acronyms read as words unless
  separated (`A I` vs `AI`); for a recurring brand or term, a v3 pronunciation
  dictionary (`dict_id`) is steadier than respelling it in every segment.
- **Match the language code to the script.** Devanagari text with
  `target_language_code: "en-IN"` produces mangled output — set `hi-IN`.

## Choosing a delivery

| Register | Settings |
|---|---|
| Calm explainer / founder voice | `pace` 0.9–1.0, `temperature` 0.4–0.6 |
| Energetic promo / social hook | `pace` 1.05–1.15, `temperature` 0.7–0.9 |
| Steady corporate / compliance | `pace` 0.9, `temperature` 0.3 |

Higher `temperature` buys expressiveness at the price of occasional artifacts —
audition a single line before batching a whole script, and keep the sample in
the project workspace so the approval is reviewable.

## Multi-language variants

One script, several languages, is Sarvam's strongest use in OpenMontage: run
the same `scene_plan` and re-narrate per language with a per-language speaker,
then re-render. Keep the visual timing loose (or re-time from the generated
audio durations) — Hindi narration typically runs 10–20% longer than the same
line in English.

## Pricing

Bulbul v3 bills **₹30 per 10,000 characters** (~$0.0034 per 1,000 characters at
₹88/USD). A 150-word narration segment costs roughly ₹2.7 (~$0.03). Sarvam's
speech, translate and STT APIs bill separately — see the pricing page for
current rates. `sarvam_tts` estimates `cost_usd` from character count and the
`SARVAM_INR_PER_USD` rate.

Shipping generated audio commercially is covered by Sarvam's commercial
licensing terms — check them before publishing a monetized video.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 403 at CONNECT / tunnel failure | `api.sarvam.ai` not on the network's egress allowlist | Allow the host; this is not an API-key problem |
| HTTP 403 with a JSON body | Invalid or exhausted key | Check the key and remaining credits in the dashboard |
| HTTP 422 | Speaker/model mismatch, or a v2-only field sent to v3 | Use the tool's parameters — it filters per model |
| HTTP 429 | Plan rate limit (Starter = 60 req/min) | The tool retries with backoff; batch narration sequentially |
| Digits read one by one | Number written without commas | `10,000` not `10000` |
| Flat or robotic delivery | `temperature` too low, or the sentence is too long | Raise to 0.6–0.8; split the sentence |
