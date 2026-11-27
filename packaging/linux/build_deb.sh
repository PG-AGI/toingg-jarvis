#!/usr/bin/env bash
# Target path in repo: packaging/linux/build_deb.sh
set -euo pipefail

VERSION="${1:-2.0.0}"
ARCH="${2:-amd64}"
PKG_NAME="toingg-jarvis"
STAGE_DIR="build/deb/${PKG_NAME}_${VERSION}_${ARCH}"

rm -rf "${STAGE_DIR}"
mkdir -p "${STAGE_DIR}/DEBIAN" \
         "${STAGE_DIR}/opt/${PKG_NAME}" \
         "${STAGE_DIR}/usr/local/bin" \
         "${STAGE_DIR}/usr/share/applications"

cp -a dist/toingg-jarvis/* "${STAGE_DIR}/opt/${PKG_NAME}/"

cat > "${STAGE_DIR}/DEBIAN/control" <<EOF
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: PG-AGI <maintainers@pg-agi.dev>
Description: Toingg J.A.R.V.I.S AI Voice Terminal
 Cross-platform voice assistant launcher and local web interface.
EOF

cat > "${STAGE_DIR}/usr/local/bin/${PKG_NAME}" <<'EOF'
#!/usr/bin/env bash
exec /opt/toingg-jarvis/toingg-jarvis "$@"
EOF
chmod 0755 "${STAGE_DIR}/usr/local/bin/${PKG_NAME}"

cat > "${STAGE_DIR}/usr/share/applications/${PKG_NAME}.desktop" <<EOF
[Desktop Entry]
Name=Toingg J.A.R.V.I.S
Comment=AI Voice Terminal
Exec=/usr/local/bin/${PKG_NAME}
Terminal=true
Type=Application
Categories=Utility;Development;
EOF

mkdir -p dist/installers
dpkg-deb --build "${STAGE_DIR}" "dist/installers/${PKG_NAME}_${VERSION}_${ARCH}.deb"
echo "Built dist/installers/${PKG_NAME}_${VERSION}_${ARCH}.deb"
