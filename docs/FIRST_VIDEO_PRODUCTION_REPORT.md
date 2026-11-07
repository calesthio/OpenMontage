# First Video Production Report

## Deliverable
- Final MP4: `projects/pilot/first_video/final.mp4`
- Preview MP4: `projects/pilot/first_video/preview.mp4`
- Contact sheet: `projects/pilot/first_video/qc/visual_review_contact_sheet.jpg`
- QC report: `projects/pilot/first_video/qc/final_qc_report.json`

## Media facts
- Duration: 174.371 s
- Resolution: 1920x1080, 16:9
- Frame rate: 30 fps
- Video codec: H.264 (h264)
- Audio codec: AAC
- File size: 52211001 bytes (~49.8 MB)

## Content
- Script slice: S001-S041 (41 sentences)
- Images: 41 scene images in `projects/pilot/first_video/images/` (one per sentence)
- Composed/rig scenes: 11 in `projects/pilot/first_video/images/composed/`
- Stickman rig overlays: 11 PNGs in `projects/pilot/first_video/character/`
- Voice: Kokoro-82M, voice `af_heart`
- Image model: FLUX.2 Klein 4B (existing pilot assets)

## QC result
Core technical QC: PASS (6/6 core checks: ffprobe streams, full decode, blackdetect, freezedetect, silencedetect, ebur128).
Optional checks NOT_RUN due to missing inputs: duration_vs_script, subtitle_sync, credits_complete, claim_ids, claim_ids_resolve, rights_basis, added_value, ai_illustration_label, motion_variety.

## Flow credits
- Current balance checked via gflow MCP: 50 credits (profile `flow_remote`).
- No generation was performed in this delivery step; spend ledger for earlier pilot generation is not present in this workspace snapshot.

## Tests
- `tests/test_flow_job_manager.py`: 25 passed, 1 failed (pre-existing missing fixture `jobs/demo_jobs.json`, unrelated to this delivery).

## Limitations
- Optional QC checks remain NOT_RUN because supporting manifests/ledgers were not wired into this QC invocation.
- Music bed: no music file was added in this step (`assets/music/` remains empty per prior state).
- Publication not performed; title/description/tags/thumbnail remain draft-only.
