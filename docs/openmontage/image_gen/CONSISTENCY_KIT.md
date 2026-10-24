# CONSISTENCY KIT — canonical creature sheets with the LOCKED model (P2)

**Locked model:** `klein` → `black-forest-labs/FLUX.2-klein-4B`
(`config/image_engine.json` → `model`, status `OWNER_GATED`;
prompt target `klein`, variant C, 4 steps, guidance 1.0, fp16).
**Kit code:** `tools/illustration/style_kit.py`, `tools/illustration/creature_sheet.py`,
driver `scripts/creature_sheet.py`.
**Style files:** `docs/openmontage/niches/<niche>/style.json` + `STYLE_BIBLE.md`
(4 niches: space_iss, art_history, speculative_science, speculative_evolution).
**Input specs:** `docs/openmontage/niches/speculative_evolution/creatures/*.yaml`
(OpenCode-owned, **read only** — the kit never writes them).
**Roles:** inline, not independent. Image quality is judged by the **owner**.

## 1. What the kit produces

For every creature (or habitat) spec it produces a **canonical sheet**: the
same subject in the **front**, **side** and **three-quarter** view, each
with

- the **anatomy counts written into the prompt** (`6 limbs, 2 eyes, 0 horns`),
- the **canonical silhouette** (first clause) as the identity anchor,
- the niche's palette, line style, camera vocabulary and constraints,
- its **own fixed seed** (never shared inside a batch),
- and — for the locked model — the side and three-quarter views generated
  **from the front view as a reference image**.

The job file is **deterministic**: the same spec + style + model produce a
byte-identical JSON (no timestamps inside). Verified by
`tests/illustration/test_style_kit.py`.

```
spec (YAML, read only)  ->  style.json  ->  prompt (tools/prompting, read only)
                        ->  render plan ->  deterministic job file -> Kaggle bridge
```

## 2. Seed and reference policy

| Item | Rule |
|---|---|
| Seed range | **3000-3999** (reserved for illustrations; `ILLUSTRATION_STYLE_BIBLE.md` §3) |
| Seed per creature+view | `base + creature_index * 3 + view_index` — derived from the sorted creature list, so it is stable and collision-free inside a batch |
| Reuse | never the same seed for two subjects inside one batch |
| Reference image | used **only** for the locked model (klein), because its official card documents multi-reference image-to-image editing: https://huggingface.co/black-forest-labs/FLUX.2-klein-4B (accessed 2026-10-22) — "Text-to-image and image-to-image multi-reference editing in a single unified model", Diffusers snippet `pipe(image=input_image, prompt=prompt)` |
| Fallback | every model without card evidence uses **seed + prompt anchoring** (the sheet builder simply does not declare `reference_render_id`) |

Note on the seed range: the S7 bake-off used 4000-4022 and the episode
planner 7000+, both **outside** the reserved range. The style files use the
reserved range for new work; the divergence is recorded here rather than
silently changed.

### Prompt anchoring without a reference image

For a model without card evidence the consistency comes from four anchors
that travel with every prompt of that creature:

1. the **anatomy counts** (limbs / eyes / horns),
2. the **canonical silhouette** phrase,
3. the **niche palette + line style + camera vocabulary**,
4. the **fixed seed** (same seed + same prompt + same model = same image).

## 3. Constraints: positive wording (the locked model has no negative prompt)

`klein` takes no negative prompt, so every style constraint is written
**positively** into the prompt. The read-only builder
(`tools/prompting/builder.py`) already applies `no_text`, `not_photoreal`,
`no_people`, `no_logos`; the kit injects the remaining style constraints as
positive phrases. A model that accepts a negative prompt (SDXL family) gets
the **negative** forms in its negative prompt instead — the same style file
drives both, see `style.json` → `constraints[]` (`positive` / `negative`).

## 4. Label rule per niche

| Niche | Label | AI share |
|---|---|---|
| speculative_evolution | "Speculative illustration" | 100% |
| speculative_science | "Speculative illustration" (the niche requires the speculation label) | <= 15% |
| space_iss | "Illustration" | <= 15% |
| art_history | "Illustration" | <= 15% |

The label is burned into the image and written into the manifest
(`tools/illustration/illustration_batch.py`). Editorial overlays (labels,
scale bars, arrows, numbers) are drawn in the editor, never by the model.

## 5. The 4-image smoke job (the only generation in this milestone)

| Item | Value |
|---|---|
| Job | `smoke_sheet_klein_4img_1` (Kaggle kernel `forts845/openmontage-runner`) |
| Model | klein, 1024x1024, 4 steps, guidance 1.0, fp16, CPU offload |
| Renders | `vent grazer` front (T2I), side (reference r0001), three-quarter (reference r0001), `ice burrower` front (T2I) |
| Seeds | 3015, 3016, 3017, 3006 |
| Cost | 4 x 24.691 s + ~134 s load ≈ **4 min of T4 time** |
| Attempt 1 | **FAILED** — `NameError: name 'guidance' is not defined` in the runner's manifest block (the P1 refactor had moved the guidance resolution into the call builder). The text-to-image render itself worked: `r0001.png` (1024x1024, non-black, 397 KB) was written before the manifest step failed. Fixed in `tools/kaggle_bridge/s7_bakeoff_run.py`; covered by the new static check `tests/test_runner_static.py` |
| Attempt 2 | submitted 2026-10-22 (`smoke_sheet_klein_4img_2`); kernel status **QUEUED** at the time of writing — the fetch + verify + QC step is pending the GPU queue |
| Fetch | `python scripts/creature_sheet.py fetch --job-json projects/sheets/work/smoke_sheet_klein_4img_2/job.json` (fail-closed verification + label + image QC) |

The job exercises both paths of the kit (text-to-image and reference image)
and the P1 runner change (the model contract now comes from the config).

## 6. Usage

```bash
# plan (deterministic job file; nothing is generated)
python scripts/creature_sheet.py plan --niche speculative_evolution \
    --creature "vent grazer"

# push it through the bridge ONCE (no polling loop)
python scripts/creature_sheet.py submit --job-json <job.json>

# one status call between phases
python scripts/creature_sheet.py status

# download + verify (fail-closed) + label + image QC
python scripts/creature_sheet.py fetch --job-json <job.json>
```

## 7. Known limits (documented, not hidden)

- The read-only builder emits the counts line for **every** subject, so a
  habitat plate carries "0 limbs, 0 eyes, 0 horns". Harmless for diagrams,
  unchanged because the builder is read only.
- The builder repeats the anatomy phrase in variant C, so the canonical
  silhouette is trimmed to its first clause (max 110 characters) to stay
  inside the builder's 1200-character limit. The full silhouette stays in the
  YAML spec.
- The reference-image path is implemented for the pipeline call
  (`build_generation_call(..., reference_path=...)`), but the **quality** of an
  I2I render with guidance 1.0 (the locked config value) has not been judged
  by the owner yet. Changing the guidance is a **config** edit (no code
  change) — it must not be changed silently (RUN_RULES §5).
- Nothing here trains a LoRA: see `docs/openmontage/image_gen/LORA_FEASIBILITY.md`
  (NOT feasible on a Kaggle T4 as documented; the rented-GPU path is paid).
