#!/usr/bin/env bash
set -euo pipefail
APP="${1:-dist/JARVIS.app}"
OUTPUT="${2:-dist/installers/JARVIS-macOS.dmg}"
test -d "$APP" || { echo "Missing .app bundle: $APP" >&2; exit 1; }
mkdir -p "$(dirname "$OUTPUT")"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
ditto "$APP" "$STAGE/JARVIS.app"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "JARVIS" -srcfolder "$STAGE" -format UDZO -ov "$OUTPUT"
echo "Created unsigned DMG: $OUTPUT"
