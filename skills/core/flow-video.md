# Flow Video Skill

## When to Use

Use `flow_video` when the machine has a paid Google Flow subscription and a browser to
drive — especially when **no video provider API key is configured at all**. It is the
only video provider in the registry that costs no money.

Do **not** reach for it when a keyed provider is available and the job is a batch. It runs
one clip at a time through a browser tab, needs a human's Chrome to be awake, and spends a
daily credit allowance that does not refill on demand.

## Tool

| Tool | Provider | Model | Cash cost | Real cost |
|------|----------|-------|-----------|-----------|
| `flow_video` | `flow` | Veo 3.1 (Lite/Fast/Quality) or Omni 1.1 Flash | $0.00 | Google Flow credits — Veo ~10, Omni ~7 per clip; one at a time, ~2 min each |

Selection is automatic: `video_selector` discovers any tool with
`capability = "video_generation"`, so call the selector rather than this tool directly
unless you specifically want to force the subscription path.

## Choosing Between Video Providers

| Situation | Pick |
|---|---|
| No video API key configured anywhere | `flow_video` |
| Need 10+ clips for one video | a keyed provider (`seedance_video`, `veo_video`, `kling_video`); if none, warn about credits before proceeding |
| Need Veo 3 specifically and a key exists | `veo_video` — same model, no browser dependency |
| Unattended or CI run | never `flow_video` — it needs a signed-in Chrome started with a debugging port |
| Need to control clip length or resolution | `model_variant: Omni` — the Veo tiers expose neither |
| User explicitly wants zero spend | `flow_video` |
| Need synced native audio at no cash cost | `flow_video` |

## Preflight

```bash
python -c "from tools.tool_registry import registry; registry.discover(); \
  print(registry.support_envelope()['flow_video']['status'])"
```

- `available` — Playwright is installed
- `unavailable` — Playwright is not installed; see `install_instructions` on the tool

`available` means **installed**, not **ready**. Readiness — Chrome running with a
debugging port, signed in to Flow — is checked when the tool actually runs, and a
failure there comes back as a structured blocker naming the exact next step. This split is
deliberate: `video_selector` silently drops any provider that is not `AVAILABLE`, so a
liveness check in `get_status()` would hide the provider on every machine where Chrome
happens to be closed, and the user would never be told to start it.

To check readiness before proposing a plan:

```bash
curl http://127.0.0.1:9222/json/version
```

A JSON answer means a Chrome is attachable. Being *signed in* is checked when the
tool runs, and reported as a blocker naming the next step.

## Setup (three parts, all local)

1. `pip install playwright`
2. `python scripts/flow_chrome.py` (or double-click `flow-chrome.cmd`)

   It launches Chrome on a dedicated profile at `~/.openmontage/chrome-flow`.
   That separate `--user-data-dir` is required, not preferred: since Chrome 136
   the debugging port is silently ignored on the default profile.

3. Sign in to <https://labs.google/fx/tools/flow> once in that window.

The profile keeps the session indefinitely. **Opening Chrome from the normal
shortcut uses the default profile instead** — a different browser as far as
Google is concerned — which looks exactly like the session was lost. Always
start it through the launcher, and check with:

```bash
python scripts/flow_chrome.py --check
```

Point the tool at a specific project with `FLOW_PROJECT_URL`, or let it create one.

## Cost Communication (binding)

`estimate_cost()` returns `0.0`, which is true about money and misleading about cost.
Whenever you put `flow_video` in a proposal, state both halves:

> Sinh video: $0.00 tiền mặt — dùng credit subscription Google Flow, ~2 phút/clip.
> 6 clip 8 giây ở mức Quality ≈ tiêu phần lớn hạn mức credit trong ngày.

Never present it as unlimited free capacity. Unlike an API balance, a spent daily
allowance cannot be topped up — running out ends video generation until reset.

Also tell the user, once, that automating Flow may violate Google's terms of service and
carries a risk of account suspension. State it and move on; do not repeat it per clip.

## Planning Around It

- **Sample before batching.** Generate one clip at `Fast`, get approval, then spend
  `Quality` credits on the rest. This matters more here than with a keyed provider,
  because a wasted batch cannot be bought back.
- **Ask for the delivery aspect ratio directly** (`9:16` for shorts) rather than
  generating `16:9` and cropping — Veo composes for the frame it is given.
- **Never plan a fallback that silently swaps to a paid provider.** If credits run out
  mid-run, surface the blocker and let the user choose, per the Decision Communication
  Contract in AGENT_GUIDE.md.

## Layer 3

Read [`.agents/skills/flow-video/SKILL.md`](../../.agents/skills/flow-video/SKILL.md)
before writing any prompt — it carries the prompt shape, the model/duration/resolution
matrix Flow actually offers, and the browser-specific failure-mode table. Its
[`references/flow-api.md`](../../.agents/skills/flow-video/references/flow-api.md)
maps Flow's internal API and marks which calls are behind bot detection.

## Related

- [codex-image.md](codex-image.md) — the same subscription-not-API economics, for stills
- `veo_video` — the same model through a paid API, when a key exists
- `video_compose` / `auto_reframe` — composing and reframing the generated clips
