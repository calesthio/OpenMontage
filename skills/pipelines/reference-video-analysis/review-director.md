# Reference Video Analysis — Review Director

Guide the human review before downstream production.

Ask the user to edit the rewrite draft, confirm scene notes, choose a production mode, and confirm that any face or avatar asset used later is team-authorized. The review decision can be `approved`, `approved_with_changes`, or `rejected`.

Only approved or approved_with_changes packages can feed direct face replacement, full remake, or hybrid creator-video production.

Use `reference_review_approval` after the human finishes editing the JSON package. It requires the exact approval phrase `APPROVE REFERENCE PACKAGE`, a reviewer identity, non-empty scene script text, Seedance prompts for Seedance/hybrid targets, and team-authorized selected assets. This tool writes an approved package copy only; it does not call Seedance, digital-human APIs, face replacement, or composition tools.

After approval, use `reference_production_plan` on the approved package to validate the edited package and write a `production_plan` handoff. This validates editable script text, Seedance prompts, selected uploaded assets, and Seedance constraints (`4`-`15` seconds, `480p`/`720p`, max batch size `5`). It must not call Seedance, digital-human APIs, face replacement, or composition tools.

Then use `seedance_batch` in dry-run mode to create `seedance_batch_preview`. This lists the exact provider tool, prompt, duration, resolution, reference image paths, and output path for each clip in the first batch. Keep `dry_run=true` until the user explicitly approves paid generation.

If the user approves a paid sample, run only one Seedance task first with `allow_paid_generation=true`, `sample_only=true`, and `approval_phrase="RUN SEEDANCE SAMPLE"`. Announce the provider tool, model variant, and that it is a single paid sample before execution. Do not execute the rest of the batch until the sample clip is reviewed.
