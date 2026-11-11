# Provider and model update plan — 3 October 2026

## Implementation status

Implemented on `codex/provider-model-refresh`, based on main `08e2151f`.
The research below is preserved as the original plan; this table records the
actual implementation and supersedes proposed file names or uncertain endpoints.

| Family | Implemented tools and behavior |
| --- | --- |
| Avatar V (Avatar 5) | `heygen_avatar`: v3 look discovery, eligibility checks, explicit V/IV engine, script or supplied audio, same-group reference look, polling/download/resume. Added to avatar-spokesperson. |
| Eleven v4 / Turbo | `elevenlabs_tts`: exact model IDs, input limits, continuity fields, proper PCM-to-WAV wrapping. `fal_elevenlabs_tts`: exact v4 endpoint and schema, no unsupported speed/style, persisted queue jobs and resume. |
| Wan 3.0 | `wan_fal_video`, `wan_atlas_video`, `wan_replicate_video`: host-specific contracts. Text/image/reference on fal and Atlas; text/image only on Replicate. Atlas is a separate adapter to preserve the established Atlas catalog's behavior. |
| GPT Image 2.5 | `openai_image`: both variants, generate/edit, local references/masks, transparency, usage metadata. `openai_fal_image` and `atlas_refresh_image`: both variants and edit routes. |
| Google Pro image | `google_imagen`: Gemini 3 Pro Image and 3.1 Flash Image, local references and resolution. Nano Banana Pro also through `gemini_fal_image`, `gemini_replicate_image`, `atlas_refresh_image`. Replicate fallback explicitly disabled. |
| Ideogram 4.5 | `ideogram_image`: direct generation/edit/Precise Edit and dry-run quotes. `ideogram_fal_image`: generation/edit with Precise Edit mapped to verified `edit_precision=high`. |
| Other video | `h3_max_video`: fal text/image/reference routes. `ltx_api_video`: direct Fast/Pro text/image/audio generation, exact duration/FPS/resolution restrictions and resume. |
| Other audio | `gemini_tts`: 3.8 Flash/Flash-Lite, single/multi-speaker Interactions, WAV, API-key voice-library discovery. `google_music`: explicit Lyria 3.5. `cartesia_tts`: Sonic 3.6 with API version 2026-08-14. `inworld_tts`: TTS-2 and Flash with usage metadata. |
| Local | `qwen_image_21`: official local Diffusers generation/edit/RGBA, no implicit weight downloads. `comfyui_video` recognizes `ltx_2.5_local` only with a supplied API workflow; refuses older-model fallback. |
| Routing | Explicit tool/host/model filters, same-host tools ranked by tool name, unsupported edit requests rejected, unknown prices no longer score as free. |

Validation uses mocked API requests and captured official input schemas. No paid
generations, voice cloning, avatar creation, or model-weight downloads were run.
`cost_usd=null` means unquoted/unreconciled, not free; current prices and account
entitlements still need to be checked for production. OpenAI token usage and
Inworld usage are retained; full billing reconciliation is not claimed.

Remaining external gates: Kling 4/Flash has no verified public execution contract
in this research; local LTX-2.5 needs installed weights and an exported workflow;
Qwen needs compatible CUDA/Diffusers and downloaded weights. Gemini Live remains
the separately scoped streaming/session integration from the original plan.

