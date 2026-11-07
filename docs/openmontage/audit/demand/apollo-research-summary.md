# Apollo Research Summary (T13–T18)

**Date:** 2026-10-19  
**Scope:** Apollo 9, 10, 11 — demand, gaps, primary sources, viewer intent, title variants, format check.  
**Data:** YouTube Data API via `scripts/mcp-host.sh` (OpenCode MCP wrapper returns "Unexpected token"; `mcp-host.sh` works), existing T1/T6/T8/T10 corpora, web search for primary sources.  
**API quota:** ~51/100 search calls used across this session; 49 remaining.  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.

---

## 1. T13 — Apollo 9 Deep Dive

~40 unique Apollo 9 videos collected. Long-form (≥15 min) coverage exists for most sub-stories but is old/low-view except one recent (Professor Dave, 2026-09-25, 20.9 min, 173k views).

**Sub-story long-form coverage (MEASURED):**

| Sub-story | Long-form ≥15 min? | Gap? |
|---|---|---|
| Rendezvous / docking maneuver | PARTIAL (125.6 min docking, 2025, lunarmodule5; 28.7 min space duet) | No recent high-view dedicated video; T10 Comp 0.0, N=3 |
| EVA test (Schweickart stand-up EVA) | PARTIAL (17.3 min, 2026-06-15, Enki Project — recent) | Mostly shorts otherwise |
| LM free flight (Spider independent) | PARTIAL (20.9 min Professor Dave; 23.2 min LM Maneuvers) | General, not flight-specific |
| Crew: McDivitt | NO dedicated solo | Covered only jointly with Scott (25.6 min) |
| Crew: Scott | NO dedicated solo | Covered only jointly with McDivitt (25.6 min) |
| Crew: Schweickert | YES (89 min Beyond Schweickert; 32 min Fighter Pilot; 16.2 min narrated) | Well covered |
| Test goals / SPS burns | PARTIAL (20.9 min Testing LM; 18.4 min overview) | General, not burn-by-burn |

**Ranked chapter candidates (Apollo 9):**
1. Rendezvous / docking maneuver (T10 Comp 0.0 — biggest gap)
2. LM free flight (Spider independent)
3. Crew: McDivitt (solo)
4. Crew: Scott (solo)
5. EVA test (has one recent long-form)
6. Test goals / SPS burns (burn-by-burn detail missing)

---

## 2. T14 — Apollo 10 and 11 Gaps

**Apollo 10:** 2 long-form videos total; only 1 recent (<12mo) and not Apollo-10-specific. Essentially **no dedicated recent long-form**. Omissions: technical detail (descent profile), test engineering (staging/abort guidance), mistakes (Snoopy tumbling crisis — only in 3.9-min short), procedure (DOI, staging, rendezvous). **Gap severity: EXTREME.**

**Apollo 11 (first moonwalk):** 8 recent long-form (<12mo) but **zero dedicated to the moonwalk itself** (only one at 25 views). Recent long-form covers hoax claims, Saturn V, LM general, Gene Kranz interview, general overviews. **Gap severity: HIGH** — demand exists (all 50 "first moonwalk" results >100k views) but no recent technical long-form.

**Omissions both missions:** technical detail, test engineering, mistakes, procedure.

---

## 3. T15 — Primary Sources Map

All three missions' primary sources are NASA public domain (U.S. govt work), reachable without a key; logos/insignia restricted (14 CFR 1221). Corrected/annotated journal content may carry editor copyright — use raw transcripts for reuse.

| Mission | Key sources |
|---|---|
| Apollo 9 | NASA Mission Details; Mission Report MSC-PA-R-69-2 (ibiblio); Press Kit; Flight Journal (nasa.gov/history/afj) |
| Apollo 10 | NASA Mission Overview; Flight Journal; NTRS mission report |
| Apollo 11 | NASA Mission Overview; Mission Report NTRS 19700008096 + 19710015566; Raw transcripts (history.nasa.gov); Crew Debriefing; Lunar Surface Journal (corrected = copyrighted); Flight Journal |

**Load-bearing facts with two independent sources (examples):** Apollo 9 crew names (NASA Mission Details + Mission Report); Apollo 9 launch date March 3 1969 (NASA + LPI + SpaceFacts); Apollo 9 top priority = rendezvous/docking (NASA Mission Details ×2 + Mission Report); Apollo 11 crew names + landing site (NASA Overview + Wikipedia/Britannica); "The Eagle has landed" July 20 1969 (NASA + Britannica).

**Caution:** Do not state mission facts from memory — verify against NTRS mission reports and Flight Journal transcripts (especially burn times, alarm codes, fuel callouts).

---

