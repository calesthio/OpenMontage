# Image module spec — DreamShaper XL 1.0 (frozen)

Milestone: **S15** · status: **style-lock test run, owner scoring pending** ·
owner: FORTS_FACTORY · model licence: OpenRAIL++ (commercial use with
use-based restrictions).

This document is the contract for the factory image module. It freezes the
model, the runtime knobs and the prompt contract so that a re-render months
from now produces the same module — not a look-alike. Anything not written
here is free to change; anything written here may only change with a new
milestone and a new recipe file.

| File | Role |
|---|---|
| `recipe_dreamshaper_xl_1_0.json` | machine-readable frozen recipe (the source of truth) |
| `licenses/dreamshaper-xl-1-0_LICENSE.md` | licence evidence saved with the recipe |
| `S15_RESULTS.csv` | per-image log (style, scene, seed, size, steps, cfg, warm s/img, VRAM, black/NaN, file) |
| `S15_STATS.json` | per-style / per-bucket aggregates + the wide-style decision |
| `S15_CHECKS.json` | objective flags (black/NaN, blur, duplicates, caption fifth, corner artefacts) |
| `s15_prompts.json` | every prompt exactly as sent (audit trail) |
| `projects/s15/blind/` (gitignored) | blind sheets, `mapping.json` (sealed), `scoring.csv` |

## 1. Frozen recipe

Model: **`Lykon/dreamshaper-xl-1-0`**, revision
**`41e6644752a8c9aa63930e6043c4fd83c7708420`** (HF `sha` at freeze time).
`StableDiffusionXLPipeline`. No other model is part of this module.

| Knob | Value | Why |
|---|---|---|
| dtype | `torch.float16` | T4 has no usable bf16 throughput; fp16 matches the vendor card |
| bf16 | **off** | not permitted in this module |
| bitsandbytes / quantisation | **off** | quality drift is not measurable against a 4-bit baseline |
| CPU offload | **off** | the model fits a 16 GB T4 (measured 9.97 GB allocated) |
| scheduler | `DEISMultistepScheduler` (`from_config`, no kwargs) | vendor card |
| steps | **25** | vendor card |
| CFG | **5.5** | vendor card |
| VAE | stock DreamShaper XL VAE | fallback `madebyollin/sdxl-vae-fp16-fix` **only** on NaN/black, logged per image, and only with owner approval |
| resolution | 1024×1024 stills; 1344×768 (16:9) wide | 1344×768 is the widest 16:9 bucket inside T4 memory |
| seeds | 1001, 2027 | fixed pair for every style × scene cell |
| watermarker | diffusers default, **not** disabled | invisible watermarking stays on; visible corner artefacts are flagged, never painted out |

