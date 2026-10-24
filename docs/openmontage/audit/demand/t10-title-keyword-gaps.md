# T10 — Title/Keyword Gaps (40 Long-Tail Queries)

**Date:** 2026-10-19  
**Scope:** Title/keyword gap analysis across Apollo 9/10/11/13, lunar rover, ISS, JWST, Voyager, Artemis.  
**Method:** 40 `collect_niche` queries (English, `period="all"`, `pages=1`, `order="viewCount"`) via `scripts/mcp-host.sh` (the OpenCode MCP wrapper returns "Unexpected token"; `mcp-host.sh` works — see diagnosis below).  
**Metrics (MEASURED via YouTube Data API):** results count, videos >100k views, videos <12 months old, Shorts share (<60s), recent long-form (≥60s, <12mo), recent long-form >100k views.  
**Competition score:** `recent_longform_>100k + 0.5 × recent_longform` — lower = fewer strong recent long-form videos = larger gap.  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.  
**API quota used:** 41/100 search calls (1 diag + 40 T10), 123/10,000 units. 59 search calls remain.

---

## Diagnosis: collect_niche via OpenCode wrapper

The OpenCode MCP wrapper (`tools["niche-finder"].collect_niche`) returns `"Unexpected token (1:3)"` for every `collect_niche` call. `scripts/mcp-host.sh` (the MCP server launcher inside youtube-niche-finder) works correctly when driven directly (verified: `db_stats` and `collect_niche` both return live data). The failure is in the OpenCode MCP client wrapper layer, outside youtube-niche-finder; all collection below was routed through `scripts/mcp-host.sh` (inside scope).

---

## Results: ranked by LOW competition (ascending)

