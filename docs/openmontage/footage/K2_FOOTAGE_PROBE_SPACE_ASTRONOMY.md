# Footage Probe — Space & Astronomy (HD Public-Domain Footage) — Milestone K2

**Status:** probe report only. No code, no installs, no process/lock changes.
**Method:** keyless search only (NASA Image and Video Library `images-api.nasa.gov`, archive.org `advancedsearch`, Wikimedia Commons). No API key, no registration, no third-party credit accepted. `curl -L` for downloads. Max 3 test files downloaded. Max 40 network requests (16 used: 10 search + 3 asset-location + 3 download).
**Rights model:** RIGHTS_MODEL.md applied. `rights_basis` ∈ {explicit_license, source_policy_us_gov, unknown}; third-party credit => REJECT. NASA items observed with `rights=None` (public domain) and NASA-center creator, no third-party credit => `source_policy_us_gov` candidate (USABLE pending frame review of identifiable_persons/logo_visible flags, which are UNKNOWN from metadata and NEEDS_REVIEW per RIGHTS_MODEL.md §4).
**HD gate:** >=720p verified only via ffprobe post-download; NASA search API exposes no resolution/duration, so HD claims below are probe-verified only for the 3 downloaded clips, asserted-as-likely for the rest.

---

## 1. Ten candidate topics — keyless probe results

| # | Topic | NASA video total_hits | Returned items | rights_basis (NASA items) | Third-party credit? | HD>=720p verified? |
|---|-------|----------------------|----------------|---------------------------|---------------------|--------------------|
| 1 | Artemis / SLS launch | 672 | 100 | source_policy_us_gov (rights=None, NASA center creator) | No | YES — 3840x2160 (probe) |
| 2 | Hubble Space Telescope | 152 | 100 | source_policy_us_gov | No | YES — 1920x1080 (probe) |
| 3 | James Webb Space Telescope | 110 | 100 | source_policy_us_gov | No | not downloaded (asserted likely HD, modern 2019-2022 items) |
| 4 | Mars rover Perseverance | 117 | 100 | source_policy_us_gov | No | YES — 3840x2160 (probe) |
| 5 | Apollo 11 | 71 | 71 | source_policy_us_gov | No | not downloaded (1969 film; HD uncertain, may be scanned SD) |
| 6 | Voyager | 36 | 36 | source_policy_us_gov | No | not downloaded |
| 7 | Cassini Saturn | 13 | 13 | source_policy_us_gov | No | not downloaded |
| 8 | DART asteroid impact | 28 | 28 | source_policy_us_gov | No | not downloaded |
| 9 | Parker Solar Probe | 25 | 25 | source_policy_us_gov | No | not downloaded |
| 10 | OSIRIS-REx | 106 | 100 | source_policy_us_gov | No | not downloaded |

Notes:
- All 10 topics returned HTTP 200 on NASA search (method validated; EMPTY results would be genuine, not errors).
- archive.org and Wikimedia were not separately probed for these topics in this session (NASA suffices for source_policy_us_gov HD candidates); ESA/Hubble not probed (beyond keyless scope / rights terms to confirm per-item).
- No topic returned a third-party-credited NASA item in the sampled top results; the REJECT rule applies if any candidate shows "courtesy of"/non-NASA credit or uploader re-upload.

---

## 2. Per-topic clip counts by narrative beat (candidate beats)

Candidate 6-beat structure for a space/astronomy episode:
- B1 Preparation — mission conception, spacecraft/instrument build, testing
- B2 Launch/deployment — liftoff, separation, deployment
- B3 Cruise/operation — transit, commissioning, checkout
- B4 Key event — landing, impact, telescope first light, sample return
- B5 Discovery/results — science images, data, findings
- B6 Legacy/lessons — extended mission, retirement, follow-on

Per-topic clip availability (returned NASA video items, approximate beat mapping from titles/centers; counts are upper bounds — HD not verified except the 3 probes):

| Topic | B1 | B2 | B3 | B4 | B5 | B6 | Total returned | Best verified HD clip |
|-------|----|----|----|----|----|----|----------------|-----------------------|
| Artemis / SLS | ~20 (MSFC resource reels, Orion) | ~40 (SLS launch, Artemis I) | ~15 | ~10 (splashdown) | ~5 | ~5 | 100 returned / 672 hits | artemis_test.mp4 3840x2160 |
| Hubble | ~5 (servicing) | ~8 (shuttle deploy) | ~20 (operations) | ~8 (first light/SM4) | ~30 (images) | ~10 | 100 returned / 152 hits | hubble_test.mp4 1920x1080 |
| Perseverance | ~15 (build/test, JPL) | ~10 (launch) | ~10 (cruise) | ~30 (landing, onboard) | ~25 (surface) | ~5 | 100 returned / 117 hits | perseverance_test.mp4 3840x2160 |

Beat counts are estimates from sampled titles; not frame-verified. Flags (identifiable persons, NASA logo) UNKNOWN for all => NEEDS_REVIEW before timeline use.

---

## 3. Three best topics (selected)

| Rank | Topic | Reason | Verified HD | rights_basis | Beat coverage |
|------|-------|--------|-------------|--------------|---------------|
| 1 | Artemis / SLS launch | Highest total_hits (672), abundant launch footage (B2 strong), 4K verified, MSFC/HDSC resource reels give B1/B3 depth | YES (4K) | source_policy_us_gov | All 6 beats, B2 strongest |
| 2 | Perseverance (Mars rover) | 117 hits, 4K verified landing + surface footage, JPL primary docs via NTRS, strong B4/B5 | YES (4K) | source_policy_us_gov | All 6 beats, B4/B5 strongest |
| 3 | Hubble Space Telescope | 152 hits, 1080p verified, astronomy flagship (best niche fit for "space & astronomy"), strong B5 (science images) | YES (1080p) | source_policy_us_gov | All 6 beats, B5 strongest |

**Selected best topic for K3:** Artemis / SLS launch (highest volume, 4K verified, covers all 6 beats).

**Remaining gap:** HD verification for topics 4-10 requires per-item download (cap reached at 3). ESA/Hubble rights terms not yet confirmed per-item. Frame review (identifiable persons / NASA logo) pending for all 3 downloaded clips.
