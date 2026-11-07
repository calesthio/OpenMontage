# Owner Actions — OpenMontage MASTER RUN

**Status:** F5 complete. Numbered, minimal steps for the owner.
**None of these are blocking for the demo slice (which is NOT_PUBLISHABLE), but all must be resolved before any publish.**

## 1. Voice license decision (REQUIRED before publish)

The slice uses Kokoro-82M (CPU local synthesis, Kaggle GPU bake-off BLOCKED).

- [ ] Review `docs/openmontage/VOICE_DECISION.md` and `docs/openmontage/VOICE_BAKEOFF_LICENSES.md`
- [ ] Decide: accept Kokoro-82M (weights + code Apache-2.0, clear per VOICE_DECISION.md; UNKNOWN only the provenance of part of the training data — synthetic data — a residual risk for the owner/guardian) or select a different voice
- [ ] If accepting Kokoro: record the decision, note the CC BY attribution obligations (Koniwa `tnc`, SIWIS), and note the synthetic-data provenance gap
- [ ] Piper `en_US-lessac-medium` remains BLOCKED (license UNKNOWN) — do not use for publish

## 2. Clip rights review (REQUIRED before publish)

All 4 CID clips in the slice are `source_policy_us_gov` and have been owner-reviewed as `USABLE_FOR_SLICE` (viewed in final F5 video only, not every source frame):

- [ ] Review `docs/openmontage/audit/REVIEW_QUEUE.md` (F5 owner review section + CID section)
- [ ] For each clip, the owner has confirmed: no identifiable persons, no logo/insignia visible, no third-party credit
- [ ] Full video (all source frames) still needs full-clip review before publish — this is the open item
- [ ] All 4 clips currently have NO third-party credit in metadata (passes this check)

## 3. Single-source claims (REQUIRED before publish)

CID-13 (load-bearing: "modified fuel ineffective; FAA requirements cancelled") has only one source (NASA Facts FS-2009-02-003-CID).

- [ ] Find a second source for CID-13, or
- [ ] Remove/S8 from the script (S8 is BLOCKED until CID-13 has a second source), or
- [ ] Accept single-source risk with owner sign-off

Other single-source claims (CID-06, CID-10, CID-12, CID-14, CID-15) should also be reviewed.

## 4. NASA insignia clearance (OWNER DECISION)

CID footage may show NASA insignia on vehicles/facilities. Per NASA Media Usage Guidelines, insignia use is protected by law; incidental appearance does not convey rights.

- [ ] Decide: does the slice's incidental insignia require separate clearance?
- [ ] If yes, contact NASA media usage for approval before publish

## 5. Monetization / publishing readiness (NOT ASSESSED)

- [ ] No monetization eligibility review has been performed
- [ ] No AdSense/YouTube partnership review
- [ ] Content ID / music policy: no music used (MUSIC_POLICY.md: no music unless license evidence exists)
- [ ] Narration uses Kokoro-82M synthetic voice — confirm commercial-use rights before publish

## 6. Kaggle GPU quota (UNVERIFIED — blocks P3)

- [ ] Verify phone number in Kaggle settings (may be required for GPU/internet)
- [ ] Check GPU quota (30 h/week limit, unverified)
- [ ] Retry the Kaggle voice bake-off (P3) — 1 retry attempt remains (max 2)

## Quick reference — slice artifacts (gitignored, in projects/slice_cid_v0/)

| File | Purpose |
|---|---|
| `final_slice.mp4` | 46.0s, 1920x1080, 30fps, h264/aac (NOT_PUBLISHABLE) |
| `qa_report.json` | 12/12 QC checks PASS (freezedetect REVIEW on static title cards) |
| `edit_decisions.json` | EDL with per-cut rationale + static_segments[] |
| `credits.txt` | All clip credits + rights_basis |
| `subtitles.srt` | 7 caption cues from Kokoro narration (S1-S7, S8 omitted) |
| `contact_sheet_f5.jpg` | ~12 frames of final video |
| `rights_records.json` | Per-clip rights_basis (9 clips, all source_policy_us_gov, 4 clips USABLE_FOR_SLICE) |
| `narration_manifest.json` | Narration duration 46.0s + tolerance 1.0s |

## 7. Slice rebuild / portability (G1)

