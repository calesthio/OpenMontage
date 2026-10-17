# Milestone C4 (v2) Report — CID (Boeing 720, 1 Dec 1984) Focus

**Status:** docs/report only. No application code, no installs, no process/lock changes.
**Time-box:** 30 min. Do NOT lower the 10-clip gate for the full video.
**Branch:** `factory/business-documentary-pilot`, HEAD `9c6a0c71bcaef7ed916db0182d2a360f1d2921f8` (working tree clean at start; preserved).
**Subagent note:** `.kilo/agents/{editor, qa-reviewer, evidence-checker, footage-scout}` exist and pass `kilo agent list`, but the `task` tool exposes only `explore`/`general` — no separate `.kilo/agents` subagent process was available. All footage-scout/evidence-checker/qa-reviewer work below was **executed inline** by the orchestrator, applying each agent's rules, attributed by domain. "inline, not independent". RIGHTS_MODEL.md NOT loosened.

---

## Step 1 — CID primary docs evidence

Created `docs/openmontage/audit/EVIDENCE_CID_PRIMARY_DOCS.md` with 6 entries, each tagged `EXTERNALLY_VERIFIED_METADATA` — metadata verified externally by Claude via web search on 2026-10-17 because this sandbox cannot reach ntrs.nasa.gov (TCP 443 persistent block, C3 step 3). NOT agent-verified; PDF retrieval not yet confirmed; no document text pasted; no topic claims derived from memory.

| # | Title | ID | URL | Org | NTRS rights statement | Provenance |
|---|---|---|---|---|---|---|
| 1 | Impact data from a transport aircraft during a controlled impact demonstration | NASA-TP-2589 / 19860021249 | https://ntrs.nasa.gov/citations/19860021249 | NASA | Not shown (NTRS unreachable) | EXTERNALLY_VERIFIED_METADATA — title/author (E.L. Fasanella, 1986) confirmed via web search |
| 2 | Full-scale Transport Controlled Impact Demonstration Program | NASA-TM-89642 / DOT/FAA/CT-87/10 / 19880000639 | https://ntrs.nasa.gov/citations/19880000639 | NASA / FAA (DOT) | Not shown (NTRS unreachable) | EXTERNALLY_VERIFIED_METADATA — ID cited in CID literature |
| 3 | Remote control of an impact demonstration vehicle | NASA-TM-85925 / 19850015486 | https://ntrs.nasa.gov/citations/19850015486 | NASA (Ames) | "Work of the US Gov. Public Use Permitted." | EXTERNALLY_VERIFIED_METADATA — authors (Harney, Craft, Johnson), NASA TM-85925, Apr 1 1985, Public Use Permitted confirmed |
| 4 | Flight Test Experience and Controlled Impact of a Remotely Piloted Jet Transport Aircraft | NASA TM 4084 / 19890006539 | https://ntrs.nasa.gov/api/citations/19890006539/downloads/19890006539.pdf | NASA | Not shown (PDF download, NTRS unreachable) | EXTERNALLY_VERIFIED_METADATA — NTRS PDF download URL externally verified |
| 5 | CID overview | Hayduk / 19860012463 | https://ntrs.nasa.gov/citations/19860012463 | NASA | Not shown (NTRS unreachable) | EXTERNALLY_VERIFIED_METADATA — NTRS citation ID externally verified |
| 6 | Summary Report — Full-Scale Transport Controlled Impact Demonstration Program | FAA/DOT / dot_92854_DS1 | https://rosap.ntl.bts.gov/view/dot/92854/dot_92854_DS1.pdf | FAA / DOT (ROSAP) | "available to the U.S. public through NTIS" | EXTERNALLY_VERIFIED_METADATA — ROSAP PDF; title, FAA/NASA joint CID, Dec 1 1984 confirmed |

Primary docs with externally verified metadata: **6**. Directly retrievable: entry 6 (ROSAP). Rights statement explicitly permitting public use: entry 3. Entries 1, 2, 4, 5 pending direct NTRS access.

---

## Step 2 — 11 Boeing NEEDS_REVIEW clips + 1 REJECT: metadata-only classification

Source: archive.org metadata API (creator, date, description, rights, licenseurl, collection, file durations). Asset downloads blocked in this sandbox (0 bytes / HTML) — metadata only, no pixel judging.

