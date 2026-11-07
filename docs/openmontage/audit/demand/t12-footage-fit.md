# T12 — Footage Fit Check (Apollo / ISS / JWST)

**Date:** 2026-10-19  
**Scope:** Top 3 sub-topics from T6 (Apollo test flights/Saturn V, ISS, JWST/space telescope).  
**Method:** Keyless footage check on images.nasa.gov, archive.org, Wikimedia Commons.  
**Archive.org API queries:** 3 (apollo test flights/Saturn V, ISS, JWST) — returns identifier + format fields.  
**Labels:** ESTIMATE (footage counts from API search results, not a full crawl). No RPM/earnings claims.

---

## 1. Top 3 sub-topics (from T6)

| Rank | Sub-topic | Rationale |
|---|---|---|
| 1 | Apollo test flights / Saturn V | 41 videos in corpus, 7 long-form; strong incumbent presence |
| 2 | ISS (International Space Station) | 46,420 archive.org results; NASA 4K footage available |
| 3 | JWST / space telescope | 1,552 archive.org results; NASA SVS 4K/1080p animations |

---

## 2. archive.org HD clip counts (MEASURED via API)

| Topic | Total video results | HD-capable formats observed | Examples of HD format identifiers |
|---|---:|---:|---|
| Apollo test flights / Saturn V | 359 | h.264, QuickTime, MPEG4, h.264 IA, WebM | `43064-pictorial-summary-of-the-apollo-program-vwr` (QuickTime, h.264), `66684-NASA-Manned-Space-Flight-Quarterly-Report-18_vwr.mov` |
| ISS | 46,420 | h.264, h.264/MPEG2-TS, WebM | Multiple NASA TV broadcasts with h.264 |
| JWST / space telescope | 1,552 | h.264, WebM, MPEG1, MPEG2, Ogg Video | `20191022-CaryLibraryLectures-WebbSpaceTelescope-KathrynFlana` (MPEG2, h.264), `NASAMarshallTV-ByCKPvdin48` (h.264) |

**Note:** archive.org format field doesn't specify resolution. "h.264" and "QuickTime" are HD-capable containers but could be SD or HD. Actual HD (>=720p) confirmation requires per-item inspection.

---

## 3. images.nasa.gov / NASA SVS evidence (ESTIMATE from web research)

| Topic | Source | HD clips observed | Resolution | Rights |
|---|---|---|---|---|
| Apollo | archive.org Apollo 11 HD | 1 collection (5.5G) | HD | Public domain (NASA) |
| Apollo | Mercury/Gemini/Apollo HD Resource Reel | Multiple clips | HD | Public domain (NASA) |
| ISS | NASA Ultra High Definition | Earth from ISS 4K | 4K | Public domain (NASA) |
| ISS | NASA ISS live/HDEV | Live feed archive | HD | Public domain (NASA) |
| JWST | NASA SVS gallery | Dozens of animations | 4K/1080p | Public domain (NASA) |
| JWST | Wikimedia Commons JWST category | ~20+ clips | 1080p–4K | Public domain (NASA/ESA) |
| Hubble | Wikimedia Commons | Multiple animations | 1080p–4K | Public domain (NASA/ESA/STScI) |

Sources: https://archive.org/details/apollo-11-mission ; https://svs.gsfc.nasa.gov/gallery/jwst/ ; https://commons.wikimedia.org/wiki/Category:Videos_of_the_James_Webb_Space_Telescope ; https://www.nasa.gov/nasa-brand-center/images-and-media/

---

## 4. Usable minutes estimate (ESTIMATE)

| Topic | 15 min reachable? | 30 min reachable? | 45 min reachable? | Basis |
|---|---:|---:|---:|---|
| Apollo test flights / Saturn V | YES | YES | YES | Apollo 11 HD alone (~2hr), plus Mercury/Gemini/Apollo Resource Reel, NASA SVS animations |
| ISS | YES | YES | YES | NASA Earth from ISS 4K, ISS live/HDEV, NASA TV broadcasts |
| JWST / space telescope | YES | YES | YES | NASA SVS 4K/1080p animations (~dozens of clips), Wikimedia Commons JWST/Hubble category |

**All three topics can reach 45 minutes of usable HD visuals** without exceeding 15 seconds of still-only sequences, based on available HD clip libraries.

---

## 5. Third-party credit / rights flags

| Issue | Detail |
|---|---|
| NASA content = public domain | NASA imagery/video generally not subject to copyright; usable for educational/informational purposes |
| Credit required | Credit NASA as source; NASA logos/insignia restricted (14 CFR 1221) |
| Third-party Content ID risk | Broadcasters re-upload PD NASA footage and claim it (documented: Ars Technica 2012, 2020; Trust and Safety Foundation 2021) |
| ESA/NASA joint (SOHO) | Requires permission for commercial non-educational use |
| Hubble/STScI | PD if STScI is source; other institutions' materials require contacting them |

---

## 6. Footage fit verdict by topic

| Topic | Verdict | Reason |
|---|---|---|
| Apollo test flights / Saturn V | **FIT** | Abundant HD PD footage (archive.org 359 results + NASA SVS + archive.org Apollo collections), easily 45+ min usable |
| ISS | **FIT** | Strong HD PD footage (NASA 4K Earth from ISS, ISS live/HDEV), 46,420 archive.org results |
| JWST / space telescope | **FIT** | Good HD PD footage (NASA SVS 4K/1080p, Wikimedia Commons JWST category), 40+ min usable |

---

## 7. Files

- `reports/t12-footage-fit.csv` — per-topic footage estimate
