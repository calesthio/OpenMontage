# Codex Image Skill

## When to Use

Use `codex_image` when the machine has a signed-in Codex CLI on a paid ChatGPT plan and
you need AI-generated stills — especially when **no image provider API key is configured
at all**. It is the only image provider in the registry that costs no money.

Do **not** reach for it when a keyed provider is available and the job is a batch. It is
an order of magnitude slower and it spends the user's coding quota.

## Tool

| Tool | Provider | Model | Cash cost | Real cost |
|------|----------|-------|-----------|-----------|
| `codex_image` | `codex` | `gpt-image-2` | $0.00 | ChatGPT subscription quota, 30–60s per image |

Selection is automatic: `image_selector` discovers any tool with
`capability = "image_generation"`, so call the selector rather than this tool directly
unless you specifically want to force the subscription path.

## Choosing Between Image Providers

| Situation | Pick |
|---|---|
| No API key configured anywhere | `codex_image` |
| Need 10+ images for one video | a keyed provider (`flux_image`, `seedream_image`); if none, warn about quota before proceeding |
| Image must contain accurate text | `codex_image` or `openai_image` (same model), or `recraft_image` |
| Need an exact non-standard aspect ratio | keyed provider — `codex_image` has only three sizes |
| User explicitly wants zero spend | `codex_image` |

## Preflight

```bash
python -c "from tools.tool_registry import registry; registry.discover(); \
  print(registry.support_envelope()['codex_image']['status'])"
```

- `available` — signed in with ChatGPT, bills subscription
- `degraded` — signed in with an API key; generation bills API credit instead. Tell the
  user before spending
- `unavailable` — `codex` not on PATH or `auth.json` unreadable → `codex login`

## Cost Communication (binding)

`estimate_cost()` returns `0.0`, which is true about money and misleading about cost.
Whenever you put `codex_image` in a proposal, state both halves:

> Sinh ảnh: $0.00 tiền mặt — dùng quota Codex subscription, ~40s/ảnh.
> 6 ảnh ≈ tiêu một phần đáng kể quota 5 giờ.

Never present it as unlimited free capacity.

## Layer 3

Read [`.agents/skills/codex-image/SKILL.md`](../../.agents/skills/codex-image/SKILL.md)
before writing any prompt — it carries the gpt-image-2 prompt shape, the three valid
sizes, and the failure-mode table.

## Related

- [remotion.md](remotion.md) — composing the generated stills
- `auto_reframe` / `video_compose` — cropping 1024×1536 up to a true 1080×1920
