#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="${GITHUB_REF_NAME:-0.0.0}"
VERSION="${VERSION#v}"
PKG_ROOT="$ROOT_DIR/dist/linux/jarvis_${VERSION}_amd64"
APP_DIR="$PKG_ROOT/opt/jarvis"

rm -rf "$PKG_ROOT"
mkdir -p "$APP_DIR" "$PKG_ROOT/DEBIAN" "$PKG_ROOT/usr/bin" "$PKG_ROOT/usr/share/applications"

rsync -a \
  --exclude ".git" \
  --exclude ".github" \
  --exclude "dist" \
  --exclude "build" \
  --exclude "__pycache__" \
  --exclude ".pytest_cache" \
  --exclude ".browser-profile" \
  --exclude ".browser-profile-test" \
  "$ROOT_DIR/" "$APP_DIR/"

install -m 0755 "$ROOT_DIR/packaging/linux/jarvis" "$PKG_ROOT/usr/bin/jarvis"
install -m 0644 "$ROOT_DIR/packaging/linux/jarvis.desktop" "$PKG_ROOT/usr/share/applications/jarvis.desktop"

cat > "$PKG_ROOT/DEBIAN/control" <<CONTROL
Package: jarvis
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: PG-AGI <maintainers@example.com>
Depends: python3, python3-pip, python3-venv, portaudio19-dev
Description: J.A.R.V.I.S AI voice terminal launcher
 A desktop voice assistant launcher powered by Toingg with browser automation.
CONTROL

dpkg-deb --build "$PKG_ROOT"
