# MEGA STATE — factory build toward FACTORY_100_SPEC.md (single resumable run)

**Source of truth:** `FACTORY_100_SPEC.md` (root; never edited) + this file.
**Branch:** `kilo/mega-100` (working branch; never `main`).
**Started:** 2026-10-22.
**Roles:** all work in this run is **inline, not independent** (one agent).

## Resume rule

Resume at the first phase whose status is not in {DONE, OWNER_GATED, BLOCKED}.
After each phase: update this table (status, evidence, commit), commit only the
paths this agent owns, then `git pull --rebase` + non-force push.

## Phase status

| Phase | Status | Evidence | Commit |
|---|---|---|---|
| G0 PREFLIGHT | DONE | ci_fast_suite 18/18 exit 0 (the image-engine + style-kit suites are in the fast gate); 19 episode/EDL tests pass; 2515 tests collected exit 0; audit appendix A in FACTORY_GAP_AUDIT.md | (this commit) |
| G1 QC + CONTRACTS | DONE | qc.py: added_value start/end fix + narration/graphics/still gates, motion_variety, speculative_label, strict rights flags/provenance; qc_report schema test; release_gate (SINGLE_SOURCE blocks publish); run_evals.py 6/6 PASS; fast suite 12/12 exit 0 | (this commit) |
| G2 EPISODE PIPELINE | DONE | run_episode.py now 13 stages: zero_cost_gate (fail-closed on unnamed/unpriced routes), speculative_gate (label + motion lint on EDL), release_gate (publication blockers; draft stays NOT_PUBLISHABLE), episode_dir state override; tests/test_run_episode_gates.py 14 passed, legacy run_episode 14 passed, lavfi integration (real ffmpeg clip -> real QC) 1 passed | (this commit) |
| G3 IMAGE ENGINE | DONE (engine) + CONFIG-LOCKED (P1) | tools/illustration/episode_batch.py (niche-spec adapter, per-model plan, budget cap 120, cache reuse, fail-closed fetch verify, label+QC manifest) + scripts/run_illustrations.py (plan/submit/status/fetch, no polling); 28 tests passed; Kaggle job `ill-se_pilot-klein-1` submitted (84 renders, klein, 1344x768, ladder released_037_x4) -> status RUNNING at submit time; images NOT YET fetched (G8 owner of output); **P1: the model is now locked in `config/image_engine.json` (klein, OWNER_GATED, SDXL-Lightning FAST_FALLBACK) with a model-adapter interface (`tools/illustration/model_registry.py`), a CLI (`scripts/image_engine.py`) and 40 new tests; the Kaggle runner now reads the model's contract from the job (`model_config`)**; **P2: consistency kit** - per-niche `style.json` + finalized `STYLE_BIBLE.md` (4 niches), canonical creature sheets (front/side/3-4) from the read-only OpenCode YAML, anatomy counts always in the prompt, fixed seeds 3000-3999, reference-image workflow only for the card-supported locked model, 30 new tests, 4-image smoke job; **P3: episode-scale pipeline** (image brief from the script with KNOWN/INFERENCE/SPECULATION tags, budget 7 img/min, batches 40-100, one kernel per batch, resume by sha256, retry-only-failed with a re-drawn seed, owner-approved cache, hard fail when images < prompts, seed log + manifest) and ONE live 24-image job: 24/24 generated, **25.287 s/image**, **11/24 = 45.8% QC-usable**, finalize fails closed; **P4: image QC v2** - connected-component text detector (precision 1.00 / recall 1.00 on 16 labelled synthetic fixtures, 1 false positive on 36 real images), palette drift vs the style file, episode near-duplicates, size/aspect, REVIEW queue (objective flags only), owner approved/rejected CSV ledger read by the P3 cache, OCR dependency request SCR-11 | (this commit) |
| G4 VISUAL SOURCES | DONE (re-verified) | stock-source adapters 35 passed + 3 xfail (offline fixtures), museum adapters/rights classifier 4 passed (third-party credit/NC/ND reject), footage classifier + governance tests pass; SOURCE_REGISTRY.md present | (this commit) |
| G5 AUDIO + VOICE | DONE (code) / OWNER_GATED (voice) | kokoro torch KPipeline helper (scripts/kokoro_torch_narrate.py) synthesizes 8.25 s in 18.5 s incl. load; ONNX weights absent so helper auto-selects torch path; Piper refusal test passes; owner listening sign-off OWNER_GATED | (this commit) |
| G6 EDITING + RENDER | PARTIAL (code verified, pilot assets pending) | 84-cut dry run (synthetic 1344x768 stills + real 299.775 s narration): cmd_render OK -> 299.775 s, 1280x720, 30 fps, h264+aac, 13.3 MB; found+fixed two real defects (EDL overshoot made the last cut -125 s; narration stage NameError on unbound `sentences`); own-graphics chapter cards (tools/illustration/cards.py) + section-aware EDL; tests: pilot_edl 9, pilot_edl_cards 7, cards 4, narration 2, episode+EDL+render suites 40 all pass | (this commit) |
| G7 NICHE + TOPIC | BLOCKED | demand measurement needs YouTube Data API quota (already recorded NOT_MEASURED by OpenCode lane); no measured numbers = no recommendation | — |
| G8 PILOT A (speculative evolution) | PENDING | — | — |
| G9 PILOT B (ISS real footage) | PENDING | — | — |
| G10 PACKAGING + SHORTS | DONE (code) | tools/packaging/package_builder.py: metadata from script titles, credits derived from rights records, chapters, disclosure checklist (official YouTube URL), Shorts plan where every beat has claim_id, status always DRAFT_NOT_PUBLISHABLE; 6 tests + wired into cmd_package_draft (20 tests total) | (this commit) |
| G11 REVIEW + VERIFICATION | PENDING | — | — |
| G12 OPERATIONS + PORTABILITY | PENDING | — | — |
| G13 SCORECARD | PENDING | — | — |

## Hard rules carried into every phase

- $0 only; no paid routes. Unknown price = BLOCKED.
- No secrets printed. `KAGGLE_API_TOKEN` reported yes/no only.
- Rights fail closed. AI illustrations always labelled, never as real footage.
- No AI upscaling of footage, no voice cloning, no music without stored licence.
- Manual publishing only; no OAuth to YouTube.
- QC fail-closed: cannot run => BLOCKED/NOT_RUN, never PASS.
- Code test-first (red then green); record exact commands + exit codes.
- Never claim a command/test/commit/push/Kaggle run that was not observed.
- Stop the whole run only if free disk < 800 MB after deleting caches this run created.

## Owner decisions (never waited on)

| Decision | Safest default used | Where to change |
|---|---|---|
| Image model (blind scores) | `klein` advisory (S7 + S8 reports), marked OWNER_GATED; `sdxl-lightning` declared FAST_FALLBACK for drafts | `config/image_engine.json` → `model` |
| Voice acceptance | Kokoro-82M (licence gate PASS), owner sign-off OWNER_GATED | `config/voice.json` |
| Speculative illustration share | 0.15 of runtime, labelled | `docs/openmontage/niches/*/profile.yaml` |
| Emblem policy | reject emblem-as-main-picture; incidental emblem flagged REVIEW | `config/qc_thresholds.json` |
| Disclosure wording | checklist citing official YouTube help page, owner confirms | `docs/openmontage/package/<ep>/DISCLOSURE.md` |
| Publication / Studio metrics | NOT_PUBLISHABLE drafts only | owner action |

## Blockers

(none yet)
