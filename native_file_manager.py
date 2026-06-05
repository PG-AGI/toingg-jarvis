import os
import platform
import subprocess
from pathlib import Path


SUPPORTED_ACTIONS = {"open_directory", "reveal_file", "open_file"}


class NativeFileActionError(ValueError):
    pass


def _target_path(raw_path):
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise NativeFileActionError("path must be a non-empty string")

    return Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()


def _validate_target(action, target):
    if action not in SUPPORTED_ACTIONS:
        raise NativeFileActionError(
            f"action must be one of: {', '.join(sorted(SUPPORTED_ACTIONS))}"
        )

    if action == "open_directory":
        if not target.exists() or not target.is_dir():
            raise NativeFileActionError("open_directory requires an existing directory")
        return

    if not target.exists():
        raise NativeFileActionError(f"{action} requires an existing path")

    if action == "open_file" and not target.is_file():
        raise NativeFileActionError("open_file requires an existing file")


def build_file_manager_command(action, path, system=None):
    target = _target_path(path)
    _validate_target(action, target)

    current_system = system or platform.system()

    if action == "open_directory":
        if current_system == "Windows":
            return ["explorer", str(target)]
        if current_system == "Darwin":
            return ["open", str(target)]
        return ["xdg-open", str(target)]

    if action == "reveal_file":
        if current_system == "Windows":
            return ["explorer", f"/select,{target}"]
        if current_system == "Darwin":
            return ["open", "-R", str(target)]
        return ["xdg-open", str(target if target.is_dir() else target.parent)]

    if current_system == "Windows":
        return ["cmd", "/c", "start", "", str(target)]
    if current_system == "Darwin":
        return ["open", str(target)]
    return ["xdg-open", str(target)]


def plan_file_action(action, path, system=None):
    command = build_file_manager_command(action, path, system=system)
    return {
        "action": action,
        "path": str(_target_path(path)),
        "command": command,
    }


def execute_file_action(action, path, dry_run=False, system=None):
    plan = plan_file_action(action, path, system=system)

    if not dry_run:
        subprocess.Popen(
            plan["command"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return plan


def handle_file_action_payload(payload):
    if not isinstance(payload, dict):
        raise NativeFileActionError("payload must be a JSON object")

    action = payload.get("action")
    path = payload.get("path")
    dry_run = bool(payload.get("dry_run", False))
    return execute_file_action(action, path, dry_run=dry_run)
