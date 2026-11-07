# Milestone C2 (v2) Report — Rights Evidence Pass + NTRS Retest + Review Queue

**Status:** docs/report only. No application code, no installs, no process/lock changes.
**Time-box:** 35 min. Free keyless access only; BLOCKED if a key/registration is needed.
**ERROR/429/EMPTY treated as separate states, never as zero results.**
**Branch:** `factory/business-documentary-pilot`, HEAD `c2a8858` (working tree clean at start; preserved).
**Subagent note (honest):** `.kilo/agents/{editor, qa-reviewer, evidence-checker, footage-scout}` exist and pass `kilo agent list`, but the `task` tool exposes only `explore`/`general` — no separate `.kilo/agents` subagent process was available. All footage-scout / evidence-checker / qa-reviewer work below was **executed inline** by the orchestrator, applying each agent's rules, and attributed by domain. No subagent run is claimed.

---

## Step 1 — Verdict breakdown by reason code (from C1_RIGHTS_REPORT.md)

### REJECT (29 clips)

| Reason code | Count | Clips | Exact metadata fields missing / present |
|---|---|---|---|
| R1 — `rights_basis=unknown`; no license/rights statement in item metadata | 25 | NIX-EM-0004-02, NIX-EM-0004-01, NIX-LV-1998-00090…00098 (9), NASA-API Shuttle 13 KSC clips, nasa_tv-STS-128_Landing | NIX: `creator`=NASA/Dryden or NASA/Langley present, but `license`, `rights`, `licenseurl` **absent**. NASA-API: `rights`="none stated", no `licenseurl`, no `duration` exposed. nasa_tv: `rights`="none stated". |
| R2 — `rights_basis=unknown`; third-party re-upload/uploader, no license statement | 4 | youtube-Jpc32JQXT_0, 59094…, 59104…, 59084… (3 IA compilations) | youtube: creator="The Federal File", no license statement. 59xxx: no `creator`, no `rights`/`licenseurl`. |

**REJECT total: 29.** Top 3 reason codes by count: R1 (25), R2 (4). (Only 2 distinct REJECT reasons exist.)

### NEEDS_REVIEW (8 clips)

| Reason code | Count | Clips |
|---|---|---|
| N1 — `rights_basis` ∈ {explicit_license, source_policy_us_gov} but flags `identifiable_persons`/`logo_visible` UNKNOWN (unreviewed) | 6 | File:Controlled Impact Demonstration.webm, RSS_294545main_edw_113008_sts126_landing_pod, STS1FirstFlight, nasa-space-shuttle-discovery-sts-26-1988-tape-02, File:Approach and Landing Tests Film Documentary.webm, File:NASA Report - Space Shuttle Enterprise Rollout.webm |
| N2 — `rights_basis` = source_policy_us_gov candidate but flags UNKNOWN | 2 | NDTV001077-X-15_Documentary_Revised, ksc_121704_b52_retires |

**NEEDS_REVIEW total: 8.** All blocked solely on unreviewed flags, not on rights_basis.

### Missing metadata fields (exact, quoted)
- NASA Image/Video Library API: no `license`, `rights`, or `duration` field in search/item responses → every NASA-API clip falls to R1.
- IA NIX items: `license`, `rights`, `licenseurl` fields absent from item metadata (only `creator` present).
- IA 59xxx compilations: `creator`, `rights`, `licenseurl` all absent.
- Commons items: extmetadata fetch returned no usable JSON (fetch limitation); license tag asserted "Public domain" in prior probe but not re-verified this session.

### Usable (fully reviewed, gate-counted): **0**.
**All 5 topics NO-GO** on the footage side of the stage 0 gate (usable 0/10 each).

---

## Step 2 — NTRS retest (3 attempts with backoff + 1 known-PDF retrieval)

| # | Target | Timestamp (UTC) | DNS/HTTP status | Time | Classification |
|---|---|---|---|---|---|
| 1 | `https://ntrs.nasa.gov/api/citations/search?q=X-15` | 02:59:24.142 | HTTP 000 (connection failure, no DNS/HTTP response) | 20.0s | persistent |
| 2 | `https://ntrs.nasa.gov/api/citations/search?q=X-15` | 02:59:47.271 | HTTP 000 | 20.0s | persistent |
| 3 | `https://ntrs.nasa.gov/api/citations/search?q=X-15` | 03:00:12.296 | HTTP 000 | 20.0s | persistent |
| 4 | `https://ntrs.nasa.gov/api/citations/19860021249/downloads/19860021249.pdf` (known URL from Milestone B probe) | 03:01:09.641 | HTTP 000 | 25.0s | persistent |

**Classification: persistent** — all 4 attempts failed at the network/connection layer (HTTP 000, timeout), not a 429/rate-limit or empty result. Not transient (3 attempts with 3s/5s backoff all failed identically).

