# OpenMontage MCP for ChatGPT

This package exposes three read-only tools:

- `om_list_pipelines` — list pipeline manifests and declared stages.
- `om_get_capabilities` — return the registered tool inventory and availability.
- `om_estimate_production` — report a pipeline's declared default budget; it is not a live quote.

The MCP integration does not execute production tools, accept arbitrary paths, or run shell commands.

## Local stdio mode

Install dependencies and run:

```bash
python -m pip install -r requirements.txt
python -m integrations.mcp_server.server
```

## Remote Streamable HTTP mode

1. Deploy the repository to a dedicated Linux service account.
2. Create a virtual environment and install `requirements.txt`.
3. Generate a token, for example `openssl rand -hex 32`, and place it in a root-readable environment file based on `deploy/mcp.env.example`.
4. Configure the service from `deploy/openmontage-mcp.service.example` and the TLS reverse proxy from `deploy/nginx-openmontage-mcp.conf.example`.
5. Keep the Python listener bound to `127.0.0.1:8000`; expose only HTTPS via the reverse proxy. Do not open port 8000 publicly.
6. Start the systemd service and verify the endpoint through HTTPS. Requests without `Authorization: Bearer <token>` must return HTTP 401.
7. Add the HTTPS MCP URL (typically `https://YOUR_DOMAIN/mcp`) to ChatGPT's connector settings if the workspace plan supports custom MCP connectors and the chosen authentication method.

Environment variables:

- `OM_MCP_TRANSPORT=streamable-http`
- `OM_MCP_BEARER_TOKEN` — required, minimum 32 characters.
- `OM_MCP_HOST=127.0.0.1`
- `OM_MCP_PORT=8000`

The backend is deliberately read-only for this first milestone. Authenticated transport does not replace TLS, host firewalling, secret rotation, or deployment-specific access controls. The reverse-proxy example is a template; TLS certificate directives must be supplied by the server operator.

## Current scope and next step

The code provides discovery/preflight only. Actual remote deployment requires SSH/server access and a real domain/TLS configuration. Production execution, durable jobs, budget enforcement, and per-project authorization are not yet implemented.
