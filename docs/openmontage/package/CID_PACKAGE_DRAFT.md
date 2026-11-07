# CID Package Draft — OpenMontage Milestone G4

**Status:** NOT_PUBLISHABLE. Draft only. No media committed. All packaging elements below are proposals for owner review.

**Slice:** CID 1984 — Controlled Impact Demonstration (Boeing 720, 1 Dec 1984, Edwards AFB)
**Slice version:** G3 (56.0s, 1920x1080, 30fps, h264/aac)
**Source assets:** docs/openmontage/assets/CID_SLICE_MANIFEST.json (committed manifest, URLs + sha256 + rights)
**Rights records:** projects/slice_cid_v0/rights_records.json (gitignored, regenerated from manifest)
**QC report:** projects/slice_cid_v0/g3_qa_report.json (gitignored, overall PASS)

---

## 1. Title Options (truthful, no clickbait)

| # | Title | Rationale |
|---|---|---|
| 1 | NASA's Controlled Impact Demonstration: Crashing a Boeing 720 on Purpose | Descriptive, states the what and who; no hype |
| 2 | The 1984 Controlled Impact Demonstration: Testing Anti-Misting Fuel on a Remotely Piloted Boeing 720 | Specific about the test purpose and aircraft; accurate |
| 3 | Controlled Impact Demonstration 1984: Did Anti-Misting Kerosene Prevent the Fireball? | Posed as a question the slice answers; no exaggeration |

**Avoid:** "Shocking," "You won't believe," "Terrible crash," "Explosion," "Disaster" — clickbait and misleading.

---

## 2. Description with Chapters

**Draft description:**

NASA and the FAA's Controlled Impact Demonstration (CID) intentionally crashed a remotely piloted Boeing 720 at Edwards Air Force Base on December 1, 1984, to test whether an anti-misting fuel additive could reduce post-crash fire. This technical slice reviews the CID program, the impact sequence, and the findings — including why the FAA ended its attempts to require the additive.

All footage and stills are NASA-produced (source_policy_us_gov), sourced from the NASA Armstrong CID image gallery and the archive.org NIX collection. No third-party credit. No AI upscaling. Narration is synthetic (Kokoro-82M).

**Chapters:**
- 0:00 — Introduction: the CID program
- 1:30 — The approach: Boeing 720 in flight
- 6:00 — Preparation: 14 test flights and remote piloting
- 14:50 — Flight path & timeline
- 22:30 — The impact: wing strikes first
- 27:00 — Crash test dummies and cabin safety
- 32:55 — Impact: front long-shot footage
- 39:00 — Fireball: fuel ignites after impact
- 43:30 — S8: additive ineffective at full scale; FAA ends requirements (source: FAA DOT/FAA/CT-87/10)
- 50:80 — Key numbers from the claim ledger

---

## 3. Credits / Attribution Block

Generated from `projects/slice_cid_v0/rights_records.json`. All assets NASA-produced, `source_policy_us_gov`, no third-party credit. No logo use, no endorsement language.

**Video — Stills (NASA Armstrong CID image gallery):**
- ECN-31803 — Initial Impact of Controlled Impact Demonstration — NASA/Armstrong — 1040x816 — https://www.nasa.gov/image-detail/initial-impact-of-controlled-impact-demonstration/
- EC84-3167-A — Practice Run Before Controlled Impact Demonstration — NASA/Armstrong — 1040x672 — https://www.nasa.gov/image-detail/practice-run-before-controlled-impact-demonstration/
- ECN-31808 — Remotely Flown Boeing 720 Erupts After Impact — NASA/Armstrong — 1040x816 — https://www.nasa.gov/image-detail/remotely-flown-boeing-720-erupts-after-impact/
- EC84-31809 — Boeing 720 Engulfed After Striking Wing Cutter — NASA/Armstrong — 1040x704 — https://www.nasa.gov/image-detail/boeing-720-engulfed-after-striking-wing-cutter/
- ECN-28307 — Crash-Test Dummies Aid in Anti-Misting Kerosene Experiment — NASA/Armstrong — 1040x832 — https://www.nasa.gov/image-detail/crash-test-dummies-aid-anti-misting-kerosene-experiment/

**Video — Archive Inserts (archive.org NIX collection):**
- NIX-EM-0004-01 — EM-0004-01.mp4 — NASA/Dryden — 320x240 — https://archive.org/details/NIX-EM-0004-01
- NIX-LV-1998-00090 — LV-1998-00090.mp4 — NASA/Langley — 320x240 — https://archive.org/details/NIX-LV-1998-00090
- NIX-LV-1998-00092 — LV-1998-00092.mp4 — NASA/Langley — 320x240 — https://archive.org/details/NIX-LV-1998-00092

**Narration:** Kokoro-82M (af_heart), synthetic voice, S1-S8. Voice license status: weights/code Apache-2.0 clear (VOICE_DECISION.md); UNKNOWN only the provenance of part of the training data (synthetic data) — residual risk, owner decision required before publish.

**Primary sources:**
- NASA Facts FS-2009-02-003-CID (https://www.nasa.gov/centers/dryden/pdf/315492main_FS-2009-02-003-CID.pdf)
- NASA TM-4084 (Horton & Kempel)
- DOT/FAA/CT-87/10 (https://rosap.ntl.bts.gov/view/dot/92854/dot_92854_DS1.pdf)

**Rights statement:** All media is NASA-produced (source_policy_us_gov). No third-party credit identified. No NASA logo use. No endorsement language. This slice is NOT_PUBLISHABLE pending owner review.

---

## 4. Pre-Publish Checklist

| # | Check | Status | Owner Action |
|---|---|---|---|
| 1 | Clip owner review (identifiable persons, logo/insignia, third-party credit) | REVIEW | Review `docs/openmontage/audit/REVIEW_QUEUE.md` F5 section; 4 clips marked USABLE_FOR_SLICE; full video full-clip review still pending |
| 2 | Voice license decision (Kokoro-82M synthetic voice) | BLOCKED | Review `docs/openmontage/VOICE_DECISION.md`; weights/code Apache-2.0 clear; UNKNOWN only synthetic-data training provenance — residual risk, do not publish until owner decision |
| 3 | YouTube Guardian / AdSense review | NOT_DONE | No monetization eligibility review performed |
| 4 | NASA insignia clearance | NOT_DONE | Decide if incidental insignia in CID footage requires separate clearance per NASA Media Usage Guidelines |
| 5 | Synthetic-voice disclosure | NOT_DONE | Evaluate against current YouTube rules for synthetic/altered content disclosure |
| 6 | Single-source claims (CID-13) | RESOLVED | CID-13 now TWO_SOURCES (FS + FAA/CT-87/10); S8 unblocked in script |
| 7 | QC gate | PASS | `tools/qa/qc.py` overall PASS (freezedetect REVIEW on static title cards — intentional) |

**Publication status: NOT_PUBLISHABLE** — items 1–5 require owner resolution before any upload.

---

## Records

- `docs/openmontage/assets/CID_SLICE_MANIFEST.json` — committed manifest (URLs + sha256 + rights) for all 8 assets
- `projects/slice_cid_v0/rights_records.json` — per-asset rights, sha256, resolution, source URL, role (gitignored)
- `projects/slice_cid_v0/credits.txt` — full credit text (gitignored)
- `projects/slice_cid_v0/g3_qa_report.json` — QC results (gitignored)
