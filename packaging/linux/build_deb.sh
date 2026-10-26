#!/usr/bin/env bash
# Linux .deb Package & AppDir Builder for J.A.R.V.I.S
set -euo pipefail

VERSION="2.0.0"
ARCH="amd64"
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
    --arch)
      ARCH="$2"
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

PKG_ROOT="${DIST_DIR}/deb-root/jarvis_${VERSION}_${ARCH}"
DEB_PATH="${DIST_DIR}/jarvis_${VERSION}_${ARCH}.deb"

echo "[Linux] Packaging JARVIS v${VERSION} (${ARCH})"
echo "[Linux] Output DEB : ${DEB_PATH}"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  echo "[Linux] Dry run complete."
  exit 0
fi

rm -rf "${PKG_ROOT}"
mkdir -p "${PKG_ROOT}/DEBIAN"
mkdir -p "${PKG_ROOT}/opt/jarvis"
mkdir -p "${PKG_ROOT}/usr/bin"
mkdir -p "${PKG_ROOT}/usr/share/applications"

if [[ -d "${DIST_DIR}/JARVIS" ]]; then
  cp -R "${DIST_DIR}/JARVIS/"* "${PKG_ROOT}/opt/jarvis/"
fi

cat > "${PKG_ROOT}/usr/bin/jarvis" <<'EOF'
#!/usr/bin/env bash
exec /opt/jarvis/JARVIS "$@"
EOF
chmod 0755 "${PKG_ROOT}/usr/bin/jarvis"

cat > "${PKG_ROOT}/usr/share/applications/jarvis.desktop" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=J.A.R.V.I.S Voice Terminal
Comment=AI Voice Terminal powered by Toingg
Exec=/usr/bin/jarvis
Terminal=true
Categories=Utility;AudioVideo;ArtificialIntelligence;
StartupNotify=false
EOF

cat > "${PKG_ROOT}/DEBIAN/control" <<EOF
Package: jarvis
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: libportaudio2
Maintainer: PG-AGI <admin@pgagi.in>
Homepage: https://github.com/PG-AGI/toingg-jarvis
Description: J.A.R.V.I.S AI Voice Terminal powered by Toingg
 Always-on desktop voice assistant with real-time WebSocket audio streaming,
 animated visual orb, and Playwright browser automation.
EOF

cat > "${PKG_ROOT}/DEBIAN/postinst" <<'EOF'
#!/usr/bin/env bash
set -e
chmod +x /opt/jarvis/JARVIS 2>/dev/null || true
chmod +x /usr/bin/jarvis 2>/dev/null || true
EOF
chmod 0755 "${PKG_ROOT}/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "${PKG_ROOT}" "${DEB_PATH}"
echo "[Linux] Created ${DEB_PATH}"
