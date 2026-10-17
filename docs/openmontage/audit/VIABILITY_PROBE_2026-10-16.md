# Topic Viability Probe — 2026-10-16 (Milestone B)

**Method:** throwaway script in `/tmp` only (deleted after use). Repo untouched except this file.
**APIs used (all keyless, no registration):** NASA Image and Video Library
(`images-api.nasa.gov`), Internet Archive advancedsearch + metadata
(`archive.org`), Wikimedia Commons API (`commons.wikimedia.org`),
NASA NTRS citations API (`ntrs.nasa.gov/api/citations/search`, keyless GET — verified working).
**Call states:** `OK` / `EMPTY` / `RATE_LIMITED` / `ERROR` kept separate.
No 429 was encountered in this probe. No API asked for a key → nothing marked BLOCKED on key grounds.
**Gate applied** (`docs/openmontage/NICHE_PROFILE_SPEC.md` §3d):
`min_licensed_video_clips = 10`, `min_primary_docs = 3`, where "licensed" =
provider + original_url + author + license/license_url + QA pass.
A clip with a NASA-center creator but **no license/rights statement in metadata
counts as UNVERIFIED, not licensed** (fail-closed, per master plan §6).
**No topic facts are asserted from memory.** Everything below is API output or a stated gap.

**Method validation (control queries):** `apollo 11` + `media_type=video` → HTTP 200,
5 items; `apollo 11` + `media_type=image` → 200, 5 items; `space shuttle landing` +
`media_type=video` → 200, 5 items. The `media_type` filter works, so `EMPTY`
results below are genuine empty result sets, not method errors.
**Durations** come from IA `metadata/<id>` file entries (`length`, seconds);
NASA API and Wikimedia search responses expose no duration.
**Flags** (identifiable persons / NASA logo) are NOT determinable from any API's
metadata — every row carries "frame check required". Only third-party-credit and
casualty-indication flags can be partially read from metadata.

---

## Topic 1 — Boeing 720 Controlled Impact Demonstration 1984

### 1a. Query × source states (video)

| # | Query | NASA video | NASA image (stills) | IA movies | Wiki |
|---|-------|-----------|---------------------|-----------|------|
| 1 | `Boeing 720 controlled impact demonstration` | EMPTY (0) | OK (7) | OK (3) | OK (batched, see 1c) |
| 2 | `controlled impact demonstration 1984 crash test` | EMPTY (0) | EMPTY (0) | OK (9) | OK (batched) |
| 3 | `Boeing 720 crash test FAA NASA` | EMPTY (0) | EMPTY (0) | EMPTY (0) | OK (batched) |
| 4 | `CID aircraft crash test` | EMPTY (0) | EMPTY (0) | EMPTY (0) | OK (batched) |

IA stills probe (`<q1> AND mediatype:image`): OK (6). No ERROR / RATE_LIMITED on any T1 call.

### 1b. Unique on-topic VIDEO items (deduplicated)

| id | URL | Title | Date | Creator | Rights statement | Duration |
|----|-----|-------|------|---------|------------------|----------|
| NIX-EM-0004-02 | https://archive.org/details/NIX-EM-0004-02 | Controlled Impact Demonstration (CID) tail camera video | 1988-12-02 (item metadata; program year per query context, not asserted) | NASA/Dryden Flight Research Center | **none stated** (licenseurl/rights empty in item metadata) | 36 s |
| NIX-EM-0004-01 | https://archive.org/details/NIX-EM-0004-01 | Controlled Impact Demonstration (CID) flight video montage | 1988-12-02 | NASA/Dryden Flight Research Center | **none stated** | 38 s |
| NIX-LV-1998-00090 … 00098 (9 items, pts 1–9/10 + pt 7/10) | https://archive.org/details/NIX-LV-1998-00090 (…00091…00098) | Crash Impact Demonstration (pt N/10) | 1988-12-02 | NASA/Langley Research Center | **none stated** (all 9) | 11–39 s each |
| youtube-Jpc32JQXT_0 | https://archive.org/details/youtube-Jpc32JQXT_0 | Controlled Impact Demonstration 1984 NASA FAA CID Test Video | 2017-03-17 | The Federal File (third-party re-upload) | **none stated** | 275 s |
| File:Controlled Impact Demonstration.webm | https://commons.wikimedia.org/wiki/File:Controlled_Impact_Demonstration.webm | Controlled Impact Demonstration.webm | (not recorded) | uploader: Askeuhd | Public domain (Commons license tag) | not exposed |

