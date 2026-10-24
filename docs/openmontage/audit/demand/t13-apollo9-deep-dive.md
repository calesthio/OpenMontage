# T13 — Apollo 9 Deep Dive

**Date:** 2026-10-19  
**Scope:** Apollo 9 LM docking/orbital test (Spider and Gumdrop).  
**Data:** Existing corpus (T1/T6/T10) + 10 new `collect_niche` queries via `scripts/mcp-host.sh` (OpenCode MCP wrapper returns "Unexpected token"; `mcp-host.sh` works).  
**Metrics:** channel size, views, duration, date, angle (MEASURED via YouTube Data API).  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.  
**API quota:** 10 search calls used (51/100 total today).

---

## 1. Corpus (MEASURED)

~40 unique Apollo 9 videos collected across niches `t1_apollo_test_flights`, `t6_saturn_v_stage`, `t10_apollo9_*`, `t13_apollo9_*`.

Long-form (≥15 min) Apollo 9 videos (MEASURED, top by views):

| Duration | Views | Subs | Date | Channel | Title | Angle |
|---:|---:|---:|---|---|---|---|
| 33.7 min | 433,496 | 117,000 | 2018 | Homemade Documentaries | Apollo 9 | General overview |
| 20.9 min | 173,341 | 4,470,000 | 2026-09-25 | Professor Dave Explains | Apollo 9: Testing the Lunar Module | LM worthiness/testing |
| 17.3 min | 155,795 | 509,000 | 2011 | AIRBOYD | Apollo 9 - Three To Make Ready | Historical film |
| 158.2 min | 76,279 | 45,800 | 2024 | lunarmodule5 | Apollo 9 - Countdown and Launch (Full Mission 1) | Full mission |
| 81.0 min | 74,105 | 38,300 | 2024 | Retro Space HD | Apollo 9 - Historical Footage, Full Mission | Archival footage |
| 32.0 min | 59,965 | 1,290,000 | 2024 | American Veterans Center | Fighter Pilot... Russell Schweickart | Crew (Schweickart) |
| 18.4 min | 19,280 | 907,000 | 2020 | PeriscopeFilm | 1969 NASA APOLLO 9 LUNAR MISSION OVERVIEW | Overview |
| 125.6 min | 4,511 | 45,800 | 2025-11-23 | lunarmodule5 | Apollo 9 - Docking with LM - End of Day 1 | Rendezvous/docking |
| 17.3 min | 172 | 242,000 | 2013 | A/V Geeks | Apollo 9 : three to make ready | Historical film |
| 89.0 min | 421 | 548 | 2012 | Petaluma Community Media | Beyond: Russell Schweickert - Apollo 9 Astronaut | Crew (Schweickart) |
| 17.3 min | 172 | 242,000 | 2026-06-15 | The Enki Project | Apollo 9 The First Space Walk... | EVA + LM testing (recent) |

---

## 2. Sub-story coverage: which have NO long-form video (≥15 min)?

Per sub-story, assessing whether a dedicated long-form (≥15 min) video exists:

| Sub-story | Long-form ≥15 min? | Evidence | Gap assessment |
|---|---|---|---|
| Rendezvous / docking maneuver | PARTIAL | "Apollo 9 - Docking with LM" (125.6 min, 2025, lunarmodule5); "Space Duet of Spider and Gumdrop" (28.7 min); CSM/LM docking (17.8 min) | Covered but old/low-view; **no recent high-view dedicated docking video** (T10: "Apollo 9 docking maneuver test" = N=3, 0 >100k, 0 <12mo, 0 long-form) |
| EVA test (Schweickart stand-up EVA) | PARTIAL | "Apollo 9 The First Space Walk" (17.3 min, 2026-06-15, Enki Project - recent); EVA shorts (3.8 min) | Has one recent long-form; mostly short clips otherwise |
| LM free flight (Spider independent) | PARTIAL | "Apollo 9: Testing the Lunar Module" (20.9 min, Professor Dave); "Apollo 9 - Lunar Module Maneuvers" (23.2 min) | Covered but general, not flight-specific |
| Crew: McDivitt | NO dedicated | "Apollo 9 - The Crew - McDivitt, Scott" (25.6 min, covers both McDivitt & Scott) | No McDivitt-solo long-form |
| Crew: Scott | NO dedicated | Same 25.6 min covers both | No Scott-solo long-form |
| Crew: Schweickert | YES | "Beyond: Russell Schweickert" (89 min); "Fighter Pilot... Schweickart" (32 min); "Narrated by Schweickart" (16.2 min) | Well covered |
| Test goals / SPS burns / LM worthiness | PARTIAL | "Apollo 9: Testing the Lunar Module" (20.9 min); "1969 NASA APOLLO 9 LUNAR MISSION OVERVIEW" (18.4 min) | Covered generally, not burn-by-burn detail |

**Gap finding:** The clearest Apollo 9 gap is the **rendezvous/docking maneuver** as a dedicated recent long-form topic (T10 Comp score 0.0, N=3, zero >100k views, zero <12 months, zero long-form). Schweickert (EVA/crew) is well covered; McDivitt and Scott individually are not.

---

## 3. Ranked sub-stories as chapter candidates

| Rank | Sub-story | Rationale | Existing long-form |
|---|---|---|---|
| 1 | Rendezvous / docking maneuver (Spider-Gumdrop) | T10 Comp 0.0; zero recent long-form; top priority of flight plan per NASA | None recent/dedicated |
| 2 | LM free flight (Spider independent operations) | Core Apollo 9 uniqueness; only general coverage | Professor Dave 20.9 min (general) |
| 3 | Crew: McDivitt (Commander) | No solo long-form; Schweickert covered, McDivitt not | None solo |
| 4 | Crew: Scott (CMP, transposition/docking) | No solo long-form; performed the critical transposition/docking | None solo |
| 5 | EVA test (Schweickart stand-up EVA) | One recent long-form (Enki 2026-06-15) but mostly shorts | Enki Project 17.3 min (recent) |
| 6 | Test goals / SPS burns / LM worthiness | General overview exists; burn-by-burn detail missing | Professor Dave 20.9 min (general) |

---

## 4. Files

- `reports/t13-apollo9-deep-dive.csv` — per-video Apollo 9 data
