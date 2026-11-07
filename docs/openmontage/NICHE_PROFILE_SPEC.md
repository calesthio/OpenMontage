# Niche Profile Spec — Aviation & Spaceflight Test History (SPEC ONLY)

**Status:** spec only, no implementation.
**Niche:** Aviation & spaceflight test history on free / public-domain archive footage.
**Binding rule:** the niche MUST be CONFIG (`niche_profile.yaml`), not hardcoded in code.

## 1. Purpose

Define the schema of `niche_profile.yaml` so a later milestone can implement
validation, viability gating, and added-value gating without guessing the
contract. Nothing in this file executes anything.

## 2. File location (convention, not created here)

- `projects/<project-id>/niche_profile.yaml` (per-project), or
- `configs/niches/aviation_spaceflight_test_history.yaml` (shared preset).

The runner loads exactly one profile per run. Unknown fields fail closed.

## 3. Schema of `niche_profile.yaml`

```yaml
version: "1.0"                       # string, required, const "1.0"
niche_id: aviation_spaceflight_test_history  # string, required, slug
display_name: "Aviation & Spaceflight Test History"  # string, required

# --- 3a. Allowed sources + per-source storage policy ---
allowed_sources:                   # list, required, min 1
  - name: nasa                     # must match a registered stock adapter name
    storage_policy: per_project_asset
  - name: nara
    storage_policy: per_project_asset
  - name: archive_org
    storage_policy: per_project_asset
  - name: wikimedia
    storage_policy: per_project_asset
  - name: loc
    storage_policy: per_project_asset
  - name: pond5_pd
    storage_policy: temporary_cache

# storage_policy enum (per source, required):
#   query_only        — search/browse metadata only; do not persist files or embeddings.
#   per_project_asset — download once into the project corpus with full provenance.
#   temporary_cache   — short-lived cache only; evict after the run; never a permanent base.
#   needs_permission  — blocked until written permission terms are recorded in the artifact.

# --- 3b. Excluded content (hard reject at footage/editorial) ---
excluded_content:                  # list, required
  - fatalities                     # any fatal accident depiction
  - graphic_crash_footage          # graphic impact / wreckage close-ups
  - identifiable_private_persons_without_clearance  # private persons, no clearance on file

# --- 3c. Required primary document types ---
required_primary_doc_types:        # list, required, min 1
  - NASA_NTRS                      # NASA Technical Reports Server
  - FAA                            # FAA reports / ADs / accident dockets as applicable
  - NTSB                           # NTSB reports / dockets as applicable

# --- 3d. Viability gate (configurable, checked before script/compose) ---
viability_gate:
  min_licensed_video_clips: 10     # integer >= 0, default 10
  min_primary_docs: 3              # integer >= 0, default 3
  # "licensed" means: asset has provider, original_url, author where exposed,
  # license + license_url, and qa_verdict != reject_license.

# --- 3e. Added-value gate (INITIAL GUESSES — tune after human review) ---
# These are NOT YouTube thresholds. They are editorial starting points to
# prevent a slideshow of unannotated archive clips.
added_value_gate:
  min_narration_coverage: 0.90          # narration on >= 90% of runtime
  min_original_diagrams_per_90s: 1      # >= 1 original diagram/chart per 90 s
  max_unannotated_archive_clip_s: 20    # no unannotated archive clip > 20 s
  max_still_only_sequence_s: 15         # still-image-only sequence <= 15 s
  claim_source_card_policy: every_claim # every claim has an on-screen source card or credits entry

# --- 3f. Episode templates (>= 3 distinct structures) ---
episode_templates:                 # list, required, min 3
  - id: test_campaign_chronology
    description: "One test campaign start-to-finish: goal, vehicle, test points, anomaly, outcome, lesson."
  - id: incident_anatomy
    description: "One incident: timeline, primary docs, what the test revealed, what changed after."
  - id: machine_biography
    description: "One airframe/vehicle across its test life: variants, records, retirements, legacy."
  - id: requirement_to_runway
    description: "One requirement: why it existed, competing designs, test evidence, winner and cost."
```

## 4. Validation rules (for the future implementer)

1. `allowed_sources[].name` must resolve via `get_source(name)`; unknown name → BLOCKED.
2. `storage_policy` must be one of the four enum values; missing → BLOCKED.
3. `excluded_content` matches are reject reasons at footage (`license_rejected`-style
   taxonomy extended with `excluded_content`) and at editorial.
4. `viability_gate` counts use only assets with `qa_verdict == pass`; failure → stage BLOCKED.
5. `added_value_gate` is measured on the timeline (`edit_decisions` + final file),
   never on a class or a checkpoint flag.
6. Profile file itself is checksummed into `research_brief` / `asset_manifest` metadata.

## 5. Explicit non-goals

- No adapter code, no downloader, no schema change, no pipeline wiring in this spec.
- No claim that the listed archives hold enough licensable clips — that is what
  the viability gate is for at runtime.
