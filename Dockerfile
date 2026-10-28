FROM python:3.12-slim-bookworm

# FFmpeg for assembly, Node 22 for Remotion and HyperFrames (HyperFrames needs >= 22),
# and the shared libraries the headless Chrome used by Remotion links against.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl ca-certificates gnupg git make \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 libxcomposite1 \
        libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 libcairo2 fonts-liberation \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip install --no-cache-dir piper-tts
COPY remotion-composer/package*.json remotion-composer/
RUN cd remotion-composer && npm install
COPY . .
RUN cp -n .env.example .env

# Run as a regular user (uid 1000) so renders on a mounted folder are not owned by root.
# Remotion and webpack write caches under node_modules/.remotion and .cache, so those must be writable too.
RUN useradd -m -u 1000 montage \
    && mkdir -p remotion-composer/node_modules/.remotion remotion-composer/node_modules/.cache projects \
    && chown -R montage:montage remotion-composer/node_modules/.remotion remotion-composer/node_modules/.cache projects
USER montage

# Productions and renders are written under /app/projects; mount it to keep them.
VOLUME ["/app/projects"]
CMD ["python", "render_demo.py", "--list"]
