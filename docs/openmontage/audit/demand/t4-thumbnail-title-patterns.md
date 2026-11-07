# T4 — Thumbnail/Title Patterns (30 Space Topics)

**Date:** 2026-10-19  
**Scope:** Existing T1 corpus (280 video records, top 10 per topic × 30 topics, MEASURED via API).  
**Thumbnail text:** NOT available via YouTube Data API (only thumbnail URL returned; text would require OCR/image inspection — NOT_CHECKED, no image judgement made).  
**Labels:** MEASURED (API) or ESTIMATE. No RPM/earnings claims.

---

## 1. Title length (MEASURED, n=280)

| Stat | Value |
|---|---|
| Median length | 53 chars |
| Mean length | 56 chars |
| Min | 7 chars |
| Max | 100 chars |
| <= 60 chars | 173 (62%) |
| 61–100 chars | 107 (38%) |
| > 100 chars | 0 (0%) |

No title exceeded 100 characters; titles cluster around 40–70 chars.

---

## 2. Title patterns (MEASURED, n=280)

| Pattern | Count | Share |
|---|---:|---:|
| Contains a digit | 71 | 25% |
| Curiosity-gap keyword (secret/impossible/shocking/why/real reason/exposed/first time, etc.) | 46 | 16% |
| 4+ consecutive caps (e.g., "NASA", "JUST STOPPED") | 110 | 39% |
| Emoji | 72 | 26% |

Top title-opening words (MEASURED): "The" (19), "NASA" (16), "NASA's"/"NASA’s" (14+9), "This" (11), "Why" (9), "SpaceX" (7), "We" (6), "Starship" (6).

---

## 3. Breakout vs non-breakout pattern comparison (MEASURED)

Breakouts = long-form >=8 min, >50k views, channel <50k subs, last 12 months (n=5). Non-breakouts (n=275).

| Pattern | Breakouts (n=5) | Non-breakouts (n=275) |
|---|---:|---:|
| Median title length | 64 chars | 53 chars |
| Contains a digit | 2 (40%) | 69 (25%) |
| Curiosity-gap keyword | 1 (20%) | 45 (16%) |
| 4+ caps run | 1 (20%) | 109 (40%) |

Breakout titles (all 5):
- "Lo que la Voyager detectó en el borde del Sistema Solar" (Spanish)
- "¿Cuánto se tarda en cruzar UN AÑO LUZ? (la respuesta te va a doler)" (Spanish)
- "Кассини-Гюйгенс: жертва ради жизни" (Russian)
- "6 MINUTES AGO: Vera Rubin's First Images JUST STOPPED THE WORLD!" (English)
- "Dinosaur Saves the Car… Henry's Mission Is Complete!" (off-topic, dinosaur)

---

## 4. Verdict: NO supported pattern — noise

**No title/thumbnail pattern is supported by the data.** The breakout sample is too small (n=5) to draw statistical conclusions, and pattern rates are nearly identical between breakouts and non-breakouts:
- Curiosity keywords: 20% breakouts vs 16% non-breakouts
- Digit use: 40% vs 25% (driven by 2 Spanish titles with "UN AÑO")
- Caps runs: 20% vs 40% (breakouts actually use FEWER caps)

The single English on-topic breakout ("6 MINUTES AGO: Vera Rubin's First Images...") uses recency ("6 MINUTES AGO") + caps + exclamation, but n=1 cannot establish a pattern. 3 of 5 breakouts are non-English; 1 is off-topic.

**Thumbnail text:** not inspectable via API (URL only). No claim made about thumbnail text or visual design.

---

## 5. Sample sizes

- Titles analyzed: 280 (MEASURED)
- Breakouts: 5 (MEASURED) — too small for pattern inference
- Non-breakouts: 275 (MEASURED)

---

## 6. Files

- `reports/t4-thumbnail-title-patterns.csv` — 280 rows with title length, pattern flags, breakout flag, thumbnail-text-availability note
