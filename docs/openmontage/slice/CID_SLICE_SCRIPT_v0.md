# CID Slice Script v0 — OpenMontage MASTER RUN P2

**Status:** DRAFT, NOT_PUBLISHABLE. One sentence per line, each with claim_id(s) from docs/openmontage/evidence/CID_CLAIM_LEDGER.md.
**Provenance:** same as ledger (NASA Facts FS-2009-02-003-DFRC + NASA TM-4084, retrieved 2026-10-17; NTRS blocked).
**Source flags:** SINGLE_SOURCE = claim backed by only one source (FS or TM alone); LOAD-BEARING = publication-critical claim needing a second source.

| line | sentence | claim_ids | source_flags | publication status |
|---|---|---|---|---|
| S1 | On December first, 1984, NASA crashed a Boeing 720 airliner on purpose. | CID-01 | TWO | DRAFT, NOT_PUBLISHABLE |
| S2 | Nobody was on board. A pilot flew it by remote control from the ground. | CID-04 | name SINGLE | DRAFT, NOT_PUBLISHABLE |
| S3 | The goal was to test a fuel additive meant to stop crash fires. | CID-03 | TWO | DRAFT, NOT_PUBLISHABLE |
| S4 | Before the real thing, the team flew fourteen test flights with crews aboard and practiced sixty-nine approaches to the crash site. | CID-05 | TWO | DRAFT, NOT_PUBLISHABLE |
| S5 | But in practice, the airplane had never flown lower than a hundred and fifty feet toward the crash site. | CID-06 | SINGLE_SOURCE | DRAFT, NOT_PUBLISHABLE — depends on SINGLE_SOURCE claim (TM only) |
| S6 | On the real flight, it arrived slightly off the centerline, and its left wing hit first. | CID-08, CID-09 | TWO | DRAFT, NOT_PUBLISHABLE |
| S7 | The fuel ignited into a fireball that burned for more than an hour. | CID-10 | SINGLE_SOURCE | DRAFT, NOT_PUBLISHABLE — depends on SINGLE_SOURCE claim (FS only) |
| S8 | At full scale the modified fuel did not prevent a massive fuel-fed fire, and the FAA ended its attempts to require the additive. | CID-13 | TWO_SOURCES | DRAFT, NOT_PUBLISHABLE — unblocked (CID-13 TWO_SOURCES: FS + FAA/CT-87/10 both read; no intensity claim used in wording) |

## Notes

- S5 depends on CID-06 (TM-only, SINGLE_SOURCE).
- S7 depends on CID-10 (FS-only, SINGLE_SOURCE).
- S8 depends on CID-13 (FS-only, SINGLE_SOURCE, LOAD-BEARING). S8 is BLOCKED for publication until CID-13 is confirmed by a second source.
- All lines: status DRAFT, NOT_PUBLISHABLE until claims are verified and publication blockers cleared.
