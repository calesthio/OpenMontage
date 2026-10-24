# Footage Quality Findings — CID Slice F5 (moving footage + stills + Kokoro narration)

**Status:** docs only. No media committed (media lives in gitignored projects/slice_cid_v0/).

## 1. Findings — archive CID video

All CID video available via the archive.org NIX collection is 320x240 h.264 (best derivative, not the ~512kb variant):

| archive.org item | derivative | resolution | size | sha256 | role in F5 |
|---|---|---|---|---|---|
| NIX-EM-0004-01 | EM-0004-01.mp4 | 320x240 | 3,052,294 B | 13d2a7e4... | S1 approach insert (6.0-13.2s motion) |
| NIX-LV-1998-00090 | LV-1998-00090.mp4 | 320x240 | 1,740,303 B | ae128d36... | S6 impact insert (8.0-13.5s motion) |
| NIX-LV-1998-00092 | LV-1998-00092.mp4 | 320x240 | 1,252,468 B | abbd001b... | S7 fireball insert (0.0-4.2s motion) |

archive.org advancedsearch surfaced additional CID items but:
- NIX-ECN-* and NIX-EC84-* are still photos (JPEG only, no video).
- NIX-EM-0004-02, NIX-LV-1998-00091/00093/00096/00098 are also 320x240 video.

**No higher-resolution (>640x480) CID video source was found.** archive.org metadata was re-read (not guessed) for every item; the h.264 mp4 is the best derivative in each case.

NASA images API (images.nasa.gov) search for "Controlled Impact Demonstration" returned the web application (HTML), not a usable JSON candidate list; no additional video candidates retrieved.

## 2. Findings — NASA Armstrong still photos

Official NASA stills are max ~1040x816 (highest-resolution derivative available on nasa.gov image gallery).

