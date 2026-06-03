<div align="center">

<!-- BANNER -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:00e5ff,100:1565c0&height=200&section=header&text=J.A.R.V.I.S&fontSize=80&fontColor=ffffff&fontAlignY=38&desc=AI%20Voice%20Terminal%20%E2%80%94%20Powered%20by%20Toingg&descAlignY=60&descSize=18&descColor=a0e4f1" width="100%"/>

<!-- BADGES -->
<p align="center">
  <a href="https://github.com/PG-AGI/toingg-jarvis/stargazers">
    <img src="https://img.shields.io/github/stars/PG-AGI/toingg-jarvis?style=for-the-badge&logo=starship&color=00e5ff&labelColor=000d1a" alt="Stars"/>
  </a>
  <a href="https://github.com/PG-AGI/toingg-jarvis/forks">
    <img src="https://img.shields.io/github/forks/PG-AGI/toingg-jarvis?style=for-the-badge&logo=git&color=1565c0&labelColor=000d1a" alt="Forks"/>
  </a>
  <a href="https://github.com/PG-AGI/toingg-jarvis/issues">
    <img src="https://img.shields.io/github/issues/PG-AGI/toingg-jarvis?style=for-the-badge&logo=github&color=ff1744&labelColor=000d1a" alt="Issues"/>
  </a>
  <a href="https://github.com/PG-AGI/toingg-jarvis/blob/main/LICENSE">
    <img src="https://img.shields.io/badge/License-MIT-00e676?style=for-the-badge&labelColor=000d1a" alt="License"/>
  </a>
  <img src="https://img.shields.io/badge/Python-3.8+-ffd600?style=for-the-badge&logo=python&logoColor=ffd600&labelColor=000d1a" alt="Python"/>
  <img src="https://img.shields.io/badge/Platform-Win%20%7C%20Mac%20%7C%20Linux-00e5ff?style=for-the-badge&labelColor=000d1a" alt="Platform"/>
</p>

<!-- STAR CALL TO ACTION -->
<a href="https://github.com/PG-AGI/toingg-jarvis">
  <img src="https://img.shields.io/badge/⭐%20Star%20this%20repo%20if%20you%20find%20it%20useful!-FFD600?style=for-the-badge&labelColor=000d1a&color=ffd600" alt="Star CTA"/>
</a>

<br/><br/>

---

## 🎬 Preview

<a href="https://x.com/vivekjyotibhow1/status/2054589428363120765?s=46">
  <img src="https://img.shields.io/badge/▶%20Watch%20Preview%20on%20𝕏-000000?style=for-the-badge&logo=x&logoColor=white" alt="Watch Preview on X"/>
</a>

<br/><br/>

> 👆 Click to watch the live preview on X — JARVIS in action: voice activation, animated orb, Toingg AI responses, and browser automation.

---

## 🐦 Share on X

<a href="https://x.com/vivekjyotibhow1/status/2054589428363120765?s=46">
  <img src="https://img.shields.io/badge/View%20%26%20Repost%20on%20𝕏-000000?style=for-the-badge&logo=x&logoColor=white" alt="Repost on X"/>
</a>

> 💬 *Enjoying JARVIS? Repost the preview — it helps the community grow!*

</div>

---

## 📖 Table of Contents

