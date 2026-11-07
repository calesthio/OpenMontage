# M State — OpenMontage Milestone M (Kilo)

**Started:** 2026-10-20T16:30:00Z  
**Branch:** factory/business-documentary-pilot  
**Constraint:** scope docs/, tools/, scripts/, tests/, .kilo/ only; never touch youtube-niche-finder/, owner's .env.example/AGENTS.md; no secrets; no paid routes; no AI upscaling; curl -L; stop if disk < 800 MB; never sleep/poll Kaggle in a loop.

## M1 — Finish G2 + ISS v2 — DONE (blocked-resolved)
- **G2 image bake-off:** CONCLUDED FAILED. Kernel forts845/g2-image-bakeoff: v1 ERROR (bitsandbytes missing → 0 images), v2 re-pushed (ONE fix + ONE re-push used) → ERROR (CPU generation `TypeError: 'dict' object is not callable` for SDXL-Lightning + Z-Image-Turbo; FLUX.2-klein-4B OOM `Killed`). No images, 0.0 GPU min. Cause documented in docs/openmontage/image_gen/G2_STATE.md. No further re-push allowed.
- **ISS video:** Phase 1 complete — 25 scenes cut (watermark/emblem crop documented), 3 animated claim diagrams (PIL+ffmpeg), 24-claim ledger (2 NASA primary sources, ISS-020=TWO_SOURCES), 37-sentence script with claim_ids (claim_ids_resolve PASS 37/37), kokoro-82M re-narration + finish_audio (I=-15.1 LUFS), video assembled 1280x720/30fps/298s, qc.py ALL inputs PASS, 12-frame contact sheet. NOT_PUBLISHABLE for creative reasons (duration <6–8 min target, graphics not spliced, no title/credits cards). Recorded in M1 todo list above.
- **M_STATE.md:** this file.

## M2 — AI illustration module — DONE
- style bible: docs/openmontage/image_gen/ILLUSTRATION_STYLE_BIBLE.md (palette hex, flat-vector line style, prompt templates, seed policy 3000-3999, model policy zero-cost, acceptance QC, Illustration label)
- tools/illustration/illustration_qc.py: blur (Laplacian variance >=100), p-hash dups (Hamming <=8), aspect/size (1%), text-like artifact flagging; qc_image + qc_batch
- tools/illustration/illustration_batch.py: IllustrationBatchTool run_batch via Kaggle bridge (build/push/fetch/verify job_id+sha256/bytes, Illustration label overlay, batch_manifest.json)
- tests/tools/test_illustration_qc.py (6 pass), tests/tools/test_illustration_batch.py (3 pass) — fake kaggle CLI, no network/paid routes

## M3 — Niche profiles — DONE
- docs/openmontage/niches/space_iss.yaml, art_history.yaml, speculative_science.yaml (allowed_sources, excluded_content, required_primary_doc_types, viability_gate, added_value_gate, 3 episode_templates each); YAML validated

## M4 — Museum adapters — DONE
- tools/museum/rights.py: CC0/PD only, reject third-party credit, fail-closed
- tools/museum/asset_record.py: make_asset_record (sha256, credit, URL, rights_basis, usable) + write_asset_record
- tools/museum/adapters.py: Met, Smithsonian, Rijksmuseum, NGA, Wikimedia (http_get injectable for fixtures)
- tests/tools/test_museum_adapters.py (4 pass) — recorded fixtures, no network/keys

## M5 — Motion variety module — DONE
- tools/motion/motion_variety.py: pan/zoom (easein/easeout/easeinout/linear, in/out), detail crop, parallax, chapter card spec, subtitle styles
- lint_variation: flags two consecutive identical moves (type+easing+direction)
- tests/tools/test_motion_variety.py (8 pass)

## M6 — Packaging module — DONE
- tools/packaging/packaging.py: thumbnail generator (own flat-vector graphics, no emblems/people), build_metadata_block, disclosure_checklist citing official YouTube support URLs
- tests/tools/test_packaging.py (3 pass)

## M7 — Review harness — DONE
- scripts/review_pack.py: bundle_review_pack (read-only reports+qa_report+ledger, no media/secrets), run_evals (all 5 EVALS.md tasks via pytest)
- tests/tools/test_review_pack.py (3 pass; run_evals ran E1-E5, all pass)

## M8 — Analytics import — DONE
- tools/analytics/analytics_import.py: parse_studio_csv (flexible cols), retention_drop_points (threshold), import_analytics -> docs/openmontage/analytics/analytics.json
- tests/tools/test_analytics_import.py (3 pass)

## M9 — Ops — IN_PROGRESS
- M3 niche profiles YAML (space_iss, art_history, speculative_science)
- M4 museum adapters (Met, Smithsonian, Rijksmuseum, NGA, Wikimedia) + tests w/ fixtures
- M5 motion variety module + per-segment variation lint
- M6 packaging module (thumbnail, titles/description/credits, disclosure checklist w/ URLs)
- M7 review harness scripts/review_pack.py + EVALS.md tasks
- M8 analytics import (YouTube Studio CSVs, retention drop points per chapter)
- M9 ops (CI fast suite, clean-venv dry-run, disk/time logging, MASTER_RUN_STATE + OWNER_ACTIONS)

## Next action
M2: write docs/openmontage/image_gen/ILLUSTRATION_STYLE_BIBLE.md and tools/illustration/ batch generator + QC + label.