| # | asset id | title | description (excerpt) | date | duration | center | collection | classification | dupe? |
|---|---|---|---|---|---|---|---|---|---|
| 1 | NIX-EM-0004-01 | Controlled Impact Demonstration (CID) flight video montage | "The edited 'CID movie mont..." | 12/2/1988 | 36.56s | NASA/Dryden Flight Research Center (NASA-DFRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 2 | NIX-EM-0004-02 | Controlled Impact Demonstration (CID) tail camera video | "The tail camera movie is o..." | 12/2/1988 | 35.22s | NASA/Dryden Flight Research Center (NASA-DFRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 3 | NIX-LV-1998-00090 | Crash Impact Demonstration. (pt 1/10) | "Front view, long shot. The plane impacts short of the target area and port wing first..." | 12/2/1988 | 16.93s | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 4 | NIX-LV-1998-00091 | Crash Impact Demonstration. (pt 2/10) | "wing cutters rips through the starboard inboard engine, rupturing fuel lines..." | 12/2/1988 | n/a | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 5 | NIX-LV-1998-00092 | Crash Impact Demonstration. (pt 3/10) | "Extreme Long shot of impact showing the huge fireball surrounding the airplane..." | 12/2/1988 | n/a | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 6 | NIX-LV-1998-00093 | Crash Impact Demonstration. (pt 4/10) | "Demonstrates and explains how AMK can 'fail' and then burn..." | 12/2/1988 | n/a | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 7 | NIX-LV-1998-00094 | Crash Impact Demonstration. (pt 5/10) | "Wide shot of impact, front/port side showing a large volume of AMK flowing over the fuselage..." | 12/2/1988 | n/a | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 8 | NIX-LV-1998-00095 | Crash Impact Demonstration. (pt 6/10) | "Cockpit interior. Showing the pilot during impact, view forward..." | 12/2/1988 | n/a | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 9 | NIX-LV-1998-00096 | Crash Impact Demonstration. (pt 7/10) | "Montage of several different views thru the duration of impact..." | 12/2/1988 | 38.69s | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 10 | NIX-LV-1998-00097 | Crash Impact Demonstration. (pt 8/10) | "Montage of high-speed (slow-motion) footage..." | 12/2/1988 | n/a | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |
| 11 | NIX-LV-1998-00098 | Crash Impact Demonstration. (pt 9/10) | "Long shot, wide, showing entire impact and fireball in realtime..." | 12/2/1988 | n/a | NASA/Langley Research Center (NASA-LaRC) | nasa, nasaimageexchangecollection | on-topic | no |

**REJECT (1):**
| asset id | reason |
|---|---|
| youtube-Jpc32JQXT_0 | third-party credit ("The Federal File" re-upload) + no license statement → rights_basis=unknown → REJECT |

**Classification basis (RIGHTS_MODEL.md §3 source_policy_us_gov):**
- All 11 clips: creator is a NASA center (Dryden or Langley) → condition 1 met.
- All 11 clips: no third-party credit ("courtesy of", credit: non-NASA, copyright notice) in description → condition 2 met.
- All 11 clips: no per-item restriction text ("rights": None, "licenseurl": None, no restriction text) → condition 3 met.
- Therefore all 11 = source_policy_us_gov under the written rule. Flags `identifiable_persons`/`logo_visible` UNKNOWN → NEEDS_REVIEW (hard block per §4).

**Duplicate detection:** No exact duplicates by title (all distinct part numbers pt 1/10–pt 9/10 plus two distinct NIX-EM titles). Duration-based dedupe: confirmed durations differ (36.56s, 35.22s, 16.93s, 38.69s); remaining titles/descriptions distinct per part number. **Deduplicated on-topic count: 11.** (CID-4 through CID-8 durations not confirmed from summary metadata, but titles/descriptions are distinct per part number, so no dedupe merge.)

---

## Step 3 — Gate recompute for CID under the WRITTEN gate

**Gate:** usable-pending-review >= 10 clips AND primary docs >= 3. (Do NOT lower the 10-clip gate.)

| measure | count | threshold | met? |
|---|---|---|---|
| usable-pending-review (on-topic, deduped, source_policy_us_gov, flags pending review) | 11 | >= 10 | yes (count) |
| primary docs (externally verified metadata) | 6 | >= 3 | yes (count) |

**Verdict for the FULL video:** Counts met (11/10 clips, 6/3 docs) BUT with two caveats:
1. The 11 clips are NEEDS_REVIEW (flags `identifiable_persons`/`logo_visible` unreviewed), not USABLE — owner flag review required before they count as usable.
2. Primary docs metadata verified externally (web search) but NTRS unreachable from sandbox; PDFs not retrieved.

So the full-video gate is **met on counts, blocked on review/verification** — not a clean PASS; it is NEEDS_OWNER_REVIEW.

**30–60s technical slice (3–6 clips per master plan):** Met. 11 on-topic clips available; a 3–6 clip slice can be selected from the on-topic set (e.g. NIX-EM-0004-01 montage, NIX-EM-0004-02 tail camera, NIX-LV-1998-00092 fireball, NIX-LV-1998-00091 wing cutters).

**Resolve C3 inconsistency:** C3 step 6 (gate check) listed only X-15 and Shuttle/Edwards ALT, omitting Boeing 720 entirely — even though Boeing 720 was analyzed in C3 steps 1–2 (REJECT=1, NEEDS_REVIEW=11). That was an omission in the gate-check table, not a classification error. C4 resolves it by including Boeing 720 in the gate recompute above.

---

## Step 4 — Owner review pack

`docs/openmontage/audit/REVIEW_QUEUE.md` CID section (appended) contains:
- 11 corrected NEEDS_REVIEW clips (CID-1..CID-11) with URL, rights_basis, duration, sole open issue.
- 1 REJECT clip (youtube-Jpc32JQXT_0) + 1 Commons REJECT (File:Controlled Impact Demonstration.webm).
- Contact-sheet evidence: archive.org `__ia_thumb.jpg` downloads = 0 bytes (blocked); individual `.thumbs/*.jpg` frames = HTML (not images); MP4 derivatives = 0 bytes (blocked). `projects/c4_review/previews/` is empty; 0 bytes downloaded (200 MB cap not reached). Per-clip contact sheets (ffmpeg tile of ~12 frames) **not generated** — defer to an environment that can reach archive.org asset hosts.
- One-line owner checklist per clip: "identifiable person? | logo/insignia visible (NASA, FAA, Boeing, other)? | third-party credit? (yes => REJECT)". All eleven = unclear / unclear / no.

Owner rule restated: any third-party credit = REJECT regardless of review.

---

## Step 5 — PROPOSED (not applied) wording: incidental insignia on vehicles

**Source re-read:** official NASA media usage guidelines, https://www.nasa.gov/nasa-brand-center/images-and-media/, accessed 2026-10-17 (orchestrator fetch, same as C1 step 1).

Exact exception categories (short paraphrase, from the guidelines):
1. NASA Insignia ("meatball"), Logotype ("worm"), identifiers and imagery are **NOT public domain** — use protected by law.
2. Third-party copyrighted material NASA uses with permission — marked with the copyright holder's name; NASA's use conveys no rights; contact the copyright holder directly.
3. Identifiable persons — commercial use may infringe privacy/publicity rights; permission from the person required; current NASA employees' names/likenesses/position titles barred on commercial products.
4. Commercial/promotional use — cannot be filmed on NASA property; must not convey NASA endorsement.
5. NFTs/cryptocurrency — not permitted.
6. AI applications — attribution to NASA not permitted; NASA insignia cannot appear with AI-generated imagery; do not imply NASA review/permission.

**PROPOSED (not applied; owner decision) wording for incidental insignia visible on vehicles in footage:**

> "Incidental NASA insignia/logotype visible on vehicles, aircraft, or facilities in archival footage is governed by the NASA Media Usage Guidelines: the NASA Insignia and Logotype are not public domain and their use is protected by law. Incidental appearance in historical footage does not convey usage rights. Before using any clip containing visible NASA insignia/identifiers in a published work, obtain owner review and, where required, clearance per the NASA Film & Documentary Guidelines and Merchandise/Approvals process. Do not imply NASA endorsement of the documentary or any commercial good/service."

**Marked "owner decision" — not applied to RIGHTS_MODEL.md or to any clip verdict.** The owner decides whether incidental insignia in CID footage (e.g. NASA insignia on the Boeing 720, Dryden facilities) requires separate clearance beyond the source_policy_us_gov / flag-review path.

---

## Step 6 — Plan/work log update

**Slice and pilot topic candidate:** CID 1984 (Boeing 720 Controlled Impact Demonstration).
- Rationale: only topic with >=10 usable-pending-review clips (11) and >=3 primary docs (6 externally verified). All other probed topics (X-15=2, Shuttle/Edwards ALT-specific=1, XB-70=0, Helios=0) fall far short of 10 even after review.
- Caveat: clips are NEEDS_REVIEW (flags unreviewed); primary docs NTRS-unreachable from sandbox; owner flag review + insignia clearance decision required before publish.

**Fallback topics (listed):** X-15 research flights (2 NEEDS_REVIEW clips), Shuttle/Edwards ALT (1 ALT-specific + 14 operational-era NEEDS_REVIEW). Both below the 10-clip gate — listed only as fallbacks if CID is blocked.

**Observed vs assumed:**
- Observed: 11 CID clips are NASA-produced, no third-party credit, source_policy_us_gov under written rule; archive.org asset downloads blocked; NTRS persistently unreachable; primary docs externally verified via web search.
- Assumed (not verified): clip durations for 7 of 11 items (summary metadata lacks duration); flag states (identifiable_persons/logo_visible) — require frame/pixel review; NTRS PDF contents.

**Next smallest step:** commit + push C4 docs; then obtain owner flag review for the 11 CID clips and an insignia-clearance decision (owner decision, step 5) before proceeding to milestone D/Q.

---

## Files changed

- `docs/openmontage/audit/EVIDENCE_CID_PRIMARY_DOCS.md` (new)
- `docs/openmontage/audit/REVIEW_QUEUE.md` (appended CID section)
- `docs/openmontage/audit/C4_CID_FOCUS_REPORT.md` (new — this report)
- `docs/OPENMONTAGE_WORK_LOG.md` (append dated C4 entry — committed with this report)

**Tests actually run:** none (docs/report only; archive.org metadata API observed working; asset downloads observed blocked — 0 bytes / HTML; ffmpeg contact-sheet not generated due to blocked downloads).

**Budget / provider verification:** strict $0 held. archive.org metadata API worked (keyless); archive.org asset downloads blocked (not a key issue — access blocked); NTRS persistent network ERROR (not key-related). No paid API call, generation, upload, publish. No installs.

**Git status / user changes preserved:** tree clean at start; only agent docs staged; no destructive commands, no force-push.
