"""Cross-platform native OS file manager command builder and execution handler.

Validates target filesystem paths and requested file manager actions before
dispatching platform-specific shell commands (Explorer on Windows, Finder on
macOS, and xdg-open on Linux) so invalid or unhashable JSON payloads fail
fast with a structured NativeFileActionError for HTTP 400 translation.
"""

import os
import platform
import subprocess
from pathlib import Path


SUPPORTED_ACTIONS = {"open_directory", "reveal_file", "open_file"}


class NativeFileActionError(ValueError):
    """Domain validation error raised when a file action request is malformed."""


def _target_path(raw_path):
    """Resolve and normalize user-supplied filesystem path string."""
    if not isinstance(raw_path, str):
        raise NativeFileActionError("path must be a non-empty string")
    if not raw_path.strip():
        raise NativeFileActionError("path must be a non-empty string")

    return Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()


def _validate_action_name(action):
    """Verify the requested action is a string matching a supported operation."""
    if not isinstance(action, str) or action not in SUPPORTED_ACTIONS:
        raise NativeFileActionError(
            f"action must be one of: {', '.join(sorted(SUPPORTED_ACTIONS))}"
        )


def _validate_directory_target(target):
    """Ensure target exists on disk and points to a directory."""
    if not target.exists() or not target.is_dir():
        raise NativeFileActionError("open_directory requires an existing directory")


def _validate_existing_target(action, target):
    """Ensure target exists on disk and satisfies file requirement for open_file."""
    if not target.exists():
        raise NativeFileActionError(f"{action} requires an existing path")

    if action == "open_file" and not target.is_file():
        raise NativeFileActionError("open_file requires an existing file")


def _validate_target(action, target):
    """Enforce action type/membership invariants and filesystem target existence."""
    _validate_action_name(action)

    if action == "open_directory":
        _validate_directory_target(target)
        return

    _validate_existing_target(action, target)


def _command_for_open_directory(target, current_system):
    """Construct OS-native command vector to open a directory window."""
    if current_system == "Windows":
        return ["explorer", str(target)]
    if current_system == "Darwin":
        return ["open", str(target)]
    return ["xdg-open", str(target)]


def _command_for_reveal_file(target, current_system):
    """Construct OS-native command vector to highlight a file in its parent folder."""
    if current_system == "Windows":
        return ["explorer", f"/select,{target}"]
    if current_system == "Darwin":
        return ["open", "-R", str(target)]
    parent_or_dir = target if target.is_dir() else target.parent
    return ["xdg-open", str(parent_or_dir)]


def _command_for_open_file(target, current_system):
    """Construct OS-native command vector to launch a file with its default handler."""
    if current_system == "Windows":
        return ["cmd", "/c", "start", "", str(target)]
    if current_system == "Darwin":
        return ["open", str(target)]
    return ["xdg-open", str(target)]


def build_file_manager_command(action, path, system=None):
    """Validate action and target path, returning the platform command vector."""
    target = _target_path(path)
    _validate_target(action, target)

    current_system = system or platform.system()

    if action == "open_directory":
        return _command_for_open_directory(target, current_system)

    if action == "reveal_file":
        return _command_for_reveal_file(target, current_system)

    return _command_for_open_file(target, current_system)


def plan_file_action(action, path, system=None):
    """Generate a validated execution plan dictionary for the requested file action."""
    command = build_file_manager_command(action, path, system=system)
    return {
        "action": action,
        "path": str(_target_path(path)),
        "command": command,
    }


def execute_file_action(action, path, dry_run=False, system=None):
    """Build the file action plan and spawn the native file manager unless dry_run is set."""
    plan = plan_file_action(action, path, system=system)

    if not dry_run:
        subprocess.Popen(
            plan["command"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return plan


def handle_file_action_payload(payload):
    """Validate incoming HTTP JSON payload dictionary and execute the file action."""
    if not isinstance(payload, dict):
        raise NativeFileActionError("payload must be a JSON object")

    action = payload.get("action")
    path = payload.get("path")
    dry_run = bool(payload.get("dry_run", False))
    return execute_file_action(action, path, dry_run=dry_run)
