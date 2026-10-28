# OpenMontage Factory — target state

Generated during KILO_CODE_YOUTUBE_FACTORY_MASTER.md bootstrap (2026-10-17).

## Goal
A reliable, maintainable, low-cost YouTube video production pipeline with staged, resumable, licensed and human-approved workflows.

## Stages
idea → research → outline/script → fact-check → asset plan → asset/license verification → edit decision list → render → technical QA → human review → upload preparation → human-approved publish → analytics → experiment

## Required artifacts per job
- `projects/<job-id>/script/script.md`
- `projects/<job-id>/assets/asset-rights-ledger.csv`
- `projects/<job-id>/timeline/edl.json`
- `projects/<job-id>/output/review.mp4`
- `projects/<job-id>/reports/qa.json`
- `projects/<job-id>/checkpoint_*.json`

## Verification criteria
- Every asset has VERIFIED rights record (source URL, creator, license, SHA-256)
- FFmpeg/ffprobe render passes all quality-gate checks (PASS/NOT_CHECKED, never unverified PASS)
- No public upload without explicit human approval
- All 9 Skills discoverable with correct frontmatter
- Global AGENTS.md preserves existing instructions + merged YouTube Factory rules

## Next milestone
First vertical slice: one local MP4 from user-owned/public-domain assets, through research → script → license ledger → EDL → FFmpeg render → QA report → human review.
