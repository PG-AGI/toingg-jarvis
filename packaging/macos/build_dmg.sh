#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <JARVIS.app> <version> <output-dir>" >&2
  exit 2
fi

app_path=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
version=${2#v}
output_dir=$(mkdir -p "$3" && cd "$3" && pwd)

if [[ ! -d "$app_path/Contents/MacOS" ]]; then
  echo "invalid app bundle: $app_path" >&2
  exit 1
fi
if [[ ! "$version" =~ ^[0-9][0-9A-Za-z.+-]*$ ]]; then
  echo "invalid release version: $version" >&2
  exit 1
fi

staging_dir=$(mktemp -d)
trap 'rm -rf -- "$staging_dir"' EXIT
cp -R "$app_path" "$staging_dir/JARVIS.app"
ln -s /Applications "$staging_dir/Applications"

artifact="$output_dir/JARVIS-${version}-macos.dmg"
hdiutil create \
  -volname "JARVIS ${version}" \
  -srcfolder "$staging_dir" \
  -ov \
  -format UDZO \
  "$artifact"
echo "$artifact"
