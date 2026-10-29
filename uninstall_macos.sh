#!/usr/bin/env bash
# ==============================================================================
# Tasmota Speaker Guard - macOS Uninstaller
# ==============================================================================
PLIST_NAME="com.sykir.tasmotaspeakerguard.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo -e "\033[1;33mUnloading LaunchAgent...\033[0m"
if [ -f "$PLIST_FILE" ]; then
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    rm -f "$PLIST_FILE"
    echo -e "\033[1;32mPlist file removed ($PLIST_FILE).\033[0m"
fi

echo -e "\033[1;32mUninstallation complete.\033[0m"
