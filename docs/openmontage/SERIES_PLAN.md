# OpenMontage Series Plan — 12 Topics, Space Niche (Milestone Z5)

**Sources:** T1 space-series demand (30 topics, MEASURED via YouTube Data API), T5 footage crawl (top 10 T1 topics, ESTIMATE), T12 footage fit (Apollo/ISS/JWST, MEASURED API + ESTIMATE), T15 primary sources (Apollo 9/10/11, MEASURED), T16 viewer intent (Apollo comments, MEASURED), VIABILITY_PROBE_2026-10-16 (CID/LLRV/Shuttle), TOPIC_BACKLOG (X-15/XB-70).  
**Rule:** No demand claims beyond measured data. All footage/rights/primary-doc figures are ESTIMATE unless marked MEASURED.

---

## 1. Demand signal (T1, MEASURED)

**Breakout definition:** long-form >= 8 min, > 50k views, channel < 50k subs, published in last 12 months.  
**Corpus:** 30 topics × top 10 videos = 300 video records, window = last 12 months (2025-10-19 to 2026-10-19).

| Rank | Topic | Breakouts (MEASURED) | Language of breakout(s) |
|---|---|---:|---|
| 1 | Voyager | 2 | Spanish (both) |
| 2 | Cassini | 1 | Russian |
| 3 | James Webb first images | 1 | English (on-topic) |
| 4 | Lucy mission | 1 | English (OFF-TOPIC — dinosaur video) |
| 5–30 | Artemis, SLS, Perseverance, Hubble, JWST, Apollo test flights, ISS, Mars helicopter Ingenuity, SpaceX Starship, Falcon 9, Curiosity rover, New Horizons, OSIRIS-REx, Artemis II, SpaceX Crew Dragon, Parker Solar Probe, Juno, Mars sample return, SpaceX Polaris Dawn, Starliner, DART mission, Europa Clipper, Artemis I, SpaceX Starship test flight, Mars rover, space telescope | 0 | — |

**Total breakouts: 5 / 300 videos. 26 of 30 topics: zero breakouts.**  
**Demand verdict: WEAK.** Only 1 of 5 breakouts is English and on-topic ("6 MINUTES AGO: Vera Rubin's First Images JUST STOPPED THE WORLD!" — 1,844,152 views, 16,400 subs, 21:12, 2026-07-23). High-volume topics (Artemis, SLS, Perseverance, Hubble, JWST, ISS, Starship) are dominated by large channels/official sources; zero small-channel breakouts on those topics.

---

## 2. Feasibility by topic (T5, T12, T15, viability probe, TOPIC_BACKLOG)

**Rights_basis values:** `source_policy_us_gov` (NASA/ESA public domain, usable), `unknown` (no license statement → fail-closed, REJECT unless owner resolves).  
**Clip counts:** ESTIMATE unless marked MEASURED (archive.org API counts are MEASURED but resolution unconfirmed).

| # | Topic | HD clips (ESTIMATE) | Usable minutes (ESTIMATE) | Rights_basis | Primary docs reachable | Max feasible length |
|---|---|---:|---:|---|---|---|
| 1 | Apollo test flights / Saturn V | 30–100+ (MEASURED: 359 archive.org video results) | 20–60 min (T12: 45+ min reachable) | source_policy_us_gov | YES (T15: Apollo 9/10/11 NTRS mission reports, Flight Journal, transcripts) | 45–50 min |
| 2 | ISS | 10–30 (MEASURED: 46,420 archive.org results) | 5–15 min (T12: 45+ min reachable) | source_policy_us_gov | YES (NASA mission pages, NTRS) | 30–45 min |
| 3 | JWST / space telescope | 20–60+ (MEASURED: 1,552 archive.org results) | 10–30 min (T12: 45+ min reachable) | source_policy_us_gov | YES (NASA SVS, NTRS) | 30–45 min |
| 4 | Artemis | 10–40 | 5–20 min | source_policy_us_gov | YES (NASA mission pages, NTRS) | 15–20 min |
| 5 | SLS | 5–20 | 3–10 min | source_policy_us_gov | YES (NASA mission pages, NTRS) | 10–15 min |
| 6 | Artemis II | 5–20 | 3–10 min | source_policy_us_gov | YES (NASA mission pages) | 10–15 min |
| 7 | New Horizons | 5–15 | 3–8 min | source_policy_us_gov | YES (NASA/JHU APL) | 8–12 min |
| 8 | Voyager | — (not in T5 top 10) | — | unknown (not surveyed) | unknown (not surveyed) | unknown |
| 9 | Cassini | — (not in T5 top 10) | — | unknown (not surveyed) | unknown (not surveyed) | unknown |
| 10 | Apollo 11 | — (covered under Apollo test flights) | — | source_policy_us_gov | YES (T15: 6 primary sources) | 15–20 min |
| 11 | Apollo 10 | — (covered under Apollo test flights) | — | source_policy_us_gov | YES (T15: 3 primary sources, thinner) | 10–15 min |
| 12 | Apollo 9 | — (covered under Apollo test flights) | — | source_policy_us_gov | YES (T15: 4 primary sources) | 10–15 min |

