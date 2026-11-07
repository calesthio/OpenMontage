---
description: Methodology for researching faceless YouTube niches with the niche-finder MCP server — which of the 100 tools to call, in what order, with quota discipline, the 100-point scoring rubric, and evidence standards. Use when asked to find/compare YouTube niches, analyze small-channel outliers, or plan 8–15-minute faceless videos.
---

# YouTube niche research — methodology

## 0. Start here (always)

```json
// via the niche-finder MCP tools:
db_stats();
```

 decides the mode:

| `db_stats` result | Mode |
|---|---|
| `videos == 0` and `search_calls_left_today > 0` | **Cold start** — collection tools need `YOUTUBE_API_KEY`; if it's absent, do web-sourced research and mark the report `MODE: web-only` |
| `videos > 0`, niches exist | **Live mode** — query collected data first, spend search only for gaps |
| `search_calls_left_today == 0` | **Read-only** — search list is bucket-limited to 100/day |

## 1. Tool ordering per research topic (Live mode)

1. `list_niches` / `niche_map` — what's already known locally.
2. For a niche slug: `niche_overview`-style read tools; `find_viral_videos`
   for outlier hits; `video_velocity` for acceleration.
3. `policy_signals` / `niche_policy_signals` — count of channels showing
   reused/template/red flags; feeds the "policy risk" rubric line.
4. `track_channel` the 5–10 exemplars you cite in the report (RSS watch is
   free, keeps history growing without quota).
5. Only then `collect_niche` for a genuinely new topic (1 `search.list`
   call per topic, ≤5 topics/day is a sane budget).

## 2. What to verify for each niche candidate

- **Demand**: period views (24h/7d/30d/90d), velocity, evergreen vs decay.
- **Competition**: sub-count distribution of top channels serving the same
  query; share of faceless incumbents; per-video median views.
- **Small-channel probability**: recent videos from channels < 50k subs
  with ≥10× the channel median (the tool's outlier score).
- **Production fit**: truly faceless; AI narration acceptable; visual
  assets are free/license-safe (public domain, CC0, own charts/maps);
  is 8–15 min the native length or are winners 2h+ broadcasts?
- **Monetization**: RPM band (ranges, not invented point values), ad
  relevance (advertiser demand), sponsors/affiliate potential.
- **Policy risk**: reused-content exposure, YMYL, QoE (kids), music
  Content-ID, "inauthentic content" (July 15, 2025 policy).

## 3. Scoring rubric (100 points)

- Confirmed demand — 20
- Gaps for a small/new channel — 20
- Monetization/ad attractiveness — 15
- Durability 6–12 months — 10
- Series/serializable formats — 10
- Production simplicity & cost — 10
- Language/market advantage — 5
- Policy safety & originality room — 10

Confidence labels per niche: HIGH (local API data + primary policy pages),
MEDIUM (primary sources, no local data), LOW (secondary/blog claims only).

## 4. Evidence standards

- FACT = you observed it in tool output or a primary page you fetched (URL
  + date), ESTIMATE = derived with method stated, HYPOTHESIS = reasoned
  assumption to be tested with the first 10 videos, NOT_CHECKED/UNKNOWN =
  could not verify this session.
- RPM: never quote a point value without a source; prefer published ranges
  and say whose sample it comes from. YouTube publishes no RPM table.
- Never pass a marketing-blog claim ("$24K/month from 8.8k subs") off as
  data — label UNVERIFIED-sales-signal.

## 5. Deliverable conventions

Reports live in `reports/` of the research repo:

- `niche-research.md` — methodology + per-niche evidence dossier.
- `niche-comparison.csv` — scorecard CSV (numeric columns only for CSV
  fields, so it can be plotted).
- `winning-niche.md` — the winner + runner-ups + first-30-videos plan.
- `setup-report.md` — environment/infra results, diagnostics, blockers.

Any plan written before live data exists must carry: "MODEL: web-evidence
plan; re-score after first 5–10 collected videos via niche-finder tools."
