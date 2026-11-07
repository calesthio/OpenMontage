# T18 — Shorts vs Long-Form Check (Apollo Topics)

**Date:** 2026-10-19  
**Scope:** Apollo topics (Apollo 9/10/11 niches). Compare Shorts vs long-form among videos under 12 months old from small channels (<50k subs).  
**Data:** Existing corpus via `scripts/mcp-host.sh` DB query (MEASURED via YouTube Data API).  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.  
**Noise warning:** Sample sizes are small (23 Shorts, 25 long-form) — treat as ESTIMATE, not conclusive.

---

## 1. Small channels (<50k subs), under 12 months, Apollo niches (MEASURED)

| Format | Count | Median views | Median subs | Median views/subs | Median duration |
|---|---:|---:|---:|---:|---:|
| Shorts (<60s) | 23 | 7,140 | 1,070 | 2.5x | <1 min |
| Long-form (≥8 min) | 25 | 9,276 | 2,430 | 1.4x | 18.8 min |

**Total small-channel Apollo videos under 12 months: 48** (23 Shorts, 25 long-form). Roughly even split.

---

## 2. Top examples (MEASURED)

**Small recent Shorts (top by views):**
| Views | Subs | Date | Channel | Title |
|---:|---:|---|---|---|
| 142,483 | 8,510 | 2026-05-15 | error-log | CASE 5283 - Apollo 1 (1967) Hatch opened inward #shorts |
| 142,263 | 393 | 2025-10-25 | about game | STARSHIP FLIGHT TEST 12 (not Apollo) |
| 60,160 | 16,300 | 2025-11-16 | THINK & PLAY | How Many Astronauts Flew on Apollo Missions? |
| 54,329 | 229 | 2025-10-25 | QURIOSITY PULSE | SATURN V ROCKET ENGINE |
| 40,220 | 14,600 | 2026-08-16 | Deep Sky Engine | Neil Armstrong's Near-Fatal Lunar Landing Test |

**Small recent long-form (top by views):**
| Views | Subs | Duration | Date | Channel | Title |
|---:|---:|---:|---|---|---|
| 168,639 | 1,980 | 15.85 min | 2026-10-02 | Forgotten Orbit | Where Is the Apollo 1 Capsule Now |
| 93,114 | 3,140 | 10.65 min | 2026-04-14 | Dr_Curio | Every Apollo Mission Explained in 10 Minutes |
| 80,921 | 10,000 | 17.85 min | 2025-12-10 | Supernova | Every NASA Space Program Explained |
| 55,756 | 1,030 | 21.0 min | 2026-06-01 | The Space Explained | Every Apollo Moon Mission Explained |
| 52,895 | 26,200 | 14.0 min | 2025-12-05 | apollo11space | Inside the J-2 Engine |

---

## 3. Verdict

**Shorts vs long-form for a small faceless Apollo channel:**

| Consideration | Shorts | Long-form |
|---|---|---|
| Views/subs efficiency | 2.5x (better discovery) | 1.4x |
| Median views | 7,140 | 9,276 (slightly higher) |
| Median subs of channel | 1,070 (smaller channels) | 2,430 (bigger channels) |
| Count in sample | 23 | 25 |
| Best for | Discovery, subscriber growth | Watch time, monetization depth |

**Verdict: Publish BOTH, but sequence Shorts first for discovery.**

Shorts achieve higher views-per-subscriber (2.5x vs 1.4x) from smaller channels — better for discovery from zero. Long-form achieves slightly higher absolute median views but from bigger-subscriber channels — better once you have an audience.

**Recommended sequence:** Shorts first (test angles, build subscriber base), then long-form (deepen engagement, watch time). Do NOT publish long-form first as a small faceless channel — the data shows long-form long-form performers come from channels with ~2.3x more subs.

**Noise warning:** N=23 Shorts, N=25 long-form. Median views/subs ratios (2.5x vs 1.4x) could flip with more data. The difference is directionally suggestive but not statistically conclusive at this sample size.

---

## 4. Files

- `reports/t18-shorts-vs-longform.csv` — per-video Shorts/long-form data
