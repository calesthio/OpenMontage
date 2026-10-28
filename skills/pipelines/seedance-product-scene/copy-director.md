# Copy Director — Three Codex Copy Variants

## Inputs

Required final `asset_manifest`; use the original brief and approved scenes.

## Generation

Generate copy with the active Codex model. Do not call Ark or another text API.
For every selected style produce:

- `grassroots`: 种草型, conversational, suitable emoji, clear CTA.
- `premium`: 高级型, restrained, lifestyle and quality.
- `conversion`: 详情页转化型, benefits, audience, use case, purchase reason.

Each variant has one title, one subtitle, 3–4 highlights, and one social post.
Use only supplied product facts. Put unresolved or inferred context in
`assumptions`; remove unsupported claims.

## Artifact

Write schema-valid `product_copy` with
`generation_source="codex_active_session"`.

## Approval

Present all three variants per style. Offer:

1. Keep all three.
2. Revise one variant.
3. Rewrite all variants.
4. Return to video review.

停止并等待用户审批，不要进入音乐下载。
