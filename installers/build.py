"""
Build native installers for Toingg JARVIS.

Freezes jarvis_launcher.py with PyInstaller, then packages the result for the
OS it runs on:

    Windows  dist/toingg-jarvis-<ver>-windows-x64-setup.exe   (Inno Setup)
    Linux    dist/toingg-jarvis_<ver>_<arch>.deb               (dpkg-deb)
    macOS    dist/toingg-jarvis-<ver>-macos-<arch>.dmg         (.app inside)

Usage:
    pip install -r installers/requirements.txt
    python installers/build.py [--version 2.1.0] [--out dist]

Signing (optional, used when set):
    Windows  SIGNTOOL, WINDOWS_CERT_PATH, WINDOWS_CERT_PASSWORD
    macOS    MACOS_SIGN_IDENTITY (otherwise the app is ad-hoc signed)
"""

import argparse
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALLERS = os.path.join(ROOT, "installers")
BUILD = os.path.join(ROOT, "build")

APP_NAME = "Toingg JARVIS"
PACKAGE = "toingg-jarvis"
BUNDLE_ID = "com.toingg.jarvis"
HOMEPAGE = "https://github.com/PG-AGI/toingg-jarvis"
MAINTAINER = "PG-AGI <https://github.com/PG-AGI>"
DATA_FILES = ["jarvis_web.html", "jarvis_visual.html", "config.example.json", "LICENSE"]

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


# ── versions and names ───────────────────────────────────────────────────────
def default_version():
    """The version jarvis_launcher.py reports when run from source."""
    with open(os.path.join(ROOT, "jarvis_launcher.py"), "r", encoding="utf-8") as f:
        match = re.search(r'def _app_version\(res_dir, default="([^"]+)"\)', f.read())
    if not match:
        raise RuntimeError("could not find the default version in jarvis_launcher.py")
    return match.group(1)


def normalize_version(value):
    """Turn a tag such as 'v2.1.0' or 'refs/tags/v2.1.0-rc1' into '2.1.0'/'2.1.0-rc1'."""
    version = value.strip().rsplit("/", 1)[-1]
    if version[:1] in ("v", "V"):
        version = version[1:]
    if not _VERSION_RE.match(version):
        raise ValueError(f"not a release version (expected X.Y.Z): {value!r}")
    return version


def deb_version(version):
    """Debian sorts '~' before anything, so 2.1.0~rc1 comes before 2.1.0."""
    return version.replace("-", "~", 1)


def target_for(system=None):
    system = system or platform.system()
    return {"Windows": "windows", "Linux": "linux", "Darwin": "macos"}.get(system)


def deb_arch(machine=None):
    machine = (machine or platform.machine()).lower()
    return {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)


def mac_arch(machine=None):
    machine = (machine or platform.machine()).lower()
    return {"x86_64": "x64", "amd64": "x64", "arm64": "arm64", "aarch64": "arm64"}.get(machine, machine)


def artifact_name(target, version, machine=None):
    if target == "windows":
        return f"{PACKAGE}-{version}-windows-x64-setup.exe"
    if target == "linux":
        return f"{PACKAGE}_{deb_version(version)}_{deb_arch(machine)}.deb"
    if target == "macos":
        return f"{PACKAGE}-{version}-macos-{mac_arch(machine)}.dmg"
    raise ValueError(f"unknown target: {target}")


# ── PyInstaller ──────────────────────────────────────────────────────────────
def pyinstaller_args(version_file, sep=os.pathsep, identity=None):
    """One-folder console build: the launcher asks for the API key in its terminal."""
    args = [
        os.path.join(ROOT, "jarvis_launcher.py"),
        "--name", PACKAGE,
        "--onedir",
        "--console",
        "--noconfirm",
        "--clean",
        "--distpath", os.path.join(BUILD, "pyinstaller", "dist"),
        "--workpath", os.path.join(BUILD, "pyinstaller", "work"),
        "--specpath", os.path.join(BUILD, "pyinstaller"),
        "--paths", ROOT,
        # Imported lazily, when the launcher re-runs itself with --browser-client.
        "--hidden-import", "browserClient",
        "--collect-all", "playwright_stealth",
        "--collect-data", "speech_recognition",
        "--add-data", f"{version_file}{sep}.",
    ]
    if identity:
        args += ["--codesign-identity", identity]
    for name in DATA_FILES:
        args += ["--add-data", f"{os.path.join(ROOT, name)}{sep}."]
    return args


