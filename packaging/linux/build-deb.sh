#!/usr/bin/env bash
set -euo pipefail

VERSION="${JARVIS_VERSION:-0.1.0}"
ARCH="${JARVIS_ARCH:-amd64}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ -d "${ROOT_DIR}/dist/jarvis" ]]; then
  APP_SOURCE="${ROOT_DIR}/dist/jarvis"
else
  APP_SOURCE="${ROOT_DIR}/dist/JARVIS"
fi
BUILD_ROOT="${ROOT_DIR}/dist/deb/jarvis_${VERSION}_${ARCH}"
INSTALL_DIR="${BUILD_ROOT}/opt/jarvis"
BIN_DIR="${BUILD_ROOT}/usr/bin"
DESKTOP_DIR="${BUILD_ROOT}/usr/share/applications"
CONTROL_DIR="${BUILD_ROOT}/DEBIAN"
OUTPUT_DIR="${ROOT_DIR}/dist/installers"

if [[ ! -d "${APP_SOURCE}" ]]; then
  echo "Missing staged app at ${APP_SOURCE}" >&2
  exit 1
fi

rm -rf "${BUILD_ROOT}"
mkdir -p "${INSTALL_DIR}" "${BIN_DIR}" "${DESKTOP_DIR}" "${CONTROL_DIR}" "${OUTPUT_DIR}"
cp -R "${APP_SOURCE}/." "${INSTALL_DIR}/"

cat > "${BIN_DIR}/jarvis" <<'EOF'
#!/usr/bin/env bash
exec /opt/jarvis/jarvis_launcher "$@"
EOF
chmod 0755 "${BIN_DIR}/jarvis"

cat > "${DESKTOP_DIR}/jarvis.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=JARVIS
Comment=AI voice terminal powered by Toingg
Exec=jarvis
Terminal=false
Categories=Utility;AudioVideo;
EOF

cat > "${CONTROL_DIR}/control" <<EOF
Package: jarvis
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: PG-AGI <maintainers@example.com>
Description: JARVIS AI voice terminal powered by Toingg
 Native package for installing the JARVIS launcher and browser client.
EOF

dpkg-deb --build "${BUILD_ROOT}" "${OUTPUT_DIR}/jarvis_${VERSION}_${ARCH}.deb"
