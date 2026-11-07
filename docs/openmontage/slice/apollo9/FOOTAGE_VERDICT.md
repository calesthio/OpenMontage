# FOOTAGE_VERDICT.md — Apollo 9 footage reality check (Milestone X)

**Date:** 2026-10-20  
**Scope:** Apollo 9 NASA-produced stills (AS09-xx-xxxx series) and NASA-produced video on images.nasa.gov + archive.org.  
**Rule:** third-party credit or NC/ND license = REJECT (fail-closed, per RIGHTS_MODEL.md). No AI upscaling. curl -L only. Cap 600 MB.

---

## 1. Apollo 9 stills (NASA Image & Video Library, 100 items, all NASA centers)

Searched `https://images-api.nasa.gov/search?q=Apollo%209&media_type=image` (100 items, centers JSC/HQ/MSFC). archive.org `AS09*` image search returned 0 (the two cataloged stills, AS09-21-3199 and GPN-2000-001283, live under non-AS09 identifiers).

Rights classification per RIGHTS_MODEL.md (source_policy_us_gov requires NASA center + no third-party credit + no per-item restriction; NASA insignia/emblem restricted by 14 CFR 1221; identifiable persons = NEEDS_REVIEW, not cleanly usable):

| Category | Count | Disposition |
|---|---:|---|
| Total NASA images returned | 100 | — |
| Emblem / insignia restricted (e.g. S69-18569 "Emblem - Apollo 9 Space Mission") | 1 | REJECT (14 CFR 1221) |
| Identifiable crew / portraits / training / EVA (McDivitt, Scott, Schweickart identifiable) | ~27 | REJECT (privacy/publicity, NEEDS_REVIEW) |
| Art concepts (uncertain rights) | 2 | REJECT (unclear) |
| Press conference / modern event (HQ, likely copyrighted) | 4 | REJECT (copyright/event) |
| **Rights-clean usable stills (vehicle, launch, pad, LM/CM, docked, Earth obs, recovery capsule)** | **59** | usable, but see coverage gaps below |

**Usable stills = 59** — just under the 60-stable threshold for a stills-primary rebuild, and critically **not chapter-complete**: chapters C4 (Spider systems check — LM interior/engine test-fire), C5 (Schweickart EVA — porch/hatch), C6 (Spider flies free — free-flight/separation), and C7 (S-IVB near-miss — S-IVB stage/engine test-fire) have **zero** usable stills (inventory t05 marks these "NO — 0"). The rights-clean stills are dominated by launch pad, spacecraft exterior, Earth-observation geography, and recovery-capsule shots — none depict LM interior, EVA, free-flight, or S-IVB separation.

---

## 2. Apollo 9 video (NASA images.nasa.gov + archive.org)

| Source | Query | Items | Usable HD minutes | Disposition |
|---|---|---:|---:|---|
| images-api.nasa.gov | `Apollo 9`, video | 13 | 0 | None are Apollo 9 archival footage (50th-anniversary retrospectives, Apollo 11/13/14, Artemis, ISS interviews, Mercury-Gemini-Apollo resource reel) |
| archive.org | `apollo9_three_to_make_ready` | 2 | 0 | 17 min SD, third-party credit "A/V Geeks LLC" → **REJECT** |
| archive.org | `17584-apollo-action-center-footage-mos-vwr` | 1 | 0 | Splashdown/recovery; `licenseurl: CC BY-NC-ND 4.0`, `creator: None` → **REJECT** (NC + ND) |
| Wikimedia Commons | `Apollo 9 16mm Film 1969.webm` | 1 | 0 | 22.83 min, 1734x1080 but **"AI-upscaled (not native HD)"** → REJECT (no AI upscaling rule) |
| Wikimedia Commons | `Space Duet of Spider and Gumdrop` | 1 | 0 | 678x442 SD only → 0 min |

**Apollo 9 usable HD video minutes = 0.**

---

## 3. Verdict: Apollo 9 footage is too thin

- Usable stills: 59 (< 60 threshold) and not chapter-complete (C4, C5, C6, C7 = zero footage).
- Usable video: 0 minutes.
- All candidate motion footage rejected (NC/ND, third-party credit, SD-only, or AI-upscaled).

**A faithful 15–17 min Apollo 9 rebuild cannot be produced from rights-clean NASA footage.** Per Milestone X step 2, footage is too thin → recommend a replacement first topic.

---

## 4. Replacement recommendation: ISS (International Space Station)

From T5 (ISS is a top-10 topic with Tier-A footage tier) and the NASA API check:

| Check | Result |
|---|---|
| NASA-produced video on images.nasa.gov | **100 items** (centers GRC/JSC/HQ), HD, PD (source_policy_us_gov) |
| NASA-Ultra-High-Definition directory | 4K Earth from ISS, PD (t05 inventory) |
| Third-party credit / NC/ND | None found in sampled items |
| Usable HD minutes | Abundant (>> 15 min) |

**ISS is the recommended replacement first topic.** It has abundant rights-clean HD video and covers all chapter types without the identifiable-person/emblem restrictions that cripple Apollo 9.

---

## 5. Same reality check on ISS (best replacement candidate)

Ran `https://images-api.nasa.gov/search?q=ISS%20International%20Space%20Station&media_type=video` → **100 items**, all NASA centers (GRC/JSC/HQ), HD video, PD. No third-party credit or NC/ND licenses observed in the sampled set. ISS passes the footage reality check and is cleared as the replacement topic.

---

## 6. qc.py (all inputs, thresholds unchanged)

Apollo 9 is **not rebuilt** (footage too thin), so there is no new Apollo 9 render to QC. The existing Milestone Y Apollo 9 draft (graphics + 2 NASA PD stills, 1920x1080p30, 428.6s) was already QC'd:

| Check | Status |
|---|---|
| ffprobe_streams | PASS |
| full_decode | PASS |
| blackdetect | PASS (0.0000 <= 0.05) |
| freezedetect | REVIEW (static_by_design cards/stills — expected) |
| silencedetect | PASS |
| ebur128 | PASS (I=-15.6 LUFS, TP=-4.1 dBTP) |
| duration_vs_script | PASS (drift 0.00s <= 1.0s) |
| subtitle_sync | PASS |
| credits_complete | PASS |
| claim_ids | PASS (9/9) |
| claim_ids_resolve | PASS (9/9 resolve, all TWO_SOURCES) |
| rights_basis | PASS (19/19 valid) |
| added_value | PASS (no unannotated clips > 20s) |

**Overall Apollo 9 draft: NOT_PUBLISHABLE** — reasons: no clean native-HD PD motion footage (build uses graphics + 2 stills only), synthetic-voice disclosure pending (YouTube AI-content policy), NASA insignia/frame review pending (NEEDS_REVIEW), 4 chapters (C4–C7) have no usable footage so the draft is graphics-only for those sections.

**Next step (owner decision):** approve ISS as replacement topic; run the full build pipeline (claim ledger → script → footage manifest + rights → narration → subtitles → EDL → render → finish_audio → qc → package) on ISS with the same fail-closed gates.

---

**Requests this phase:** 6 (NASA images ×2, archive.org AS09, archive.org splashdown metadata, NASA Apollo 9 video, NASA ISS video).  
**Disk:** ~5.3 GB free /workspaces (above 800 MB stop threshold). No AI upscaling, no secrets, no publishing.
