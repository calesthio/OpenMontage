# Footage Source Registry — OpenMontage MASTER RUN P5

**Status:** docs only. Source registry + keyless probe results. No code written to adapters yet (P5 is docs/probes only; adapter authoring is a follow-up).
**Probe method:** one small keyless search query per source, 20s timeout each, no media downloads. ERROR/HTTP/EMPTY recorded as separate states.
**Probe date:** 2026-10-17.

## Source registry

One row per source. `adapter` = existing `tools/video/stock_sources/<name>.py` path or `MISSING` (no adapter yet — worth writing if keyless + clear rights policy). `rights_basis` = default classification under RIGHTS_MODEL.md rules.

| # | Source | Root URL | Content type | Search method | rights_basis (default) | Attribution required | Adapter | Probe result |
|---|---|---|---|---|---|---|---|---|
| 1 | NASA Image and Video Library | https://images-api.nasa.gov | video + image | API keyless (`q=`, `media_type=`) | source_policy_us_gov | NASA credit requested; insignia/persons exceptions apply | tools/video/stock_sources/nasa.py (EXISTS) | WORKS — 1621 hits for "rocket"; rights=None (NASA public domain), center/date_created/description/keywords exposed |
| 2 | NASA SVS (Scientific Visualization Studio) | https://svs.gsfc.nasa.gov | video + image | web/API | source_policy_us_gov | NASA credit requested | MISSING | not probed (beyond P5 scope) |
| 3 | Internet Archive (Moving Image / Prelinger / stock_footage) | https://archive.org | video + image | API keyless (`advancedsearch.php`) | source_policy_us_gov / explicit_license (per-item licenseurl/rights vary) | per-item license | tools/video/stock_sources/archive_org.py (EXISTS) | WORKS — returns docs with identifier/title/date/creator/licenseurl/rights; licenseurl=None typically |
| 4 | Library of Congress (free-to-use) | https://www.loc.gov/ | video + image | API | source_policy_us_gov / per-item | per-item | tools/video/stock_sources/loc.py (EXISTS) | BLOCKED — Cloudflare bot protection ("Just a moment..."), no keyless JSON |
| 5 | US National Archives (NARA catalog) | https://catalog.archives.gov | video + image | API key required | source_policy_us_gov | per-item | tools/video/stock_sources/nara.py (EXISTS) | BLOCKED — catalog.archives.gov/api/v1/ requires API key; www.archives.gov 302 |
| 6 | DVIDS (Defense Visual Information Distribution Service) | https://www.dvidshub.net | video + image | API key / registration required | source_policy_us_gov | DoD credit | MISSING | BLOCKED — returns HTML, no simple keyless JSON API |
| 7 | Wikimedia Commons | https://commons.wikimedia.org | video + image | API keyless (`action=query&list=search`) | explicit_license (per-file license tag) | yes (per license) | tools/video/stock_sources/wikimedia.py (EXISTS) | WORKS — 5 results for "rocket" in File namespace; title+snippet returned |
| 8 | Open Beelden (Netherlands) | https://openbeelden.nl | video | API/web | source_policy_us_gov | per-item | MISSING | not probed |
| 9 | Europeana | https://www.europeana.eu | video + image | API key required | per-item | per-item | MISSING | not probed |
| 10 | Smithsonian Open Access | https://smithsonian.edu | video + image | API keyless | source_policy_us_gov / CC0 | per-item | MISSING | not probed |
| 11 | NPS B-roll (National Park Service) | https://www.nps.gov | video | web | source_policy_us_gov | NPS credit | MISSING | not probed |
| 12 | CDC B-roll | https://www.cdc.gov | video | web | source_policy_us_gov | CDC credit | MISSING | not probed |
| 13 | Vimeo CC | https://vimeo.com | video | API key required | explicit_license (CC) | yes | MISSING | not probed |
| 14 | Pexels | https://www.pexels.com | video | API key required | explicit_license (Pexels license) | attribution requested | tools/video/stock_sources/pexels.py (EXISTS) | not probed (key required) |
| 15 | Pixabay | https://pixabay.com | video + image | API key required | explicit_license (Pixabay license) | no attribution required | tools/video/stock_sources/pixabay_video.py (EXISTS) | not probed (key required) |
| 16 | Mixkit | https://mixkit.co | video | web/API | explicit_license (Mixkit license) | no attribution required | tools/video/stock_sources/mixkit.py (EXISTS) | not probed |
| 17 | Coverr | https://coverr.co | video | web | explicit_license | attribution requested | tools/video/stock_sources/coverr.py (EXISTS) | not probed |
| 18 | Videezy | https://www.videezy.com | video | web | explicit_license | attribution requested | MISSING | not probed |
| 19 | Pond5 Public Domain Project | https://www.pond5.com | video | web | explicit_license (public domain) | no | tools/video/stock_sources/pond5_pd.py (EXISTS) | not probed |

