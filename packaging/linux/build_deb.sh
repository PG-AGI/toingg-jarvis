#!/usr/bin/env bash
# Builds a .deb from the PyInstaller one-folder output at dist/JARVIS.
# Usage:  VERSION=1.0.0 bash packaging/linux/build_deb.sh
set -euo pipefail

VERSION="${VERSION:-0.0.0}"
ARCH="${ARCH:-amd64}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRC="${ROOT}/dist/JARVIS"
PKG="${ROOT}/dist/deb/jarvis_${VERSION}_${ARCH}"

if [[ ! -d "$SRC" ]]; then
    echo "Missing PyInstaller output at $SRC — run 'pyinstaller packaging/jarvis.spec' first." >&2
    exit 1
fi

rm -rf "$PKG"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/jarvis" "$PKG/usr/bin" "$PKG/usr/share/applications"

cp -a "$SRC/." "$PKG/opt/jarvis/"

cat > "$PKG/DEBIAN/control" <<EOF
Package: jarvis
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: libportaudio2, libasound2
Maintainer: PG-AGI <noreply@pg-agi.example>
Description: J.A.R.V.I.S voice-activated launcher
 Wake-word activated launcher that opens the JARVIS web UI in Chrome.
EOF

cat > "$PKG/usr/bin/jarvis" <<'EOF'
#!/usr/bin/env bash
exec /opt/jarvis/JARVIS "$@"
EOF
chmod 755 "$PKG/usr/bin/jarvis"

cat > "$PKG/usr/share/applications/jarvis.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=JARVIS
Comment=Voice-activated JARVIS launcher
Exec=/opt/jarvis/JARVIS
Icon=utilities-terminal
Terminal=true
Categories=Utility;
EOF

dpkg-deb --build --root-owner-group "$PKG"
echo "Built: ${PKG}.deb"
