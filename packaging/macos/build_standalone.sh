#!/usr/bin/env bash
set -euo pipefail

# PyInstaller attempts to re-sign every Mach-O file it collects. Chromium is a
# nested signed app, so copying it after freezing preserves its valid layout.
browser_dir=$(python - <<'PY'
from pathlib import Path
import playwright

print(Path(playwright.__file__).parent / "driver" / "package" / ".local-browsers")
PY
)

if [[ ! -d "$browser_dir" ]]; then
  echo "Playwright browsers not found: $browser_dir" >&2
  exit 1
fi

temporary_dir=$(mktemp -d)
browser_backup="$temporary_dir/.local-browsers"

restore_browser_cache() {
  if [[ -d "$browser_backup" && ! -e "$browser_dir" ]]; then
    mkdir -p "$(dirname "$browser_dir")"
    mv "$browser_backup" "$browser_dir"
  fi
  rm -rf -- "$temporary_dir"
}
trap restore_browser_cache EXIT

mv "$browser_dir" "$browser_backup"
pyinstaller jarvis.spec --clean --noconfirm

packaged_browser_dir="dist/JARVIS/_internal/playwright/driver/package/.local-browsers"
mkdir -p "$(dirname "$packaged_browser_dir")"
cp -R "$browser_backup" "$packaged_browser_dir"
