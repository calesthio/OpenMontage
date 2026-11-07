# Review Queue — OpenMontage Milestone C3 (corrected)

**Status:** docs/report only. Corrected per RIGHTS_MODEL.md as written (not loosened).
**Subagent note:** executed inline (orchestrator). The `task` tool exposes only `explore`/`general`; no separate `.kilo/agents` subagent process was available. Footage-scout/evidence-checker/qa-reviewer rules applied inline and attributed by domain.

---

## Step 1 — R1 (25 "no license/rights statement") diagnosis vs written RIGHTS_MODEL.md

**The earlier R1 verdict was STRICTER than the written rule.**

Written rule (RIGHTS_MODEL.md §3), `source_policy_us_gov` granted ONLY when ALL hold:
1. The item is NASA-produced per its own metadata (`creator`/`center` is a NASA center or "NASA").
2. No third-party credit ("courtesy of", "credit: <non-NASA>", copyright notice) in the credit/description fields.
3. No per-item restriction text (no "copyright protected", no license-limiting statement, no "rights reserved").

Notably, source_policy_us_gov does **NOT** require a license statement. The earlier R1 verdict implicitly required one → stricter than written.

### (a) center/creator says NASA, no third-party text/credit, no restriction → source_policy_us_gov under written rule

| nasa_id / asset | center/creator | Third-party credit? | Restriction text? | Written-rule classification | Earlier C1 verdict | Change? |
|---|---|---|---|---|---|---|
| NIX-EM-0004-02 | NASA/Dryden Flight Research Center | No | No | source_policy_us_gov | REJECT (unknown) | Yes → source_policy_us_gov |
| NIX-EM-0004-01 | NASA/Dryden Flight Research Center | No | No | source_policy_us_gov | REJECT (unknown) | Yes → source_policy_us_gov |
| NIX-LV-1998-00090 … 00098 (9 items) | NASA/Langley Research Center | No | No | source_policy_us_gov | REJECT x9 (unknown) | Yes → source_policy_us_gov |
| NASA-API Shuttle 13 KSC clips (e.g. edw_052409_sts125_land) | KSC | No (none observed) | No | source_policy_us_gov | REJECT x13 (unknown) | Yes → source_policy_us_gov |
| nasa_tv-STS-128_Landing | NASA TV | No | No | source_policy_us_gov | REJECT (unknown) | Yes → source_policy_us_gov |

**25 clips reclassified from REJECT to source_policy_us_gov under the written rule.** None become USABLE — all remain NEEDS_REVIEW because `identifiable_persons`/`logo_visible` are UNKNOWN (flags unreviewed = hard NEEDS_REVIEW block per RIGHTS_MODEL.md §4).

### (b) center/creator missing or not NASA
- STS1FirstFlight: creator=Department of Defense (not NASA) → not source_policy_us_gov.
- 59xxx IA compilations: no creator → not source_policy_us_gov.

### (c) other
- nasa-space-shuttle-discovery-sts-26-1988-tape-02: creator=NASA BUT third-party credits present (see step 2).

---

## Step 2 — Classification inconsistency fix: third-party credit → REJECT (not NEEDS_REVIEW)

RIGHTS_MODEL.md §3 condition #2: no third-party credit in credit/description fields. Any clip with third-party credit/courtesy/copyright text → REJECT, regardless of flag-review state.

