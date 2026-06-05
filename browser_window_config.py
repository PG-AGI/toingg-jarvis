import json
import os
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class BrowserWindowConfig:
    preferred_monitor: str = "active"
    window_size: tuple[int, int] | None = None
    position: str | tuple[int, int] | None = None


def parse_window_size(value):
    if value is None or value == "":
        return None
    if isinstance(value, dict):
        width = value.get("width")
        height = value.get("height")
    elif isinstance(value, (list, tuple)) and len(value) == 2:
        width, height = value
    else:
        match = re.fullmatch(r"\s*(\d+)\s*[xX,]\s*(\d+)\s*", str(value))
        if not match:
            raise ValueError(f"Invalid browser window size: {value!r}")
        width, height = match.groups()

    width, height = int(width), int(height)
    if width <= 0 or height <= 0:
        raise ValueError("Browser window width and height must be positive")
    return width, height


def parse_window_position(value):
    if value is None or value == "":
        return None
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return int(value[0]), int(value[1])

    text = str(value).strip().lower()
    if text in {"center", "top-left", "top-right"}:
        return text

    match = re.fullmatch(r"x\s*=\s*(-?\d+)\s*,\s*y\s*=\s*(-?\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))

    raise ValueError(f"Invalid browser window position: {value!r}")


def parse_browser_window_config(config_data=None, environ=None, cli_values=None, config_path=None):
    environ = environ if environ is not None else os.environ
    cli_values = cli_values or {}
    config_data = config_data if config_data is not None else _load_config_file(config_path)
    browser_data = config_data.get("browser", {}) if isinstance(config_data, dict) else {}

    preferred_monitor = _first_non_empty(
        cli_values.get("preferred_monitor") or cli_values.get("monitor"),
        environ.get("JARVIS_BROWSER_MONITOR"),
        browser_data.get("preferred_monitor") or browser_data.get("monitor"),
        "active",
    )
    window_size = _first_non_empty(
        cli_values.get("window_size"),
        environ.get("JARVIS_BROWSER_WINDOW_SIZE"),
        browser_data.get("window_size"),
    )
    position = _first_non_empty(
        cli_values.get("position"),
        environ.get("JARVIS_BROWSER_POSITION"),
        browser_data.get("position"),
    )

    return BrowserWindowConfig(
        preferred_monitor=str(preferred_monitor).strip().lower(),
        window_size=parse_window_size(window_size),
        position=parse_window_position(position),
    )


def resolve_window_geometry(config, default_size, default_position, screen_bounds):
    width, height = config.window_size or default_size
    default_x, default_y = default_position

    if isinstance(config.position, tuple):
        x, y = config.position
    elif config.position == "center":
        sx, sy, sw, sh = screen_bounds
        x = sx + max(0, (sw - width) // 2)
        y = sy + max(0, (sh - height) // 2)
    elif config.position == "top-left":
        sx, sy, _, _ = screen_bounds
        x, y = sx, sy
    elif config.position == "top-right":
        sx, sy, sw, _ = screen_bounds
        x = sx + max(0, sw - width)
        y = sy
    else:
        x, y = default_x, default_y

    return int(width), int(height), int(x), int(y)


def choose_screen_bounds(preferred_monitor, screens, active_screen, fallback_screen):
    monitor = str(preferred_monitor or "active").strip().lower()
    screens = list(screens or [])

    if monitor == "active":
        return active_screen or (screens[0] if screens else fallback_screen)
    if monitor == "primary":
        return screens[0] if screens else active_screen or fallback_screen

    match = re.fullmatch(r"monitor-(\d+)", monitor)
    if match:
        index = int(match.group(1)) - 1
        if 0 <= index < len(screens):
            return screens[index]

    return active_screen or (screens[0] if screens else fallback_screen)


def chrome_window_args(width, height, x, y):
    return [f"--window-size={int(width)},{int(height)}", f"--window-position={int(x)},{int(y)}"]


def _first_non_empty(*values):
    for value in values:
        if value is not None and value != "":
            return value
    return None


def _load_config_file(config_path):
    path = config_path or os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    try:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except FileNotFoundError:
        return {}