- [🔍 Overview](#-overview)
- [🎯 Target Audience](#-target-audience)
- [✨ Features](#-features)
- [📋 Prerequisites](#-prerequisites)
- [🚀 Quick Start](#-quick-start)
- [🛠️ Installation](#️-installation)
- [⚙️ Environment Setup](#️-environment-setup)
- [💻 Running JARVIS](#-running-jarvis)
  - [Windows](#windows)
  - [macOS](#macos)
  - [Linux](#linux)
- [🎮 Usage](#-usage)
- [📄 Data Requirements](#-data-requirements)
- [🔧 Configuration](#-configuration)
- [🗂️ Project Structure](#️-project-structure)
- [🧠 Methodology](#-methodology)
- [⚡ Performance](#-performance)
- [🧪 Testing](#-testing)
- [🔧 Troubleshooting](#-troubleshooting)
- [📅 Changelog](#-changelog)
- [🤝 Contributing](#-contributing)
- [📜 License](#-license)
- [📚 Citation](#-citation)
- [📬 Contact](#-contact)
- [⭐ Star History](#-star-history)

---

## 🔍 Overview

**J.A.R.V.I.S** (Just A Rather Very Intelligent System) is a free, open-source AI voice terminal that brings natural spoken interaction to your desktop. Say **"Hey Jarvis"** and a real-time conversation begins — your voice streams to the [Toingg](https://toingg.com) AI backend via WebSocket, the AI responds in speech, and supporting browser tabs open automatically in a tidy 2×2 Chrome grid.

The system is built from three cooperating layers:

1. **Wake layer** (`jarvis_launcher.py`) — always-on microphone listener that detects wake words and voice commands, manages a local HTTP server, and launches desktop applications on demand.
2. **Web layer** (`jarvis_web.html`) — a terminal-style browser UI that handles full-duplex audio (microphone capture + speaker playback) using the Web Audio API and communicates with Toingg over WebSocket.
3. **Browser automation layer** (`browserClient.py`) — a Playwright-powered client that receives browser commands from the AI backend and executes them in a real Chrome instance with stealth anti-bot patches applied.

All three layers run simultaneously and communicate over `localhost:8766`.

---

## 🎯 Target Audience

| User | Why JARVIS fits |
|------|----------------|
| **Developers & makers** | Self-host a local AI voice assistant — no subscription, fully transparent code |
| **Productivity enthusiasts** | Launch apps, open URLs, and control your desktop entirely by voice |
| **AI / voice-UI researchers** | A working reference implementation of real-time WebSocket audio streaming + browser automation |
| **Toingg platform users** | The official showcase for Toingg's streaming voice API |

---

## ✨ Features

<table>
<tr>
<td width="50%">

**🎙️ Voice Interaction**
- Wake-word activation — just say **"Hey Jarvis"**
- Real-time WebSocket streaming to Toingg AI
- Barge-in support while AI is speaking
- SpeechRecognition + Web Speech API

</td>
<td width="50%">

**🖥️ Visual Interface**
- Animated orb with live frequency spectrum
- Colour-reactive to listening / speaking states
- Boot sequence with radar scan animation
- Terminal UI with scan-beam visualizer

</td>
</tr>
<tr>
<td width="50%">

**🌐 Browser Automation**
- Opens URLs in a precise 2×2 Chrome grid
- Playwright-powered browser client with stealth patches
- Automatic tab management (open + close)
- Cross-platform Chrome / Chromium / Edge support

</td>
<td width="50%">

**🚀 App Launcher**
- Launch Spotify, VS Code, Chrome & more by voice
- Smart window focus if app is already running
- Custom window size + positioning per app
- Platform-aware paths (Windows / macOS / Linux)

</td>
</tr>
</table>

---

## 📋 Prerequisites

### Knowledge
- Basic comfort with a terminal / command prompt
- No programming knowledge required to *use* JARVIS; Python familiarity helpful for customisation

### Hardware
- **Microphone** — any USB or built-in mic; a headset gives the best results
- **Speakers or headphones** — required for AI audio playback
- **Internet connection** — needed for Toingg API and Google Speech Recognition

### System compatibility

| OS | Minimum version | Notes |
|----|----------------|-------|
| Windows | 10 (64-bit) | Windows 11 recommended |
| macOS | 10.15 Catalina | M1/M2 fully supported |
| Linux | Ubuntu 20.04 / Fedora 34 | Requires `portaudio19-dev` |

### Software
- **Python 3.8+** (`python --version` to check)
- **Google Chrome**, Chromium, or Microsoft Edge
- **Toingg account** — free, [sign up here](https://prepodapp.toingg.com)

---

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/PG-AGI/toingg-jarvis.git
cd toingg-jarvis

# 2. Add your Toingg API key
cp config.example.json config.json
# Edit config.json and paste your token

# 3. Launch
python3 jarvis_launcher.py
# Then say: "Hey Jarvis"
```

> 💡 No API key yet? The launcher will walk you through getting one interactively.

---

## 🛠️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/PG-AGI/toingg-jarvis.git
cd toingg-jarvis
```

### 2. Install Python dependencies

```bash
pip install pyaudio numpy websocket-client rich SpeechRecognition playwright playwright-stealth
python -m playwright install chromium
```

> ⚠️ **Windows — PyAudio failing?** Run: `pip install pipwin && pipwin install pyaudio`
>
> ⚠️ **macOS** — install PortAudio first: `brew install portaudio`
>
> ⚠️ **Linux** — install system audio libs first: `sudo apt install portaudio19-dev`

### 3. Configure credentials

```bash
cp config.example.json config.json
```

Edit `config.json` with your Toingg token (see [Data Requirements](#-data-requirements)).

---

## ⚙️ Environment Setup

### Python packages

| Package | Purpose |
|---------|---------|
| `pyaudio` | Microphone input for wake-word detection |
| `numpy` | Audio signal processing |
| `websocket-client` | WebSocket connection to Toingg backend |
| `rich` | Terminal UI formatting |
| `SpeechRecognition` | Google Speech API for wake-word detection |
| `playwright` | Browser automation (Chromium) |
| `playwright-stealth` | Anti-bot-detection patches for Playwright |

### Platform-specific setup

<details>
<summary><b>Windows</b></summary>

No extra setup required — `JARVIS.bat` installs everything automatically on first run.

For manual installs, PyAudio requires a compiled binary:
```cmd
pip install pipwin
pipwin install pyaudio
```
</details>

<details>
<summary><b>macOS</b></summary>

Run the one-time permission fixer before first launch:
```bash
bash setup_mac.sh
```

This grants execute permissions to `JARVIS.command` and requests Microphone + Accessibility access.

PortAudio must be installed via Homebrew:
```bash
brew install portaudio
```
</details>

<details>
<summary><b>Linux</b></summary>

Install system audio libraries:
```bash
# Debian/Ubuntu
sudo apt update && sudo apt install portaudio19-dev python3-pyaudio

# Fedora/RHEL
sudo dnf install portaudio-devel

# Add user to audio group if mic is not detected
sudo usermod -aG audio $USER  # log out and back in after this
```
</details>

---

## 💻 Running JARVIS

### Windows

**Option A — Double-click (recommended)**

Double-click **`JARVIS.bat`** — it auto-installs everything and launches.

**Option B — Manual**

```cmd
pip install pyaudio numpy websocket-client rich SpeechRecognition playwright playwright-stealth
python -m playwright install chromium
python jarvis_launcher.py
```

---

### macOS

**Option A — Double-click (recommended)**

```bash
# First time only
bash setup_mac.sh
```

Then double-click **`JARVIS.command`** anytime.

**Option B — Manual**

```bash
brew install portaudio
pip3 install pyaudio numpy websocket-client rich SpeechRecognition playwright playwright-stealth --break-system-packages
python3 -m playwright install chromium
python3 jarvis_launcher.py
```

> 🔐 macOS will prompt for **Microphone** permission on first run — click **Allow**.

---

### Linux

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install portaudio19-dev python3-pyaudio

# Fedora/RHEL
sudo dnf install portaudio-devel

# Python packages
pip3 install pyaudio numpy websocket-client rich SpeechRecognition playwright playwright-stealth
python3 -m playwright install chromium

# Add user to audio group (if mic not detected)
sudo usermod -aG audio $USER  # then log out & back in

# Run
python3 jarvis_launcher.py
```

---

## 🎮 Usage

| Action | Result |
|--------|--------|
| Say **"Hey Jarvis"** | Activates the terminal & visual UI |
| **Press [Space] / [Enter]** in web UI | Toggle microphone manually |
| **Speak naturally** | Streams audio to Toingg AI, plays response |
| Say **"open Spotify"** | Launches Spotify |
| Say **"open Chrome"** | Launches Chrome |
| Say **"open VS Code"** | Launches Visual Studio Code |
| **Ctrl+C** in terminal | Exit JARVIS |

When JARVIS fetches news, weather, or web results — Chrome windows open automatically in a **2×2 grid** and close after the response finishes.

### Scheduled browser actions

While `jarvis_launcher.py` is running, you can queue browser actions through the local HTTP server. Scheduled actions stay in memory for the current launcher session.

```bash
curl -X POST http://localhost:8766/schedule_action \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Open dashboard in 30 seconds",
    "trigger": { "delay_seconds": 30 },
    "actions": [
      { "type": "open_url", "url": "https://calendar.google.com" },
      { "type": "wait", "seconds": 2 },
      { "type": "open_url", "url": "https://mail.google.com" }
    ]
  }'
```

Supported triggers:

- `{ "delay_seconds": 30 }`
- `{ "run_at": "2026-06-03T14:30:00Z" }`
- `{ "type": "daily", "time": "09:00" }`

Supported action types are `open_url`, `open_tabs`, `wait`, and `close_tabs`. Use `GET /scheduled_actions` to inspect queued actions and `POST /cancel_scheduled_action` with `{ "id": "..." }` to cancel one.

---

## 📄 Data Requirements

JARVIS requires a `config.json` file at the project root. Copy the template and fill in your credentials:

```bash
cp config.example.json config.json
```

```json
{
  "WS_URL": "wss://prepodapi.toingg.com/api/v3/media/streaming",
  "TOKEN": "your_toingg_api_token_here",
  "CAMP_ID": "69d79c72b7ab98a9ef49bcad"
}
```

| Field | Description | How to get |
|-------|-------------|-----------|
| `WS_URL` | Toingg WebSocket endpoint | Leave as-is (default endpoint) |
| `TOKEN` | Your personal Toingg API token | [prepodapp.toingg.com/api-keys](https://prepodapp.toingg.com/api-keys) |
| `CAMP_ID` | Campaign / agent ID | Use the default for the free demo, or create your own campaign |

> 🆓 The default campaign ID `69d79c72b7ab98a9ef49bcad` is the **free JARVIS demo** shown in the preview video — no setup required beyond your API token.

> 🔒 `config.json` is listed in `.gitignore` and will never be committed to version control.

---

## 🔧 Configuration

Key settings in the source files:

| Setting | File | Default | Description |
|---------|------|---------|-------------|
| `WAKE_WORDS` | `jarvis_launcher.py` | `["hey jarvis", "jarvis", ...]` | Phrases that trigger full launch |
| `LAUNCH_COOLDOWN` | `jarvis_launcher.py` | `4.0` s | Minimum seconds between consecutive launches |
| `HTTP_PORT` | `jarvis_launcher.py` | `8766` | Local server port |
| `energy_threshold` | `jarvis_launcher.py` | `400` | Mic sensitivity (lower = more sensitive) |
| `pause_threshold` | `jarvis_launcher.py` | `1.2` s | Silence duration before phrase ends |
| `BROWSER_ACTION_DELAY_MS` | `jarvis_web.html` | `900` ms | Delay before first browser tab opens after audio starts |
| `MIN_BROWSER_ACTION_AUDIO_LEAD` | `jarvis_web.html` | `0.65` s | Minimum audio buffer lead before spawning Chrome |
| `PLAYBACK_IDLE_GRACE_MS` | `jarvis_web.html` | `220` ms | Grace period after last audio chunk before marking idle |

---

## 🗂️ Project Structure

```
toingg-jarvis/
├── 🐍 jarvis_launcher.py     # Wake-word listener, app launcher, HTTP server (:8766)
├── 🐍 browserClient.py       # Playwright browser automation client
├── 🌐 jarvis_web.html         # Web frontend — WebSocket audio, terminal UI
├── 🎨 jarvis_visual.html      # Animated orb / visual display
├── 🖥️  JARVIS.bat              # Windows auto-installer & launcher
├── 🍎 JARVIS.command          # macOS auto-installer & launcher
├── 🔧 setup_mac.sh            # macOS one-time permission fixer
├── 📄 config.json             # API credentials (create from example, not committed)
└── 📄 config.example.json     # Config template
```

---

## 🧠 Methodology

JARVIS is composed of three cooperating processes that communicate over `localhost:8766`:

```
┌─────────────────────────────────────────────────────────────┐
│  User speaks                                                │
│       │                                                     │
│  [Wake layer — jarvis_launcher.py]                          │
│   SpeechRecognition (Google Speech API, 16 kHz)             │
│   Detects "Hey Jarvis" → spawns browser client              │
│   Opens jarvis_web.html + jarvis_visual.html in Chrome      │
│       │                                                     │
│  [Web layer — jarvis_web.html]                              │
│   Web Audio API captures mic → 8 kHz Float32 chunks         │
│   AudioWorklet (off-main-thread) downsamples in real time   │
│   Base64 chunks → WebSocket → Toingg streaming API          │
│   Toingg responses → decoded Float32 → Web Audio playback   │
│   Animated spectrum visualiser reacts to RMS levels         │
│   URL events from Toingg → queued until audio has 0.65s lead│
│       │                                                     │
│  [Browser layer — browserClient.py]                         │
│   Playwright persistent Chromium context                    │
│   Stealth patches (navigator, WebGL, plugins, permissions)  │
│   Receives JSON action commands via WebSocket               │
│   Executes: navigate, click, fill, get_text, screenshot…    │
│   Returns results as JSON to Toingg backend                 │
└─────────────────────────────────────────────────────────────┘
```

**Audio pipeline detail:**
- Microphone is captured at the browser's native sample rate (typically 44.1 kHz or 48 kHz)
- An `AudioWorkletProcessor` running off the main thread downsamples to 8,000 Hz (Toingg's expected input rate) using a linear interpolation decimator
- Chunks of 512 samples are base64-encoded and sent as WebSocket binary-text frames
- Incoming audio from Toingg arrives as base64-encoded Float32 arrays at 24,000 Hz
- Playback is scheduled ahead-of-time using `AudioBufferSourceNode.start(scheduledTime)` to prevent underruns

**Browser automation detail:**
- `browserClient.py` uses `playwright_stealth` to patch fingerprint leaks (WebGL vendor/renderer, `navigator.plugins`, `navigator.webdriver`, permissions API)
- A persistent Chromium profile in `.browser-profile/` preserves cookies and sessions across restarts
- The `_click_element` method uses a scored text-matching algorithm in `page.evaluate()` to find the best DOM target, then uses a `data-*` marker attribute to safely re-locate it via Playwright's locator API

---

## ⚡ Performance

| Metric | Expected value | Notes |
|--------|---------------|-------|
| Wake-word latency | 1–3 s | Depends on Google Speech API round-trip |
| Audio stream start | < 500 ms after wake | After Chrome windows open |
| First AI audio chunk | 1–3 s | Depends on Toingg API latency |
| Browser tab open | 0.5–2 s per tab | Chrome spawn time varies by machine |
| CPU at idle (wake listener) | < 2% | SpeechRecognition daemon thread |
| CPU during tab opens | 20–60% spike | Chrome process creation; staggered 400 ms apart |
| Memory (full session) | 300–600 MB | 2 Chrome instances + Playwright Chromium |

**Reducing latency tips:**
- Use a wired headset to minimise mic input noise and false triggers
- Keep Chrome already running — subsequent launches use existing profiles and start faster
- On slower machines, reduce `LAUNCH_COOLDOWN` only if you frequently re-trigger JARVIS

---

## 🧪 Testing

There is currently no automated test suite. Contributions adding unit or integration tests are **very welcome** and carry bonus reward points (see [REWARD_SYSTEM.md](REWARD_SYSTEM.md)).

**Manual smoke-test checklist:**

```
[ ] python3 jarvis_launcher.py starts without errors
[ ] HTTP server responds: curl http://localhost:8766/state
[ ] Say "Hey Jarvis" — visual orb and web panel open in Chrome
[ ] Speak a question — audio response plays cleanly
[ ] Chrome tab grid opens and closes with the response
[ ] Say "open Spotify" — Spotify launches (or focuses if already open)
[ ] Ctrl+C cleanly stops the process
```

**Verifying the browser client:**

```bash
python3 browserClient.py --url wss://prepodapi.toingg.com/api/v3/media/browser/default
# Should print: Browser launched (headless=False, profile=.browser-profile)
# Then: WebSocket opened
```

---

## 🔧 Troubleshooting

<details>
<summary><b>🔴 "No module named pyaudio"</b></summary>

```bash
# Windows
pip install pipwin && pipwin install pyaudio

# macOS
brew install portaudio && pip3 install pyaudio --break-system-packages

# Linux
sudo apt install portaudio19-dev && pip3 install pyaudio
```
</details>

<details>
<summary><b>🔴 Microphone not detected</b></summary>

- **macOS**: System Settings → Privacy & Security → Microphone → enable Terminal / Chrome
- **Windows**: Settings → Privacy → Microphone → enable for apps
- **Linux**: `sudo usermod -aG audio $USER` then log out and back in
</details>

<details>
<summary><b>🔴 Chrome windows don't open</b></summary>

- Ensure Google Chrome is installed at its default path
- On Linux: `google-chrome` or `chromium-browser` must be in your `$PATH`
- On Windows: Edge is used as a fallback if Chrome is not found
</details>

<details>
<summary><b>🔴 WebSocket connection fails</b></summary>

- Verify `TOKEN` and `CAMP_ID` in `config.json`
- Check your internet connection
- Confirm no VPN is blocking WSS connections to `prepodapi.toingg.com`
</details>

<details>
<summary><b>🔴 Audio distortion / no sound</b></summary>

- Check your default output device in system sound settings
- Try a different browser for the web frontend
- On macOS, run `bash setup_mac.sh` to ensure microphone permissions are granted
</details>

<details>
<summary><b>🔴 Voice listener not responding after first activation</b></summary>

- This can happen if JARVIS was launched by double-clicking (no terminal attached)
- Upgrade to the latest version — this is fixed in v2.0.1+
</details>

---

## 📅 Changelog

### v2.0 (current)
- Replaced `jarvis_terminal.py` with `jarvis_web.html` — full browser-based audio engine using Web Audio API
- Added `browserClient.py` — Playwright browser automation with stealth patches
- 2×2 Chrome window grid for source URLs
- Multi-platform Chrome detection (Chrome / Chromium / Edge)
- Animated visual orb (`jarvis_visual.html`) separated from audio logic
- Interactive API key setup flow in terminal
- macOS multi-monitor support via AppKit

### v1.0
- Initial release — terminal-based voice interface
- Wake-word detection with Google Speech API
- Toingg WebSocket audio streaming
- Basic app launcher (Spotify, VS Code, Chrome)

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/amazing-feature`
3. **Commit** your changes: `git commit -m 'feat: add amazing feature'`
4. **Push** to the branch: `git push origin feat/amazing-feature`
5. **Open** a Pull Request

Please check [open issues](https://github.com/PG-AGI/toingg-jarvis/issues) before starting — something you want may already be in progress!

> 💰 **Earn rewards for your contributions** — see [REWARD_SYSTEM.md](REWARD_SYSTEM.md) for the full points table. First-time contributors earn a **1.5× bonus multiplier**.

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

---

## 📚 Citation

If you use JARVIS in research or reference it in a publication, please cite:

```bibtex
@software{jarvis_toingg_2025,
  author  = {PG-AGI},
  title   = {J.A.R.V.I.S — AI Voice Terminal powered by Toingg},
  year    = {2025},
  url     = {https://github.com/PG-AGI/toingg-jarvis},
  license = {MIT}
}
```

---

## 📬 Contact

| Channel | Link |
|---------|------|
| **GitHub Issues** | [Report a bug or request a feature](https://github.com/PG-AGI/toingg-jarvis/issues) |
| **GitHub Discussions** | [Community Q&A and rewards](https://github.com/PG-AGI/toingg-jarvis/discussions) |
| **Maintainer email** | admin@pgagi.in |
| **Toingg platform** | [toingg.com](https://toingg.com) |
| **X / Twitter** | [@PG_AGI](https://x.com/vivekjyotibhow1) |

---

## ⭐ Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=PG-AGI/toingg-jarvis&type=Date&theme=dark)](https://star-history.com/#PG-AGI/toingg-jarvis&Date)

</div>

---

<div align="center">

<!-- FOOTER WAVE -->
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:1565c0,100:00e5ff&height=100&section=footer" width="100%"/>

**Built with ❤️ by [PG-AGI](https://github.com/PG-AGI) — powered by [Toingg](https://toingg.com)**

<br/>

[![Preview on 𝕏](https://img.shields.io/badge/Preview%20on%20𝕏-000000?style=for-the-badge&logo=x&logoColor=white)](https://x.com/vivekjyotibhow1/status/2054589428363120765?s=46)
&nbsp;
[![GitHub followers](https://img.shields.io/github/followers/PG-AGI?style=for-the-badge&logo=github&color=00e5ff&labelColor=000d1a)](https://github.com/PG-AGI)

<br/>

*If this project helped you, please consider giving it a ⭐ — it means a lot!*

</div>
