# ISS — Footage Inventory (Milestone W2)

**Source:** NASA Image & Video Library, `NHQ_2019_0626 "Earth Views from the ISS"` (HQ, 2019-06-26).  
**Rights:** source_policy_us_gov (NASA public domain). metadata.json: Creator=None, no copyright/license/NC/ND field, 1280x720 HD, 44:00 duration. Third-party credit: none. Creator=None → NASA-produced.  
**Derivative used:** ~medium.mp4 (776 MB, 1280x720, h.264, 2.48 Mbps).  
**Cap:** 800 MB — single download, 776 MB, under cap.

| asset_id | kind | file | source_url | duration_seconds | resolution | rights_basis | credit_line | third_party_credit | sha256 |
|---|---|---|---|---|---|---|---|---|---|
| iss_earth_views | footage | projects/slice_iss/footage/iss_earth_views_medium.mp4 | https://images-api.nasa.gov/search?q=ISS%20Earth%20view&media_type=video (item NHQ_2019_0626) | 2640.13 | 1280x720 | source_policy_us_gov | NASA Image & Video Library (NHQ_2019_0626) | none | 248b111940d65e4968950702206d6636eda8e2890f9c29dacdf0ea5e7416c0a5 |
| step_inside_station | footage | projects/slice_iss/footage/step_inside_4k_clean_medium.mp4 | https://images-api.nasa.gov/search?q=international%20space%20station%20orbit%20earth&media_type=video (item Step_Inside_the_Station-4K-Clean) | 896.83 | 1080x608 | source_policy_us_gov | NASA Image & Video Library (Step_Inside_the_Station-4K-Clean, JSC) | none | 19c4c9ee785953bf... |

**New downloads this session:** step_inside_4k_clean_medium.mp4 (266 MB). Total new downloads ~266 MB, under the 1.5 GB cap.
**Scene cuts:** 25 scenes cut from iss_earth_views_medium.mp4 into projects/slice_iss/scenes/scn_01..scn_25.mp4 (1280x720). Watermark/emblem crop applied (top 50px + bottom 90px removed, scaled back to 1280x720; zoom scenes use center 1100x520 crop). Full per-scene sha256 in projects/slice_iss/scenes/scenes_manifest.json and documented in edit_decisions.json (watermark_crop + scene_cuts). Speed variation not applied (ffmpeg setpts hangs on this build); all scenes at 1.0x.
**Derived scenes:** scn_01..scn_25, see edit_decisions.json scene_cuts for per-scene sha256/bytes/crop_mode/start.

**Notes:** archive.org `iss cupola earth view` and `international space station earth view` searches returned 0 items. NASA API returned 13 items; NHQ_2019_0626 is the only dedicated Earth-view footage. All footage segments in this build are drawn from this single asset via time-segment trims (no re-download). step_inside_station added as a second HD source (station interior tour).
