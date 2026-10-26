# S10 — visual-style test report

**Status:** renders + fetch + objective checks + blind pack are DONE.
**Style winner: OWNER_GATED** — the owner has not scored `projects/s10_blind/results.csv`
yet, so this report declares **no** winner and the style bible is unchanged.

This file is **not blind** (it names the styles). It is safe to read before
scoring; `projects/s10_blind/mapping.json` is the file the owner must not open
until the CSV is filled.

## 1. What ran

| Item | Value |
|---|---|
| Job | `s10-style-test-1` |
| Kernel | `forts845/openmontage-runner` (GPU T4, internet) |
| Model | `black-forest-labs/FLUX.2-klein-4B` (`Flux2KleinPipeline`), config lock `config/image_engine.json -> klein` |
| dtype / steps / guidance | fp16 / 4 / 1.0 |
| Load path | `pipe.enable_model_cpu_offload()` (never `.to("cuda")`), peak VRAM 7 995 MB of 16 GB |
| Resolution | 1024x1024 |
| Test set | `docs/openmontage/image_gen/S10_TEST_SET.json` — 6 scenes x 3 styles x 3 seeds = **54** |
| Seeds | per scene `3100/3101/3102`, `3110..3112`, `3120..3122`, `3130..3132`, `3140..3142`, `3150..3152` (same three seeds per scene across styles) |
| Styles | S-A flat vector illustration, S-B natural-history gouache field-guide plate, S-C layered paper-cut diorama |
| Scenes | s01 vent grazer (creature), s03 filter drifter (creature), s05 vent chimney field (habitat), s06 under-ice cavern (habitat), s10 food-web plate, s12 frozen-surface wide |

Prompt source: `tools/prompting/builder.py` (read-only), target `klein`, variant C.
Prompt tokens asserted by `tests/test_s10_style_test.py` (16 passed): no named
artist/channel/franchise, no "plain background", anatomy counts present in
creature prompts, style tokens present.

## 2. Fetch + verify (S10-3) — PASS

`python scripts/s7_fetch.py klein --prefix s10 --job-id s10-style-test-1`

| Check | Result |
|---|---|
| Kernel status | `COMPLETE` |
| Manifest valid | true |
| sha256 of all 54 PNGs vs kernel manifest | match (fail-closed bridge `verify`) |
| Generated / requested | 54 / 54 |
| Black frames | 0 |
| Non-finite (NaN) | 0 |
| OOM | 0 |
| Wall cap | not hit (5 400 s cap) |

Artefacts (text only, media stays in `/tmp/kilo/s10_out/klein/`):

- `docs/openmontage/image_gen/logs/s10-style-test-1/status.txt`
- `docs/openmontage/image_gen/logs/s10-style-test-1/summary.json`
- `docs/openmontage/image_gen/logs/s10-style-test-1/manifest.json` (includes every prompt)
- `docs/openmontage/image_gen/logs/s10-style-test-1/install_log.json`
- `docs/openmontage/image_gen/logs/s10-style-test-1/kernel.log`

Images: `/tmp/kilo/s10_out/klein/s10_bakeoff_klein/images/` (p001..p054).

## 3. Cost of the run

| Metric | Value |
|---|---|
| Load time | 119.2 s |
| Steady-state sec/image (first excluded) | 25.08 s |
| Median sec/image | 25.10 s |
| Usable images/minute | 2.24 |
| GPU seconds | 1 446.5 |
| Peak VRAM | 7 995 MB @ T4 16 GB |

## 4. Stack, pinned (from `summary.json -> versions`)

torch `2.11.0+cu128` · diffusers `0.37.0` · transformers `4.57.6` ·
huggingface_hub `0.36.2` · accelerate `1.14.0` · safetensors `0.8.0` ·
numpy `2.1.3` · pillow `12.3.0` · CUDA `12.8` · python `3.13.15` ·
GPU Tesla T4. Install ladder rung 1 (`released_037_x4`) worked first try, no
bitsandbytes, no CPU fallback.

