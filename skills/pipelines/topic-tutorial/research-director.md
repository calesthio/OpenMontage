# Research Director — Topic Tutorial Pipeline

## When to Use

You are the **Research Director** for the `topic-tutorial` pipeline. You ingest user inputs (PDF, DOCX, PPTX, XLSX, CSV, codebases, web pages, or media) using `universal_ingestor` and synthesize a structured, grounded `research_brief.json` and `fact_sheet.json`.

## Prerequisites

| Layer | Resource | Purpose |
|-------|----------|---------|
| Tool | `universal_ingestor` | Material ingestion & secret redaction |
| Schema | `schemas/artifacts/research_brief.schema.json` | Artifact validation |
| Schema | `schemas/artifacts/fact_sheet.schema.json` | Fact validation |

## Process

1. **Ingest Raw Inputs:** Call `universal_ingestor` on the user-provided `input_path` (or input directory `inputs/`).
2. **Review Manifest:** Inspect `artifacts/input_manifest.json` to verify all sources were scanned and secrets redacted.
3. **Map Landscape & Core Claims:**
   - Identify core entities, technologies, or principles explained in the sources.
   - Extract at least 3 concrete data points with source citations.
   - Synthesize at least 3 distinct tutorial angles (e.g. beginner practical walkthrough, architectural deep-dive, comparative analysis).
4. **Produce Artifact:**
   - Save `artifacts/research_brief.json` conforming to `research_brief.schema.json`.
   - Ensure `sources` array has at least 5 citations with valid URIs.
