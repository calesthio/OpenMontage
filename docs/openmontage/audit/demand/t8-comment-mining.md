# T8 — Comment Mining (CID competitors + top Apollo videos)

**Date:** 2026-10-19  
**Scope:** 8 videos (5 CID competitors + 3 Apollo), 422 comments collected via `video_comments` API.  
**Data:** Top-100 comments by relevance per video.  
**Labels:** Counts only, no usernames/personal data. MEASURED (API) or ESTIMATE.

---

## 1. Comment volume per video (MEASURED)

| Video | Channel | Topic | Comments collected |
|---|---|---|---:|
| 7fjV70tZQfI | Aerospace, Casually | CID | 32 |
| Imo4uKqd3Yo | Land or Go Around | CID | 66 |
| pMO5gLNBKKU | NASA Armstrong FRC | CID | 9 |
| vVyZeSgxmsw | airailimages | CID | 8 |
| phhH4LswVgA | theflinx | CID | 90 |
| FxphOosK08I | Scott Manley | Apollo | 100 |
| jESn3W0vaRg | Aviões e Músicas | Apollo | 100 |
| GVMTzBDhHMU | Ashes & Steel | Apollo | 17 |
| **Total** | | | **422** |

---

## 2. Viewer topic requests (MEASURED, n=8)

| Likes | Channel | Request |
|---:|---|---|
| 8 | Land or Go Around | "How about some original content? Seen it many times" |
| 0 | Land or Go Around | "I got that test was really about remotely controlling planes? I was told fuel additive was a cover" |
| 5 | Scott Manley | "Pretty good commentary... Had not been aware of this tragedy of the Gemini 9 crew" |
| 11 | Scott Manley | "Reading the title I'm scratching my head thinking - there were no Gemini crashes... To follow up" |
| 2 | Scott Manley | "Thanks for covering this and for the original research" |
| 2 | Scott Manley | "Thank you, Mr. Manley. Now that seems to look as more balanced coverage" |
| 1 | Aviões e Músicas | Portuguese: saw this "accident" on Discovery |
| 0 | Aviões e Músicas | Portuguese: saw this video years ago on a documentary (Discovery, NatGeo, cable TV) |

**Top request themes:** Original/non-repetition content, behind-the-scenes technical details (remote piloting), Gemini program coverage, balanced/factual coverage.

---

## 3. Common complaints (MEASURED)

| Complaint type | Examples (count) |
|---|---|
| **Repetition / lack of original content** | "How about some original content? Seen it many times" (Land or Go Around, 8 likes) |
| **Footage quality** | "whole lotta grey" (theflinx, 32 likes) — low-quality/gray archival footage |
| **Moderation/censorship** | "conspiracy theory posts will be deleted" (theflinx, 46 likes) |
| **Music** | "this needs dramatic music" (NASA Armstrong, 3 likes) |
| **Logo/nasa branding painted over** | "Small thing but I wondered why the 727s number, nasa logo and faa nose logo were painted over" (Aerospace, Casually, 0 likes) |

---

## 4. Factual corrections from viewers (MEASURED, n=18)

| Likes | Channel | Correction |
|---:|---|---|
| 0 | Aerospace, Casually | "The test was a failure. Because the last minute remote-piloting error drove an engine through that hyper-aggressive cutter blade" |
| 10 | Aerospace, Casually | "Gathering data is never a failure" (counter-argument) |
| 1 | Land or Go Around | "The test wasn't a complete failure as the fireball self extinguished" |
| 14 | theflinx | "this was supposed to be the last flyby before controlled impact and so it exited the planned debris path" |
| 5 | Scott Manley | "Pretty good commentary... Had not been aware of this tragedy of the Gemini 9 crew" |

**Pattern:** Viewers actively correct mischaracterizations of test outcomes (failure vs. success) and technical details. Channels that get facts wrong face visible pushback.

---

## 5. Personal memories / nostalgia (MEASURED, n=21)

| Likes | Channel | Memory |
|---:|---|---|
| 13 | airailimages | "I was there! I lived in Edwards AFB 84-86" |
| 12 | airailimages | "I remember this test crash like it was YESTERDAY!!!!" |
| 8 | Aerospace, Casually | "Here in the UK, this clip was always captioned as a fuel test. I remember seeing it as a kid in the 80's." |
| 96 | Scott Manley | "When I was 8, I remember finding clippings about the accident in a scrapbook" |

---

## 6. Ranked list of viewer requests

1. **Original/non-repetition content** — viewers are tired of seeing the same archival clips repeated across channels
2. **Behind-the-scenes technical details** — how remote piloting worked, what systems failed, why design choices were made
3. **Balanced/factual coverage** — viewers appreciate corrections and nuance, push back on mischaracterizations
4. **Gemini program coverage** — specific interest in Gemini 9 and related missions
5. **Personal witness accounts** — high engagement on comments from people who witnessed events (Edwards AFB, etc.)

---

## 7. Common mistakes to avoid

1. **Repetitive archival re-uploads** — viewers explicitly ask for "original content" and note they've "seen it many times"
2. **Mislabeling test outcomes** — viewers correct "failure" vs "success" characterizations
3. **Low-quality/gray footage without enhancement** — "whole lotta grey" complaint
4. **Missing dramatic music** on dramatic footage — NASA uploads criticized for lacking music
5. **Ignoring witness/personal connections** — viewers with direct experience engage strongly

---

## 8. Files

- `reports/t8-comment-mining.csv` — per-comment categorization