**Comparison with Milestone B:** Milestone B's probe (2026-10-16) recorded NTRS keyless JSON search as reachable and returning records (e.g. citations 19860021249, 19850015486 with PDFs). In this session NTRS is network-unreachable (ERROR). Same public API, different outcome — consistent with an environmental/network block, not an API change. Primary-doc side of the stage 0 gate remains **unverifiable, not satisfied**.

No retries beyond the cap of 3 + 1 retrieval.

---

## Step 3 — Rights evidence pass (8 NEEDS_REVIEW clips, cap 12)

Rules from `RIGHTS_MODEL.md` applied **as written, not loosened**. `source_policy_us_gov` requires: NASA-produced per metadata AND no third-party/"courtesy of"/copyright notice in credit/description AND no per-item restriction text.

| # | nasa_id | center | secondary creator / credit / "courtesy" / copyright | description (excerpt) | date | rights_basis | Rule applied | Verdict |
|---|---|---|---|---|---|---|---|---|
| 1 | RSS_294545main_edw_113008_sts126_landing_pod | (IA; NASA collection) | creator=NASA; uploader=bonnie@archive.org; **no** third-party credit in metadata | "Space shuttle Endeavour … touchdown at Edwards Air Force Base" | 11/30/2008 | explicit_license (rights="Public Domain") | source_policy_us_gov conditions met (NASA-produced, no 3rd-party credit, no restriction); rights="Public Domain" → explicit_license. Flags UNKNOWN. | NEEDS_REVIEW |
| 2 | STS1FirstFlight | (IA; opensource_movies) | creator=**Department of Defense**; description="Provided by Fight for Space / Paul Hildebrandt" + fightforspace.com (**third-party credit**); uploader=eventidevisuals@gmail.com | "…Columbia (OV-102)… ignition, liftoff… landing at Edwards Air Force Base… crew (John W. Young… Robert L. Crippen…)" | 1981-04-12 | explicit_license (licenseurl=Public Domain Mark 1.0) | explicit_license (PDM 1.0), but third_party_credit=YES (DoD + Fight for Space — not NASA-produced). Flags UNKNOWN. | NEEDS_REVIEW |
| 3 | nasa-space-shuttle-discovery-sts-26-1988-tape-02 | (IA; cdromsoftware) | creator=NASA; description="via NASA TV / Multnomah Cable Access, CNN & NBC" + "Bernard Shaw … on CNN" (**third-party credits**); uploader=drnormal@gmail.com | "STS-26 Launch and Landing… Vice President George H.W. Bush welcomes the crew home to Edwards" | 1988-09-29 | explicit_license (licenseurl=CC-BY 4.0) | explicit_license (CC-BY 4.0), but third_party_credit=YES (CNN/NASA TV/Multnomah). Flags UNKNOWN. | NEEDS_REVIEW |
| 4 | File:Controlled Impact Demonstration.webm | Commons | uploader=Askeuhd (2022-05-23); **third-party uploader**; extmetadata fetch returned no usable JSON (fetch limitation) | "Controlled Impact Demonstration.webm" | (not recorded) | explicit_license (Public domain tag per prior probe) | explicit_license, but third_party_credit=YES (third-party uploader Askeuhd). Flags UNKNOWN. | NEEDS_REVIEW |
| 5 | File:Approach and Landing Tests Film Documentary.webm | Commons | uploader=Askeuhd (2022-07-25); third-party uploader; extmetadata fetch returned no usable JSON | ALT film documentary | (not recorded) | explicit_license (Public domain tag per prior probe) | explicit_license, but third_party_credit=YES. Flags UNKNOWN. | NEEDS_REVIEW |
| 6 | File:NASA Report - Space Shuttle Enterprise Rollout.webm | Commons | uploader=Askeuhd (2022-07-25); third-party uploader; extmetadata fetch returned no usable JSON | Enterprise rollout report | (not recorded) | explicit_license (Public domain tag per prior probe) | explicit_license, but third_party_credit=YES. Flags UNKNOWN. | NEEDS_REVIEW |
| 7 | NDTV001077-X-15_Documentary_Revised | AFRC | **no** third-party credit/restriction in metadata | "X-15 Documentary… Early test footage, engineers in mission control room, in-flight footage from B-52 and chase aircraft, on-board the X-15, accidents, audio, maintenance, and pilots" | 2021-02-01 | source_policy_us_gov candidate | NASA-produced (center=AFRC), no 3rd-party credit, no restriction → source_policy_us_gov conditions met. Flags UNKNOWN. | NEEDS_REVIEW |
| 8 | ksc_121704_b52_retires | KSC | photographer="NASA or National Aeronautics and Space Administration"; **no** third-party credit/restriction | "NASA retired its esteemed B-52B… carried aloft the first X-15 hypersonic rocket planes…" | 2004-12-21 | source_policy_us_gov candidate | NASA-produced (center=KSC, photographer NASA), no 3rd-party credit, no restriction → source_policy_us_gov conditions met. Flags UNKNOWN. | NEEDS_REVIEW |

