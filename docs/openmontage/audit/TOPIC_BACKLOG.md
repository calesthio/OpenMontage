# Topic Backlog — OpenMontage Milestone H5

**Status:** docs only. Read-only viability probe (no downloads, no demand claims). Keyless sources only: archive.org advancedsearch + metadata; NASA images API returned web-app HTML (not parsed).
**Probe date:** 2026-10-18
**Probe scope:** X-15 and XB-70 as potential future slice topics (beyond CID). Beat coverage, rights_basis, primary-doc reachability assessed read-only.
**Downloads:** none new (metadata reads only; 0 of any test-file limit).

---

## 1. X-15 viability probe

### 1.1 Primary docs reachable (keyless)

| doc | URL | reachable? | notes |
|---|---|---|---|
| NASA Facts / image gallery (X-15) | archive.org item 342972main_EC05-0177-33 | YES | metadata read; creator=NASA; rights=Public Domain |
| NASA image "Flight of the X-15" | archive.org item 358032main_image_1382_full | YES | metadata read; creator=NASA; rights=Public Domain |
| NTRS "Remote control of an impact demonstration vehicle" | ntrs.nasa.gov/citations/19850015486 | NOT_REACHABLE | NTRS blocked from this sandbox (per M1 preflight) |

### 1.2 Video count by beat (archive.org advancedsearch, keyless)

Search: `X-15 NASA rocket plane` → 15 docs; relevant NASA items:
- 342972main_EC05-0177-33 — X-15 (still image, NASA, Public Domain)
- 358032main_image_1382_full — Flight of the X-15 (still image, NASA, Public Domain)
- 17564-Flying-Machines_vwr.mov — "FLYING MACHINES" 1970s NASA history (video, creator blank → rights unknown)
- 86134-america-in-space-the-firstyears-vwr — "AMERICA IN SPACE" 1957-1962 (video, creator=PeriscopeFilm → third-party, REJECT)

**Beat coverage estimate (read-only, no downloads):**
- Preparation: 2 stills (EC05-0177-33, image_1382_full) — partial
- Remote piloting: 0 video (X-15 was pilot-flown, not remote) — GAP
- Approach: 0 dedicated — GAP
- Impact: 0 (X-15 did not crash in a demonstration) — N/A
- Fire: 0 — GAP
- Aftermath/lessons: 0 — GAP

**Rights_basis:** NASA stills = source_policy_us_gov (creator=NASA, rights=Public Domain). Non-NASA video (PeriscopeFilm, CIA Reading Room) = rights_basis=unknown → REJECT per RIGHTS_MODEL.md (third-party credit / no license statement).

**Viability assessment:** LOW for a 6–8 minute narrative slice. X-15 was pilot-flown (not remote), had no demonstration crash/fireball, and lacks dedicated impact/fire/aftermath footage. Would require substantial stills-only treatment with voiceover; not recommended without owner-sourced primary video.

---

## 2. XB-70 viability probe

### 2.1 Primary docs reachable (keyless)

| doc | URL | reachable? | notes |
|---|---|---|---|
| archive.org item 359368main_ED97-44244-1 | XB-70 Valkyrie (still) | YES | metadata read; creator=NASA; rights=Public Domain |
| NTRS 19710007657 | Base pressure measurements on XB-70 | NOT_REACHABLE | NTRS blocked |
| NTRS 19710021242 | XB-70 high-altitude turbulence | NOT_REACHABLE | NTRS blocked |
| NTRS 19750065519 | XB-70 air-induction system | NOT_REACHABLE | NTRS blocked |

### 2.2 Video count by beat (archive.org advancedsearch, keyless)

Search: `XB-70 NASA` → 15 docs; relevant NASA items:
- 359368main_ED97-44244-1 — XB-70 Valkyrie (still image, NASA, Public Domain)
- 2004-L-00283 — Edwards Flight Test - Aircraft (NASA/Langley, creator=NASA/Langley → source_policy_us_gov)
- NIX-ECN-2493 — Two F-104s in flight (NASA/Dryden → source_policy_us_gov, related chase aircraft)
- 13414-NASA-Space-Highlights-1965_vwr.mov — NASA news films (creator blank → rights unknown)

**Beat coverage estimate (read-only, no downloads):**
- Preparation: 1 still (ED97-44244-1) — partial
- Remote piloting: 0 (XB-70 was pilot-flown) — GAP
- Approach: 0 dedicated — GAP
- Impact: 0 (XB-70 crashed in 1966 mid-air collision, not a demonstration) — PARTIAL (historical, not a controlled test)
- Fire: 0 — GAP
- Aftermath/lessons: 0 — GAP

**Rights_basis:** NASA still = source_policy_us_gov (creator=NASA, rights=Public Domain). NASA/Langley item = source_policy_us_gov. Non-NASA video = rights_basis=unknown → REJECT per RIGHTS_MODEL.md.

**Viability assessment:** LOW for a 6–8 minute narrative slice. XB-70 was pilot-flown, its loss was a mid-air collision (not a controlled demonstration), and lacks dedicated impact/fire/aftermath demonstration footage. Stills-only treatment possible but thin.

---

## 3. Comparative summary (read-only, no demand claims)

| topic | NASA stills (source_policy_us_gov) | NASA video (source_policy_us_gov) | beats covered (of 6) | primary docs reachable | viability |
|---|---|---|---|---|---|
| CID (Boeing 720, 1984) | 5 (up to 1040x833) | 12 NIX clips (320x240) | 6/6 | YES (FS, TM, FAA/CT-87/10) | HIGH — in production |
| X-15 | 2 (EC05-0177-33, image_1382_full) | 0 dedicated | ~1/6 | PARTIAL (NTRS blocked) | LOW — pilot-flown, no crash/fire |
| XB-70 | 1 (ED97-44244-1) | 0 dedicated | ~1/6 | PARTIAL (NTRS blocked) | LOW — pilot-flown, collision not demo |

---

## 4. Rights notes (RIGHTS_MODEL.md applied)

- creator=NASA + rights=Public Domain or None → source_policy_us_gov (usable)
- creator blank or third-party (PeriscopeFilm, CIA Reading Room, YouTube re-uploads) → rights_basis=unknown → REJECT per RIGHTS_MODEL.md (third-party credit = REJECT)
- NTRS docs not reachable from sandbox → NOT_CHECKED; do not retry

---

## 5. Recommendation (read-only, owner decision)

CID remains the only topic with full 6-beat coverage and sourced primary docs. X-15 and XB-70 are NOT_RECOMMENDED for near-term production without owner-sourced primary video and additional research. No demand claims made; this is a read-only probe.
