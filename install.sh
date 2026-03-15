#!/usr/bin/env bash

# VideoFaceSwap installer (Ubuntu 22.04+)
# This script clones the repository (if not present), installs dependencies, creates a venv,
# installs requirements, and registers a systemd service to run the app on port 80.

set -euo pipefail

REPO_URL="https://github.com/imranhameedw2/videofaceswap.git"
ROOT_DIR="$HOME/videofaceswap"
VENV_DIR="$ROOT_DIR/.venv"
SERVICE_NAME="videofaceswap.service"
PYTHON_BIN="$VENV_DIR/bin/python"

echo "=== VideoFaceSwap Installer ==="

# Clone the repository if it doesn't exist
if [[ ! -d "$ROOT_DIR" ]]; then
  echo "Cloning VideoFaceSwap repository to $ROOT_DIR..."
  git clone "$REPO_URL" "$ROOT_DIR"
else
  echo "Repository already exists at $ROOT_DIR. Pulling latest changes..."
  cd "$ROOT_DIR"
  git pull origin main
fi

cd "$ROOT_DIR"

echo "ROOT_DIR: $ROOT_DIR"  # Debug: show where the script thinks the repo is

test -f "$ROOT_DIR/app.py" || {
  echo "ERROR: app.py not found in $ROOT_DIR. Repository may be corrupted." >&2
  exit 1
}

if [[ $(id -u) -ne 0 ]]; then
  echo "This installer needs to run with sudo/root to bind to port 80 and register a systemd service."
  echo "Run it again using: sudo $0"
  exit 1
fi

echo "Updating apt packages..."
# Some environments include a yarn APT source that cannot be securely updated.
# Disable it to prevent `apt-get update` failures.
if [[ -f "/etc/apt/sources.list.d/yarn.list" ]]; then
  mv /etc/apt/sources.list.d/yarn.list /etc/apt/sources.list.d/yarn.list.disabled
fi
apt-get update -y

echo "Installing system dependencies..."
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-pip \
  build-essential \
  libatlas-base-dev \
  libavcodec-dev libavformat-dev libavdevice-dev libavutil-dev libswscale-dev \
  libsm6 libxext6 \
  ffmpeg \
  git

# Create venv
if [[ ! -d "$VENV_DIR" ]]; then
  echo "Creating Python virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# Upgrade pip in venv
"$VENV_DIR/bin/pip" install --upgrade pip

# Install Python requirements
"$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt"

# Create systemd service
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
cat > "$SERVICE_PATH" <<'EOF'
[Unit]
Description=VideoFaceSwap Web Service
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/videofaceswap
Environment=PYTHONUNBUFFERED=1
ExecStart=%h/videofaceswap/.venv/bin/python %h/videofaceswap/app.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

# Ensure permissions (service uses home path, adjust if needed)
chmod 644 "$SERVICE_PATH"

# Enable and start
systemctl daemon-reload
systemctl enable --now "$SERVICE_NAME"

echo ""
echo "✅ VideoFaceSwap installed and running."

# Detect GitHub Codespaces and provide the appropriate URL
if [[ -n "${CODESPACE_NAME:-}" ]]; then
  echo "Visit: https://$CODESPACE_NAME-8000.app.github.dev/"
else
  echo "Visit: http://localhost:8000/"
fi

echo "To check status: sudo systemctl status $SERVICE_NAME"
echo "To stop: sudo systemctl stop $SERVICE_NAME"