Flags T1: identifiable persons — frame check required (all rows). NASA logo — frame check
required. Third-party credit — YES for `youtube-Jpc32JQXT_0` (The Federal File) and the
Commons webm (third-party uploader); NO indication on the 11 NIX items (NASA-center creators).
Fatalities/crash-with-casualties — no casualty indication in any item metadata; one NTRS
record title indicates remote control (`19850015486`, see 1d). Editorial frame check still required.

### 1c. Stills (for context, not gate-counted)
NASA image q1: 7 hits. IA stills: 6. Wiki: 26 images (+1 video above, 8 other).

### 1d. Primary-document candidates (exact URLs, all verified HTTP 200 via NTRS API)

| # | URL | Title | Type | PDF |
|---|-----|-------|------|-----|
| 1 | https://ntrs.nasa.gov/citations/19860021249 | Impact data from a transport aircraft during a controlled impact demonstration | NASA NTRS | yes — https://ntrs.nasa.gov/api/citations/19860021249/downloads/19860021249.pdf |
| 2 | https://ntrs.nasa.gov/citations/19850015486 | Remote control of an impact demonstration vehicle | NASA NTRS | yes — https://ntrs.nasa.gov/api/citations/19850015486/downloads/19850015486.pdf |
| 3 | https://ntrs.nasa.gov/citations/19860064315 | Structural dynamics research in a full-scale transport aircraft crash test | NASA NTRS | not listed in record |
| 4 (backup) | https://ntrs.nasa.gov/citations/20040191337 | A History of Full-Scale Aircraft and Rotorcraft Crash Testing and Simulation at NASA Langley | NASA NTRS | yes (per record) |

FAA: no exact-URL primary doc retrieved (FAA has no keyless JSON API; no FAA-authored report
URL verified this round). NTSB: CAROL (`data.ntsb.gov/carol-main-public/basic-search`)
returns a JS-app shell only → **BLOCKED** (no keyless data endpoint found; no registration attempted).

### 1e. Verdict: **NO-GO**
- `min_primary_docs = 3`: MET (4 verified NTRS candidates, 2+ with PDFs).
- `min_licensed_video_clips = 10`: NOT MET — 1 of 10 (only the Commons PD webm has an
  explicit license statement). 11 NIX clips are NASA-center-created but carry no
  license/rights statement → unverified under fail-closed rules.
- Exact gaps: (a) verify rights on the 11 NIX items (9 more verified-license clips needed);
  (b) zero exact-URL FAA docs; (c) NTSB/CAROL blocked; (d) NASA API holds no CID video
  under 4 query wordings (stills only).

---

## Topic 2 — Lunar Landing Research Vehicle

### 2a. Query × source states (video)

| # | Query | NASA video | NASA image (stills) | IA movies | Wiki |
|---|-------|-----------|---------------------|-----------|------|
| 1 | `lunar landing research vehicle` | EMPTY (0) | OK (30) | OK (30, mostly off-topic — see 2b) | OK (batched, 0 video) |
| 2 | `LLRV test flight NASA` | EMPTY (0) | OK (8) | OK (2) | OK (batched, 0 video) |
| 3 | `lunar landing training vehicle flight` | EMPTY (0) | OK (14) | OK (10, mostly off-topic) | OK (batched, 0 video) |
| 4 | `flying bedstead lunar lander` | EMPTY (0) | EMPTY (0) | EMPTY (0) | OK (batched, 0 video) |

IA stills probe: OK (30). No ERROR / RATE_LIMITED on any T2 call.

### 2b. Unique on-topic VIDEO items (deduplicated; off-topic Apollo/Gemini/Periscope/Vintage-Space noise excluded by title/creator)

| id | URL | Title | Date | Creator | Rights statement | Duration |
|----|-----|-------|------|---------|------------------|----------|
| NIX-EM-0019-02 | https://archive.org/details/NIX-EM-0019-02 | LLRV in flight and landing on ramp | 1964-01-02 | NASA/Dryden Flight Research Center | **none stated** | 29 s |
| NIX-EM-0019-01 | https://archive.org/details/NIX-EM-0019-01 | LLRV liftoff from ramp | 1964-01-02 | NASA/Dryden Flight Research Center | **none stated** | 25 s |

Off-topic-but-noted: `youtube-f4h2GwnAbTo` (The Vintage Space explainer, CC-BY 3.0 —
third-party MODERN explainer, not program archive); ~30 PeriscopeFilm/Apollo IA hits
(commercial uploads or other programs — excluded, several carry CC BY-NC-ND 4.0 which
bars derivatives).

