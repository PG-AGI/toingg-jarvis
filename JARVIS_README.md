# J.A.R.V.I.S — Weestream Intelligence Terminal

A voice-driven AI terminal that connects to your JARVIS campaign, displays a live spectrum UI, opens news/weather/content tabs on command, and speaks back through your speakers.

---

## Files — put all of these in one folder

| File | What it does |
|---|---|
| `jarvis_terminal.py` | Main script — terminal UI, mic, audio, WebSocket |
| `jarvis_visual.html` | JARVIS orb animation (opened automatically) |
| `JARVIS.command` | **Mac** double-click launcher |
| `JARVIS.bat` | **Windows** double-click launcher |

That's it. All 4 files in the same folder.

---

## Run on Mac

### First time setup (do this once)

Open **Terminal**, drag the JARVIS folder into Terminal to get the path, then run:

```bash
bash setup_mac.sh
```

That's it — fixes all permissions in one shot. Then double-click `JARVIS.command` anytime.

---

**Getting "access privileges" or "can't be opened" error?**

Open Terminal, `cd` into the JARVIS folder and run:
```bash
chmod +x JARVIS.command && xattr -d com.apple.quarantine JARVIS.command
```
Then double-click `JARVIS.command` again.

---

**Every time after setup:**
Just double-click `JARVIS.command` — installs everything automatically.

**Mic permission:** Mac will ask for microphone access on first run — allow it in System Settings → Privacy & Security → Microphone.

---

## Run on Windows

**First time only:**
- Install Python from [python.org](https://www.python.org/downloads/) — check **"Add Python to PATH"** during install
- If pyaudio fails to install automatically, run in Command Prompt:
  ```
  pip install pipwin
  pipwin install pyaudio
  ```

**Every time:**
Just double-click `JARVIS.bat`

---

## Requirements (installed automatically by the launchers)

| Package | Purpose |
|---|---|
| `pyaudio` | Mic input + audio playback |
| `numpy` | Audio signal processing |
| `websocket-client` | WebSocket connection to JARVIS backend |
| `rich` | Terminal UI rendering |

**Mac only (system level):**
- `portaudio` — installed via Homebrew by `JARVIS.command`

---

## Config (inside jarvis_terminal.py)

If you need to change the campaign or token, open `jarvis_terminal.py` and edit lines 22–24:

```python
WS_URL  = "wss://prepodapi.toingg.com/api/v3/media/streaming"
TOKEN   = "your-token-here"
CAMP_ID = "your-campaign-id-here"
```

---

## What it does

- Connects to your JARVIS AI campaign over WebSocket
- Opens a live terminal UI with spectrum visualizer
- Press **Enter** to speak — JARVIS listens and responds via audio
- When JARVIS fetches news/weather/war updates, browser tabs open automatically in a 2×2 grid
- JARVIS can open specific URLs, scrape article details, and close tabs on command
- Press **Ctrl+C** to stop

---

## Troubleshooting

**"No module named pyaudio" on Mac:**
```bash
brew install portaudio
pip install pyaudio
```

**Mic not working:**
- Mac: System Settings → Privacy & Security → Microphone → enable Terminal
- Windows: Settings → Privacy → Microphone → enable for apps

**Chrome tabs not positioning correctly:**
- Make sure Google Chrome is installed
- The script opens independent Chrome instances per tab slot using separate profiles stored in your system temp folder (`/tmp/jarvis_chrome_slot_*` on Mac, `%TEMP%\jarvis_chrome_slot_*` on Windows)

**Audio distortion / no sound:**
- Check your default output device is set correctly in system sound settings
