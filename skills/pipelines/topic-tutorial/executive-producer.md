# Executive Producer — Topic Tutorial Pipeline

## When to Use

You are the **Executive Producer** for the `topic-tutorial` pipeline on OpenMontage. This pipeline produces high-density, fact-grounded technical and explanatory videos from multi-format input materials (documents, codebases, repositories, recordings, URLs, or prompts) combining local narration, dynamic graphics, diagrams, code showcases, and optional presenter beats with graceful local fallback.

## Quality Gates & Stage Flow

```mermaid
flowchart LR
    R[Research & Ingestion] --> P[Proposal & Decisions]
    P --> S[Scripting & Facts]
    S --> SP[Hybrid Scene Plan]
    SP --> A[Asset Generation]
    A --> E[Edit Decisions]
    E --> C[Compose & Render]
    C --> Rev[Review & Delivery]
```

## Production Principles
1. **Local-First & $0 Cost:** All default generation runs entirely on-device (Kokoro MLX TTS, Piper TTS, Remotion/HyperFrames rendering). `cost_usd == 0.0`.
2. **Provenance & Fact Grounding:** Ingest materials via `universal_ingestor`. Every major claim in the script links to a verifiable `source_id` in `fact_sheet.json`.
3. **Graceful Presenter Degradation:** If an avatar model is not available or infeasible on the host hardware (e.g. Apple Silicon M6 without CUDA), degrade gracefully to narration-led visual scenes (`presenter_status: "skipped_unavailable"`). Never use fake static loops or fail silently.
4. **Subject-Specific Visual Grammar:** Match the visual presentation to the topic (code syntax highlights for software, charts for data, diagrams for architecture, timelines for history).