Flags T2: identifiable persons / NASA logo — frame check required. Third-party credit —
YES on excluded noise items; NO indication on the 2 NIX items. Fatalities — no casualty
indication in item metadata; no NTSB record retrieved (CAROL blocked, see §1d).

### 2c. Stills
NASA image: 30 + 8 + 14 hits across q1–q3. IA stills: 30. Wiki: 33 images, 0 video.

### 2d. Primary-document candidates (exact URLs, all verified HTTP 200 via NTRS API, all with PDF)

| # | URL | Title | Type | PDF |
|---|-----|-------|------|-----|
| 1 | https://ntrs.nasa.gov/citations/19650023948 | Design and operational characteristics of a lunar-landing research vehicle | NASA NTRS | yes (per record) |
| 2 | https://ntrs.nasa.gov/citations/19670013964 | Flight-test evaluation of an on-off rate command attitude control system of a manned lunar … | NASA NTRS | yes — https://ntrs.nasa.gov/api/citations/19670013964/downloads/19670013964.pdf |
| 3 | https://ntrs.nasa.gov/citations/19660030246 | Operational experience with the electronic flight control systems of a lunar-landing resea… | NASA NTRS | yes — https://ntrs.nasa.gov/api/citations/19660030246/downloads/19660030246.pdf |

(First-pass NTRS queries for `lunar landing research vehicle LLRV` returned only 2 weak
anniversary/history records; the three records above came from follow-up queries and a
verified secondary search result. FAA/NTSB: no exact-URL docs retrieved; CAROL blocked.)

### 2e. Verdict: **NO-GO**
- `min_primary_docs = 3`: MET (3 verified NTRS records with PDFs, barely — corpus is thin).
- `min_licensed_video_clips = 10`: NOT MET — 0 of 10. Only 2 on-topic archive videos exist
  across all three keyless sources, and neither carries a license/rights statement.
- Exact gaps: (a) 10 verified-license clips short — the footage simply was not found;
  (b) rights unverified on both NIX items; (c) zero FAA/NTSB exact-URL docs.

---

## Topic 3 — Space Shuttle landing tests at Edwards

### 3a. Query × source states (video)

| # | Query | NASA video | NASA image (stills) | IA movies | Wiki |
|---|-------|-----------|---------------------|-----------|------|
| 1 | `space shuttle landing Edwards Air Force Base` | OK (14) | OK (30) | OK (24) | OK (batched, see 3b) |
| 2 | `shuttle approach and landing test Enterprise` | EMPTY (0) | OK (30) | OK (4) | OK (batched) |
| 3 | `space shuttle Edwards landing rollout` | EMPTY (0) | OK (3) | OK (1) | OK (batched) |
| 4 | `Enterprise shuttle test flight landing` | EMPTY (0) | OK (30) | OK (5) | OK (batched) |

IA stills probe: OK (30). One asset-lookup ERROR (see 3b note). No RATE_LIMITED.

### 3b. Unique on-topic VIDEO items (deduplicated)

NASA API (all have `original_url`-grade file URLs verified via `/asset/` endpoint):

| id | Direct file URL (observed) | Title | Date | Creator | Rights | Duration |
|----|---------------------------|-------|------|---------|--------|----------|
| edw_052409_sts125_land | http://images-assets.nasa.gov/video/edw_052409_sts125_land/edw_052409_sts125_land~orig.mp4 | KSC-09-S-00056 | 2009-05-24 | KSC (center field) | none stated in API | not exposed |
| ksc_092209_sts128_ferry | …/ksc_092209_sts128_ferry~orig.mp4 | KSC-09-S-00107 | 2009-09-22 | KSC | none stated | not exposed |
| edw_052409_sts125_burn | …/edw_052409_sts125_burn~orig.mp4 | KSC-09-S-00055 | 2009-05-24 | KSC | none stated | not exposed |
| edw_113008_sts126_landing | …/edw_113008_sts126_landing~orig.mp4 | KSC-08-S-00074 | 2008-11-30 | KSC | none stated | not exposed |
| edw_113008_sts126_misc | …/edw_113008_sts126_misc~orig.mp4 | KSC-08-S-00075 | 2008-12-01 | KSC | none stated | not exposed |
| ksc_062207_sts117_landing3 | …/ksc_062207_sts117_landing3~orig.mp4 | KSC-07-S-00043 | 2007-06-22 | KSC | none stated | not exposed |
| ksc_062207_sts117_inspect | …/ksc_062207_sts117_inspect~orig.mp4 | KSC-07-S-00044 | 2007-06-22 | KSC | none stated | not exposed |
| ksc_082505_114landing | …/ksc_082505_114landing~orig.mp4 | KSC-05-S-00294 | 2005-08-25 | KSC | none stated | not exposed |
| ksc_101405_sssr | …/ksc_101405_sssr~orig.mp4 | KSC-05-S-00301 | 2005-10-14 | KSC | none stated | not exposed |
| ksc_091205_rtf_sca | …/ksc_091205_rtf_sca~orig.mp4 | KSC-05-S-00297 | 2005-09-13 | KSC | none stated | not exposed |
| ksc_082905_rtf_overview | (asset OK; URL pattern as above) | KSC-05-S-00296 | 2005-09-01 | KSC | none stated | not exposed |
| ksc_112304_shuttle_home | (asset OK) | KSC-04-S-00043… (KSC-04-S-00376) | 2004-11-24 | KSC | none stated | not exposed |
| ksc_081505_goesn_arrives | (asset OK) | KSC-05-S-00295 | 2005-08-26 | KSC | none stated | not exposed (title suggests non-landing content — relevance UNVERIFIED) |

