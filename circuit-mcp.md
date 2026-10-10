# Circuit MCP — connect and use

Use the **circuit-video** MCP to turn a Circuit backoffice Cypress tutorial into
a 1080p MP4, then upload it to AWS S3.

You pass the **demo app URL**. The server runs the Cypress spec against that
URL, assembles the video, and (when AWS keys are set) returns a download link.

`base_url` must be a **resettable demo environment**, never production.

Server code: `mcp_servers/circuit_video/`
Grok project config: `.grok/config.toml`
Env names: `mcp_servers/circuit_video/env.example`

---

## 1. Prerequisites

From the OpenMontage repo root:

```bash
python3 mcp_servers/circuit_video/server.py --help
```

Needs:

- Python 3 (stdlib only — no extra pip packages)
- `ffmpeg` / `ffprobe`
- Node + Cypress in `circuitauction-backoffice/client`
- A demo URL Cypress can reach
- For spoken narration: `ttsd` on `http://127.0.0.1:5557` (`tutorialctl up`), or
  `narration_backend=elevenlabs` with `ELEVENLABS_API_KEY` + `ELEVENLABS_VOICE_IDS`
  (or a `voice_id`) to call ElevenLabs directly
- For S3 upload: AWS keys in the environment (see [S3](#4-s3-upload))

Paths default from `tutorial.config.json`. Override with `TUTORIAL_CLIENT_DIR`,
`TUTORIAL_BASE_URL`, `TUTORIAL_NARRATION_URL`, `TUTORIAL_RENDER_RUNTIME`,
`TUTORIAL_NARRATION_BACKEND`, `TUTORIAL_VOICE_ID`.

Smoke-test the protocol (no Cypress):

```bash
printf '%s\n' \
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}}' \
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' \
  | python3 mcp_servers/circuit_video/server.py
```

You should see `serverInfo.name = circuit-video` and five tools.

Check the machine:

```bash
grok mcp doctor circuit-video
```

Healthy looks like: command found, server started, handshake OK, 5 tools.

Grok only starts **repo-local** MCP servers when the OpenMontage folder is
trusted. If doctor says `folder untrusted`, trust this repo in Grok first.

---

## 2. Connect the MCP

Always launch from the **OpenMontage repo root**. `stdout` is the MCP channel;
do not wrap the command in anything that prints to stdout.

### Grok (this repo)

Already registered in `.grok/config.toml`:

```toml
[mcp_servers.circuit-video]
command = "python3"
args = ["mcp_servers/circuit_video/server.py"]
enabled = true
startup_timeout_sec = 15
tool_timeout_sec = 2400
tool_timeouts = { render_tutorial = 2400, upload_video = 300, doctor = 60, list_tutorials = 30, get_render = 120 }
```

Or:

```bash
grok mcp add --scope project circuit-video -- python3 mcp_servers/circuit_video/server.py
```

Then:

1. Open Grok in `/media/bl/Disk2/htdocs/OpenMontage` (or your clone).
2. Trust the folder if prompted.
3. `/mcps` → confirm `circuit-video` is enabled. Press `r` to reload.
4. Ask: “list Circuit tutorials” or “render sales-tour against https://DEMO”.

Slash command for the agent skill: `/circuit-video`.

### Claude Code / Cursor / other stdio hosts

```json
{
  "mcpServers": {
    "circuit-video": {
      "command": "python3",
      "args": ["mcp_servers/circuit_video/server.py"],
      "cwd": "/media/bl/Disk2/htdocs/OpenMontage"
    }
  }
}
```

Put that in `.mcp.json` (project), Claude’s MCP config, or Cursor’s
`.cursor/mcp.json`. Point `cwd` at this repo. Use an absolute path to
`server.py` if the host does not set cwd.

### Manual stdio

```bash
cd /media/bl/Disk2/htdocs/OpenMontage
python3 mcp_servers/circuit_video/server.py
```

The process reads JSON-RPC lines on stdin and writes lines on stdout.

---

## 3. Tools

In Grok, tool names are prefixed: `circuit-video__list_tutorials`.

| Tool | When to call | Arguments |
|---|---|---|
| `list_tutorials` | See which Cypress specs exist | none |
| `doctor` | Check ffmpeg, ttsd, demo URL, AWS | optional `base_url` |
| `render_tutorial` | **Record + assemble + upload** | **`base_url` required**; `tutorial`, `offline`, `render_runtime`, `upload`, `wait`, `project_id`, `music` |
| `get_render` | Poll a background / remote job | **`render_id` required**; optional `wait` |
| `upload_video` | Publish an existing MP4 | **`file_path` required**; optional `render_id`, `key` |

### `render_tutorial`

| Field | Required | Notes |
|---|---|---|
| `base_url` | yes | Demo URL Cypress records against (`https://…`) |
| `tutorial` | usually | Spec stem, e.g. `sales-tour`. Optional only if `list_tutorials` returns exactly one spec |
| `offline` | no | `true` = silent audio (no ttsd). Default `false` |
| `render_runtime` | no | `ffmpeg` (default) or `remotion` |
| `upload` | no | Upload to S3. Default `true` |
| `wait` | no | Block until done. Default `true`. Set `false` and poll `get_render` for long jobs |
| `project_id` | no | Default `<tutorial>-<8 hex chars>` |
| `music` | no | Path or `music_library/` track name |

A render takes **5–20 minutes**. The Grok timeout for this tool is 2400s.

### Example (Grok)

1. `circuit-video__list_tutorials`
2. `circuit-video__doctor` with the demo URL
3. `circuit-video__render_tutorial`:

```json
{
  "tutorial": "sales-tour",
  "base_url": "https://YOUR-DEMO-HOST",
  "offline": false,
  "upload": true,
  "wait": true
}
```

Response includes `render_id`, `local_path` (`projects/<id>/renders/final.mp4`),
and when S3 worked: `s3_uri` and `download_url`.

Background:

```json
{
  "tutorial": "sales-tour",
  "base_url": "https://YOUR-DEMO-HOST",
  "wait": false
}
```

Then poll `get_render` with that `render_id`.

---

## 4. S3 upload

The k8s worker still uses MinIO. This MCP uses **AWS S3**.

Export keys (do not commit them; do not put them in `.grok/config.toml`).
Local notes: `circuit-kubernetes/tmp/secret.yml`, section `bAWS s3`.
Do not point the MCP at that file — it also holds GitHub tokens and VPN passwords.

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=eu-central-1
export CIRCUIT_VIDEO_S3_BUCKET=circuit-kubernetes
```

Optional: copy `mcp_servers/circuit_video/env.example` into OpenMontage `.env`
(gitignored).

Object key:

```
s3://circuit-kubernetes/openmontage/tutorials/<render_id>/final.mp4
```

`download_url` is a **24-hour presigned GET**. Missing AWS keys: render still
runs locally; the tool reports `upload_skipped`.

Already have an MP4? Call `upload_video` with `file_path`.

---

## 5. Typical session

```text
You: Render the sales tour against https://demo.example.com and put it on S3.

Agent:
  1. circuit-video__list_tutorials     → sales-tour
  2. circuit-video__doctor             → ffmpeg/ttsd/demo/AWS
  3. circuit-video__render_tutorial
       tutorial=sales-tour
       base_url=https://demo.example.com
  4. Return render_id, local path, s3_uri, download_url
```

Narration sidecar (skip if `offline: true`):

```bash
./tutorialctl up
```

Remote k8s instead of local Cypress: set `CIRCUIT_VIDEO_RENDER_API_URL` to the
render-api base (`deploy/k8s/README.md`). `get_render` polls that API.

---

## 6. Troubleshooting

| Symptom | Fix |
|---|---|
| `folder untrusted` | Trust the OpenMontage folder in Grok, then `/mcps` → `r` |
| Server missing in `/mcps` | Start Grok from this repo; config is `.grok/config.toml` |
| `ttsd … Connection refused` | `./tutorialctl up`, or render with `offline: true` |
| Demo URL unreachable | `base_url` must be reachable from this machine (or the k8s cluster, in remote mode) |
| `upload_skipped` | Export `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, restart Grok so the MCP inherits them |
| Unknown tutorial | `list_tutorials`; names match `*.tutorial.cy.js` stems |
| Handshake works, render hangs | Expected for 5–20 min; use `wait: false` + `get_render` |

Do not pass a production Circuit URL as `base_url`.
