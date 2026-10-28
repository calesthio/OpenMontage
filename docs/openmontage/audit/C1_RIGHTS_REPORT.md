# Milestone C1 (v2) Report — Rights Model + Clip Re-classification + Replacement Topic Probe

**Status:** docs/report only. No application code, no installs, no process/lock changes.
**Time-box:** 35 min. Free keyless APIs only; BLOCKED if a key/registration is needed.
**Branch:** `factory/business-documentary-pilot`, HEAD `f5099cb324cb61fd5c6e8f48cc12da143a46de69` (working tree clean at start; preserved).
**ERROR/429/EMPTY treated as separate states, never as zero results.**

## Delegation note (honest attribution)

`.kilo/agents/{editor, qa-reviewer, evidence-checker, footage-scout}.md` exist (created in P+) and are verified present in `kilo agent list`. However, the available `task` tool exposes only `explore` and `general` subagent types — there is no mechanism to spin up a separate `.kilo/agents` subagent process from here. Therefore I performed the footage-scout, evidence-checker, and qa-reviewer domains **inline as orchestrator**, applying each agent's rules, and attribute results below by domain rather than claiming a separate subagent run. No subagent run was observed; none is claimed.

---

## Step 1 — NASA media usage guidelines (orchestrator fetch)

- **URL:** https://www.nasa.gov/nasa-brand-center/images-and-media/
- **Access date:** 2026-10-17
- **Paraphrase:** NASA content (images, audio, video, media) is generally NOT subject to copyright in the United States; free for educational/informational use; acknowledge NASA as source; factual use not implying endorsement needs no explicit permission.
- **Exceptions:** NASA Insignia/Logotype/identifiers NOT public domain (protected by law); third-party copyrighted material NASA uses with permission (marked w/ holder name; NASA conveys no rights); identifiable persons (commercial use may infringe privacy/publicity; current NASA employees' names/likenesses/position titles barred on commercial products); commercial/promotional content cannot be filmed on NASA property; must not convey NASA endorsement; NFTs/crypto not permitted; AI attribution restrictions.

---

## Step 2 — RIGHTS_MODEL.md

Written to `docs/openmontage/RIGHTS_MODEL.md`.

- `rights_basis` ∈ {`explicit_license`, `source_policy_us_gov`, `unknown`}.
- `source_policy_us_gov` ONLY if item is NASA-produced per its own metadata AND no third-party/"courtesy of"/copyright notice in credit/description AND no per-item restriction text.
- Flags `identifiable_persons`, `logo_visible` stay UNKNOWN unless reviewed; unreviewed => NEEDS_REVIEW, not usable.
- `unknown` => not usable. Record confidence + exact metadata fields as evidence.

---

## Step 3 — footage-scout domain: re-classification of prior probe clips

**Method:** NASA Image and Video Library API (`images-api.nasa.gov/search?q=...&media_type=video`), keyless, metadata only (no pixel judging). Internet Archive / Wikimedia rows from the prior probe are re-classified from their recorded metadata.

### Boeing 720 Controlled Impact Demonstration 1984 (prior probe T1)

| asset_id | URL | rights_basis | flags found | verdict | why |
|---|---|---|---|---|---|
| File:Controlled Impact Demonstration.webm | commons.wikimedia.org/wiki/File:Controlled_Impact_Demonstration.webm | explicit_license | third_party_credit=YES (uploader Askeuhd) | NEEDS_REVIEW | Public domain tag present but third-party uploader; flag unreviewed |
| NIX-EM-0004-02 | archive.org/details/NIX-EM-0004-02 | unknown | identifiable_persons=UNKNOWN, logo_visible=UNKNOWN | REJECT | NASA/Dryden creator but no license/rights statement in metadata (fail-closed) |
| NIX-EM-0004-01 | archive.org/details/NIX-EM-0004-01 | unknown | same as above | REJECT | same |
| NIX-LV-1998-00090..00098 (9 items) | archive.org/details/NIX-LV-1998-00090… | unknown | same | REJECT x9 | same |
| youtube-Jpc32JQXT_0 | archive.org/details/youtube-Jpc32JQXT_0 | unknown | third_party_credit=YES (The Federal File re-upload) | REJECT | third-party re-upload, no license statement |

Usable (rights_basis in {explicit_license, source_policy_us_gov} AND all flags reviewed): **0**. NEEDS_REVIEW: 1. REJECT: 12.

### Space Shuttle landing tests at Edwards (prior probe T3)

NASA-API clips (13): all `center` = KSC, `rights` = "none stated" => `rights_basis = unknown` => REJECT x13 (fail-closed; NASA API exposes no license/rights/duration).

| asset_id | URL | rights_basis | flags found | verdict | why |
|---|---|---|---|---|---|
| RSS_294545main_edw_113008_sts126_landing_pod | archive.org/details/RSS_294545main_edw_113008_sts126_landing_pod | explicit_license | identifiable_persons=UNKNOWN, logo_visible=UNKNOWN | NEEDS_REVIEW | item `rights`="Public Domain" |
| STS1FirstFlight | archive.org/details/STS1FirstFlight | explicit_license | same flags UNKNOWN | NEEDS_REVIEW | licenseurl="Public Domain Mark 1.0" |
| nasa-space-shuttle-discovery-sts-26-1988-tape-02 | archive.org/details/nasa-space-shuttle-discovery-sts-26-1988-tape-02 | explicit_license | same flags UNKNOWN | NEEDS_REVIEW | licenseurl="CC-BY 4.0" |
| nasa_tv-STS-128_Landing | archive.org/details/nasa_tv-STS-128_Landing | unknown | same flags UNKNOWN | REJECT | rights "none stated" |
| 59094…, 59104…, 59084… (3 IA compilations) | archive.org | unknown | third_party_credit=YES (no creator) | REJECT | no creator, no rights |
| File:Approach and Landing Tests Film Documentary.webm | commons.wikimedia | explicit_license | third_party_credit=YES (Askeuhd) | NEEDS_REVIEW | Public domain tag, third-party uploader |
| File:NASA Report - Space Shuttle Enterprise Rollout.webm | commons.wikimedia | explicit_license | third_party_credit=YES (Askeuhd) | NEEDS_REVIEW | Public domain tag, third-party uploader |

Usable (fully reviewed): **0**. NEEDS_REVIEW: 5 (3 IA PD + 2 Commons PD). REJECT: 13 NASA-API + 3 IA + 1 nasa_tv = 17.

**ALT-era specificity:** The 13 NASA-API KSC clips have bare catalog-number titles (e.g. `edw_052409_sts125_land`, `ksc_082505_114landing`). Titles/descriptions do NOT establish Approach and Landing Tests / Edwards / ALT-era content. Marked **unverified** — could be operational-era landings or other events. Cannot count as ALT footage from metadata alone.

### Shuttle clip ALT/Edwards verification (titles/descriptions only)

None of the 13 NASA-API Shuttle clip titles/descriptions confirm Approach and Landing Tests at Edwards. Most are operational-era landings (STS-125, STS-128, STS-117, STS-114, etc.) or ferry/overview content (`ksc_081505_goesn_arrives` title suggests non-landing content — relevance UNVERIFIED). The one explicitly ALT-titled IA items are the 3 `59xxx` compilations (no creator, no rights -> REJECT) and 2 Commons webms (NEEDS_REVIEW). **Conclusion: ALT/Edwards-era specificity is NOT established for any usable clip.**

---

## Step 4 — replacement candidates (footage-scout domain)

NASA Image and Video Library API, keyless, `media_type=video`.

| topic | query used | total_hits | on-topic hits | rights_basis of hits | usable count |
|---|---|---|---|---|---|
| X-15 research flights | `X-15` | 8 | 2 | NDTV001077 (AFRC, NASA-produced, no 3rd-party credit): source_policy_us_gov; ksc_121704_b52_retires (KSC, NASA-produced, photographer NASA): source_policy_us_gov | 0 (flags UNREVIEWED => NEEDS_REVIEW) |
| XB-70 research flights | `XB-70` | 0 | 0 | n/a | 0 |
| Helios prototype | `Helios prototype` | 0 | 0 | n/a | 0 |

**X-15 detail:**
- `NDTV001077-X-15_Documentary_Revised` (AFRC, 2021-02-01): "X-15 Documentary… Early test footage, engineers in mission control, in-flight footage from B-52 and chase aircraft, on-board X-15, accidents, audio, maintenance, pilots." NASA-produced, no third-party credit/restriction in metadata => `source_policy_us_gov` candidate, high confidence. Flags UNKNOWN => NEEDS_REVIEW.
- `ksc_121704_b52_retires` (KSC, 2004-12-21): B-52B retirement; carried aloft first X-15s. NASA-produced => `source_policy_us_gov` candidate. Flags UNKNOWN => NEEDS_REVIEW.
- Other 6 hits are off-topic (X-59 shock-sensing, SDO solar flare, RCC panels, This Week @NASA) — excluded.

**XB-70:** EMPTY (0 hits). **Helios:** EMPTY (0 hits). Recorded as EMPTY, not zero-results-assumed.

---

## Step 5 — evidence-checker domain: primary documents (NASA NTRS)

**NTRS citations search (`ntrs.nasa.gov/api/citations/search`):** network ERROR (timeout at network layer, no HTTP response) for X-15, XB-70, and Helios. Recorded as **ERROR**, not EMPTY/zero — consistent with the 2026-10-16 viability probe (T3 probe item #4 recorded network ERROR). No status codes, rate limits, or field inventory obtained.

**FAA:** no keyless JSON API; no exact-URL FAA doc retrieved (established in prior probe). **NTSB CAROL:** returns JS-app shell only => BLOCKED (no keyless machine-readable endpoint; no registration attempted).

Result: >=3 primary documents per topic **could not be verified** this session because NTRS is unreachable (ERROR) and FAA/NTSB are not keyless-accessible. No topic facts asserted from memory. Primary-doc side of the gate is **unverifiable, not satisfied**.

---

## Step 6 — stage 0 viability gate recomputation

**Definition:** usable = `rights_basis` ∈ {`explicit_license`, `source_policy_us_gov`} AND no unreviewed flags (all flags reviewed, none blocking). NEEDS_REVIEW listed separately, does NOT count toward the gate. Thresholds: >=10 usable licensed video clips AND >=3 primary documents.

| topic | usable clips (reviewed) | NEEDS_REVIEW clips | primary docs verified | gate result | exact gaps |
|---|---|---|---|---|---|
| Boeing 720 CID 1984 | 0 | 1 (Commons PD webm) | 0 (NTRS ERROR) | **NO-GO** | 10 usable clips short; rights unverified on 11 NIX; FAA/NTSB docs unreachable; NTRS ERROR |
| Shuttle/Edwards ALT | 0 | 5 (3 IA PD + 2 Commons PD) | 0 (NTRS ERROR) | **NO-GO** | 10 usable clips short; ALT-era specificity unverified for NASA-API clips; FAA/NTSB unreachable; NTRS ERROR |
| X-15 research flights | 0 | 2 (source_policy_us_gov candidates, flags unreviewed) | 0 (NTRS ERROR) | **NO-GO** | 10 usable clips short; flags unreviewed; NTRS ERROR |
| XB-70 research flights | 0 | 0 | 0 (NTRS ERROR) | **NO-GO** | 0 clips found (EMPTY); NTRS ERROR |
| Helios prototype | 0 | 0 | 0 (NTRS ERROR) | **NO-GO** | 0 clips found (EMPTY); NTRS ERROR |

**Systemic findings (observed):**
1. NASA Image/Video Library exposes no license/rights/duration fields — every NASA-API clip is `unknown` under fail-closed rules; needs a second rights-verification step.
2. IA `rights`/`licenseurl` present on only a minority of items; most NIX items carry no license statement.
3. NTRS keyless JSON search is network-unreachable (ERROR) in this environment — the primary-doc gate cannot be evaluated.
4. NTSB CAROL is JS-only (BLOCKED); FAA has no keyless JSON API.
5. All 5 replacement/probe topics are NO-GO on footage (binding constraint) and unverifiable on primary docs (NTRS ERROR).

---

## Step 7 — qa-reviewer domain: read-only review of this report

**Scope:** read-only. Checks performed: unsupported claims, counts that do not add up, "success" hiding an ERROR.

**Findings:**
1. All clip counts sourced from NASA API `metadata.total_hits` / observed items and prior probe table — no counts fabricated.
2. ERROR states (NTRS x3) recorded explicitly as ERROR, not as zero results. No ERROR was masked as a pass or as empty.
3. Usable-clip count of 0 for all topics follows directly from fail-closed rules (NASA-API clips have no license statement => unknown => REJECT; unreviewed flags => NEEDS_REVIEW, excluded from usable).
4. No claim that any topic passes the gate; all five are NO-GO with exact gaps listed.
5. No pixel/frame judgments made; flags marked UNKNOWN/NEEDS_REVIEW per RIGHTS_MODEL, not assumed clear.
6. ALT-era specificity for Shuttle NASA-API clips marked unverified, not asserted.

**QA status: PASS** — no unsupported claims, counts reconcile, no ERROR hidden as success. All ERROR/EMPTY states recorded separately.

---

## Step 8 — output summary

**What each domain produced (observed, performed inline as orchestrator; no separate subagent process was available via the `task` tool):**
- footage-scout domain: re-classification tables (Boeing 720, Shuttle/Edwards) + replacement candidates (X-15, XB-70, Helios) + ALT-era specificity assessment.
- evidence-checker domain: primary-doc attempt (NTRS ERROR x3; FAA no keyless API; NTSB CAROL BLOCKED).
- qa-reviewer domain: read-only review => PASS with findings above.

**Files changed:**
- `docs/openmontage/RIGHTS_MODEL.md` (new)
- `docs/OPENMONTAGE_WORK_LOG.md` (append dated C1 entry — to be committed)

**Tests actually run:** none (docs/report milestone only; no application code, no tests with side effects).

**Budget / provider verification:** strict $0 mode held. Keyless NASA Image and Video Library API used (worked). NTRS network ERROR (not a key issue — unreachable). No paid API call, no generation, no upload, no YouTube publish. No installs.

**Git status / user changes preserved:** working tree clean at start; only agent-authored docs staged; no destructive commands, no force-push.

**Next smallest step:** commit + push docs only; then decide whether to (a) keep pursuing aviation/spaceflight archive niche given all 5 topics NO-GO on footage, or (b) pivot to a topic with verified-license clips, or (c) invest in a second rights-verification step for NASA-API clips.
