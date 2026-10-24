# Scene Director — Style Preview and Storyboard

## Inputs

Required: `proposal_packet`.

## Style Preview

Call `seedream_ark_image` once per style with `count=1`:

- `luxury`: marble, warm gold light, quiet home; slow push.
- `nature`: plants, dappled sunlight, breeze; slow lateral move.
- `tech`: dark space, blue-violet neon, scan light; controlled rotation.
- `office`: clean desk, daylight, laptop; stable lateral move.

Use direct Chinese prompts and the product lock from the Layer 3 skill.
Save under `assets/images/previews/<style>/batch-001/`. Record model, prompt,
and paths in `asset_manifest`. Use the next `batch-NNN` directory when
regenerating; never overwrite a reviewed preview.

After generation, present all four images and ask the user to choose complete
styles. Use 4 choices: luxury, nature, tech, office. Allow 1–3 selections.
Never generate a complete style before this approval.

## Storyboard

For each selected style, write `scene_plan` with exactly three shots:

- 0–3 seconds: detail close-up;
- 3–6 seconds: approved use scene;
- 6–8 seconds: hero product still.

Specify product lock, camera motion, lighting, physics, and
`AUDIO: no music, no dialogue, no sound effects` for each scene.

## Approval

Summarize the selected styles and three-shot plan. Give 3 choices:

1. Approve and generate three image candidates per style.
2. Adjust one storyboard.
3. Return to style selection.

停止并等待用户审批，不要继续生成完整图或视频。
