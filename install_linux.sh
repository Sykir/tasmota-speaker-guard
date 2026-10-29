#!/usr/bin/env bash
# ==============================================================================
# Tasmota Speaker Guard - Linux Installer (systemd user service)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="tasmota-speaker-guard.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo -e "\033[1;36m========================================================\033[0m"
echo -e "\033[1;36m       Installing Tasmota Speaker Guard for Linux       \033[0m"
echo -e "\033[1;36m========================================================\033[0m"

# 1. Verify Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "\033[1;31m[ERROR] python3 is not installed.\033[0m"
    exit 1
fi

PYTHON_BIN="$(which python3)"

# 2. Install dependencies
echo -e "\033[1;33m[INFO] Verifying Python dependencies...\033[0m"
pip install -r "$SCRIPT_DIR/requirements.txt" || python3 -m pip install requests

# 3. Create systemd user directory
mkdir -p "$SYSTEMD_USER_DIR"

# 4. Generate systemd service file
SERVICE_FILE="$SYSTEMD_USER_DIR/$SERVICE_NAME"
echo -e "\033[1;33m[INFO] Generating systemd service: $SERVICE_FILE\033[0m"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Tasmota Speaker Guard - Smart audio-reactive speaker power manager
After=pipewire.service pulseaudio.service default.target

[Service]
Type=simple
WorkingDirectory=$SCRIPT_DIR
ExecStart=$PYTHON_BIN $SCRIPT_DIR/speaker_guard.py run
Restart=on-failure
RestartSec=5s
KillMode=mixed
TimeoutStopSec=5s

[Install]
WantedBy=default.target
EOF

# 5. Enable and start service
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

echo ""
echo -e "\033[1;32m[OK] systemd service installed and started successfully!\033[0m"
echo -e "Check service status: \033[1;37msystemctl --user status $SERVICE_NAME\033[0m"
echo -e "View real-time logs:  \033[1;37mjournalctl --user -u $SERVICE_NAME -f\033[0m"
echo ""
