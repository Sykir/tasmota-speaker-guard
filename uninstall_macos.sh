#!/usr/bin/env bash
# ==============================================================================
# Desinstallation de Tasmota Speaker Guard sous macOS
# ==============================================================================
PLIST_NAME="com.sykir.tasmotaspeakerguard.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo -e "\033[1;33mDechargement du LaunchAgent...\033[0m"
if [ -f "$PLIST_FILE" ]; then
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    rm -f "$PLIST_FILE"
    echo -e "\033[1;32mFichier Plist supprime ($PLIST_FILE).\033[0m"
fi

echo -e "\033[1;32mDesinstallation terminee avec succes.\033[0m"
