# S14 — smoke test, 3 new models (free Kaggle T4)

Generated: 2026-10-23T05:39:16.498145+00:00

## Precheck (per kernel, enforced before any generation)
- GPU: T4, compute capability 7.5; fp16 only; bf16 NOT supported; bitsandbytes absent.
- One model per kernel (never stacked dependency sets).
- fp16 only; no pipe.to('cuda') before offload; enable_model_cpu_offload().

## Per-model outcome
- minit2i-b-16 (None): HARDWARE FAIL: pipeline load failed for 'minit2i-b-16': Cannot load model MiniT2I/MiniT2I-B-16: model is not cached locally and an error occurred while trying to fetch metadata from the Hub. Please check out the root cause in the stacktrace above. HARDWARE FAIL; license=unknown; revision=unknown; pipeline=None; steps=None; guidance=None; load=Nones; warm=Nones/img; peak VRAM alloc=NoneMB reserved=NoneMB; generated=0/0 ok=0 black=0 nan=0
- minit2i-l-16 (None): HARDWARE FAIL: pipeline load failed for 'minit2i-l-16': Cannot load model MiniT2I/MiniT2I-L-16: model is not cached locally and an error occurred while trying to fetch metadata from the Hub. Please check out the root cause in the stacktrace above. HARDWARE FAIL; license=unknown; revision=unknown; pipeline=None; steps=None; guidance=None; load=Nones; warm=Nones/img; peak VRAM alloc=NoneMB reserved=NoneMB; generated=0/0 ok=0 black=0 nan=0
- zimage-base (Tongyi-MAI/Z-Image): COMPLETE: 0/3 ok, load 0.0s, peak VRAM 12107.11 MB ; license=apache-2.0; revision=04cc4abb7c5069926f75c9bfde9ef43d49423021; pipeline=ZImagePipeline; steps=50; guidance=None; load=0.0002s; warm=86.4496s/img; peak VRAM alloc=12107.11MB reserved=12714.0MB; generated=3/3 ok=0 black=3 nan=0

## Per-image detail
| model | seed | output_file | seconds | warm_s | black_or_nan | error |
|---|---:|---|---:|---:|---|---|
| zimage-base | 101 | 101.png | 88.443 | None | True |  |
| zimage-base | 202 | 202.png | 87.7098 | 87.7098 | True |  |
| zimage-base | 303 | 303.png | 85.1893 | 85.1893 | True |  |

## Aggregate
- models run: 3
- total images: 3 | ok: 0 | black: 3 | nan: 0 | errors: 0
- hardware-fail models: 2

## Notes
- MiniT2I B/16 and MiniT2I L/16 repos are not public on HuggingFace (404) -> HARDWARE FAIL, recorded with exact error; no retry beyond one attempt per model.
- Z-Image Base loads (ZImagePipeline, revision 04cc4abb..., Apache-2.0 per model card README) but produces black frames for all 3 seeds -> black/NaN flag set, n_ok=0.
- No 1024 bake-offs run; no Kromoss/MOSS-Image-SFT/Iris/HiDream/FLUX.3 Klein downloaded (only model-card licence reporting required for those).
- License for MiniT2I models could not be fetched (repo not found); recorded as unknown.
