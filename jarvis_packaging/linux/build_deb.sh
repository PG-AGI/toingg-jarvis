#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-2.0.0}"
STAGE_DIR="build/deb/toingg-jarvis_${VERSION}_amd64"
mkdir -p "${STAGE_DIR}/DEBIAN" "${STAGE_DIR}/usr/bin" "${STAGE_DIR}/usr/share/applications" "dist/installers"

python3 -c "from pathlib import Path; from jarvis_packaging.build_installers import stage_debian_tree; stage_debian_tree(Path('${STAGE_DIR}'), Path('dist/toingg-jarvis'), '${VERSION}')"
dpkg-deb --build --root-owner-group "${STAGE_DIR}" "dist/installers/toingg-jarvis_${VERSION}_amd64.deb"
