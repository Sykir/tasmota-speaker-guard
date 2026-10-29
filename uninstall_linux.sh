#!/usr/bin/env bash
# ==============================================================================
# Desinstallation de Tasmota Speaker Guard sous Linux
# ==============================================================================
SERVICE_NAME="tasmota-speaker-guard.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$SYSTEMD_USER_DIR/$SERVICE_NAME"

echo -e "\033[1;33mArret et desactivation du service...\033[0m"
systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true

if [ -f "$SERVICE_FILE" ]; then
    rm -f "$SERVICE_FILE"
    echo -e "\033[1;32mFichier de service supprime ($SERVICE_FILE).\033[0m"
fi

systemctl --user daemon-reload
echo -e "\033[1;32mDesinstallation terminee avec succes.\033[0m"