| nasa_id / asset | Third-party credit observed | New verdict | Reason |
|---|---|---|---|
| STS1FirstFlight | "Provided by Fight for Space / Paul Hildebrandt" + fightforspace.com; creator=DoD | REJECT | third-party credit (condition #2 fails) |
| nasa-space-shuttle-discovery-sts-26-1988-tape-02 | "via NASA TV / Multnomah Cable Access, CNN & NBC"; "Bernard Shaw … on CNN" | REJECT | third-party credit (condition #2 fails) |
| File:Controlled Impact Demonstration.webm | uploader Askeuhd (third-party uploader) | REJECT | third-party credit |
| File:Approach and Landing Tests Film Documentary.webm | uploader Askeuhd (third-party uploader) | REJECT | third-party credit |
| File:NASA Report - Space Shuttle Enterprise Rollout.webm | uploader Askeuhd (third-party uploader) | REJECT | third-party credit |

**Owner rule (step 5): any third-party credit = REJECT regardless of review.**

### Recomputed counts per topic

| topic | REJECT | NEEDS_REVIEW (sole open issue = flags) | rule-pass (usable pending flag review) |
|---|---|---|---|
| Boeing 720 CID 1984 | 13 (11 NIX now source_policy_us_gov→NEEDS_REVIEW? No—NIX have no third-party credit, so they move to NEEDS_REVIEW; youtube + ...) | 11 (NIX, source_policy_us_gov, flags UNKNOWN) | 0 USABLE (all blocked on flags) |
| Shuttle/Edwards ALT | 5 (STS1FirstFlight, STS-26 tape, 3 Commons) | 14 (13 NASA-API KSC + nasa_tv + RSS_294545main, source_policy_us_gov, flags UNKNOWN) | 0 USABLE |
| X-15 research flights | 0 | 2 (NDTV001077, ksc_121704_b52_retires, source_policy_us_gov, flags UNKNOWN) | 0 USABLE |

Wait — recompute carefully. Under written rule + step 2:

**Boeing 720:**
- 11 NIX: source_policy_us_gov, flags UNKNOWN → NEEDS_REVIEW
- youtube-Jpc32JQXT_0: third-party credit (The Federal File) + no license → REJECT
- NEEDS_REVIEW: 11; REJECT: 1; USABLE: 0

**Shuttle/Edwards:**
- 13 NASA-API KSC: source_policy_us_gov, flags UNKNOWN → NEEDS_REVIEW
- nasa_tv-STS-128_Landing: source_policy_us_gov, flags UNKNOWN → NEEDS_REVIEW
- RSS_294545main_edw_113008_sts126_landing_pod: rights="Public Domain" + creator=NASA, no third-party credit → source_policy_us_gov/explicit_license, flags UNKNOWN → NEEDS_REVIEW
- STS1FirstFlight: third-party credit → REJECT
- STS-26 tape: third-party credit → REJECT
- 3 Commons: third-party uploader → REJECT x3
- 59xxx IA compilations (3): no creator, no rights → REJECT x3 (already REJECT)
- NEEDS_REVIEW: 15 (13 KSC + nasa_tv + RSS); REJECT: 9 (STS1FirstFlight, STS-26, 3 Commons, 3 IA 59xxx); USABLE: 0

**X-15:**
- NDTV001077: source_policy_us_gov, flags UNKNOWN → NEEDS_REVIEW
- ksc_121704_b52_retires: source_policy_us_gov, flags UNKNOWN → NEEDS_REVIEW
- NEEDS_REVIEW: 2; REJECT: 0; USABLE: 0

---

## Corrected NEEDS_REVIEW list (sole open issue = identifiable_persons/logo_visible; NO third-party credit)

| # | nasa_id / asset | URL | rights_basis | sole open issue |
|---|---|---|---|---|
| NR-1 | RSS_294545main_edw_113008_sts126_landing_pod | archive.org/details/RSS_294545main_edw_113008_sts126_landing_pod | source_policy_us_gov (rights="Public Domain", creator=NASA) | identifiable_persons/logo_visible |
| NR-2 | NDTV001077-X-15_Documentary_Revised | images-assets.nasa.gov/video/NDTV001077-X-15_Documentary_Revised | source_policy_us_gov (center=AFRC, NASA-produced) | identifiable_persons/logo_visible |
| NR-3 | ksc_121704_b52_retires | images-assets.nasa.gov/video/ksc_121704_b52_retires | source_policy_us_gov (center=KSC, photographer NASA) | identifiable_persons/logo_visible |

All other clips are REJECT (third-party credit or rights_basis=unknown/not NASA-produced).

---

## Contact-sheet path

`projects/c2_review/previews/contact_sheet_previews.jpg` (ffmpeg `tile=2x1` of x15_nasa_thumb.jpg + ksc_b52_thumb.jpg; gitignored, not committed). IA thumb fetch blocked (0 bytes). Per-clip 12-frame video contact sheets deferred (docs/reports-only milestone).

---

## One-line owner checklist per NEEDS_REVIEW clip

| nasa_id | identifiable person? | logo/insignia visible? | third-party credit? |
|---|---|---|---|
| RSS_294545main_edw_113008_sts126_landing_pod | unclear | unclear | no |
| NDTV001077-X-15_Documentary_Revised | unclear | unclear | no |
| ksc_121704_b52_retires | unclear | unclear | no |

Owner rule: any third-party credit = REJECT regardless of review. All three above have no third-party credit in metadata → pending flag review only.

---

## CID section — Boeing 720 Controlled Impact Demonstration (Milestone C4)

**Topic candidate:** CID 1984 (Boeing 720, December 1 1984, Edwards AFB / Rogers Dry Lake).
**Source:** archive.org NIX items (creator = NASA/Dryden or NASA/Langley), metadata only; asset downloads blocked (0 bytes / HTML) in this sandbox — contact sheets not generated.

### Corrected NEEDS_REVIEW list (sole open issue = identifiable_persons/logo_visible; NO third-party credit; rights_basis = source_policy_us_gov under written rule)

| # | nasa_id / asset | URL | rights_basis | duration | sole open issue |
|---|---|---|---|---|---|
| CID-1 | NIX-EM-0004-01 | archive.org/details/NIX-EM-0004-01 | source_policy_us_gov (creator=NASA/Dryden) | 36.56s | identifiable_persons/logo_visible |
| CID-2 | NIX-EM-0004-02 | archive.org/details/NIX-EM-0004-02 | source_policy_us_gov (creator=NASA/Dryden) | 35.22s | identifiable_persons/logo_visible |
| CID-3 | NIX-LV-1998-00090 | archive.org/details/NIX-LV-1998-00090 | source_policy_us_gov (creator=NASA/Langley) | 16.93s | identifiable_persons/logo_visible |
| CID-4 | NIX-LV-1998-00091 | archive.org/details/NIX-LV-1998-00091 | source_policy_us_gov (creator=NASA/Langley) | n/a (metadata only) | identifiable_persons/logo_visible |
| CID-5 | NIX-LV-1998-00092 | archive.org/details/NIX-LV-1998-00092 | source_policy_us_gov (creator=NASA/Langley) | n/a | identifiable_persons/logo_visible |
| CID-6 | NIX-LV-1998-00093 | archive.org/details/NIX-LV-1998-00093 | source_policy_us_gov (creator=NASA/Langley) | n/a | identifiable_persons/logo_visible |
| CID-7 | NIX-LV-1998-00094 | archive.org/details/NIX-LV-1998-00094 | source_policy_us_gov (creator=NASA/Langley) | n/a | identifiable_persons/logo_visible |
| CID-8 | NIX-LV-1998-00095 | archive.org/details/NIX-LV-1998-00095 | source_policy_us_gov (creator=NASA/Langley) | n/a | identifiable_persons/logo_visible |
| CID-9 | NIX-LV-1998-00096 | archive.org/details/NIX-LV-1998-00096 | source_policy_us_gov (creator=NASA/Langley) | 38.69s | identifiable_persons/logo_visible |
| CID-10 | NIX-LV-1998-00097 | archive.org/details/NIX-LV-1998-00097 | source_policy_us_gov (creator=NASA/Langley) | n/a | identifiable_persons/logo_visible |
| CID-11 | NIX-LV-1998-00098 | archive.org/details/NIX-LV-1998-00098 | source_policy_us_gov (creator=NASA/Langley) | n/a | identifiable_persons/logo_visible |

### REJECT (CID)
| nasa_id | reason |
|---|---|
| youtube-Jpc32JQXT_0 | third-party credit ("The Federal File" re-upload) + no license statement → rights_basis=unknown → REJECT |
| File:Controlled Impact Demonstration.webm | third-party uploader (Askeuhd) → third-party credit → REJECT |

### Contact-sheet evidence

- archive.org download works when following HTTP 302 redirects (`curl -L`); earlier C4 "0 bytes / HTML" results were missing `-L` (got the 302 redirect with no body).
- Verified (C5 step 2): HEAD + ranged GET (first 64 KB) of `__ia_thumb.jpg` and `LV-1998-00090_512kb.mp4` both returned HTTP 206 with correct content-types (image/jpeg, video/mp4) and valid file magic.
- Downloaded preview-size derivatives into gitignored `projects/c5_review/` (cap 200 MB not reached; ~2.6 MB total):
  - `projects/c5_review/EM-0004-01_512kb.mp4` (2,236,128 bytes, HTTP 200)
  - `projects/c5_review/LV-1998-00090_512kb.mp4` (405,589 bytes, HTTP 200)
- Built per-clip contact sheets (~12 frames, ffmpeg `select='not(mod(n,90))',scale=320:240,tile=3x4`):
  - `projects/c5_review/EM-0004-01_contact_sheet.jpg` (39,784 bytes)
  - `projects/c5_review/LV-1998-00090_contact_sheet.jpg` (28,423 bytes)
- Contact sheets for the remaining 9 items were not generated within the 10-request cap (metadata file names needed before constructing download URLs).


### One-line owner checklist per CID NEEDS_REVIEW clip

| nasa_id | identifiable person? | logo/insignia visible (NASA, FAA, Boeing, other)? | third-party credit? (yes => REJECT) |
|---|---|---|---|
| NIX-EM-0004-01 | unclear | unclear | no |
| NIX-EM-0004-02 | unclear | unclear | no |
| NIX-LV-1998-00090 | unclear | unclear | no |
| NIX-LV-1998-00091 | unclear | unclear | no |
| NIX-LV-1998-00092 | unclear | unclear | no |
| NIX-LV-1998-00093 | unclear | unclear | no |
| NIX-LV-1998-00094 | unclear | unclear | no |
| NIX-LV-1998-00095 | unclear | unclear | no |
| NIX-LV-1998-00096 | unclear | unclear | no |
| NIX-LV-1998-00097 | unclear | unclear | no |
| NIX-LV-1998-00098 | unclear | unclear | no |

Owner rule: any third-party credit = REJECT regardless of review. All eleven above have no third-party credit in metadata → pending flag review only.

---

## CID owner review list — archive.org item pages (Milestone C5)

**Purpose:** numbered list the owner can open on a phone. URLs constructed as `https://archive.org/details/<identifier>` (no network needed to list). Descriptions/durations from archive.org metadata fetched in C4 + C5.

| # | Item page URL | One-line description | Org | Date | Duration |
|---|---|---|---|---|---|
| 1 | https://archive.org/details/NIX-EM-0004-01 | CID flight video montage | NASA/Dryden | 12/2/1988 | 35.56s (ffprobe of downloaded derivative) |
| 2 | https://archive.org/details/NIX-EM-0004-02 | CID tail camera video | NASA/Dryden | 12/2/1988 | 34.22s (ffprobe of downloaded derivative) |
| 3 | https://archive.org/details/NIX-LV-1998-00090 | Crash Impact Demonstration pt 1/10 | NASA/Langley | 12/2/1988 | 16.83s |
| 4 | https://archive.org/details/NIX-LV-1998-00091 | Crash Impact Demonstration pt 2/10 | NASA/Langley | 12/2/1988 | 36.47s |
| 5 | https://archive.org/details/NIX-LV-1998-00092 | Crash Impact Demonstration pt 3/10 | NASA/Langley | 12/2/1988 | 12.43s |
| 6 | https://archive.org/details/NIX-LV-1998-00093 | Crash Impact Demonstration pt 4/10 | NASA/Langley | 12/2/1988 | 30.17s |
| 7 | https://archive.org/details/NIX-LV-1998-00094 | Crash Impact Demonstration pt 5/10 | NASA/Langley | 12/2/1988 | 21.67s |
| 8 | https://archive.org/details/NIX-LV-1998-00095 | Crash Impact Demonstration pt 6/10 | NASA/Langley | 12/2/1988 | 11.00s |
| 9 | https://archive.org/details/NIX-LV-1998-00096 | Crash Impact Demonstration pt 7/10 | NASA/Langley | 12/2/1988 | 38.60s |
| 10 | https://archive.org/details/NIX-LV-1998-00097 | Crash Impact Demonstration pt 8/10 | NASA/Langley | 12/2/1988 | 29.50s |
| 11 | https://archive.org/details/NIX-LV-1998-00098 | Crash Impact Demonstration pt 9/10 | NASA/Langley | 12/2/1988 | 16.03s |

**Note:** titles use "pt N/10" (implies 10 parts) but only 9 parts (00090-00098) are located under NIX-LV-1998-*. Durations are ffprobe-measured from the downloaded `_512kb.mp4` derivatives (C6). Contact sheets built for all 11 items (`projects/c5_review/`).

---

## Sequential-ID analysis — NIX-LV-1998-00090…00098 (Milestone C5 step 6)

**Metadata observation (from C4 + C5 fetches):**
- All 9 items share creator = NASA/Langley Research Center (NASA-LaRC), date = 12/2/1988, mediatype = movies.
- Titles are sequential parts: "Crash Impact Demonstration. (pt 1/10)" through "(pt 9/10)".
- Descriptions each describe a different camera angle / view of the same CID impact (front long shot, tail camera, cockpit interior, wide shot, fireball, high-speed slow-motion, etc.).
- `pt 1/10` implies a 10th part exists but is not located under NIX-LV-1998-* (only 00090-00098 = 9 parts found).

**Are they segments of one reel with possible overlapping footage?**
- They are segments of the same CID event (December 1 1984, Edwards AFB) but appear to be **separate camera angles**, not sequential slices of a single continuous reel.
- Because multiple cameras recorded the same impact simultaneously, different parts likely **overlap in time** (same impact moment from different angles) rather than being strictly sequential non-overlapping segments.
- The "pt N/10" numbering suggests a produced multi-camera edit, not a single linear reel.

**What viewing is needed to confirm:**
- Frame/pixel review of each part to (a) confirm whether any two parts show the exact same impact moment (overlap) and (b) identify which parts contain unique footage vs. duplicates.
- Compare timestamps/impact-onset across parts to detect temporal overlap.
- Confirm whether a 10th part exists elsewhere (not under NIX-LV-1998-*).

---

## CID per-clip table + owner checklist (Milestone C6)

**Source:** ffprobe of downloaded `_512kb.mp4` derivatives (local, no network); contact sheets in gitignored `projects/c5_review/` (never committed, under 200 MB cap).

| clip | duration | resolution | audio | contact-sheet path | identifiable person? | logo/insignia visible? | third-party credit? |
|---|---|---|---|---|---|---|---|
| NIX-EM-0004-01 | 35.56s | 320x240 | no | projects/c5_review/EM-0004-01_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-EM-0004-02 | 34.22s | 320x240 | no | projects/c5_review/EM-0004-02_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00090 | 16.83s | 320x240 | yes | projects/c5_review/LV-1998-00090_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00091 | 36.47s | 320x240 | yes | projects/c5_review/LV-1998-00091_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00092 | 12.43s | 320x240 | yes | projects/c5_review/LV-1998-00092_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00093 | 30.17s | 320x240 | yes | projects/c5_review/LV-1998-00093_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00094 | 21.67s | 320x240 | yes | projects/c5_review/LV-1998-00094_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00095 | 11.00s | 320x240 | yes | projects/c5_review/LV-1998-00095_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00096 | 38.60s | 320x240 | yes | projects/c5_review/LV-1998-00096_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00097 | 29.50s | 320x240 | yes | projects/c5_review/LV-1998-00097_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |
| NIX-LV-1998-00098 | 16.03s | 320x240 | yes | projects/c5_review/LV-1998-00098_512kb_contact_sheet.jpg | (empty — owner) | (empty — owner) | (empty — owner) |

**Total CID footage:** ~286 s (~4.8 min) across 11 clips; all at 320x240. Two Dryden clips (NIX-EM-*) have no audio track; nine Langley clips have audio.

Owner rule (restated): any third-party credit = REJECT regardless of review. All eleven clips have no third-party credit in metadata → pending flag review (person/logo/insignia) only.

---

## Coverage map — narrative beats (Milestone C6 step 3)

**Method:** metadata title/description + ffprobe only; no pixel judging. Beat assigned from description text.

| beat | clips covering it | clip ids |
|---|---|---|
| preparation | 0 | (none) |
| remote piloting | 1 | NIX-LV-1998-00095 (cockpit interior, pilot during impact) |
| flight | 0 | (none) |
| impact | 11 | all 11 (every title/description references the impact) |
| fire | 5 | NIX-LV-00092 (fireball), 00093 (AMK burn), 00094 (AMK flowing), 00096 (impact montage), 00098 (fireball realtime) |
| aftermath | 0 | (none) |
| other | 1 | NIX-LV-1998-00093 (AMK "fail and then burn" explanation) |
| unclear | 0 | (none) |

**Distinct beats covered:** 4 (remote piloting, impact, fire, other)
**Beats with zero clips:** 3 (preparation, flight, aftermath)

**PROPOSED (not applied) viability-gate wording — narrative-beat coverage:**
> In addition to the raw clip count (>= 10 usable clips), the stage 0 topic viability gate requires coverage of >= 6 distinct narrative beats with >= 1 usable clip per beat. Beats: preparation, remote piloting, flight, impact, fire, aftermath. A topic lacking >= 6 beats is NOT_GATE_READY regardless of clip count.

**Applied to CID:** CID covers only 4 of 7 beats (missing preparation, flight, aftermath) → under this proposed wording CID would be NOT_GATE_READY on narrative coverage despite having 11 usable-pending-review clips. This wording is a proposal only; it is NOT applied to any gate.

---

## Voice decision summary (Milestone C6 step 4)

**Source:** `docs/openmontage/TOOLING_DECISIONS.md` §12.2 (D1 voice-license table) — read-only, no new claims.

| Engine | Code license | Weights/voice license | Commercial use | Evidence |
|---|---|---|---|---|
| Piper engine | GPL-3.0-or-later | n/a (engine) | permitted (copyleft) | piper_tts-1.8.0.dist-info/METADATA (local) |
| Piper voice `en_US-lessac-medium` | n/a | **UNKNOWN** — sidecar has `"dataset": "lessac"`, no license field | UNKNOWN | `~/.local/share/piper/voices/en_US-lessac-medium.onnx.json` (local, read) |
| Kokoro | Apache-2.0 | Apache-2.0 (weights), UNKNOWN (training-data provenance: synthetic data) | clear at weights level, residual risk | https://huggingface.co/hexgrad/Kokoro-82M |

**Decision / blocker:** Piper `en_US-lessac-medium` is the locally-installed TTS engine already used in the P1 pilot (18 segments, 84.975 s measured). Its voice license is **UNKNOWN** — the pilot manifest asserts `CC-BY-4.0 (lessac dataset voice)` but no license text exists in the repo, README, `tools/audio/piper_tts.py`, or the voice sidecar `.onnx.json`. Kokoro is installed locally; weights/code Apache-2.0 clear (VOICE_DECISION.md); UNKNOWN only the provenance of part of the training data (synthetic data) — residual risk, owner decision required. Until the Piper voice license is confirmed (or a licensed alternative selected) and the Kokoro residual risk is accepted, commercial publication is **blocked** — the "voice license known" Go/No-Go gate (plan v3.2) cannot pass. Voice synthesis smoke test was technical only (RTF 0.21, real-time factor ~4.7× faster than real-time on CPU) and is NOT a commercial-use approval.

**Notes:** ffmpeg 6.1.1 (Ubuntu build) license UNKNOWN from repo files. No music used in pilot (music gate-blocked, library empty). Audio finishing prototype verified via ebur128 (-13.8 LUFS / -5.2 dBTP) but used synthetic test-tone bed, not licensed music.

---
## F5 owner review — CID slice clips + stills (Milestone F5)

**reviewer:** owner
**date:** 2026-10-18
**scope:** viewed in final f4 video only, not every source frame
**identifiable_persons:** no
**logo_visible:** no
**third_party_credit:** no

**Result:** 4 slice clips marked USABLE_FOR_SLICE; full video still needs full-clip review before publication.

| # | nasa_id / asset | role in slice | review outcome | flags (owner) | third-party credit? |
|---|---|---|---|---|---|
| 1 | NIX-EM-0004-01 | archive insert (S6-S7 region, approach) | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |
| 2 | NIX-LV-1998-00090 | archive insert (impact) | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |
| 3 | NIX-LV-1998-00092 | archive insert (fireball) | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |
| 4 | NIX-LV-1998-00098 | reserve archive insert | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |

**5 stills (already reviewed C4/C5; re-confirmed F5):**
| # | nasa.gov id | role | review outcome | flags (owner) | third-party credit? |
|---|---|---|---|---|---|
| 1 | ECN-31803 | still (S1) | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |
| 2 | EC84-3167-A | still (S2) | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |
| 3 | ECN-31808 | still (S3) | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |
| 4 | EC84-31809 | still (S4) | USABLE_FOR_SLICE | identifiable_persons=no; logo_visible=no | no |
| 5 | ECN-28307 | still (S5) | USABLE_FOR_SLICE | identifiable_persons=no (crash-test dummies, not real persons); logo_visible=no | no |

**Open item:** full video (all source frames) still needs full-clip review; the F5 review covers only the segments actually used in the final slice. Full review remains a publication precondition.

**Owner rule (restated):** any third-party credit = REJECT regardless of review. None of the 9 reviewed assets have third-party credit in metadata → pending flag review only (all cleared: no identifiable persons, no logo visible).


