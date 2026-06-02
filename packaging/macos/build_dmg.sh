#!/usr/bin/env bash
# Wraps the PyInstaller-built JARVIS.app into a .dmg.
# Usage:  VERSION=1.0.0 bash packaging/macos/build_dmg.sh
set -euo pipefail

VERSION="${VERSION:-0.0.0}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
APP="${ROOT}/dist/JARVIS.app"
OUT_DIR="${ROOT}/dist"
DMG="${OUT_DIR}/JARVIS-${VERSION}.dmg"
STAGE="${OUT_DIR}/dmg-stage"

if [[ ! -d "$APP" ]]; then
    echo "Missing $APP — run 'pyinstaller packaging/jarvis.spec' on macOS first." >&2
    exit 1
fi

rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

hdiutil create \
    -volname "JARVIS ${VERSION}" \
    -srcfolder "$STAGE" \
    -ov -format UDZO \
    "$DMG"

rm -rf "$STAGE"
echo "Built: $DMG"
