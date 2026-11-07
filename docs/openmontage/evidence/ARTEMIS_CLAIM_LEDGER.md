# Artemis Claim Ledger — OpenMontage Milestone K3

**Status:** DRAFT, NOT_PUBLISHABLE. Claim ledger for the Artemis I (SLS/Orion) script.
**Method:** paraphrase only, no memory facts. Every claim sourced from NASA Image and Video Library records (images-api.nasa.gov) reached from this sandbox; all observed items are NASA-produced per metadata (`center` = NASA center), `rights=None` (public domain), no third-party credit → `source_policy_us_gov` candidate (rights per RIGHTS_MODEL.md; frame-level identifiable_persons/logo_visible flags UNKNOWN → NEEDS_REVIEW before timeline use). Primary doc type: NASA_NTRS-class mission imagery/descriptions; nasa.gov HTML pages were rate-limited (429) this session, so image-library descriptions are the reachable primary text.
**Source flag:** TWO = supported by 2+ distinct NASA records; SINGLE = 1 NASA record.
**Two-source rule:** load-bearing claims (launch date/time/pad, first integrated test, flyby distance, farthest distance, splashdown, performance records, legacy) carry TWO_SOURCES; hardware-detail claims (Michoud core stage, rollout, "only rocket" single-mission capability) carry SINGLE_SOURCE honestly.

| claim_id | claim (paraphrased) | sources (distinct NASA records) | source_type | evidence_notes |
|---|---|---|---|---|
| ARTEMIS-01 | NASA's Space Launch System (SLS) rocket and Orion spacecraft form the backbone for the agency's Artemis missions to the Moon. | MSFC_SLS_ArtemisI_Progress-60secs (MSFC, 2019-09-09); MSFC_20230412_April Resource Reel (MSFC, 2023-04-12) | TWO | images-api.nasa.gov descriptions; rights=None |
| ARTEMIS-02 | The SLS core stage was built at Michoud Assembly Facility — the largest rocket stage NASA has built since the Saturn V, 212 feet tall, four RS-25 engines, over 2 million pounds of thrust. | MAF_20190917_Artemis 1 ES Join_BROL (MAF, 2019-09-17) | SINGLE | one NASA record |
| ARTEMIS-03 | SLS will be the most powerful rocket ever built, powered by two solid rocket boosters and four RS-25 engines providing over 8 million pounds of thrust. | MSFC_102621_SLS_Resource_Reel_0119 (MSFC, 2021-10-26); Space Launch System Short Resource Reel April 2020 (MSFC, 2020-04-30) | TWO | images-api.nasa.gov descriptions; rights=None |
| ARTEMIS-04 | SLS rolled out to Launch Complex 39B at Kennedy and was stacked inside the Vehicle Assembly Building ahead of its first flight. | SLS-4091 August 2022 Artemis I Resource Reel 081922 (MSFC, 2022-08-18) | SINGLE | one NASA record |
| ARTEMIS-05 | At 1:47 a.m. EST (6:47 UTC) on November 16, 2022, NASA's Orion spacecraft launched atop the SLS rocket from historic Launch Pad 39B at Kennedy Space Center, beginning the Artemis I mission. | KSC-20250128-MH-NAS02-0001 (KSC, 2025-01-28); Success and Preparation (HQ, 2024-04-23); GX010506 Artemis I Launch from NASA Causeway Slo Mo (MSFC, 2022-11-16); Artemis I Launch Press Site (MSFC, 2022-11-16) | TWO | four distinct NASA records agree on date/time/pad |
| ARTEMIS-06 | Artemis I was an uncrewed flight test and the first integrated test of the agency's deep space exploration systems: the SLS rocket, the Orion spacecraft, and supporting ground systems; first in a series of increasingly complex missions to the Moon. | MSFC_SLS_01142021 SLS Launch and Mission Animation (MSFC, 2021-01-14); GX010506 (MSFC, 2022-11-16); Artemis I Launch Press Site (MSFC, 2022-11-16); KSC Live Launch Coverage - 4K (KSC, 2022-11-16) | TWO | four distinct NASA records |
| ARTEMIS-07 | Over the course of the 25.5-day mission, Orion performed two lunar flybys, coming within 80 miles (129 kilometers) of the lunar surface. | KSC-20250128-MH-NAS02-0001 (KSC, 2025-01-28); Success and Preparation (HQ, 2024-04-23) | TWO | two distinct NASA records |
| ARTEMIS-08 | At its farthest distance during the mission, Orion traveled nearly 270,000 miles (435,000 kilometers) from Earth. | KSC-20250128-MH-NAS02-0001 (KSC, 2025-01-28); Success and Preparation (HQ, 2024-04-23) | TWO | two distinct NASA records |
| ARTEMIS-09 | NASA's Orion spacecraft completed a parachute-assisted splashdown in the Pacific Ocean at 9:40 a.m. PST (12:40 p.m. EST), the final major milestone of the Artemis I mission. | KSC-20250128-MH-NAS02-0001 (KSC, 2025-01-28); Success and Preparation (HQ, 2024-04-23) | TWO | two distinct NASA records |
| ARTEMIS-10 | Artemis I set new records of performance, exceeded efficiency expectations, and established new safety baselines for humans in deep space. | KSC-20250128-MH-NAS02-0001 (KSC, 2025-01-28); Success and Preparation (HQ, 2024-04-23) | TWO | two distinct NASA records |
| ARTEMIS-11 | Following Artemis I, human beings will fly around the Moon on Artemis II; under Artemis, NASA will land the first woman and the first person of color on the Moon. | KSC-20250128-MH-NAS02-0001 (KSC, 2025-01-28); GX010506 (MSFC, 2022-11-16); Artemis I Launch Press Site (MSFC, 2022-11-16) | TWO | three distinct NASA records |
| ARTEMIS-12 | SLS, Orion, and the Gateway in lunar orbit form NASA's backbone for deep space exploration; SLS is the only rocket that can send Orion, astronauts, and supplies to the Moon in a single mission. | MSFC_20230412_April Resource Reel (MSFC, 2023-04-12) [backbone]; MSFC_102621_SLS_Resource_Reel_0119 (MSFC, 2021-10-26) [SLS most powerful] | TWO / SINGLE | backbone = one record (SINGLE); "only rocket... single mission" = one record (SINGLE) — flagged |

## Verification status summary

- All 12 claims paraphrased from NASA Image and Video Library records (images-api.nasa.gov), fetched 2026-10-19.
- nasa.gov HTML (artemis/, sls/) returned HTTP 429 (rate-limited) — not used; image-library descriptions are the reachable primary text.
- ESA pages not probed (ESA/Hubble rights terms not confirmed per-item in this session).
- Load-bearing claims ARTEMIS-01, 03, 05, 06, 07, 08, 09, 10, 11 = TWO_SOURCES.
- ARTEMIS-02, 04, 12 = SINGLE_SOURCE (one NASA record each) and flagged in the script.
- Total claims: 12 (ARTEMIS-01 to ARTEMIS-12).
- Network/disk: 20 requests used (<40 cap); 3 test files downloaded (at cap) for K2 HD verification; no publishing, no AI upscaling, no secrets.
