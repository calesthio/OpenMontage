# Pull Request Review Guide

This guide is for community reviewers, maintainers, and AI assistants reviewing
OpenMontage pull requests. It is a review framework, not a closed checklist.
Use it to structure the review, then keep looking for issues that are specific
to the PR in front of you.

OpenMontage is an agent-orchestrated video production system. Many PRs affect
more than the file they edit: a provider change can affect tool discovery,
selector routing, setup instructions, pipeline decisions, cost reporting, and
the user-visible production flow. Good reviews protect those contracts.

## Review Mindset

Start with these questions:

- Does this PR move OpenMontage in the right direction?
- Is the scope focused, or is it mixing unrelated changes?
- Can a user, maintainer, or agent understand the behavior after this lands?
- Does the PR preserve the agent-first architecture?
- Does it introduce regressions in provider discovery, pipeline artifacts, or
  rendering behavior?
- Are tests and docs updated at the same level as the behavior change?
- Are there security, privacy, dependency, or supply-chain concerns?

The answer can be "useful, but not merge-ready." That is a good review outcome
when the idea is aligned but the implementation needs cleanup.

## Review Outputs

A useful review should usually produce one of these outcomes:

- **Approve**: the PR is useful, focused, tested, and low-risk enough to merge.
- **Comment**: the PR is promising but needs cleanup before approval.
- **Request changes**: the PR has blockers that would create regressions,
  break contracts, or mislead users.
- **Close or redirect**: the PR is not aligned, mostly noise, or belongs in an
  issue/discussion before code.

Avoid rubber-stamp approvals. Also avoid turning every concern into a blocker.
Name the actual severity and explain the impact.

## General Review Areas

### Project Direction

Check whether the PR solves a real OpenMontage problem.

- Does it improve video production quality, reliability, speed, portability,
  provider coverage, local execution, docs, tests, or contributor experience?
- Does it duplicate an existing path without improving it?
- Is it a speculative feature with no clear user workflow?
- Does it introduce maintenance burden disproportionate to the value?

### Scope Hygiene

Noise makes reviews unsafe.

- Are unrelated files changed?
- Are lockfiles changed only when dependencies actually changed?
- Are generated files, screenshots, binary assets, or local artifacts included
  without reason?
- Are docs/test fixes bundled with feature work in a way that hides risk?
- Is the branch stale against latest `main`?

If a PR is useful but noisy, ask for a narrower diff before deep approval.

### Regression Risk

Look beyond the changed file.

- Does the change affect existing users or only add a new optional path?
- Does it alter default provider selection, fallback behavior, or setup menus?
- Does it change schemas, artifacts, or pipeline stage contracts?
- Does it change rendering output, timing, audio, captions, or file paths?
- Does it create silent fallback behavior where the user should be told?

### Security and Supply Chain

Review security issues factually and with evidence. Do not make public claims
about a contributor's intent. If you see suspicious code, describe the behavior
and risk.

Check for:

- New network calls, uploads, telemetry, or background processes
- Secret exfiltration risks, `.env` reads, token logging, or unsafe debug output
- Shell execution, `subprocess`, dynamic imports, `eval`, `exec`, or generated
  code execution
- Dependency additions, install scripts, package-lock churn, or broad version
  ranges
- Unsafe file deletion, path traversal, archive extraction, or writes outside
  the expected project directory
- Remote model downloads or provider calls that are not surfaced in metadata
- Prompt injection surfaces where external content could instruct the agent

Use language like:

- "I found a security blocker: this command executes user-controlled input."
- "This dependency change needs justification before merge."
- "I did not find an actionable security issue in the reviewed diff."

Avoid public phrasing like:

- "No malicious intent."
- "This author is safe."
- "This is definitely harmless."

### Performance and Resource Use

OpenMontage works with video, audio, image generation, and local models. Small
code changes can create large runtime costs.

- Does the PR add repeated model loads instead of reusing state?
- Does it download large files without clear setup/status messaging?
- Does it increase render time, memory, VRAM, disk, or network use?
- Does it change frame extraction, composition, encoding, or audio processing
  in a way that could slow common paths?
- Are resource profiles and cost estimates realistic?

## OpenMontage Architecture Checks

### Agent-First Architecture

