# k8s deployment (self-managed k3s)

On-demand tutorial rendering. The render-api creates a Job per request; each Job
runs the **worker** (capture + render + upload) with **ttsd** as a native sidecar.
Final videos land in MinIO; the API hands back a presigned download URL.

## Prerequisites (blockers)

- A **dedicated, resettable demo environment** the cluster can reach (recording
  mutates state; the dev-only test-token route must not exist on production).
- Images pushed to a registry the cluster can pull (see `deploy/README.md`):
  `tutorial-worker`, `circuit-ttsd`, `render-api`.
- An ingress controller (nginx assumed) — or change `50-render-api.yaml`.

## Apply

```bash
kubectl apply -f 00-namespace.yaml
cp 20-secrets.example.yaml 20-secrets.yaml   # fill in real values; do NOT commit
kubectl apply -f 20-secrets.yaml
# edit REGISTRY in 30-configmap.yaml and 40/50 image fields, then:
kubectl apply -f 10-rbac.yaml -f 30-configmap.yaml -f 40-minio.yaml -f 50-render-api.yaml
```

Rotate the ElevenLabs key currently committed in
`circuit-bid/.ddev/docker-compose.narrator.yaml` before putting it in `ttsd-secret`.

## Trigger a render

```bash
curl -XPOST http://tutorials.example.com/renders \
  -H 'content-type: application/json' \
  -d '{"tutorial":"sales-tour","base_url":"https://DEMO_HOST"}'
# -> {"render_id":"sales-tour-ab12cd34","status":"queued"}

curl http://tutorials.example.com/renders/sales-tour-ab12cd34
# -> {"status":"succeeded","download_url":"https://.../final.mp4?..."}
```

`{"offline": true}` renders with silent placeholder narration (no ttsd) — handy
for a smoke test. `{"render_runtime": "ffmpeg"}` overrides the default Remotion
path for a single render.

## Render runtime

The worker renders via **Remotion** by default (`RENDER_RUNTIME=remotion` in the
configmap) — the `screencast_scene` Explainer composition with animated
callouts/zoom tracking each step. This needs the worker image built with
`INSTALL_REMOTION=true` (the default). Set `RENDER_RUNTIME=ffmpeg` (and optionally
a lighter `INSTALL_REMOTION=false` image) for the self-contained ffmpeg assembly.

## Notes

- **Job hygiene:** `ttlSecondsAfterFinished` cleans up finished Jobs;
  `activeDeadlineSeconds` kills runaways; the worker has 4–8Gi memory limits.
  The API caps concurrent renders (`MAX_CONCURRENT`).
- **Storage:** `work` and `clips` are `emptyDir` (no RWX PVC needed on k3s). To
  reuse the narration cache across renders, mount a RWX PVC at `/clips` instead.
- The worker holds **no** ElevenLabs/Anthropic key; narration is the sidecar.
- **Downloads:** the presigned URL uses `MINIO_ENDPOINT`, which is the in-cluster
  service DNS — reachable from inside the cluster. For downloads from outside,
  expose MinIO (ingress/LoadBalancer) and point `MINIO_ENDPOINT` at that public
  host (a split connect-vs-public presign host is a small follow-up if you need
  both). Until then, pull results with `mc`/`kubectl port-forward svc/minio`.
