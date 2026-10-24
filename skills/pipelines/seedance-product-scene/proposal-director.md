# Proposal Director — Preview and Production Plan

## Inputs

Required: `brief`.

## Proposal

Explain the fixed production shape:

- four style previews, one image each;
- user selects 1–3 complete styles;
- three scene images, one 8-second 9:16 video, three copy variants, and one approved music track for each selected style;
- three-shot sequence: detail, use scene, hero still;
- no burned text, subtitle, CTA, or logo.

Show known costs and mark unknown Seedance image pricing as “需要报价”.
For Seedance 2.5 video, record the user-confirmed ARK quote in CNY per million
completion tokens in the proposal and decision log. If no quote exists, stop
before paid video generation.
Ask the user to approve preview spend before any paid request.

## Runtime Contract

Because the approved output has no overlays, recommend `render_runtime="ffmpeg"`
for audio muxing and validation. If both runtimes are available and the user
changes the brief toward text or motion graphics, **Present both** Remotion and
`hyperframes` before choosing. Record the full shortlist in a
`render_runtime_selection` decision. Never silently choose Remotion.

## Output

Write `proposal_packet` and `decision_log`. Include concept options, selected
style range, storyboard, video parameters, copy plan, music plan, cost, and the
runtime decision.

## Approval

Present 3 choices:

1. Generate four style previews (recommended).
2. Adjust product facts or budget.
3. Stop before paid generation.

Write `awaiting_human` and end the turn. 停止并等待用户审批。