def freeze(version):
    os.makedirs(BUILD, exist_ok=True)
    version_file = os.path.join(BUILD, "VERSION")
    with open(version_file, "w", encoding="utf-8") as f:
        f.write(version + "\n")
    import PyInstaller.__main__
    identity = os.environ.get("MACOS_SIGN_IDENTITY") if target_for() == "macos" else None
    PyInstaller.__main__.run(pyinstaller_args(version_file, identity=identity))
    return os.path.join(BUILD, "pyinstaller", "dist", PACKAGE)


def run(cmd, **kwargs):
    print("  $", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run(cmd, check=True, **kwargs)


# ── Windows ──────────────────────────────────────────────────────────────────
def sign_windows(path):
    signtool = os.environ.get("SIGNTOOL")
    cert = os.environ.get("WINDOWS_CERT_PATH")
    if not (signtool and cert):
        print(f"  [sign] skipped (no certificate): {os.path.basename(path)}")
        return
    run([signtool, "sign", "/fd", "sha256", "/f", cert, "/p", os.environ.get("WINDOWS_CERT_PASSWORD", ""),
         "/tr", "http://timestamp.digicert.com", "/td", "sha256", path])


def find_iscc():
    found = shutil.which("ISCC") or shutil.which("iscc")
    if found:
        return found
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidate = os.path.join(base, "Inno Setup 6", "ISCC.exe")
            if os.path.exists(candidate):
                return candidate
    raise RuntimeError("Inno Setup (ISCC.exe) not found; install it from https://jrsoftware.org/isinfo.php")


def package_windows(frozen_dir, version, out_dir):
    sign_windows(os.path.join(frozen_dir, f"{PACKAGE}.exe"))
    name = artifact_name("windows", version)
    run([find_iscc(),
         f"/DAppVersion={version}",
         f"/DAppSourceDir={frozen_dir}",
         f"/DOutputDir={out_dir}",
         f"/DOutputBaseFilename={name[:-len('.exe')]}",
         os.path.join(INSTALLERS, "windows", "jarvis.iss")])
    path = os.path.join(out_dir, name)
    sign_windows(path)
    return path


# ── Linux (.deb) ─────────────────────────────────────────────────────────────
def deb_control(version, arch, installed_size_kb):
    return (
        f"Package: {PACKAGE}\n"
        f"Version: {deb_version(version)}\n"
        f"Architecture: {arch}\n"
        f"Maintainer: {MAINTAINER}\n"
        f"Installed-Size: {installed_size_kb}\n"
        "Depends: libportaudio2, libc6\n"
        "Recommends: chromium | google-chrome-stable | microsoft-edge-stable\n"
        "Section: utils\n"
        "Priority: optional\n"
        f"Homepage: {HOMEPAGE}\n"
        "Description: AI voice terminal powered by Toingg\n"
        " J.A.R.V.I.S listens for a wake word, opens the Toingg web terminal and\n"
        " lets you control apps and the browser by voice.\n"
    )


def _dir_size_kb(path):
    total = 0
    for dirpath, _, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(dirpath, name))
    return max(1, total // 1024)


def package_linux(frozen_dir, version, out_dir):
    root = os.path.join(BUILD, "deb")
    shutil.rmtree(root, ignore_errors=True)
    app_dir = os.path.join(root, "opt", PACKAGE)
    shutil.copytree(frozen_dir, app_dir)

    bin_dir = os.path.join(root, "usr", "bin")
    os.makedirs(bin_dir)
    wrapper = os.path.join(bin_dir, PACKAGE)
    with open(wrapper, "w", encoding="utf-8") as f:
        f.write(f'#!/bin/sh\nexec /opt/{PACKAGE}/{PACKAGE} "$@"\n')
    os.chmod(wrapper, 0o755)

    apps_dir = os.path.join(root, "usr", "share", "applications")
    os.makedirs(apps_dir)
    shutil.copy(os.path.join(INSTALLERS, "linux", f"{PACKAGE}.desktop"), apps_dir)

    doc_dir = os.path.join(root, "usr", "share", "doc", PACKAGE)
    os.makedirs(doc_dir)
    shutil.copy(os.path.join(ROOT, "LICENSE"), os.path.join(doc_dir, "copyright"))

    debian = os.path.join(root, "DEBIAN")
    os.makedirs(debian)
    with open(os.path.join(debian, "control"), "w", encoding="utf-8") as f:
        f.write(deb_control(version, deb_arch(), _dir_size_kb(root)))

    path = os.path.join(out_dir, artifact_name("linux", version))
    run(["dpkg-deb", "--root-owner-group", "--build", root, path])
    return path


# ── macOS (.app + .dmg) ──────────────────────────────────────────────────────
def info_plist(version):
    return {
        "CFBundleName": APP_NAME,
        "CFBundleDisplayName": APP_NAME,
        "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": PACKAGE,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": version.split("-", 1)[0].split("+", 1)[0],
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "JARVIS listens for the wake word and your voice commands.",
        "NSAppleEventsUsageDescription": "JARVIS opens its console in Terminal and controls apps you ask for.",
    }


# The launcher is a console app, so the bundle opens it in a Terminal window.
_MAC_LAUNCHER = f"""#!/bin/sh
DIR="$(cd "$(dirname "$0")/../Resources/{PACKAGE}" && pwd)"
exec open -a Terminal "$DIR/{PACKAGE}"
"""


def sign_macos(path):
    identity = os.environ.get("MACOS_SIGN_IDENTITY") or "-"
    cmd = ["codesign", "--force", "--deep", "--sign", identity]
    if identity != "-":
        cmd += ["--options", "runtime", "--timestamp"]
    run(cmd + [path])


def package_macos(frozen_dir, version, out_dir):
    stage = os.path.join(BUILD, "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    app = os.path.join(stage, f"{APP_NAME}.app")
    contents = os.path.join(app, "Contents")
    shutil.copytree(frozen_dir, os.path.join(contents, "Resources", PACKAGE), symlinks=True)

    os.makedirs(os.path.join(contents, "MacOS"))
    launcher = os.path.join(contents, "MacOS", PACKAGE)
    with open(launcher, "w", encoding="utf-8") as f:
        f.write(_MAC_LAUNCHER)
    os.chmod(launcher, 0o755)
    with open(os.path.join(contents, "Info.plist"), "wb") as f:
        plistlib.dump(info_plist(version), f)

    sign_macos(app)
    os.symlink("/Applications", os.path.join(stage, "Applications"))

    path = os.path.join(out_dir, artifact_name("macos", version))
    if os.path.exists(path):
        os.remove(path)
    run(["hdiutil", "create", "-volname", APP_NAME, "-srcfolder", stage, "-ov", "-format", "UDZO", path])
    return path


PACKAGERS = {"windows": package_windows, "linux": package_linux, "macos": package_macos}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the Toingg JARVIS installer for this OS")
    parser.add_argument("--version", help="release version or tag, e.g. v2.1.0 (default: the launcher's)")
    parser.add_argument("--out", default=os.path.join(ROOT, "dist"), help="output directory (default: dist)")
    args = parser.parse_args(argv)

    target = target_for()
    if target is None:
        parser.error(f"unsupported OS: {platform.system()}")
    version = normalize_version(args.version) if args.version else default_version()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    print(f"  Building {APP_NAME} {version} for {target}", flush=True)
    frozen_dir = freeze(version)
    path = PACKAGERS[target](frozen_dir, version, out_dir)
    print(f"  ✅  {path}")


if __name__ == "__main__":
    sys.exit(main())
