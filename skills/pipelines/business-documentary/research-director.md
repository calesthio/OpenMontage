# Research Director - Business Documentary Pipeline

## When To Use

Stage 2 of 12. You turn the approved `topic_brief` into a `research_brief`:
the map of sources the film will stand on, what each one says, where they
disagree, and what could not be found.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Artifact in | `topic_brief` (validated) | The approved angle |
| Schema | `schemas/artifacts/research_brief.schema.json` | Output validation |
| Registry | `registry.get_by_capability(...)` | What fetching is actually possible |

## Process

### 1. Work the primary-source list first

For each entry in `topic_brief.primary_source_expectations`, collect the
concrete source: filing date, document, page or section, publisher, URL.
Record it in `metadata.sources[]` with:

```json
{
  "source_id": "SRC-edgar-10k-2024",
  "title": "Form 10-K, fiscal 2024",
  "publisher": "Company name",
  "published_date": "2025-02-14",
  "accessed_date": "2026-10-15",
  "url": "https://...",
  "source_type": "primary",
  "source_class": "corporate_filing",
  "notes": "Segment revenue on p. 32; margin discussion p. 41"
}
```

`source_id` must be stable (`SRC-...`) — the evidence ledger cites it.

### 2. Use secondary sources for context and cross-checking only

Reporting and analysis are allowed and useful, but they do not carry the
central thesis alone. When a secondary source repeats a primary figure, cite
the primary.

### 3. Never confuse availability with accuracy

HTTP 200 proves the URL answered, not that the claim is true. Record what the
source actually says — quote it, do not round it into a headline.

### 4. Record conflicts and gaps as findings

- `metadata.gaps[]` — what you looked for and could not find. Empty only with
  an explicit justification.
- Source conflicts: record both numbers and their dates. Do not pick the
  convenient one.

### 5. Keep the competitor/audience read light

Optional: what comparable films cover, what the audience already believes.
This informs the script's framing; it is not evidence.

### 6. Quality gate

- Every source has publisher, date, URL, access date, type and class.
- Primary sources outnumber secondary ones for the central thesis.
- `metadata.gaps[]` is present and honest.
- No interpretation has been promoted to fact.

## Common Pitfalls

- Citing an aggregator that cites a report. Find the report.
- Treating a company's marketing page as a filing.
- Recording a number without its date or unit. A margin from 2019 is not a
  margin today.
- Silently dropping a source that contradicts the angle.

---

## Checkpoint Note

`research` is auto-approved (`human_approval_default: false`): write the
checkpoint, self-review with `skills/meta/reviewer.md`, and continue.
