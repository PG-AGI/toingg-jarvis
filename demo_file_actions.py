"""Print a safe native-file-action demo without opening local applications."""

import os
from pathlib import Path

import jarvis_launcher


def main():
    demo_file = Path(__file__).resolve()
    demo_dir = demo_file.parent

    cases = [
        ("Windows", "open_directory", demo_dir),
        ("Windows", "reveal_file", demo_file),
        ("Darwin", "reveal_file", demo_file),
        ("Linux", "open_file", demo_file),
    ]

    for platform_name, action, target in cases:
        command = jarvis_launcher._launch_native_path(
            action,
            os.fspath(target),
            platform_name,
        )
        print(f"{platform_name:7} {action:14} {command}")


if __name__ == "__main__":
    main()
