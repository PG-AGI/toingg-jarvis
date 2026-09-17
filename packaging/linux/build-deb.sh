#!/usr/bin/env bash
set -euo pipefail

APP_NAME=toingg-jarvis
VERSION=1.0
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$ROOT/dist/$APP_NAME"
DEB="$ROOT/dist/deb"

rm -rf "$DEB"
mkdir -p "$DEB/DEBIAN" "$DEB/usr/share/$APP_NAME" "$DEB/usr/bin"

cp -r "$ROOT/jarvis_launcher.py" "$ROOT/JARVIS_README.md" "$DEB/usr/share/$APP_NAME/"

cat > "$DEB/DEBIAN/control" <<CTRL
Package: $APP_NAME
Version: $VERSION
Architecture: all
Maintainer: Toingg Jarvis
Description: Toingg Jarvis desktop assistant
CTRL

cat > "$DEB/usr/bin/$APP_NAME" <<'LAUNCH'
#!/usr/bin/env bash
exec python3 /usr/share/toingg-jarvis/jarvis_launcher.py "$@"
LAUNCH
chmod +x "$DEB/usr/bin/$APP_NAME"

dpkg-deb --build "$DEB" "$ROOT/dist/${APP_NAME}.deb"
