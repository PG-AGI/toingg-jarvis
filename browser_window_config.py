"""
browser_window_config.py — Terminal configuration options for customizing browser/window behavior.

Supports configuring:
1. Preferred screen/monitor (`preferred_monitor`: `"active"`, `"primary"`, or monitor index `0`, `1`, ...)
2. New tab window size (`window_size`: `"WIDTHxHEIGHT"`, preset `"small" | "medium" | "large" | "fullscreen"`, or `{"width": W, "height": H}`)
3. Window positioning settings (`position`: `"grid"`, `"center"`, `"top-left"`, `"top-right"`, `"bottom-left"`, `"bottom-right"`, `"top-center"`, or `"x=X,y=Y"`)

Precedence order:
  CLI flags (`--monitor`, `--window-size`, `--position`)
  > Environment variables (`JARVIS_BROWSER_MONITOR`, `JARVIS_BROWSER_WINDOW_SIZE`, `JARVIS_BROWSER_POSITION`)
  > `config.json` (`browser` section)
  > Built-in defaults (`active`, `860x580`, `grid`)
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import platform as _plat
import re
import subprocess
from pathlib import Path
from typing import Any


DEFAULT_WIN_W = 860
DEFAULT_WIN_H = 580
DEFAULT_PADDING = 20

WINDOW_SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "small": (680, 480),
    "default": (DEFAULT_WIN_W, DEFAULT_WIN_H),
    "medium": (1024, 720),
    "large": (1280, 800),
    "xlarge": (1440, 900),
}

POSITION_PRESETS = {
    "grid",
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "top-center",
}


class BrowserWindowConfigError(ValueError):
    """Raised when browser window configuration values are invalid."""


def parse_preferred_monitor(value: Any) -> str | int:
    """Normalize preferred monitor specifier to `'active'`, `'primary'`, or non-negative `int`."""
    if value is None or value == "":
        return "active"
    if isinstance(value, bool):
        raise BrowserWindowConfigError("preferred_monitor cannot be a boolean")
    if isinstance(value, int):
        if value < 0:
            raise BrowserWindowConfigError("preferred_monitor index must be >= 0")
        return value
    text = str(value).strip().lower()
    if text in ("active", "current", "auto"):
        return "active"
    if text in ("primary", "main", "default"):
        return "primary"
    if re.fullmatch(r"\d+", text):
        return int(text)
    raise BrowserWindowConfigError(
        f"Invalid preferred_monitor {value!r}; expected 'active', 'primary', or monitor index (0, 1, ...)"
    )


def parse_window_size(
    value: Any,
    screen_bounds: tuple[int, int, int, int] | None = None,
) -> tuple[int, int]:
    """Parse a window size configuration into `(width, height)` in pixels."""
    sw = screen_bounds[2] if screen_bounds else 1920
    sh = screen_bounds[3] if screen_bounds else 1080

    if value is None or value == "":
        return DEFAULT_WIN_W, DEFAULT_WIN_H

    if isinstance(value, dict):
        try:
            w = int(value.get("width") or value.get("w"))
            h = int(value.get("height") or value.get("h"))
        except (TypeError, ValueError) as exc:
            raise BrowserWindowConfigError(f"Invalid window_size object: {value!r}") from exc
        if w < 200 or h < 150:
            raise BrowserWindowConfigError("window_size dimensions must be at least 200x150")
        return w, h

    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            w, h = int(value[0]), int(value[1])
        except (TypeError, ValueError) as exc:
            raise BrowserWindowConfigError(f"Invalid window_size tuple: {value!r}") from exc
        if w < 200 or h < 150:
            raise BrowserWindowConfigError("window_size dimensions must be at least 200x150")
        return w, h

    text = str(value).strip().lower()
    if text in ("fullscreen", "maximized", "full"):
        return max(200, sw - DEFAULT_PADDING * 2), max(150, sh - DEFAULT_PADDING * 2)
    if text in WINDOW_SIZE_PRESETS:
        return WINDOW_SIZE_PRESETS[text]

    match = re.fullmatch(r"(\d+)\s*[x,]\s*(\d+)", text)
    if match:
        w, h = int(match.group(1)), int(match.group(2))
        if w < 200 or h < 150:
            raise BrowserWindowConfigError("window_size dimensions must be at least 200x150")
        return w, h

    raise BrowserWindowConfigError(
        f"Invalid window_size {value!r}; expected 'WIDTHxHEIGHT' (e.g. '1280x800') or preset ({sorted(WINDOW_SIZE_PRESETS)})"
    )


def parse_window_position(value: Any) -> dict[str, Any]:
    """
    Parse a window position specifier into either:
    - `{"mode": preset}` where preset is in `POSITION_PRESETS`
    - `{"mode": "custom", "x": int, "y": int}`
    """
    if value is None or value == "":
        return {"mode": "grid"}

    if isinstance(value, dict):
        if "mode" in value and str(value["mode"]).strip().lower() in POSITION_PRESETS:
            return {"mode": str(value["mode"]).strip().lower()}
        if "x" in value and "y" in value:
            try:
                return {"mode": "custom", "x": int(value["x"]), "y": int(value["y"])}
            except (TypeError, ValueError) as exc:
                raise BrowserWindowConfigError(f"Invalid custom position coordinates: {value!r}") from exc
        raise BrowserWindowConfigError(f"Invalid position object: {value!r}")

    if isinstance(value, (list, tuple)) and len(value) == 2:
        try:
            return {"mode": "custom", "x": int(value[0]), "y": int(value[1])}
        except (TypeError, ValueError) as exc:
            raise BrowserWindowConfigError(f"Invalid position tuple: {value!r}") from exc

    text = str(value).strip().lower().replace("_", "-")
    if text in POSITION_PRESETS:
        return {"mode": text}

    kv_match = re.fullmatch(r"x\s*=\s*(-?\d+)\s*,\s*y\s*=\s*(-?\d+)", text)
    if kv_match:
        return {"mode": "custom", "x": int(kv_match.group(1)), "y": int(kv_match.group(2))}

    pair_match = re.fullmatch(r"(-?\d+)\s*,\s*(-?\d+)", text)
    if pair_match:
        return {"mode": "custom", "x": int(pair_match.group(1)), "y": int(pair_match.group(2))}

    raise BrowserWindowConfigError(
        f"Invalid position {value!r}; expected one of {sorted(POSITION_PRESETS)} or 'x=100,y=100'"
    )


def enumerate_monitors() -> list[tuple[int, int, int, int]]:
    """Return a list of connected monitor work-area bounds `(x, y, width, height)`."""
    plat = _plat.system()
    monitors: list[tuple[int, int, int, int]] = []

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
                ctypes.c_void_p,
                ctypes.c_void_p,
                ctypes.POINTER(_RECT),
                ctypes.c_long,
            )

            raw_list: list[tuple[int, tuple[int, int, int, int]]] = []

            def _cb(hmon, _hdc, _lprect, _lparam):
                info = _MONITORINFO()
                info.cbSize = ctypes.sizeof(_MONITORINFO)
                if user32.GetMonitorInfoW(ctypes.c_void_p(hmon), ctypes.byref(info)):
                    r = info.rcWork
                    is_primary = bool(info.dwFlags & 1)
                    bounds = (int(r.left), int(r.top), int(r.right - r.left), int(r.bottom - r.top))
                    raw_list.append((0 if is_primary else 1, bounds))
                return 1

            user32.EnumDisplayMonitors(None, None, MonitorEnumProc(_cb), 0)
            raw_list.sort(key=lambda item: (item[0], item[1][0], item[1][1]))
            monitors = [item[1] for item in raw_list if item[1][2] > 0 and item[1][3] > 0]
        except Exception:
            pass

    elif plat == "Darwin":
        try:
            from AppKit import NSScreen  # type: ignore

            screens = list(NSScreen.screens())
            if screens:
                max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
                for s in screens:
                    f = s.frame()
                    sx, sy = int(f.origin.x), int(max_y - (f.origin.y + f.size.height))
                    sw, sh = int(f.size.width), int(f.size.height)
                    monitors.append((sx, sy, sw, sh))
        except Exception:
            pass

    else:
        try:
            out = subprocess.check_output(
                ["xrandr", "--query"], text=True, stderr=subprocess.DEVNULL
            )
            for m in re.finditer(r"connected(?:\s+primary)?\s+(\d+)x(\d+)\+(\d+)\+(\d+)", out):
                sw, sh, sx, sy = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
                monitors.append((sx, sy, sw, sh))
        except Exception:
            pass

    return monitors


def resolve_monitor_bounds(
    preferred_monitor: str | int = "active",
    *,
    monitors: list[tuple[int, int, int, int]] | None = None,
    active_screen_bounds: tuple[int, int, int, int] | None = None,
    fallback_screen_size: tuple[int, int] = (1920, 1080),
) -> tuple[int, int, int, int]:
    """Resolve target monitor work-area bounds `(x, y, width, height)`."""
    spec = parse_preferred_monitor(preferred_monitor)
    available = monitors if monitors is not None else enumerate_monitors()

    if isinstance(spec, int):
        if available and 0 <= spec < len(available):
            return available[spec]
        if available:
            return available[0]

    if spec == "primary":
        if available:
            return available[0]
        return (0, 0, fallback_screen_size[0], fallback_screen_size[1])

    # Default 'active'
    if active_screen_bounds:
        return active_screen_bounds
    if available:
        return available[0]
    return (0, 0, fallback_screen_size[0], fallback_screen_size[1])


def compute_window_geometry(
    config: dict[str, Any] | None = None,
    *,
    slot: int = 0,
    tab: dict[str, Any] | None = None,
    monitors: list[tuple[int, int, int, int]] | None = None,
    active_screen_bounds: tuple[int, int, int, int] | None = None,
    fallback_screen_size: tuple[int, int] = (1920, 1080),
    padding: int = DEFAULT_PADDING,
) -> tuple[int, int, int, int]:
    """
    Compute `(width, height, x, y)` for a new browser tab/slot window using the resolved
    terminal configuration and optional per-tab overrides.
    """
    cfg = dict(config or {})
    tab_dict = tab if isinstance(tab, dict) else {}

    monitor_spec = tab_dict.get("monitor", tab_dict.get("preferred_monitor", cfg.get("preferred_monitor", "active")))
    sx, sy, sw, sh = resolve_monitor_bounds(
        monitor_spec,
        monitors=monitors,
        active_screen_bounds=active_screen_bounds,
        fallback_screen_size=fallback_screen_size,
    )

    size_spec = tab_dict.get("windowSize") or tab_dict.get("window_size") or cfg.get("window_size")
    win_w, win_h = parse_window_size(size_spec, screen_bounds=(sx, sy, sw, sh))
    win_w = min(win_w, max(200, sw - padding * 2))
    win_h = min(win_h, max(150, sh - padding * 2))

    pos_spec = tab_dict.get("position") or tab_dict.get("windowPosition") or tab_dict.get("window_position") or cfg.get("position", "grid")
    pos = parse_window_position(pos_spec)
    mode = pos["mode"]

    if mode == "center":
        x = sx + max(0, (sw - win_w) // 2)
        y = sy + max(0, (sh - win_h) // 2)
    elif mode == "top-left":
        x = sx + padding
        y = sy + padding
    elif mode == "top-right":
        x = sx + max(padding, sw - win_w - padding)
        y = sy + padding
    elif mode == "bottom-left":
        x = sx + padding
        y = sy + max(padding, sh - win_h - padding)
    elif mode == "bottom-right":
        x = sx + max(padding, sw - win_w - padding)
        y = sy + max(padding, sh - win_h - padding)
    elif mode == "top-center":
        x = sx + max(0, (sw - win_w) // 2)
        y = sy + padding
    elif mode == "custom":
        raw_x = int(pos["x"])
        raw_y = int(pos["y"])
        # Offset relative to selected monitor origin if coordinates are within monitor dimensions
        x = sx + raw_x if 0 <= raw_x < sw else raw_x
        y = sy + raw_y if 0 <= raw_y < sh else raw_y
    else:
        # 2x2 slot grid
        col = (slot % 4) % 2
        row = (slot % 4) // 2
        x = sx + padding + col * (win_w + padding)
        y = sy + padding + row * (win_h + padding)

    # Clamp inside selected monitor work area so windows never spawn off-screen
    max_x = sx + max(padding, sw - win_w - padding)
    max_y = sy + max(padding, sh - win_h - padding)
    x = max(sx + padding, min(x, max_x))
    y = max(sy + padding, min(y, max_y))

    return win_w, win_h, x, y


def load_browser_window_config(
    *,
    config_path: str | os.PathLike[str] | None = None,
    cli_args: dict[str, Any] | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Merge browser window settings from `config.json`, environment variables, and CLI arguments.
    Returns a normalized dict: `{"preferred_monitor": ..., "window_size": "WxH", "position": ...}`.
    """
    env = environ if environ is not None else os.environ
    cli = dict(cli_args or {})

    file_browser_cfg: dict[str, Any] = {}
    if config_path and Path(config_path).exists():
        try:
            raw_cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
            if isinstance(raw_cfg, dict):
                if isinstance(raw_cfg.get("browser"), dict):
                    file_browser_cfg.update(raw_cfg["browser"])
                for legacy_key, target_key in (
                    ("BROWSER_MONITOR", "preferred_monitor"),
                    ("BROWSER_WINDOW_SIZE", "window_size"),
                    ("BROWSER_POSITION", "position"),
                ):
                    if legacy_key in raw_cfg and target_key not in file_browser_cfg:
                        file_browser_cfg[target_key] = raw_cfg[legacy_key]
        except Exception:
            pass

    raw_monitor = (
        cli.get("preferred_monitor")
        if cli.get("preferred_monitor") is not None
        else cli.get("monitor")
        if cli.get("monitor") is not None
        else env.get("JARVIS_BROWSER_MONITOR")
        or file_browser_cfg.get("preferred_monitor")
        or "active"
    )
    raw_size = (
        cli.get("window_size")
        if cli.get("window_size") is not None
        else env.get("JARVIS_BROWSER_WINDOW_SIZE")
        or file_browser_cfg.get("window_size")
        or f"{DEFAULT_WIN_W}x{DEFAULT_WIN_H}"
    )
    raw_position = (
        cli.get("position")
        if cli.get("position") is not None
        else env.get("JARVIS_BROWSER_POSITION")
        or file_browser_cfg.get("position")
        or "grid"
    )

    preferred_monitor = parse_preferred_monitor(raw_monitor)
    w, h = parse_window_size(raw_size)
    pos = parse_window_position(raw_position)
    position_str = (
        f"x={pos['x']},y={pos['y']}" if pos["mode"] == "custom" else pos["mode"]
    )

    return {
        "preferred_monitor": preferred_monitor,
        "window_size": f"{w}x{h}",
        "width": w,
        "height": h,
        "position": position_str,
    }


def build_launcher_arg_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser for `jarvis_launcher.py` browser/window customization flags."""
    parser = argparse.ArgumentParser(
        description="JARVIS Web Launcher with customizable browser/window behavior",
        add_help=True,
    )
    parser.add_argument(
        "--monitor",
        "--preferred-monitor",
        dest="preferred_monitor",
        default=None,
        help="Preferred monitor: 'active', 'primary', or monitor index (0, 1, ...)",
    )
    parser.add_argument(
        "--window-size",
        dest="window_size",
        default=None,
        help="New tab window size: 'WIDTHxHEIGHT' (e.g. '1280x800') or preset ('small', 'medium', 'large', 'fullscreen')",
    )
    parser.add_argument(
        "--position",
        "--window-position",
        dest="position",
        default=None,
        help="Window positioning: 'grid', 'center', 'top-left', 'top-right', 'bottom-left', 'bottom-right', or 'x=100,y=100'",
    )
    return parser
