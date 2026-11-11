# Agent Guide — Decisions

Part of [`AGENT_GUIDE.md`](../../AGENT_GUIDE.md), which states every rule in brief and says when to read this.
**Read this in full before the proposal or idea stage, and before changing any provider, model, runtime, voice, music or composition choice mid-run.**

## Decision Communication Contract

### Announce Before Execution

Stated in full in `AGENT_GUIDE.md`.

### Ask Before Major Changes

Stated in full in `AGENT_GUIDE.md`.

### Re-log Changed Decisions (Binding)

The `decision_log` is the board's Decisions rail and the run's audit trail. It is **append-only history, not a scratchpad.** When a choice you already logged changes mid-run — the user swaps the voice, you switch provider/model/runtime/music, or a fallback overrides an earlier pick — you MUST **append a new `decision_log` entry** for the new choice, reusing the **same `category` AND the same `subject`** (e.g. `category: "voice_selection"`, `subject: "Narration TTS provider"`), with the superseded option moved into `options_considered` and `rejected_because` noting it was changed.

Editing only a downstream artifact (the `asset_manifest`, a prop) while leaving the old decision in the log is a defect: the board keeps showing the stale choice (e.g. `voice → openai_onyx` after the user moved to Chirp3). The board identifies a decision by its **(category, subject) pair** and renders the latest entry for that pair as current (tagged "revised") — so the fix is to append the new entry with an identical `subject`, never to silently mutate the old one or reword the subject (a reworded subject reads as a different decision and both will show). Keeping distinct decisions in one category (e.g. TTS vs image `provider_selection`) is exactly why the pair, not the category alone, is the key. This applies at every stage, not just `idea`.

### Present Both Composition Runtimes (HARD RULE)

When both Remotion and HyperFrames are available on the machine (check `video_compose.get_info()["render_engines"]`), the agent **MUST present both options to the user** before locking `render_runtime` at the proposal stage. The agent MAY recommend one with rationale — but silently picking a "default" is forbidden even when the pipeline manifest or a director skill suggests one.

The presentation MUST include, for each runtime:

1. A one-sentence plain-language description of what it is best at for **this specific brief**.
2. A one-sentence honest tradeoff (why it might not be the right pick here).
3. The agent's recommendation and the reason, tied to the brief's delivery_promise and visual approach.

Then wait for explicit user approval before advancing. Record the full shortlist — BOTH runtimes plus any "ffmpeg" option that applies — as `options_considered` in the `render_runtime_selection` decision logged in `decision_log`. A decision log entry with only one runtime considered when both were available is a CRITICAL reviewer finding.

Exception: if only one runtime is available on the machine, the agent proceeds with it but MUST say so explicitly ("HyperFrames isn't installed on this machine; I'm proceeding with Remotion. Install HyperFrames if you want the alternative."). The `render_runtime_selection` decision still records the unavailable option as `rejected_because: "runtime not available on this machine"`.

This rule applies to every pipeline that invokes `video_compose` — not just Wave 1. A pipeline's director skill may recommend a runtime, but that recommendation is input to the conversation with the user, not a decision.

### Composition Authoring Mode — Templated vs Atelier

Orthogonal to *runtime* is *authoring mode*: **how** the composition is built. Present it as its own proposal decision and log it in `decision_log` (`category: "composition_mode"`).

- **Templated** — assemble the stock `cut.type` scene-types (`text_card`, `stat_card`, `bar_chart`, …) into the `Explainer`/`CinematicRenderer` compositions. Fast, cheap, reliable — and the reason most videos look alike. Right for batch output, localization variants, quick drafts, and low-stakes internal clips.
- **Atelier** — **hand-author the composition from scratch**: bespoke scenes, a one-off theme, and motion written for this piece, rendered via `composition_mode: "atelier"` (see `video_compose` → `_render_via_atelier`). No reusable creative components; a fresh visual language every time.

**Default to atelier for hero work** — marketing, launches, brand pieces, any single-deliverable explainer that must impress. The deciding rule: *reuse engine knowledge, never creative components.* In atelier mode the stock scene-type catalog, `hyperframes-registry` blocks, fixtures, and finished components are **off-limits** — they are frozen looks that reintroduce sameness. Before building, route through **`skills/meta/taste-direction.md`** to set the design read and taste dials, then **`skills/meta/bespoke-composition.md`**, which sequences: art direction (`visual-style`) → motion principles (Disney 12 via `framer-motion`/`lottie-bodymovin`) → engine mechanics (`remotion-best-practices` + the stock components read *only as a mechanics codex*) → render via the atelier path. Close with a **distinctness review**: *could this be any other product's video? does it reuse a look I've made before?* — the inverse of "does it match the reference." Atelier costs more tokens and iteration than templated; say so at proposal so the user opts in knowingly.

### Escalate Blockers Explicitly

Stated in full in `AGENT_GUIDE.md`.

### Recommendation Style

Stated in full in `AGENT_GUIDE.md`.

### No Unilateral Substitutions

Stated in full in `AGENT_GUIDE.md`.