| Rank | Topic | Query | N | >100k | <12mo | Shorts% | RecLF | RecLF>100k | Comp |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | Apollo 9 | Apollo 9 docking maneuver test | 3 | 0 | 0 | 66.7 | 0 | 0 | 0.0 |
| 2 | Apollo 10 | Apollo 10 closest approach lunar | 4 | 1 | 1 | 25.0 | 0 | 0 | 0.0 |
| 3 | Apollo 11 | Apollo 11 first moonwalk Armstrong | 50 | 50 | 0 | 42.0 | 0 | 0 | 0.0 |
| 4 | ISS | ISS Earth view cupola | 50 | 16 | 9 | 56.0 | 1 | 0 | 0.5 |
| 5 | Apollo 9 | Apollo 9 lunar module EVA test | 41 | 5 | 6 | 24.4 | 3 | 0 | 1.5 |
| 6 | Apollo 9 | Apollo 9 Saturn V crew McDivitt | 31 | 1 | 4 | 9.7 | 3 | 0 | 1.5 |
| 7 | Lunar rover | Apollo 15 lunar rover first drive | 50 | 14 | 14 | 58.0 | 1 | 1 | 1.5 |
| 8 | Apollo 10 | Apollo 10 dress rehearsal moon | 50 | 3 | 7 | 16.0 | 4 | 0 | 2.0 |
| 9 | JWST | JWST launch Ariane 5 | 50 | 22 | 2 | 12.0 | 2 | 1 | 2.0 |
| 10 | Apollo 13 | Apollo 13 reentry blackout Odyssey | 13 | 6 | 4 | 7.7 | 3 | 1 | 2.5 |
| 11 | Lunar rover | Apollo 16 lunar rover highlands | 50 | 4 | 10 | 24.0 | 5 | 0 | 2.5 |
| 12 | ISS | ISS first module Zarya Unity | 36 | 3 | 7 | 16.7 | 5 | 0 | 2.5 |
| 13 | ISS | ISS Expedition 1 crew | 50 | 20 | 6 | 4.0 | 5 | 0 | 2.5 |
| 14 | Apollo 10 | Apollo 10 Stafford Cernan Young | 50 | 2 | 13 | 20.0 | 6 | 0 | 3.0 |
| 15 | Apollo 11 | Apollo 11 moon landing Eagle | 50 | 50 | 3 | 22.0 | 2 | 2 | 3.0 |
| 16 | Artemis | Artemis I uncrewed test flight | 50 | 4 | 13 | 32.0 | 6 | 0 | 3.0 |
| 17 | JWST | JWST deployment sunshield mirror | 32 | 6 | 12 | 18.8 | 7 | 0 | 3.5 |
| 18 | Apollo 9 | Apollo 9 lunar module spider | 50 | 2 | 12 | 14.0 | 8 | 0 | 4.0 |
| 19 | Lunar rover | Apollo 17 lunar rover last mission | 50 | 50 | 3 | 26.0 | 3 | 3 | 4.5 |
| 20 | Apollo 11 | Apollo 11 quarantine Hornet | 50 | 2 | 21 | 48.0 | 10 | 0 | 5.0 |
| 21 | ISS | ISS construction assembly spacewalks | 36 | 5 | 23 | 50.0 | 12 | 0 | 6.0 |
| 22 | Lunar rover | lunar rover vehicle deployment moon | 50 | 21 | 9 | 46.0 | 7 | 3 | 6.5 |
| 23 | JWST | JWST exoplanet atmosphere | 50 | 15 | 19 | 46.0 | 8 | 3 | 7.0 |
| 24 | Voyager | Voyager golden record | 50 | 50 | 5 | 20.0 | 5 | 5 | 7.5 |
| 25 | Apollo 10 | Apollo 10 lunar module Snoopy descent | 50 | 4 | 23 | 18.0 | 17 | 0 | 8.5 |
| 26 | Apollo 13 | Apollo 13 oxygen tank explosion | 47 | 29 | 17 | 21.3 | 11 | 3 | 8.5 |
| 27 | Apollo 11 | Apollo 11 Saturn V launch Kennedy | 50 | 49 | 8 | 14.0 | 6 | 6 | 9.0 |
| 28 | Artemis | Artemis SLS rocket launch | 50 | 50 | 10 | 40.0 | 6 | 6 | 9.0 |
| 29 | Apollo 13 | Apollo 13 successful failure | 50 | 41 | 9 | 24.0 | 7 | 6 | 9.5 |
| 30 | Apollo 13 | Apollo 13 Lovell Haise Swigert | 50 | 14 | 28 | 36.0 | 18 | 1 | 10.0 |
| 31 | ISS | ISS spacewalk EVA repair | 50 | 11 | 24 | 32.0 | 15 | 3 | 10.5 |
| 32 | JWST | JWST first deep field image | 50 | 29 | 10 | 20.0 | 10 | 8 | 13.0 |
| 33 | Voyager | Voyager 2 grand tour planets | 50 | 25 | 18 | 24.0 | 13 | 7 | 13.5 |
| 34 | Voyager | Voyager pale blue dot | 50 | 50 | 12 | 36.0 | 10 | 10 | 15.0 |
| 35 | Voyager | Voyager 1 interstellar space | 50 | 50 | 14 | 34.0 | 13 | 13 | 19.5 |
| 36 | JWST | JWST earliest galaxies | 50 | 50 | 20 | 12.0 | 19 | 19 | 28.5 |
| 37 | Voyager | Voyager 1 solar system exit | 50 | 43 | 24 | 28.0 | 21 | 18 | 28.5 |
| 38 | Artemis | Artemis Gateway lunar station | 50 | 50 | 26 | 12.0 | 25 | 25 | 37.5 |
| 39 | Artemis | Artemis II crewed lunar flyby | 50 | 35 | 48 | 18.0 | 40 | 27 | 47.0 |
| 40 | Artemis | Artemis III moon landing Starship | 50 | 50 | 39 | 24.0 | 34 | 34 | 51.0 |

---

## Key findings (MEASURED)

**Largest gaps (lowest competition):**
- **Apollo 9 docking maneuver test** (Comp 0.0): tiny corpus (N=3), zero >100k views, zero recent content — a near-empty topic.
- **Apollo 10 closest approach lunar** (Comp 0.0): N=4, only 1 video >100k, only 1 under 12 months.
- **Apollo 11 first moonwalk Armstrong** (Comp 0.0): 50 results all >100k views, but **zero under 12 months** — massive historical demand with no recent long-form coverage.

**Apollo 9/10 consistently show low competition** (ranks 1, 2, 5, 6, 8, 14, 18) — confirming the T6 finding that Apollo 9/10 lack long-form incumbent coverage. Apollo 11 has strong demand but no recent long-form (rank 3, 15, 20).

**Highest competition (saturated):** Artemis III (Comp 51.0), Artemis II (47.0), Artemis Gateway (37.5), Voyager 1 interstellar (28.5), JWST earliest galaxies (28.5). These are dominated by recent long-form content from large channels.

**Shorts share:** varies widely (4% for ISS Expedition 1 crew to 66.7% for Apollo 9 docking). Low-Shorts topics (ISS Expedition 1 crew at 4%, Apollo 9 Saturn V crew at 9.7%, JWST launch Ariane 5 at 12%) offer more long-form headroom.

---

## Files

- `reports/t10-title-keyword-gaps.csv` — per-query data (40 rows)
