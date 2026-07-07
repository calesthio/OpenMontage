# OpenMontage tutorial render worker.
#
# Runs render_tutorial.py: captures a Cypress *.tutorial.cy.js spec against a
# demo URL and assembles the finished video (ffmpeg). Narration comes from the
# `ttsd` sidecar over localhost, so NO ElevenLabs/Anthropic key lives here.
#
# Base image `cypress/included` already ships Node + the Cypress binary +
# browsers + Xvfb + all the system libraries Cypress needs; we add Python +
# ffmpeg + the two repos on top. Keep the tag in sync with the client's Cypress.
#
# Build context must contain both repos (see deploy/README.md), e.g.:
#   context/
#     openmontage/   (this repo)
#     client/        (circuitauction-backoffice/client)
#
#   docker build -f openmontage/deploy/Dockerfile -t <registry>/tutorial-worker:latest context/
#
# INSTALL_REMOTION (default true) installs remotion-composer deps so the worker can
# render via Remotion (animated callouts/zoom). Set false for an ffmpeg-only image.

FROM cypress/included:15.8.1

# Default true: the worker renders via Remotion (animated callouts/zoom). Set to
# false only for an ffmpeg-only (lighter) image.
ARG INSTALL_REMOTION=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-pip ffmpeg git curl ca-certificates fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# --- OpenMontage (Python) ---
COPY openmontage/ /app/openmontage/
RUN pip3 install --no-cache-dir --break-system-packages -r /app/openmontage/requirements.txt \
    && pip3 install --no-cache-dir --break-system-packages minio
RUN if [ "$INSTALL_REMOTION" = "true" ]; then \
      cd /app/openmontage/remotion-composer && (npm ci || npm install); \
    fi

# --- Client repo (Cypress specs) baked in with node_modules ---
# Runtime does only `git fetch && checkout <CLIENT_REF>` (see worker-entrypoint.sh),
# so a spec change never triggers a full npm install per render.
COPY client/ /app/client/
RUN cd /app/client && (npm ci || npm install)

COPY openmontage/deploy/worker-entrypoint.sh /usr/local/bin/worker-entrypoint.sh
RUN chmod +x /usr/local/bin/worker-entrypoint.sh

ENV OPENMONTAGE_PROJECTS_DIR=/work/projects \
    CLIENT_DIR=/app/client \
    NARRATION_URL=http://127.0.0.1:5557 \
    CYPRESS_NO_COMMAND_LOG=1
VOLUME ["/work"]
WORKDIR /app/openmontage

ENTRYPOINT ["/usr/local/bin/worker-entrypoint.sh"]
