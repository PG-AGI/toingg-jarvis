"""Unit tests for cross-platform packaging and native installer generation (#13)."""

from pathlib import Path
import tempfile

from jarvis_packaging.build_installers import (
    APP_SLUG,
    APP_VERSION,
    generate_debian_control,
    generate_linux_desktop_entry,
    generate_macos_info_plist,
    generate_windows_inno_setup_script,
    get_pyinstaller_args,
    stage_debian_tree,
)


def test_pyinstaller_args_use_platform_specific_data_separators() -> None:
    win_args = get_pyinstaller_args("Windows")
    assert "--windowed" in win_args
    assert "jarvis_web.html;." in win_args

    linux_args = get_pyinstaller_args("Linux")
    assert "jarvis_web.html:." in linux_args


def test_windows_inno_setup_and_macos_plist_manifests() -> None:
    iss = generate_windows_inno_setup_script("2.1.0")
    assert "OutputBaseFilename=toingg-jarvis-setup-2.1.0-win64" in iss
    assert "jarvis_web.html" in iss

    plist = generate_macos_info_plist("2.1.0")
    assert "<string>com.pgagi.toingg-jarvis</string>" in plist
    assert "NSMicrophoneUsageDescription" in plist


def test_stage_debian_tree_creates_control_and_desktop_files() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        staged = stage_debian_tree(Path(tmp), version=APP_VERSION)
        assert staged["control"].is_file()
        assert f"Package: {APP_SLUG}" in staged["control"].read_text(encoding="utf-8")
        assert staged["desktop"].is_file()
        assert "Exec=/usr/bin/toingg-jarvis" in staged["desktop"].read_text(encoding="utf-8")
        assert staged["binary"].is_file()