NASA Armstrong CID image gallery (https://www.nasa.gov/centers/armstrong/multimedia/imagegallery/CID/index.html) and linked item pages list 7 image-detail pages; 5 unique CID photos (2 pages are a generic duplicate):

| NASA id | title | max resolution | source_url |
|---|---|---|---|
| ECN-31803 | Initial Impact of Controlled Impact Demonstration | 1040x816 | image-detail/initial-impact-of-controlled-impact-demonstration |
| ECN-31808 | Remotely Flown Boeing 720 Erupts After Impact | 1040x816 | image-detail/remotely-flown-boeing-720-erupts-after-impact |
| EC84-3167-A | Practice Run Before Controlled Impact Demonstration | 1040x672 | image-detail/practice-run-before-controlled-impact-demonstration |
| EC84-31809 | Boeing 720 Engulfed After Striking Wing Cutter | 1040x704 | image-detail/boeing-720-engulfed-after-striking-wing-cutter |
| ECN-28307 | Crash-Test Dummies Aid in Anti-Misting Kerosene Experiment | 1040x832 | image-detail/crash-test-dummies-aid-anti-misting-kerosene-experiment |

All 5 are NASA-produced (source_policy_us_gov), no third-party credit on the nasa.gov pages. Downloaded highest-res derivative of each (5/5), recorded sha256 and resolution in projects/slice_cid_v0/rights_records.json.

Caption-only flags (owner reviews pixels):
- identifiable_persons: none (ECN-28307 shows crash-test dummies, not real persons).
- logo_visible: none noted in captions.

## 3. F5 slice design

- Stills as primary visuals for preparation/context: slow zoompan (max 1.15x), 1080p, letterboxed on dark background, no stretch, no upscaling beyond source.
- Archive video inserts (4-8s each) in 2x framed layout (640x480 centered, thin frame, source card): clip01 (NIX-EM-0004-01 approach), clip02 (NIX-LV-1998-00090 impact), clip03 (NIX-LV-1998-00092 fireball). Moving footage used for approach/impact/fireball beats; static title cards at source heads trimmed.
- 2 original graphics cards: "Flight Path & Timeline" and "Key Numbers (claim_ids)" with claim_ids shown.
- Narration: Kokoro-82M (af_heart), S1-S7 only (S8 BLOCKED), ~46s, finish_audio applied.
- Archive-clip audio muted; narration laid over all visuals.
- Added-value gate: original graphics ≈ 17% (~8s of ~46s), archive video inserts ≈ 37% (~17s), stills ≈ 46% (~21s).
- Final F5 slice: 46.0s, 1920x1080, h264/aac, 30fps (gitignored, not committed).

## 4. QC result (thresholds NOT changed)

| check | status | note |
|---|---|---|
| ffprobe_streams | PASS | video+audio streams present, 1920x1080@30fps |
| full_decode | PASS | full decode, no errors |
| blackdetect | PASS | black ratio 0.0000 <= 0.05 |
| freezedetect | REVIEW | freeze(s) 17.60-20.67s, 41.17-45.17s within static_by_design segment(s); max 4.00s > 2.0s — static title cards, intentional |
| silencedetect | PASS | silence ratio 0.0000 <= 0.1 |
| ebur128 | PASS | I=-15.3 LUFS (target -14.0 +/- 2.0); TP=-4.3 dBTP (max -1.5) |
| duration_vs_script | PASS | duration 46.00s vs script 46.0s (drift 0.00s <= 1.0s) |
| subtitle_sync | PASS | last cue ends 44.70s <= audio 46.00s (+0.5s tolerance) |
| credits_complete | PASS | all required credit fields present |
| claim_ids | PASS | 9/9 sentences have claim_id |
| rights_basis | PASS | 9/9 clips have valid rights_basis |
| added_value | PASS | no unannotated clips > 20s |

Overall: PASS (freezedetect REVIEW on static title cards declared static_by_design; not a footage defect).

## 5. Draft email — request for higher-quality CID film/video

To: ARC-DL-archives@mail.nasa.gov
Subject: Request for higher-quality digitized copies of Controlled Impact Demonstration (CID) film/video (Boeing 720, 1 Dec 1984)

Dear NASA Armstrong Digital Assets Library,

I am producing a YouTube documentary channel technical slice about the NASA Controlled Impact Demonstration (CID) of the remotely piloted Boeing 720 (1 December 1984) at Edwards Air Force Base — this is for a YouTube documentary channel (monetization possible).

The best-quality CID video I have been able to locate online (archive.org NIX collection, e.g. items NIX-EM-0004-01, NIX-LV-1998-00090, NIX-LV-1998-00092) is 320x240 resolution. The NASA Armstrong CID image gallery holds higher-resolution still photographs (up to ~1040x833), but I have not located a digitized CID film/video source above 320x240.

I am writing to ask whether NASA Armstrong can provide, or point me to, higher-quality digitized copies of the CID film/video (original film, MPEG-2, or larger MP4 derivatives), suitable for a YouTube documentary retrospective. I am happy to provide attribution per NASA media guidelines.

No claim is made herein about the existence or availability of such material; this is solely a request.

Thank you,
[owner name]
OpenMontage Factory

## 6. AI-upscaling option (4th component)

**Status: NEEDS OWNER APPROVAL — do not proceed without sign-off.**

Option: apply AI upscaling (e.g. Real-ESRGAN or similar) to the 320x240 archive CID video to raise it toward 720p/1080p before inserting into the slice.

Considerations:
- This is an AI/ML-based upscale, not a native high-resolution source; it synthesizes detail and does not recover information absent from the 320x240 master.
- Requires model downloads and GPU/CPU inference; no AI upscaling tool is currently installed in this pipeline.
- Would change the footage from its archival form; rights/attribution remain source_policy_us_gov (NASA) but the upscaled pixels are derivative.
- Must not be applied without explicit owner approval (this is the 4th component: stills, archive inserts, original graphics, AI-upscale).

Decision needed: owner to approve or decline AI upscaling of the 320x240 CID archive video before any model download or processing.

## Records

- projects/slice_cid_v0/rights_records.json — per-asset rights, sha256, resolution, source URL, role, caption-only flags.
- projects/slice_cid_v0/credits.txt — full credit text.
- projects/slice_cid_v0/qa_report.json — QC results (gitignored, not committed).
