"""
JARVIS LAUNCHER  v2.0
=====================
Wake trigger / voice command → opens jarvis_web.html in Chrome.

HTTP server on :8766:
  GET  /          → serves jarvis_web.html
  POST /open_tabs → opens URLs in 2×2 Chrome slot grid
  POST /close_tabs→ terminates all slot windows

Requirements:
    pip install sounddevice numpy speechrecognition
"""

import argparse
import os, sys, time, threading, subprocess, tempfile, json, webbrowser
import uuid
import ctypes, ctypes.wintypes
import platform as _plat
from datetime import datetime, timedelta, timezone

from browser_window_config import (
    choose_screen_bounds,
    chrome_window_args,
    parse_browser_window_config,
    resolve_window_geometry,
)
from native_file_manager import NativeFileActionError, handle_file_action_payload

# ── CONFIG ────────────────────────────────────────────────────────────────────
_DIR        = os.path.dirname(os.path.abspath(__file__))
WEB_HTML    = os.path.join(_DIR, "jarvis_web.html")
VISUAL_HTML = os.path.join(_DIR, "jarvis_visual.html")
BROWSER_CLIENT = os.path.join(_DIR, "browserClient.py")
WAKE_WORDS  = ["hey jarvis", "jarvis", "hey jervis", "hey davis"]
LAUNCH_COOLDOWN = 4.0
HTTP_PORT   = 8766

# ── shared state (jarvis_web.html POSTs here; jarvis_visual.html polls here) ─
_http_state      = {"state": "initializing", "text": "", "status": "INITIALIZING..."}
_http_state_lock = threading.Lock()

# ── SLOT WINDOW CONFIG (mirrors jarvis_terminal.py) ───────────────────────────
URL_WIN_W  = 860
URL_WIN_H  = 580
DESKTOP_PREVIEW_MIN_W = 1280
DESKTOP_PREVIEW_MIN_H = 800
_PADDING   = 20
_url_slot      = 0
_url_slot_wins = {}
_url_slot_modes = {}
_slot_profiles = {}
BROWSER_WINDOW_CONFIG = parse_browser_window_config()
BROWSER_CLIENT_ARGS = []

# ── APP REGISTRY ──────────────────────────────────────────────────────────────
_IS_MAC = _plat.system() == "Darwin"

