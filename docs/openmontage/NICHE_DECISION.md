# Niche Decision — Aviation & Spaceflight Test History

**Date:** 2026-10-16
**Decision:** proceed with **"Aviation & spaceflight test history"** on free /
public-domain archive footage as the configured niche (`niche_profile.yaml`).
The niche is CONFIG, not hardcoded.

## Why this niche

- Strong fit with keyless archive adapters already in code (`nasa`, `nara`,
  `archive_org`, `wikimedia`, `loc`, `pond5_pd`).
- Primary documents exist as a class (NASA NTRS, FAA, NTSB) for evidence-first
  episodes.
- Archive-first material suits original narration + diagrams as the added value.

## Rejected niches with reasons

| Niche | Reason |
|-------|--------|
| Infrastructure | Rejected by owner. |
| Business / finance | Weak footage + YouTube AI-persona rule. |
| Celebrities | Rights / defamation risk. |

## UNKNOWNS (not verified, not assumed)

- Competition not measured.
- Monetization eligibility for the creator's country not verified.
- RPM only third-party estimates — no first-party data.

## What this decision does NOT claim

- No claim that 10 licensable clips + 3 primary docs exist for any specific episode.
- No claim about YouTube thresholds — the added-value numbers in
  `NICHE_PROFILE_SPEC.md` are initial guesses to tune after human review.
- No code, adapter, or pipeline change follows from this file alone.

## Test video status

**CID (1984 NASA/FAA Controlled Impact Demonstration, Boeing 720) stays as the pilot/test video only.**

Reason: demand is measured for CID (aviation-test-history demand report: DEMAND_SIGNAL_PRESENT; top videos reach ~100k–138k views in 365d), but every licensable CID clip surfaced keyless is **320x240 h.264** (archive.org NIX collection), i.e. below the HD (>=720p) bar of the space & astronomy niche profile. CID remains useful as a test fixture for claim-ledger, QC, and rebuild tooling; it is NOT a candidate for the primary niche rollout until HD (>=720p) licensable footage is verified.

## Companion niche profile

- `docs/openmontage/NICHE_PROFILE_SPACE_ASTRONOMY_HD.md` — niche profile spec for
  "Space & Astronomy on HD Public-Domain Footage" (NASA SVS, images.nasa.gov,
  ESA/Hubble where rights allow, archive.org, Wikimedia), created 2026-10-19.