Note: the 14th NASA hit (`Guy Bluford…`, HQ) returned asset-lookup **ERROR**
(non-ASCII nasa_id, endpoint rejected) — recorded as ERROR, not as a result.
Most KSC titles above are operational-era landings; Enterprise/ALT-era specificity is NOT
established by the API metadata (titles are bare catalog numbers).

Internet Archive on-topic selection:

| id | URL | Title | Date | Creator | Rights statement | Duration |
|----|-----|-------|------|---------|------------------|----------|
| 59094SpaceShuttleAmericasSpaceTransportationSystem | https://archive.org/details/59094SpaceShuttleAmericasSpaceTransportationSystem | SPACE SHUTTLE ENTERPRISE LANDING TESTS & SHUTTLE PROGRAM OVERVIEW 59094 | none | none | **none stated** | 459 s |
| 59104SpaceShuttleOrbiterFirstFreeFlight | https://archive.org/details/59104SpaceShuttleOrbiterFirstFreeFlight | SPACE SHUTTLE ENTERPRISE APPROACH AND LANDING TESTS at NASA DRYDEN 59104 | none | none | **none stated** | 667 s |
| 59084ASpaceshipLandedOnEarth | https://archive.org/details/59084ASpaceshipLandedOnEarth | SPACE SHUTTLE ENTERPRISE APPROACH AND LANDING TESTS NASA DRYDEN 1977 59084 | none | none | **none stated** | 396 s |
| RSS_294545main_edw_113008_sts126_landing_pod | https://archive.org/details/RSS_294545main_edw_113008_sts126_landing_pod | Landing of Space Shuttle Endeavour | 2008-11-30 | NASA | Public Domain (item `rights`) | 119 s |
| STS1FirstFlight | https://archive.org/details/STS1FirstFlight | STS-1 Space Shuttle First Manned Orbital Flight | 1981-04-12 | Department of Defense | Public Domain Mark 1.0 (licenseurl) | 784 s |
| nasa-space-shuttle-discovery-sts-26-1988-tape-02 | https://archive.org/details/nasa-space-shuttle-discovery-sts-26-1988-tape-02 | NASA Space Shuttle Discovery STS 26 1988 TAPE 02 | 1988-09-29 | NASA | CC-BY 4.0 (licenseurl) | 4325 s |
| nasa_tv-STS-128_Landing | https://archive.org/details/nasa_tv-STS-128_Landing | STS-128 Landing | 2009-09-11 | NASA TV | **none stated** | 335 s |

Wikimedia (both Public domain, uploader Askeuhd — third-party uploader):

| title | URL | License | Duration |
|-------|-----|---------|----------|
| File:Approach and Landing Tests Film Documentary.webm | https://commons.wikimedia.org/wiki/File:Approach_and_Landing_Tests_Film_Documentary.webm | Public domain | not exposed |
| File:NASA Report - Space Shuttle Enterprise Rollout.webm | https://commons.wikimedia.org/wiki/File:NASA_Report_-_Space_Shuttle_Enterprise_Rollout.webm | Public domain | not exposed |

Flags T3: identifiable persons / NASA logo — frame check required (all rows). Third-party
credit — YES on the three 59xxx IA items (no creator, unknown provenance — treat as
highest-risk rows) and the two Commons webms (third-party uploader). Fatalities — no
casualty indication in any item metadata; frame/editorial check still required.

### 3c. Stills
NASA image: 30 + 30 + 3 + 30 hits. IA stills: 30. Wiki: 34 images (+2 video above).

