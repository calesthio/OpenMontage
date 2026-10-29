# Aviation & Spaceflight Test-History Demand Report

**Pilot topic:** 1984 NASA/FAA Controlled Impact Demonstration (Boeing 720)  
**Decided niche:** aviation and spaceflight test history on archival NASA/USAF footage  
**Date of research:** 2026-10-19  
**Data source:** YouTube Data API v3 via the niche-finder MCP server (`collect_niche`, stdio), stored in local Postgres (`youtube-niche-finder/backend`)  
**Verdict:** DEMAND_SIGNAL_PRESENT

---

## 1. Preflight

| Check | Result |
|---|---|
| `git remote -v` | origin https://github.com/sora73636-stack/OpenMontage ; upstream https://github.com/calesthio/OpenMontage.git |
| `git branch --show-current` | factory/business-documentary-pilot |
| `git status --short` | clean working tree within youtube-niche-finder/ (reports/ added by this task) |
| `git check-ignore .env` | exit 0 — `.env` IS ignored; no secret printed, logged, or committed |
| Scope | Only `youtube-niche-finder/` and `youtube-niche-finder/reports/` touched |
| `video_stat_snapshots` DB | Healthy. Table `video_stats_history` exists (schema v4, `SCHEMA_VERSION=4` in code and `meta`). `init_db()` runs clean, no migration error. Snapshots: 663 before this task → 1,252 after (growth from my own collections recording stats). No schema/migration fix was required — no error was found. |
| `collect_niche` via MCP | WORKS. 12 calls succeeded via MCP stdio (`scripts/mcp-host.sh` → `backend/server.py`). Note: the OpenCode `tools["niche-finder"].*` wrapper returns "Unexpected token (1:3)" in this session, but MCP stdio is fully functional and was used for every call below. |

---

## 2. Queries run (English)

All 6 queries, collected twice each: last 12 months (`period="365d"`) and all-time (`period="all"`), `order="viewCount"`, `pages=1` (up to 50 videos per query, top 15 used).

| # | Query |
|---|---|
| 1 | "boeing 720 controlled impact demonstration" |
| 2 | "nasa crashed a plane on purpose" |
| 3 | "nasa flight test history" |
| 4 | "x-15 test flights documentary" |
| 5 | "xb-70 valkyrie documentary" |
| 6 | "space shuttle approach and landing tests" |

For each query's top 15 videos I recorded: title, channel, subscribers, publish date, views, duration, and views ÷ channel median views (where a channel median could be computed from the collected corpus). Full per-video detail is in `reports/aviation-test-history-demand.csv` (180 rows: 6 queries × 2 periods × 15 videos).

**Labels:** Every number below from the API is **MEASURED**. Channel median views and the views/median ratio are **ESTIMATE** (median computed over that channel's *collected* videos only, not the channel's full lifetime history). No RPM or earnings figures are claimed anywhere.

---

## 3. API quota used (this task)

| Counter | Before | After | Used by this task |
|---|---|---|---|
| search.list calls (100/day bucket) | 12 | 24 | **12** (6 queries × 2 periods) |
| Shared pool units (10,000/day) | 40 | 76 | **36** (~1 unit per 50 videos + per 50 channels, ×12) |

Search budget remaining: 76 calls today (resets at midnight Pacific Time).

---

## 4. Findings

### (a) Videos >100k views from channels <50k subscribers, last 12 months

**Count: 14 unique videos (MEASURED via API).** Deduped by `video_id` (2 rows appeared under two queries). Per-query unique hits:
- boeing 720 controlled impact demonstration: 2
- nasa crashed a plane on purpose: 4
- nasa flight test history: 3
- x-15 test flights documentary: 1
- xb-70 valkyrie documentary: 3
- space shuttle approach and landing tests: 1

**List (MEASURED):**

