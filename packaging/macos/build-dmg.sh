#!/usr/bin/env bash
set -euo pipefail

VERSION="${JARVIS_VERSION:-0.1.0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
APP_PATH="${ROOT_DIR}/dist/JARVIS.app"
FROZEN_DIR="${ROOT_DIR}/dist/JARVIS"
DMG_ROOT="${ROOT_DIR}/dist/dmg-root"
OUTPUT_DIR="${ROOT_DIR}/dist/installers"
DMG_PATH="${OUTPUT_DIR}/JARVIS-${VERSION}.dmg"

if [[ ! -d "${APP_PATH}" ]]; then
  if [[ ! -d "${FROZEN_DIR}" ]]; then
    echo "Missing app bundle at ${APP_PATH} or frozen app at ${FROZEN_DIR}" >&2
    exit 1
  fi
  mkdir -p "${APP_PATH}/Contents/MacOS" "${APP_PATH}/Contents/Resources"
  cp -R "${FROZEN_DIR}/." "${APP_PATH}/Contents/MacOS/"
  cat > "${APP_PATH}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>JARVIS</string>
  <key>CFBundleDisplayName</key><string>JARVIS</string>
  <key>CFBundleIdentifier</key><string>ai.pgagi.jarvis</string>
  <key>CFBundleVersion</key><string>${VERSION}</string>
  <key>CFBundleShortVersionString</key><string>${VERSION}</string>
  <key>CFBundleExecutable</key><string>jarvis_launcher</string>
</dict>
</plist>
EOF
fi

rm -rf "${DMG_ROOT}" "${DMG_PATH}"
mkdir -p "${DMG_ROOT}" "${OUTPUT_DIR}"
cp -R "${APP_PATH}" "${DMG_ROOT}/"
ln -s /Applications "${DMG_ROOT}/Applications"

hdiutil create \
  -volname "JARVIS ${VERSION}" \
  -srcfolder "${DMG_ROOT}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

echo "Created ${DMG_PATH}"
