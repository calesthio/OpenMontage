# yt-script — OpenMontage local adaptation (binding)

Upstream skill files (`SKILL.md`, `hookscore.py`, `hooks.json`) are vendored
verbatim from `Jakeschincariol/youtube-agent-skill` at pinned commit
`a2feb21` (see `docs/openmontage/TOOLING_DECISIONS.md`). This file adds
factory rules that OVERRIDE upstream where they conflict. Upstream guidance
applies only insofar as it does not contradict the following:

1. **Every factual sentence must reference a real `claim_id` from the run's
   evidence ledger.** A script line that asserts a fact without a resolving
   `evidence_id`/`claim_id` (checked by `lib/artifact_ids.resolve_all`) fails
   the script stage. "Never invent a number" (upstream) is necessary but not
   sufficient — sourced numbers must also resolve to the ledger.
2. **Hook scores are heuristics, not forecasts.** `hookscore.py` verdicts
   (SPECIFICITY/ADDRESS/STAKES/CURIOSITY/BREVITY bands) describe surface
   properties of a line. They predict nothing about views, CTR, or retention.
   Never report a score as an expected outcome; report it as a lint signal
   ("look again", never "this will perform").
3. **Voice profile path:** upstream reads `~/.claude/youtube/voice.md` when
   present. In this factory the narration voice is locked per-run in
   `narration_manifest` (`provider`, `model`, `voice_license`); no home-directory
   voice file is required and none is read by the pipeline.
4. **Nothing here publishes.** Preserved from upstream: every output ends in a
   user-copyable block ending with "ship it, or change it?". Publish remains
   manual per the master plan.
