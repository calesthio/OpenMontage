# Deploy: tutorial render worker + ttsd sidecar on k8s

Two images run together in one Job pod:

- **worker** (`deploy/Dockerfile`) — captures a Cypress tutorial spec and renders
  the final video. Base `cypress/included` (Node + Cypress + browsers + Xvfb) +
  Python + ffmpeg + both repos.
- **ttsd** (`circuit-bid/redis-bridge/Dockerfile.ttsd`) — the narration sidecar.
  Holds the `ELEVENLABS_*` secret; the worker calls it over `localhost:5557`.

## Build

The worker build context must contain both repos side by side:

```
context/
  openmontage/   # this repo
  client/        # circuitauction-backoffice/client
```

```bash
# worker (renders via Remotion by default — animated callouts/zoom)
docker build -f openmontage/deploy/Dockerfile -t <registry>/tutorial-worker:latest context/
#   add --build-arg INSTALL_REMOTION=false for a lighter ffmpeg-only image
#   (then set RENDER_RUNTIME=ffmpeg)

# ttsd (from the circuit-bid repo)
docker build -f redis-bridge/Dockerfile.ttsd -t <registry>/circuit-ttsd:latest redis-bridge/

docker push <registry>/tutorial-worker:latest
docker push <registry>/circuit-ttsd:latest
```

Put a `.dockerignore` in `context/` excluding `**/node_modules`, `**/projects`,
`**/.git`, `**/cypress/videos` to keep the build fast (the image installs its own
`node_modules`).

## Deploy (k3s)

```bash
kubectl apply -f openmontage/deploy/k8s/
# then trigger a render on demand:
curl -XPOST http://<render-api-ingress>/renders \
  -H 'content-type: application/json' \
  -d '{"tutorial":"sales-tour","base_url":"https://<demo-host>"}'
```

See `deploy/k8s/README.md` for the manifest set, secrets, and the render-api.

## Verify locally without k8s

```bash
# assemble with silent placeholder narration (no ttsd) against an existing capture:
python render_tutorial.py --tutorial sales-tour --client-dir ../circuitauction-backoffice/client \
  --project-id smoke --offline-narration --capture raw.mp4 --manifest manifest.json
```
