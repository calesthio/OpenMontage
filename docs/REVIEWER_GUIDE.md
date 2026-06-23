# OpenMontage Reviewer Guide

OpenMontage is actively seeking reviewers with hands-on AI video production experience.
This guide helps prospective reviewers understand where their expertise is most valuable.

## Why reviewers matter

Reviewers help keep OpenMontage production-ready by catching issues that are easy to miss in code-only reviews:

- provider quality regressions and hidden cost changes
- runtime or render workflow drift
- fragile provider assumptions and unsafe fallback behavior
- poor defaults that hurt creator experience
- gaps in the pipeline contract or auditability

## What reviewers can help with

Reviewers are most helpful on PRs that touch:

- video generation providers and selector logic
- composition runtimes, Remotion/HyperFrames render workflows, or FFmpeg output paths
- pipeline stage behavior, checkpointing, and approval flow
- prompting guidance, pipeline-directed prompts, and creator-facing docs
- provider/security docs and `.env`/API key handling

## Ideal background

Helpful experience includes any of:

- shipping videos with Seedance, Kling, Veo, Runway, LTX, Wan, HeyGen, or similar systems
- building video pipelines, render/composition systems, or post-production automation
- working with Remotion, FFmpeg, motion graphics, captions, audio mixing, or prompt-to-video workflows
- reviewing provider integrations for reliability, security, cost, and quality

## PRs you can review comfortably

Good review candidates for video experts include:

- provider integration or fallback changes
- render/runtime selection and composition workflow updates
- pipeline manifest and stage director changes
- prompting guidance and user-facing workflow docs
- cost or budget behavior changes
- quality/regression risk for production video output

## Areas where OpenMontage needs stronger direction

Reviewers can make the biggest impact by helping ensure that:

- provider selection remains explicit and auditable
- video production stays pipeline-driven instead of ad hoc
- render/runtime decisions are fully documented and traceable
- zero-key and paid paths are both well-supported
- output locations, checkpoint behavior, and approval gates are transparent to creators

## How to volunteer

If you want to help review PRs, please comment on the relevant issue, discussion, or PR with:

- the video generation / production tools you have used
- the kinds of PRs you are comfortable reviewing
- any areas where you think OpenMontage needs stronger technical direction

### Example volunteer comment

- Video generation / production tools I've used:
  - Seedance, Kling, Veo, Runway, Wan, local LTX/diffusion workflows
  - Remotion, FFmpeg, HyperFrames/GSAP, captions, audio mixing
  - prompt-based production pipelines and stock footage edit automation

- PRs I'm comfortable reviewing:
  - provider integrations and fallback behavior
  - render/runtime selection and composition workflow changes
  - pipeline stage and approval/checkpoint behavior
  - prompting guidance, style defaults, and creator-facing docs
  - cost, reliability, and quality regression risks

- Areas for stronger technical direction:
  - keep provider selection explicit rather than hidden behind implicit fallbacks
  - keep the pipeline contract central to production flow
  - improve fail-safe behavior for missing keys and flaky providers
  - document best zero-key vs paid-provider workflows clearly
  - make output and checkpoint behavior easy to find for new users
