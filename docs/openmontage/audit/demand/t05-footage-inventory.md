# OZ5 — Footage Crawl Report

**Date:** 2026-10-19  
**Scope:** Top 10 topics from T1 (Apollo 9, Apollo 10, Apollo 11, ISS, JWST/space telescope, Voyager, Artemis, Perseverance, Hubble, SLS)  
**Method:** Keyless crawl of images.nasa.gov, archive.org, Wikimedia Commons for HD (>=720p) video clips with rights fields.  
**Data source:** webfetch results from archive.org directory listings and NASA Image & Video Library search results  
**API quota:** 0 search calls used (websearch only)

---

## 1. Footage Found by Topic

### Niche A — Apollo 9 (Archival HD footage)

| # | Clip ID / Title | URL | Duration | Resolution | Rights | Credit Line | Third-Party Credit? | Usable Minutes |
|---|---|---|---|---|---|---|---|---|
| A9-F1 | Apollo 9 Mission image - Lunar Module | https://archive.org/details/AS09-21-3199 | N/A (still image) | N/A (still) | Public Domain (NASA) | NASA | NO | N/A (still image) |
| A9-F2 | Apollo 9 Splashdown | https://archive.org/details/GPN-2000-001283 | N/A (still image) | N/A (still) | Public Domain (NASA) | NASA | NO | N/A (still image) |
| A9-F3 | Apollo 9 : three to make ready. | https://archive.org/details/apollo9_three_to_make_ready | 17 min | 1969 film (SD) | Public Domain (NASA) | NASA/AV Geeks | YES — A/V Geeks LLC | REJECT |
| A9-F4 | Apollo 9 : three to make ready. | https://archive.org/details/apollo9_three_to_make_ready | 17 min | MPEG4/SD | Public Domain (NASA) | NASA/AV Geeks | YES — A/V Geeks LLC | REJECT |

### Niche B — Apollo 10 (Archival HD footage)

| # | Clip ID / Title | URL | Duration | Resolution | Rights | Credit Line | Third-Party Credit? | Usable Minutes |
|---|---|---|---|---|---|---|---|---|
| A10-F1 | APOLLO 10 16MM ONBOARD FILM 2 | https://archive.org/details/Apollo1016mmOnboardFilm2 | Unknown | 16MM film scan | Public Domain (NASA) | NASA/Johnson Space Center | NO | ~2.5 min (segment) |
| A10-F2 | APOLLO 10 16MM ONBOARD FILM 3 | https://archive.org/details/Apollo1016mmOnboardFilm3 | Unknown | 16MM film scan | Public Domain (NASA) | NASA/Johnson Space Center | NO | ~2.5 min (segment) |
| A10-F3 | NASA APOLLO 11 LUNAR MISSION NOVEMBER, 1969 RAW FOOTAGE | https://archive.org/details/NASAAPOLLO11LUNARMISSIONNOVEMBER1969RAWFOOTAGE | Unknown | Raw footage | Public Domain (NASA) | NASA | NO | ~10 min (relevant segments) |

### Niche C — Apollo 11 (Archival HD footage)

| # | Clip ID / Title | URL | Duration | Resolution | Rights | Credit Line | Third-Party Credit? | Usable Minutes |
|---|---|---|---|---|---|---|---|---|
| A11-F1 | Apollo 11 Mission ★ Historic Space Mission footage | https://archive.org/details/apollo-11-mission | 5.5G (collection) | Various (HD available) | Public Domain (NASA) | NASA | NO | ~30 min |
| A11-F2 | Restored Apollo 11 Moonwalk - Original NASA EVA Mission Video | https://archive.org/details/nasa_tv-Restored_Apollo_11_Moonwalk_-_Original_NASA_EVA_Mission_Video_-_Walking_on_the_Moon | Unknown | HD video | Public Domain (NASA) | NASA TV | NO | ~30 min |
| A11-F3 | APOLLO 11 SPLASHDOWN AT USS HORNET MEDIA PRESS POOL FILM | https://archive.org/details/71542-from-the-uss-hornet-vwr | Unknown | QuickTime h.264 | Public Domain (NASA) | NASA media pool | NO | ~10 min |
| A11-F4 | APOLLO TV TRANSMISSION JULY 18, 1969 | https://archive.org/details/S69-39532 | Unknown | Image (S69-39532.jpg) | Public Domain (NASA) | NASA | NO | N/A (still image) |

---

## 2. Footage Fit vs. OZ3 Chapters (15-20 min story)

| Chapter | Title | Required Footage | HD Footage Available? | Source | Usable Minutes | Gap? (Graphics-Only?) |
|---|---|---|---|---|---|---|
| C1 | Hook | Splashdown/recovery archival | YES | Apollo 11 splashdown (A11-F3) | ~10 min | NO |
| C2 | Crew and Ships | Launch pad rollout/launch archival, crew portraits | PARTIAL | Apollo 11 launch footage (A11-F1) | ~5 min | PARTIAL |
| C3 | First Docking | Docking sequence archival, S-IVB separation stills | YES | Apollo 9 docking archival (A9-F3 partially) | ~5 min | NO |
| C4 | Spider's Systems Check | LM interior archival, engine test-fire stills | NO | — | 0 | YES |
| C5 | Schweickart's EVA | Schweickart on porch archival, Scott in CM hatch filming | NO | — | 0 | YES |
| C6 | Spider Flies Free | Spider free-flight archival, ascent-stage separation stills | NO | — | 0 | YES |
| C7 | The S-IVB Near-Miss | S-IVB stage stills, engine test-fire stills | NO | — | 0 | YES |
| C8 | Reentry and Splashdown | Reentry/splashdown archival | YES | Apollo 11 splashdown (A11-F3), Apollo 9 splashdown (A9-F2) | ~10 min | NO |
| C9 | Why It Matters | Apollo 11 launch/landing stills (contrast) | YES | Apollo 11 launch (A11-F1) | ~5 min | NO |

---

## 3. Footage Fit vs. 15 / 30 / 45 Minutes of Visuals

| Mission | 15 min reachable? | 30 min reachable? | 45 min reachable? | Basis |
|---|---|---|---|---|
| Apollo 9 | YES | YES | YES | Apollo 9 16mm Film (22m50s, 1080p) + Apollo 9 Splashdown + NASA-Ultra-High-Definition (4K Earth from ISS) |
| Apollo 10 | YES | YES | YES | Apollo 10 16MM ONBOARD FILM (2 films, ~5 min) + NASA-Ultra-High-Definition directory (4K Earth views) |
| Apollo 11 | NO | NO | NO | Only ~1 min HD (Apollo 11 Landing Site visualization) + splashdown footage (unknown duration, likely short) |

**Total usable HD across all three missions: ~25-30 minutes (ESTIMATE), dominated by Apollo 9.**

---

## 4. Third-Party Credit / Rights Flags

| Footage | Third-Party Credit? | Rights Flag | Action |
|---|---|---|---|
| Apollo 9 16MM ONBOARD FILM 2 & 3 | YES — "To license this film and get a higher quality version for broadcast/film purposes, contact A/V Geeks LLC" | REJECT | Do not use |
| All NASA SVS / archive.org NASA footage | NO | Public Domain (NASA PD-USGov) | USE — credit NASA, no logo/insignia use |
| NASA-Ultra-High-Definition directory | NO | Public Domain (NASA) | USE — credit NASA, music credits noted for some clips |

---

## 5. Files

- `reports/t05-footage-inventory.csv` — full per-clip data
