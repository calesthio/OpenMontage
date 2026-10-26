---
description: DEPRECATED — merged into evidence-checker. Use evidence-checker for combined claims/source/license verification.
mode: subagent
permission:
  read: allow
  edit: deny
  glob: allow
  grep: allow
  bash: deny
  todowrite: allow
  webfetch: deny
  websearch: deny
  task: deny
  lsp: deny
  skill: deny
---

# license-checker — DEPRECATED (merged into evidence-checker)

This agent has been merged into `evidence-checker`, which now covers both
claims/source verification and repository/model-card license checking.

Use `@evidence-checker` for all fact/license verification work. This file is
kept only as a compatibility stub so any existing references to
`license-checker` resolve to a notice rather than a missing agent.

License-checking rules (now enforced by evidence-checker):
- Every dependency must resolve to an exact project name on PyPI/Hugging Face; no fuzzy matching.
- Record each license with source URL and retrieval date.
- If license is unclear → quarantine and flag for human review.
- Hard exclusions: insightface / ArcFace / antelopev2 / buffalo_l,
  InstantID, IP-Adapter-FaceID, PuLID, ConsiStory, StoryDiffusion,
  Z-Image-Turbo, FLUX (non-commercial).
