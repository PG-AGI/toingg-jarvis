# Native JARVIS installers

Issue #13 adds an **unsigned** Windows .exe installer, a Debian .deb,
and a macOS .app inside a drag-to-Applications .dmg. Each is built
from the real source on its target OS by the Native installers GitHub
Actions workflow. **No API token or provider account is needed to build.**

## Build and test

Use Python 3.11, and native PortAudio headers (portaudio19-dev and
libasound2-dev on Ubuntu; brew install portaudio on macOS). Windows
uses the prebuilt PyAudio wheel.

    python -m unittest discover -p 'test_*.py' -v
    python -m pip install -r packaging/requirements-build.txt
    python -m PyInstaller --noconfirm --clean jarvis.spec

The bundled executable is dist/JARVIS/JARVIS on Linux,
dist/JARVIS/JARVIS.exe on Windows, or
dist/JARVIS.app/Contents/MacOS/JARVIS on macOS.

Smoke it with --version, --help and --browser-client --help,
all without Toingg credentials. These tests exercise real frozen
module loading and cannot be satisfied by merely scanning files.

On Linux, run:

    python packaging/linux/build_deb.py
    dpkg-deb --contents dist/installers/*.deb

It installs files under /opt/jarvis/ and a shell entry point at
/usr/bin/jarvis. Installation needs the usual administrator privileges.

On macOS, run:

    bash packaging/macos/build_dmg.sh

The resulting DMG contains JARVIS.app and an Applications shortcut.

On Windows, install Inno Setup 6 then invoke:

    ISCC.exe packaging\windows\JARVIS.iss

The resulting installer uses the current user's local app directory
and does not request administrator permissions.

## Automated builds and versioned releases

Pull requests run the source tests and the three-platform build matrix.
Every job uploads its installer as a GitHub Actions artifact.
When a maintainer pushes a version tag such as v2.0.0, the same
workflow publishes the installers on a versioned GitHub Release.
A contributor PR alone never creates or publishes a release.

## Configuration and runtime resources

Running from the Python source checkout preserves the original
config.json location at the repository root.

Native packages store API credentials and the persistent browser profile
in a writable user-specific location, not inside a code-signed or read-only
package resource directory:

| Platform | User configuration path |
| --- | --- |
| Windows | %APPDATA%\JARVIS\config.json |
| macOS | ~/Library/Application Support/JARVIS/config.json |
| Linux | XDG_CONFIG_HOME/jarvis/config.json (or ~/.config/jarvis/config.json) |

Unix token files are created with owner-only mode 0600. Never package a
real config.json or user's browser profile. jarvis_web.html,
jarvis_visual.html and config.example.json are immutable bundled assets.

The browser automation child process starts through the same bundled
executable using --browser-client, not the system Python.
On a first installation, use JARVIS --install-browser to fetch
Playwright's Chromium into the user's local browser cache.
This does not require a provider account; live Toingg voice service use
still requires a valid Toingg API token.

**Limitations:** These artifacts are not Developer ID signed/notarized
or Windows Authenticode signed. OS security prompts are expected.
Build and smoke checks do not prove microphone access, full browser
automation, live provider authentication or end-user GUI onboarding.
Those require an actual interactive test on each platform.
