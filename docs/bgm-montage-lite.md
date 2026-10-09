# BGM Montage Lite

BMTS-Lite is OpenMontage's fast, local, audio-led montage route. It accepts one music file and one or more supplied video clips, analyzes the complete track, plans beat/phrase-aware cuts, reuses clips when needed, adapts the output frame to the selected or majority-detected aspect ratio, and renders an MP4. It does not require a reference video or API key.

## Choose the right mode

| Mode | Best for | Required media | Selection and review |
| --- | --- | --- | --- |
| **BMTS-Lite** (`bgm_montage_lite`) | Fast, full-song beat montage from footage the user already chose | One audio file and 1–100 video clips | Random, balanced reuse; automatic aspect ratio; no semantic selection or tool-specific agent visual review |
| **BGM Montage** (separate integration in [PR #751](https://github.com/calesthio/OpenMontage/pull/751)) | Professional reference-guided edit with style analysis and stricter source selection | Audio, reference video, and source-footage library | Reference-style analysis, intelligent selection, renderer QA, and the full integration's review gates |

The Lite tool deliberately calls BMTS-Lite's existing `worker.run()` and `engine/` modules. It does not copy that engine into OpenMontage or route through the BGM Montage full workflow. Its existing random assignment, 12-shot render batches, full-track audio mux, automatic aspect-ratio vote, and blur-fill framing are preserved.

## Install the optional local runtime

The integration keeps BMTS-Lite dependencies outside OpenMontage's main Python environment. Use a clean BMTS-Lite checkout and a dedicated Python 3.11 environment:

```powershell
git clone https://github.com/sharbvane/BMTS-Lite.git
cd BMTS-Lite
py -3.11 -m venv .venv-openmontage
.\.venv-openmontage\Scripts\python.exe -m pip install -r requirements-runtime.txt
$env:BGM_MONTAGE_LITE_ROOT = (Get-Location).Path
$env:BGM_MONTAGE_LITE_PYTHON = (Resolve-Path .\.venv-openmontage\Scripts\python.exe).Path
```

Install FFmpeg (including `ffprobe`) on `PATH`. On macOS/Linux, create the virtual environment with `python3.11 -m venv .venv-openmontage`, install the same requirements file, and export the two variables to the checkout and environment interpreter paths.

No network access or API credentials are used during a montage run. The tool reports as unavailable until the source checkout, runtime packages, FFmpeg, and ffprobe are present.

## Call from the cinematic compose stage

The tool is an optional `video_post` capability in the cinematic pipeline's compose stage. Choose it only for an uncomplicated, full-song music montage without reference matching, narration, titles, or semantic clip selection. Keep the existing video-compose route for authored compositions, mixed media, and the professional reference-guided workflow.

```python
from tools.tool_registry import registry

registry.discover()
result = registry.get("bgm_montage_lite").execute({
    "audio_path": "project/assets/music.mp3",
    "video_paths": [
        "project/assets/clip-01.mp4",
        "project/assets/clip-02.mp4",
        "project/assets/clip-03.mp4",
    ],
    "project_dir": "project",
    "aspect_ratio": "auto",
})
if not result.success:
    raise RuntimeError(result.error)
print(result.data["output_path"])
```

Supported explicit aspect ratios are `16:9`, `9:16`, `4:3`, `3:4`, `1:1`, and `4:5`; `auto` selects the closest supported ratio to the majority of source clips. Mismatched clips retain their full frame in the existing blur-fill treatment. The full audio is never silently shortened: BMTS-Lite accepts music tracks from 1 second through 10 minutes and fails outside that range.

The tool returns three OpenMontage artifacts: the MP4, `*.timeline.json`, and `*.audiomap.json`. The render report includes probed codec, dimensions, frame rate, duration, file size, and the renderer's full-decode verification. Outputs are never overwritten; choose a new `output_path` if any of the three files already exists.

## End-to-end verification

On 2026-10-09, the OpenMontage tool adapter rendered a local 21.768-second music track with five local video clips and no reference video or API key. It produced a 33-shot, 1920×1080 H.264/AAC MP4; the output audio stream covered the full 21.768-second track. BMTS-Lite detected 45 beats: cut boundaries had a 62.8 ms mean and 250.9 ms maximum distance to the nearest detected beat, with 78.1% within 120 ms (the remainder include half-beat/phrase cuts). All five clips were reused 6–7 times at varying source offsets, and the renderer plus an independent FFmpeg full-decode check succeeded. The source media and rendered files are local test inputs/outputs and are intentionally not redistributed with this project.

## Licensing and attribution

BMTS-Lite source at the current main revision and later is licensed under AGPL-3.0-only, copyright © 2026 Cui (sharbvane). Historical snapshots retain the license that accompanied them. No BMTS-Lite engine source or third-party media is vendored in this OpenMontage contribution. See [BMTS-Lite](https://github.com/sharbvane/BMTS-Lite) and its [`requirements-runtime.txt`](https://github.com/sharbvane/BMTS-Lite/blob/main/requirements-runtime.txt) for the separately installed engine and runtime dependencies.
