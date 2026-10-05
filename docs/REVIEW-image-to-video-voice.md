# Review — Image → Video / Voice / Music / Compose path in OpenMontage

> Collected 2026-07-06 from a grounded read of the OpenMontage codebase, with a
> side-by-side against the sibling MLX-on-Apple-Silicon repo
> (`video_generation__image_workflow` / `python/mlx-movie-director`). Scope: every
> post-image stage — motion generation, voice/TTS, music + audio mixing, the
> avatar/lip-sync layer, and the compose stage that finalizes the deliverable.
> This is the second half of the review started in
> `docs/REVIEW-story-to-image.md`.
>
> Companion to `docs/ARCHITECTURE.md`, `docs/PROVIDERS.md`, and the story→image
> review. All excerpts carry `file:line` references.

## TL;DR

The image→deliverable half of OpenMontage is **governance-heavy by design** —
this is where a wrong choice costs real money (cloud motion/TTS) or breaks the
creative contract (a runtime swap). Three locks hold the line:

1. **`render_runtime` lock** — locked at proposal, carried through `edit_decisions`
   unchanged; a silent swap is a **CRITICAL** violation, detected in-tool by a
   three-source comparator (`video_compose._run_final_review`).
2. **"Present Both Composition Runtimes" HARD RULE** — when both Remotion and
   HyperFrames are installed, the agent MUST surface both at proposal; a
   single-runtime `options_considered` is a **CRITICAL** reviewer finding.
3. **Motion-required prohibition** — for any `motion_required=true` brief, a
   still-image / FFmpeg-Ken-Burns / animatic substitute is forbidden without
   explicit user approval of the downgrade. Stated in 5 reinforcing locations.

The tool layer mirrors the image side's selector-plus-provider seam:
`video_selector`, `tts_selector`, `music_gen`(+`suno_music`/library/stock), and
`audio_mixer` are all registry-auto-discovered. The compose stage dispatches one
tool (`video_compose`) across three runtimes (FFmpeg / Remotion / HyperFrames),
orthogonal to a Templated-vs-Atelier authoring axis.

The honest gaps (all verified): (1) **seedance dedup race** — fal.ai and Replicate
Seedance share `provider="seedance"`, so the second-registered is invisible to the
selector; (2) **LUFS mismatch** — `audio_mixer` hard-codes `-16 LUFS` while
`sound-design.md` targets `-14` for YouTube; (3) **ducking schema drift** —
`edit_decisions` declares `threshold_db`/`reduction_db`, but `audio_mixer._duck`
consumes `music_volume_during_speech` with no translation step; (4) **no MLX
motion path** — OM's local video providers (wan/hunyuan/ltx/cogvideo) need CUDA
`diffusers`; on Apple Silicon there is no native i2v (the `mlx_video` port fills
this); (5) the **faceswap orphan** stands, refined — the skill is HeyGen-API-backed,
not a dangling local-tool reference.

---

## 1. The chain, stage by stage (post-image)

The canonical state machine continues from where the story→image review left off
(`AGENT_GUIDE.md:185`):

```
… scene_plan → assets → edit → compose
```

| Stage | Director skill (explainer) | Canonical artifact | Post-image content |
|---|---|---|---|
| assets | `pipelines/explainer/asset-director.md` | `asset_manifest` | narration (TTS), music/sfx, generated video clips; per-asset `source_tool`/`cost_usd`/`scene_id` |
| edit | `pipelines/explainer/edit-director.md` | `edit_decisions` | cut list, audio layers (narration/music/sfx + ducking), subtitles, **`render_runtime` lock carried forward** |
| compose | `pipelines/explainer/compose-director.md` | render + `final_review` | dispatch on `render_runtime` → FFmpeg/Remotion/HyperFrames; promise-preservation check |

The **proposal** stage is where the post-image commitments are locked:
`production_plan.render_runtime` + `composition_mode` (the lock), the mandatory
**Music Plan** (`music_source`), and `delivery_promise.motion_required`. These
three are the governance seeds for everything downstream.

## 2. The motion tool layer

### 2.1 `video_selector` — the routing entry point

`tools/video/video_selector.py` — `capability="video_generation"`,
`provider="selector"`. Same auto-discovery seam as `image_selector`:
`registry.get_by_capability("video_generation")` minus itself
(`video_selector.py:135-140`). Adding a provider = drop a file in `tools/video/`.

Routing (`execute()`, `video_selector.py:175-231`):

1. discover candidates → `_filter_candidates` (operation-aware: `image_to_video`
   needs `supports.image_to_video` or an `image_url`/`reference_image_url` schema
   key; `reference_to_video` needs `reference_image_urls`; custom workflows need
   `custom_workflow` capability — `video_selector.py:328-366`);