OpenMontage's control plane is the agent following markdown skills and YAML
manifests. Python should provide tools and persistence, not hidden orchestration.

Flag PRs that:

- Add Python orchestrators for creative decisions, stage transitions, or review
  policy
- Hide provider/model/runtime decisions inside code without user visibility
- Bypass pipeline manifests, stage director skills, checkpoints, or review
- Move quality policy into ad hoc code instead of documented instructions

Good PRs keep intelligence in instructions and contracts, with Python handling
well-bounded execution.

### Tool Contract

Every tool should inherit from `tools/base_tool.py` and satisfy the `BaseTool`
contract.

For new or changed tools, review:

- `name`, `version`, `tier`, `capability`, `provider`
- `runtime`, `stability`, `execution_mode`, `determinism`
- `dependencies` using supported prefixes such as `cmd:`, `env:`, `python:`
- `install_instructions`
- `input_schema`, `output_schema`, and artifact behavior
- `supports`, `best_for`, `not_good_for`
- `resource_profile`
- `retry_policy`
- `fallback` and `fallback_tools`
- `agent_skills`
- `user_visible_verification`
- `estimate_cost()` and `estimate_runtime()` where relevant
- `execute()` returning a `ToolResult`

Metadata is user-facing. If setup, offline behavior, cost, model downloads, or
hardware requirements are inaccurate, the provider menu and agent planning will
mislead users.

### Tool Registry and Discovery

Tool discovery flows through `tools/tool_registry.py`. Avoid hardcoded tool
lists unless there is a strong reason.

Check:

- Does the tool register through normal package discovery?
- Does it use the right `capability` so selectors can find it?
- Does `get_status()` report availability accurately?
- Does an import failure in one optional provider break unrelated discovery?
- Does the provider menu show useful setup instructions?
- Does the PR accidentally make unavailable tools look configured?

Useful commands:

```bash
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.capability_catalog(), indent=2))"
python -c "from tools.tool_registry import registry; import json; registry.discover(); print(json.dumps(registry.provider_menu_summary(), indent=2))"
```

### Selectors and Providers

Selectors route capability-level requests to provider tools:

- `tts_selector`
- `image_selector`
- `video_selector`

When reviewing selector or provider changes:

- Confirm the provider has the correct `capability`.
- Confirm selector input names map to provider input names.
- Confirm provider-specific options do not get silently ignored.
- Confirm user preference is respected when explicit.
- Confirm unavailable providers do not block available alternatives.
- Confirm ranking/fallback changes are tested.
- Confirm the selector still returns useful alternatives and reasoning.

Adding a provider should usually not require selector code changes. If it does,
the PR should explain why.

### Pipeline Manifests and Stage Skills

Pipeline manifests live in `pipeline_defs/`. Stage instructions live in
`skills/pipelines/`.

For pipeline changes, check:

- Manifest schema validity
- Stage order and stage names
- `produces` artifacts
- `tools_available`
- `review_focus`
- `success_criteria`
- `checkpoint_required`
- `human_approval_default`
- Matching stage director skills
- Tests in `tests/contracts/` or `tests/pipelines/`

The manifest and the stage skill must agree. If the manifest says a stage
produces `scene_plan`, the director skill should actually guide creation of a
valid `scene_plan`.

### Canonical Artifacts and Schemas

Artifacts in `schemas/artifacts/` are contracts between stages.

When reviewing schema or artifact changes:

- Does every producer still write valid artifacts?
- Does every consumer still understand the artifact?
- Are required fields justified?
- Are migrations or backward compatibility needed?
- Do tests cover valid and invalid examples?
- Does the checkpoint protocol still work with the changed artifact?

Schema changes are high-impact. Treat them as cross-pipeline changes unless the
PR proves otherwise.

### Checkpoints and Review Policy

OpenMontage uses checkpoints for resume, human approval, audit trails, and
stage gating.

Check:

- Does the PR preserve checkpoint status semantics?
- Does it avoid skipping required human approval?
- Does it preserve cost snapshots and review metadata where expected?
- Does it avoid writing incomplete canonical artifacts as completed stages?
- Does it align with `skills/meta/checkpoint-protocol.md`?
- Does it align with `skills/meta/reviewer.md`?

