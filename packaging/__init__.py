"""Cross-platform packaging and native installer generation utilities for JARVIS."""

from .installer_builder import (
    PackageMetadata,
    build_deb_package,
    build_platform_artifacts,
    render_windows_inno_script,
    render_windows_nsis_script,
    resolve_bundle_root,
    resolve_runtime_asset,
    resolve_user_config_dir,
    stage_linux_deb_tree,
    stage_macos_app_bundle,
)


def default_package_metadata() -> PackageMetadata:
    """Return the default release metadata configuration for native installer builds."""
    return PackageMetadata()


__all__ = [
    "PackageMetadata",
    "build_deb_package",
    "build_platform_artifacts",
    "default_package_metadata",
    "render_windows_inno_script",
    "render_windows_nsis_script",
    "resolve_bundle_root",
    "resolve_runtime_asset",
    "resolve_user_config_dir",
    "stage_linux_deb_tree",
    "stage_macos_app_bundle",
]