## Probe results detail (P5 step: keyless search, max 30 requests)

| Source | Query used | HTTP status | Result | Key required? | Rights/credit fields exposed |
|---|---|---|---|---|---|
| NASA images-api | `q=rocket&media_type=video&page_size=5` | 200 | WORKS — 1621 total_hits; sample items returned with nasa_id/title/center/rights | No (`DEMO_KEY` path works; optional NASA_API_KEY raises limits) | rights (None = public domain), center, date_created, description, keywords, photographer, secondary_creator |
| Internet Archive | `q=rocket AND mediatype:movies&rows=5&output=json` | 200 | WORKS — docs returned with identifier/title/date/creator/licenseurl/rights | No | licenseurl (None typically), rights (None typically), creator, description |
| Wikimedia Commons | `srsearch=rocket&srnamespace=6&srlimit=5` | 200 | WORKS — 5 File: results with title+snippet | No | license tag per file (via separate imageinfo call) |
| Library of Congress | `q=rocket&c=5&fo=json` | 200 (HTML) | BLOCKED — Cloudflare "Just a moment..." bot page, no JSON | N/A (blocked) | N/A |
| NARA catalog | `search=rocket&rows=5` (catalog.archives.gov/api/v1/) | 200 (HTML) | BLOCKED — requires API key; www.archives.gov 302 | Yes | N/A |
| DVIDS | `search=rocket` (dvidshub.net) | 200 (HTML) | BLOCKED — returns HTML, no simple keyless JSON API | Yes (registration) | N/A |

## Rights/credit field exposure summary (keyless sources)

| Source | rights/license field | credit/creator field | date field | duration/dimensions |
|---|---|---|---|---|
| NASA | `rights` (None=public domain) | `photographer`/`center`/`secondary_creator` | `date_created` | duration=0, width/height=0 (probe post-download) |
| Internet Archive | `licenseurl`/`rights` (None typically) | `creator` | `date` | probe post-download |
| Wikimedia Commons | license tag (separate `imageinfo` call) | uploader/author (separate call) | date (separate call) | probe post-download |

## MISSING adapters worth writing (keyless + clear rights policy)

These sources lack an adapter in `tools/video/stock_sources/` and are worth authoring if they have a clear rights policy and (ideally) keyless access:

1. **NASA SVS** (svs.gsfc.nasa.gov) — NASA SVS is public domain, keyless web/API; high-value Earth/space visualisation. High priority.
2. **Open Beelden** (openbeelden.nl) — Dutch open video, clear rights; keyless web. Medium priority.
3. **Europeana** — requires API key (lower priority unless key obtained).
4. **Smithsonian Open Access** — CC0/public domain, keyless API; high value. Medium priority.
5. **NPS B-roll** — US National Park Service, public domain; keyless web. Medium priority.
6. **CDC B-roll** — US CDC, public domain; keyless web. Medium priority.
7. **Vimeo CC** — requires API key (lower priority).
8. **Videezy** — explicit license, attribution required; keyless web. Lower priority.
9. **DVIDS** — DoD footage, public domain, but requires registration/API key (blocked for keyless; lower priority).

Sources NOT worth writing adapters for (blocked/key-required, no clear keyless path): Library of Congress (Cloudflare), NARA (API key), Vimeo CC (API key), Europeana (API key).

## Adapter protocol (for future authors)

Every new adapter goes in `tools/video/stock_sources/<name>.py` and satisfies the `StockSource` protocol (see `tools/video/stock_sources/base.py`):
- `name` (stable key), `display_name`, `provider`, `priority`, `supports` ({video, image})
- `is_available()` — cheap non-network check
- `search(query, filters)` → list[Candidate]
- `download(candidate, out_path)` → Path

`Candidate` fields: source, source_id, source_url, download_url, kind, width, height, duration, creator, license, source_tags, thumbnail_url, extra.

## Notes

- Pexels/Pixabay/Mixkit/Coverr/Videezy/Pond5 adapters already exist but were not probed (key required or web-only). Their redistribution limits/monetized-video use should be confirmed against each source's official license page before use in a monetized video.
- "source_policy_us_gov" applies to US government sources (NASA, NARA, DVIDS, NPS, CDC, Smithsonian) where the item is US-government-produced with no third-party credit/restriction — per RIGHTS_MODEL.md §3.
- Wikimedia Commons and most creative sources use `explicit_license` (per-item license tag), requiring per-item rights verification.