| Views | Subscribers | Channel | Publish date | Duration | Query | Title |
|---|---|---|---|---|---|---|
| 1,706,334 | 3,080 | Space Wonder | 2026-10-05 | 0:44 | nasa crashed a plane | A Solar Plane Wider Than a Jumbo Jet Bent Until It Broke |
| 817,044 | 25,800 | Xsans Network | 2026-03-08 | 1:12 | nasa crashed a plane | Pesawat Ini Sengaja Dijatuhkan?? (Indonesian) |
| 758,015 | 8,880 | MilitaryMachines | 2026-02-19 | 1:01 | x-15 test flights | Neil Armstrong X-15 Mach 3 skip over Los Angeles |
| 678,610 | 10,000 | Supernova | 2026-01-12 | 8:12 | nasa flight test | Every Artemis Mission Explained |
| 492,725 | 30,100 | Cosmic Galaxies | 2026-04-19 | 0:05 | nasa crashed a plane | NASA Pushed This Rocket Tank Until It Exploded |
| 416,240 | 30,600 | Rocketry | 2026-06-04 | 2:35 | nasa flight test | The Raptor Vacuum Problem Nobody Saw Coming |
| 342,676 | 14,600 | Deep Sky Engine | 2026-07-31 | 0:09 | nasa flight test | The 4-Inch Rocket Flight That Changed NASA Forever |
| 338,838 | 14,200 | Легенды Неба | 2026-01-28 | 27:40 | xb-70 valkyrie | XB-70 Valkyrie (Russian) |
| 288,164 | 29,700 | The insight | 2026-06-15 | 0:30 | xb-70 valkyrie | The Bomber Faster Than Concorde (#shorts) |
| 275,104 | 7,370 | LukaStory | 2026-08-21 | 1:05 | shuttle ALT | Thai-language XB-70 / heavy-cargo-on-airliner video |
| 162,144 | 27,200 | Ashes & Steel | 2026-08-29 | 0:09 | nasa crashed a plane | NASA Crashed a Boeing 720 to Test a Safer Fuel Additive |
| 139,867 | 17,500 | 60Sec History | 2026-06-24 | 0:07 | xb-70 valkyrie | The Bomber That Rode Its Own Shockwaves (#shorts) |
| 137,569 | 327 | Aerospace, Casually | 2026-09-22 | 9:51 | boeing 720 CID | NASA's Famous 1984 Crash Test Wasn't Testing the Plane |
| 107,031 | 7,160 | Land or Go Around | 2026-08-20 | 1:28 | boeing 720 CID | NASA Crashed a Boeing 720 on Purpose in 1984 |

**Signal:** A small channel (327 subs) broke out to 137,569 views on the *exact pilot topic* (1984 CID), with a long-form (9:51) video — that's a 419× views/subs outlier and proof a <50k channel can win here. 13 of the 14 are Shorts (<1 min) or very short; only Aerospace, Casually (9:51) and Supernova (8:12) are long-form.

### (b) Which big channels own each query (all-time top 15, aggregate views, MEASURED)

| Query | Dominant channels |
|---|---|
| boeing 720 controlled impact demonstration | NASA Armstrong Flight Research Center (official, 217,699 agg, 2 videos), Aviões e Músicas (221,530), Land or Go Around (178,768, 2 videos), airailimages (140,616) |
| nasa crashed a plane on purpose | Cleo Abram (40,109,983, 3 videos), Mark Rober (30,281,898), Dhruv Rathee (25,132,044), Brut America (23,364,676) |
| nasa flight test history | Mark Rober (152,637,491), NASA official (102,999,628, 6 videos), Red Bull (86,144,182) |
| x-15 test flights documentary | Real Engineering (8,811,663), Curious Droid (2,626,321), Dark Docs (2,412,613), Scott Manley (1,946,457) |
| xb-70 valkyrie documentary | Mustard (11,575,923), Not What You Think (10,573,202, 2 videos), Across Media (5,884,741), Mike Bell (3,639,097, 2 videos) |
| space shuttle approach and landing tests | Scott Manley (16,845,569, 2 videos), Bret (12,599,527), Steven Jochums (3,670,167) |

**Read:** All-time demand is real and is captured by big channels (NASA official, Mark Rober, Cleo Abram, Real Engineering, Mustard, Scott Manley — tens of millions of views). No single big channel monopolizes every query; there are per-query incumbents to beat or differentiate from.

### (c) Typical duration of top results (MEASURED, median of top 15)

| Query | Median duration (all-time) | Median duration (last 12 mo) |
|---|---|---|
| boeing 720 controlled impact demonstration | 1:28 | 0:41 |
| nasa crashed a plane on purpose | 0:41 | 0:41 |
| nasa flight test history | 31:30 | 8:12 |
| x-15 test flights documentary | 10:14 | 1:21 |
| xb-70 valkyrie documentary | 11:17 | 1:08 |
| space shuttle approach and landing tests | 4:41 | 1:09 |

**Read:** All-time top results skew long (documentary-length, 8–31 min) — that's the incumbent format. But last-12-months results are dominated by Shorts (<1 min): recent discovery is Shorts-led. A long-form entrant faces a format gap: the proven recent vehicle is short, but the proven *deep* vehicle is long.

### (d) Angles the incumbents use (from titles, MEASURED)

- **boeing 720 CID:** counter-intuitive reveal ("Wasn't Testing the Plane"), "crashed on purpose," crash-test destruction spectacle, fireball thumbnails.
- **nasa crashed a plane:** spectacular destruction + "why crash the airplane?" explainer; NASA testing new vehicles (supersonic/solar/rocket); Gemini tragedy.
- **nasa flight test:** current-mission coverage (Artemis II broadcasts, Starship flight coverage) — official-broadcast style.
- **x-15:** engineering deep-dive ("Insane Engineering," "Ultimate Flying Machine"), speed records (Mach 6.7), "bounced off the atmosphere."
- **xb-70:** spectacle + "how was this real?" ("Photoshoot that Destroyed an Airplane," "Looked Fake But Was Real"), mid-air crash, world's fastest bomber.
- **shuttle ALT:** landing/gliding how-to ("How to Land the Space Shuttle," "Like a Glider"), Enterprise archive footage, "Top Gun pilot."

**Common incumbent playbook:** high-production spectacle or engineering explainer, vehicle-centric, official-archive-backed, English-dominant (with some non-English breakouts).

---

## 5. Verdict: DEMAND_SIGNAL_PRESENT

**Reasons:**
1. All-time demand is proven: incumbent big channels pull tens of millions of views on test-flight/archive topics across all six queries (MEASURED).
2. Small channels *can* break out: 14 unique videos >100k views from <50k-subscriber channels in the last 12 months across these queries (MEASURED), including a 327-sub channel at 137,569 views on the exact 1984 CID pilot topic — a 419× views/subs outlier (MEASURED).
3. The pilot topic specifically has a documented small-channel breakout (Aerospace, Casually), meaning the topic is not locked by incumbents.

**Caveats (not a reason to abort, but to shape the format):**
- Recent (12-month) discovery is Shorts-dominated: median duration 0:41–1:21. A long-form pilot would be swimming against the current discovery format.
- All-time views are owned by incumbents (NASA official, Cleo Abram, Mark Rober, Real Engineering, Mustard, Scott Manley); a new entrant must differentiate, not copy.

**No RPM or earnings claims are made.**

---

## 6. Three candidate angles that differ from the big channels

1. **"What they weren't actually testing"** — Counter-intuitive reveal angle: each video exposes the hidden secondary objective behind a famous test flight (e.g., the 1984 CID wasn't really about the plane). Long-form narrative, built around the "gotcha" reveal. Differs from Cleo Abram's polished explainers and Real Engineering's engineering deep-dives by leading with a concealed purpose rather than the vehicle.

2. **Forensic archival breakdown** — Frame-accurate technical reading of the actual NASA/USAF footage with on-screen measurements (impact speed, G-load, fuel slippage, telemetry). Treats the archival film as primary evidence. Differs from Mustard/Dark Docs spectacle and NASA's official broadcasts by adding measured, frame-level analysis big channels don't do.

3. **"The test pilots"** — Human-interest profiles of the people who flew the tests (X-15 pilots, NASA Armstrong crews, Enterprise pilots), woven from archival footage, photos, and the pilot's own words. Vehicle-agnostic, people-centric. Differs from the vehicle-centric incumbent coverage (Scott Manley, Mustard) which focuses on the machine, not the human at the controls.

---

## 7. Files

- `reports/aviation-test-history-demand.md` — this report
- `reports/aviation-test-history-demand.csv` — 180 rows, all top-15 videos per query/period with title, channel, subscribers, publish date, views, duration, and channel-median-views ratio (ESTIMATE)