2. score with `lib/scoring.rank_providers` (reused, not reimplemented);
3. honor `preferred_provider` (a booster, see gap §6.4) and `allowed_providers`;
4. read the `VIDEO_GEN_LOCAL_MODEL` env hint (`video_selector.py:252-262`) to
   pre-select a local model when `preferred=="auto"`;
5. delegate `tool.execute(adapted)` and annotate `selected_tool`/`selected_provider`/
   `provider_score`/`alternatives_considered` **and** `selected_tool_agent_skills`.

Supports `operation: "rank"` (score without generating) for preflight. Note the
`fallback_tools` property (`video_selector.py:142-145`) **unconditionally appends
`image_selector`** — a latent footgun for motion-required briefs (§6.7).

### 2.2 Concrete providers (`tools/video/`)

17 providers. Local providers gate on `VIDEO_GEN_LOCAL_ENABLED=true` + importable
`diffusers`/`torch` (`_shared.py:183-195`) — i.e. **CUDA-oriented**, not Apple
Silicon native.

| tool | provider | runtime | cost | i2v/t2v | motion strength | `agent_skills` | key `supports` |
|---|---|---|---|---|---|---|---|
| `wan_video` | wan | LOCAL_GPU | $0 | both | 1.3B 832×480@16fps 81f (8 GB) / 14B 720p (24 GB) | `ltx2` | reference_image, offline, local_gpu |
| `hunyuan_video` | hunyuan | LOCAL_GPU | $0 | both | 848×480@24fps 121f (14 GB) | `ltx2` | reference_image, offline, local_gpu |
| `ltx_video_local` | ltx | LOCAL_GPU | $0 | both | 768×512@30fps 121f (12 GB) | `ltx2` | reference_image, offline, local_gpu |
| `cogvideo_video` | cogvideo | LOCAL_GPU | $0 | both (but `cogvideo-2b` variant is i2v=False — gap §6.3) | 5B 720×480@8fps 49f (12 GB) / 2B (6 GB) | `ltx2` | reference_image, offline, local_gpu |
| `ltx_video_modal` | ltx-modal | API | flat $0.25/gen | both | self-hosted cloud LTX2 (`MODAL_LTX2_ENDPOINT_URL`) | `ltx2` | reference_image, self_hosted_cloud |
| `comfyui_video` | comfyui | HYBRID | $0 | both | server-driven, bundled WAN 2.2 14B FP8 (16 GB) | `comfyui`, `ai-video-gen`, `ltx2` | custom_workflow, custom_output_node, offline |
| `heygen_video` | heygen | API | $0.15–0.50/gen (quality tier) | both | veo3.1/veo3/kling/sora/runway/seedance variants | `ai-video-gen`, `create-video` | reference_image, cloud_generation |
| `seedance_video` | **seedance** | API (fal.ai) | $0.3034/s std, $0.2419/s fast | t2v+i2v+ref | quality_score 0.95; lip_sync, multi_shot, native_audio | `seedance-2-0`, `ai-video-gen` | text/image/reference_to_video, multiple_reference, native_audio, lip_sync, multi_shot |
| `seedance_replicate` | **seedance** | API (Replicate) | via Replicate | t2v+i2v | quality_score 0.95 | `seedance-2-0`, `ai-video-gen` | text_to_video, image_to_video, native_audio, lip_sync, multi_shot |
| `kling_video` | kling | API | $0.30 master / $0.20 pro / $0.10 std per 5s | t2v+i2v | v2.1/v3; native_audio | `ai-video-gen` | text/image_to_video, native_audio, cinematic_quality |
| `minimax_video` | minimax | API | $0.08–0.15/gen | t2v+i2v | hailuo-02/2.3 variants | `ai-video-gen` | text/image_to_video, camera_direction |
| `veo_video` | veo | API | $0.10/s fast, $0.20/s base, $0.40/s 4k, +$0.20–0.40/s audio | t2v+i2v+ref+first_last | veo3/3.1; dialogue_generation, ambient_sound | `ai-video-gen` | text/image/reference/first_last_frame, native_audio, dialogue_generation |
| `runway_video` | runway | API | $0.05–0.30/s by model | t2v+i2v | gen3a/gen4/seedance_2.0; quality_score 0.9 | `seedance-2-0`, `ai-video-gen` | text/image_to_video, professional_control, lip_sync, multi_shot |
| `higgsfield_video` | higgsfield | API | $0.10–0.80/clip | t2v+i2v | multi_model_routing; quality_score 0.9 | `seedance-2-0`, `ai-video-gen` | text/image_to_video, character_consistency, multi_model_routing |
| `grok_video` | grok | API | $0.05/s 480p, $0.07/s 720p, +$0.002/in img | t2v+i2v+ref | 1–15s; lip_sync | `grok-media`, `ai-video-gen` | text/image/reference_to_video, native_audio, lip_sync — **no quality_score (gap §6.5)** |
| `pexels_video` / `pixabay_video` | pexels / pixabay | API | free (SOURCE tier) | stock only | stock footage; not i2v/t2v | — | orientation/size/category filters, free_commercial_use |

