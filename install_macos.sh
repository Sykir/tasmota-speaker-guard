#!/usr/bin/env bash
# ==============================================================================
# Installation de Tasmota Speaker Guard sous macOS (LaunchAgent launchd)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.sykir.tasmotaspeakerguard.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo -e "\033[1;36m========================================================\033[0m"
echo -e "\033[1;36m   Installation de Tasmota Speaker Guard pour macOS     \033[0m"
echo -e "\033[1;36m========================================================\033[0m"

# 1. Verification de Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "\033[1;31m[ERREUR] python3 n'est pas installe. Installez-le via brew install python3.\033[0m"
    exit 1
fi

PYTHON_BIN="$(which python3)"

# 2. Installation des dependances (requests)
echo -e "\033[1;33m[INFO] Verification des dependances Python...\033[0m"
pip3 install -r "$SCRIPT_DIR/requirements.txt" || python3 -m pip install requests

# 3. Creation du dossier LaunchAgents
mkdir -p "$LAUNCH_AGENTS_DIR"

# 4. Dechargement de l'ancienne version si presente
if [ -f "$PLIST_FILE" ]; then
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
fi

# 5. Generation du fichier Plist
echo -e "\033[1;33m[INFO] Generation de l'agent launchd : $PLIST_FILE\033[0m"

cat <<EOF > "$PLIST_FILE"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.sykir.tasmotaspeakerguard</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$SCRIPT_DIR/speaker_guard.py</string>
        <string>run</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$SCRIPT_DIR</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$SCRIPT_DIR/speaker_guard.log</string>
    <key>StandardErrorPath</key>
    <string>$SCRIPT_DIR/speaker_guard.log</string>
</dict>
</plist>
EOF

# 6. Chargement et demarrage immediat
launchctl load "$PLIST_FILE"

echo ""
echo -e "\033[1;32m[OK] LaunchAgent installe et demarre avec succes !\033[0m"
echo -e "Pour verifier : \033[1;37mlaunchctl list | grep tasmotaspeakerguard\033[0m"
echo -e "Consultez les logs dans : \033[1;37m$SCRIPT_DIR/speaker_guard.log\033[0m"
echo ""
