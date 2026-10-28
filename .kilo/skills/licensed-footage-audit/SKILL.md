---
name: licensed-footage-audit
description: Use whenever finding, importing, downloading, selecting, transforming or publishing video footage, audio, images, music, fonts or other media assets for YouTube. Mandatory for stock-footage pipelines and rights/provenance checks.
---

# Asset rights and provenance

## Allowed asset sources
Use user-owned material, public-domain material, or a source with explicit license terms that cover the planned use. Confirm whether commercial use, editing, redistribution, attribution and YouTube monetization are allowed.

## Required asset record
For each asset store:
- asset_id and local path
- source URL and creator/rights holder
- exact license name and terms URL
- access/retrieval date (UTC)
- commercial-use status and modification status
- attribution text and required notices
- checksum (SHA-256) and media metadata
- review status: VERIFIED / HUMAN_REVIEW / REJECTED
- evidence path (saved license page/screenshot/receipt when legally permitted)

## Rules
- Never infer rights from a search snippet or "free" label.
- Never use YouTube, TikTok or other creator uploads as stock without documented permission.
- Do not bypass DRM, paywalls, private links, cookies, authentication or site restrictions.
- Do not remove watermarks or metadata intended to identify ownership.
- If license text cannot be checked or commercial rights are ambiguous, quarantine and ask for review.
- Re-check license conditions when asset source or planned use changes.
- Keep music, sound effects, fonts, images and video on the same provenance ledger.
- Provide attribution in the final description where required.
