# S10 state — visual-style test (Kilo)

**Goal:** compare THREE visual styles on the same six frozen-alien-ocean scenes
(2 creatures, 2 habitats, 1 food-web plate, 1 wide scene), same seeds,
1024x1024, 3 images per style per scene = **54 images in ONE kernel run**.

**Rule:** resume at the first phase whose status is not in {DONE, OWNER_GATED,
BLOCKED}. Repository reality outranks this file. Scope: `docs/`, `tools/` (not
`tools/prompting/`), `scripts/` (not `score_rubric.py`), `tests/`, `config/`,
`.kilo/`. fp16 only, no bitsandbytes, no paid routes, no secrets printed, no
media in git, own paths only.

**Locked model:** `config/image_engine.json` -> `model: klein`
(FLUX.2-klein-4B, prompt target `klein`, variant C, 4 steps, guidance 1.0,
fp16, CPU offload) — used as-is, no model change in S10.

## Styles under test (no artist, channel or franchise named)

| key | style | prompt block (rendered by `tools/prompting/builder.py`) |
|---|---|---|
| S-A | flat vector illustration | saturated colour, bold contours, smooth gradients, rich coloured background, readable shapes, no texture noise |
| S-B | natural-history gouache field-guide plate | warm paper texture, visible brush strokes, detailed anatomy, muted-but-varied palette |
| S-C | layered paper-cut diorama | foreground/midground/background layers, soft drop shadows, clear depth |

## Phases

| Phase | Status | Evidence |
|---|---|---|
| S10-1 BUILD TEST SET | DONE | `scripts/s10_build_testset.py` -> `docs/openmontage/image_gen/S10_TEST_SET.json` (6 scenes x 3 styles x 3 seeds = 54; seeds 3100-3152, same three seeds per scene across styles; per-scene palette + background; anatomy counts in creature prompts; style tokens asserted; no "plain background", no named artist). `tests/test_s10_style_test.py` 16 passed. |
| S10-2 ONE KERNEL RUN | DONE | `scripts/s10_push_style_test.py` job `s10-style-test-1`, kernel `forts845/openmontage-runner`, GPU+internet, 54 renders, ladder `released_037_x4` -> `released_037_x5` -> `released_041_x5_ao` (released only), fp16, model config from the config lock. Kernel status `COMPLETE`; 54/54 rendered, load 119.2 s, 25.08 s/img steady, peak VRAM 7 995 MB. |
| S10-3 FETCH + VERIFY | DONE | `scripts/s7_fetch.py klein --prefix s10 --job-id s10-style-test-1` -> bridge `verify` **PASS** (manifest valid, sha256 match on all 54 PNGs, 0 black, 0 NaN, 0 OOM). Logs: `docs/openmontage/image_gen/logs/s10-style-test-1/`. Images: `/tmp/kilo/s10_out/klein/s10_bakeoff_klein/images/`. |
| S10-4 OBJECTIVE CHECKS | DONE | `S10_CHECKS.json`: 0 resolution/blur flags anywhere, 0 duplicates, 1 colour-spread flag (S-C), caption-contrast flags S-A 3 / S-B 6 / S-C 4, text-like flags S-C 2. |
| S10-5 BLIND PACK | DONE | `projects/s10_blind/`: 6 plain sheets + 6 caption sheets, `mapping.json` separate, `results.csv` empty, `INSTRUCTIONS.txt`. |
| S10-6 REPORT | DONE | `docs/openmontage/image_gen/STYLE_TEST_S10.md`. Style winner remains OWNER_GATED; style bible untouched. |
| S10-7 OWNER SCORING | OWNER_GATED | owner fills `projects/s10_blind/results.csv`; then `python scripts/s10_tally.py`; only then may the style bible be updated |

## Commands

```
python scripts/s10_build_testset.py
python -m pytest tests/test_s10_style_test.py -q
python scripts/s10_push_style_test.py --timeout 3600
python scripts/s7_fetch.py klein --prefix s10 --job-id s10-style-test-1
python scripts/s10_checks.py --images ... --manifest ... \
    --mapping projects/s10_blind/mapping.json \
    --out docs/openmontage/image_gen/S10_CHECKS.json
python scripts/s10_blind_pack.py --images ... --manifest ...
python scripts/s10_tally.py            # owner, after filling results.csv
```

## Notes / risks

- The kernel runner's `manifest.json` records the prompt per image, so the
  committed log is **not** blind. Only `projects/s10_blind/` is blind; the
  owner must not open `mapping.json` before filling the CSV.
- The two habitat scenes and the wide scene carry a zero anatomy count
  (`0 limbs, 0 eyes, 0 horns`) because the read-only builder always renders the
  counts line. Identical across styles, so the comparison is unaffected.
- Image quality/style is the **owner's** call; the agent produces objective
  flags only and declares no style winner.
