FROM python:3.12-slim

# curl is also how NodeSource's setup script is fetched below. The
# libnspr4/libnss3/... block is the standard Chrome/Puppeteer headless
# runtime dependency list — Remotion's `browser ensure` step below happily
# downloads chrome-headless-shell without them, but the binary then fails
# to LAUNCH at actual render time: "error while loading shared libraries:
# libnspr4.so: cannot open shared object file" (confirmed live 2026-07-21 —
# the download-only smoke test this Dockerfile was validated with never
# caught it, only a real render did).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl ca-certificates gnupg \
    libnspr4 libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22, needed for the Remotion render path (tools/video/video_compose.py
# shells out to `npx remotion render` — this image previously had no Node at
# all, so render_runtime="remotion" always reported unavailable). Debian
# trixie's own apt repo doesn't carry a recent-enough Node, hence NodeSource.
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install server deps
COPY server/requirements.txt /tmp/server_requirements.txt
RUN pip install --no-cache-dir -r /tmp/server_requirements.txt

# Install OpenMontage core deps
COPY requirements.txt /tmp/om_requirements.txt
RUN pip install --no-cache-dir -r /tmp/om_requirements.txt || true

# remotion-composer is NOT a docker-compose volume mount (unlike tools/lib/
# etc below) — its node_modules (and the headless-shell browser binary
# baked in by `remotion browser ensure`) must live inside the image, and a
# host bind-mount would shadow them with whatever (or nothing) is on the
# host's own remotion-composer/node_modules. video_compose.py resolves this
# directory as Path(__file__).parent.parent.parent / "remotion-composer",
# i.e. relative to tools/video/video_compose.py once tools/ is mounted at
# /app/tools — so it MUST land at exactly /app/remotion-composer.
COPY remotion-composer/ /app/remotion-composer/
RUN cd /app/remotion-composer \
    && npm install --no-audit --no-fund \
    && npx remotion browser ensure

# Copy source (tools/lib/etc mounted via docker-compose volumes in dev)
COPY server/ /app/server/

# The code imports the server package as top-level `app` (e.g.
# `from app.routers import ...`) and resolves the OpenMontage root as /app, so
# run from the server dir with both /app and /app/server on the path. Running
# `uvicorn server.app.main:app` from /app breaks: app/main.py's own
# `from app.routers import ...` finds no top-level `app` package there.
WORKDIR /app/server
ENV PYTHONPATH=/app:/app/server

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