### 2.3 Motion-required governance (the crown jewels)

For any `delivery_promise.motion_required=true` brief, five locations state the
prohibition consistently:

- **`AGENT_GUIDE.md:391-406`** — "Critical Rule: Motion-Required Requests":
  still-image fallback is forbidden; FFmpeg-only fallback is forbidden when it
  changes the deliverable from motion-led to still-led; **silent runtime swap is
  forbidden** ("If `render_runtime='hyperframes'` was locked and HyperFrames is
  unavailable, do NOT route to Remotion instead. Surface the blocker…").
- **`skills/core/hyperframes.md:74-82`** — the locked runtime is "a commitment,
  not a hint"; Compose MUST NOT downgrade to FFmpeg Ken Burns.
- **`skills/pipelines/cinematic/compose-director.md:15,35`** — silent swap
  (including FFmpeg Ken Burns) is a **CRITICAL governance violation**.
- **`skills/pipelines/cinematic/asset-director.md:46-82`** — for motion-required
  jobs, use `video_selector` first; `image_selector` does not satisfy the motion
  requirement by itself.
- **`skills/pipelines/cinematic/proposal-director.md:30,101`** — preflight
  enforcement: if neither generation nor stock can deliver motion, "do not
  silently downgrade to still-led… present the constraint honestly."

## 3. The voice path

### 3.1 The `script.voice_performance` contract

`schemas/artifacts/script.schema.json:12-33` — a top-level (optional) object:
`performance_intent`, `pacing_profile` (enum: contemplative/conversational/
energetic/technical/cinematic/custom), `energy_curve`, `pause_policy`,
`sample_section_id` ("most performance-sensitive section to use for TTS sample
approval"), `provider_notes`. Section-level `delivery_cues` (`:46-68`) carry
`pace`/`energy`/`emphasis_words`/`pause_before_seconds`/`pause_after_seconds`/
`delivery_note` and **`provider_text`** — the provider-ready string that may
contain SSML `<break time="0.6s"/>` tags. This is the SSML contract.

### 3.2 `tts_selector` + 6 providers

`tools/audio/tts_selector.py` — `capability="tts"`, `provider="selector"`.
Auto-discovers via `registry.get_by_capability("tts")` (`tts_selector.py:124-129`),
reuses `lib/scoring.rank_providers`, supports `operation: "rank"`. Annotates
`selected_tool`/`selected_provider`/`provider_score`/`selected_tool_agent_skills`/
`alternatives_considered`.

| provider | runtime | cost | cloning | SSML | `agent_skills` | fallback |
|---|---|---|---|---|---|---|
| `elevenlabs_tts` | API | $0.0003/char (**$300/1M**) | **yes** | voice settings, not tags | `elevenlabs`, `text-to-speech` | openai → piper |
| `openai_tts` | API | $0.000015/char (**$15/1M**) | no | no; `instructions` on `gpt-4o-mini-tts` only | `openai-docs` | piper |
| `google_tts` | API | $4–$160/1M (tiered: Standard→Chirp3-HD) | no | **yes** — `input_type:"ssml"` wraps `<speak>`, `<break>` supported | `text-to-speech` | openai → elevenlabs → piper |
| `dashscope_tts` | API | $15/1M | no | no; `instructions` on `qwen3-tts-instruct-flash` | `dashscope` | doubao → elevenlabs → openai → piper |
| `doubao_tts` | API (ASYNC poll) | $15/1M | no | no; **`enable_timestamp`** → word/sentence alignment (subtitle specialist) | `doubao-tts`, `text-to-speech` | google → elevenlabs → openai → piper |
| `piper_tts` | LOCAL | **$0** | no | no; `length_scale` + `sentence_silence` | `text-to-speech` | terminal (universal floor) |

No `edge-tts`. Piper is the universal offline floor — every API chain terminates
there. ElevenLabs is the only cloning provider. Google is the only first-class
SSML provider. Doubao is the only one returning timestamp metadata.

### 3.3 `voice-performance-director` + sample-then-batch

`skills/meta/voice-performance-director.md` sits above the asset-director. Its
thesis (`:3-7`): "make generated narration sound **directed**, not merely read."
It mandates the `voice_performance` contract, translates intent into per-provider
knobs (`:56-71`: OpenAI `instructions` only on `gpt-4o-mini-tts`; Google `ssml`+
`speaking_rate 0.25..2.0`; ElevenLabs `stability`/`similarity_boost`/`style`),
and defines four failure conditions (`:83-94`): no plan, vague directions,
provider/voice change after sample approval, and generating from raw text when
`provider_text` exists.

The asset-director runs **sample-first, batch-second** (`asset-director.md:69-82`):
generate the `sample_section_id` (most demanding section, ~$0.03–0.08), play it,
confirm voice/pace/pauses/tone (max 3 iterations), then batch. Each narration
asset records `voice_performance` provenance (`asset_manifest.schema.json:37-53`):
`source_section_id`, `delivery_cues_applied`, `provider_text_used`,
`provider_settings`, `sample_approved`, `sample_path`, `review_notes`.

## 4. Music + audio mixing

### 4.1 Generation + sources

- `tools/audio/music_gen.py` — **ElevenLabs Music only** (`music_v1`),
  `~$0.05/30s`, 3–600s, `agent_skills: ["music","sound-effects","elevenlabs"]`.
  No `supports` flags. The `force_instrumental=true` mandate lives only in the
  usage skill (`skills/creative/music-gen-usage.md:14`); the tool never sends it
  (gap §6.8).
- `tools/audio/suno_music.py` — Suno V4/V4_5/V5, ASYNC, BETA, vocals + custom
  lyrics; declares `supports = {instrumental, vocals, custom_lyrics,
  style_control, long_form}`; `fallback_tools = ["music_gen"]`.
- `tools/audio/music_library.py` — local filesystem scan (read-only), default
  `<root>/music_library/`. **No mood/BPM/genre/license metadata**
  (`music_library.py:102-122`) — selection is by filename + duration only (gap
  §6.9).
- `freesound_music` / `pixabay_music` — stock search/download.

### 4.2 Mandatory Music Plan

At proposal, `skills/pipelines/explainer/proposal-director.md:362-397` ("Step 5b:
Music Plan (Mandatory)") requires surfacing music availability in order:
user library → AI generation → stock → none (told to user explicitly). The
decision lands in `proposal_packet.production_plan.music_source`
(`proposal_packet.schema.json:167-178`: `source_type` user_library/ai_generated/
bring_your_own/none, `track_path`, `provider`, `mood_direction`, `estimated_cost_usd`).
**Policy-mandatory, not schema-enforced** (`music_source` is not in `production_plan.required`).

### 4.3 `audio_mixer` + ducking + LUFS

`tools/audio/audio_mixer.py` — pure **FFmpeg** `filter_complex` engine
(`provider="ffmpeg"`, `agent_skills: ["ffmpeg","video-toolkit"]`). Operations:
`mix`, `duck`, `extract`, `full_mix`, `segmented_music`.

**Ducking = real sidechain compression, not static gain** (`audio_mixer.py:356-362`):

```python
[1:a]sidechaincompress=threshold=0.02:ratio=9:attack={attack}:release={release}:level_sc=1:mix=0.9[ducked];
[ducked]volume={music_vol * 3}[music_out];
[0:a][music_out]amix=inputs=2:duration=longest[out]
```

Speech is the sidechain key; music is compressed by it. `full_mix` layers
narration+music+sfx, runs the music subgroup through the same sidechain keyed by
the speech subgroup (`:526-531`), then `loudnorm`.

**LUFS target = `-16`** (`audio_mixer.py:254,578`):
`loudnorm=I=-16:LRA=11:TP=-1.5`. This is the **podcast/Apple** target, NOT the
YouTube `-14` that `skills/creative/sound-design.md:17,138` targets — a
documented inconsistency (gap §6.1). The mixer does not parameterize the target.

`segmented_music` (`:606-706`) builds a per-frame `volume` expression for
"music during talking-head, silence during showcase", looping the bed with
`-stream_loop -1`.

### 4.4 edit-director ducking wiring (and the schema drift)

`skills/pipelines/explainer/edit-director.md:84-113` configures audio layers:
narration segments + a music bed (volume `0.08`, fade in/out) + a `ducking`
object (`threshold_db: -3`, `reduction_db: -8`, attack 200ms, release 500ms) +
sfx. **But** the `edit_decisions` ducking shape (`threshold_db`/`reduction_db`)
is **not** the shape `audio_mixer._duck` consumes (`music_volume_during_speech`/
`attack_ms`/`release_ms` + fixed `threshold=0.02`/`ratio=9`). No translation step
exists in the mixer (gap §6.2). Note also: when rendering via **Remotion** (the
default), `audio_mixer` is not used at all — Remotion's `<Audio>` components mix
natively (`compose-director.md:188-201`); `audio_mixer` is the FFmpeg-fallback
path only.

## 5. The compose stage + 3 runtimes

### 5.1 `video_compose` dispatch

`tools/video/video_compose.py` — `operation: "render"` resolves asset IDs and
dispatches on **`edit_decisions.render_runtime`** (`video_compose.py:1307-1402`).
The field is mandatory and enum-validated (`remotion`/`hyperframes`/`ffmpeg`); an
unset runtime returns a structured error that explicitly refuses to default
(`:1314`). `get_info()["render_engines"]` (`:256-323`) surfaces `{ffmpeg: True,
remotion: <bool>, hyperframes: <bool>}` so the proposal stage knows what's
installed.

### 5.2 The three runtimes

| runtime | what it does | deps | strengths | scene fit |
|---|---|---|---|---|
| **FFmpeg** (`_compose`/`_render_via_ffmpeg`) | per-cut trim+re-encode to 1920×1080@30fps yuv420p, concat-demuxer join, ASS subtitle burn, audio mux | `ffmpeg`/`ffprobe` only | pure-video concat/trim/subtitle/encode; the floor | talking-head raw cuts, no composition |
| **Remotion** (`_remotion_render`/`_render_via_atelier`) | React/TSX frame-accurate render via `npx remotion render` | Node + `remotion-composer/` + node_modules | animated text/stat cards, data-driven charts (spring physics), word-level captions (`remotion_caption_burn`), `TalkingHead` avatar, `CinematicRenderer`, `<OffthreadVideo>` embed | explainer, cinematic, screen-demo, talking-head, data-viz |
| **HyperFrames** (`_render_via_hyperframes`→`hyperframes_compose`) | HTML/CSS/GSAP render via `npx hyperframes` (upstream npm pkg) | Node ≥22 + ffmpeg + `npx hyperframes doctor`==0 | kinetic typography, product promos, GSAP-native animation, SVG rigs, registry blocks (grain/shimmer/shader) | motion-graphics-heavy, animation-first |

Composition ID is resolved from `renderer_family` via `RENDERER_FAMILY_MAP`
(`:683-692`): explainer-data/teacher/product-reveal/screen-demo/animation-first →
`Explainer`; cinematic-trailer/documentary-montage → `CinematicRenderer`;
presenter → `TalkingHead`.

### 5.3 The `render_runtime` lock (CRITICAL severity)

Stated in 5 places; enforced in-tool by a three-source swap comparator.

- **Tool docstring** (`video_compose.py:7-8,26-29`) + **routing comment**
  (`:1307-1312`): "Silent runtime swaps are forbidden by governance."
- **Schema** (`edit_decisions.schema.json:197-201`): `render_runtime` enum,
  "Locked at proposal… Edit MUST carry this forward unchanged unless a logged
  `render_runtime_selection` decision overrides it." Same lock language on
  `renderer_family` (`:192-196`) and `composition_mode` (`:202-206`).
- **AGENT_GUIDE** (`:389`): locked at proposal, carried through edit_decisions
  unchanged.
- **Reviewer** (`skills/meta/reviewer.md:236-240`): a mismatch without a logged
  `render_runtime_selection` decision → **CRITICAL**.
- **In-tool detection** (`video_compose._run_final_review`, `:2189-2242`):
  three-source priority ladder — (1) `proposal_packet.production_plan.render_runtime`
  (authoritative), (2) `edit_decisions.metadata.proposal_render_runtime`
  (edit-stage opt-in), (3) `edit_decisions.render_runtime` alone (cannot detect a
  swap solo). If proposal ≠ edit → `runtime_swap_detected = true` + an issue
  appended. `final_review.schema.json:91,95` carries the field.

The tool itself refuses silent substitution: `_render_via_hyperframes` returns a
structured BLOCKER if HyperFrames is unavailable (`:1504-1516`); the Remotion
failure path (`:1418-1432`) refuses silent FFmpeg fallback.

### 5.4 "Present Both Composition Runtimes" HARD RULE

`AGENT_GUIDE.md:123-137` — when both Remotion and HyperFrames report `True` in
`get_info()["render_engines"]`, the agent MUST present both at proposal (per
runtime: what it's best at for **this brief**, an honest tradeoff, a
recommendation tied to `delivery_promise`/`visual_approach`), then wait for
explicit approval. **A `render_runtime_selection` decision with only one runtime
in `options_considered` when both were available is a CRITICAL reviewer finding**
(`reviewer.md:242-246`). If only one is available, the unavailable one is still
recorded with `rejected_because: "runtime not available on this machine"`.

### 5.5 Templated vs Atelier

`AGENT_GUIDE.md:139-146` — orthogonal to `render_runtime`.
- **Templated** — assemble stock `cut.type` scene-types (`text_card`, `stat_card`,
  `bar_chart`, …) into `Explainer`/`CinematicRenderer`. Fast/cheap/reliable.
- **Atelier** — hand-author from scratch (`composition_mode: "atelier"`), bespoke
  scenes + one-off theme; no reusable creative components. Default for hero/brand
  work. Enforced mechanically by `_run_atelier_checks` (`video_compose.py:976-1034`)
  via `_ATELIER_STOCK_IMPORT_RE` — bespoke projects importing stock components
  (`Explainer`, `CinematicRenderer`, `TalkingHead`, `CollageBurst`, …) fail the
  render. Missing `bespoke.art_direction` is a warning. For HyperFrames, atelier
  is the default and needs no flag.

### 5.6 `edit_decisions` artifact

`schemas/artifacts/edit_decisions.schema.json` — `required: [version, cuts,
render_runtime]`. Carries: `cuts[]` (`source`/`in_seconds`/`out_seconds`/`speed`/
`layer`/`transform`/`transition_in`/`transition_out`), `overlays[]`, `audio`
(`narration.segments[]`/`music`+`ducking`/`sfx[]`), `subtitles` (style
sentence/word-by-word/karaoke), `renderer_family`, `render_runtime`,
`composition_mode`, `bespoke` (required when atelier), `slideshow_risk_score`
(verdict `fail` blocks render, `video_compose.py:1240-1256`), `metadata`
(`compose_target`/`delivery_promise`/`playbook`/`proposal_render_runtime`).

## 6. Avatar / lip-sync layer + faceswap (refined)

### 6.1 Local GPU avatar tools

- `tools/avatar/talking_head.py` — still portrait + audio → talking video.
  `capability="avatar"`, `provider="sadtalker"`, LOCAL_GPU, $0. **SadTalker
  implemented** (`:175-242`); **MuseTalk is a stub** (`:244-258`, returns "not yet
  implemented, use sadtalker"). `fallback="lip_sync"`. Status: AVAILABLE iff
  `SADTALKER_PATH` or `import sadtalker`.
- `tools/avatar/lip_sync.py` — video with face + new audio → re-lined video.
  `provider="wav2lip"`, LOCAL_GPU, $0. **Wav2Lip + Wav2Lip-GAN** implemented
  (`MODEL_CHECKPOINTS`, `:30-33`). No LatentSync/muse-talk-lip. No fallback
  declared (it is the fallback target).

### 6.2 `avatar-spokesperson` pipeline

`pipeline_defs/avatar-spokesperson.yaml` (production, $2.00 budget, 12-min).
Stages: idea → script → scene_plan → assets → edit → compose → publish. The
**idea-director classifies the avatar path** into `platform_avatar` /
`photo_talking_head` / `presenter_plate_lip_sync` (`idea-director.md:27-30`) and
**locks Remotion** (HyperFrames rejected — no TalkingHead parity). The
**Executive Producer Pivot Decision Matrix** (`executive-producer.md:47-71`)
runs at **G1 (after IDEA)**, not deferred to assets:

```
IF talking_head AVAILABLE                          → Standard avatar path
IF talking_head UNAVAILABLE, lip_sync AVAILABLE    → Lip-sync path (user supplies plate)
IF NEITHER                                          → Narration-Over-Graphics pivot (or block)
```

Asset-director locks ONE avatar path; narration resolved via `tts_selector`
**before** graphics; manifest carries `metadata.avatar_generation_path`. The
avatar clip enters `asset_manifest` as a generic `type:"video"` asset tagged
`source_tool:"talking_head"`/`"lip_sync"` — **no avatar-specific schema field**
exists.

### 6.3 Layer-3 skills — all HeyGen-API

`.agents/skills/{avatar-video,heygen,faceswap,create-video}/` are **all HeyGen v2
API skills** (`allowed-tools: mcp__heygen__*`, fallback to direct HTTP). They do
**not** call the local `talking_head`/`lip_sync` tools — a separate (cloud, paid)
avatar stack. `heygen` is **DEPRECATED** (superseded by `create-video` +
`avatar-video`).

### 6.4 Faceswap orphan — refined

The prior review (`docs/REVIEW-story-to-image.md:39-40,216-218`) flagged
`.agents/skills/faceswap/` as orphaned (no backing tool). **Verified still true**
— `find tools -iname '*faceswap*' -o '*face_swap*' -o '*swap*'` returns zero
files; the registry auto-discovers `tools/` via `pkgutil.walk_packages`
(`tool_registry.py:118-134`), so no `faceswap` tool is registered. **But the
refinement matters**: the skill is **not a dangling reference** — it documents
direct HeyGen FaceswapNode workflow calls (`POST …/v1/workflows/executions` with
`workflow_type: "FaceswapNode"`, `faceswap/SKILL.md:23-27,40-49`). It is
**API-backed, not tool-backed**. If `HEYGEN_API_KEY`/MCP is configured it is
functional; otherwise dead weight. `.claude/skills/faceswap/SKILL.md` is a
byte-identical duplicate.

## 7. Side-by-side vs the MLX repo

The MLX repo (`python/mlx-movie-director/run.py`) is native generation on Apple
Silicon with no orchestration/story layer. For the post-image stages it is
**mostly silent** — it has motion gen + upscale + ASR, but **no TTS, no music, no
mixer, no compose, no avatar/lip-sync**.

| Concern | OpenMontage | MLX repo (`run.py`) | Map |
|---|---|---|---|
| Motion i2v | cloud (seedance/kling/veo/runway/higgsfield/grok/heygen) + **CUDA locals** (wan/hunyuan/ltx/cogvideo — need `diffusers`/torch VRAM) + comfyui | **LTX-2.3 native MLX I2V** (`video t2i2v`: ZImage T2I → VLM prompt → LTX-2.3 dasiwa animate); `video generate` | `mlx_video` provider fills the **Apple-Silicon-native** i2v gap (OM's CUDA locals don't run on MPS) |
| Motion t2v | cloud + CUDA locals | `video generate` (LTX-2.3) | same seam |
| Voice / TTS | full chain (elevenlabs/openai/google/dashscope/doubao/piper) | **NONE** (`video-asr-gate.py:9` "there is no native [MLX TTS]") | no MLX TTS port possible — OM stays as-is |
| ASR / transcription | (not a first-class tool) | **mlx-whisper** (ASR only; used as t2i2v audio quality gate) | MLX could be OM's local ASR provider (new finding) |
| Music | music_gen/suno/library/stock + mixer | **NONE** | OM-only |
| Audio mix / ducking / LUFS | `audio_mixer` (FFmpeg sidechain, -16 LUFS) | **NONE** | OM-only |
| Compose | FFmpeg/Remotion/HyperFrames + render_runtime lock | **NONE** (generates clips only) | OM-only |
| Avatar / lip-sync | talking_head (SadTalker)/lip_sync (Wav2Lip) + HeyGen skills | **NONE** | OM-only |
| Upscale / restore | Real-ESRGAN/CodeFormer/GFPGAN (torch) | ESRGAN (torch vision-venv) + **SeedVR2 7B** (`--upscale-method seedvr2`) | overlap; SeedVR2 could enhance OM's upscale |
| Visual QA | planned `test_02_image_gen.py` (**missing**) | `caption` (Qwen3-VL 4B) + CLIP `video_understand` | MLX already has the QA brain |
| Motion governance | render_runtime lock + motion-required prohibition | n/a | OM-only (the value of plugging MLX in) |

**The bidirectional findings:**
1. **`mlx_video` (LTX-2.3 i2v) is the highest-value motion port** — but its value
   is specifically **Apple-Silicon-native**. OM already has 4 local i2v providers
   (wan/hunyuan/ltx/cogvideo) that are `$0`, but they require CUDA `diffusers`
   (8–24 GB VRAM). On an Apple Silicon box they don't run; MLX LTX-2.3 does. This
   refines F2: it's not "OM has no offline i2v" — it's "OM's offline i2v is
   CUDA-only; MLX is the MPS-native path."
2. **mlx-whisper → OM local ASR provider** is a new finding. OM's video path has
   no first-class transcription tool; MLX's mlx-whisper (already proven as the
   t2i2v audio gate) could fill it.
3. **No MLX TTS / music / compose / avatar port is possible** — these are OM's
   exclusive value; the MLX repo has nothing to contribute here. Recorded as a
   negative so no future goal chases it.

## 8. Seams, gaps, and what I'd touch first

Verified gaps (from the post-image sweep):

1. **LUFS target mismatch** — `audio_mixer` hard-codes `I=-16` (podcast/Apple);
   `sound-design.md` targets `-14` for YouTube. The mixer doesn't parameterize
   it. Either make the target a `edit_decisions.metadata.loudnorm_target` field
   or align the docs.
2. **Ducking schema drift** — `edit_decisions` declares
   `threshold_db`/`reduction_db`; `audio_mixer._duck` consumes
   `music_volume_during_speech` + fixed `threshold=0.02`/`ratio=9`. No
   translation step. The declarative intent and the executed params diverge
   silently.
3. **Seedance dedup race** — `seedance_video` (fal) and `seedance_replicate`
   share `provider="seedance"`; `_select_best_tool` keys `tool_by_provider` by
   provider string (`video_selector.py:267-270`), so the second-registered is
   invisible to the selector.
4. **`cogvideo-2b` i2v mismatch** — `_shared.py:122-136` declares the 2B variant
   `i2v: False`, but `cogvideo_video` advertises `image_to_video` +
   `reference_image: True` unconditionally; the variant flag is never consulted.
5. **`preferred_provider` has no score-gap gate** — `video_selector.py:272-277`
   returns the preferred provider on the first ranking match regardless of how
   much lower its score is than the top (comment claims "unless drastically
   worse").
6. **`grok_video` has no `quality_score`** — every other premium provider sets
   0.9–0.95; grok (lip_sync + native_audio) is scored only on supports/stability,
   likely under-ranked.
7. **`video_selector.fallback_tools` appends `image_selector` unconditionally**
   (`:145`) — the motion-required prohibition lives in director skills, not in
   the selector; a direct caller (no director) can silently fall back to an image
   tool for a motion-required brief.
8. **`force_instrumental` mandate never sent** — `music-gen-usage.md:14` says
   "always set `force_instrumental=true`"; `music_gen.py` never sets it.
9. **`music_library` has no mood/BPM/genre/license metadata** — selection is by
   filename + duration; the BPM-driven selection the skills assume is impossible
   on the local library.
10. **Missing tests** — no `tests/qa/test_02_image_gen.py` (carried from
    story→image review) **and** no video tests (`ls tests | grep video` empty);
    provider routing/`estimate_cost`/`estimate_runtime` entirely untested.
11. **`.env.example` drift** — missing `REPLICATE_API_TOKEN`,
    `HIGGSFIELD_API_KEY`/`_SECRET`/`HIGGSFIELD_KEY`, and the `FAL_AI_API_KEY`
    alias (only `FAL_KEY` listed).
12. **Faceswap orphan (refined)** — still no local tool; the skill is HeyGen-API-
    backed. Either add `tools/avatar/faceswap.py` wrapping the HeyGen workflow
    (MLX repo has `image faceswap` for a local option), reclassify as
    `heygen-faceswap`, or remove.
13. **`asset_manifest` has no music/avatar structured fields** — no `bpm`/`mood`/
    `loop_points` for music; no avatar-specific field (clip is generic
    `type:"video"`). `additionalProperties: false` blocks ad-hoc fields.

**What I'd land first:** the **`mlx_video` provider** (LTX-2.3 i2v, future-plan
F2). It is the single change that (a) gives OM an Apple-Silicon-native i2v path —
the gap its CUDA-only locals leave on every MPS box — (b) is auto-discovered by
`video_selector` with zero selector edits, (c) costs `$0` (scorer rewards), and
(d) is the motion analog of the story→image review's `mlx_image` (F1). Together
F1+F2 are the first two stitches of the OM-story-front / MLX-native-back seam.

## 9. File reference (image → video / voice only)

```
# motion generation
tools/video/video_selector.py                         # THE routing entry point
tools/video/_shared.py                                # local-provider gating + variant metadata
tools/video/{wan,hunyuan,ltx_video_local,ltx_video_modal,cogvideo}_video.py   # CUDA locals
tools/video/{heygen,seedance,seedance_replicate,kling,minimax,veo,runway,higgsfield,grok,comfyui}_video.py
tools/video/{pexels,pixabay}_video.py                 # stock (SOURCE tier)

# voice / TTS
tools/audio/tts_selector.py                           # selector (reuses lib/scoring)
tools/audio/{elevenlabs,openai,google,dashscope,doubao,piper}_tts.py
skills/meta/voice-performance-director.md             # direction authority
schemas/artifacts/script.schema.json                  # voice_performance + delivery_cues contract

# music + audio
tools/audio/{music_gen,suno_music,music_library,freesound_music,pixabay_music}.py
tools/audio/audio_mixer.py                            # FFmpeg sidechain ducking, -16 LUFS
skills/creative/{music-gen-usage,sound-design}.md
schemas/artifacts/proposal_packet.schema.json         # music_source (mandatory by policy)

# compose + runtimes
tools/video/video_compose.py                          # dispatcher (render_runtime → 3 runtimes)
tools/video/hyperframes_compose.py                    # HyperFrames sibling
tools/video/{remotion_caption_burn,video_stitch,video_trimmer}.py
skills/core/{remotion,hyperframes}.md
remotion-composer/SCENE_TYPES.md                      # Remotion scene-type catalog
schemas/artifacts/edit_decisions.schema.json          # render_runtime lock + audio/subtitles/bespoke
skills/meta/reviewer.md                               # CRITICAL swap/single-runtime findings

# avatar / lip-sync
tools/avatar/{talking_head,lip_sync}.py               # SadTalker/Wav2Lip (MuseTalk stub)
pipeline_defs/avatar-spokesperson.yaml
skills/pipelines/avatar-spokesperson/                 # idea/asset/compose directors + EP pivot
.agents/skills/{avatar-video,heygen,faceswap,create-video}/   # Layer-3 (all HeyGen-API)
```