Versions (must be recorded per run, from the kernel's `install_log.json`):

| package | version |
|---|---|
| torch | 2.11.0+cu128 (CUDA 12.8) |
| diffusers | 0.37.0 |
| transformers | 4.57.6 |
| huggingface_hub | 0.36.2 |
| accelerate | 1.14.0 |
| safetensors | 0.8.0 |
| Python / GPU | 3.13.15 / Tesla T4 16 GB |

Measured performance (S12, 18 images, same recipe): load **87.7 s**, median
warm **26.3 s/img**, mean warm **25.5 s/img**, peak VRAM allocated **9 968 MB**,
peak reserved **12 828 MB**, 0 black, 0 NaN, 0 OOM.

Measured performance (S15, one fresh T4, 42 images):

| Bucket | Images | Median warm s/img | Mean warm s/img | Peak alloc MB | Peak reserved MB | black/NaN/OOM |
|---|---|---|---|---|---|---|
| 1024×1024 | 36 | 26.005 | 25.832 | 9 968 | 12 828 | 0 / 0 / 0 |
| 1344×768 | 6 | 25.761 | 25.765 | 9 921 | 12 828 | 0 / 0 / 0 |

Load 84.9 s, GPU time 1 114.7 s for all 42 images, install stack
`released_037_x4`, bridge verify PASS (all 42 sha256 match), `DONE.json`
status `ok`. The stock VAE held: the `sdxl-vae-fp16-fix` fallback was **not**
used. The wide bucket costs no extra VRAM on this grid, only disk.

## 2. Prompt contract

Every prompt is built in this order and nothing else may be added:

1. anatomy line (creature scenes only — see §3),
2. scene subject (verbatim from `S10_TEST_SET.json`),
3. environment + light (verbatim),
4. style string (verbatim, identical across scenes),
5. camera (verbatim) + the fixed tail:

```
stylized, non-photorealistic, empty low-detail lower fifth for captions, no text
```

Common negative prompt (never varied inside a run):

```
photorealistic, photo, glossy 3D render, mirror reflections, text, letters,
watermark, signature, logo, extra limbs, fused anatomy, duplicated creature,
cluttered bottom edge
```

Style strings (palettes translated into colour words — no hex codes reach the
model):

- **A paper-cut** — `layered hand-cut paper shapes, matte paper fiber, clean cut
  edges, separate foreground midground background, broad directional light, soft
  cutout shadows, deep navy, mineral teal, sea-glass, shell ivory, one coral
  accent`
- **B field-guide** — `naturalist field-guide illustration, clean ink outline
  with thicker outer contour, opaque gouache colour masses, restrained
  watercolor texture, warm paper, graphite, sea-ink, kelp green, mineral blue,
  one rust-coral accent`
- **C graphic-novel ink** — `bold graphic-novel ink illustration, thick outer
  contour, sparse hatching, large flat shadow masses, limited halftone, night
  ink, deep sea, electric teal, pale bone, one coral accent`

## 3. Anatomy control

S10 defines the cast. The only measured anatomy sentence used in this module
is, verbatim:

```
exactly six separate tendrils, two pairs of fins
```

It is applied to the limbed creature only (S10 `limb_count = 6`): the vent
grazer in `s01` and the grazer inside the `s10` food-web plate. The filter
drifter (`s03`, `limb_count = 0`) is prompted as limbless (`no legs, no arms,
one continuous undulating fin, wide filter mouth`) — putting a six-tendril
sentence on a deliberately limbless creature would contradict S10 and would
bias the owner's anatomy score. This is the only intentional deviation from a
literal "every creature scene" reading; the full prompt text is in
`s15_prompts.json`.

## 4. Known failure modes

1. **Style drift.** Style strings are long, and SDXL will trade style tokens
   against scene tokens (e.g. paper-cut degrades into flat vector; ink gains
   halftone density it was not asked for). Mitigation: identical style string
   everywhere, one style per prompt, no style mixing; style is judged blind per
   tile, and the frozen strings may not be edited between scenes.
2. **Appendage counts.** Six tendrils + two pairs of fins is beyond what SDXL
   reliably counts; expect fused/missing/extra tendrils and duplicated
   creatures. Mitigation: anatomy sentence first in the prompt, negative prompt
   carries `extra limbs, fused anatomy, duplicated creature`, and the owner
   scores anatomy per tile. Do **not** "fix" this with a LoRA or IP-Adapter in
   this module — that is a separate decision.
3. **Watermark-like artefacts.** The pipeline's watermarker is left at its
   default; a visible faint repeating pattern or text-like mark can still
   appear in a corner. `S15_CHECKS.json` reports such corners as **suspect**
   (2-D autocorrelation lattice peak away from both axes, or ≥5 aligned small
   components); it never auto-rejects. The owner decides. Never inpaint them
   away silently — that breaks provenance.
4. **Caption-zone violations.** The prompt asks for an empty lower fifth; the
   model does not always obey. `S15_CHECKS.json` measures the bottom **20 %**
   band (dark fraction for white text, busy fraction) and flags unreadable
   panels; the S10 28 % band is reported for continuity.
5. **Wide-bucket memory.** 1344×768 uses more activation memory than 1024².
   The wide pass runs after the square pass and logs per-image VRAM; OOM is
   recorded per image and never retried at a different size in the same run.
6. **VRAM measurement.** Peak memory is reset before every render, so the
   logged peak is per image; the manifest keeps the max across the run.

### Observed in this run (S15, facts only — no style or anatomy verdict)

- **0 black, 0 NaN, 0 OOM** across 42 images; every file passed sha256 verify.
- **Caption fifth:** 5 of 36 square frames fall under the caption-contrast
  threshold at 20 % (`S15_CHECKS.json` → `caption_fifth_flagged`; 6 of 36 at the
  S10 28 % band). All 6 wide frames pass. Owner scores caption space blind.
- **Near-duplicate pairs:** two same-scene cross-style pairs are below the dHash
  duplicate threshold — `field-guide` vs `graphic-novel-ink` on `s06` seed 1001
  (hamming 6) and on `s10` seed 1001 (hamming 3). Flagged, not rejected.
- **Watermark-like corners:** 3 of 42 frames carry a suspect corner
  (`paper-cut` s03 ×2, s10 ×1). Listed in `S15_CHECKS.json`; the owner decides
  whether they are real watermark artefacts or illustration texture.
- **Semantic drift on habitat wording:** the S10 text "vent chimney field with
  black smokers" is read by the model as industrial smokestacks in several
  frames. That is a content-fidelity risk for habitat plates, not a style
  failure; it is recorded for the layering decision (a habitat plate shipped to
  camera must be checked by a human for what it actually shows).

## 5. Layering policy (binding for this module)

The image module produces **backgrounds and habitats only**:

- **From the model:** habitat plates and planet-surface wides (`s05`, `s06`,
  `s12`) and the environment/light layer of every scene. These are the images
  the pipeline consumes.
- **Creature as a separate simple layer, later:** creatures are drawn as a
  separate, simple layer (vector or cut-out) in a later milestone so that
  appendage counts are exact and reusable across episodes. Until then, creature
  images from this module are **reference/atmosphere only**, never a
  diagrammatic claim about anatomy.
- **Captions, labels and diagrams live in the editor only** — burned in by the
  composition step, never generated by the model. The model's job is to leave
  the lower fifth empty; it is not asked to draw letters, arrows or legends.

Out of scope for S15 (explicitly **not** implemented): layering/compositing
code, IP-Adapter, LoRA training or loading, ControlNet, any new model, any
paid API. Adding any of these requires a new milestone, a new recipe file and
owner approval.

## 6. Gates (owner-applied)

`python scripts/s15_tally.py` joins `scoring.csv` with the sealed
`mapping.json` and applies:

| Gate | Threshold | Source |
|---|---|---|
| black / NaN | 0 images | objective, `S15_CHECKS.json` |
| anatomy per style | owner gate 14/18, applied as a ratio (≥ 0.778) of the creature tiles scored for that style | owner, blind |
| caption space per style | owner gate 15/18, applied as a ratio (≥ 0.833) of scored tiles | owner, blind |
| phone readability | median ≥ 4/5 | owner, blind on `_captioned` sheets |

The tally refuses to report a verdict while `scoring.csv` is incomplete
(`OWNER_GATED`). No LLM scores anatomy or style. Nothing is locked on partial
data.

## 7. Reproduce

```bash
# push the frozen job to ONE fresh Kaggle T4 kernel (fp16, no bf16, no bnb)
python scripts/s15_push_style_lock.py

# poll real status until terminal (bridge poll), then fetch + verify:
python scripts/s15_collect.py --job-id s15-style-lock-1

# from the manifest path printed by the collector:
python scripts/s15_assemble.py    --manifest <out>/manifest.json
python scripts/s15_checks.py      --manifest <out>/manifest.json \
                                  --mapping projects/s15/blind/mapping.json
python scripts/s15_blind_pack.py  --manifest <out>/manifest.json
# owner fills projects/s15/blind/scoring.csv
python scripts/s15_tally.py
```

The kernel writes `/kaggle/working/DONE.json` in every path (success, partial,
crash) and is polled by real status, never by a fixed sleep.
