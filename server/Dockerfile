FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install server deps
COPY server/requirements.txt /tmp/server_requirements.txt
RUN pip install --no-cache-dir -r /tmp/server_requirements.txt

# Install OpenMontage core deps
COPY requirements.txt /tmp/om_requirements.txt
RUN pip install --no-cache-dir -r /tmp/om_requirements.txt || true

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
