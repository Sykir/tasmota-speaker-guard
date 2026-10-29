#!/usr/bin/env bash
# ==============================================================================
# Tasmota Speaker Guard - macOS Installer (launchd LaunchAgent)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_NAME="com.sykir.tasmotaspeakerguard.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$LAUNCH_AGENTS_DIR/$PLIST_NAME"

echo -e "\033[1;36m========================================================\033[0m"
echo -e "\033[1;36m       Installing Tasmota Speaker Guard for macOS       \033[0m"
echo -e "\033[1;36m========================================================\033[0m"

# 1. Verify Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "\033[1;31m[ERROR] python3 is not installed. Please install it (e.g. brew install python3).\033[0m"
    exit 1
fi

PYTHON_BIN="$(which python3)"

# 2. Install dependencies
echo -e "\033[1;33m[INFO] Verifying Python dependencies...\033[0m"
pip3 install -r "$SCRIPT_DIR/requirements.txt" || python3 -m pip install requests

# 3. Create LaunchAgents directory
mkdir -p "$LAUNCH_AGENTS_DIR"

# 4. Unload older agent if present
if [ -f "$PLIST_FILE" ]; then
    launchctl unload "$PLIST_FILE" 2>/dev/null || true
fi

# 5. Generate Plist file
echo -e "\033[1;33m[INFO] Generating launchd agent: $PLIST_FILE\033[0m"

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

# 6. Load and start agent
launchctl load "$PLIST_FILE"

echo ""
echo -e "\033[1;32m[OK] LaunchAgent installed and loaded successfully!\033[0m"
echo -e "Check status: \033[1;37mlaunchctl list | grep tasmotaspeakerguard\033[0m"
echo -e "Logs saved to: \033[1;37m$SCRIPT_DIR/speaker_guard.log\033[0m"
echo ""
