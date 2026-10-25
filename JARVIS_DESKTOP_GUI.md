# Cross-Platform Desktop GUI for JARVIS Terminal Controls

This repository includes a cross-platform desktop GUI control center for **Windows**, **macOS**, and **Linux** in two flavors:

1. **Zero-Dependency Python Controller (`jarvis_desktop_gui.py`)**:
   - Runs out-of-the-box with standard Python (`tkinter` + headless `JarvisDesktopController` API).
2. **Native Fyne v2 Desktop App (`desktop_gui/fyne/main.go`)**:
   - Hardware-accelerated Go + Fyne v2 desktop application.

---

## Features & Supported Controls

- **Service Lifecycle Management:** Start, stop, and restart `jarvis_launcher.py` and `browserClient.py` with live stdout/stderr log streaming.
- **Backend Provider Switcher:** Select between `toingg` and `pipecat_gemini`.
- **API Keys & Model Settings:** Configure `TOKEN` (Toingg API key), `GEMINI_API_KEY`, `MODEL`, `CAMP_ID`, and `WS_URL`.
- **Browser Automation Controls:** Configure headless mode, persistent profile directory, preferred monitor (`active`, `primary`, `0`, `1`), window size (`860x580`, `1280x800`), and window position (`grid`, `center`, `top-left`, etc.).
- **Scheduled Events:** View, queue (`/schedule_action`), and cancel (`/cancel_scheduled_action`) scheduled automation tasks.
- **Native File & Output Actions:** Open generated files, reveal files in the native OS file manager, or open output directories (`open_directory`, `open_file`, `reveal_file`).

---

## Quick Start

### Option A — Python Desktop GUI
```bash
python jarvis_desktop_gui.py
```

### Option B — Fyne v2 Desktop App (Go)
```bash
cd desktop_gui/fyne
go mod tidy
go run .
```
