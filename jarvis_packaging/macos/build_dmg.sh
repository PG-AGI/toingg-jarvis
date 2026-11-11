#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.0.0}"
mkdir -p "dist/installers"
hdiutil create -volname "ToinggJarvis" -srcfolder "dist/ToinggJarvis.app" -ov -format UDZO "dist/installers/ToinggJarvis-${VERSION}-macos.dmg"
