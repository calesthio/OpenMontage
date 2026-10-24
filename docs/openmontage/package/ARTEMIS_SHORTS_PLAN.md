# Artemis Shorts Cut Plan — OpenMontage Milestone K3

**Status:** DRAFT, NOT_PUBLISHABLE. 45-second YouTube Shorts cut derived from ARTEMIS_FULL_SCRIPT_v0.md.
**Source:** Artemis I script (6 beats, claim_ids on every sentence; see docs/openmontage/slice/ARTEMIS_FULL_SCRIPT_v0.md and ARTEMIS_CLAIM_LEDGER.md).
**Format:** vertical 9:16 Shorts, ≤60s, narration on ≥90% of runtime (added-value gate), original graphics cards declared static_by_design, every claim has on-screen source card or credits entry.
**Footage:** Artemis I launch inserts (NASA, source_policy_us_gov candidates, 4K verified artemis_test.mp4) + stills/graphics; no third-party credit; NASA insignia present in source animation frames (frame review required — NASA insignia cannot appear with AI-generated imagery; do not imply NASA endorsement).

---

## 45-second cut — beat map

| Segment | Time | Beat | Narration (paraphrased, claim_ids) | Visuals | Static by design? |
|---|---|---|---|---|---|
| Hook | 0–5 s | B2 Launch | "At 1:47 a.m. EST on November 16, 2022, NASA's Orion launched atop the SLS rocket from Launch Pad 39B." [ARTEMIS-05] | Artemis I launch insert, 4K, 2x framed | no |
| Mission | 5–20 s | B3/B4 Transit & Moon | "A 25.5-day path to the Moon. Two lunar flybys within 80 miles. Farthest point: nearly 270,000 miles from Earth." [ARTEMIS-05, ARTEMIS-07, ARTEMIS-08] | Orion transit graphics + Moon flyby card | transit card: yes |
| Return | 20–35 s | B5 Return | "Parachute-assisted splashdown in the Pacific at 9:40 a.m. PST — the final major milestone." [ARTEMIS-09] | splashdown graphic card | yes |
| Legacy | 35–45 s | B6 Legacy | "Next: Artemis II flies humans around the Moon; NASA will land the first woman and first person of color on the Moon." [ARTEMIS-11] | "Artemis II — coming" title card + source credits | title card: yes |

**Total runtime:** 45 s. **Narration coverage:** ~42/45 s (≥90%). **Unannotated archive clip:** none >20 s (longest insert 5 s). **Still-only sequence:** none >15 s.

---

## Edit decisions (EDL)

| Cut | Source | in_s | out_s | annotation | static_by_design |
|---|---|---|---|---|---|
| C1 | artemis_test.mp4 (launch) | 0 | 5 | hook, liftoff | no |
| C2 | graphics/transit_card | 5 | 10 | path to Moon, 25.5 days | yes |
| C3 | graphics/moon_flyby_card | 10 | 15 | two flybys, 80 miles | yes |
| C4 | graphics/farthest_card | 15 | 20 | 270,000 miles from Earth | yes |
| C5 | graphics/splashdown_card | 20 | 25 | Pacific splashdown 9:40 PST | yes |
| C6 | artemis_test.mp4 (launch/orion) | 25 | 30 | return B-roll | no |
| C7 | graphics/artemis_ii_card | 30 | 40 | Artemis II crew around Moon | yes |
| C8 | graphics/credits_card | 40 | 45 | source credits: NASA images-api | yes |

---

## Source cards / credits

- All footage/stills: NASA Image and Video Library (images-api.nasa.gov), NASA-produced, rights=None (public domain) → source_policy_us_gov candidates; credit NASA.
- Claims sourced per ARTEMIS_CLAIM_LEDGER.md; claim_ids shown on each source card.
- NASA insignia appears in source animation frames; frame review required. No implication of NASA endorsement. No AI-generated imagery combined with NASA insignia.

**NOT_PUBLISHABLE pending:** voice license sign-off (Kokoro-82M Apache-2.0 weights/code, synthetic-data provenance residual risk), clip frame-level review, NASA insignia clearance, synthetic-voice disclosure.