**Topics not in T5 footage crawl (no measured footage data):** Voyager, Cassini, Lucy mission, Perseverance, Hubble (as standalone), Mars helicopter Ingenuity, Mars rover, OSIRIS-REx, Parker Solar Probe, Juno, Mars sample return, Europa Clipper, Starliner, DART, SpaceX Starship, SpaceX Crew Dragon, Falcon 9, SpaceX Polaris Dawn, SpaceX Starship test flight.  
**SpaceX topics (T5 Tier C):** no public-domain HD footage (SpaceX = private, copyrighted). Max feasible length: ~0–2 min, requires license or fair-use commentary. **Not recommended for PD-only pipeline.**

---

## 3. Combined ranking — 12-topic series plan

Ranking weights measured demand (T1 breakouts) first, then footage feasibility (T5/T12), then primary-doc reachability (T15). Demand signal is weak across all topics; this ranking reflects available evidence, not predicted performance.

| Rank | Topic | Measured breakouts | Footage tier | Primary docs | Max feasible length | Notes |
|---|---|---:|---|---|---|---|
| 1 | Apollo test flights / Saturn V | 0 | Tier A (best) | YES (T15) | 45–50 min | Best footage + docs; strongest long-form candidate |
| 2 | ISS | 0 | Tier A (best) | YES | 30–45 min | Abundant NASA 4K HD; strong viewer interest in Earth from ISS |
| 3 | JWST / space telescope | 1 (English on-topic) | Tier A (best) | YES | 30–45 min | Only English on-topic breakout in T1; NASA SVS + Wikimedia 4K/1080p |
| 4 | Artemis | 0 | Tier B (adequate) | YES | 15–20 min | NASA broadcasts + SVS; Z2 draft already built on this topic |
| 5 | SLS | 0 | Tier B (adequate) | YES | 10–15 min | Subset of Artemis footage |
| 6 | Artemis II | 0 | Tier B (adequate) | YES | 10–15 min | Crewed mission upcoming; subset of Artemis |
| 7 | New Horizons | 0 | Tier B (adequate) | YES | 8–12 min | Pluto flyby footage/visualizations |
| 8 | Voyager | 2 (Spanish, non-English) | not surveyed | unknown | unknown | Measured demand exists but non-English; footage not surveyed |
| 9 | Cassini | 1 (Russian, non-English) | not surveyed | unknown | unknown | Measured demand exists but non-English; footage not surveyed |
| 10 | Apollo 11 | 0 | Tier A (under Apollo test flights) | YES (T15) | 15–20 min | Most-documented Apollo mission; 6 primary sources |
| 11 | Apollo 10 | 0 | Tier A (under Apollo test flights) | YES (T15, thinner) | 10–15 min | LM descent to ~50k ft; primary docs thinner than Apollo 9/11 |
| 12 | Apollo 9 | 0 | Tier A (under Apollo test flights) | YES (T15) | 10–15 min | CSM/LM rendezvous/docking; Schweickart EVA (single-source flagged) |

**Excluded (not viable for PD-only pipeline):** SpaceX Starship, Crew Dragon, Starship test flight (Tier C — no PD footage, copyrighted), Lucy mission (breakout is off-topic dinosaur video), Perseverance/Hubble/Mars topics (not in T5 footage crawl — no measured footage data).

---

## 4. Added-value gate (per chapter, from Z4 LONGFORM_SPEC.md)

A chapter is releasable only if ALL pass:

- **Narration share:** narration audio present for >= 60% of chapter duration.
- **Original graphics:** at least one original graphics card per 90 s of chapter runtime (title, claim, source, stat, credits card).
- **Archive annotation:** no archive clip > 20 s without on-screen annotation (claim_id, source card, lower-third).
- **Still-only:** no run of still-only frames > 15 s.
- **Claim sourcing:** every load-bearing claim has 2 NASA/ESA primary sources reachable from this environment; single-source claims flagged.
- **Rights:** every clip rights_basis in (`explicit_license`, `source_policy_us_gov`); unknown → BLOCKED.

---

## 5. Step ladder with go/no-go

| Step | Length | Entry criterion | Go/no-go driver |
|---|---|---|---|
| 1 | 3–4 min | Artemis draft (Z2 complete, QC PASS) | Owner decision |
| 2 | 8–10 min | Step 1 published + metrics reviewed | Owner's YouTube Studio metrics |
| 3 | 15–20 min | Step 2 published + metrics reviewed | Owner's YouTube Studio metrics |
| 4 | 40–50 min | Step 3 published + metrics reviewed | Owner's YouTube Studio metrics |

**No invented thresholds.** Go/no-go at each step is driven exclusively by the owner's YouTube Studio metrics (CTR, average view duration, retention curve, subscriber conversion). This plan records the ladder structure only; metric values and decisions belong to the owner.

---

## 6. Data caveats

- T1 demand: 300 video records across 30 topics; only 5 breakouts; weak signal. No RPM/earnings claims.
- T5 footage: ESTIMATE from web evidence of source catalogs, not a full crawl. NASA API clips carry no license/rights field → unverified under fail-closed rules (see VIABILITY_PROBE §3).
- T12 archive.org counts: MEASURED but resolution (>=720p) unconfirmed without per-item inspection.
- T15 primary docs: all NASA public domain (U.S. govt work); logos/insignia restricted (14 CFR 1221); corrected/annotated journal content may carry editor copyright.
- Beat-level clip counts: only available for CID (viability probe), X-15, XB-70 (TOPIC_BACKLOG). Other topics have aggregate clip counts only.
