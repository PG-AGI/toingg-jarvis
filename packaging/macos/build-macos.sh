#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DIST_DIR="$ROOT_DIR/dist/macos"
APP_BUNDLE="$DIST_DIR/JARVIS.app"
APP_RESOURCES="$APP_BUNDLE/Contents/Resources/app"

rm -rf "$DIST_DIR"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_RESOURCES"

rsync -a \
  --exclude ".git" \
  --exclude ".github" \
  --exclude "dist" \
  --exclude "build" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".browser-profile" \
  --exclude ".browser-profile-test" \
  "$ROOT_DIR/" "$APP_RESOURCES/"

install -m 0755 "$ROOT_DIR/packaging/macos/jarvis-macos-launcher" "$APP_BUNDLE/Contents/MacOS/JARVIS"
install -m 0644 "$ROOT_DIR/packaging/macos/Info.plist" "$APP_BUNDLE/Contents/Info.plist"
chmod +x "$APP_RESOURCES/JARVIS.command"

(cd "$DIST_DIR" && zip -qry JARVIS.app.zip JARVIS.app)
hdiutil create -volname "J.A.R.V.I.S" -srcfolder "$APP_BUNDLE" -ov -format UDZO "$DIST_DIR/JARVIS.dmg"
