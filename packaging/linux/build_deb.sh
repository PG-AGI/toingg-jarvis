#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <pyinstaller-dir> <version> <output-dir>" >&2
  exit 2
fi

source_dir=$(realpath "$1")
version=${2#v}
output_dir=$(realpath -m "$3")

if [[ ! -x "$source_dir/JARVIS" ]]; then
  echo "missing executable: $source_dir/JARVIS" >&2
  exit 1
fi
if [[ ! "$version" =~ ^[0-9][0-9A-Za-z.+:~-]*$ ]]; then
  echo "invalid Debian version: $version" >&2
  exit 1
fi

architecture=$(dpkg --print-architecture)
work_dir=$(mktemp -d)
trap 'rm -rf -- "$work_dir"' EXIT

package_root="$work_dir/jarvis"
install_dir="$package_root/opt/jarvis"
mkdir -p "$install_dir" "$package_root/usr/bin" \
  "$package_root/usr/share/applications" "$package_root/DEBIAN" "$output_dir"
cp -a "$source_dir/." "$install_dir/"

cat > "$package_root/usr/bin/jarvis" <<'EOF'
#!/usr/bin/env sh
exec /opt/jarvis/JARVIS "$@"
EOF
chmod 0755 "$package_root/usr/bin/jarvis"

cat > "$package_root/usr/share/applications/jarvis.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=JARVIS
Comment=Voice-enabled personal assistant
Exec=/opt/jarvis/JARVIS
Terminal=true
Categories=Utility;
EOF

cat > "$package_root/DEBIAN/control" <<EOF
Package: jarvis
Version: $version
Section: utils
Priority: optional
Architecture: $architecture
Maintainer: PG-AGI <noreply@github.com>
Depends: libportaudio2
Description: Cross-platform JARVIS voice assistant
 A standalone desktop package for the Toingg-powered JARVIS assistant.
EOF

artifact="$output_dir/JARVIS-${version}-linux-${architecture}.deb"
dpkg-deb --root-owner-group --build "$package_root" "$artifact"
dpkg-deb --info "$artifact" >/dev/null
echo "$artifact"
