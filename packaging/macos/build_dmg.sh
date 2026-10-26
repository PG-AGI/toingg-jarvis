#!/usr/bin/env bash
# macOS .app Bundle & .dmg Disk Image Builder for J.A.R.V.I.S
set -euo pipefail

VERSION="2.0.0"
DIST_DIR="$(cd "$(dirname "$0")/../.." && pwd)/dist"
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="$2"
      shift 2
      ;;
    --dist-dir)
      DIST_DIR="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

APP_BUNDLE="${DIST_DIR}/JARVIS.app"
DMG_STAGING="${DIST_DIR}/dmg-staging"
DMG_PATH="${DIST_DIR}/JARVIS-${VERSION}-macOS.dmg"

echo "[macOS] Packaging JARVIS v${VERSION}"
echo "[macOS] App Bundle : ${APP_BUNDLE}"
echo "[macOS] Output DMG : ${DMG_PATH}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[macOS] Dry run complete."
  exit 0
fi

# Ensure .app structure exists (if PyInstaller produced dist/JARVIS folder instead of .app)
if [[ ! -d "${APP_BUNDLE}" ]]; then
  mkdir -p "${APP_BUNDLE}/Contents/MacOS"
  mkdir -p "${APP_BUNDLE}/Contents/Resources"
  if [[ -d "${DIST_DIR}/JARVIS" ]]; then
    cp -R "${DIST_DIR}/JARVIS/"* "${APP_BUNDLE}/Contents/MacOS/"
  fi
fi

cat > "${APP_BUNDLE}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>JARVIS</string>
  <key>CFBundleDisplayName</key>
  <string>J.A.R.V.I.S Voice Terminal</string>
  <key>CFBundleIdentifier</key>
  <string>com.pgagi.toingg.jarvis</string>
  <key>CFBundleVersion</key>
  <string>${VERSION}</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundleExecutable</key>
  <string>JARVIS</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.15</string>
  <key>NSMicrophoneUsageDescription</key>
  <string>JARVIS requires microphone access for wake-word and voice command detection.</string>
  <key>NSAppleEventsUsageDescription</key>
  <string>JARVIS uses AppleEvents to focus and position desktop applications.</string>
</dict>
</plist>
EOF

rm -rf "${DMG_STAGING}"
mkdir -p "${DMG_STAGING}"
cp -R "${APP_BUNDLE}" "${DMG_STAGING}/JARVIS.app"
ln -s /Applications "${DMG_STAGING}/Applications"

rm -f "${DMG_PATH}"
hdiutil create \
  -volname "JARVIS ${VERSION}" \
  -srcfolder "${DMG_STAGING}" \
  -ov \
  -format UDZO \
  "${DMG_PATH}"

rm -rf "${DMG_STAGING}"
echo "[macOS] Created ${DMG_PATH}"
