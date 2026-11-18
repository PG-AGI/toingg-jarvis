#!/bin/bash
# Executable inside Toingg Jarvis.app. Runs the app from a per-user copy because
# the app writes config.json next to its code and the bundle may be read-only.
SRC="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
DEST="$HOME/Library/Application Support/Toingg Jarvis"

mkdir -p "$DEST"
cp -f "$SRC"/*.py "$SRC"/*.html "$DEST/"
[ -f "$DEST/config.json" ] || cp "$SRC/config.example.json" "$DEST/config.json"

# Open the existing launcher script in Terminal; it installs dependencies and starts Jarvis.
cp -f "$SRC/JARVIS.command" "$DEST/JARVIS.command"
chmod +x "$DEST/JARVIS.command"
open -a Terminal "$DEST/JARVIS.command"