### 3d. Primary-document candidates (exact URLs, all verified HTTP 200 via NTRS API)

| # | URL | Title | Type | PDF |
|---|-----|-------|------|-----|
| 1 | https://ntrs.nasa.gov/citations/19780011246 | Space Shuttle Orbiter Approach and Landing Test: Final Evaluation Report | NASA NTRS | yes (per record) |
| 2 | https://ntrs.nasa.gov/citations/19780063993 | The Approach and Landing Test program of the Space Shuttle Orbiter 101 | NASA NTRS | not listed in record |
| 3 | https://ntrs.nasa.gov/citations/20070034952 | Free Enterprise: Contributions of the Approach and Landing Test (ALT) Program to the Developmen… | NASA NTRS | yes (per record) |
| 4 | https://ntrs.nasa.gov/citations/19780002256 | Space Shuttle Orbiter Approach and Landing Test Evaluation Report. Captive-Active Flight Test S… | NASA NTRS | yes (per record) |

FAA/NTSB: no exact-URL docs retrieved; CAROL blocked (see §1d).

### 3e. Verdict: **NO-GO** (closest of the three)
- `min_primary_docs = 3`: MET (4 verified NTRS candidates, 3 with PDFs).
- `min_licensed_video_clips = 10`: NOT MET — 5 of 10 (RSS pod PD, STS-1 PDM, Discovery
  tape CC-BY 4.0, 2 Commons PD webms). 13 NASA-API videos are downloadable but carry no
  explicit license string; 3 Enterprise-ALT compilations have no creator and no rights.
- Exact gaps: (a) 5 more verified-license clips; (b) ALT/Enterprise-era specificity
  unverified for the KSC-catalog NASA clips (bare-number titles); (c) provenance unknown
  on the three 59xxx compilations; (d) zero FAA/NTSB exact-URL docs.


---

## Probe 4 — NTRS client (Milestone B probe item)

**Status:** probe item recorded, not executed. No NTRS client exists in `tools/`
(grep for ntrs/NTRS hits only docs) and none was written — this milestone only
records the probe item.

**Test:** `GET https://ntrs.nasa.gov/api/citations/search` without an API key.
Record: HTTP status codes, rate limits (including 429 responses), and the
document fields available per record — id, title, center, date, PDF URL
(`https://ntrs.nasa.gov/api/citations/<id>/downloads/<id>.pdf`).

**Execution status this session:** direct reachability was attempted twice;
both requests timed out at the network layer (no HTTP response received). Per
the probe rule, any failure is recorded as ERROR, not as zero results: the
outcome is ERROR (network unreachable), not EMPTY. No status codes, rate
limits, or field inventory were obtained; the probe remains pending. See
`docs/openmontage/TOOLING_DECISIONS.md` §8 row 1 and §11.

## Cross-topic summary

| Topic | On-topic videos found | …with explicit license/rights | Primary docs (verified) | Verdict |
|-------|----------------------|-------------------------------|-------------------------|---------|
| T1 Boeing 720 CID 1984 | 13 (11 NIX + 1 re-upload + 1 Commons) | 1/10 | 4 NTRS | **NO-GO** |
| T2 LLRV | 2 (NIX) | 0/10 | 3 NTRS (thin) | **NO-GO** |
| T3 Shuttle/Edwards | 22 (13 NASA + 7 IA + 2 Commons) | 5/10 | 4 NTRS | **NO-GO** (closest) |

**Systemic findings (observed, not assumed):**
1. NASA Image/Video Library search exposes no license/rights or duration fields — every
   NASA-API clip needs a second rights-verification step before it can count as "licensed".
2. IA NIX-collection items (NASA-center creators) likewise carry no license/rights in
   item metadata; IA `rights`/`licenseurl` present on only 3 of ~20 on-topic IA rows checked.
3. NTRS keyless JSON search works and returns downloadable PDFs — the primary-doc side of
   the gate is satisfiable; the footage-license side is the binding constraint on all 3 topics.
4. NTSB CAROL is JS-only (fetch returned the app shell) — NTSB records are unreachable by
   keyless machine-readable means in this probe.
5. `required_primary_doc_types` (NASA NTRS, FAA, NTSB): NTRS covered on all topics; FAA and
   NTSB exact-URL docs retrieved on **none**.

**Blockers encountered:** none on footage APIs (no keys needed, no 429). One websearch call
was cancelled by the tool (retry succeeded). NTSB CAROL recorded as BLOCKED (1 attempt,
JS shell — no further attempts per scope; not a key issue, no registration attempted).
