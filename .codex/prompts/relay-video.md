# /relay-video — media + loose brief → finished video through your relays

The user wants a finished video from their material, produced through their configured relays: <your material + brief>

1. Read `AGENT_GUIDE.md` (mandatory), then `.agents/skills/relay-providers/SKILL.md` and `skills/core/relay-providers.md`.
2. Run `python -m tools.relay check` and `python -m tools.relay list`. Report config errors, missing env vars and `live: false` relays verbatim — never print or ask the user to paste key values into chat.
3. Treat the supplied media as the brief: follow `skills/meta/creative-intake.md` → "Handling Open, Media-Led Briefs". Analyze every file, infer duration / aspect / tone / shot list / transitions / music / narration, and pick a declared-capable relay model per shot. Ask at most one blocking question.
4. Go through the `cinematic` pipeline (Rule Zero): init the project, preflight, proposal with cost from `estimate_cost`, then stage by stage with checkpoints, review and approval gates. Show a `dry_run` of the first paid request before the first sample.
5. Generate with `preferred_tool` pinned to the approved relay tool and a local first frame where the shot animates a photo. A `pending` result is resumed by calling again — never resubmitted. Never switch to another paid vendor without approval.
6. Compose with `video_compose` / `audio_mixer`, review, and deliver `projects/<id>/renders/final.mp4` with a cost summary.
