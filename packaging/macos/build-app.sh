#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="$ROOT/dist/toingg-jarvis.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$ROOT/jarvis_launcher.py" "$APP/Contents/MacOS/"
chmod +x "$APP/Contents/MacOS/jarvis_launcher.py"
cp "$ROOT/JARVIS_README.md" "$APP/Contents/Resources/" 2>/dev/null || true

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
 <key>CFBundleName</key><string>Toingg Jarvis</string>
 <key>CFBundleIdentifier</key><string>com.toingg.jarvis</string>
 <key>CFBundleExecutable</key><string>jarvis_launcher.py</string>
</dict>
</plist>
PLIST
