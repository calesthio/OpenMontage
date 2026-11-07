# T14 — Apollo 10 and 11 Gaps

**Date:** 2026-10-19  
**Scope:** Apollo 10 closest lunar approach; Apollo 11 first moonwalk.  
**Data:** Existing corpus (T1/T6/T10/T13) + 5 new `collect_niche` queries via `scripts/mcp-host.sh`.  
**Metrics:** recent (<12 mo) long-form videos, angles, omissions (MEASURED via YouTube Data API).  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.

---

## 1. Apollo 10 — closest lunar approach

**Long-form (≥15 min) videos in corpus: 2 total (MEASURED)**

| Duration | Views | Subs | Date | Channel | Title | Recent (<12mo)? |
|---|---:|---:|---|---|---|---|
| 15.7 min | 12,124 | 32 | 2026-10-11 | Relics of Orbit | Where Are All the Apollo Lunar Modules Now | YES |
| 60.4 min | 3,512 | 45,800 | 2012 | Sound Museum | Apollo 10: Tape 094-AAA | NO |

**Recent (<12 mo) long-form count: 1** — but it's about lunar modules generally, not Apollo 10 specifically. Apollo 10 has essentially **no dedicated recent long-form coverage**.

**Short-form Apollo 10:** "APOLLO 10 NEARLY CRASHES ON MOON" (Michael Lennick, 334,886 views, 3.9 min) — covers the Snoopy staging crisis but is short-form.

**Angles present:** Snoopy staging crisis/near-crash (short-form only), full mission tape (raw audio, 192 min, 252 views).

**What Apollo 10 omissions (gaps):**
- Technical detail: no long-form explanation of the LM staging/descent-to-50k-feet profile
- Test engineering: no explanation of why the descent stage was jettisoned, the staging sequence, or the abort guidance
- Mistakes: the Snoopy tumbling/crisis (gimbal lock, switch error) is only covered in 3.9-min short-form
- Procedure: no step-by-step walkthrough of the descent orbit insertion, low pass, staging, rendezvous

**Verdict:** Apollo 10 is a wide-open gap — 2 long-form videos total, only 1 recent and not Apollo-10-specific. No channel owns "Apollo 10 closest approach" as a long-form topic.

---

## 2. Apollo 11 — first moonwalk

**Recent (<12 mo) long-form (≥15 min) videos: 8 (MEASURED)**

| Duration | Views | Subs | Date | Channel | Title | About first moonwalk? |
|---|---:|---:|---|---|---|---|
| 52.0 min | 555,925 | 137,000 | 2026-08-16 | The American Story | Apollo Hoax Claims Tested: Shadows, Flags, Jodrell Bank | NO (hoax claims) |
| 34.3 min | 545,482 | 6,750,000 | 2026-02-08 | 60 Minutes Australia | Apollo 11 pilot thinks we don't need to go back to the moon | NO (opinion) |
| 21.0 min | 55,756 | 1,030 | 2026-06-01 | The Space Explained | Every Apollo Moon Mission Explained | NO (general) |
| 82.6 min | 45,258 | 26,200 | 2025-10-21 | apollo11space | The Lunar Module: The Spacecraft That Shouldn't Have Worked | NO (LM general) |
| 43.6 min | 35,553 | 26,200 | 2026-05-24 | apollo11space | The Apollo 11 Saturn V: The Rocket That Changed History | NO (Saturn V) |
| 172.7 min | 31,727 | 68,600 | 2026-04-01 | C-SPAN | Flight Director Gene Kranz (Full Interview) | NO (interview) |
| 52.1 min | 19,036 | 52,200 | 2026-07-01 | Free Documentary - Space | We Choose to Go to the Moon: NASA's Most Dangerous Missions | NO (general) |
| 17.9 min | 25 | 303 | 2026-05-18 | Reel2Reel Mixtapes | Apollo Project - tape 05, side B - Apollo 11 | YES (but 25 views) |

**Recent (<12 mo) long-form count specifically about the first moonwalk: effectively 0** (the only one has 25 views).

**Angles present (recent long-form):** hoax-claims debunking, Saturn V, LM general, Gene Kranz interview, general mission overviews, "don't go back" opinion.

**What Apollo 11 omissions (gaps):**
- Technical detail of the first moonwalk: no recent long-form walkthrough of the landing, the 1201/1202 alarms, the manual landing, fuel callouts
- Test engineering: no explanation of the LM descent/ascent engine behavior during landing
- Mistakes: no recent long-form covering the landing anomalies (computer alarms, boulder field, fuel low)
- Procedure: no step-by-step EVA timeline, hatch opening, first steps, contingency planning

**Verdict:** Apollo 11 first moonwalk has massive demand (50 results, all >100k views for "first moonwalk Armstrong" query, T10 Comp 0.0) but **zero recent long-form technical coverage**. Recent long-form covers everything except the moonwalk itself.

---

## 3. Comparison

| Metric | Apollo 10 | Apollo 11 (first moonwalk) |
|---|---|---|
| Long-form ≥15 min total | 2 | 38 (but only 1 recent about moonwalk) |
| Recent (<12mo) long-form | 1 (not Apollo-10-specific) | 0 dedicated to moonwalk |
| Dedicated long-form on topic | NO | NO (recent) |
| Gap severity | EXTREME | HIGH (demand exists, no recent technical long-form) |

---

## 4. Files

- `reports/t14-apollo10-11-gaps.csv` — per-video Apollo 10/11 data