Review logic should remain instruction-driven unless the PR is adding a narrow
mechanical validator.

### Composition Runtimes

OpenMontage can compose with Remotion, HyperFrames, or FFmpeg. Runtime choices
are user-visible production decisions.

For render/composition PRs, check:

- Does `video_compose` preserve explicit `render_runtime` routing?
- Are Remotion, HyperFrames, and FFmpeg paths considered where relevant?
- Does the PR avoid silent runtime swaps?
- Are runtime availability errors surfaced as blockers?
- Are Node, FFmpeg, `npx`, and package requirements checked accurately?
- Do render reports contain enough evidence to debug failures?
- Are browser previews treated as QA/debug artifacts when the production render
  path is different?

Silent downgrades from motion-led production to still-led fallback are review
findings, not harmless implementation details.

### Cost, Budget, and Paid Providers

OpenMontage should not silently spend money or imply a paid provider is free.

Check:

- Does the tool estimate cost accurately enough for planning?
- Are first-time paid provider uses visible to the user?
- Does the provider doc mention pricing/free-tier caveats?
- Does fallback from paid to free, or free to paid, require user visibility?
- Are model downloads, hosted endpoints, or cloud GPU usage described honestly?

### Docs and User-Facing Claims

Docs are part of the product. Provider setup docs often drive agent behavior.

Check:

- Does the PR update `docs/PROVIDERS.md` when adding a provider?
- Does `docs/ARCHITECTURE.md` need an update for architectural changes?
- Are setup instructions accurate on macOS, Windows, and Linux where claimed?
- Do docs distinguish API keys, local installs, model downloads, and cached
  offline operation?
- Are package versions and model versions clearly separated?
- Are limitations stated plainly?

## Scenario-Specific Review Prompts

### New Provider or Tool

Ask:

- Is this provider useful for OpenMontage workflows?
- Does it add real coverage or just duplicate an existing provider?
- Is the provider internationally known, nationally or regionally important,
  or otherwise clearly valuable to OpenMontage users?
- Is the tool discoverable through the registry?
- Does the matching selector discover and route to it?
- Are provider inputs compatible with selector inputs?
- Does status checking reflect real availability?
- Are setup docs, dependencies, cost, network, and cache behavior accurate?
- Does it have focused tests?
- Does it avoid importing heavyweight dependencies at module import time?
- Are generated artifacts written to expected paths?

Minimum expected coverage:

- Tool metadata/contract test
- Registry discovery test
- Status behavior test with dependencies mocked when needed
- Selector/routing test if it joins a selector-backed capability
- Docs update for user-visible providers

Provider viability matters. OpenMontage should not become a grab bag of
unmaintained or one-off integrations. A provider does not need to be globally
dominant, but it should have a clear reason to belong here.

Consider:

- Is there evidence of an active user base, maintained API docs, SDK support,
  or community adoption?
- Is it widely used internationally, or meaningfully popular in a specific
  national, regional, language, or industry market?
- Does it unlock a capability, language, price point, region, quality tier,
  compliance posture, or local/offline workflow that existing providers do not
  cover well?
- Are pricing, quotas, API access, model availability, and terms clear enough
  for contributors to test and maintain the integration?
- Is the provider likely to remain usable over the next six months?
- Does the provider's value justify the maintenance burden it adds?

### Selector Change

Ask:

- Does it still auto-discover providers?
- Does it avoid hardcoded provider lists?
- Does it preserve explicit user preference?
- Does it handle unavailable providers cleanly?
- Does it explain the selected provider?
- Does it preserve alternatives considered?
- Does it map shared inputs to provider-specific inputs?

### Local GPU or Model Runtime Change

Ask:

- Is the hardware requirement accurate?
- Does CPU/MPS/CUDA behavior match the implementation?
- Are dtype choices safe for each device?
- Are model downloads and cache behavior documented?
- Does the resource profile reflect realistic RAM, VRAM, and disk needs?
- Does setup avoid pretending local GPU install is a one-minute API-key fix?

### Render Runtime Change

Ask:

- Does it preserve runtime choice in `edit_decisions.render_runtime`?
- Does it avoid fallback without user-visible approval?
- Are Remotion and HyperFrames contracts respected?
- Are smoke tests or render probes included?
- Does final output get validated with ffprobe/frame/audio checks where relevant?

