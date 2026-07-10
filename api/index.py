"""Vercel Python entrypoint for Balamonis Studio.

Balamonis Studio is a local, agent-driven video production toolkit — it has no
application server of its own. This module exists purely so the repository has a
valid Vercel deployment target: a tiny, dependency-free serverless function that
serves a static landing page. It intentionally imports nothing from the toolkit
(`tools/`, `lib/`, …) so the deploy never depends on the full toolchain.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler

PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Balamonis Studio</title>
  <meta name="description" content="Balamonis Studio — an open-source, agentic video production system." />
  <style>
    :root { color-scheme: dark; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
      background: radial-gradient(1200px 600px at 50% -10%, #16203a 0%, #0b0f1a 60%, #070910 100%);
      color: #f5f7fb;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, system-ui, sans-serif;
      -webkit-font-smoothing: antialiased;
    }
    main { padding: 48px 24px; max-width: 720px; text-align: center; }
    .brand {
      font-size: clamp(40px, 8vw, 76px);
      font-weight: 800;
      letter-spacing: -0.03em;
      margin: 0 0 12px;
      background: linear-gradient(180deg, #ffffff, #9fb4e6);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }
    .tagline { font-size: clamp(16px, 3.5vw, 22px); color: #aab3c9; margin: 0 0 28px; }
    p.lead { font-size: 16px; line-height: 1.6; color: #c7cede; margin: 0 auto 32px; max-width: 560px; }
    .pill {
      display: inline-block; padding: 8px 16px; border-radius: 999px;
      border: 1px solid #2a3656; background: #121a2e; color: #aab3c9;
      font-size: 13px; letter-spacing: 0.02em;
    }
    footer { margin-top: 40px; font-size: 13px; color: #6b768f; }
    a { color: #8fb0ff; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <main>
    <h1 class="brand">Balamonis Studio</h1>
    <p class="tagline">The open-source, agentic video production system.</p>
    <p class="lead">
      Describe what you want in plain language — the agent handles research,
      scripting, asset generation, editing, and final composition, rendering a
      finished video through Remotion or HyperFrames.
    </p>
    <span class="pill">Agent-driven · Remotion + HyperFrames · Open source</span>
    <footer>
      Built on the open-source
      <a href="https://github.com/calesthio/OpenMontage">OpenMontage</a> project.
    </footer>
  </main>
</body>
</html>
"""


class handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (Vercel's expected method name)
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
