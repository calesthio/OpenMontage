# OpenMontage Reference-to-Script Contract v1.1

## Purpose

OpenMontage uses a reference video to produce an original, grounded production. The
contract preserves what was observed, what was inferred, what the user decided, and
what later stages must render. It is not a claim that any one story template is
universally correct.

## Layer model

```text
reference source(s)
  -> video_analysis_brief@1.1       observed and evidence-linked reference facts
  -> brief/proposal_packet@1.1      adaptation intent and approved direction
  -> script@1.1                     timed narrative and semantic AV decisions
  -> scene_plan@1.1                renderable visual timeline
  -> assets/edit/compose            production execution
```

`video_analysis_brief` is one artifact per analyzed source. Multiple source analyses may
travel in a `video_analysis_bundle@1.1`; their observations are not silently merged into
one undifferentiated claim. Proposal/script/scene artifacts cite the source analysis IDs
that actually inform them.

## Assertion discipline

Every meaningful statement belongs to one of three classes:

- `observed`: directly supported by media, transcript, metadata, or a tool result;
- `inferred`: an interpretation such as audience, hook mechanism, or why a choice may
  work; it must cite evidence and carry confidence;
- `recommended`: an adaptation or production decision; it must cite the observation or
  interpretation that motivated it.

Unknown values are not negative findings. Use `unknown` when the analyzer did not have
sufficient evidence. Use `not_applicable` only when the aspect genuinely does not apply.
Never silently omit a required five-aspect field.

## Evidence index

The v1.1 analysis artifact contains an `evidence` index. Evidence entries have stable
IDs, a kind, availability status, and a source locator. When applicable they carry a
start/end range and scene index. Keyframes and transcript segments receive stable IDs
and corresponding evidence entries. In a multi-source bundle, an ambiguous local ID is
qualified as `analysis_id#evidence_id`.

Evidence is provenance, not permission to copy. Reference-driven generation must still
make preserve/change/avoid decisions and remain meaningfully differentiated.

Rights and privacy are explicit unknowns by default. The analyzer records
`rights_status: unknown`, `privacy_status: review_required`, and
`retention_policy: caller_managed`; it does not grant permission, infer consent, or
claim that redaction occurred. A later authorized review may replace those values.

## Five visual aspects

Each detected scene receives exactly one status-bearing observation for each aspect:

1. `subject`
2. `subject_motion`
3. `scene`
4. `spatial_framing`
5. `camera`

The analyzer emits an explicit low-confidence `unknown` scaffold. The vision-enrichment
step may replace it with `observed` or `inferred` content and evidence references. A
scene-bearing run remains `partial` until that enrichment step is recorded; a valid but
empty schema object must never pretend that the reference was fully understood.

The five-aspect vocabulary is a project-local observation vocabulary. It is not a
narrative framework, a rights model, or an editing interchange format.

## Framework composition

Narrative profiles are versioned and composable. Examples:

- `explainer_arc@1`
- `but_therefore@1`
- `guided_discovery@1`
- `short_form_hook_value_payoff@1`
- `long_form_chapter_arc@1`
- `source_segment_selection@1`

A script can reference more than one profile. Beat roles are namespaced strings such as
`explainer_arc/hook`; there is no universal beat enum. Profiles define criteria and
role mappings, while the artifact contract defines identity, timing, evidence, and
handoff semantics.

Platform and review profiles are separate from narrative profiles. A short-form
profile may inspect first-frame hook, early pacing, captions, payoff, and loop behavior;
a long-form profile may inspect chapters, re-hooks, proof, and landing. These are
criteria over the shared analysis artifact, not separate lineage systems.

## Handoff rules

Reference-driven v1.1 downstream artifacts carry `reference_analysis_refs` containing
the attached analysis IDs. This requirement applies only to reference-driven outputs;
original work may carry optional analysis context without declaring lineage. A checkpoint
that carries a reference-driven v1.1 artifact must carry the referenced v1.1 analysis
artifact or `video_analysis_bundle@1.1` as well, so the IDs are resolvable without relying
on conversation context.

- Proposal concepts may carry their own reference and evidence refs. The selected concept's non-empty subset is the effective analysis lineage for downstream stages.
- Script sections carry plural `evidence_refs` and `source_refs`.
- Scene plans carry plural `script_section_ids` and may carry evidence refs.
- Script visual/audio intent is semantic; camera/framing/assets belong in scene plan.
- Timing overlap may help a display layer, but must not repair a dangling explicit ID.

## Versioning and migration

Legacy v1.0 schemas remain readable and unchanged. The loader dispatches by the
artifact's `version` value. `migrate_artifact(name, data, target_version="1.1")` returns
a new object and never mutates the input.

Migration preserves legacy fields, creates deterministic IDs, and marks unavailable
legacy provenance as unavailable. It must not turn an old URL or prose string into
invented evidence. v1.1 writers should be used for new reference-driven artifacts;
legacy checkpoints can be dual-read and migrated at a controlled boundary.

## Deferred boundaries

The following are intentionally not v1.1 core contracts:

- a standalone format-pattern ontology;
- publishing, retention, or learning analytics;
- causal claims that a reference formula caused performance;
- full MPEG-7, EBUCore, PROV, C2PA, or NLE interchange conformance;
- screenplay exporters and external timeline adapters.

Borrow compatible vocabulary only when a concrete interoperability requirement exists.

## Acceptance gate

A v1.1 implementation is acceptable when fixtures prove:

- legacy v1.0 artifacts still validate;
- v1.1 analysis has source identity, evidence, IDs, and five-aspect coverage;
- observed and inferred claims cannot omit evidence;
- unknown and not-applicable remain explicit;
- inverted or out-of-range time ranges fail;
- downstream refs resolve within the checkpoint;
- two narrative profiles can consume the same analysis without mutation;
- proposal -> script -> scene plan retains analysis IDs and evidence refs;
- partial analysis is honest and persisted only after validation;
- one or more independently analyzed sources can be bundled without ambiguous evidence refs;
- migration is deterministic and preserves the v1.0 input;
- no analytics, format ontology, deployment, or paid provider is required.