## 5. Objective flags (S10-4) — `S10_CHECKS.json`

These are "look at this frame" flags, **not** verdicts.

| Metric | S-A flat vector | S-B gouache plate | S-C paper-cut |
|---|---|---|---|
| images | 18 | 18 | 18 |
| resolution bad | 0 | 0 | 0 |
| blur (absolute) | 0 | 0 | 0 |
| blur (relative) | 0 | 0 | 0 |
| colour-spread flagged | 0 | 0 | 1 |
| caption-contrast flagged | 3 | 6 | 4 |
| text-like flagged | 0 | 0 | 2 |
| mean Laplacian var | 343.5 | 784.8 | 260.3 |
| mean saturation | 0.556 | 0.204 | 0.347 |
| mean hue entropy (bits) | 2.90 | 2.88 | 2.49 |
| mean caption-band dark fraction | 0.73 | 0.48 | 0.53 |

Reading of the flags (mechanical, no style preference implied):

- S-B has the highest detail energy (gouache brushwork) but the lowest
  saturation and the most caption-contrast flags (6/18) — the muted paper
  background fights white subtitles in the lower band more often.
- S-A has the most consistently dark caption band (0.73) and only 3 caption
  flags, i.e. the friendliest of the three for burned-in subtitles.
- S-C produced 2 text-like frames and 1 low-colour-spread frame — worth an eye
  on those panels before use.
- No duplicates were detected (`duplicates: []`).

Caption-band rule used: bottom 28% of the frame, white subtitle, flag when the
band is too bright or too busy for readable text.

## 6. Blind pack (S10-5) — `projects/s10_blind/`

- `sheet_s01.png` … `sheet_s12.png` — three panels A/B/C, **randomised order
  per sheet**, no style names.
- `sheet_<scene>_caption.png` — same panels with the narration caption burned
  into the bottom of each panel.
- `mapping.json` — panel → style, **do not open before scoring**.
- `results.csv` — scoring sheet, currently empty.
- `INSTRUCTIONS.txt` — the 5–10 minute procedure.

Scoring columns: `best_panel`, `worst_panel`, `readable_with_captions_A/B/C`,
`comment`, per scene (s01, s03, s05, s06, s10, s12).

Captions burned into the caption sheets:

| Scene | Caption |
|---|---|
| s01 | The vent grazer crops bacterial mats at the chimney rim. |
| s03 | Filter drifters sieve microbes from the open water column. |
| s05 | Chimney fields vent mineral-rich water onto the sea floor. |
| s06 | Melt pools glow beneath the frozen ice shell. |
| s10 | Chemosynthetic bacteria feed the whole vent food web. |
| s12 | Plumes break through the ice crust of the frozen ocean world. |

## 7. Next step (owner)

1. Open the six plain sheets, fill `best_panel` / `worst_panel`.
2. Open the six `_caption` sheets, fill `readable_with_captions_A/B/C`.
3. `python scripts/s10_tally.py` — prints wins/losses/caption readability per
   style and refuses to recommend anything until the CSV is complete.
4. Only then may `ILLUSTRATION_STYLE_BIBLE.md` record the winner.

Until step 3 completes, S12 (the 54-image model bake-off) uses the
**flat-vector field-guide** look — S-A's flat vector rendering with the
field-guide plate structure (labelled copy space, specimen framing). That
choice is provisional and is stated in the S12 report.

## 8. Known limitations

- One image per style per scene is in the blind sheets (the scene's first
  seed); the other two seeds are represented by objective flags only, so the
  owner's judgement rests on 18 panels, not 54.
- The two habitat scenes and the wide scene carry a zero anatomy count
  (`0 limbs, 0 eyes, 0 horns`) because the read-only builder always renders the
  counts line. Identical across styles, so the comparison is unaffected.
- Caption contrast is measured on a synthetic white subtitle; the production
  caption style (outline, drop shadow, position) may differ.
- Image quality and style are the owner's call; no agent verdict is recorded
  here.