**Observed looseness check:** No rule was loosened. Notably, S-2 (STS1FirstFlight) and S-3 (STS-26 tape) carry explicit third-party credits (DoD/Fight-for-Space; CNN/NASA TV/Multnomah) — these do NOT satisfy `source_policy_us_gov` condition #2 (no third-party credit), but they do satisfy `explicit_license` (PDM 1.0 / CC-BY 4.0). They remain NEEDS_REVIEW solely because flags are unreviewed.

**Rule-strictness proposal (NOT applied):** For NASA-produced material where `creator`/center is a NASA center and there is no third-party credit/restriction, one could treat the absence of an explicit `license`/`rights` field (per NASA's own guideline that NASA content is "generally not subject to copyright") as satisfying `source_policy_us_gov` rather than `unknown`. This would convert the 13 NASA-API Shuttle clips + 11 NIX clips from REJECT to source_policy_us_gov candidates (still NEEDS_REVIEW pending flag review). **Risks:** NASA guideline exceptions (insignia, identifiable persons, third-party material) still require flag review; treating silence-as-license could over-claim rights for material NASA licensed from third parties. **Who decides:** owner. Not applied in this milestone.

---

## Step 4 — NASA media usage guidelines exception categories (re-read, exact paraphrase)

Re-read official page: https://www.nasa.gov/nasa-brand-center/images-and-media/ (accessed 2026-10-17). Exception categories (short paraphrase, matches the review checklist in REVIEW_QUEUE.md):

1. **NASA Insignia / Logotype / identifiers / imagery** — NOT public domain; use protected by law; available only consistent with Media Usage Guidelines.
2. **Third-party copyrighted material** — NASA occasionally uses copyright-protected material of third parties with permission; those items are marked with the copyright holder's name; NASA's use conveys no rights to others; contact the copyright holder directly.
3. **Identifiable persons** — commercial use may infringe that person's right of privacy/publicity; permission should be obtained from the person. Current NASA employees' names/likenesses/position titles cannot be used on commercial products. Retired astronauts may grant discretion; deceased — estates may retain rights.
4. **Commercial/promotional use** — cannot be filmed on NASA property; must not explicitly or implicitly convey NASA endorsement of commercial goods/services.
5. **NFTs / cryptocurrency** — not permitted.
6. **AI applications** — attribution to NASA not permitted; NASA insignia cannot appear with AI-generated imagery; do not imply NASA review/permission.

Default rule: NASA content is generally not subject to copyright in the US; free for educational/informational use; acknowledge NASA as source; factual use not implying endorsement needs no explicit permission.

---

## Step 6 — PROPOSED gate wording (gate itself not changed)

> **usable** = rule-pass **OR** owner-reviewed (reviewer name, date, notes). A technical slice built from NEEDS_REVIEW clips is tagged **NOT_PUBLISHABLE** until a recorded owner review clears each clip's flags (identifiable_persons, logo_visible, third-party_credit).

This adds an owner-review escape hatch without changing the fail-closed default (unknown => not usable; unreviewed flags => NEEDS_REVIEW). The owner decides whether to grant the review.

---

## Step 7 — Summary, outputs, next step

**Files created:**
- `docs/openmontage/audit/REVIEW_QUEUE.md` (per-clip evidence + human checklist + preview paths)
- `docs/OPENMONTAGE_WORK_LOG.md` (append dated C2 entry — committed with this report)
- Media artifacts under `projects/c2_review/previews/` (gitignored, NOT committed): `x15_nasa_thumb.jpg`, `ksc_b52_thumb.jpg`, `contact_sheet_previews.jpg` (~20K total; IA thumb fetch blocked = 0 bytes)

**Files not created (deferred):** no per-clip 12-frame video contact sheets (most NEEDS_REVIEW clips are stills/thumbnails; milestone is docs/reports-only; deferred to next milestone).

**Tests actually run:** none (docs/report only; ffmpeg contact-sheet generation observed exit 0).

**Budget / provider verification:** strict $0 held. Keyless NASA Image/Video Library API worked (worked for X-15 search, thumb downloads). IA metadata API worked. Commons extmetadata fetch returned no usable JSON (fetch limitation). NTRS = persistent network ERROR (HTTP 000 ×4), not a key/registration issue. No paid API call, no generation, no upload, no YouTube publish. No installs.

**Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.

**Next smallest step:** commit + push C2 docs; then decide whether to (a) apply the owner-reviewed escape hatch to convert source_policy_us_gov candidates to reviewable, (b) pivot topic given all 5 probed topics are NO-GO on footage, or (c) invest in a second rights-verification step for NASA-API clips (the binding constraint: NASA API exposes no license/rights).
