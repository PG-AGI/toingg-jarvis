#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-dist/JARVIS}"
OUT_DIR="${2:-dist/packages}"
VERSION="${VERSION:-0.1.0}"
PKG_ROOT="${OUT_DIR}/jarvis_${VERSION}_amd64"

if [[ ! -x "${APP_DIR}/JARVIS" ]]; then
  echo "Expected executable at ${APP_DIR}/JARVIS" >&2
  exit 1
fi

rm -rf "${PKG_ROOT}"
mkdir -p "${PKG_ROOT}/DEBIAN" "${PKG_ROOT}/opt/jarvis" "${PKG_ROOT}/usr/bin"
cp -R "${APP_DIR}/." "${PKG_ROOT}/opt/jarvis/"
ln -s /opt/jarvis/JARVIS "${PKG_ROOT}/usr/bin/jarvis"

cat > "${PKG_ROOT}/DEBIAN/control" <<EOF2
Package: jarvis
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: PG-AGI <admin@pgagi.in>
Depends: google-chrome-stable | chromium-browser | chromium | microsoft-edge-stable
Description: J.A.R.V.I.S desktop voice assistant launcher
 A packaged build of the JARVIS local launcher, visual UI, and browser automation helper.
EOF2

dpkg-deb --build "${PKG_ROOT}"
echo "Created ${PKG_ROOT}.deb"