APPS = {
    "spotify": (
        ["/Applications/Spotify.app/Contents/MacOS/Spotify"] if _IS_MAC else
        [r"C:\Users\{user}\AppData\Local\Microsoft\WindowsApps\Spotify.exe",
         r"C:\Users\{user}\AppData\Roaming\Spotify\Spotify.exe"]
    ),
    "vs code": (
        ["/Applications/Visual Studio Code.app/Contents/MacOS/Electron"] if _IS_MAC else
        [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"]
    ),
    "vscode": (
        ["/Applications/Visual Studio Code.app/Contents/MacOS/Electron"] if _IS_MAC else
        [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"]
    ),
    "code": (
        ["/Applications/Visual Studio Code.app/Contents/MacOS/Electron"] if _IS_MAC else
        [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"]
    ),
    "visual studio code": (
        ["/Applications/Visual Studio Code.app/Contents/MacOS/Electron"] if _IS_MAC else
        [r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe"]
    ),
    "chrome":     ["chrome"],
    "firefox":    ["firefox"],
    "notepad":    ["notepad"],
    "calculator": ["calc"],
    "explorer":   ["explorer"],
    "terminal":   ["wt"],
}

SMALL_WIN = {
    "vs code":            {"w": 700, "h": 480, "x": 40, "y": 40},
    "vscode":             {"w": 700, "h": 480, "x": 40, "y": 40},
    "code":               {"w": 700, "h": 480, "x": 40, "y": 40},
    "visual studio code": {"w": 700, "h": 480, "x": 40, "y": 40},
    "spotify":            {"w": 420, "h": 580, "x": 40, "y": 560},
}

PROCESS_NAMES = {
    "vs code":            "Code.exe",
    "vscode":             "Code.exe",
    "code":               "Code.exe",
    "visual studio code": "Code.exe",
    "spotify":            "Spotify.exe",
}

# ── CHROME FINDER (cross-platform) ───────────────────────────────────────────
def find_chrome():
    plat = _plat.system()
    user = os.environ.get("USERNAME") or os.environ.get("USER", "")
    if plat == "Windows":
        for c in [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            rf"C:\Users\{user}\AppData\Local\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]:
            if os.path.exists(c): return c
    elif plat == "Darwin":
        for c in [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]:
            if os.path.exists(c): return c
    else:
        for cmd in ["google-chrome","google-chrome-stable","chromium-browser","chromium","microsoft-edge"]:
            try:
                r = subprocess.run(["which", cmd], capture_output=True, text=True)
                if r.returncode == 0: return r.stdout.strip()
            except Exception: pass
    return None

# ── SCREEN SIZE ───────────────────────────────────────────────────────────────
def get_screen_size():
    try:
        if _plat.system() == "Windows":
            u = ctypes.windll.user32
            return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        elif _plat.system() == "Darwin":
            import re
            out = subprocess.check_output(
                ["system_profiler", "SPDisplaysDataType"], text=True, stderr=subprocess.DEVNULL)
            m = re.search(r"Resolution: (\d+) x (\d+)", out)
            if m: return int(m.group(1)), int(m.group(2))
        else:
            import re
            out = subprocess.check_output(
                ["xrandr","--current"], text=True, stderr=subprocess.DEVNULL)
            m = re.search(r"current (\d+) x (\d+)", out)
            if m: return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return 1920, 1080

def get_active_window_bounds():
    """Return the front macOS window bounds as (x, y, width, height), if available."""
    if _plat.system() != "Darwin":
        return None
    script = (
        'tell application "System Events"\n'
        '  set frontApp to first application process whose frontmost is true\n'
        '  set frontWindows to windows of frontApp\n'
        '  if (count of frontWindows) is 0 then return ""\n'
        '  set {wx, wy} to position of window 1 of frontApp\n'
        '  set {ww, wh} to size of window 1 of frontApp\n'
        '  return (wx as text) & "," & (wy as text) & "," & (ww as text) & "," & (wh as text)\n'
        'end tell'
    )
    try:
        out = subprocess.check_output(
            ["osascript", "-e", script], text=True, stderr=subprocess.DEVNULL
        ).strip()
        parts = [int(float(p.strip())) for p in out.split(",")]
        if len(parts) == 4 and parts[2] > 0 and parts[3] > 0:
            return tuple(parts)
    except Exception:
        pass
    return None

def get_active_screen_bounds():
    """Return the bounds (x, y, width, height) of the monitor containing the active window."""
    plat = _plat.system()

    if plat == "Windows":
        try:
            user32 = ctypes.windll.user32

            class _RECT(ctypes.Structure):
                _fields_ = [
                    ("left",   ctypes.c_long), ("top",    ctypes.c_long),
                    ("right",  ctypes.c_long), ("bottom", ctypes.c_long),
                ]

            class _MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize",    ctypes.c_ulong),
                    ("rcMonitor", _RECT),
                    ("rcWork",    _RECT),
                    ("dwFlags",   ctypes.c_ulong),
                ]

            MONITOR_DEFAULTTONEAREST = 2
            hwnd = user32.GetForegroundWindow()
            hmon = user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
            info = _MONITORINFO()
            info.cbSize = ctypes.sizeof(_MONITORINFO)
            if user32.GetMonitorInfoW(hmon, ctypes.byref(info)):
                r = info.rcWork  # work area excludes the taskbar
                return r.left, r.top, r.right - r.left, r.bottom - r.top
        except Exception:
            pass
        return None

    elif plat == "Darwin":
        try:
            from AppKit import NSEvent, NSScreen

            screens = list(NSScreen.screens())
            if not screens:
                return None

            max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
            points = []

            active = get_active_window_bounds()
            if active:
                ax, ay, aw, ah = active
                points.append((ax + aw / 2, max_y - (ay + ah / 2)))

            mouse = NSEvent.mouseLocation()
            points.append((mouse.x, mouse.y))

            for px, py in points:
                for screen in screens:
                    frame = screen.frame()
                    sx, sy = frame.origin.x, frame.origin.y
                    sw, sh = frame.size.width, frame.size.height
                    if sx <= px < sx + sw and sy <= py < sy + sh:
                        return int(sx), int(max_y - (sy + sh)), int(sw), int(sh)
        except Exception:
            pass

    return None

def top_center_near_active_window(win_w):
    """Place a window at the top of the same display area as the active app."""
    screen = get_active_screen_bounds()
    if screen:
        sx, sy, sw, _ = screen
        return sx + max(0, (sw - win_w) // 2), sy + _PADDING
    active = get_active_window_bounds()
    if active:
        ax, ay, aw, _ = active
        return ax + (aw - win_w) // 2, ay
    sw, _ = get_screen_size()
    return max(0, (sw - win_w) // 2), _PADDING

def top_right_near_active_window(win_w):
    """Place a window near the top-right of the same display area as the active app."""
    screen = get_active_screen_bounds()
    if screen:
        sx, sy, sw, _ = screen
        return sx + sw - win_w - _PADDING, sy + _PADDING
    active = get_active_window_bounds()
    if active:
        ax, ay, aw, _ = active
        return ax + aw - win_w - _PADDING, ay
    sw, _ = get_screen_size()
    return max(0, sw - win_w - _PADDING), _PADDING

# ── SLOT MANAGER (mirrors jarvis_terminal.py exactly) ────────────────────────
def _ensure_profile(slot):
    if slot not in _slot_profiles:
        d = os.path.join(tempfile.gettempdir(), f"jarvis_chrome_slot_{slot}")
        os.makedirs(d, exist_ok=True)
        _slot_profiles[slot] = d
    return _slot_profiles[slot]

def _available_screen_bounds():
    plat = _plat.system()
    if plat == "Windows":
        try:
            monitors = []
            user32 = ctypes.windll.user32

            class _RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long),
                ]

            class _MONITORINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", ctypes.c_ulong),
                    ("rcMonitor", _RECT),
                    ("rcWork", _RECT),
                    ("dwFlags", ctypes.c_ulong),
                ]

            def _callback(hmonitor, hdc, lprect, lparam):
                info = _MONITORINFO()
                info.cbSize = ctypes.sizeof(_MONITORINFO)
                if user32.GetMonitorInfoW(hmonitor, ctypes.byref(info)):
                    r = info.rcWork
                    monitors.append((r.left, r.top, r.right - r.left, r.bottom - r.top))
                return 1

            monitor_enum_proc = ctypes.WINFUNCTYPE(
                ctypes.c_int,
                ctypes.c_ulong,
                ctypes.c_ulong,
                ctypes.POINTER(_RECT),
                ctypes.c_double,
            )
            user32.EnumDisplayMonitors(0, 0, monitor_enum_proc(_callback), 0)
            return monitors
        except Exception:
            return []

    if plat == "Darwin":
        try:
            from AppKit import NSScreen

            screens = list(NSScreen.screens())
            if not screens:
                return []
            max_y = max(s.frame().origin.y + s.frame().size.height for s in screens)
            bounds = []
            for screen in screens:
                frame = screen.frame()
                sx, sy = frame.origin.x, frame.origin.y
                sw, sh = frame.size.width, frame.size.height
                bounds.append((int(sx), int(max_y - (sy + sh)), int(sw), int(sh)))
            return bounds
        except Exception:
            return []

    try:
        import re
        out = subprocess.check_output(["xrandr", "--listmonitors"], text=True, stderr=subprocess.DEVNULL)
        bounds = []
        for line in out.splitlines()[1:]:
            match = re.search(r"(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)", line)
            if match:
                width, height, x, y = [int(part) for part in match.groups()]
                bounds.append((x, y, width, height))
        return bounds
    except Exception:
        return []

def _screen_bounds_for_window_config():
    active = get_active_screen_bounds()
    sw, sh = get_screen_size()
    fallback = (0, 0, sw, sh)
    return choose_screen_bounds(
        BROWSER_WINDOW_CONFIG.preferred_monitor,
        _available_screen_bounds(),
        active,
        fallback,
    )

def _resolve_configured_geometry(default_size, default_position):
    return resolve_window_geometry(
        BROWSER_WINDOW_CONFIG,
        default_size=default_size,
        default_position=default_position,
        screen_bounds=_screen_bounds_for_window_config(),
    )

def _parse_browser_window_cli(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--monitor", dest="preferred_monitor")
    parser.add_argument("--window-size", dest="window_size")
    parser.add_argument("--position")
    args, _ = parser.parse_known_args(argv)
    return {key: value for key, value in vars(args).items() if value}

def _browser_client_args_from_config(config):
    args = []
    if config.preferred_monitor:
        args.extend(["--monitor", config.preferred_monitor])
    if config.window_size:
        args.extend(["--window-size", f"{config.window_size[0]}x{config.window_size[1]}"])
    if config.position:
        if isinstance(config.position, tuple):
            position = f"x={config.position[0]},y={config.position[1]}"
        else:
            position = config.position
        args.extend(["--position", position])
    return args

def configure_browser_windows(argv=None):
    global BROWSER_WINDOW_CONFIG, BROWSER_CLIENT_ARGS
    BROWSER_WINDOW_CONFIG = parse_browser_window_config(cli_values=_parse_browser_window_cli(argv or []))
    BROWSER_CLIENT_ARGS = _browser_client_args_from_config(BROWSER_WINDOW_CONFIG)
    return BROWSER_WINDOW_CONFIG

def _slot_pos(slot, win_w=URL_WIN_W, win_h=URL_WIN_H):
    """
    2×2 grid inset from screen edges:
      slot 0 = top-left    slot 1 = top-right
      slot 2 = bottom-left slot 3 = bottom-right
    """
    screen = get_active_screen_bounds()
    if screen:
        sx, sy, sw, sh = screen
    else:
        sx, sy = 0, 0
        sw, sh = get_screen_size()
    p   = _PADDING
    col = slot % 2
    row = slot // 2
    x   = sx + p + col * (win_w + p)
    y   = sy + p + row * (win_h + p)
    x   = min(x, sx + sw - win_w - p)
    y   = min(y, sy + sh - win_h - p)
    return x, y

def _is_desktop_preview_tab(tab):
    if not isinstance(tab, dict):
        return False
    mode = str(tab.get("windowMode") or tab.get("window_mode") or "").strip().lower()
    size = str(tab.get("windowSize") or tab.get("window_size") or "").strip().lower()
    label = str(tab.get("label") or tab.get("title") or "").strip().lower()
    return mode == "desktop_preview" or size == "large" or label == "campaign dashboard"

def _should_auto_close_tab(tab):
    if not isinstance(tab, dict):
        return True
    label = str(tab.get("label") or tab.get("title") or "").strip().lower()
    if label == "campaign dashboard":
        return False
    auto_close = tab.get("autoClose", tab.get("auto_close", True))
    return auto_close is not False

def _desktop_preview_geometry():
    screen = get_active_screen_bounds()
    if screen:
        sx, sy, sw, sh = screen
    else:
        sx, sy = 0, 0
        sw, sh = get_screen_size()
    p = _PADDING
    w = min(sw - p * 2, max(DESKTOP_PREVIEW_MIN_W, int(sw * 0.92)))
    h = min(sh - p * 2, max(DESKTOP_PREVIEW_MIN_H, int(sh * 0.88)))
    x = sx + max(0, (sw - w) // 2)
    y = sy + max(0, (sh - h) // 2)
    return w, h, x, y

def open_url_in_slot(url, slot, tab=None):
    """Open url in a specific grid slot; kill previous window in that slot first."""
    global _url_slot_wins, _url_slot_modes
    chrome  = find_chrome()
    desktop_preview = _is_desktop_preview_tab(tab)
    if desktop_preview:
        win_w, win_h, x, y = _desktop_preview_geometry()
    else:
        default_w, default_h = BROWSER_WINDOW_CONFIG.window_size or (URL_WIN_W, URL_WIN_H)
        x, y = _slot_pos(slot, default_w, default_h)
        win_w, win_h, x, y = _resolve_configured_geometry((URL_WIN_W, URL_WIN_H), (x, y))
    profile = _ensure_profile(slot)

    old = _url_slot_wins.get(slot)
    if old:
        try: old.terminate()
        except Exception: pass
        time.sleep(0.2)
        _url_slot_wins[slot] = None
        _url_slot_modes.pop(slot, None)

    if chrome:
        args = [
            chrome,
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            *chrome_window_args(win_w, win_h, x, y),
            url,
        ]
        # Mac-specific: suppress non-essential background services
        if _IS_MAC:
            args.extend([
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-sync",
                # NOTE: do NOT add --disable-background-networking here —
                # it silently blocks WebSocket connections on Chrome 120+
            ])
        proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        _url_slot_wins[slot] = proc
        _url_slot_modes[slot] = "manual" if not _should_auto_close_tab(tab) else "auto"
    else:
        webbrowser.open_new(url)

def close_all_url_windows(auto=False):
    global _url_slot_wins, _url_slot_modes
    for slot, proc in list(_url_slot_wins.items()):
        if auto and _url_slot_modes.get(slot) == "manual":
            continue
        if proc:
            try: proc.terminate()
            except Exception: pass
        _url_slot_wins.pop(slot, None)
        _url_slot_modes.pop(slot, None)

# ── JARVIS WINDOWS ────────────────────────────────────────────────────────────
_scheduled_actions = {}
_scheduled_actions_lock = threading.Lock()
_scheduler_started = False

def _utc_now():
    return datetime.now(timezone.utc)

def _parse_run_at(value, now=None):
    now = now or _utc_now()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), timezone.utc)
    if not isinstance(value, str) or not value.strip():
        raise ValueError("run_at must be an ISO timestamp or epoch seconds")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=now.tzinfo or timezone.utc)
    return parsed.astimezone(timezone.utc)

def _next_daily_run(trigger, now=None):
    now = now or _utc_now()
    time_text = str(trigger.get("time", "")).strip()
    try:
        hour_text, minute_text = time_text.split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
    except ValueError:
        raise ValueError("daily trigger time must be HH:MM")
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    return candidate

def _next_schedule_time(trigger, now=None):
    now = now or _utc_now()
    if not isinstance(trigger, dict):
        raise ValueError("trigger must be a JSON object")
    trigger_type = str(trigger.get("type", "once")).lower()
    if "delay_seconds" in trigger:
        delay = max(0, float(trigger["delay_seconds"]))
        return now + timedelta(seconds=delay)
    if "run_at" in trigger:
        return _parse_run_at(trigger["run_at"], now)
    if trigger_type in ("daily", "recurring"):
        return _next_daily_run(trigger, now)
    raise ValueError("trigger needs delay_seconds, run_at, or type=daily with time=HH:MM")

def _normalize_scheduled_actions(payload):
    actions = payload.get("actions")
    if actions is None:
        action = payload.get("action")
        if not action:
            raise ValueError("actions or action is required")
        actions = [{"type": action, **payload.get("params", {})}]
    if not isinstance(actions, list) or not actions:
        raise ValueError("actions must be a non-empty list")
    normalized = []
    for item in actions:
        if not isinstance(item, dict):
            raise ValueError("each scheduled action must be an object")
        action_type = str(item.get("type") or item.get("action") or "").strip().lower()
        if not action_type:
            raise ValueError("each action needs type")
        normalized.append({**item, "type": action_type})
    return normalized

def create_scheduled_action(payload, now=None):
    if not isinstance(payload, dict):
        raise ValueError("payload must be a JSON object")
    trigger = payload.get("trigger", {"delay_seconds": payload.get("delay_seconds", 0)})
    scheduled_for = _next_schedule_time(trigger, now)
    item = {
        "id": payload.get("id") or uuid.uuid4().hex[:12],
        "name": str(payload.get("name") or "scheduled action"),
        "trigger": trigger,
        "actions": _normalize_scheduled_actions(payload),
        "status": "scheduled",
        "scheduled_for": scheduled_for.isoformat(),
        "created_at": (now or _utc_now()).isoformat(),
        "last_error": "",
    }
    with _scheduled_actions_lock:
        _scheduled_actions[item["id"]] = item
    print(f"  [schedule] queued {item['id']} for {item['scheduled_for']}")
    return item

def list_scheduled_actions():
    with _scheduled_actions_lock:
        return sorted(_scheduled_actions.values(), key=lambda item: item["scheduled_for"])

def cancel_scheduled_action(action_id):
    with _scheduled_actions_lock:
        item = _scheduled_actions.get(action_id)
        if not item:
            return False
        item["status"] = "cancelled"
        return True

def _execute_scheduled_actions(item):
    global _url_slot
    try:
        for action in item["actions"]:
            action_type = action["type"]
            if action_type in ("wait", "sleep"):
                time.sleep(max(0, float(action.get("seconds", 0))))
            elif action_type in ("open_url", "open_window"):
                url = str(action.get("url", "")).strip()
                if not url:
                    raise ValueError("open_url action needs url")
                slot = _url_slot % 4
                _url_slot = (_url_slot + 1) % 4
                open_url_in_slot(url, slot, action)
            elif action_type == "open_tabs":
                tabs = action.get("tabs") or action.get("urls") or []
                if not isinstance(tabs, list):
                    raise ValueError("open_tabs action needs tabs or urls list")
                close_all_url_windows()
                for index, tab in enumerate(tabs[:4]):
                    url = tab.get("url", tab) if isinstance(tab, dict) else str(tab)
                    open_url_in_slot(url, index % 4, tab)
                    time.sleep(0.4)
            elif action_type == "close_tabs":
                close_all_url_windows(auto=bool(action.get("auto", False)))
            else:
                raise ValueError(f"unsupported scheduled action: {action_type}")
        item["status"] = "completed"
        print(f"  [schedule] completed {item['id']}")
    except Exception as exc:
        item["status"] = "failed"
        item["last_error"] = str(exc)
        print(f"  [schedule] failed {item['id']}: {exc}")
    trigger = item.get("trigger", {})
    if isinstance(trigger, dict) and str(trigger.get("type", "")).lower() in ("daily", "recurring"):
        try:
            item["scheduled_for"] = _next_schedule_time(trigger).isoformat()
            item["status"] = "scheduled"
        except Exception as exc:
            item["status"] = "failed"
            item["last_error"] = str(exc)

def _scheduler_loop():
    while True:
        now = _utc_now()
        due = []
        with _scheduled_actions_lock:
            for item in _scheduled_actions.values():
                if item["status"] != "scheduled":
                    continue
                if _parse_run_at(item["scheduled_for"], now) <= now:
                    item["status"] = "running"
                    due.append(item)
        for item in due:
            threading.Thread(target=_execute_scheduled_actions, args=(item,), daemon=True).start()
        time.sleep(0.25)

def start_scheduler():
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True
    threading.Thread(target=_scheduler_loop, daemon=True, name="scheduler").start()

_visual_proc = None
_web_proc    = None
_browser_client_proc = None

def start_browser_client():
    """Start browserClient.py in the background for browser automation."""
    global _browser_client_proc
    if _browser_client_proc and _browser_client_proc.poll() is None:
        print("  [browser] already running"); return
    if not os.path.exists(BROWSER_CLIENT):
        print("  [browser] ⚠  browserClient.py not found"); return

    try:
        _browser_client_proc = subprocess.Popen([sys.executable, BROWSER_CLIENT, *BROWSER_CLIENT_ARGS], cwd=_DIR)
        print("  [browser] ✅ browserClient.py started")
    except Exception as e:
        print(f"  [browser] ⚠  Failed to start browserClient.py: {e}")

def open_jarvis_visual():
    """Open jarvis_visual.html at the top-center of the screen — the main visible window."""
    global _visual_proc
    if _visual_proc and _visual_proc.poll() is None:
        print("  [visual] already running"); return

    url     = f"http://localhost:{HTTP_PORT}/visual"
    chrome  = find_chrome()
    default_size = (420, 520)
    default_w = BROWSER_WINDOW_CONFIG.window_size[0] if BROWSER_WINDOW_CONFIG.window_size else default_size[0]
    vx, vy = top_center_near_active_window(default_w)
    win_w, win_h, vx, vy = _resolve_configured_geometry(default_size, (vx, vy))
    profile = os.path.join(tempfile.gettempdir(), "jarvis_chrome_visual")
    os.makedirs(profile, exist_ok=True)
    if chrome:
        args = [
            chrome,
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--autoplay-policy=no-user-gesture-required",
            *chrome_window_args(win_w, win_h, vx, vy),
        ]
        if _IS_MAC:
            args.extend([
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-sync",
                # NOTE: do NOT add --disable-background-networking here —
                # it silently blocks WebSocket connections on Chrome 120+
            ])
        _visual_proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  [visual] ✅ opened ({win_w}×{win_h} @ {vx},{vy})")
    else:
        webbrowser.open(url)

def open_jarvis_web_bg():
    """Open jarvis_web.html as a small top-right window — handles WebSocket + audio."""
    global _web_proc
    if _web_proc and _web_proc.poll() is None:
        print("  [web] already running"); return

    url     = f"http://localhost:{HTTP_PORT}/"
    chrome  = find_chrome()
    default_size = (700, 420)
    default_w = BROWSER_WINDOW_CONFIG.window_size[0] if BROWSER_WINDOW_CONFIG.window_size else default_size[0]
    wx, wy = top_right_near_active_window(default_w)
    win_w, win_h, wx, wy = _resolve_configured_geometry(default_size, (wx, wy))

    profile = os.path.join(tempfile.gettempdir(), "jarvis_chrome_web")
    os.makedirs(profile, exist_ok=True)

    if chrome:
        args = [
            chrome,
            f"--app={url}",
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--autoplay-policy=no-user-gesture-required",
            *chrome_window_args(win_w, win_h, wx, wy),
        ]
        if _IS_MAC:
            args.extend([
                "--disable-client-side-phishing-detection",
                "--disable-component-update",
                "--disable-sync",
                # NOTE: do NOT add --disable-background-networking here —
                # it silently blocks WebSocket connections on Chrome 120+
            ])
        _web_proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"  [web] opened ({win_w}x{win_h} @ {wx},{wy}) - click window once to activate audio")
    else:
        webbrowser.open(url)

# ── HTTP SERVER ───────────────────────────────────────────────────────────────
_http_started = False

def _kill_port(port):
    """Kill any process already bound to port (Mac/Linux only)."""
    try:
        out = subprocess.check_output(
            ["lsof", "-ti", f"tcp:{port}"], stderr=subprocess.DEVNULL
        ).decode().strip()
        for pid in out.splitlines():
            try:
                subprocess.run(["kill", "-9", pid], check=False)
                print(f"  [http] Killed stale process {pid} on port {port}")
            except Exception:
                pass
        time.sleep(0.4)
    except Exception:
        pass

def start_http_server():
    global _http_started
    if _http_started:
        return
    _http_started = True

    _kill_port(HTTP_PORT)
    start_scheduler()

    from http.server import HTTPServer, BaseHTTPRequestHandler

    class H(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin",  "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-store")

        def do_OPTIONS(self):
            self.send_response(200)
            self._cors()
            self.end_headers()

        def _serve_file(self, path, ctype="text/html; charset=utf-8"):
            try:
                with open(path, "rb") as f: data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            except FileNotFoundError:
                self.send_response(404); self.end_headers()
                self.wfile.write(os.path.basename(path).encode() + b" not found")

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self._serve_file(WEB_HTML)
            elif self.path in ("/visual", "/visual.html"):
                self._serve_file(VISUAL_HTML)
            elif self.path == "/config.json":
                self._serve_file(os.path.join(_DIR, "config.json"), "application/json")
            elif self.path == "/state":
                with _http_state_lock:
                    data = json.dumps(_http_state).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            elif self.path == "/scheduled_actions":
                data = json.dumps({"ok": True, "items": list_scheduled_actions()}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404); self.end_headers()

        def do_POST(self):
            global _url_slot
            length = int(self.headers.get("Content-Length", 0))
            body   = self.rfile.read(length) if length else b""

            if self.path == "/state":
                try:
                    payload = json.loads(body) if body else {}
                    with _http_state_lock:
                        _http_state.update(payload)
                except Exception:
                    pass
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            elif self.path == "/open_tabs":
                try:
                    tabs = json.loads(body) if body else []
                    tabs = tabs[:4]
                    def _open_batch():
                        global _url_slot
                        close_all_url_windows()
                        for i, tab in enumerate(tabs):
                            url  = tab.get("url", tab) if isinstance(tab, dict) else str(tab)
                            slot = i % 4
                            open_url_in_slot(url, slot, tab)
                            time.sleep(0.4)  # wider stagger reduces overlapping CPU spikes
                        _url_slot = len(tabs) % 4
                        print(f"  [tab] ✅ Opened {len(tabs)} tab(s) in grid slots")
                    threading.Thread(target=_open_batch, daemon=True).start()
                except Exception as e:
                    print(f"  [tab] ⚠  open_tabs error: {e}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            elif self.path == "/open_window":
                try:
                    tab = json.loads(body) if body else {}
                    url = tab.get("url", tab) if isinstance(tab, dict) else str(tab)
                    if url:
                        slot = _url_slot % 4
                        _url_slot = (_url_slot + 1) % 4
                        # Run in background so the HTTP handler returns immediately
                        # and doesn't block the audio pipeline while Chrome spawns.
                        threading.Thread(
                            target=open_url_in_slot, args=(url, slot, tab), daemon=True
                        ).start()
                        print(f"  [tab] ✅ Opened one tab in grid slot {slot}")
                except Exception as e:
                    print(f"  [tab] ⚠  open_window error: {e}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            elif self.path == "/close_tabs":
                try:
                    payload = json.loads(body) if body else {}
                except Exception:
                    payload = {}
                auto = bool(payload.get("auto")) if isinstance(payload, dict) else False
                label = "Auto-closed" if auto else "All slot windows closed"
                threading.Thread(
                    target=close_all_url_windows, args=(auto,), daemon=True
                ).start()
                print(f"  [tab] ✅ {label}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            elif self.path == "/schedule_action":
                try:
                    payload = json.loads(body) if body else {}
                    item = create_scheduled_action(payload)
                    self.send_response(201)
                    self.send_header("Content-Type", "application/json")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": True, "item": item}).encode())
                except Exception as e:
                    print(f"  [schedule] schedule_action error: {e}")
            elif self.path == "/file_action":
                try:
                    payload = json.loads(body) if body else {}
                    result = handle_file_action_payload(payload)
                    print(f"  [file] ok {result['action']} -> {result['path']}")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors()
                    self.end_headers()
                    response = {"ok": True, **result}
                    self.wfile.write(json.dumps(response).encode())
                except (NativeFileActionError, json.JSONDecodeError) as e:
                    print(f"  [file] action error: {e}")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

            elif self.path == "/cancel_scheduled_action":
                try:
                    payload = json.loads(body) if body else {}
                    cancelled = cancel_scheduled_action(str(payload.get("id", "")))
                    self.send_response(200 if cancelled else 404)
                    self.send_header("Content-Type", "application/json")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": cancelled}).encode())
                except Exception as e:
                    self.send_response(400)
                except Exception as e:
                    print(f"  [file] unexpected error: {e}")
                    self.send_response(500)
                    self.send_header("Content-Type", "application/json")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())

            elif self.path == "/config":
                try:
                    payload = json.loads(body) if body else {}
                    token = payload.get("token", "").strip()
                    if not token:
                        raise ValueError("token is empty")
                    cfg_path = os.path.join(_DIR, "config.json")
                    try:
                        with open(cfg_path, "r") as f:
                            cfg = json.load(f)
                    except Exception:
                        cfg = {}
                    cfg["TOKEN"] = token
                    with open(cfg_path, "w") as f:
                        json.dump(cfg, f, indent=2)
                    print(f"  [config] ✅ API key updated")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                except Exception as e:
                    print(f"  [config] ⚠  update error: {e}")
                    self.send_response(400)
                    self.send_header("Content-Type", "application/json")
                    self._cors()
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": str(e)}).encode())

            else:
                self.send_response(404); self.end_headers()

        def log_message(self, *_): pass   # silence access logs

    import socket as _socket
    class ReuseHTTPServer(HTTPServer):
        allow_reuse_address = True
        def server_bind(self):
            self.socket.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
            super().server_bind()

    srv = ReuseHTTPServer(("localhost", HTTP_PORT), H)
    threading.Thread(target=srv.serve_forever, daemon=True, name="http-server").start()
    print(f"  [http] Server listening on http://localhost:{HTTP_PORT}/")

# ── APP HELPERS (unchanged) ───────────────────────────────────────────────────
def resolve_path(path):
    user = os.environ.get("USERNAME", os.environ.get("USER", ""))
    return path.replace("{user}", user)

def find_running_pid(exe_name):
    try:
        out = subprocess.check_output(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
            shell=True, stderr=subprocess.DEVNULL
        ).decode(errors="ignore")
        for line in out.strip().splitlines():
            parts = line.strip('"').split('","')
            if len(parts) >= 2 and parts[0].lower() == exe_name.lower():
                return int(parts[1])
    except Exception:
        pass
    return None

def focus_window_by_exe(exe_name, rect):
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    found = []
    def enum_cb(hwnd, _):
        win_pid = ctypes.wintypes.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
        try:
            buf = ctypes.create_unicode_buffer(260)
            h = ctypes.windll.kernel32.OpenProcess(0x0400 | 0x0010, False, win_pid.value)
            ctypes.windll.psapi.GetModuleFileNameExW(h, None, buf, 260)
            ctypes.windll.kernel32.CloseHandle(h)
            if exe_name.lower() in buf.value.lower():
                if user32.GetWindowTextLengthW(hwnd) > 0:
                    found.append(hwnd)
        except Exception:
            pass
        return True
    user32.EnumWindows(EnumWindowsProc(enum_cb), 0)
    if found:
        hwnd = found[0]
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        if rect:
            user32.MoveWindow(hwnd, rect["x"], rect["y"], rect["w"], rect["h"], True)
        print(f"  [win] ✅ Focused {exe_name}")
        return True
    return False

def resize_window_by_pid(pid, rect, retries=20, interval=0.5):
    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
    def find_hwnd():
        found = []
        def cb(hwnd, _):
            if not user32.IsWindowVisible(hwnd): return True
            if user32.GetWindowTextLengthW(hwnd) == 0: return True
            win_pid = ctypes.wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(win_pid))
            if win_pid.value == pid:
                found.append(hwnd); return False
            buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, buf, 256)
            if 'spotify' in buf.value.lower():
                found.append(hwnd); return False
            return True
        user32.EnumWindows(EnumWindowsProc(cb), 0)
        return found[0] if found else None
    for _ in range(retries):
        time.sleep(interval)
        hwnd = find_hwnd()
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            time.sleep(0.2)
            user32.MoveWindow(hwnd, rect["x"], rect["y"], rect["w"], rect["h"], True)
            user32.SetForegroundWindow(hwnd)
            print(f"  [win] ✅ Resized to {rect['w']}x{rect['h']}")
            return
    print(f"  [win] ⚠  Could not find window for pid {pid}")

def open_app(name):
    if _IS_MAC:
        mac_names = {
            "vs code": "Visual Studio Code", "vscode": "Visual Studio Code",
            "code": "Visual Studio Code", "visual studio code": "Visual Studio Code",
            "spotify": "Spotify", "chrome": "Google Chrome", "firefox": "Firefox",
        }
        app = mac_names.get(name)
        if app:
            try:
                subprocess.Popen(["open", "-a", app])
                print(f"  [app] ✅ Launched {name}")
                return True
            except Exception as e:
                print(f"  [app] ⚠  Mac open failed: {e}")
        return False

    paths    = APPS.get(name, [])
    rect     = SMALL_WIN.get(name)
    exe_name = PROCESS_NAMES.get(name)
    if exe_name:
        pid = find_running_pid(exe_name)
        if pid:
            print(f"  [app] ♻  {name} already running — focusing...")
            if focus_window_by_exe(exe_name, rect):
                return True
    for raw in paths:
        p = resolve_path(raw)
        try:
            proc = None
            if os.path.exists(p):
                proc = subprocess.Popen([p], shell=False)
                print(f"  [app] ✅ Launched {name} → {p}")
            elif os.sep not in p and not p.endswith('.exe'):
                proc = subprocess.Popen([p], shell=True)
                print(f"  [app] ✅ Launched {name} via shell")
            else:
                print(f"  [app] ⚠  Not found: {p}"); continue
            if proc and rect:
                threading.Thread(target=resize_window_by_pid, args=(proc.pid, rect), daemon=True).start()
            return True
        except Exception as e:
            print(f"  [app] ⚠  Failed: {e}")
    print(f"  [app] ✗ Could not open: {name}")
    return False

# ── STATE ─────────────────────────────────────────────────────────────────────
last_launch  = 0.0
lock         = threading.Lock()
stop_capture = threading.Event()

def full_launch(source):
    global last_launch
    with lock:
        now = time.time()
        if now - last_launch < LAUNCH_COOLDOWN:
            return
        last_launch = now

    stop_capture.set()
    print(f"\n  🚀  [{source}] JARVIS ACTIVATED\n")

    def sequence():
        print("  [1/3] Browser automation client...")
        start_browser_client()
        print("  [2/3] JARVIS Visual window...")
        open_jarvis_visual()
        print("  [3/3] JARVIS Web backend (minimized)...")
        open_jarvis_web_bg()
        print("  ✅  Done.\n")
    threading.Thread(target=sequence, daemon=True).start()

def handle_command(text):
    text = text.lower().strip()
    print(f"  [cmd] Heard: \"{text}\"")
    if any(w in text for w in WAKE_WORDS) and "open" not in text:
        print("  [cmd] ✅ Wake word → full launch")
        full_launch("wake word")
        return
    if "open" in text:
        for app_name in APPS:
            if app_name in text:
                print(f"  [cmd] ✅ open {app_name}")
                threading.Thread(target=open_app, args=(app_name,), daemon=True).start()
                return
        if any(w in text for w in ["jarvis", "weestream", "stream"]):
            full_launch("voice command")
            return
        print(f"  [cmd] ⚠  Unknown app: \"{text}\"")

# ── VOICE LISTENER ────────────────────────────────────────────────────────────
def voice_listener():
    try:
        import speech_recognition as sr
    except ImportError:
        print("  [voice] pip install speechrecognition"); return

    recognizer = sr.Recognizer()
    recognizer.energy_threshold         = 400
    recognizer.dynamic_energy_threshold = False
    recognizer.pause_threshold          = 1.2
    recognizer.non_speaking_duration    = 0.8
    recognizer.phrase_threshold         = 0.3
    print("  [voice] 🎙  Listening for: hey jarvis / jarvis...")

    while True:
        if stop_capture.is_set():
            print("  [voice] ⏸  Mic paused. Press Enter to resume...")
            input()
            stop_capture.clear()
            print("  [voice] ▶  Resumed.\n")
        try:
            mic = sr.Microphone(sample_rate=16000)
            with mic as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
            with mic as source2:
                audio = recognizer.listen(source2, timeout=8, phrase_time_limit=6)
            try:
                text = recognizer.recognize_google(audio).lower()
                handle_command(text)
            except sr.UnknownValueError:
                pass
        except sr.WaitTimeoutError:
            pass
        except sr.RequestError as e:
            print(f"  [voice] Network error: {e} — retry in 3s"); time.sleep(3)
        except Exception as e:
            print(f"  [voice] Error: {e}"); time.sleep(1)

# ── API KEY SETUP (terminal prompt) ──────────────────────────────────────────
_PLACEHOLDER_TOKENS = {"your-token-here", "", "your-api-key-here", "q", "quit", "exit"}

def _is_valid_token(token):
    token = token.strip() if token else ""
    return len(token) >= 20 and token.lower() not in _PLACEHOLDER_TOKENS

def _load_token():
    cfg_path = os.path.join(_DIR, "config.json")
    try:
        with open(cfg_path, "r") as f:
            return json.load(f).get("TOKEN", "").strip()
    except Exception:
        return ""

def _save_token(token):
    cfg_path = os.path.join(_DIR, "config.json")
    try:
        with open(cfg_path, "r") as f:
            cfg = json.load(f)
    except Exception:
        cfg = {}
    cfg["TOKEN"] = token
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)

def _prompt(text):
    print(text, end="", flush=True)
    return input().strip()

def _save_and_continue(token):
    _save_token(token.strip())
    print("  ✅  API key saved to config.json — continuing...\n", flush=True)

def _open_url(url):
    try:
        chrome = find_chrome()
        if chrome:
            subprocess.Popen(
                [chrome, "--new-tab", url],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        else:
            webbrowser.open(url)
    except Exception:
        webbrowser.open(url)

def check_api_key():
    """If token is missing or placeholder, run interactive setup in the terminal."""
    token = _load_token()
    if _is_valid_token(token):
        return  # token looks valid, continue normally

    print("""
  ╔══════════════════════════════════════════╗
  ║        API KEY NOT FOUND / INVALID       ║
  ╚══════════════════════════════════════════╝

  To use J.A.R.V.I.S you need a free Toingg API key.

    [1]  Open signup page  →  prepodapp.toingg.com
    [2]  Open API-key page →  prepodapp.toingg.com/api-keys
    [3]  Paste API key     →  save and continue
    [Q]  Quit

  Type your choice, then press Enter.
""", flush=True)
    while True:
        try:
            choice = _prompt("  Enter choice, or paste API key [1/2/3/Q]: ")
        except (EOFError, KeyboardInterrupt):
            print("\n  Stopped.")
            sys.exit(0)

        choice_upper = choice.upper()
        choice_lower = choice.lower()

        if choice_upper == "1":
            _open_url("https://prepodapp.toingg.com")
            print("  ✅  Signup page opened in browser.\n", flush=True)

        elif choice_upper == "2":
            _open_url("https://prepodapp.toingg.com/api-keys")
            print("  ✅  API-key page opened in browser.\n", flush=True)

        elif choice_upper == "3":
            try:
                token = _prompt("  Paste API key, or Q to quit: ")
            except (EOFError, KeyboardInterrupt):
                print("\n  Stopped.")
                sys.exit(0)
            if token.lower() in {"q", "quit", "exit"}:
                print("  Stopped.")
                sys.exit(0)
            if not _is_valid_token(token):
                print("  ⚠   No valid key entered. Try again.\n", flush=True)
                continue
            _save_and_continue(token)
            break

        elif choice_upper == "Q" or choice_lower in {"quit", "exit"}:
            print("  Stopped.")
            sys.exit(0)

        elif _is_valid_token(choice):
            _save_and_continue(choice)
            break

        else:
            print("  ⚠   Invalid choice. Enter 1, 2, 3, Q, or paste your API key.\n", flush=True)

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    configure_browser_windows(sys.argv[1:])
    print("""
  ╔══════════════════════════════════════════╗
  ║   W E E S T R E A M  //  J A R V I S    ║
  ║         Web Launcher  v2.0               ║
  ╚══════════════════════════════════════════╝

  Wake trigger  →  JARVIS Web Terminal (Chrome)
  "Hey Jarvis"  →  full launch
  "Open Spotify / VS Code / ..."

  Ctrl+C to stop.
""")

    check_api_key()

    print(f"  📄  Web HTML : {WEB_HTML}")
    print(f"  🌐  Server   : http://localhost:{HTTP_PORT}/\n")

    start_http_server()

    threads = [
        threading.Thread(target=voice_listener, daemon=True, name="voice"),
    ]
    for t in threads:
        t.start()

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n  Stopped.")

if __name__ == "__main__":
    main()