- [ ] Review `scripts/rebuild_slice_assets.sh` and `docs/openmontage/HANDOFF_NEW_ACCOUNT.md`
- [ ] Manifest: `docs/openmontage/assets/CID_SLICE_MANIFEST.json` (committed, URLs + sha256 + rights for 8 assets)
- [ ] To rebuild elsewhere: `git clone <repo-url>`, `git checkout factory/business-documentary-pilot`, install deps (curl, sha256sum, ffmpeg, python3, kokoro, misaki, espeak-ng), `bash scripts/rebuild_slice_assets.sh`
- [ ] Secret: `KAGGLE_API_TOKEN` Codespaces secret (name only, value never committed) — needed only for P3 Kaggle bake-off (BLOCKED)

## 8. Publication blockers (all must clear before publish)

- [ ] Voice license: Kokoro-82M weights/code Apache-2.0 (clear, VOICE_DECISION.md); UNKNOWN only the provenance of part of the training data (synthetic data) — residual risk, owner decision required.
- [ ] Clip full-clip review: F5 owner review done (4 clips USABLE_FOR_SLICE); full video frame-level review pending
- [ ] NASA insignia clearance: decide if incidental insignia requires separate clearance
- [ ] Synthetic-voice disclosure: evaluate against current YouTube rules
- [ ] Guardian/AdSense: no monetization review performed

## 9. Milestone H — autonomous session close (H1-H6) — COMPLETE this session

- [x] H1: CID_CLAIM_LEDGER.md extended to 50 claims (CID-31..50 from NASA Facts FS extracted this session); CID_FULL_SCRIPT_v0.md 6 beats/40 sentences with claim_ids; QC claim_ids PASS (52/52).
- [x] H2: CID_BEAT_COVERAGE.md corrected (8 NIX video clips + 5 NASA stills; photos no longer listed as video); B6 aftermath LIMITED; viability gate proposed; all 6 beats covered.
- [x] H3: hardening tests present and passing; EVALS.md recorded (E1-E4 PASS, E5 NOT_CHECKED); py_compile exit 0; fast suite exit 0.
- [x] H4: 3 thumbnail candidates 1280x720 PNG in gitignored projects/slice_cid_v0/thumbnails/; THUMBNAIL_NOTES.md describes them.
- [x] H5: TOPIC_BACKLOG.md — X-15/XB-70 read-only probe, both LOW viability.
- [x] H6: OWNER_ACTIONS.md, MASTER_RUN_STATE.md, docs/agent-improvement/CHANGELOG.md updated.
- [ ] Stop Codespace when done: `gh codespace stop -c <codespace-name>`

## 10. Milestone I (Kilo), factory scope only — COMPLETE this session

- [x] I1: FAA/CT-87/10 fetched + extracted (92 pages); CID-06/10/15 upgraded to TWO_SOURCES; CID-20 vs CID-25 contradiction recorded; ledger 50 claims.
- [x] I2: qc.py claim_ids_resolve check added (red then green, PASS 52/52); lib/footage_classifier.py + test added (E5 PASS); fast suite exit 0; EVALS.md updated.
- [x] I3: B6 aftermath = graphics-only (Key Numbers + Lessons Learned cards); images.nasa.gov not viable keyless; gap documented in CID_BEAT_COVERAGE.md §5.
- [x] I4: Kokoro-82M license status corrected (Apache-2.0 weights/code clear; UNKNOWN only synthetic-data training provenance residual risk) in OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CID_PACKAGE_DRAFT.md, REVIEW_QUEUE.md; FOOTAGE_QUALITY.md email says "for a YouTube documentary channel (monetization possible)".
- [ ] I5: FULL-VIDEO DRAFT BLOCKED — Kokoro-82M not installed in this environment; no cleared alternative TTS without secrets. Wrote docs/openmontage/slice/artifacts/FULL_DRAFT_STATUS.md (EDL plan, NOT_PUBLISHABLE reasons). Owner to install Kokoro + synthesize narration to unblock.
- [x] I6: MASTER_RUN_STATE.md, OWNER_ACTIONS.md, CHANGELOG.md, EVALS.md updated.

## 11. Milestone K (Kilo), factory scope only — COMPLETE this session

- [x] K1: Niche profile docs/openmontage/NICHE_PROFILE_SPACE_ASTRONOMY_HD.md created (space & astronomy HD public-domain footage); NICHE_DECISION.md updated — CID stays pilot/test video (demand measured, 320x240 below HD bar).
- [x] K2: Footage probe docs/openmontage/footage/K2_FOOTAGE_PROBE_SPACE_ASTRONOMY.md — 10 topics, rights_basis per RIGHTS_MODEL.md, 3 HD-verified clips (Artemis 4K, Hubble 1080p, Perseverance 4K); top 3 topics: Artemis/SLS, Perseverance, Hubble.
- [x] K3: Artemis claim ledger (12 claims, TWO_SOURCES/SINGLE_SOURCE flagged), ARTEMIS_FULL_SCRIPT_v0.md (6 beats, 19 sentences, ~3.5–4 min), ARTEMIS_CLAIM_IDS.json, ARTEMIS_SHORTS_PLAN.md (45s Shorts). QC claim_ids PASS (21/21), claim_ids_resolve PASS (21/21). Generalized qc.py `_parse_claim_ledger` regex from CID-only to any <ID>-<digits>; CID regression PASS (52/52).
- [x] K4: MASTER_RUN_STATE.md, OWNER_ACTIONS.md, CHANGELOG.md updated (this block).