## 4. T16 — Viewer Intent (1,022 Apollo comments, 449 questions)

| Category | Count | Share |
|---|---:|---:|
| Total Apollo comments | 1,022 | 100% |
| Questions | 449 | 44% |
| Technical questions | 160 | 18% |
| "Why did they..." questions | 6 | <1% |
| Myth/hoax comments | 62 | 6% |

**Top technical terms:** communications (54), landing (48), roll/pitch/yaw (~36), pilot (23), orbit (20), EVA (8), descent/ascent (12), fuel (10), abort (4).

**Myth intent:** "Why does everybody think this is fake?" (744 likes on NASA moonwalk video) — strong myth-busting appetite.

**Ranked hook candidates:**
1. Myth-busting / "was it real?" (62 comments)
2. Communications / how they talked to Houston (54)
3. Landing procedure / how it worked (48)
4. Attitude control / manual landing with alarms (~36)
5. Fuel callouts (10)
6. EVA / Schweickart (8)
7. Abort modes (4)

**Viewers ask technical "how" at ~4x the rate of "why did they" (160 vs 6).**

---

## 5. T17 — Title Variants (analysis only)

Ten truthful title candidates for Apollo 9/10 gap topics, each tied to an observed (N=1) pattern from measured breakouts. **No claim that any pattern works** — sample size N=1 per pattern. Closest existing video views are MEASURED, not predictions.

Top candidates: "Apollo 9: Testing the Lunar Module Docking" (pattern from Professor Dave 173k views); "Apollo 10: Snoopy's Descent to 50,000 Feet" (pattern from Lennick 334k views); "Apollo 10: Staging Crisis — When Snoopy Tumbled"; "Apollo 9: The Rendezvous: Spider Meets Gumdrop"; "Apollo 10: The Final Test Before Apollo 11".

Use `hookscore.py` (yt-script skill) to score variants before publishing.

---

## 6. T18 — Shorts vs Long-Form (small channels, <50k subs, <12 mo)

| Format | Count | Median views | Median subs | Median views/subs | Median duration |
|---|---:|---:|---:|---:|---:|
| Shorts (<60s) | 23 | 7,140 | 1,070 | 2.5x | <1 min |
| Long-form (≥8 min) | 25 | 9,276 | 2,430 | 1.4x | 18.8 min |

**Verdict: Publish BOTH, sequence Shorts first.** Shorts achieve 2.5x views/subs (better discovery from zero); long-form has slightly higher absolute median views but from bigger-subscriber channels (~2.3x more subs). **Noise warning: N=23/N=25 — directionally suggestive, not conclusive.**

---

## 7. Five Concrete Recommendations

1. **Pilot on Apollo 9 rendezvous/docking** — T10 Comp score 0.0 (N=3, 0 >100k views, 0 <12mo, 0 long-form). It is the widest gap with NASA Mission Report + Flight Journal as primary sources for technical detail.
2. **Sequence Shorts first, then long-form** — Shorts get 2.5x views/subs from small channels (N=23, noise warning); use them to test angles, then long-form for watch time once you have subscribers.
3. **Lead hooks with technical specifics + myth-busting** — Viewers ask "how" (communications, landing, alarms) 4x more than "why did they" (160 vs 6), and 62 comments + a 744-like comment show myth-busting appetite. Combine: "What really happened during Apollo 10's staging crisis — with the telemetry."
4. **Use NTRS mission reports + Flight Journal for technical accuracy** — These are the source of burn-by-burn, staging, alarm, and procedure detail that recent long-form lacks. Verify every load-bearing fact against two sources (see T15 two-source table).
5. **Score title variants with hookscore.py before publishing** — Ten candidates drafted (T17), all N=1 pattern observations. Test hook variants; don't rely on title pattern alone.

---

## 8. Unknowns

- Whether a <50k-sub channel can break out with Apollo 9 docking long-form (Comp 0.0 suggests demand but no recent supply — untested).
- Exact Content ID risk on NASA archival footage (public domain but third parties claim it — documented by Ars Technica 2012/2020).
- Whether Shorts-first actually converts to long-form watch time for this niche (small sample, no longitudinal data).
- Whether the Apollo 10 "nearly crashes" short-form angle (334k views) translates to long-form (no long-form equivalent exists).
- CTR/retention for any angle — not measurable from public API data.

---

## 9. Files

- `reports/t13-apollo9-deep-dive.md` + `.csv`
- `reports/t14-apollo10-11-gaps.md` + `.csv`
- `reports/t15-primary-sources.md` + `.csv`
- `reports/t16-viewer-intent.md` + `.csv`
- `reports/t17-title-variants.md`
- `reports/t18-shorts-vs-longform.md` + `.csv`
