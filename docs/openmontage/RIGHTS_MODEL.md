# Rights Model — OpenMontage Milestone C1 (v2)

**Status:** docs/report only. No application code, no installs, no process/lock changes.
**Accessed:** NASA Images and Media Usage Guidelines, https://www.nasa.gov/nasa-brand-center/images-and-media/, 2026-10-17 (orchestrator fetch).

## 1. Source (orchestrator paraphrase)

Default: NASA content (images, audio, video, media files) is generally NOT subject to copyright in the United States. Free for educational/informational use; NASA should be acknowledged as source; factual use that does not imply endorsement needs no explicit permission.

Exceptions (rights restrictions):
- NASA Insignia ("meatball"), Logotype ("worm"), identifiers and imagery are NOT public domain — use protected by law.
- Third-party copyrighted material NASA uses with permission — marked with the copyright holder's name; NASA's use conveys no rights to others; contact the copyright holder directly.
- Identifiable persons — commercial use may infringe privacy/publicity rights; permission needed from the person. Current NASA employees' names/likenesses/position titles cannot be used on commercial products. Retired astronauts may grant permission at their discretion. Deceased — estates may retain rights.
- Commercial/promotional content cannot be filmed on NASA property; must not convey NASA endorsement.
- NFTs/cryptocurrency not permitted.
- AI: attribution to NASA not permitted; NASA insignia cannot appear with AI-generated imagery; do not imply NASA review/permission.

## 2. rights_basis enum

`rights_basis` ∈ {`explicit_license`, `source_policy_us_gov`, `unknown`}

## 3. Fail-closed classification rules

### source_policy_us_gov (US government work, no separate license needed)
Granted ONLY when ALL of the following hold, based on the item's own metadata:
1. The item is NASA-produced per its own metadata (`creator`/`center` is a NASA center or "NASA").
2. No third-party credit ("courtesy of", "credit: <non-NASA>", copyright notice) in the credit/description fields.
3. No per-item restriction text (no "copyright protected", no license-limiting statement, no "rights reserved").

If any condition fails, do NOT classify as source_policy_us_gov.

### explicit_license
The item carries an explicit, machine-readable license statement in its metadata (e.g. `licenseurl`, `rights: "Public Domain"`, `licenseurl: "CC-BY 4.0"`, Commons license tag). Record the exact license text and URL as evidence.

### unknown (default / fail-closed)
Any item that does not satisfy source_policy_us_gov OR explicit_license. `unknown` => NOT USABLE. No clip with `rights_basis == unknown` may enter the timeline.

## 4. Flags

- `identifiable_persons`: UNKNOWN unless reviewed. Unreviewed => NEEDS_REVIEW, not usable.
- `logo_visible`: UNKNOWN unless reviewed. Unreviewed => NEEDS_REVIEW, not usable.
- `third_party_credit`: set from metadata when present (e.g. "courtesy of", uploader name, re-uploader).
- A flag marked UNKNOWN is not a pass; it is a hard NEEDS_REVIEW block until frame/pixel review.

## 5. Evidence recording

For every asset record, record:
- `rights_basis` value
- `confidence` (high/medium/low)
- exact metadata fields used as evidence (e.g. `creator`, `rights`, `licenseurl`, `description`)
- the source URL where the metadata was observed
- flags with their review state

## 6. Usability verdict

| rights_basis | flags reviewed? | verdict |
|---|---|---|
| explicit_license | all reviewed, no blocking flag | USABLE |
| source_policy_us_gov | all reviewed, no blocking flag | USABLE |
| explicit_license / source_policy_us_gov | any flag UNKNOWN | NEEDS_REVIEW |
| unknown | any | REJECT (not usable) |

NEEDS_REVIEW clips are listed separately and do NOT count toward the stage 0 viability gate.
