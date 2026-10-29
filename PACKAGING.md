# Cross-Platform Packaging & Native Installers Guide (Fixes #13)

This guide explains how to build standalone executables and native OS packages for **Windows (`.exe`)**, **macOS (`.app` / `.dmg`)**, and **Linux (`AppImage` / `.desktop`)** using `cross_platform_packager.py`.

## Quick Start

```bash
pip install pyinstaller
python -c "from cross_platform_packager import handle_package_payload; handle_package_payload({'dry_run': False})"
```

## Supported Targets

| Platform | Output Bundle | Native Artifact | Data Separator |
| :--- | :--- | :--- | :--- |
| **Windows** | `dist/windows/JarvisAssistant.exe` | `JarvisAssistant-Setup-Windows.exe` | `;` |
| **macOS** | `dist/darwin/JarvisAssistant.app` | `JarvisAssistant-macOS.dmg` (`Info.plist` with mic permissions) | `:` |
| **Linux** | `dist/linux/JarvisAssistant` | `JarvisAssistant-Linux-x86_64.AppImage` + `.desktop` entry | `:` |

## Running Tests

```bash
python -m unittest test_cross_platform_packager.py -v
```
