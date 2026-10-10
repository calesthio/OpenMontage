---
name: circuit-video
description: >
  Drive the OpenMontage Circuit-video generator as an MCP. Use when the user
  wants a Cypress tutorial video of Circuit backoffice, to call the video
  generator with a demo-app URL, to upload the MP4 to AWS S3, or when they
  mention Circuit-video, tutorialctl, render_tutorial, sales-tour, or
  /circuit-video.
---

# Circuit-video MCP

This branch (`Circuit-video`) turns a Circuit backoffice Cypress walkthrough
into a 1080p tutorial MP4 and can publish it to AWS S3. Agents call the
**circuit-video MCP**, not ad-hoc Python.

Authoring a new spec is a different skill: `.agents/skills/cypress-recording/SKILL.md`.

## What this branch built

Deterministic re-render of a locked recipe (no LLM in the render loop):

1. Cypress `*.tutorial.cy.js` records the demo app (CDP screencast + drift markers).
2. `tools/capture/cypress_bridge.py` normalizes to 1920×1080 CFR.
3. Narration: `ttsd` sidecar (default) or ElevenLabs direct (`narration_backend=elevenlabs`,
   optional `voice_id`; clip cache in `.cache/narration/`); `--offline` skips it.
4. `render_tutorial.py` assembles intro/body/outro (`ffmpeg` or Remotion `screencast_scene`).
5. Output: `projects/<id>/renders/final.mp4`.
6. k8s path (`deploy/`): render-api Job + ttsd sidecar + **MinIO**.
7. MCP path (`mcp_servers/circuit_video/`): same local renderer, then **AWS S3**.

Local CLI remains `tutorialctl` (`list` / `doctor` / `render`). The MCP is the
same generator with a tool interface plus S3.

`base_url` is the demo environment Cypress hits. Recording mutates state — never
point it at production.

## First call

1. Confirm the MCP is up (`/mcps`, server `circuit-video`). If it is missing,
   the project file is `.grok/config.toml`; reload with `r` in `/mcps`.
   Grok only starts repo-local MCP servers when the OpenMontage folder is trusted.
2. `search_tool` for `circuit-video` / `render_tutorial`.
3. `use_tool` `circuit-video__list_tutorials` (or `doctor` if the env is unknown).
4. `use_tool` `circuit-video__render_tutorial` with the demo URL and tutorial name.

Required input for a render:

- `base_url` — http(s) URL of the **resettable demo** Cypress records against.
- `tutorial` — spec stem (e.g. `sales-tour`). Skip only when `list_tutorials`
  returns exactly one spec.

Useful optional fields: `offline` (silent audio), `render_runtime`
(`ffmpeg` | `remotion`), `upload` (default true), `wait` (default true).
Renders take minutes; if the host may time out, `wait: false` then poll
`get_render`.

Tell the user the `render_id`, local path, `s3_uri`, and `download_url`.

## S3

The MCP uploads to AWS S3 (not the k8s MinIO). Variable names, bucket, and
prefix live in `mcp_servers/circuit_video/env.example`. Export
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from the Circuit AWS s3 notes
(`circuit-kubernetes/tmp/secret.yml`, section `bAWS s3`) into the environment.

Do not read `secret.yml` from the MCP: that file also holds GitHub tokens and
VPN passwords. If upload is skipped, say so and leave the local MP4 path.
Default download URL is a 24h presigned GET.

`upload_video` publishes an already-rendered `final.mp4` without re-capturing.

## Remote k8s

When `CIRCUIT_VIDEO_RENDER_API_URL` is set, `render_tutorial` POSTs
`{tutorial, base_url}` to the render-api (`deploy/k8s/README.md`) instead of
running Cypress on this machine. `get_render` polls that API.

## Do not

- Bypass this MCP with a one-off `render_tutorial.py` call unless the MCP is
  unavailable (`doctor` will say why).
- Use a production Circuit URL as `base_url`.
- Put AWS keys in `.grok/config.toml` or in this skill.
