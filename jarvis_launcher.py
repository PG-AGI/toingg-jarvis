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

import os, sys, time, threading, subprocess, tempfile, json, webbrowser
import ctypes, ctypes.wintypes
import platform as _plat

# ── CONFIG ────────────────────────────────────────────────────────────────────
_DIR        = os.path.dirname(os.path.abspath(__file__))
WEB_HTML    = os.path.join(_DIR, "jarvis_web.html")
VISUAL_HTML = os.path.join(_DIR, "jarvis_visual.html")
WAKE_WORDS  = ["hey jarvis", "jarvis", "hey jervis", "hey davis"]
LAUNCH_COOLDOWN = 4.0
HTTP_PORT   = 8766

# ── shared state (jarvis_web.html POSTs here; jarvis_visual.html polls here) ─
_http_state      = {"state": "initializing", "text": "", "status": "INITIALIZING..."}
_http_state_lock = threading.Lock()

# ── SLOT WINDOW CONFIG (mirrors jarvis_terminal.py) ───────────────────────────
URL_WIN_W  = 860
URL_WIN_H  = 580
_PADDING   = 20
_url_slot      = 0
_url_slot_wins = {}
_slot_profiles = {}

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

# ── SLOT MANAGER (mirrors jarvis_terminal.py exactly) ────────────────────────
def _ensure_profile(slot):
    if slot not in _slot_profiles:
        d = os.path.join(tempfile.gettempdir(), f"jarvis_chrome_slot_{slot}")
        os.makedirs(d, exist_ok=True)
        _slot_profiles[slot] = d
    return _slot_profiles[slot]

def _slot_pos(slot):
    """
    2×2 grid inset from screen edges:
      slot 0 = top-left    slot 1 = top-right
      slot 2 = bottom-left slot 3 = bottom-right
    """
    sw, sh = get_screen_size()
    p   = _PADDING
    col = slot % 2
    row = slot // 2
    x   = p + col * (URL_WIN_W + p)
    y   = p + row * (URL_WIN_H + p)
    x   = min(x, sw - URL_WIN_W - p)
    y   = min(y, sh - URL_WIN_H - p)
    return max(0, x), max(0, y)

def open_url_in_slot(url, slot):
    """Open url in a specific grid slot; kill previous window in that slot first."""
    global _url_slot_wins
    chrome  = find_chrome()
    x, y    = _slot_pos(slot)
    profile = _ensure_profile(slot)

    old = _url_slot_wins.get(slot)
    if old:
        try: old.terminate()
        except Exception: pass
        time.sleep(0.2)
        _url_slot_wins[slot] = None

    if chrome:
        args = [
            chrome,
            f"--user-data-dir={profile}",
            "--no-first-run",
            "--no-default-browser-check",
            f"--window-size={URL_WIN_W},{URL_WIN_H}",
            f"--window-position={x},{y}",
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
    else:
        webbrowser.open_new(url)

def close_all_url_windows():
    global _url_slot_wins
    for proc in _url_slot_wins.values():
        if proc:
            try: proc.terminate()
            except Exception: pass
    _url_slot_wins = {}

# ── JARVIS WINDOWS ────────────────────────────────────────────────────────────
_visual_proc = None
_web_proc    = None

def open_jarvis_visual():
    """Open jarvis_visual.html centered on screen — the main visible window."""
    global _visual_proc
    if _visual_proc and _visual_proc.poll() is None:
        print("  [visual] already running"); return

    url     = f"http://localhost:{HTTP_PORT}/visual"
    chrome  = find_chrome()
    sw, sh  = get_screen_size()
    win_w, win_h = 420, 520
    vx = max(0, (sw - win_w) // 2)
    vy = max(0, (sh - win_h) // 2)
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
            f"--window-size={win_w},{win_h}",
            f"--window-position={vx},{vy}",
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
    """Open jarvis_web.html as a small visible window — handles WebSocket + audio."""
    global _web_proc
    if _web_proc and _web_proc.poll() is None:
        print("  [web] already running"); return

    url     = f"http://localhost:{HTTP_PORT}/"
    chrome  = find_chrome()
    sw, sh  = get_screen_size()
    win_w, win_h = 700, 420
    wx = max(0, sw - win_w - 20)
    wy = max(0, sh - win_h - 60)

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
            f"--window-size={win_w},{win_h}",
            f"--window-position={wx},{wy}",
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
        print(f"  [web] ✅ opened ({win_w}×{win_h} @ {wx},{wy}) — click window once to activate audio")
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
            else:
                self.send_response(404); self.end_headers()

        def do_POST(self):
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
                    close_all_url_windows()
                    global _url_slot
                    threads = []
                    for i, tab in enumerate(tabs[:4]):
                        url   = tab.get("url", tab) if isinstance(tab, dict) else str(tab)
                        slot  = i % 4
                        t     = threading.Thread(target=open_url_in_slot, args=(url, slot), daemon=True)
                        threads.append(t)
                        t.start()
                    _url_slot = len(tabs) % 4
                    for t in threads: t.join(timeout=0)  # fire-and-forget
                    print(f"  [tab] ✅ Opened {len(tabs[:4])} tab(s) in grid slots")
                except Exception as e:
                    print(f"  [tab] ⚠  open_tabs error: {e}")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

            elif self.path == "/close_tabs":
                close_all_url_windows()
                print("  [tab] ✅ All slot windows closed")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self._cors()
                self.end_headers()
                self.wfile.write(b'{"ok":true}')

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
        print("  [1/2] JARVIS Visual window...")
        open_jarvis_visual()
        print("  [2/2] JARVIS Web backend (minimized)...")
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
_PLACEHOLDER_TOKENS = {"your-token-here", "", "your-api-key-here"}

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
    if token and token not in _PLACEHOLDER_TOKENS:
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
""")
    while True:
        try:
            choice = input("  Enter choice [1/2/3/Q]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            print("\n  Stopped.")
            sys.exit(0)

        if choice == "1":
            _open_url("https://prepodapp.toingg.com")
            print("  ✅  Signup page opened in browser.\n")

        elif choice == "2":
            _open_url("https://prepodapp.toingg.com/api-keys")
            print("  ✅  API-key page opened in browser.\n")

        elif choice == "3":
            try:
                token = input("  Paste API key: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  Stopped.")
                sys.exit(0)
            if not token:
                print("  ⚠   No key entered. Try again.\n")
                continue
            _save_token(token)
            print("  ✅  API key saved to config.json — continuing...\n")
            break

        elif choice == "Q":
            print("  Stopped.")
            sys.exit(0)

        else:
            print("  ⚠   Invalid choice. Enter 1, 2, 3 or Q.\n")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
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
