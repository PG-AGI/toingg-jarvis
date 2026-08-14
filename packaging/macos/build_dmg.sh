#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <pyinstaller-dir> <version> <output-dir>" >&2
  exit 2
fi

source_dir=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
version=${2#v}
output_dir=$(mkdir -p "$3" && cd "$3" && pwd)

if [[ ! -x "$source_dir/JARVIS" ]]; then
  echo "missing executable: $source_dir/JARVIS" >&2
  exit 1
fi
if [[ ! "$version" =~ ^[0-9][0-9A-Za-z.+-]*$ ]]; then
  echo "invalid release version: $version" >&2
  exit 1
fi

staging_dir=$(mktemp -d)
trap 'rm -rf -- "$staging_dir"' EXIT
app_path="$staging_dir/JARVIS.app"
mkdir -p "$app_path/Contents/MacOS" "$app_path/Contents/Resources"
cp -R "$source_dir" "$app_path/Contents/Resources/JARVIS"

cat > "$app_path/Contents/MacOS/JARVIS" <<'EOF'
#!/usr/bin/env sh
contents_dir=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
exec "$contents_dir/Resources/JARVIS/JARVIS" "$@"
EOF
chmod 0755 "$app_path/Contents/MacOS/JARVIS"

cat > "$app_path/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDisplayName</key><string>JARVIS</string>
  <key>CFBundleExecutable</key><string>JARVIS</string>
  <key>CFBundleIdentifier</key><string>com.pgagi.jarvis</string>
  <key>CFBundleName</key><string>JARVIS</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>$version</string>
  <key>NSMicrophoneUsageDescription</key><string>JARVIS uses the microphone for voice commands.</string>
</dict>
</plist>
EOF

JARVIS_CONFIG_DIR="$staging_dir/smoke-config" \
  "$app_path/Contents/MacOS/JARVIS" --packaging-smoke-test
rm -rf -- "$staging_dir/smoke-config"

ditto -c -k --sequesterRsrc --keepParent \
  "$app_path" "$output_dir/JARVIS-${version}-macos-app.zip"
ln -s /Applications "$staging_dir/Applications"

artifact="$output_dir/JARVIS-${version}-macos.dmg"
hdiutil create \
  -volname "JARVIS ${version}" \
  -srcfolder "$staging_dir" \
  -ov \
  -format UDZO \
  "$artifact"
echo "$artifact"