## 12. Milestone Z (Kilo), factory scope only — DONE Z1-Z8, Z9 this close

- [x] Z1 VOICE ENV: isolated python3.12 venv at /tmp/kilo/z1_venv (NOT system 3.14.2), pinned kokoro==0.2.2/misaki==0.7.17/torch==2.6.0+cpu, Kokoro-82M weights into gitignored /tmp/kilo/hf_cache; 10s sample synthesized, finish_audio PASS, qc.py PASS (decode/loudness/silence/freeze). **BLOCKER: venv + weights wiped during session; HF xet CAS + CDN unreachable from this network; HF_HUB_DISABLE_XET=1 regular HTTP stuck at 0 bytes. Owner action: restore /tmp/kilo/z1_venv + /tmp/kilo/hf_cache on a network with HF access.**
- [x] Z2 ARTEMIS DRAFT (3:05): 20-sentence Kokoro narration, stable-ts word alignment, 20-cue subtitles, 8 original graphics cards with claim_ids, EDL with per-cut rationale + static_by_design cards, 4x16s HD inserts from NASA GX010506 (1920x1080, used unscaled). qc.py with ALL inputs: PASS (11 PASS + 1 REVIEW freezedetect on static_by_design cards). NOT_PUBLISHABLE (voice-license residual risk, no frame-level review, NASA insignia clearance pending, synthetic-voice disclosure pending, 4 single-source claims flagged).
- [x] Z3 PIPELINE: scripts/run_episode.py (claim_ledger_check → … → package_draft), per-stage checkpoint + resume + idempotency via output hash + fail-closed + 800MB disk budget + wall-time/disk logging. 6/6 orchestration tests pass with fake stages (resume, mid-chain failure, unknown claim_id, rights unknown, hash mismatch, disk threshold). Real smoke test BLOCKED — same Kokoro weight download issue as Z1.
- [x] Z4 CHAPTER MODE: --chapters splits script into <=6 min chapters, per-chapter checkpoint+resume + disk budget before each chapter + xfade concat + final loudness pass. 5/5 chapter tests pass. docs/openmontage/LONGFORM_SPEC.md written (40-50 min targets, added-value gate, step ladder, no invented thresholds). Dry-run BLOCKED — Kokoro weights.
- [x] Z5 SERIES PLAN: docs/openmontage/SERIES_PLAN.md — 12 ranked space topics, per topic: HD clip count, rights_basis, primary docs reachable, est. usable minutes, max feasible length; T1 demand measured (5/300 breakouts, weak signal); SpaceX Tier C excluded (no PD footage).
- [x] Z6 SCRIPTS: Apollo test flights / Saturn V, ISS, JWST — full scripts (3-5 min each) + claim ledgers + 45s Shorts plans. claim_ids resolve check: ALL OK (every claim_id resolves to ledger, all SINGLE/UNVERIFIED flagged). Apollo: 4 TWO_SOURCE + 9 SINGLE/UNVERIFIED flagged. ISS/JWST: all UNVERIFIED pending NASA primary page verification.
- [x] Z7 PACKAGING: docs/openmontage/slice/artifacts/ARTEMIS_PACKAGING.md — 3 truthful titles, 3 thumbnail text options, 1280x720 PNG thumbnails (gitignored projects/ from own graphics + NASA still, no emblem/people), description with chapters + credits block, synthetic-voice disclosure checklist citing https://support.google.com/youtube/answer/14328491 with owner action items.
- [x] Z8 REVIEW PACK: docs/openmontage/REVIEW_PACK.md — files a fresh session must read, paste-ready read-only reviewer prompt, verification commands with exit codes. All 29 fast tests pass (exit 0), py_compile OK.
- [ ] Z9 CLOSE: this block — update OWNER_ACTIONS.md, MASTER_RUN_STATE.md, CHANGELOG.md, LESSONS.md; print stop-Codespace commands.

## Owner's remaining decisions (consolidated, incl. Z additions)

