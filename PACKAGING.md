# Packaging scaffold

This patch adds a minimal packaging CI workflow and instructions to produce
platform builds (PyInstaller-based) for Windows/macOS/Linux. It's intentionally
small: CI uploads a placeholder artifact per-platform to demonstrate the pipeline.

Steps a maintainer can follow to produce real artifacts:

1. Add PyInstaller spec files for the launcher.
2. Add OS-specific installer helpers (Inno/NSIS for Windows, .deb for Debian, .dmg for macOS).
3. Configure secrets for code signing if desired.

