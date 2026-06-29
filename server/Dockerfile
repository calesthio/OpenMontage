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

EXPOSE 8000
CMD ["uvicorn", "server.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
