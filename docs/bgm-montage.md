# BGM Montage Integration

OpenMontage exposes BGM Montage as the bgm_montage tool and as the
bgm-montage pipeline. The implementation stays in
[sharbvane/bgm-montage](https://github.com/sharbvane/bgm-montage); OpenMontage
only provides the agent-facing contract and canonical artifact mapping.

## Why this boundary

BGM Montage already contains the mature domain logic for:

- BPM, beat, onset, phrase, section, energy, pause, drop, surge, and climax
  analysis;
- event-snapped pre-download timeline planning;
- reference editing-grammar learning;
- YouTube-first, Pixabay, approved-manifest, and offline local-library
  material acquisition;
- source reuse, screen-share, repeat-gap, crop, and continuity controls;
- FFmpeg H.264/AAC rendering and full-decode black/freeze/silence/sequence QA;
- validation frames, visual-review requests, resumable runs, and optional
  JianYing export.

Copying those scripts into OpenMontage would create two implementations and
would make BGM Montage's standalone releases harder to maintain. The bridge
invokes the exact BGM Montage CLI from an explicitly configured checkout and
maps its outputs into OpenMontage's tool and checkpoint contracts.

## Install

From the OpenMontage checkout:

~~~powershell
git clone https://github.com/sharbvane/bgm-montage.git ..\bgm-montage
py -3.11 -m venv ..\bgm-montage\.venv
..\bgm-montage\.venv\Scripts\python.exe -m pip install -r ..\bgm-montage\requirements.lock.txt
$env:BGM_MONTAGE_ROOT = (Resolve-Path ..\bgm-montage).Path
$env:BGM_MONTAGE_PYTHON = (Resolve-Path ..\bgm-montage\.venv\Scripts\python.exe).Path
~~~

The bridge also requires ffmpeg and ffprobe on PATH. Keep the BGM environment
separate from OpenMontage because BGM Montage's optional audio and
semantic-analysis stack includes NumPy/SciPy/librosa/OpenCV and optional
PyTorch/Transformers.

## Reference-video requirement

The full `run` operation is reference-dependent. Supply `reference_dir` with
at least one video file using an extension supported by BGM Montage. If
omitted, the bridge reads `projects/<project-id>/references/`; it fails before
starting the CLI when that directory is missing or has no supported video
files. BGM Montage then decodes and analyzes the references, and reports an
analysis error if they are unreadable. It does not invent a style profile from
an empty folder. Reference files are read-only and are never moved, renamed,
or used as source footage. This is a different boundary from the `analyze`,
`plan`, and `validate` operations.

## Tool calls

The agent should always use a project-scoped project_dir:

~~~python
bgm_montage.execute({
    "operation": "run",
    "project_dir": "projects/rain-city",
    "bgm": "projects/rain-city/input/music.wav",
    "theme": "rainy city at night",
    "duration_seconds": 30,
    "ratio": "16:9",
    "reference_dir": "projects/rain-city/references",
    "source_provider": "local-library",
    "local_library_dir": "projects/rain-city/library",
    "usage_mode": "local_evaluation",
    "agent_visual_review": "required",
})
~~~

The smaller analyze, plan, and validate operations are useful when the agent
wants to inspect or resume individual artifacts. They write audiomap.json,
timeline.json, and a BGM validation report below project_dir/artifacts by
default.

The full run preserves BGM Montage's optional JianYing draft export through
the `jianying_draft`, `jianying_draft_name`, `jianying_draft_root`, and
`jianying_python` inputs. When enabled, this writes to the configured JianYing
workspace, which may be outside the OpenMontage project directory; use it only
when that editor-side output is intended.

run places native artifacts under
projects/<id>/renders/bgm-montage/<theme>/<run-id>/, cache under
projects/<id>/.bgm-montage-cache/, and material under
projects/<id>/assets/bgm-montage/. By default, references are read from
projects/<id>/references/ and must contain at least one supported video. A
local-library root is read as input and is not
modified by the bridge. Any custom output, report, frames, or cache path must
stay inside project_dir.

## Artifact mapping

| BGM Montage artifact | OpenMontage use |
| --- | --- |
| audiomap.json | Raw music-analysis evidence retained in the run directory |
| timeline.json | Raw event-snapped slot plan retained in the run directory |
| asset_manifest.json | Raw provenance plus canonical asset_manifest |
| edit_decisions.json | Raw BGM edit plan plus canonical edit_decisions |
| render_report.json / validation.json | Raw QA report plus canonical render_report |
| validation_frames/, visual_review.* | Agent-visible quality evidence |
| run_state.json, run_report.json | Resume and stage audit records |

The canonical edit artifact uses render_runtime=ffmpeg and
renderer_family=documentary-montage. OpenMontage must not silently route this
run through Remotion or HyperFrames.

## QA and resume

BGM Montage returns exit code 0 after a passed full run. Exit code 3 means
programmatic QA passed and the run is waiting for agent visual review. Inspect
the requested frames, write the review JSON required by BGM Montage, and call
the same run with run_id and resume_run=true. Exit code 2 from the standalone
validator means programmatic QA failed; do not present that video as complete.

## License and provenance

The current BGM Montage branch is AGPL-3.0-or-later and retains the
sharbvane/bgm-montage attribution. Existing historical BGM tags/releases
retain their published terms. BGM Montage's direct dependency and media-source
notice is in its
[THIRD_PARTY_NOTICES.md](https://github.com/sharbvane/bgm-montage/blob/main/THIRD_PARTY_NOTICES.md).
Downloaded media remains subject to each source's license and attribution
requirements; usage_mode=publish does not create rights that are not present.
