# Circuit-video MCP

stdio MCP server that drives the Circuit-video generator on this branch:
Cypress tutorial capture → OpenMontage `render_tutorial.py` → AWS S3 upload.

Grok (and any MCP host) can call `render_tutorial` with the **demo app URL**
Cypress should record against.

## Tools

| Tool | What it does |
|---|---|
| `list_tutorials` | Specs under `client/cypress/e2e-tutorials/*.tutorial.cy.js` |
| `doctor` | ffmpeg, ttsd, client specs, demo URL, AWS creds |
| `render_tutorial` | Capture + assemble. Required: `base_url`. Then uploads to S3. |
| `get_render` | Status / download URL for a `render_id` |
| `upload_video` | PUT an existing local MP4 to the same S3 bucket |

Authoring a new Cypress tutorial is a different workflow — see
`.agents/skills/cypress-recording/SKILL.md`. This server only **runs** a locked recipe.

## Run

From the OpenMontage repo root (stdout is the MCP channel):

```bash
python3 mcp_servers/circuit_video/server.py
```

Handshake smoke test:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | python3 mcp_servers/circuit_video/server.py
```

Grok is configured in `.grok/config.toml` as `mcp_servers.circuit-video`.
Reload with `/mcps` → `r`.

Claude Code picks it up automatically from the repo-root `.mcp.json`
(project-scoped, server name `circuit-video`). Start `claude` from the repo
root, approve the project server when prompted, and check with `/mcp`.

## S3

The k8s worker still uploads to **MinIO**. This MCP uploads to **AWS S3** using
the Circuit account keys (export them; do not commit):

```bash
# from circuit-kubernetes/tmp/secret.yml  →  "## bAWS s3"
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=eu-central-1
export CIRCUIT_VIDEO_S3_BUCKET=circuit-kubernetes
```

Objects: `s3://circuit-kubernetes/openmontage/tutorials/<render_id>/final.mp4`.
The tool response includes a 24-hour presigned GET URL.

## Local vs remote

- Default: run `render_tutorial.py` on this machine (needs Cypress, the demo
  app at `base_url`, and usually ttsd on `:5557` — `tutorialctl up`).
- If `CIRCUIT_VIDEO_RENDER_API_URL` is set, `render_tutorial` POSTs to the
  k8s render-api instead (`deploy/k8s/README.md`).

## Narration

- Default: the `ttsd` sidecar (`tutorialctl up`), one fixed voice per language.
- `narration_backend: "elevenlabs"` (tool argument, `TUTORIAL_NARRATION_BACKEND`,
  or `narration_backend` in the tutorial recipe `<name>.tutorial.json`) calls
  ElevenLabs directly using `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_IDS`; pass
  `voice_id` (tool argument, `TUTORIAL_VOICE_ID`, or recipe `voice_id`) to pick
  any voice. Precedence: tool/CLI argument > recipe > environment.
- Clips are cached under `.cache/narration/elevenlabs/` keyed on voice, model,
  settings and text, so authoring and rendering never pay twice.
- Changing the voice changes durations: re-run `tutorialctl author <name>` with
  the same backend/voice before rendering, or the capture pacing drifts (the
  render prints a WARN when `timings.json` disagrees).
- The k8s render-api path still uses the ttsd sidecar; `narration_backend` and
  `voice_id` are forwarded in the request body but not acted on there yet.
