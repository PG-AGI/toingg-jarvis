"""Cross-platform helpers for opening local files and directories.

The launcher uses these helpers to integrate with the operating system's
native file manager without depending on a GUI toolkit.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path
from typing import Literal

FileManagerAction = Literal["open", "reveal"]


class FileManagerError(ValueError):
    """Raised when a file-manager request cannot be handled safely."""


def _resolve_existing_path(path: str | os.PathLike[str]) -> Path:
    if path is None:
        raise FileManagerError("path is required")

    raw = str(path).strip()
    if not raw:
        raise FileManagerError("path is required")

    resolved = Path(raw).expanduser().resolve()
    if not resolved.exists():
        raise FileManagerError(f"path does not exist: {resolved}")
    return resolved


def build_file_manager_command(
    path: str | os.PathLike[str],
    action: FileManagerAction = "open",
    system: str | None = None,
) -> list[str]:
    """Return the native command for opening or revealing a local path.

    ``action='open'`` opens files with the default app and directories in the
    file manager. ``action='reveal'`` opens the containing folder and selects
    the file when the platform supports selection.
    """

    if action not in {"open", "reveal"}:
        raise FileManagerError("action must be 'open' or 'reveal'")

    resolved = _resolve_existing_path(path)
    system = system or platform.system()

    if system == "Windows":
        if action == "reveal" and resolved.is_file():
            return ["explorer", f"/select,{resolved}"]
        return ["explorer", str(resolved)]

    if system == "Darwin":
        if action == "reveal":
            return ["open", "-R", str(resolved)]
        return ["open", str(resolved)]

    if action == "reveal" and resolved.is_file():
        resolved = resolved.parent
    return ["xdg-open", str(resolved)]


def open_in_file_manager(
    path: str | os.PathLike[str],
    action: FileManagerAction = "open",
) -> subprocess.Popen:
    """Launch the native file manager/default app for ``path``."""

    command = build_file_manager_command(path, action=action)
    return subprocess.Popen(command)