Contract sources: [fal OpenAPI](https://fal.ai/api/openapi/queue/openapi.json),
[Atlas model pages](https://www.atlascloud.ai/models),
[Replicate Wan schema](https://replicate.com/alibaba/wan-3/api/schema),
[Replicate Nano Banana Pro schema](https://replicate.com/google/nano-banana-pro/api/schema),
[LTX OpenAPI](https://docs.ltx.io/openapi.json),
[Ideogram 4.5](https://developer.ideogram.ai/api-reference/images/generate/ideogram-4-5),
[HeyGen Avatar V](https://developers.heygen.com/avatar-v),
[Cartesia TTS](https://docs.cartesia.ai/api-reference/tts/bytes),
[Inworld model IDs](https://docs.inworld.ai/docs/tts/tts-models),
[Qwen model card](https://huggingface.co/Qwen/Qwen-Image-2.1).

Research window: **3 September–3 October 2026**, with adjacent/older releases separated below. Scope: media generation, editing, narration, music, avatars, and useful local alternatives. General-purpose chat models are outside this provider-update scope.

Baseline: `main` fast-forwarded from `51330d17` to `08e2151f` (123 commits). Registry discovery and implementation inspection completed. This is a researched implementation plan, not a claim that new integrations have been exercised against paid APIs. Priorities reflect production usefulness and breadth of access; no comprehensive, comparable usage ranking was available, so “popular” is a shortlist rather than a measured market-share ranking.

## 1. Additions beyond the requested models

| Priority | Model | Release evidence | Provider path | Work and value |
|---|---|---|---|---|
| P1 | **Qwen Image 2.1** | September 20, official Qwen announcement | Evaluate official weights through local/ComfyUI first. Verify a named DashScope or aggregator endpoint before advertising cloud support. | Unified generation/editing and native transparency: useful for reusable foreground assets, overlays and targeted edits. Current `dashscope_image` lists 2.0 Pro; no explicit 2.1 integration found. |
| P1 | **Gemini 3.8 Flash TTS + Flash-Lite TTS** | September 22 GA, Gemini changelog | Google Gemini API | Add `gemini_tts` as a distinct adapter. Current `google_tts` uses Cloud Text-to-Speech, so changing a model string there is insufficient. Add voice discovery, speaker turns, delivery controls and audio-format handling. |
| P1 | **Lyria 3.5** | September 3 GA, Gemini changelog | Google Gemini API | Upgrade `google_music`, currently built around `lyria-3-pro-preview`. Add explicit model selection; validate duration, structure, vocals, image conditioning, output encoding and costs against the new contract. |
| P1 discovery; gated implementation | **Kling 4.0 + 4.0 Flash** | Late-September announcement; fal page dated September 29 | Kling direct and fal early access; Atlas only after endpoint verification | Plan text/image/reference generation and video editing. Keep variants distinct. Do not expose as generally available until account access and exact request schemas are verified. |
| P3 / separate product scope | **Gemini 3.8 Live + Live Extended Thinking** | September 15 GA, Gemini changelog | Google Live API | Useful for interactive voice/avatar experiences, but not required for offline video narration. Requires session lifecycle and streaming audio; defer behind batch TTS. |

Sources: [Qwen Image 2.1](https://qwen.ai/blog?id=qwen-image-2.1), [Gemini release notes](https://ai.google.dev/gemini-api/docs/changelog), [Gemini TTS guide](https://ai.google.dev/gemini-api/docs/speech-generation), [Lyria music guide](https://ai.google.dev/gemini-api/docs/music-generation), [Kling official release](https://kling.ai/dev/model-release/kling-4), [fal Kling 4 early-access status](https://fal.ai/kling-4).

Kling caveat: fal explicitly says its showcased clips came from Kling, not the fal API. The early-access page is evidence for planning, not proof of working public endpoints. Treat advertised future 4K/HDR/extension features separately from available capabilities.

## 2. Requested models: concrete integration map

| Family | Verified provider surface | Repository gap | Implementation |
|---|---|---|---|
| **HeyGen Avatar V** | HeyGen developer index documents Avatar V and v3 rendering | Registry has no HeyGen avatar adapter. `heygen_video` is a general video-model gateway, not an Avatar V implementation. | New `tools/avatar/heygen_avatar.py`; discover eligible avatars/looks, explicitly select engine, submit/poll/download v3 jobs, support supplied audio and scripts. Validate look eligibility and refuse silent IV fallback. |
| **Eleven v4 + v4 Turbo** | ElevenLabs direct API; fal documents `elevenlabs/tts/eleven-v4` | Direct adapter accepts arbitrary model IDs but defaults to v2; that is not verified v4 support. fal adapter catalogs v3/v2/v2.5 only. | Update `elevenlabs_tts` and `fal_elevenlabs_tts`: exact model IDs, per-model settings, pricing, voice compatibility, long-form stitching. Direct Turbo is confirmed by release; fal Turbo remains a separate verification task. |
| **Wan 3.0** | fal, Replicate, Atlas Cloud | `wan_video` is a local GPU path. Atlas catalog lacks Wan 3. | Add `wan_fal_video` and `wan_replicate_video`; extend `atlas_models.py`/`atlas_video.py`. Keep the local Wan tool separate. Validate text/image/reference routes individually, including native audio and long durations. |
| **GPT Image 2.5 Flare + Sunburst** | OpenAI API; Atlas advertises API availability for both variants | `openai_image` only declares GPT Image 2 and implements generation; Atlas catalog also only declares Image 2. | Add both exact variants to direct and Atlas adapters. Implement direct editing with references/masks, model-specific size/quality/transparency support, and real usage-based cost reconciliation. |
| **Ideogram 4.5 + Precise Edit** | Ideogram direct v2 API; fal generation/edit endpoints | No dedicated Ideogram adapter discovered | Add direct `ideogram_image` and fal `ideogram_fal_image`. Treat generation, ordinary edits and Precise Edit as explicit operations. Verify whether fal offers the precise mode before claiming parity with direct. |

Primary references:

- [HeyGen developer index](https://developers.heygen.com/llms.txt) — Avatar V is opt-in per look; the index describes Avatar IV as the default v3 engine. [April research post](https://www.heygen.com/research/avatar-v-model) establishes that Avatar V is older than this research window, despite the September-updated launch page.
- [Eleven v4 release, September 28](https://elevenlabs.io/blog/eleven-v4), [fal v4 schema](https://fal.ai/models/elevenlabs/tts/eleven-v4/api). Do not derive the new endpoint by blindly retaining the old `fal-ai/` prefix.
- [fal Wan 3](https://fal.ai/wan-3), [Replicate Wan 3](https://replicate.com/alibaba/wan-3), [Atlas Wan 3](https://www.atlascloud.ai/models/wan-3.0). fal publishes `alibaba/wan-3.0/text-to-video`, `/image-to-video`, `/reference-to-video`; Replicate publishes `alibaba/wan-3`. Availability is verified; an original September release date is not established here.
- [OpenAI Image 2.5 release, September 8](https://openai.com/index/introducing-chatgpt-images-2-5/), [Sunburst model contract](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst), [Atlas availability](https://www.atlascloud.ai/free-gpt-image-2.5-generator). Exact Atlas route IDs and schemas still need to be captured before implementation.
- [Ideogram model page](https://ideogram.ai/models/4.5/), [direct API overview](https://developer.ideogram.ai/ideogram-api/api-overview), [fal generation](https://fal.ai/models/ideogram/v4.5), [fal edits](https://fal.ai/models/ideogram/v4.5/edit/api). Model and API availability are confirmed; the precise September 30 release date was found in secondary reporting, not a dated primary announcement.

## 3. Important catch-up work outside the strict window

**Google image follow-up:** “Google image pro 3” most likely means **Gemini 3 Pro Image / Nano Banana Pro**. Google's announcement dates to November 20, 2025, so include it as a requested coverage gap rather than a September launch. Current Google docs identify `gemini-3-pro-image`; use the currently documented ID rather than assuming an old preview suffix. [Google announcement](https://blog.google/innovation-and-ai/products/nano-banana-pro/), [current image API guide](https://ai.google.dev/gemini-api/docs/image-generation).

**P1 provider map:** Google direct first (`google_imagen` already has a Gemini backend, but its declared Gemini model is only `gemini-2.5-flash-image` and its request passes a text prompt). Add explicit Pro support, reference-image editing, resolution controls, and per-model validation/pricing. Add Pro generation/edit routes to Atlas's catalog; Nano Banana 2 already being cataloged does not cover Pro. Offer fal and Replicate adapters as additional host coverage: [fal Pro API](https://fal.ai/models/fal-ai/nano-banana-pro/api), [Replicate Pro](https://replicate.com/google/nano-banana-pro), [Atlas model index](https://www.atlascloud.ai/docs/en/openapi-index). Confirm generation/edit parity on each host. Do not conflate Nano Banana Pro with Nano Banana 2, even where old aggregator marketing uses those names interchangeably.

| Priority | Model | Provider | Recommendation |
|---|---|---|---|
| P1 | **MiniMax H3 Max** | fal | Add a distinct variant to `minimax_fal_video`; current code targets Hailuo-03 routes. Max is a separate post-trained model, not an alias for base H3. [Announcement dated August 27](https://blog.fal.ai/introducing-h3-max-by-fal/); [exact API route](https://fal.ai/models/minimax/h3-max/text-to-video/api). |
| P2 | **LTX-2.5 Fast / Pro** | LTX direct; local/ComfyUI after workflow validation | New direct LTX adapter; update local model/runtime contracts separately. Current local/Modal tools expose LTX-2. [Model docs](https://docs.ltx.io/models/ltx-2-5); [September 2 update](https://docs.ltx.io/api-changelog/2026/9/2) adds resolution/frame-rate options, not the initial model release. |
| P2 | **Cartesia Sonic 3.6** | Cartesia direct | New TTS provider for an additional narration option; measure quality/latency/cost before recommending it over existing voices. [Official blog](https://www.cartesia.ai/ja/blog) has a September listing, but the [original announcement](https://t.co/lYA5Ym6hCX) says August 27. Do not label this a new September model. |
| P2 discovery | **Inworld TTS-2 / Flash** | Inworld direct | Available and relevant, but no original September launch date verified. Validate API contract and add only if voice quality/language coverage justifies another adapter. [Provider pricing and availability](https://inworld.ai/pricing). |

Do not count **Seedance 2.5, MiniMax H3, Seedream 5 Pro, Gemini Omni, or Nano Banana 2** as wholly missing: the pulled code already exposes integrations. Audit operation coverage and provider parity instead. Qwen Image 3 and Krea 2 also predate this window; they belong in a later coverage audit, not the September-release list. [Qwen Image 3 announcement](https://qwen.ai/blog?id=qwen-image-3.0), [Krea technical report](https://www.krea.ai/blog/krea-2-technical-report).

## 4. Delivery order and acceptance criteria

### PR 1 — Model contracts and route correctness

Extend the existing catalog approach, rather than adding model-name lists scattered across tools. Record model family separately from hosting provider, exact endpoint, operation, access status, verified-on date, supported media, duration/resolution constraints, and pricing basis. Keep provider-specific schemas; matching model names do not guarantee matching inputs.

Audit `image_selector`, `video_selector`, and `tts_selector` for operation-aware routing and explicit tool/host selection. Registry discovery already exists. In particular, direct and fal MiniMax tools both report `provider="minimax"`; test that a hosting preference is unambiguous. Preserve references, masks, audio flags and exact model selection through the selector. Unsupported features must fail clearly, not disappear during adaptation.

### PR 2 — Image upgrades

GPT Image 2.5 direct + Atlas, Gemini 3 Pro Image direct + Atlas, Ideogram direct + fal, then Qwen 2.1 local/workflow validation. Add/edit schemas, alpha-preserving output handling where supported, reference/mask validation, and model-specific cost estimates. Replace OpenAI's generic FLUX skill pointer with applicable provider guidance. Follow with fal/Replicate Pro coverage. fal's [current model index](https://fal.ai/explore/search) also lists Image 2.5 Flare/Sunburst edit routes: include a fal Image 2.5 adapter after capturing each exact generation/edit schema.

Acceptance: mocked payload tests for every route; a five-step edit sequence checks subject/layout preservation; masked-edit and transparent-output checks; selector retains all conditioning inputs; legacy GPT Image 2 remains usable.

### PR 3 — Speech and music

Eleven v4/v4 Turbo direct and fal v4, new Gemini TTS adapter, Lyria 3.5 update. Keep Cloud TTS and Gemini TTS distinct. Verify voice IDs/settings against each provider, dialogue alignment and stitching, declared output formats, and duration/cost reporting.

Acceptance: short and long narration fixtures, two-speaker fixtures where supported, decoding/sample-rate checks, timestamp checks if exposed, and pricing tests using captured usage responses. Add paid samples only as a separately scoped validation run.

### PR 4 — Wan across aggregators, plus H3 Max

Implement fal and Replicate adapters, then Atlas catalog additions. Share job-lifecycle helpers only where contracts actually match. Store task IDs and support resume after polling timeout, so retrying does not blindly create another paid job.

Acceptance: submit/poll/error/download fixtures for each host; text/image/reference route tests; native audio and actual duration/resolution verification; retain host+model+operation in provenance and cost records.

### PR 5 — Avatar V

Implement the direct avatar adapter and expose it in the avatar pipeline tool menu. Separate avatar discovery/eligibility from generation. Honor existing account assets and provider consent requirements for any new identity enrollment.

Acceptance: eligible versus ineligible look fixtures, explicit engine selection, audio-driven and script-driven requests, failed-job handling, and an approved short lip-sync sample before long-form use.

### PR 6 — Access-gated and secondary providers

Kling 4/Flash once schemas and access are available; LTX-2.5 direct/local; Cartesia and Inworld after comparative samples. Gemini Live stays a separate interactive-feature proposal. Do not hold the available-model updates for these dependencies.

Every integration also updates `docs/PROVIDERS.md`, relevant Layer 2/3 skills, registry metadata, cost handling and contract tests. No production pipeline redesign is needed for ordinary provider additions.

## 5. Validation and remaining research

- Public docs verify availability, not that this account is entitled to a model. No paid generation or credential inspection was performed.
- Before implementing, capture exact route schemas/pricing for Atlas Image 2.5/Wan, direct Eleven v4/Turbo, Ideogram Precise Edit, and HeyGen Avatar V. The HeyGen detailed Markdown page could not be fetched in this pass; its official index was readable.
- Qwen 2.1 cloud hosting, fal v4 Turbo, and Atlas Kling 4 remain unverified. Do not invent IDs from naming conventions.
- Compare like-for-like prompts, duration, resolution and native audio. Provider marketing rankings are not independent OpenMontage evaluations.
- Run targeted adapter/selector tests first. Paid cross-provider samples require a concrete costed test batch; this planning task does not execute one.

## 6. Pull and local-work preservation

The update initially conflicted with local provider documentation and older untracked Atlas files. A named stash, `codex-before-provider-research-main-update-2026-10-03`, remains intact. Original colliding files also live in `.tmp/provider-update-backup-2026-10-03/`.

Local architecture and Google TTS edits were reapplied. Provider documentation was reconciled with the current upstream catalog, preserving the setup guidance rather than restoring obsolete route claims. Upstream versions of colliding Atlas code/tests/skill remain active; the older local versions are preserved in the backup and stash. No unresolved Git conflicts remain. Other pre-existing work was left in place.
