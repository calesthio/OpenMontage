FROM python:3.11-slim-bookworm

ARG NODE_MAJOR=22
ARG REMOTION_VERSION=4.0.484
ARG REMOTION_CHROMIUM_SHA256=""
ARG REMOTION_CHROMIUM_SHA256_ARM64=28b420325c2ff7d088e2f8c8a776f10b17a9f1ff22d8c319a7b79a2792ea6404
ARG REMOTION_CHROMIUM_SHA256_X64=47e823e3a14b431ffa8dc88f97db6a854cd92e04800c01fc765c16a18d393d72
ARG RAY_REPO_SHA=unknown

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    OPENMONTAGE_PROJECTS_DIR=/data/projects \
    RAY_REPO_SHA=${RAY_REPO_SHA} \
    RAY_RENDER_CONCURRENCY=1 \
    REMOTION_BROWSER_EXECUTABLE=/usr/local/bin/remotion-browser \
    NODE_OPTIONS=--max-old-space-size=4096

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      bash \
      ca-certificates \
      curl \
      ffmpeg \
      git \
      gnupg \
      fonts-dejavu-core \
      fonts-dejavu-extra \
      fonts-noto-core \
      fonts-noto-color-emoji \
      libasound2 \
      libatk-bridge2.0-0 \
      libatk1.0-0 \
      libcups2 \
      libdbus-1-3 \
      libdrm2 \
      libgbm1 \
      libglib2.0-0 \
      libgtk-3-0 \
      libnspr4 \
      libnss3 \
      libx11-6 \
      libxcb1 \
      libxcomposite1 \
      libxdamage1 \
      libxext6 \
      libxfixes3 \
      libxkbcommon0 \
      libxrandr2 \
      xdg-utils \
    && curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt setup.py ./
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt "pytest>=8.0"

COPY remotion-composer/package*.json ./remotion-composer/
RUN cd remotion-composer && npm ci

COPY . .
RUN python -m pip install --no-cache-dir -e .

RUN cd remotion-composer \
    && node -e "const v=require('./package-lock.json').packages['node_modules/remotion'].version; if (v !== process.env.REMOTION_VERSION && v !== '${REMOTION_VERSION}') { throw new Error('Unexpected Remotion version '+v); } console.log('Remotion', v)" \
    && npx remotion browser ensure \
    && browser_path="$(find node_modules/.remotion -type f \( -name headless_shell -o -name chrome-headless-shell -o -name chrome -o -name chromium \) | head -n 1)" \
    && test -n "$browser_path" \
    && chmod +x "$browser_path" \
    && mkdir -p /opt/remotion \
    && ln -sf "/app/remotion-composer/$browser_path" "$REMOTION_BROWSER_EXECUTABLE" \
    && test "$(stat -c%s "$browser_path")" -gt 50000000 \
    && sha256sum "$browser_path" | tee /opt/remotion/browser.sha256 \
    && if [ -n "$REMOTION_CHROMIUM_SHA256" ]; then \
         echo "$REMOTION_CHROMIUM_SHA256  $browser_path" | sha256sum -c -; \
	       elif [ "$(uname -m)" = "aarch64" ] && [ -n "$REMOTION_CHROMIUM_SHA256_ARM64" ]; then \
	         echo "$REMOTION_CHROMIUM_SHA256_ARM64  $browser_path" | sha256sum -c -; \
	       elif [ "$(uname -m)" = "x86_64" ] && [ -n "$REMOTION_CHROMIUM_SHA256_X64" ]; then \
	         echo "$REMOTION_CHROMIUM_SHA256_X64  $browser_path" | sha256sum -c -; \
	       else \
	         echo "No Chromium SHA pin configured for $(uname -m); set REMOTION_CHROMIUM_SHA256 to enforce."; \
	       fi

RUN npx --yes hyperframes --version

RUN python scripts/remotion_smoke_render.py \
    --frames 0-9 \
    --output /tmp/openmontage-build-smoke.mp4 \
    --require-browser-executable

EXPOSE 8080

CMD ["bash", "scripts/fly-start.sh"]
