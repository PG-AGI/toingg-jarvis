#!/bin/bash
# Run this ONCE in Terminal to fix Mac permissions, then double-click JARVIS.command forever after.
# Usage: bash setup_mac.sh

cd "$(dirname "$0")"

echo "Fixing permissions..."
chmod +x JARVIS.command
xattr -d com.apple.quarantine JARVIS.command 2>/dev/null || true
xattr -d com.apple.quarantine jarvis_launcher.py 2>/dev/null || true
xattr -d com.apple.quarantine jarvis_terminal.py 2>/dev/null || true

echo "Done. You can now double-click JARVIS.command anytime."
