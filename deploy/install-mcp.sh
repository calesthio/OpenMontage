#!/usr/bin/env bash
set -euo pipefail

# Run on Ubuntu/Debian after this repository has been checked out.
# Example: sudo bash deploy/install-mcp.sh
APP_DIR="${APP_DIR:-/opt/OpenMontage}"
SERVICE_USER="${SERVICE_USER:-openmontage}"
ENV_DIR="/etc/openmontage"
ENV_FILE="$ENV_DIR/mcp.env"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo bash deploy/install-mcp.sh" >&2
  exit 1
fi
if [[ "$APP_DIR" != /* || "$APP_DIR" == *"|"* || "$APP_DIR" == *" "* ]]; then
  echo "APP_DIR must be an absolute path without spaces or '|'." >&2
  exit 1
fi
if [[ ! "$SERVICE_USER" =~ ^[a-z_][a-z0-9_-]*[$]?$ ]]; then
  echo "SERVICE_USER must be a valid Linux service account name." >&2
  exit 1
fi
if [[ ! -f "$APP_DIR/integrations/mcp_server/server.py" ]]; then
  echo "ERROR: MCP source not found at $APP_DIR/integrations/mcp_server/server.py" >&2
  exit 1
fi
if [[ ! -f "$APP_DIR/requirements.txt" || ! -f "$APP_DIR/deploy/openmontage-mcp.service.example" ]]; then
  echo "ERROR: requirements.txt or systemd unit template is missing." >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx openssl

if ! id "$SERVICE_USER" >/dev/null 2>&1; then
  useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
fi
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_DIR"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" /var/lib/openmontage
install -d -o root -g "$SERVICE_USER" -m 0750 "$ENV_DIR"

if [[ ! -f "$ENV_FILE" ]]; then
  TOKEN="$(openssl rand -hex 32)"
  umask 027
  printf 'OM_MCP_BEARER_TOKEN=%s\n' "$TOKEN" > "$ENV_FILE"
  chown root:"$SERVICE_USER" "$ENV_FILE"
  chmod 0640 "$ENV_FILE"
  echo "Created $ENV_FILE with a generated bearer token."
  echo "Store this token securely; do not commit or paste it into chat."
else
  echo "Preserving existing $ENV_FILE"
  chown root:"$SERVICE_USER" "$ENV_FILE"
  chmod 0640 "$ENV_FILE"
fi

chown -R "$SERVICE_USER":"$SERVICE_USER" "$APP_DIR"
sudo -u "$SERVICE_USER" "$PYTHON_BIN" -m venv "$APP_DIR/.venv"
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
sudo -u "$SERVICE_USER" "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

# Render the unit with the configured paths/account instead of silently using
# the template's defaults when APP_DIR or SERVICE_USER has been overridden.
sed \
  -e "s|^User=openmontage$|User=$SERVICE_USER|" \
  -e "s|^Group=openmontage$|Group=$SERVICE_USER|" \
  -e "s|^WorkingDirectory=/opt/OpenMontage$|WorkingDirectory=$APP_DIR|" \
  -e "s|^ExecStart=/opt/OpenMontage/.venv/bin/python -m integrations.mcp_server.server$|ExecStart=$APP_DIR/.venv/bin/python -m integrations.mcp_server.server|" \
  "$APP_DIR/deploy/openmontage-mcp.service.example" > /etc/systemd/system/openmontage-mcp.service
chmod 0644 /etc/systemd/system/openmontage-mcp.service
systemctl daemon-reload
systemctl enable --now openmontage-mcp.service
systemctl --no-pager --full status openmontage-mcp.service || true

cat <<'EOF'

Service installed. Backend listens on 127.0.0.1:8000.
Next: configure a domain and TLS certificate, then configure the HTTPS reverse
proxy using deploy/nginx-openmontage-mcp.conf.example. Do not expose port 8000.
EOF
