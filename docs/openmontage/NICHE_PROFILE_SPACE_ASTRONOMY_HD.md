# Niche Profile Spec — Space & Astronomy on HD Public-Domain Footage (SPEC ONLY)

**Status:** spec only, no implementation. Created 2026-10-19 (Milestone K).
**Niche:** Space & astronomy on HD public-domain footage.
**Binding rule:** the niche MUST be CONFIG (`niche_profile.yaml`), not hardcoded in code.

## 1. Purpose

Define the schema of a `niche_profile.yaml` for a space & astronomy niche built from HD (>=720p) public-domain footage, so a later milestone can implement validation, viability gating, and added-value gating without guessing the contract. Nothing in this file executes anything.

## 2. File location (convention, not created here)

- `projects/<project-id>/niche_profile.yaml` (per-project), or
- `configs/niches/space_astronomy_hd.yaml` (shared preset).

The runner loads exactly one profile per run. Unknown fields fail closed.

## 3. Schema of `niche_profile.yaml`

```yaml
version: "1.0"                           # string, required, const "1.0"
niche_id: space_astronomy_hd             # string, required, slug
display_name: "Space & Astronomy (HD Public-Domain Footage)"  # string, required

# --- 3a. Allowed sources + per-source storage policy ---
allowed_sources:                         # list, required, min 1
  - name: nasa                           # NASA Image and Video Library (images-api.nasa.gov)
    storage_policy: per_project_asset
  - name: nasa_svs                       # NASA Scientific Visualization Studio (svs.gsfc.nasa.gov)
    storage_policy: per_project_asset
  - name: esa_hubble                     # ESA/Hubble (www.spacetelescope.org; rights allow per ESA/Hubble terms)
    storage_policy: per_project_asset
  - name: archive_org                    # Internet Archive (Moving Image / Prelinger / stock_footage)
    storage_policy: per_project_asset
  - name: wikimedia                      # Wikimedia Commons
    storage_policy: per_project_asset

# storage_policy enum (per source, required):
#   query_only        — search/browse metadata only; do not persist files or embeddings.
#   per_project_asset — download once into the project corpus with full provenance.
#   temporary_cache   — short-lived cache only; evict after the run; never a permanent base.
#   needs_permission  — blocked until written permission terms are recorded in the artifact.

# --- 3b. Excluded content (hard reject at footage/editorial) ---
excluded_content:                        # list, required
  - identifiable_private_persons_without_clearance  # private persons, no clearance on file
  - third_party_credit_not_usable       # third-party credit present => rights_basis unknown => REJECT
  - nasa_insignia_with_ai_imagery       # NASA insignia cannot appear with AI-generated imagery

# --- 3c. Required primary document types ---
required_primary_doc_types:              # list, required, min 1
  - NASA_NTRS                            # NASA Technical Reports Server (primary mission/science docs)
  - ESA                                  # ESA science/release pages (primary source for ESA/Hubble material)

# --- 3d. Viability gate (configurable, checked before script/compose) ---
viability_gate:
  min_licensed_video_clips: 10           # integer >= 0, default 10
  min_primary_docs: 3                    # integer >= 0, default 3
  min_resolution: 720p                   # clips must be >=720p HD
  # "licensed" means: asset has provider, original_url, author where exposed,
  # license + license_url, and qa_verdict != reject_license.

# --- 3e. Added-value gate (INITIAL GUESSES — tune after human review) ---
# These are NOT YouTube thresholds. They are editorial starting points to
# prevent a slideshow of unannotated archive clips.
added_value_gate:
  min_narration_coverage: 0.90           # narration on >= 90% of runtime
  min_original_diagrams_per_90s: 1       # >= 1 original diagram/chart per 90 s
  max_unannotated_archive_clip_s: 20     # no unannotated archive clip > 20 s
  max_still_only_sequence_s: 15          # still-image-only sequence <= 15 s
  claim_source_card_policy: every_claim  # every claim has an on-screen source card or credits entry

# --- 3f. Episode templates (>= 3 distinct structures) ---
episode_templates:                       # list, required, min 3
  - id: mission_chronology
    description: "One space mission start-to-finish: goal, spacecraft, milestones, outcome, legacy."
  - id: discovery_anatomy
    description: "One astronomical discovery: observation, instrument, what it revealed, what changed after."
  - id: spacecraft_biography
    description: "One spacecraft/telescope across its life: variants, records, retirement, legacy."
  - id: concept_to_orbit
    description: "One concept: why it existed, competing designs, test evidence, winner and cost."

## 4. Validation rules (for the future implementer)

1. `allowed_sources[].name` must resolve via `get_source(name)`; unknown name → BLOCKED.
2. `storage_policy` must be one of the four enum values; missing → BLOCKED.
3. `excluded_content` matches are reject reasons at footage (`license_rejected`-style taxonomy extended with `excluded_content`) and at editorial.
4. `viability_gate` counts use only assets with `qa_verdict == pass`; failure → stage BLOCKED.
5. `added_value_gate` is measured on the timeline (`edit_decisions` + final file), never on a class or a checkpoint flag.
6. Profile file itself is checksummed into `research_brief` / `asset_manifest` metadata.

## 5. Rights notes (RIGHTS_MODEL.md applied)

- NASA SVS and NASA Image and Video Library content is generally `source_policy_us_gov` (NASA public domain) when the item is NASA-produced per its own metadata, has no third-party credit, and no per-item restriction text.
- ESA/Hubble material: classify per the ESA/Hubble copyright/terms observed on each item's page; `explicit_license` only when an explicit license statement is present, else `unknown` => NOT USABLE.
- archive.org: `source_policy_us_gov` / `explicit_license` per item `licenseurl`/`rights` metadata; `unknown` (typically none stated) => NOT USABLE until verified.
- Wikimedia Commons: `explicit_license` per-file license tag; attribution required per license.
- `third_party_credit` = REJECT per RIGHTS_MODEL.md §3.

## 6. Explicit non-goals

- No adapter code, no downloader, no schema change, no pipeline wiring in this spec.
- No claim that the listed archives hold enough licensable HD clips — that is what
  the viability gate is for at runtime.
