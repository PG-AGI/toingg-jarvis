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

- [✨ Features](#-features)
- [🚀 Quick Start](#-quick-start)
- [📋 Requirements](#-requirements)
- [🛠️ Setup](#️-setup)
- [💻 Running JARVIS](#-running-jarvis)
  - [Windows](#windows)
  - [macOS](#macos)
  - [Linux](#linux)
- [🎮 Usage](#-usage)
- [⚙️ Configuration](#️-configuration)
- [🗂️ Project Structure](#️-project-structure)
- [🔧 Troubleshooting](#-troubleshooting)
- [🤝 Contributing](#-contributing)
- [⭐ Star History](#-star-history)
- [📜 License](#-license)

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
- Playwright-powered browser client
- Automatic tab management (open + close)
- Cross-platform Chrome/Chromium/Edge support

</td>
<td width="50%">

**🚀 App Launcher**
- Launch Spotify, VS Code, Chrome & more
- Smart window focus if app already running
- Custom window size + positioning per app
- Platform-aware (Mac / Windows paths)

</td>
</tr>
</table>

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

## 📋 Requirements

| Requirement | Details |
|---|---|
| **Python** | 3.8 or higher |
| **Browser** | Google Chrome, Chromium, or Edge |
| **Toingg account** | Free — [sign up here](https://prepodapp.toingg.com) |
| **Microphone** | Any — headset recommended for best results |

### Python packages (auto-installed by launchers)

```
pyaudio           — mic input + audio playback
numpy             — signal processing
websocket-client  — WebSocket connection
rich              — terminal UI
SpeechRecognition — wake word detection
playwright        — browser automation
```

---

## 🛠️ Setup

### 1. Clone the repository

```bash
git clone https://github.com/PG-AGI/toingg-jarvis.git
cd toingg-jarvis
```

### 2. Configure your Toingg credentials

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "WS_URL": "wss://prepodapi.toingg.com/api/v3/media/streaming",
  "TOKEN": "your_toingg_token_here",
  "CAMP_ID": "69d79c72b7ab98a9ef49bcad"
}
```

> 🆓 Use campaign ID `69d79c72b7ab98a9ef49bcad` for the **free demo campaign** shown in the preview.

---

## 💻 Running JARVIS

### Windows

**Option A — Double-click (recommended)**

Double-click **`JARVIS.bat`** — it auto-installs everything and launches.

**Option B — Manual**

```cmd
pip install pyaudio numpy websocket-client rich SpeechRecognition playwright
python -m playwright install chromium
python jarvis_launcher.py
```

> ⚠️ PyAudio failing? Run: `pip install pipwin && pipwin install pyaudio`

---

### macOS

**Option A — Double-click (recommended)**

```bash
# First time only — fix permissions
bash setup_mac.sh
```

Then double-click **`JARVIS.command`** anytime.

**Option B — Manual**

```bash
brew install portaudio
pip3 install pyaudio numpy websocket-client rich SpeechRecognition playwright --break-system-packages
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
pip3 install pyaudio numpy websocket-client rich SpeechRecognition playwright
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
| **Press [Space] / [Enter]** | Toggle microphone manually |
| **Speak naturally** | Streams audio to Toingg AI, plays response |
| Say **"open Spotify"** | Launches Spotify |
| Say **"open Chrome"** | Launches Chrome |
| Say **"open VS Code"** | Launches Visual Studio Code |
| **Ctrl+C** | Exit JARVIS |

When JARVIS fetches news, weather, or web results — Chrome windows open automatically in a **2×2 grid** and close after the response finishes.

---

## ⚙️ Configuration

Key settings at the top of each script:

| Setting | File | Default | Description |
|---------|------|---------|-------------|
| `MIC_ENERGY_THRESHOLD` | `jarvis_terminal.py` | `600` | Mic sensitivity (100 = very sensitive, 4000 = noise-resistant) |
| `MIC_PAUSE_THRESHOLD` | `jarvis_terminal.py` | `1.2` | Silence (seconds) before phrase ends |
| `BARGE_IN_PAUSE` | `jarvis_terminal.py` | `0.4` | Interrupt AI while it's speaking |
| `WAKE_WORDS` | `jarvis_launcher.py` | `["hey jarvis", ...]` | Trigger phrases |
| `HTTP_PORT` | both | `8766` | Local server port |

---

## 🗂️ Project Structure

```
toingg-jarvis/
├── 🐍 jarvis_launcher.py     # Wake-word listener, app launcher, HTTP server
├── 🐍 jarvis_terminal.py     # Terminal UI, WebSocket, mic input, audio engine
├── 🐍 browserClient.py       # Playwright browser automation client
├── 🌐 jarvis_web.html         # Web frontend (served at localhost:8766)
├── 🎨 jarvis_visual.html      # Animated orb / visual display
├── 🖥️  JARVIS.bat              # Windows launcher script
├── 🍎 JARVIS.command          # macOS launcher script
├── 🔧 setup_mac.sh            # Mac one-time permission fixer
├── 📄 config.json             # API credentials (create from example)
└── 📄 config.example.json     # Config template
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
</details>

<details>
<summary><b>🔴 WebSocket connection fails</b></summary>

- Verify `TOKEN` and `CAMP_ID` in `config.json`
- Check your internet connection
- Confirm no VPN is blocking WSS connections
</details>

<details>
<summary><b>🔴 Audio distortion / no sound</b></summary>

- Check your default output device in system sound settings
- Try a different browser for the web frontend
</details>

---

## 🤝 Contributing

Contributions are welcome! Here's how:

1. **Fork** the repository
2. **Create** a feature branch: `git checkout -b feat/amazing-feature`
3. **Commit** your changes: `git commit -m 'feat: add amazing feature'`
4. **Push** to the branch: `git push origin feat/amazing-feature`
5. **Open** a Pull Request

Please check [open issues](https://github.com/PG-AGI/toingg-jarvis/issues) before starting — something you want may already be in progress!

---

## ⭐ Star History

<div align="center">

[![Star History Chart](https://api.star-history.com/svg?repos=PG-AGI/toingg-jarvis&type=Date&theme=dark)](https://star-history.com/#PG-AGI/toingg-jarvis&Date)

</div>

---

## 📜 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more information.

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
