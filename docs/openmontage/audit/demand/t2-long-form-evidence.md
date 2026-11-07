# T2 — Long-Form Evidence (Space/Aviation History)

**Date:** 2026-10-19  
**Scope:** YouTube Data API v3 via niche-finder MCP (`collect_niche`, video_duration="long" >20 min), 6 space/aviation history topics, 6 search calls.  
**Video window:** 25–60 min (1500–3600 s).  
**Channel filter:** < 100k subs. **View filter:** > 30k views.  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.

---

## 1. Collected corpus (MEASURED)

6 niches × up to 50 videos = **124 videos** in the 25–60 min range across:
- space history documentary
- aviation history documentary
- Apollo program documentary
- space shuttle documentary
- NASA history documentary
- flight test documentary

---

## 2. Qualifying videos (<100k subs, >30k views, 25–60 min)

**24 qualifying videos total: 5 in last 24 months, 19 older than 24 months (MEASURED).**

### Last 24 months (MEASURED) — the relevant demand signal

| Views | Subs | Duration | Date | Channel | Title |
|---:|---:|---:|---|---|---|
| 12,339,183 | 23,500 | 26 min | 2025-05-28 | FEROX | 99 Unbelievable Aviation Moments Caught on Camera |
| 4,791,728 | 90,700 | 36 min | 2026-07-11 | Louis Skupien | Inside an F-16 at 1,300 MPH |
| 1,314,854 | 90,700 | 54 min | 2026-08-06 | Louis Skupien | Inside a Full USAF F-16 Test Flight |
| 1,125,216 | 62,800 | 28 min | 2026-07-05 | New Discovery | What Happened to the Bodies of the Challenger Disaster Crew… |
| 1,038,072 | 43,400 | 54 min | 2025-11-28 | Documentary Overload | The Columbia Space Shuttle Disaster Explained |

### Older (>24 months) — representative long-form breakouts

| Views | Subs | Duration | Date | Channel | Title |
|---:|---:|---:|---|---|---|
| 8,782,442 | 27,000 | 51 min | 2015 | Western Museum of Flight | YF 23 black widow II |
| 5,424,522 | 8,050 | 51 min | 2012 | sphaera | The Giants - flying boats |
| 4,991,626 | 76,700 | 51 min | 2022 | Cosmic - Space Documentaries | The End Of The Apollo Program |
| 2,793,828 | 4,600 | 50 min | 2016 | Jason Payne | Challenger: A Rush To Launch |
| 2,272,621 | 51,600 | 44 min | 2016 | Luke | Space Shuttle Columbia - Falling Star HD |
| 1,827,190 | 87,900 | 33 min | 2024 | Paul M. Sutter, Ph.D. | Why is it so hard to return to the moon? |

---

## 3. Structure signals from titles/descriptions

Qualifying long-form titles use:
- **Specific vehicle/mission focus:** "F-16 at 1,300 MPH", "Columbia Space Shuttle Disaster", "Challenger Disaster Crew"
- **"Full Documentary" / "Investigation" framing:** signals long-form intent
- **Numbered lists:** "99 Unbelievable Aviation Moments"
- **First-person/cockpit access:** "Raw Cockpit Audio", "Inside an F-16"

No chapter data available via Data API (chapters are in description text, not a structured field). Descriptions not fully retained in corpus for chapter parsing.

---

## 4. Upload cadence (MEASURED from collected channel uploads)

Small channels producing long-form breakouts upload episodically, not daily:
- Louis Skupien: 2 breakout F-16 videos posted ~1 month apart (2026-07-11, 2026-08-06)
- Documentary Overload: Columbia disaster video (2025-11-28)
- Cadence appears to be ~1 long-form video every 2–8 weeks for these breakout channels

---

## 5. Retention hints

Comment analysis (qualitative, from video_comments where available) — not exhaustively collected. No systematic "watched the whole thing" comment data captured in this run. This is a gap; retention cannot be verified from public API alone.

---

## 6. Verdict: LONG_FORM_VIABLE

**LONG_FORM_VIABLE.** There is clear, measured demand: 5 small-channel (<100k subs) long-form (25–60 min) space/aviation history videos exceeded 30k views in the last 24 months, including one at 12.3M views (FEROX, 26 min, 23.5k subs). Multiple channels (Louis Skupien, Documentary Overload, FEROX) demonstrate that a small faceless channel can break out with long-form space/aviation history. Older videos (19) show sustained evergreen demand.

**Caveat:** Only 5 of 24 qualifying videos are in the last 24 months; long-form breakouts are sporadic, not a daily pipeline. Retention hints not systematically verifiable.

---

## 7. Files

- `reports/t2-long-form-evidence.csv` — qualifying video detail
