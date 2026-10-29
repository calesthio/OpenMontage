# S15 — DreamShaper XL 1.0 style-lock run (facts, no style verdict)

Job `s15-style-lock-1` · one fresh Kaggle T4 · fp16, no bf16, no bitsandbytes,
no offload · recipe frozen in `recipe_dreamshaper_xl_1_0.json` · module contract
in `IMAGE_MODULE_SPEC.md`.

## What ran

- 36 images @1024×1024: 6 scenes × 3 styles × seeds 1001/2027.
- 6 images @1344×768 (16:9): the style with the best objective flags
  (`graphic-novel-ink`, all three tied at 20 bad-flag points; ink won the
  caption-dark-fraction tie-break), one per scene, seed 1001.
- Prompts exactly as sent: `s15_prompts.json`. Style strings are byte-identical
  across scenes; every prompt ends with the fixed tail; negative prompt common.

## Objective results

| Check | Result |
|---|---|
| images generated / requested | 42 / 42 |
| `DONE.json` | `status: ok`, `n_black: 0` |
| bridge verify (sha256) | PASS, 42/42 |
| black / NaN / OOM | 0 / 0 / 0 |
| resolution | 36×1024², 6×1344×768, 0 bad |
| blur (absolute + vs cell median) | 0 flagged |
| near-duplicate dHash pairs | 2 (same scene, different styles: s06 1001 hamming 6; s10 1001 hamming 3) |
| caption fifth (20 %) unreadable | 5/36 square, 0/6 wide |
| caption legacy band (28 %) unreadable | 6/36 square, 0/6 wide |
| watermark-suspect corners | 3/42 (paper-cut s03 ×2, s10 ×1) |
| warm speed | 26.0 s/img median (square), 25.8 s/img (wide) |
| peak VRAM | 9 968 MB alloc / 12 828 MB reserved |
| VAE fallback | not used (stock VAE clean) |

## Gates (owner-applied, still open)

0 black/NaN → **PASS** (objective). Anatomy ≥14/18 per style, caption space
≥15/18 per style, phone readability median ≥4/5 → **OWNER_GATED**: the owner
fills `projects/s15/blind/scoring.csv`, then `python scripts/s15_tally.py`.

Blind pack: `projects/s15/blind/` (gitignored) — 9 sheets × 2 variants
(plain with caption-zone band, `_captioned` with sample subtitle), tiles
K1..K42 in randomised order, no style/seed in file names, `mapping.json`
sealed.

## Notes for the owner

- Three frames have a suspect corner; the report does not decide whether it is
  a watermark or illustration texture.
- Two cross-style near-duplicate pairs exist at seed 1001 (s06 and s10); if a
  style pair looks identical in the blind review, this is why.
- The S10 habitat wording "vent chimney field with black smokers" is sometimes
  rendered as an industrial smokestack scene. That is content fidelity, not
  style, and it matters for any habitat plate that ships as a factual visual.
