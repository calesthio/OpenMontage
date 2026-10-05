# Review — Story-Line → Image path in OpenMontage

> Collected 2026-07-06 from a grounded read of the OpenMontage codebase, with a
> side-by-side against the sibling MLX-on-Apple-Silicon repo
> (`video_generation__image_workflow` / `python/mlx-movie-director`). Scope: the
> early pipeline stages that turn an idea/script into image assets. Image →
> video / voice is deferred to a later pass.
>
> Companion to `docs/ARCHITECTURE.md`, `docs/PROVIDERS.md`, and the (now stale)
> `docs/comfyui-adapter-plan.md`.

## TL;DR

OpenMontage's story→image path is a **clean, instruction-driven contract chain**:

```
research_brief → proposal_packet → script → scene_plan → asset_manifest
```

Each stage = a YAML-declared gate + a markdown director skill + one canonical
JSON artifact (schema-validated). The agent (not Python) drives it. Image
generation is reached through exactly one entry point — `image_selector` —
which auto-discovers every `capability="image_generation"` tool and routes by a
weighted score (`lib/scoring.rank_providers`). Providers are API-first (FLUX via
fal.ai, OpenAI gpt-image-2, Imagen 4, Grok, Recraft, DashScope) with two local
options (ComfyUI server, in-process `diffusers`) and two stock (Pexels/Pixabay).

The strongest ideas worth keeping: (1) the **selector-plus-provider** discovery
seam, (2) the **`shot_language` → `shot_prompt_builder.py`** cinematography
vocabulary that turns structured enums into prompts, (3) the **playbook as the
style contract** with `image_prompt_prefix` distilled (never pasted) +
`consistency_anchors`, (4) the **CHAI pre/critique/post self-review** applied to
every generation prompt.

The honest gaps: (1) **no ControlNet / inpainting / true img2img** provider
except Grok's edit mode — the scorer *weights* those `supports` flags but nothing
advertises them; (2) **two providers share `FAL_KEY`** (flux + recraft) so one
env-var flips both on, distorting the score; (3) the planned
`tests/qa/test_02_image_gen.py` was never written; (4) the `.agents/skills/faceswap/`
Layer-3 skill is **orphaned** — no `faceswap` tool exists in `tools/`.

---

## 1. The chain, stage by stage

Canonical state machine (`AGENT_GUIDE.md:185`):

```
research → proposal → script → scene_plan → assets → edit → compose
```

`hybrid` collapses research+proposal into a single `idea` stage producing a
`brief`. The research-first pipelines (`animated-explainer`, `animation`,
`cinematic`) produce a richer `research_brief` then a `proposal_packet`.

| Stage | Director skill (explainer) | Canonical artifact | Image-relevant content |
|---|---|---|---|
| research | `pipelines/explainer/research-director.md` | `research_brief` | `angles_discovered`, visual inspiration, `landscape.underserved_gaps` |
| proposal | `pipelines/explainer/proposal-director.md` | `proposal_packet` + `decision_log` | **visual identity designed here** (not picked); playbook chosen/generated; cost estimate; **hard approval gate** |
| script | `pipelines/explainer/script-director.md` | `script` | `sections[].enhancement_cues` = visual hand-off (`overlay/broll/diagram/stat_card/animation/code_snippet`); density ≥1 per 8–10 s |
| scene_plan | `pipelines/explainer/scene-director.md` | `scene_plan` | `scenes[].shot_language` + `required_assets[]` (source: generate\|source\|provided\|record) |
| assets | `pipelines/explainer/asset-director.md` | `asset_manifest` | per-asset `prompt/seed/model/cost_usd/source_tool/scene_id` |

