# Modal deploy — self-hosted LTX-Video endpoint

Stands up the cheap draft/bulk video GPU that `tools/video/ltx_video_modal.py` calls.
Once deployed, the `quality_tier` router (PR #299) sends `draft` video here and keeps
premium APIs (Kling/Seedance/Veo) for `hero` shots.

## One-time

```bash
pip install modal
python3 -m modal setup      # opens a browser to authenticate; nothing to paste
```

## Deploy

```bash
modal deploy deploy/modal_ltx_endpoint.py
```

Modal prints a web URL for the `generate` endpoint. Point the app at it (the tool
reads this env var; it's already listed in `.env.example`):

```bash
export MODAL_LTX2_ENDPOINT_URL="https://<workspace>--openmontage-ltx-ltx-generate.modal.run"
# or add it to your .env
```

That's it — `ltx_video_modal` flips from UNAVAILABLE to AVAILABLE and joins the video menu.

## Smoke test

```bash
curl -s -X POST "$MODAL_LTX2_ENDPOINT_URL" \
  -H 'content-type: application/json' \
  -d '{"prompt":"a red fox trotting through snow, cinematic","width":1024,"height":576,"num_frames":121,"fps":24,"steps":30,"negative_prompt":""}' \
  --output test.mp4 && open test.mp4
```

## Cost / GPU

- Default GPU is **L40S** (~$1.95/hr serverless) — LTX is light, so this stretches
  Starter credits further than A100. A 5s clip is ~$0.03–0.05 warm; the container
  **scales to zero** when idle (`scaledown_window=120`).
- First request is a cold start that downloads the model (~10GB) into a persistent
  Modal Volume, so it happens only once.
- Edit `GPU` at the top of `modal_ltx_endpoint.py` to change hardware (`"A10G"` cheaper
  for short clips, `"A100"` for large batches).

## Notes

- `scaledown_window` is the current Modal parameter name; on older `modal` versions it
  is `container_idle_timeout` — rename if deploy errors on it.
- The endpoint returns raw MP4 bytes, matching `generate_ltx_modal_video`, so no
  external storage/bucket is required.
