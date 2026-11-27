#!/usr/bin/env bash
# Target path in repo: packaging/macos/build_dmg.sh
set -euo pipefail

VERSION="${1:-2.0.0}"
APP_NAME="JARVIS.app"
STAGE_DIR="build/macos"
APP_DIR="${STAGE_DIR}/${APP_NAME}"

rm -rf "${STAGE_DIR}"
mkdir -p "${APP_DIR}/Contents/MacOS" "${APP_DIR}/Contents/Resources" dist/installers

cp -a dist/toingg-jarvis/* "${APP_DIR}/Contents/MacOS/"

cat > "${APP_DIR}/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Toingg JARVIS</string>
  <key>CFBundleIdentifier</key>
  <string>com.pgagi.toingg-jarvis</string>
  <key>CFBundleVersion</key>
  <string>${VERSION}</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundleExecutable</key>
  <string>toingg-jarvis</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
</dict>
</plist>
EOF

hdiutil create -volname "Toingg JARVIS" -srcfolder "${APP_DIR}" -ov -format UDZO \
  "dist/installers/toingg-jarvis-${VERSION}-macos.dmg"
echo "Built dist/installers/toingg-jarvis-${VERSION}-macos.dmg"