### Pipeline or Skill Change

Ask:

- Does the manifest still validate?
- Do stage skills exist and match stage names?
- Are `review_focus` and `success_criteria` meaningful?
- Are canonical artifacts valid?
- Are human approval gates correct?
- Are tests updated?

### Schema Change

Ask:

- Which producers and consumers are affected?
- Is the field required or optional?
- Do existing checkpoints/artifacts still work?
- Are tests updated for both valid and invalid data?
- Does the change need a migration note?

### Dependency or Lockfile Change

Ask:

- Is the dependency necessary for the PR?
- Is the lockfile change proportional?
- Are install scripts or transitive packages risky?
- Is the package maintained and appropriately licensed?
- Does it work on the supported Python/Node versions?
- Are version bounds too loose or too strict?

### Docs-Only Change

Ask:

- Is the doc technically accurate?
- Does it match current code and registry behavior?
- Does it overpromise provider quality, cost, offline operation, or platform
  support?
- Does it point users to the right setup and troubleshooting path?

Docs-only PRs can still create regressions by teaching users or agents the
wrong behavior.

## Testing Expectations

Pick tests based on risk. Do not require expensive integration tests for every
small doc fix, but do require evidence for changed behavior.

Common checks:

```bash
python -m pytest tests/contracts -q
python -m pytest tests/tools -q
python -m pytest tests/qa -q
python -m py_compile path/to/changed_file.py
```

For provider PRs, focused mocked tests are often better than expensive live API
tests. Live-provider QA is useful when credentials and cost are acceptable, but
the contract should not depend on a maintainer having every provider configured.

If tests cannot be run, the review should say why and what risk remains.

## PR Comment Guidance

Good review comments are specific, evidence-based, and actionable.

Prefer:

- "This test fails with the current branch: `...`"
- "This provider will not be discovered because `capability` is set to `...`."
- "This setup claim is misleading because first run downloads model weights."
- "Please split the lockfile churn from this provider change."

Avoid:

- Vague comments like "clean this up"
- Personal comments about the contributor
- Public speculation about intent
- Overclaiming safety
- Long lists of nits when there is a clear blocker

When a PR has several issues, prefer one consolidated comment. It helps the
author fix everything in one pass. Use inline comments for exact line-level
bugs that need code context.

Suggested public language for security review:

- "I found an actionable security issue in this diff."
- "This area needs a security review before merge."
- "I did not find an actionable security issue in the reviewed diff."

Do not state or imply that a contributor has or lacks malicious intent. Review
the code and behavior.

## Maintainer and AI-Agent Workflow

This section is public so contributors understand how reviews are performed.
It is a workflow, not a limit on reviewer judgment.

For a full review:

1. Fetch latest `main`.
2. Check out the PR in a clean worktree.
3. Inspect PR metadata: title, linked issues, changed files, author notes, and
   prior comments.
4. Review the diff for scope, usefulness, and architecture fit.
5. Identify the PR scenario: provider, selector, pipeline, schema, runtime,
   docs, tests, dependency, or mixed.
6. Apply the relevant scenario prompts from this guide.
7. Run focused tests or explain why they were not run.
8. Check docs and user-facing claims against implementation.
9. Check security, dependency, and supply-chain risk.
10. Write findings ordered by severity.
11. Decide: approve, comment, request changes, or close/redirect.

For AI-assisted review, ask the agent to report evidence, not just conclusions:

- Commands run and their results
- Files inspected
- Architecture contracts touched
- Risks that remain unverified
- Exact merge blockers

Do not approve from a summary alone. The reviewer or agent should inspect the
diff and relevant project contracts.

## Merge-Readiness Rubric

Before approving, confirm:

- The PR is useful and aligned with project direction.
- The diff is focused and free of unrelated churn.
- Architecture contracts are preserved.
- Tests cover the behavior at the right level.
- Docs match user-visible behavior.
- Security and supply-chain risks have been considered.
- Performance, cost, and resource claims are realistic.
- The branch is current enough that review findings are still valid.
- Remaining risks are acceptable and stated.

Approving does not mean the PR is perfect. It means the change is useful,
understood, appropriately tested, and safe enough to land.
