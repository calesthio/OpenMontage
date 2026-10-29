# T6 — Apollo Deep Dive

**Date:** 2026-10-19  
**Scope:** Apollo test flights sub-topics (LM tests, Saturn V stage tests, Apollo 9/10, Mercury/Gemini tests, lunar rover).  
**Data:** Existing T1 corpus ("Apollo test flights", 50 videos) + T6 corpus ("Saturn V stage test", 50 videos).  
**Note:** `collect_niche` tool returned errors for 16 of 17 sub-topic queries attempted; only "Saturn V stage test" succeeded. Analysis limited to existing corpus (99 unique videos after dedup).  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.

---

## 1. Corpus overview (MEASURED)

| Metric | Value |
|---|---|
| Total unique videos (Apollo test flights + Saturn V stage test) | 99 |
| Videos from "Apollo test flights" niche | 50 |
| Videos from "Saturn V stage test" niche | 50 |
| Overlap (deduped) | 1 |

---

## 2. Sub-topic distribution (MEASURED)

| Sub-topic | Videos in corpus | Long-form (>=15 min) |
|---|---:|---:|
| Saturn V | 41 | 7 |
| LM test (lunar module) | 21 | 12 |
| Apollo 1 (fire) | 16 | 8 |
| Other | 14 | varies |
| Mercury | 2 | 2 |
| Gemini | 2 | 2 |
| Lunar rover | 2 | 0 |
| Apollo 8 | 1 | 1 |
| Apollo 9 | 0 | 0 |
| Apollo 10 | 0 | 0 |
| Apollo 11 | 0 | 0 |
| Apollo 13 | 0 | 0 |

**Sub-topics with NO long-form (>=15 min) video from any channel in corpus:**
- Apollo 9 — 0 videos total in corpus
- Apollo 10 — 0 videos total in corpus
- Apollo 11 — 0 long-form (shorts only)
- Apollo 13 — 0 long-form
- Lunar rover — 0 long-form

These are **candidate gap topics** — no long-form incumbent presence in the collected corpus.

---

## 3. Long-form (>=15 min) breakouts by sub-topic (MEASURED)

### Saturn V (7 long-form)
| Views | Subs | Duration | Date | Channel | Title |
|---:|---:|---:|---|---|---|
| 28,148,893 | 15,100,000 | 610 min | 2026-04-07 | NASA | Artemis II Crew Flies Around the Moon |
| 5,007,434 | 11,900,000 | 58 min | 2022-12-26 | SmarterEveryDay | Asked An Actual Apollo Engineer to Explain Saturn 5 |
| 2,160,190 | 7,290,000 | 20 min | 2017-06-05 | Adam Savage's Tested | Builds the LEGO NASA Apollo Saturn V |
| 757,697 | 15,000 | 52 min | 2024-05-17 | The Modern Age | Saturn V: Most Powerful Rocket Of Its Time |
| 461,040 | 38,300 | 25 min | 2022-08-04 | Retro Space HD | Apollo 4 & 6: First Saturn V Test Flights |

### LM test (12 long-form) — top 5
| Views | Subs | Duration | Date | Channel | Title |
|---:|---:|---:|---|---|---|
| 1,280,383 | 815,000 | 31 min | 2026-05-06 | MythBusters | Moon Landing Film Shot In Hollywood Studio? |
| 398,705 | 182,000 | 17 min | 2026-04-06 | Dave McKeegan | Artemis Causes Big Problem for Deniers |
| 353,719 | 1,130,000 | 52 min | 2026-07-08 | Free Documentary - History | Saturn V: How NASA Built the Most Powerful Rocket |
| 310,936 | 51,600 | 16 min | 2026-05-22 | Digital Astronaut | What Artemis III will do |
| 173,341 | 4,470,000 | 20 min | 2026-09-25 | Professor Dave Explains | Apollo 9: Testing the Lunar Module |

### Apollo 1 (8 long-form) — top 5
| Views | Subs | Duration | Date | Channel | Title |
|---:|---:|---:|---|---|---|
| 555,925 | 137,000 | 52 min | 2026-08-16 | The American Story | Apollo Hoax Claims Tested |
| 545,482 | 6,750,000 | 34 min | 2026-02-08 | 60 Minutes Australia | Apollo 11 pilot thinks we don't need to go back |
| 62,940 | 26,500,000 | 44 min | 2026-07-19 | National Geographic | Inside the Moon Landing: Disaster and Triumph |
| 55,756 | 68,600 | 21 min | 2026-06-01 | The Space Explained | Every Apollo Moon Mission Explained |
| 38,885 | 100,000 | 89 min | 2026-04-06 | C-SPAN | Jim Lovell Talks About Apollo 8 & Apollo 13 |

---

## 4. Angles incumbents use (MEASURED, keyword frequency in titles)

| Keyword | Videos | Angle type |
|---|---:|---|
| moon | 21 | Destination/hero |
| test | 16 | Technical/procedural |
| mission | 12 | Narrative/framework |
| explained | 7 | Educational |
| flight | 7 | Operational |
| disaster | 4 | Tragedy/safety |
| history | 4 | Retrospective |
| landing | 4 | Event-focused |
| lunar | 6 | Technical |

Dominant angles: official broadcasts (NASA), engineering explanations (SmarterEveryDay, Jared Owen), disaster/safety retrospectives (60 Minutes, National Geographic, MythBusters), and animation/visualization (Hazegrayart, James Wilkinson).

---

## 5. Top incumbent channels (MEASURED)

| Channel | Subs | Max views | Videos in corpus |
|---|---:|---:|---:|
| NASA | 15,100,000 | 28,148,893 | 2 |
| Mark Gray | 24,700 | 10,446,315 | 2 |
| Hazegrayart | 1,150,000 | 8,828,341 | 1 |
| James Wilkinson | 22,600 | 6,032,412 | 1 |
| SmarterEveryDay | 11,900,000 | 5,007,434 | 1 |
| Jared Owen | 4,440,000 | 4,928,086 | 1 |
| Digital Astronaut | 51,600 | 4,258,454 | 2 |
| Everyday Astronaut | 1,990,000 | 2,864,303 | 3 |

---

## 6. Gap analysis — candidate topics

| Sub-topic | Long-form videos | Assessment |
|---|---:|---|
| Apollo 9 | 0 | **GAP** — no incumbent long-form content |
| Apollo 10 | 0 | **GAP** — no incumbent long-form content |
| Apollo 11 | 0 | **GAP** — no long-form in corpus |
| Apollo 13 | 0 | **GAP** — no long-form in corpus |
| Lunar rover | 0 | **GAP** — no long-form in corpus |
| Mercury | 2 | Thin coverage |
| Gemini | 2 | Thin coverage |
| Apollo 1 | 8 | Covered (disaster/safety angle) |
| Saturn V | 7 | Well covered |
| LM test | 12 | Well covered |

**Recommendation:** Apollo 9, Apollo 10, and lunar rover are the strongest gap candidates — zero long-form videos from any channel in the corpus, suggesting underserved demand for long-form deep-dives on these specific missions.

---

## 7. Files

- `reports/t6-apollo-deep-dive.csv` — per-video data (99 rows)
- `reports/t6-subtopic-summary.csv` — sub-topic rollup
