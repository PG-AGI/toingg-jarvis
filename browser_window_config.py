"""Browser window placement, monitor selection, and sizing configuration."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
import re
import subprocess
from typing import Any


MIN_WINDOW_WIDTH = 200
MIN_WINDOW_HEIGHT = 150
MAX_WINDOW_WIDTH = 15360
MAX_WINDOW_HEIGHT = 8640

DEFAULT_TAB_WIDTH = 860
DEFAULT_TAB_HEIGHT = 580
DEFAULT_CLIENT_WIDTH = 1366
DEFAULT_CLIENT_HEIGHT = 768

VALID_POSITION_PRESETS = {
    "grid",
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
}

_SIZE_PATTERN = re.compile(r"^\s*(\d+)\s*[xX,\s]\s*(\d+)\s*$")
_COORD_KV_PATTERN = re.compile(
    r"^\s*x\s*=\s*(-?\d+)\s*[,;\s]\s*y\s*=\s*(-?\d+)\s*$",
    re.IGNORECASE,
)
_COORD_PAIR_PATTERN = re.compile(r"^\s*(-?\d+)\s*,\s*(-?\d+)\s*$")
_MONITOR_INDEX_PATTERN = re.compile(r"^(?:monitor|screen|display)[-_]?(\d+)$", re.IGNORECASE)


class BrowserWindowConfigError(ValueError):
    """Raised when browser window configuration values are invalid."""


@dataclass(frozen=True)
class MonitorBounds:
    x: int
    y: int
    width: int
    height: int
    name: str = "monitor-1"
    is_primary: bool = False

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width, self.height)


@dataclass(frozen=True)
class WindowSize:
    width: int = DEFAULT_TAB_WIDTH
    height: int = DEFAULT_TAB_HEIGHT

    def to_dict(self) -> dict[str, int]:
        return {"width": self.width, "height": self.height}

    def to_chrome_arg(self) -> str:
        return f"--window-size={self.width},{self.height}"


@dataclass(frozen=True)
class WindowPosition:
    mode: str = "grid"
    x: int | None = None
    y: int | None = None

    def to_dict(self) -> dict[str, Any]:
        if self.mode == "coordinates":
            return {"mode": self.mode, "x": self.x, "y": self.y}
        return {"mode": self.mode}


@dataclass(frozen=True)
class BrowserWindowConfig:
    preferred_monitor: str = "active"
    window_size: WindowSize = WindowSize(DEFAULT_TAB_WIDTH, DEFAULT_TAB_HEIGHT)
    position: WindowPosition = WindowPosition("grid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferred_monitor": self.preferred_monitor,
            "window_size": self.window_size.to_dict(),
            "position": (
                f"x={self.position.x},y={self.position.y}"
                if self.position.mode == "coordinates"
                else self.position.mode
            ),
        }


def parse_preferred_monitor(raw: Any, default: str = "active") -> str:
    if raw is None or raw == "":
        return default
    if isinstance(raw, bool):
        raise BrowserWindowConfigError("preferred_monitor must be a monitor name or index")
    if isinstance(raw, int):
        if raw < 1:
            raise BrowserWindowConfigError("monitor index must be >= 1")
        return f"monitor-{raw}"
    if not isinstance(raw, str):
        raise BrowserWindowConfigError("preferred_monitor must be a string or integer")

    text = raw.strip().lower()
    if not text:
        return default
    if text in {"primary", "active"}:
        return text
    if text.isdigit():
        idx = int(text)
        if idx < 1:
            raise BrowserWindowConfigError("monitor index must be >= 1")
        return f"monitor-{idx}"

    match = _MONITOR_INDEX_PATTERN.match(text)
    if match:
        idx = int(match.group(1))
        if idx < 1:
            raise BrowserWindowConfigError("monitor index must be >= 1")
        return f"monitor-{idx}"

    raise BrowserWindowConfigError(
        f"unsupported preferred_monitor '{raw}'; expected 'primary', 'active', or 'monitor-N'"
    )


def _validate_dimensions(width: Any, height: Any) -> WindowSize:
    if isinstance(width, bool) or isinstance(height, bool):
        raise BrowserWindowConfigError("window width and height must be integers")
    try:
        w = int(width)
        h = int(height)
    except (TypeError, ValueError) as exc:
        raise BrowserWindowConfigError("window width and height must be integers") from exc

    if w < MIN_WINDOW_WIDTH or h < MIN_WINDOW_HEIGHT:
        raise BrowserWindowConfigError(
            f"window size must be at least {MIN_WINDOW_WIDTH}x{MIN_WINDOW_HEIGHT}"
        )
    if w > MAX_WINDOW_WIDTH or h > MAX_WINDOW_HEIGHT:
        raise BrowserWindowConfigError(
            f"window size exceeds maximum {MAX_WINDOW_WIDTH}x{MAX_WINDOW_HEIGHT}"
        )
    return WindowSize(width=w, height=h)


def parse_window_size(
    raw: Any,
    default: tuple[int, int] = (DEFAULT_TAB_WIDTH, DEFAULT_TAB_HEIGHT),
) -> WindowSize:
    if raw is None or raw == "":
        return _validate_dimensions(default[0], default[1])
    if isinstance(raw, WindowSize):
        return _validate_dimensions(raw.width, raw.height)
    if isinstance(raw, dict):
        return _validate_dimensions(
            raw.get("width", raw.get("w")),
            raw.get("height", raw.get("h")),
        )
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return _validate_dimensions(raw[0], raw[1])
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return _validate_dimensions(default[0], default[1])
        match = _SIZE_PATTERN.match(text)
        if not match:
            raise BrowserWindowConfigError(
                f"invalid window_size '{raw}'; expected WIDTHxHEIGHT (e.g. 1600x900)"
            )
        return _validate_dimensions(int(match.group(1)), int(match.group(2)))

    raise BrowserWindowConfigError(
        "window_size must be a 'WIDTHxHEIGHT' string or {'width': W, 'height': H} object"
    )


def parse_window_position(raw: Any, default: str = "grid") -> WindowPosition:
    if raw is None or raw == "":
        return parse_window_position(default, default="grid") if default != "grid" else WindowPosition("grid")
    if isinstance(raw, WindowPosition):
        return raw
    if isinstance(raw, dict):
        if "x" in raw and "y" in raw:
            if isinstance(raw["x"], bool) or isinstance(raw["y"], bool):
                raise BrowserWindowConfigError("position coordinates x and y must be integers")
            try:
                return WindowPosition(mode="coordinates", x=int(raw["x"]), y=int(raw["y"]))
            except (TypeError, ValueError) as exc:
                raise BrowserWindowConfigError("position coordinates x and y must be integers") from exc
        preset = raw.get("mode") or raw.get("preset") or raw.get("position")
        if preset is not None:
            return parse_window_position(preset, default=default)
        raise BrowserWindowConfigError("position object must specify {'x': ..., 'y': ...} or {'mode': ...}")

    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        if isinstance(raw[0], bool) or isinstance(raw[1], bool):
            raise BrowserWindowConfigError("position coordinates x and y must be integers")
        try:
            return WindowPosition(mode="coordinates", x=int(raw[0]), y=int(raw[1]))
        except (TypeError, ValueError) as exc:
            raise BrowserWindowConfigError("position coordinates x and y must be integers") from exc

    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return WindowPosition(default)
        lowered = text.lower().replace("_", "-")
        if lowered in VALID_POSITION_PRESETS:
            return WindowPosition(mode=lowered)

        kv_match = _COORD_KV_PATTERN.match(text)
        if kv_match:
            return WindowPosition(
                mode="coordinates",
                x=int(kv_match.group(1)),
                y=int(kv_match.group(2)),
            )

        pair_match = _COORD_PAIR_PATTERN.match(text)
        if pair_match:
            return WindowPosition(
                mode="coordinates",
                x=int(pair_match.group(1)),
                y=int(pair_match.group(2)),
            )

        raise BrowserWindowConfigError(
            f"unsupported window position '{raw}'; expected one of "
            f"{', '.join(sorted(VALID_POSITION_PRESETS))} or 'x=<int>,y=<int>'"
        )

    raise BrowserWindowConfigError("position must be a preset string or coordinate mapping")


def _extract_config_section(config_data: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(config_data, dict):
        return {}
    nested = config_data.get("browser") or config_data.get("BROWSER")
    merged: dict[str, Any] = {}
    if isinstance(nested, dict):
        merged.update(nested)
    for key, target in (
        ("PREFERRED_MONITOR", "preferred_monitor"),
        ("preferred_monitor", "preferred_monitor"),
        ("MONITOR", "preferred_monitor"),
        ("monitor", "preferred_monitor"),
        ("WINDOW_SIZE", "window_size"),
        ("window_size", "window_size"),
        ("WINDOW_POSITION", "position"),
        ("window_position", "position"),
        ("POSITION", "position"),
        ("position", "position"),
    ):
        if key in config_data and target not in merged:
            merged[target] = config_data[key]
    return merged


def load_browser_window_config(
    cli_args: dict[str, Any] | Any | None = None,
    env: dict[str, str] | None = None,
    config_data: dict[str, Any] | None = None,
    config_path: str | Path | None = None,
    default_size: tuple[int, int] = (DEFAULT_TAB_WIDTH, DEFAULT_TAB_HEIGHT),
    default_position: str = "grid",
    default_monitor: str = "active",
) -> BrowserWindowConfig:
    if config_data is None and config_path is not None:
        try:
            raw_text = Path(config_path).read_text(encoding="utf-8")
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                config_data = parsed
        except Exception:
            config_data = {}

    cfg_section = _extract_config_section(config_data)
    environ = env if env is not None else os.environ

    if cli_args is None:
        cli_map: dict[str, Any] = {}
    elif isinstance(cli_args, dict):
        cli_map = cli_args
    else:
        cli_map = vars(cli_args)

    raw_monitor = (
        cli_map.get("monitor")
        or cli_map.get("preferred_monitor")
        or environ.get("JARVIS_PREFERRED_MONITOR")
        or environ.get("JARVIS_MONITOR")
        or cfg_section.get("preferred_monitor")
        or cfg_section.get("monitor")
    )
    raw_size = (
        cli_map.get("window_size")
        or environ.get("JARVIS_WINDOW_SIZE")
        or cfg_section.get("window_size")
    )
    raw_position = (
        cli_map.get("position")
        or cli_map.get("window_position")
        or environ.get("JARVIS_WINDOW_POSITION")
        or environ.get("JARVIS_POSITION")
        or cfg_section.get("position")
        or cfg_section.get("window_position")
    )

    return BrowserWindowConfig(
        preferred_monitor=parse_preferred_monitor(raw_monitor, default=default_monitor),
        window_size=parse_window_size(raw_size, default=default_size),
        position=parse_window_position(raw_position, default=default_position),
    )


def enumerate_monitors(system: str | None = None) -> list[MonitorBounds]:
    plat = system or platform.system()

    if plat == "Windows":
        try:
            user32 = ctypes.windll.user32

            class _RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            class _MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", _RECT),
                    ("rcWork", _RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            MonitorEnumProc = ctypes.WINFUNCTYPE(
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(_RECT),
                ctypes.c_double,
            )
            found: list[MonitorBounds] = []

            def _cb(hmonitor, _hdc, _lprect, _lparam):
                info = _MONITORINFO()
                info.cbSize = ctypes.sizeof(_MONITORINFO)
                if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                    r = info.rcWork
                    is_primary = bool(info.dwFlags & 1)
                    idx = len(found) + 1
                    found.append(
                        MonitorBounds(
                            x=int(r.left),
                            y=int(r.top),
                            width=max(MIN_WINDOW_WIDTH, int(r.right - r.left)),
                            height=max(MIN_WINDOW_HEIGHT, int(r.bottom - r.top)),
                            name=f"monitor-{idx}",
                            is_primary=is_primary,
                        )
                    )
                return 1

            user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_cb), 0)
            if found:
                return found
        except Exception:
            pass

    elif plat == "Darwin":
        try:
            from AppKit import NSScreen

            screens = list(NSScreen.screens())
            if screens:
                max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
                found = []
                for idx, screen in enumerate(screens, start=1):
                    frame = screen.frame()
                    sx = int(frame.origin.x)
                    sy = int(max_y - (frame.origin.y + frame.size.height))
                    sw = int(frame.size.width)
                    sh = int(frame.size.height)
                    found.append(
                        MonitorBounds(
                            x=sx,
                            y=sy,
                            width=sw,
                            height=sh,
                            name=f"monitor-{idx}",
                            is_primary=(idx == 1),
                        )
                    )
                return found
        except Exception:
            pass

    else:
        try:
            out = subprocess.check_output(
                ["xrandr", "--query"],
                text=True,
                stderr=subprocess.DEVNULL,
            )
            pattern = re.compile(
                r"^(\S+)\s+connected\s+(primary\s+)?(\d+)x(\d+)\+(-?\d+)\+(-?\d+)",
                re.MULTILINE,
            )
            found = []
            for idx, match in enumerate(pattern.finditer(out), start=1):
                is_primary = bool(match.group(2))
                w = int(match.group(3))
                h = int(match.group(4))
                x = int(match.group(5))
                y = int(match.group(6))
                found.append(
                    MonitorBounds(
                        x=x,
                        y=y,
                        width=w,
                        height=h,
                        name=f"monitor-{idx}",
                        is_primary=is_primary,
                    )
                )
            if found:
                return found
        except Exception:
            pass

    return [MonitorBounds(x=0, y=0, width=1920, height=1080, name="monitor-1", is_primary=True)]


def resolve_monitor_bounds(
    preferred_monitor: str = "active",
    monitors: list[MonitorBounds] | None = None,
    active_bounds: tuple[int, int, int, int] | None = None,
    primary_size: tuple[int, int] = (1920, 1080),
) -> tuple[int, int, int, int]:
    mode = parse_preferred_monitor(preferred_monitor)
    available = list(monitors) if monitors is not None else enumerate_monitors()
    if not available:
        available = [
            MonitorBounds(
                x=0,
                y=0,
                width=primary_size[0],
                height=primary_size[1],
                name="monitor-1",
                is_primary=True,
            )
        ]

    if mode == "active":
        if active_bounds is not None and len(active_bounds) == 4:
            return (
                int(active_bounds[0]),
                int(active_bounds[1]),
                int(active_bounds[2]),
                int(active_bounds[3]),
            )
        return available[0].as_tuple()

    if mode == "primary":
        for mon in available:
            if mon.is_primary:
                return mon.as_tuple()
        return available[0].as_tuple()

    match = _MONITOR_INDEX_PATTERN.match(mode)
    if match:
        index = int(match.group(1)) - 1
        if 0 <= index < len(available):
            return available[index].as_tuple()
        # Deterministic horizontal layout fallback when monitor-N is requested
        # on environments where OS monitor enumeration returns a single display.
        base = available[0]
        return (
            base.x + index * base.width,
            base.y,
            base.width,
            base.height,
        )

    return available[0].as_tuple()


def compute_window_geometry(
    config: BrowserWindowConfig,
    slot: int = 0,
    monitor_bounds: tuple[int, int, int, int] | None = None,
    padding: int = 20,
    tab_overrides: dict[str, Any] | None = None,
) -> tuple[int, int, int, int]:
    """Return (width, height, x, y) for a browser window or slot."""
    effective_config = config
    if isinstance(tab_overrides, dict):
        override_size = tab_overrides.get("window_size") or tab_overrides.get("windowSize")
        override_pos = tab_overrides.get("position") or tab_overrides.get("windowPosition")
        override_mon = tab_overrides.get("preferred_monitor") or tab_overrides.get("monitor")
        effective_config = BrowserWindowConfig(
            preferred_monitor=(
                parse_preferred_monitor(override_mon, default=config.preferred_monitor)
                if override_mon is not None
                else config.preferred_monitor
            ),
            window_size=(
                parse_window_size(
                    override_size,
                    default=(config.window_size.width, config.window_size.height),
                )
                if override_size is not None and str(override_size).lower() != "large"
                else config.window_size
            ),
            position=(
                parse_window_position(override_pos, default=config.position.mode)
                if override_pos is not None
                else config.position
            ),
        )

    sx, sy, sw, sh = monitor_bounds or resolve_monitor_bounds(effective_config.preferred_monitor)
    win_w = min(effective_config.window_size.width, max(MIN_WINDOW_WIDTH, sw))
    win_h = min(effective_config.window_size.height, max(MIN_WINDOW_HEIGHT, sh))
    pos = effective_config.position

    if pos.mode == "coordinates":
        raw_x = int(pos.x or 0)
        raw_y = int(pos.y or 0)
        # If monitor offset is non-zero and coordinates are local to the monitor, offset by sx/sy
        if (sx != 0 or sy != 0) and 0 <= raw_x < sw and 0 <= raw_y < sh:
            return win_w, win_h, sx + raw_x, sy + raw_y
        return win_w, win_h, raw_x, raw_y

    if pos.mode == "center":
        x = sx + max(0, (sw - win_w) // 2)
        y = sy + max(0, (sh - win_h) // 2)
        return win_w, win_h, x, y

    if pos.mode == "top-left":
        return win_w, win_h, sx + padding, sy + padding

    if pos.mode == "top-right":
        x = sx + max(padding, sw - win_w - padding)
        return win_w, win_h, x, sy + padding

    if pos.mode == "bottom-left":
        y = sy + max(padding, sh - win_h - padding)
        return win_w, win_h, sx + padding, y

    if pos.mode == "bottom-right":
        x = sx + max(padding, sw - win_w - padding)
        y = sy + max(padding, sh - win_h - padding)
        return win_w, win_h, x, y

    # Default "grid" mode: 2x2 slot grid within target monitor bounds
    col = (slot % 4) % 2
    row = (slot % 4) // 2
    x = sx + padding + col * (win_w + padding)
    y = sy + padding + row * (win_h + padding)
    x = min(x, sx + max(padding, sw - win_w - padding))
    y = min(y, sy + max(padding, sh - win_h - padding))
    return win_w, win_h, x, y


def build_chromium_window_args(
    config: BrowserWindowConfig,
    slot: int = 0,
    monitor_bounds: tuple[int, int, int, int] | None = None,
    padding: int = 20,
) -> list[str]:
    win_w, win_h, x, y = compute_window_geometry(
        config,
        slot=slot,
        monitor_bounds=monitor_bounds,
        padding=padding,
    )
    return [
        f"--window-size={win_w},{win_h}",
        f"--window-position={x},{y}",
    ]
