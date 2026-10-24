---
name: youtube-quality-gate
description: Use before declaring any generated video, Short, thumbnail, narration, subtitles, render pipeline or production job ready for review or publication.
---

# Technical and editorial QA

## Technical checks
- file exists, non-zero size and decodes;
- duration, dimensions, frame rate, codec, pixel format and audio streams match the target profile;
- inspect audio peaks/loudness and check clipping, silence and channel mismatch;
- detect unexpected black frames, frozen frames, missing clips and gaps;
- compare captions/subtitles against the final narration and timing;
- verify thumbnail dimensions, readability and image rights;
- verify final media checksums and job manifest.

## Editorial checks
- every factual claim has a source or is marked opinion/estimate;
- title and thumbnail match the actual video;
- no misleading promises, fabricated citations or synthetic evidence;
- asset rights ledger is complete and all assets are VERIFIED;
- description includes required attributions and disclosures;
- generated/synthetic content disclosures are evaluated against current platform rules.

## Report format
For each check use PASS, FAIL, or NOT_CHECKED with evidence and a brief explanation. Never mark a check PASS without running it. Block publication if a required check fails or asset rights are unresolved. Human review is still required before public publication.
