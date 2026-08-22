#!/usr/bin/env bash
# Builds a Debian .deb package from the PyInstaller output in dist/JARVIS/.
set -euo pipefail

VERSION="${1:-0.2.0}"
PKGROOT="dist/jarvis-deb/jarvis_${VERSION}_amd64"
DEB="dist/jarvis_${VERSION}_amd64.deb"

mkdir -p "${PKGROOT}/opt/jarvis" "${PKGROOT}/usr/local/bin" "${PKGROOT}/DEBIAN"

cp -r dist/JARVIS/. "${PKGROOT}/opt/jarvis/"

ln -sf /opt/jarvis/JARVIS "${PKGROOT}/usr/local/bin/jarvis"

cat > "${PKGROOT}/DEBIAN/control" <<EOF
Package: jarvis
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Depends: libportaudio2, libasound2
Maintainer: PG-AGI <support@pg-agi.com>
Description: Toingg JARVIS voice launcher
 Wake-trigger voice assistant with browser slot-grid control.
EOF

cat > "${PKGROOT}/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
# Chromium is required by Playwright at runtime; users may run:
#   playwright install chromium
exit 0
EOF
chmod 755 "${PKGROOT}/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$(dirname "${PKGROOT}")"
echo "Built ${DEB}"