1. **Kokoro weights restore (REQUIRED for any narration):** /tmp/kilo/z1_venv + /tmp/kilo/hf_cache wiped; HF xet CAS server (cas-server.xethub.hf.co) and CDN (us.aws.cdn.hf.co) unreachable from this network. Restore on a network with HF access, or reinstall kokoro==0.2.2 + misaki==0.7.17 + torch==2.6.0+cpu in python3.12 venv.
2. **Voice license:** Kokoro-82M weights/code Apache-2.0 (clear); UNKNOWN only synthetic-data training provenance — residual risk, owner decision required.
3. **Clip full-clip review + frame review:** identifiable persons, NASA logo/insignia flags UNKNOWN → NEEDS_REVIEW before timeline use (all Artemis candidates).
4. **NASA insignia clearance:** decide if incidental insignia requires separate clearance per NASA Media Usage Guidelines.
5. **Synthetic-voice disclosure:** evaluate against https://support.google.com/youtube/answer/14328491; set "AI use" = Yes in YouTube Studio before any upload.
6. **Guardian/AdSense:** no monetization eligibility review performed.
7. **Thumbnail selection:** choose one of 3 Artemis candidates (projects/slice_artemis_v0/thumbnails/, gitignored).

**Rollback:** `git revert` of the Z commit on branch `factory/business-documentary-pilot`.

## 13. Milestone M (Kilo), factory lane — COMPLETE this session

- [x] M1: G2 image bake-off concluded FAILED (v1 bitsandbytes missing→0 images; v2 one fix+one re-push → CPU gen `TypeError: 'dict' object is not callable` for SDXL-Lightning/Z-Image-Turbo, FLUX.2-klein-4B OOM `Killed`; no further re-push allowed). Cause documented in docs/openmontage/image_gen/G2_STATE.md. ISS v2 complete: 25 scenes + watermark crop, 3 animated claim diagrams, 24-claim ledger (2 NASA primary sources), 37-sentence script claim_ids_resolve PASS, kokoro-82M narration + finish_audio, qc.py ALL inputs PASS, 12-frame contact sheet; NOT_PUBLISHABLE (creative reasons).
- [x] M2: AI illustration module — docs/openmontage/image_gen/ILLUSTRATION_STYLE_BIBLE.md; tools/illustration/illustration_qc.py (blur Laplacian, p-hash dups, aspect/size, text-like flag); tools/illustration/illustration_batch.py (Kaggle bridge batch + manifest verify + Illustration label); 9 tests pass.
- [x] M3: Niche profiles docs/openmontage/niches/{space_iss,art_history,speculative_science}.yaml (allowed_sources, excluded_content, required_primary_doc_types, viability_gate, added_value_gate, 3 episode_templates each); YAML validated.
- [x] M4: Museum adapters tools/museum/adapters.py (Met, Smithsonian, Rijksmuseum, NGA, Wikimedia; http_get injectable), rights.py (CC0/PD only, reject third-party credit, fail-closed), asset_record.py (sha256, credit, URL, rights_basis, usable); 4 tests pass, recorded fixtures, no network/keys.
- [x] M5: Motion variety tools/motion/motion_variety.py (pan/zoom easings in/out, detail crop, parallax, chapter card, subtitle styles) + lint_variation (no two consecutive identical moves); 8 tests pass.
- [x] M6: Packaging tools/packaging/packaging.py (thumbnail from own graphics, no emblems/people; titles/description/credits block; disclosure checklist citing official YouTube support URLs); 3 tests pass.
- [x] M7: Review harness scripts/review_pack.py (bundle reports+qa_report+ledger read-only, run_evals E1-E5); 3 tests pass; all EVALS tasks pass.
- [x] M8: Analytics import tools/analytics/analytics_import.py (parse Studio CSV, retention drop points per chapter -> docs/openmontage/analytics/analytics.json); 3 tests pass.
- [x] M9: Ops scripts/ci_fast_suite.py + scripts/portability_dry_run.py (disk/time logging, 800MB floor); MASTER_RUN_STATE.md + OWNER_ACTIONS.md updated; 3 tests pass.

## Owner's remaining decisions (consolidated)

(unchanged from section 12; no new publish-critical blockers beyond existing voice-license, clip review, NASA insignia, synthetic-voice disclosure, monetization)

**Rollback:** `git revert` of the M commit on branch `factory/business-documentary-pilot`.

**Stop Codespace commands (for owner):**
- `gh codespace stop -c <codespace-name>` — stop the current Codespace
- `gh codespace list` — list all Codespaces
- Or from the VS Code Codespaces panel: stop the active codespace

