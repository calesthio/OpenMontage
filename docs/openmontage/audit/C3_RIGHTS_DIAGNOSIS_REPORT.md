# Milestone C3 (v2) Report — Rights Classification Diagnosis + NTRS Network Diagnosis

**Status:** docs/report only. No application code, no installs, no process/lock changes.
**Time-box:** 30 min. Free keyless access only. ERROR/429/EMPTY separate states.
**Branch:** `factory/business-documentary-pilot`, HEAD `447ee6085bb90fe42c7c75ddd82c7b31be4a3c6d` (working tree clean at start; preserved).
**Subagent note:** `.kilo/agents/{editor, qa-reviewer, evidence-checker, footage-scout}` exist and pass `kilo agent list`, but the `task` tool exposes only `explore`/`general` — no separate `.kilo/agents` subagent process was available. All footage-scout/evidence-checker/qa-reviewer work below was **executed inline** by the orchestrator, applying each agent's rules, attributed by domain. "inline, not independent". RIGHTS_MODEL.md NOT loosened.

---

## Step 1 — R1 (25 "no license/rights statement") diagnosis vs written RIGHTS_MODEL.md

**The earlier R1 verdict was STRICTER than the written rule.**

Written rule (RIGHTS_MODEL.md §3), `source_policy_us_gov` granted ONLY when ALL hold:
1. The item is NASA-produced per its own metadata (`creator`/`center` is a NASA center or "NASA").
2. No third-party credit ("courtesy of", "credit: <non-NASA>", copyright notice) in the credit/description fields.
3. No per-item restriction text (no "copyright protected", no license-limiting statement, no "rights reserved").

source_policy_us_gov does **NOT** require a license statement. The earlier C1 R1 verdict implicitly required one → stricter than written.

### (a) center/creator says NASA, no third-party credit, no restriction → source_policy_us_gov under written rule

| nasa_id / asset | center/creator | Third-party credit? | Restriction? | Written-rule classification | Earlier C1 verdict | Change? |
|---|---|---|---|---|---|---|
| NIX-EM-0004-02 | NASA/Dryden | No | No | source_policy_us_gov | REJECT (unknown) | Yes |
| NIX-EM-0004-01 | NASA/Dryden | No | No | source_policy_us_gov | REJECT (unknown) | Yes |
| NIX-LV-1998-00090…00098 (9 items) | NASA/Langley | No | No | source_policy_us_gov | REJECT x9 (unknown) | Yes |
| NASA-API Shuttle 13 KSC clips (e.g. edw_052409_sts125_land) | KSC | No (none observed) | No | source_policy_us_gov | REJECT x13 (unknown) | Yes |
| nasa_tv-STS-128_Landing | NASA TV | No | No | source_policy_us_gov | REJECT (unknown) | Yes |

**25 clips reclassified REJECT → source_policy_us_gov under written rule.** None USABLE — all remain NEEDS_REVIEW because `identifiable_persons`/`logo_visible` UNKNOWN (hard block per RIGHTS_MODEL.md §4).

### (b) center/creator missing or not NASA
- STS1FirstFlight: creator=Department of Defense (not NASA).
- 59xxx IA compilations: no creator.

### (c) other
- nasa-space-shuttle-discovery-sts-26-1988-tape-02: creator=NASA BUT third-party credits (step 2).

---

## Step 2 — Classification inconsistency fix: third-party credit → REJECT (not NEEDS_REVIEW)

RIGHTS_MODEL.md §3 condition #2: no third-party credit in credit/description. Any clip with third-party credit/courtesy/copyright text → REJECT regardless of flag-review state.