The **proposal** stage is the only hard money gate (`human_approval_default: true`
everywhere; `AGENT_GUIDE.md:705` "Do not begin asset generation before user
approval"). The **scene_plan → assets** hand-off is the real story→image
contract — see §3.

## 2. Image generation tool layer

### 2.1 The selector (single entry point)

`tools/graphics/image_selector.py` — `capability="image_generation"`,
`provider="selector"`. Auto-discovers providers via
`registry.get_by_capability("image_generation")` minus itself, so **adding a
provider = drop a file in `tools/graphics/`, nothing else**. `fallback_tools`
and `provider_matrix` are runtime properties — no hardcoded list.

Routing (`execute()`, line 166):

1. discover candidates → `_filter_candidates` (custom-workflow eligibility, or
   edit-capable filter when `generation_mode=="edit"` / source images present);
2. score with `lib/scoring.rank_providers` — weighted
   `task_fit·0.30 + output_quality·0.20 + control·0.15 + reliability·0.15 +
   cost_efficiency·0.10 + latency·0.05 + continuity·0.05`; stock providers
   penalized ×0.55 when the prompt wants generated visuals;
3. honor `preferred_provider`, else top-ranked selectable tool;
4. adapt (rename `prompt`→`query` for stock; strip unsupported passthrough keys
   with a warning) → `tool.execute(adapted)`;
5. annotate result with `selected_tool/provider/score/alternatives_considered`
   **and `selected_tool_agent_skills`** — the Layer-3 bridge the orchestrator
   loads next.

Supports `operation: "rank"` (score without generating) — useful at preflight.

### 2.2 Concrete providers (`tools/graphics/`)

| tool | provider | runtime | cost | strength | `agent_skills` |
|---|---|---|---|---|---|
| `flux_image` | flux | API (fal.ai) | $0.03 dev / $0.05 pro | photoreal workhorse; neg-prompt, seed, custom size | `flux-best-practices`, `bfl-api` |
| `openai_image` | openai | API | $0.006–0.211/img | text-in-image, complex instructions; `gpt-image-2` | `flux-best-practices` |
| `google_imagen` | google_imagen | API (AI Studio / Vertex) | $0.02–0.06 | aspect-ratio based, no exact px/seed | — |
| `grok_image` | grok | API (xAI) | ~$0.02/out + $0.002/in img | **only true i2i edit / style transfer / multi-image composite**; `supports.image_edit=True` | `grok-media` |
| `recraft_image` | recraft | API (fal.ai) | $0.04–0.25 | **SVG vector**, text render, brand palette | — |
| `dashscope_image` | dashscope | API (Alibaba) | $0.02/img | Qwen-Image; zh prompts; n≤6; fallback `grok→openai→flux→recraft` | `dashscope` |
| `comfyui_image` | comfyui | LOCAL_GPU | free | **custom `workflow_json`/`output_node`**; bundled FLUX2 NVFP4; DEGRADED+`missing_models` payload when models absent; fallback `flux→local_diffusion→openai` | `comfyui`, `flux-best-practices` |
| `local_diffusion` | local_diffusion | LOCAL_GPU | free | offline/air-gapped `diffusers` SD 2.1 base | — |
| `pexels_image` / `pixabay_image` | pexels / pixabay | API | free | stock; `query` not `prompt` | — |
| `image_gen` | multi | HYBRID | varies | **DEPRECATED** (`best_for` literally says "prefer image_selector"); still discoverable | — |

Related graphics producers are a **different** capability family (`"graphics"`,
not routed by the selector): `diagram_gen` (Mermaid), `code_snippet` (Pygments),
`math_animate` (ManimCE). Image transform/enhance lives in `tools/enhancement/`:
`upscale` (Real-ESRGAN), `face_restore` (CodeFormer/GFPGAN), `bg_remove` (rembg),
`color_grade` / `face_enhance` (FFmpeg), `eye_enhance` (MediaPipe).

### 2.3 Cost governance

`tools/cost_tracker.py` — `estimate → reserve → reconcile` to `cost_log.json`,
with `single_action_approval_usd=$0.50`, `require_approval_for_new_paid_tool`,
and a `CAP` mode with a 10% reserve holdback. `estimate_from_reference()` does
pacing-aware estimation from a `VideoAnalysisBrief` (scenes from cuts/min, ×1.3
retry buffer).

## 3. The story→image contract (scene_plan ↔ asset_manifest)

Encoded in three places, all schema-backed:

**(a) `scene_plan.scenes[].required_assets[]`** —
`{type, description, source}`. Any `source: "generate"` becomes an
asset-director task. This is the explicit "make an image for this" instruction.

**(b) `scene_plan.scenes[].shot_language`** — the structured cinematography
vocabulary (`shot_size`, `camera_movement`, `lens_mm`, `lighting_key`,
`depth_of_field`, `color_temperature`) + `texture_keywords`. Converted to a
prompt by `lib/shot_prompt_builder.py` using a **5-layer framework**
(Camera → Movement → Subject → Lighting → Style) with enum→phrase maps
(`extreme_wide → "extreme wide shot showing vast environment"`, `dolly_in → …`,
`orbital → …`). `build_shot_prompt` / `build_batch_prompts` are the API.

**(c) The asset-director's prompt recipe** (`asset-director.md:108–119`):
build each prompt from (1) the scene's shot/intent/texture cues, (2) an
**adapted** visual anchor from the playbook (**never** the verbatim
`image_prompt_prefix`), (3) the concrete subject/action/environment; add the
playbook negative prompt; include `consistency_anchors` without copy-pasting;
generate via `image_selector`; verify file exists; max 2 retries with prompt
refinement. Every prompt runs through a **CHAI pre/critique/post self-review**
before send, logged in asset metadata.

**Back-validation:** `asset_manifest.assets[]` must carry `scene_id`,
`source_tool`, `prompt`, `seed`, `model` — every image traceable to the scene
that requested it. Manifest success criterion: "all file paths resolve."

## 4. The playbook as style contract

`schemas/styles/playbook.schema.json` (v2). Image-relevant sections:

```yaml
asset_generation:
  image_prompt_prefix: "..."        # distilled into an anchor, NOT pasted
  image_negative_prompt: "..."
  diagram_style: "..."
  consistency_anchors: [...]        # minItems 1 — what MUST stay consistent
visual_language:
  color_palette: {primary[], accent[], background, text, muted}
  chart_palette: [...]              # v2
  color_rules: {harmony_type, WCAG contrast, colorblind-safe}   # v2
```

Flow: manifest declares `compatible_playbooks` → proposal-director designs a
visual identity (and may generate a custom playbook via
`lib/playbook_generator.py`, recording `production_plan.playbook` + a
`playbook_selection` decision) → scene-director validates every scene against
the playbook (colors enforced, transitions/pacing rules) → asset-director folds
`image_prompt_prefix`/neg-prompt/anchors into per-scene prompts via
`shot_prompt_builder`. v2 `overrides` allow per-scene exceptions capped at
`max_deviation_ratio: 0.2` (a "20% deviation budget").

## 5. Side-by-side vs the MLX repo

The MLX repo (`python/mlx-movie-director/run.py`) is the **inverse** of
OpenMontage in one dimension: it is a **single generation runtime** (native MLX
on Apple Silicon) with no orchestration/story layer; OpenMontage is **all
orchestration/story** with no native generation (every provider is a cloud API
or a vendored ComfyUI). They are nearly complementary.

| Concern | OpenMontage | MLX repo (`run.py`) | Map |
|---|---|---|---|
| Orchestration / story | YAML manifests + director skills + schema artifacts | none | OM is the front; MLX is a backend |
| Image gen entry | `image_selector` (scored) | `image t2i` (+ angle/i2i/faceswap/quality/…) | OM selector → MLX adapter |
| Providers | fal/OpenAI/Google/Grok/Recraft/DashScope + ComfyUI + diffusers | Z-Image, Flux2 Klein, Lens (all MLX) | MLX = one more provider |
| ControlNet / i2i / regional | **gap** (only Grok edit) | full: controlnet, i2i pose/style, regional attn, faceswap | MLX fills OM's biggest hole |
| LoRA | none | import-lora-image, multi-LoRA, anime2real | OM has no LoRA story at all |
| Upscale / restore | Real-ESRGAN, CodeFormer, GFPGAN (torch) | ESRGAN (torch via vision-venv), SeedVR2 | overlap |
| Visual QA | planned `test_02_image_gen.py` (**missing**) | `caption` (Qwen3-VL), CLIP `video_understand` | MLX already has the QA brain |
| Prompt vocabulary | `shot_prompt_builder` 5-layer cinematography | prompt-only (no structured shot language) | OM's builder is portable |

**The mapping opportunity is concrete:** a new `mlx_image` provider tool in
`tools/graphics/` (capability `image_generation`, runtime `LOCAL_GPU`, cost
`0.0`, `agent_skills: ["mlx-movie-director"]`) that shells to
`python/mlx-movie-director/run.py image t2i|i2i|faceswap|...` would (a) be
auto-discovered by `image_selector` with zero selector edits, (b) give OM a
free ControlNet/i2i/LoRA/faceswap path it currently lacks, (c) be the cheapest
provider on the box (cost_efficiency bonus in the scorer). The selector's
`custom_workflow` + `output_node` machinery (already proven for `comfyui_image`)
is the template — `run.py` is structurally a custom-workflow backend.

## 6. Seams, gaps, and what I'd touch first

Verified gaps (from the tool-layer sweep):

1. **No ControlNet / inpainting / true img2img** — the scorer's `control`
   dimension weights `controlnet`/`inpainting`/`img2img`/`reference_image`
   `supports` flags, but only `grok_image` advertises `image_edit`. The MLX
   repo has all of these; a `mlx_image` provider closes it.
2. **Orphaned `faceswap` skill** — `.agents/skills/faceswap/` exists, but no
   `tools/**/faceswap*.py` does. Either add the tool (MLX repo has
   `image faceswap`) or remove the skill.
3. **`FAL_KEY` shared by `flux_image` + `recraft_image`** — one env var lights
   both up; the scorer then ranks between them on `best_for` prose alone.
   Split or document.
4. **`image_gen` (deprecated) still discoverable** — appears under
   `provider="multi"` in `provider_menu` unless filtered; `best_for` steers the
   scorer off it, but it is not hard-excluded.
5. **`test_02_image_gen.py` missing** — called out in `tests/qa/QA_PLAN.md`,
   never on disk. The image QA lane is unwritten.
6. **No `schemas/tools/*.schema.json` for image tools** — contracts live only
   inline on the class (`input_schema`/`output_schema`); fine, but inconsistent
   with `video_stitch.schema.json`.

What I'd land first (smallest high-value step): the **`mlx_image` provider**.
It is the single change that (a) fills OM's ControlNet/i2i/LoRA gap, (b) gives
the MLX repo a real story/orchestration front-end, and (c) costs $0 — which the
scorer rewards. The selector pattern means it is a one-file add; the
`comfyui_image` custom-workflow path is the structural twin.

## 7. File reference (story→image only)

```
pipeline_defs/{animated-explainer,animation,cinematic,hybrid}.yaml
skills/pipelines/explainer/{idea,proposal,script,scene,asset}-director.md
skills/pipelines/animation/asset-director.md            # image-animation multi-image workflow
schemas/artifacts/{brief,research_brief,script,scene_plan,asset_manifest}.schema.json
schemas/styles/playbook.schema.json
styles/{clean-professional,flat-motion-graphics,minimalist-diagram,anime-ghibli}.yaml
tools/graphics/image_selector.py                         # THE routing entry point
tools/graphics/{flux,openai,google_imagen,grok,recraft,dashscope,comfyui,local_diffusion,pexels,pixabay}_image.py
tools/enhancement/{upscale,face_restore,bg_remove,color_grade,face_enhance,eye_enhance}.py
lib/shot_prompt_builder.py                               # shot_language → prompt
lib/scoring.py                                           # rank_providers weighted score
lib/playbook_generator.py                                # custom playbook synthesis
styles/playbook_loader.py                                # load + validate
skills/creative/{image-gen-usage,image-provider-usage}.md
.agents/skills/{flux-best-practices,bfl-api,grok-media,dashscope,comfyui}/   # Layer 3
```
