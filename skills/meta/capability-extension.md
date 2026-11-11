# Capability Extension Protocol

## When to Use

When you encounter a production need that no existing tool covers. The agent can extend the system — but with guardrails. This replaces the blanket "do NOT write ad-hoc Python scripts" rule with a structured protocol.

## Assessment First

Before writing anything, classify the gap:

| Gap Type | Example | Action |
|----------|---------|--------|
| **One-off transform** | Custom image crop, color adjustment, format conversion | Write a project-scoped Python script |
| **Recurring visual need** | New illustration style, custom chart type | Generate a custom playbook or Remotion component |
| **Missing provider** | User wants a specific API not in the registry | Create a minimal tool wrapper |
| **Missing knowledge** | Agent doesn't know how to prompt a specific model | Use web search to learn, then document as a Layer 3 skill |

## Rules for Ad-Hoc Scripts

Scripts are allowed ONLY when:
1. No existing tool covers the need (verified against registry via preflight)
2. The script is idempotent (safe to re-run)
3. The script produces a file artifact in the project workspace
4. The script is logged in the decision log: `category: "capability_extension"`
5. The user is informed: "I wrote a custom script for X because no existing tool handles Y"
6. The script does NOT call external APIs without user approval

Scripts go in: `projects/<project-name>/scripts/`

### Script Template

```python
"""<One-line description of what this script does>

Created by capability extension protocol because: <reason no existing tool covers this>
Decision log entry: <decision_id>
"""
import sys
from pathlib import Path

def main(input_path: str, output_path: str) -> None:
    # Idempotent: check if output already exists
    out = Path(output_path)
    if out.exists():
        print(f"Output already exists: {out}")
        return

    # ... transformation logic ...

    print(f"Created: {out}")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
```

## Rules for Custom Playbooks

When the existing playbooks don't match the brief:
1. Use `lib/playbook_generator.py` to create a new playbook
2. Base it on the closest existing playbook if possible
3. Validate against `schemas/styles/playbook.schema.json`
4. Save to `styles/custom/<project-name>.yaml`
5. Log as decision: `category: "playbook_selection"`, `subject: "custom playbook created"`

## Rules for New Skills (Technique Learning)

When the agent discovers technique knowledge during web research:
1. Document it as a project-scoped skill: `projects/<project-name>/skills/<name>.md`
2. Follow the Layer 3 skill format:
   - Provider name and version
   - Provider-specific prompting patterns
   - Optimal parameters for this use case
   - Quality tips and known failure modes
   - Source URLs for the information
3. Reference it in the decision log
4. Suggest promoting to `.agents/skills/` if it's generally useful

## Rules for Tool Wrappers

When a user needs a specific provider that isn't in the registry:
1. The agent can create a minimal `BaseTool` subclass
2. Save to `projects/<project-name>/tools/<name>.py`
3. It MUST inherit from `BaseTool` and implement the full contract (input_schema, execute, capabilities, etc.)
4. It MUST be registered before use
5. Log as decision: `category: "capability_extension"`
6. Requires user approval before first paid API call

## What Is Still Forbidden

- Bypassing the pipeline (all production still goes through stages)
- Calling external APIs without user knowledge
- Modifying existing tools in `tools/` (create wrappers, don't modify originals)
- Skipping the decision log
- Writing scripts that have side effects beyond their output file (no sending emails, no pushing to remote, no deleting files outside project workspace)

## Decision Log Entry Format

Every extension must be logged:

```json
{
  "decision_id": "ext-<NNN>",
  "stage": "<current stage>",
  "category": "capability_extension",
  "subject": "Created custom <script|playbook|skill|tool> for <purpose>",
  "options_considered": [
    {"option_id": "existing-tool", "label": "<closest existing tool>", "score": 0.3, "reason": "<what it covers and where it falls short>", "rejected_because": "<why it doesn't work>"},
    {"option_id": "extension", "label": "<what was created>", "score": 0.8, "reason": "<why this approach>"}
  ],
  "selected": "extension",
  "reason": "<concise justification>",
  "user_visible": true,
  "confidence": 0.8
}
```

- `decision_id` must be unique in the project's decision log (`ext-001`, `ext-002`, … — read the log first and take the next free number). The log is append-only: a re-used id with the same `selected` replaces the earlier entry, and with a different `selected` `write_checkpoint` raises a DECISION LOG VIOLATION.
- Every option needs all four of `option_id`, `label`, `score` (0–1, 1 is best) and `reason`; `rejected_because` is the only optional field. The schema (`schemas/artifacts/decision_log.schema.json`) is closed, so a missing `score`/`reason` or an extra key fails `write_checkpoint`.
- The entry goes inside a `decision_log` artifact (`{"version": "1.0", "project_id": "<project-id>", "decisions": [ ... ]}`) passed to `write_checkpoint`, or through `lib.checkpoint.append_decisions` between checkpoints.
