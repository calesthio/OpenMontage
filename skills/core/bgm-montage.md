# BGM Montage Bridge

## Purpose

Use the 'bgm_montage' tool when the deliverable is a music-led montage and
the user wants measured beat/phrase structure, source-aware material matching,
timeline generation, FFmpeg rendering, and programmatic media QA. The bridge
calls the standalone BGM Montage checkout instead of copying its
implementation into OpenMontage.

The agent remains the OpenMontage orchestrator. BGM Montage is a bounded
execution engine with auditable intermediate artifacts:

    audiomap.json -> timeline.json -> asset_manifest.json ->
    edit_decisions.json -> render_report.json -> validation_frames/

## Setup

Set these environment variables before preflight:

    BGM_MONTAGE_ROOT=/absolute/path/to/bgm-montage
    BGM_MONTAGE_PYTHON=/absolute/path/to/bgm-montage/.venv/Scripts/python.exe

BGM_MONTAGE_PYTHON is optional and defaults to the current OpenMontage
interpreter. Use a separate Python 3.11 environment for BGM Montage because
its audio and optional semantic-analysis dependencies are intentionally not
OpenMontage base dependencies.

## Operations

- 'analyze': run the signal analyzer and write an audiomap.json.
- 'plan': snap shot slots to measured beats, phrases, drops, and sections.
- 'run': execute the full BGM Montage workflow, including source acquisition,
  selection, timeline assignment, FFmpeg render, and QA.
- 'validate': run BGM Montage's independent full-decode and visual-evidence QA
  against an existing video.

For all operations, use a project-scoped project_dir. The bridge stores cache,
downloaded material, renders, canonical artifacts, and validation evidence
below that project. Input music and an explicitly supplied local library may
live elsewhere and are read as inputs.

## Provider and rights rules

Use source_provider=local-library for a network-free run. For YouTube or
Pixabay acquisition, make the network and source rights explicit in the brief.
Use usage_mode=publish only when the user has authorized distribution and the
selected assets have a usable license and attribution record. BGM Montage
records provider, source URL, and license fields when available; the agent
must not invent missing rights information.

Do not silently replace BGM Montage with video_compose, Remotion, or another
renderer. If the bridge is unavailable, report the missing checkout or
dependency and ask the agent to choose a different approved path.

## Quality gate

Exit status 0 means the full run passed. Exit status 3 means programmatic QA
passed but the run is waiting for the agent's visual review; inspect the
reported frames and write the requested BGM review JSON before resuming with
the same run ID. A failed programmatic QA is not a completed render.

For a successful run, use the returned OpenMontage asset_manifest,
edit_decisions, and render_report as canonical checkpoint artifacts while
retaining the original BGM Montage JSON files for detailed auditability.
