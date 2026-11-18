# Packaging and native installers

Release builds produce one installer per platform. All packages install the
launcher code and create a per-user working copy, because the launcher writes
`config.json` next to its code. Python dependencies and Chromium are installed on
first launch.

| Platform | Artifact | Script |
| --- | --- | --- |
| Windows | `toingg-jarvis-<version>-setup.exe` (Inno Setup, per-user) | `packaging/windows/jarvis.iss` |
| Debian/Ubuntu | `toingg-jarvis_<version>_all.deb` | `packaging/linux/build_deb.sh` |
| macOS | `Toingg Jarvis.app` inside `toingg-jarvis-<version>.dmg` | `packaging/macos/build_app.sh` |

## Building locally

```bash
sh packaging/linux/build_deb.sh          # needs dpkg-deb
bash packaging/macos/build_app.sh        # needs macOS (hdiutil)
iscc packaging\windows\jarvis.iss        # needs Inno Setup
```

Output goes to `dist/`. The default version is read from `packaging/VERSION`.

## Releases

`.github/workflows/release.yml` builds all three packages. Pushing a tag such as
`v0.2.0` builds them with that version, uploads the artifacts and attaches them
to a GitHub release. It can also be run manually (`workflow_dispatch`) to build
artifacts without releasing.

## Signing

The macOS app is signed with `codesign` when the `MACOS_SIGN_IDENTITY` repository
secret is set (the certificate must be available on the runner). Otherwise
binaries are unsigned; Windows SmartScreen and macOS Gatekeeper may warn on first
run.
