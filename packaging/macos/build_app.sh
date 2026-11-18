#!/bin/bash
# Build "Toingg Jarvis.app" and a .dmg. Usage: packaging/macos/build_app.sh [version] [outdir]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
VERSION="${1:-$(tr -d '[:space:]' < "$ROOT/packaging/VERSION")}"
OUT="${2:-$ROOT/dist}"
APP="$OUT/Toingg Jarvis.app"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/app"

cp "$ROOT"/jarvis_launcher.py "$ROOT"/native_file_manager.py \
   "$ROOT"/pipecat_gemini_tools.py "$ROOT"/browserClient.py \
   "$ROOT"/jarvis_visual.html "$ROOT"/jarvis_web.html \
   "$ROOT"/config.example.json "$ROOT"/packaging/requirements.txt \
   "$ROOT"/JARVIS.command "$APP/Contents/Resources/app/"
install -m 755 "$ROOT/packaging/macos/launcher.sh" "$APP/Contents/MacOS/toingg-jarvis"
sed "s/@VERSION@/$VERSION/g" "$ROOT/packaging/macos/Info.plist" > "$APP/Contents/Info.plist"

hdiutil create -volname "Toingg Jarvis" -srcfolder "$APP" -ov -format UDZO \
    "$OUT/toingg-jarvis-$VERSION.dmg"
echo "Built $OUT/toingg-jarvis-$VERSION.dmg"
