# Reference Video Analysis — Package Director

Build the human-editable replication package.

Use `reference_video_package` to combine `reference_source`, `reference_analysis`, and `reference_transcript` into JSON plus Markdown. The package must include transcript, rewrite draft, scene table, keyframes, pacing notes, and a recommended production mode: `direct_face_swap`, `full_remake`, or `hybrid`.

If the user wants to adjust copy or prompts before review, use `reference_text_edit` to update `rewrite_draft.text`, `scenes[].production_inputs.script_text`, and `scenes[].production_inputs.seedance_prompt`. Keep the package in `pending_human_review` after editing; text editing is not approval.

If a configured visual understanding provider is available, use `reference_prompt_reverse` before manual text edits to analyze keyframes and reverse-engineer editable Seedance prompts. For Doubao, this uses `doubao_vision_understand` through the configured Volcengine Ark/OpenAI-compatible endpoint. Keep the package in `pending_human_review`; prompt reverse is not production approval.

If the user provides team-owned face, product, brand, or background files before review, use `reference_asset_binding` to import them into the project and bind them to the relevant scene `production_inputs.selected_assets`. Keep the package in `pending_human_review` after binding; asset binding is not approval.

Set `approval.status = pending_human_review`. Do not start face replacement, digital-human generation, Seedance generation, or final composition in this stage.
