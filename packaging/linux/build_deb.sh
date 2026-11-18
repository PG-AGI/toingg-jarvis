#!/bin/sh
# Build a .deb package. Usage: packaging/linux/build_deb.sh [version] [outdir]
set -eu

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:-$(tr -d '[:space:]' < "$ROOT/packaging/VERSION")}"
OUT="${2:-$ROOT/dist}"
PKG="toingg-jarvis"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

SHARE="$STAGE/usr/share/$PKG"
mkdir -p "$SHARE" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/DEBIAN" "$OUT"

cp "$ROOT"/jarvis_launcher.py "$ROOT"/native_file_manager.py \
   "$ROOT"/pipecat_gemini_tools.py "$ROOT"/browserClient.py \
   "$ROOT"/jarvis_visual.html "$ROOT"/jarvis_web.html \
   "$ROOT"/config.example.json "$ROOT"/packaging/requirements.txt "$SHARE/"
install -m 755 "$ROOT/packaging/linux/toingg-jarvis" "$STAGE/usr/bin/$PKG"
install -m 644 "$ROOT/packaging/linux/toingg-jarvis.desktop" \
    "$STAGE/usr/share/applications/$PKG.desktop"

sed "s/@VERSION@/$VERSION/" "$ROOT/packaging/linux/control" > "$STAGE/DEBIAN/control"

dpkg-deb --build --root-owner-group "$STAGE" "$OUT/${PKG}_${VERSION}_all.deb"
echo "Built $OUT/${PKG}_${VERSION}_all.deb"
