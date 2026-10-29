#!/usr/bin/env bash
# ==============================================================================
# Installation de Tasmota Speaker Guard sous Linux (Service systemd utilisateur)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="tasmota-speaker-guard.service"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

echo -e "\033[1;36m========================================================\033[0m"
echo -e "\033[1;36m  Installation de Tasmota Speaker Guard pour Linux      \033[0m"
echo -e "\033[1;36m========================================================\033[0m"

# 1. Verification de Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "\033[1;31m[ERREUR] python3 n'est pas installe.\033[0m"
    exit 1
fi

PYTHON_BIN="$(which python3)"

# 2. Installation des dependances (requests)
echo -e "\033[1;33m[INFO] Verification des dependances Python...\033[0m"
pip install -r "$SCRIPT_DIR/requirements.txt" || python3 -m pip install requests

# 3. Creation du dossier systemd utilisateur
mkdir -p "$SYSTEMD_USER_DIR"

# 4. Creation du fichier de service systemd
SERVICE_FILE="$SYSTEMD_USER_DIR/$SERVICE_NAME"
echo -e "\033[1;33m[INFO] Generation du service systemd : $SERVICE_FILE\033[0m"

cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=Tasmota Speaker Guard - Gestion intelligente des enceintes audio
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

# 5. Activation et demarrage du service
systemctl --user daemon-reload
systemctl --user enable "$SERVICE_NAME"
systemctl --user restart "$SERVICE_NAME"

echo ""
echo -e "\033[1;32m[OK] Service systemd installe et demarre avec succes !\033[0m"
echo -e "Pour verifier le statut : \033[1;37msystemctl --user status $SERVICE_NAME\033[0m"
echo -e "Pour voir les logs :      \033[1;37mjournalctl --user -u $SERVICE_NAME -f\033[0m"
echo ""