| nasa_id / asset | Third-party credit observed | New verdict | Reason |
|---|---|---|---|
| STS1FirstFlight | "Provided by Fight for Space / Paul Hildebrandt" + fightforspace.com; creator=DoD | REJECT | third-party credit (condition #2 fails) |
| nasa-space-shuttle-discovery-sts-26-1988-tape-02 | "via NASA TV / Multnomah Cable Access, CNN & NBC"; "Bernard Shaw … on CNN" | REJECT | third-party credit |
| File:Controlled Impact Demonstration.webm | uploader Askeuhd (third-party uploader) | REJECT | third-party credit |
| File:Approach and Landing Tests Film Documentary.webm | uploader Askeuhd (third-party uploader) | REJECT | third-party credit |
| File:NASA Report - Space Shuttle Enterprise Rollout.webm | uploader Askeuhd (third-party uploader) | REJECT | third-party credit |

**Owner rule: any third-party credit = REJECT regardless of review.**

### Recomputed counts per topic

| topic | REJECT | NEEDS_REVIEW (sole open issue = flags, no third-party credit) |
|---|---|---|
| Boeing 720 CID 1984 | 1 (youtube-Jpc32JQXT_0, third-party credit) | 11 (NIX, source_policy_us_gov, flags UNKNOWN) |
| Shuttle/Edwards ALT | 9 (STS1FirstFlight, STS-26 tape, 3 Commons Askeuhd, 3 IA 59xxx no-creator) | 15 (13 NASA-API KSC + nasa_tv + RSS_294545main, source_policy_us_gov, flags UNKNOWN) |
| X-15 research flights | 0 | 2 (NDTV001077, ksc_121704_b52_retires, source_policy_us_gov, flags UNKNOWN) |

**USABLE (fully reviewed): 0 for all topics.** NEEDS_REVIEW clips do not count toward the stage 0 gate.

---

## Step 3 — NTRS network diagnosis (4 requests, 20s timeout each; within 8 cap)

| # | Method | Timestamp (UTC) | Status | Exit code | Time |
|---|---|---|---|---|---|
| 1 | DNS resolve `ntrs.nasa.gov` (getent hosts) | 03:10:50.197 | OK — 161.40.161.143, 161.40.161.179 (AWS GovCloud ELB) | 0 | — |
| 2 | TLS handshake `curl -v https://ntrs.nasa.gov/api/openapi/` | 03:11:04.775 | Connection timed out (tried 161.40.161.179 then 161.40.161.143) | 28 | 20.0s each IP |
| 3 | `GET https://ntrs.nasa.gov/citations/20260001965` | 03:11:05.726 | HTTP 000 | 28 | 20.0s |
| 4 | `POST https://ntrs.nasa.gov/api/citations/search` JSON `{"q":"X-15"}` | 03:11:34.807 | HTTP 000 | 28 | 20.0s |

**Local network control:** images-api.nasa.gov HTTP 200 (2.2s); archive.org HTTP 200 (3.5s) — local network works.

**OpenAPI schema:** could not be read (request #2 timed out). Milestone B called `GET https://ntrs.nasa.gov/api/citations/search?q=...` successfully; this session cannot reach any ntrs.nasa.gov endpoint at the TCP/TLS layer — so method/URL/headers comparison is moot; the failure precedes any HTTP exchange.

**HEAD Content-Length check:** not performed — TCP 443 to ntrs.nasa.gov times out, so HEAD would also time out; no STI harvesting ndjson downloaded.

**Classification: persistent** — 4/4 attempts fail identically at the connect layer (TCP 443 timeout), not transient (backoff didn't help), not wrong request (failure precedes HTTP), not local network (other NASA/IA hosts reachable). NTRS side blocked (or firewall between this env and NTRS). Primary-doc gate unverifiable, not satisfied.

---

## Step 4 — Candidate sweep (Shuttle/Edwards + X-15 only), NASA Image/Video Library API, keyless

### X-15 research flights
Query `q=X-15&media_type=video`: total_hits=8.
On-topic (2):
- NDTV001077-X-15_Documentary_Revised | center=AFRC | "X-15 Documentary… on-board the X-15…"
- ksc_121704_b52_retires | center=KSC | "…carried aloft the first X-15 hypersonic rocket planes…"
Off-topic (6): X-59 shock-sensing, SDO solar flare, RCC panels, This Week @NASA x2.

Apply RIGHTS_MODEL.md: both center=NASA (AFRC/KSC), no third-party credit, no restriction → source_policy_us_gov. Flags UNKNOWN → NEEDS_REVIEW.
Counts: rule-pass(source_policy_us_gov)=2, NEEDS_REVIEW=2, REJECT=0.

### Shuttle/Edwards ALT
Query `q=space shuttle landing&media_type=video&center=KSC`: total_hits=79. First 15 all operational-era Shuttle landings (STS-129, STS-114, STS-122, STS-121, STS-134, STS-132, STS-135) + Mars 2020 / Crew-13 non-Shuttle. None are Approach and Landing Tests / ALT-era; ALT-era specificity unverified (bare catalog titles, same as C1).

Apply RIGHTS_MODEL.md: all center=KSC (NASA), no third-party credit in search metadata, no restriction → source_policy_us_gov candidates. Flags UNKNOWN → NEEDS_REVIEW.
Counts (15 sampled): rule-pass(source_policy_us_gov)=15, NEEDS_REVIEW=15, REJECT=0. But ALT-era specificity unverified → cannot count as ALT footage.

---

## Step 5 — REVIEW_QUEUE.md updated

`docs/openmontage/audit/REVIEW_QUEUE.md` now contains ONLY the corrected NEEDS_REVIEW clips (3), contact-sheet path, and one-line owner checklist per clip:
- RSS_294545main_edw_113008_sts126_landing_pod
- NDTV001077-X-15_Documentary_Revised
- ksc_121704_b52_retires

Owner rule stated: any third-party credit = REJECT regardless of review. All three have no third-party credit in metadata → pending flag review only.

---

## Step 6 — Gate check (threshold: >=10 usable clips, >=3 primary docs)

| topic | usable-pending-review count | ALT/Edwards-specific usable-pending-review | primary docs verified | Gate result |
|---|---|---|---|---|
| X-15 research flights | 2 (NDTV001077, ksc_121704_b52_retires) | 2 | 0 (NTRS persistent ERROR) | **NO-GO** (2/10 clips, 0/3 docs) |
| Shuttle/Edwards ALT | 15 source_policy_us_gov candidates | 1 confirmed Edwards (RSS_294545main STS-126 landing); 14 operational-era, ALT unverified | 0 (NTRS persistent ERROR) | **NO-GO** (1/10 ALT-specific, 0/3 docs) |

**Explicit pivot recommendation:** No topic can reach 10 usable clips even after owner review clears flags (X-15 caps at 2; Shuttle/Edwards ALT-specific caps at 1). The binding constraints are: (1) NASA Image/Video Library exposes no license/rights, so every clip needs a second rights-verification step; (2) ALT-era specificity unverified for operational-era KSC clips; (3) NTRS persistently unreachable (primary docs unverifiable). Recommend **pivoting away from the aviation/spaceflight archive niche for the 30–60s slice**, or (if the niche is mandated) investing in a second rights-verification step for NASA-API clips + ALT-era verification + primary-doc retrieval from an alternative path before any further milestone.

---

## Files changed

- `docs/openmontage/audit/REVIEW_QUEUE.md` (rewritten: corrected NEEDS_REVIEW list of 3, contact-sheet path, owner checklist)
- `docs/openmontage/audit/C3_RIGHTS_DIAGNOSIS_REPORT.md` (new: this report)
- `docs/OPENMONTAGE_WORK_LOG.md` (append dated C3 entry — committed with this report)

**Tests actually run:** none (docs/report only; curl/network diagnosis observed; ffmpeg contact-sheet from C2 already exists, exit 0).

**Budget / provider verification:** strict $0 held. NASA images-api + archive.org reachable (keyless). NTRS persistent network ERROR (not key/registration). No paid API call, generation, upload, publish. No installs.

**Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.

**Next smallest step:** commit + push C3 docs; then act on the pivot recommendation (decide niche continuation vs pivot) before milestone D/Q.
