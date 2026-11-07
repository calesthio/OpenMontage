# IMAGE QC v2 — objective checks, honest numbers (P4)

**Scope:** `tools/illustration/illustration_qc.py`, `tools/illustration/text_detect.py`,
`tools/illustration/review_queue.py`, `tools/illustration/owner_review.py`,
driver `scripts/image_review.py`, thresholds `config/qc_thresholds.json`
(section `illustration_qc` - **new keys only, no existing threshold changed**).
**Anatomy, composition and beauty stay OWNER-judged.** No tool here scores them.
**No new runtime dependency:** numpy 2.5.4 + Pillow 13.0.0 only (checked:
`pip list`, `which tesseract` -> no OCR engine installed).

## 1. The weakness that was fixed

The old text-like heuristic looked for **thin near-white horizontal bands in
the top/bottom thirds**. It

- **missed lettering**: dark-on-light text, light-on-dark text, text in the
  middle of the plate and text outside the thirds were all invisible to it;
- **over-fired on flat art**: a wide light band across a flat illustration
  looked like a caption chip. In the P3 live job it flagged 2 of 24 images
  (`frozen_ocean_food_web_r0024/r0039`) - both flat plates without lettering.

The new detector (`text_detect.py`) is a **connected-component** method:

1. grayscale, scaled to a 1024 px analysis width;
2. a local background by morphological dilation/erosion (window 25) - so
   thick strokes stay detectable;
3. "ink" = pixels that differ from the local background by more than 14
   (both polarities are tried: dark-on-light and light-on-dark);
4. connected components of the ink mask (run-length union-find, numpy only);
5. a component is a **glyph** when it is small, character-shaped, filled and
   **thinner than it is tall** (the mean horizontal run <= 0.38 x height) -
   this is what separates a letter from a filled dot;
6. glyphs are grouped into **text lines** by baseline and spacing; a line
   needs >= 3 glyphs, a height of at least 6 px, a consistent baseline
   (spread <= 0.35 x height), non-overlapping glyphs and no all-identical
   shapes (a row of pebbles is an ornament, not lettering).

The old band heuristic is still computed, but as a **separate flag**
(`band_artifact`) - it no longer decides the text verdict.

## 2. Measured precision / recall (synthetic fixture set)

Fixtures are generated at test time (`scripts/make_qc_fixtures.py`, Pillow
only): 8 text images (dark-on-light, light-on-dark, small, centred, corner,
caption chip, wide tracking, text over texture), 8 clean images (flat
two-tone, flat art with a wide light band, flat panels, line art, dot grid,
gradient, noise, a row of bright blobs) and 2 ambiguous ones (a row of
dashes, a barcode - glyph-like but not lettering).

| Set | TP | FP | TN | FN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|
| labelled fixtures (16) | 8 | 0 | 8 | 0 | **1.000** | **1.000** | **1.000** |
| ambiguous (2, reported separately) | - | - | - | - | dashes: not flagged, barcode: not flagged | | |

Honest caveats:

- The fixture set is **synthetic** and small (16 labelled images). It is
  separable by construction, so 1.00/1.00 is a **floor for this method on
  this set**, not a general accuracy claim.
- On the **real** episode images (36 files in
  `projects/se_pilot/assets/illustrations/`) the new detector flags **1**
  (`frozen_ocean_food_web_r0025.png`) - a flat plate whose small lime shapes
  read as characters. It is a **false positive**: the old heuristic flagged
  3 of the same 36 (also false positives). The remaining error class needs
  a real OCR detector; the dependency request is **SCR-11** in
  `docs/openmontage/SPEC_CHANGE_REQUESTS.md` (nothing was installed).
- Cost: **~0.17 s per image** (1024 px analysis), no network.

## 3. The objective checks

| Check | What it measures | Flag |
|---|---|---|
| blur | Laplacian variance | `blur_low` (floor 100.0) |
| aspect | target ratio within 1 % | `size_mismatch` |
| size | exact target frame (1344x768 for the episode) | `size_mismatch` |
| text | the connected-component detector | `text_like` |
| band | the old caption-chip heuristic | `band_artifact` (reported, not a verdict) |
| palette | the share of pixels close to a style palette colour (distance <= 70); drift when the coverage is below 4 % or the dominant colour is off-palette and the off-palette share is above 92 % | `palette_drift` |
| duplicate | average hash **and** difference hash within Hamming 8, plus a mean-brightness guard (two different flat images share an all-zero hash) | `duplicate` |

The palette check reads the **style file** (`docs/openmontage/niches/<niche>/style.json`),
so a drift means "this plate does not use the niche palette" - an objective
fact, not a taste judgement.

## 4. The REVIEW queue

`scripts/image_review.py --episode se_pilot queue` builds
`review_queue.json` + `review_queue.csv` in the episode assets:

- every image with at least one objective flag is queued;
- the priority is the sum of the flag weights (text 60, size 40, palette 25,
  blur 20, duplicate 15);
- the queue states in every file that **anatomy, composition and beauty stay
  owner-judged**;
- the current pilot queue: 36 images -> 12 queued (1 text, 11 blur).

## 5. The owner approved/rejected ledger (CSV)

`projects/<episode>/assets/illustrations/owner_review.csv`:

```
render_id,prompt_sha256,sha256,decision,reviewer,reviewed_utc,note
```

- `approved` - the image may be used and is **never regenerated**; the P3
  cache (`tools/illustration/episode_run.py`) reads the ledger in `plan()` and
  marks the render `approved`.
- `rejected` - the image must not be used: the run re-queues it with a **new
  seed** (a concrete change) and, after 4 attempts, marks it
  `rejected_exhausted`; the episode then fails closed in `finalize()` because
  the usable count is below the prompt count.
- The old `approved.json` cache still works; the CSV ledger is read in
  addition to it.

```bash
python scripts/image_review.py --episode se_pilot queue
python scripts/image_review.py --episode se_pilot approve --render-id r0027
python scripts/image_review.py --episode se_pilot reject  --render-id r0030 \
    --note "flat, no detail"
python scripts/image_review.py --episode se_pilot ledger
```

## 6. Tests

- `tests/illustration/test_qc_text_detector.py` (7) - the fixture set, the
  flags, the precision/recall floor (>= 0.95), the ambiguous cases reported
  separately, the evidence in the result.
- `tests/illustration/test_qc_v2.py` (14) - size/aspect, palette drift,
  episode duplicates, the review queue (order, objective flags only, no
  anatomy judgement, CSV+JSON), the owner ledger round trip and the P3 cache
  reading it (approved -> never regenerated, rejected -> re-queued).
- `tests/tools/test_illustration_qc.py` (7) - updated: the band heuristic is
  now a separate flag, not a text verdict.

## 7. Not done

- No OCR dependency was installed (SCR-11 is a request; the heuristic stays).
- No threshold value was changed; the new keys were added with a documented
  rationale and the values live in `config/qc_thresholds.json`.
- No tool judges anatomy or beauty; the queue only carries objective flags.
