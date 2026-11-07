# T5 — Footage Crawl (Top 10 T1 Topics)

**Date:** 2026-10-19  
**Scope:** Keyless HD (>=720p) video clips on images.nasa.gov, archive.org, Wikimedia Commons, with rights fields.  
**Top 10 topics** (ranked by max views from T1, MEASURED): SpaceX Starship, SpaceX Crew Dragon, space telescope, ISS, Artemis, Apollo test flights, Artemis II, SLS, New Horizons, SpaceX Starship test flight.  
**Labels:** ESTIMATE (web evidence of source catalogs, not a full crawl). No RPM/earnings claims.

---

## 1. Footage availability by source (ESTIMATE)

| Source | HD (>=720p)? | Rights field? | Third-party credits / caveats | Best for |
|---|---|---|---|---|
| images.nasa.gov (NASA Image & Video Library) | Yes (720p–4K on many items) | Yes (credit/usage guidance per item) | NASA logos/insignia restricted (14 CFR 1221); some third-party copyrighted material marked | NASA topics: Artemis, Apollo, ISS, SLS, Hubble, JWST |
| archive.org | Yes (720p–4K) | Yes (Public Domain Mark / Usage) on NASA uploads | Third parties (broadcasters) re-upload PD NASA footage and may Content ID-claim it | Apollo, Mercury/Gemini, NASA 4K |
| Wikimedia Commons | Yes (720p–4K) | Yes (licensing/PD-USGov per file) | ESA/NASA joint (SOHO) requires permission for commercial non-educational; Hubble/STScI PD; APOD images may be copyrighted | JWST, Hubble, Earth from ISS |

---

## 2. Per-topic footage assessment (top 10 from T1)

| # | Topic | Public-domain HD footage? | Est. usable HD clips (ESTIMATE) | Est. usable minutes (ESTIMATE) | Third-party credit flags | Notes |
|---|---|---|---|---|---|---|
| 1 | SpaceX Starship | NO (SpaceX = private, not PD) | ~0–5 | ~0–2 min | — | SpaceX footage is copyrighted; not on NASA/archive.org/Wikimedia as PD. Requires license or fair-use commentary. |
| 2 | SpaceX Crew Dragon | NO (private) | ~0–5 | ~0–2 min | — | Same as Starship. NASA broadcasts Crew Dragon launches but SpaceX footage itself isn't PD. |
| 3 | space telescope | YES (NASA/ESA) | 20–60+ | 10–30 min | ESA/STScI credit on some; SOHO commercial restriction | JWST/Hubble animations on NASA SVS (4K/1080p) + Wikimedia Commons (many 1080p/4K PD) |
| 4 | ISS | YES (NASA) | 10–30 | 5–15 min | — | NASA ISS live/HDEV, Earth 4K from ISS (archive.org NASA Ultra High Definition 4K) |
| 5 | Artemis | YES (NASA) | 10–40 | 5–20 min | — | Artemis II official broadcasts (NASA channel), SVS visualizations; logos restricted |
| 6 | Apollo test flights | YES (NASA) | 30–100+ | 20–60 min | — | archive.org Apollo 11 HD (5.5G PD), Mercury/Gemini/Apollo HD Resource Reel |
| 7 | Artemis II | YES (NASA) | 5–20 | 3–10 min | — | Official NASA broadcasts; subset of Artemis |
| 8 | SLS | YES (NASA) | 5–20 | 3–10 min | — | SLS/Artemis launch footage (NASA), SVS |
| 9 | New Horizons | YES (NASA) | 5–15 | 3–8 min | — | NASA Pluto flyby footage/visualizations (JHU APL/NASA) |
| 10 | SpaceX Starship test flight | NO (private) | ~0–5 | ~0–2 min | — | Same as Starship |

**Total estimated usable HD minutes across NASA topics (3–10): roughly 40–150 minutes (ESTIMATE), highly variable by topic.**

---

## 3. Third-party credit / Content ID flags (applies to NASA PD footage)

Even though NASA footage is public domain, third parties routinely re-upload it and Content ID-claim re-uploads:
- **Ars Technica (Aug 2012):** five media organizations claimed one creator's NASA Curiosity-rover video.
- **Trust and Safety Foundation (2021, re 2012):** Scripps broadcasts led to NASA's own public-domain Mars footage being taken down; "NASA reps are used to having to contact YouTube to get their own public domain uploads restored."
- **Ars Technica (Jun 2020):** National Geographic briefly claimed NASA/SpaceX Demo-2 footage.

**Rule:** Public domain ≠ claim-free. Flag third-party credits on every clip; keep public-domain records; be ready to dispute Content ID claims.

---

## 4. Keyless-footage verdict by topic tier

| Tier | Topics | Footage verdict | Why |
|---|---|---|---|
| A (best) | Apollo test flights, ISS, space telescope (JWST/Hubble) | Abundant HD PD | NASA SVS + archive.org + Wikimedia all have 720p–4K PD clips; dozens to 100+ per topic |
| B (adequate) | Artemis, Artemis II, SLS, New Horizons | Adequate HD PD | NASA broadcasts/SVS; fewer clips than Apollo but usable |
| C (poor) | SpaceX Starship, Crew Dragon, Starship test flight | Scarce / not PD | SpaceX is private; footage copyrighted; requires license/fair-use commentary |

---

## 5. Files

- `reports/t5-footage-crawl.csv` — per-topic footage estimate
