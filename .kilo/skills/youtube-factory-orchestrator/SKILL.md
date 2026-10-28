---
name: youtube-factory-orchestrator
description: Use whenever planning, coding, debugging, extending or reviewing OpenMontage Factory or any automated YouTube video production pipeline. Coordinates specialist skills and enforces staged, resumable, licensed and human-approved workflows.
---

# YouTube Factory Orchestrator

1. Read project instructions and inspect the repository before proposing changes.
2. Explicitly load the relevant specialist Skills: research/script, footage rights, FFmpeg/rendering, QA, publishing/analytics, self-improvement.
3. Map the request to a pipeline stage and identify its input/output contracts.
4. Make a concise plan with files, tests, dependencies, rights/security implications and acceptance criteria.
5. Implement the smallest vertical slice; avoid broad rewrites.
6. Keep each job resumable and idempotent; use stable IDs, structured logs and manifests.
7. Use provider adapters rather than tightly coupling one asset source or renderer.
8. Never treat asset availability as a license. Route uncertain rights to human review.
9. Never publish or alter a live channel without explicit approval in the current task.
10. Finish with tests/results, skipped checks, risks and next step.

## Definition of done
A task is done only when acceptance criteria are tested or clearly marked NOT_CHECKED. Plans are not implementation. Mocked API tests are not proof of real API integration.
