# T16 — Viewer Intent (Apollo Questions from Comments)

**Date:** 2026-10-19  
**Scope:** Questions viewers actually ask about Apollo.  
**Data:** Existing T8 comments (422) + 6 new `video_comments` calls (600 comments) on Apollo 9/10/11 videos (Professor Dave, NASA moonwalk, Dhruv Rathee, Michael Lennick "Apollo 10 Nearly Crashes", Hazegrayart, NASA 50th Anniversary).  
**Metrics:** Counts only, no usernames.  
**Labels:** MEASURED (comment counts) or ESTIMATE. No RPM/earnings claims.  
**API quota:** 6 video_comments calls (units, not search calls).

---

## 1. Comment volume (MEASURED)

| Source | Comments |
|---|---:|
| T8 existing (Scott Manley, Aviões e Músicas, Ashes & Steel) | 422 |
| T16 new (6 videos, 100 each) | 600 |
| **Total Apollo comments analyzed** | **1,022** |
| Of which are questions | **449 (44%)** |
| Of which are technical questions | **160 (18%)** |
| Of which are "why did they..." questions | **6** |
| Myth/hoax-related comments | **62** |

---

## 2. Ranked viewer questions (by frequency category)

### Technical questions (top terms, MEASURED)
| Term | Count | Example context |
|---|---:|---|
| comm (communications/radio) | 54 | How did they talk to Houston? |
| landing | 48 | How did the landing work? |
| roll / pitch / yaw | ~36 | Attitude control during landing |
| pilot | 23 | Who was flying at what moment? |
| orbit | 20 | Which orbit, how did they get there? |
| EVA | 8 | What did Schweickart do outside? |
| descent / ascent | 12 | Descent engine, ascent stage |
| fuel | 10 | Fuel callouts, how much fuel left? |
| abort | 4 | Abort modes, when to abort? |
| 1201/1202 alarms | (in landing) | Computer alarms during landing |

### "Why did they..." questions (MEASURED, n=6 genuine)
Only 6 genuine "why did they..." questions found across 1,022 comments — **very low frequency**. Examples:
- "Why does everybody think this is fake?" (NASA moonwalk video, 744 likes) — myth-busting intent
- "Why do they look to be translucent?" (NASA, 732 likes) — visual quality question
- "Why is that strange?" (Michael Lennick Apollo 10, 0 likes) — orbital mechanics

### Myth / hoax intent (MEASURED, n=62)
Comments questioning whether landings were real, flag waving, shadows, "no stars," studio/film-set claims. Highest-liked: "Why does everybody think this is fake?" (744 likes on NASA's restored moonwalk video). **Strong viewer appetite for myth-busting / evidence-based explanation.**

---

## 3. What viewers actually want to know (ranked)

| Rank | Intent | Evidence (count) | Hook candidate |
|---|---|---|---|
| 1 | Myth-busting / "was it real?" | 62 myth comments + 744-like "why fake?" comment | "Was Apollo 10's near-crash real? Here's the telemetry." |
| 2 | Communications / how they talked to Houston | 54 comments mention comm/radio | "How Apollo 10 talked to Houston from 50,000 feet." |
| 3 | Landing procedure / how it worked | 48 comments mention landing | "How Apollo 11's Eagle actually landed — step by step." |
| 4 | Attitude control (roll/pitch/yaw) | ~36 comments | "How Armstrong flew the LM manually with 1201 alarms screaming." |
| 5 | Fuel / callouts | 10 comments | "The fuel callouts that decided Apollo 11's landing." |
| 6 | EVA / Schweickart's spacewalk | 8 comments | "Schweickart's stand-up EVA: what he actually tested." |
| 7 | Abort modes / when to abort | 4 comments | "Apollo 10's abort guidance — when they almost didn't come home." |

---

## 4. Viewer intent verdict

Viewers ask **technical "how" questions** (communications, landing procedure, attitude control, fuel) at ~4x the rate of "why did they" questions (160 vs 6). They also show **strong myth-busting appetite** (62 myth comments, 744-liked "why fake?"). 

**Implication:** Hook candidates should lead with technical specifics (how docking worked, how landing proceeded, what the alarms meant) and/or myth-busting framing ("what really happened during Apollo 10's crisis"), not generic "why did they go to the Moon" framing.

---

## 5. Files

- `reports/t16-viewer-intent.csv` — categorized comment data
