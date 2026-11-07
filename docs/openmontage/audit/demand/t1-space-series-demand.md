# T1 — Space Series Demand (30 Topics)

**Date:** 2026-10-19  
**Scope:** YouTube Data API v3 via niche-finder MCP (`collect_niche`), 30 space/astronomy topics, 1 query each (30 search calls).  
**Window:** Last 12 months (`published_after = 2025-10-19`).  
**Per topic:** Top 10 videos by views; channel subs, views, duration, date recorded.  
**Breakout definition (MEASURED):** long-form >= 8 min, > 50k views, channel < 50k subs, published in last 12 months.  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.

---

## 1. Topic ranking by measured small-channel breakouts

| Rank | Topic | Breakouts (MEASURED) |
|---|---|---:|
| 1 | Voyager | 2 |
| 2 | Cassini | 1 |
| 3 | James Webb first images | 1 |
| 4 | Lucy mission | 1 |
| 5–30 | Artemis, SLS, Perseverance, Hubble, JWST, Apollo test flights, ISS, Mars helicopter, SpaceX Starship, Falcon 9, Curiosity, New Horizons, OSIRIS-REx, Artemis II, Crew Dragon, Parker Solar Probe, Juno, Mars sample return, Polaris Dawn, Starliner, Lucy mission(*), DART, Europa Clipper, Artemis I, Starship test flight, Mars rover, space telescope | 0 |

**Total breakouts across 30 topics: 5 (MEASURED).** 26 of 30 topics had ZERO small-channel long-form breakouts in the last 12 months.

*Note: "Lucy mission" breakout is a false topical match (dinosaur video, not space). Voyager and Cassini breakouts are non-English (Spanish/Russian). The only English on-topic small-channel breakout is "6 MINUTES AGO: Vera Rubin's First Images JUST STOPPED THE WORLD!" under James Webb first images.*

---

## 2. Breakout video details (MEASURED via API)

| Topic | Title | Views | Subs | Duration | Date | Channel |
|---|---|---:|---:|---|---|---|
| Voyager | Lo que la Voyager detectó en el borde del Sistema Solar | 3,012,790 | 39,700 | 19:11 | 2026-01-23 | (Spanish) |
| Voyager | ¿Cuánto se tarda en cruzar UN AÑO LUZ? | 2,591,540 | 44,700 | 11:08 | 2026-07-24 | (Spanish) |
| Cassini | Кассини-Гюйгенс: жертва ради жизни | 1,315,045 | 15,500 | 20:12 | 2026-01-03 | (Russian) |
| James Webb first images | 6 MINUTES AGO: Vera Rubin's First Images JUST STOPPED THE WORLD! | 1,844,152 | 16,400 | 21:12 | 2026-07-23 | (English) |
| Lucy mission | Dinosaur Saves the Car… Henry's Mission Is Complete! | 1,045,507 | 36,100 | 48:29 | 2026-10-15 | (off-topic) |

---

## 3. Sample sizes per topic (MEASURED)

Every topic returned 50 videos (pages=1); top 10 analyzed per topic = **300 video records total**. Breakouts measured against full corpus channel medians (ESTIMATE) for views/median ratio.

---

## 4. Demand verdict

**WEAK demand signal.** Only 5 of 300 analyzed videos qualified as small-channel long-form breakouts (>50k views, <50k subs, >=8 min, 12 months), and 3 of those 5 are non-English or off-topic. 26 of 30 topics produced zero breakouts. High-volume topics (Artemis, SLS, Perseverance, Hubble, JWST, ISS, Starship) are dominated by large channels/official sources, not small-channel breakouts.

---

## 5. Files

- `reports/t1-space-series-demand.csv` — 280 rows (top 10 per topic × 30 topics)
- `reports/t1-topic-summary.csv` — 30 rows (topic → breakout count)
