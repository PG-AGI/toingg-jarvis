# J.A.R.V.I.S — AI Voice Terminal

A voice-driven AI terminal powered by [Toingg](https://toingg.com). Say **"Hey Jarvis"** to activate, speak naturally, and get real-time AI responses with an animated terminal UI, browser automation, and app launching.

---

## Features

- Wake-word activation ("Hey Jarvis")
- Real-time WebSocket streaming to Toingg AI backend
- Animated frequency spectrum terminal UI
- Browser grid — opens URLs in a 2×2 Chrome window layout
- App launcher (Spotify, VS Code, Chrome, etc.)
- Cross-platform: Windows, macOS, Linux

---

## Requirements

- **Python 3.8+**
- **Google Chrome** (or Chromium/Edge)
- A **Toingg API token** and campaign ID
- **Microphone** access

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/PG-AGI/toingg-jarvis.git
cd toingg-jarvis
```

### 2. Configure API credentials

Copy the example config and fill in your Toingg credentials:

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "WS_URL": "wss://prepodapi.toingg.com/api/v3/media/streaming",
  "TOKEN": "your_toingg_token_here",
  "CAMP_ID": "your_campaign_id_here"
}
```

> Get your token and campaign ID from your Toingg dashboard.

---

## Running on Windows

### Option A — Double-click launcher (recommended)

Double-click **`JARVIS.bat`**

It will:
1. Check for Python
2. Auto-install dependencies (`pyaudio`, `numpy`, `websocket-client`, `rich`, `SpeechRecognition`)
3. Launch JARVIS

> **PyAudio install fails?** Run these in a terminal:
> ```cmd
> pip install pipwin
> pipwin install pyaudio
> ```
> Then re-run `JARVIS.bat`.

### Option B — Manual

```cmd
pip install pyaudio numpy websocket-client rich SpeechRecognition
python jarvis_launcher.py
```

---

## Running on macOS

### Option A — Double-click launcher (recommended)

Double-click **`JARVIS.command`**

It will:
1. Install [Homebrew](https://brew.sh) if missing
2. Install PortAudio via Homebrew (`brew install portaudio`)
3. Install Python packages
4. Launch JARVIS

> **First run:** macOS will ask for **Microphone** permission. Click **Allow** in System Settings → Privacy & Security → Microphone.

### Option B — Manual

```bash
# Install PortAudio (required for PyAudio on macOS)
brew install portaudio

# Install Python dependencies
pip3 install pyaudio numpy websocket-client rich SpeechRecognition

# Run
python3 jarvis_launcher.py
```

---

## Running on Linux

```bash
# Install PortAudio and dev headers
sudo apt update
sudo apt install portaudio19-dev python3-pyaudio   # Debian/Ubuntu
# or
sudo dnf install portaudio-devel                   # Fedora/RHEL

# Install Python dependencies
pip3 install pyaudio numpy websocket-client rich SpeechRecognition

# Run
python3 jarvis_launcher.py
```

> **Microphone access:** Make sure your user is in the `audio` group:
> ```bash
> sudo usermod -aG audio $USER
> # then log out and back in
> ```

---

## Usage

| Action | Result |
|--------|--------|
| Say **"Hey Jarvis"** | Activates the terminal UI |
| Press **Enter** | Activates microphone to speak |
| Speak a command | Streams audio to AI, plays response |
| Say **"open Spotify"** | Launches Spotify |
| Say **"open Chrome"** | Launches Chrome |
| **Ctrl+C** | Exit |

The terminal displays a live animated spectrum, AI response text, and chat history.

---

## Project Structure

```
JARVIS/
├── jarvis_launcher.py    # Wake-word listener, app launcher, HTTP server
├── jarvis_terminal.py    # Main terminal UI, WebSocket, mic input, audio
├── jarvis_web.html       # Web frontend (served at localhost:8766)
├── jarvis_visual.html    # Animated orb / visual display
├── JARVIS.bat            # Windows launcher script
├── JARVIS.command        # macOS launcher script
├── config.json           # API credentials (not in repo — create from example)
└── config.example.json   # Config template
```

---

## Configuration

Key settings are at the top of each script. You can tune:

| Setting | File | Default | Description |
|---------|------|---------|-------------|
| `MIC_ENERGY_THRESHOLD` | `jarvis_terminal.py` | `600` | Mic sensitivity (100–4000) |
| `MIC_PAUSE_THRESHOLD` | `jarvis_terminal.py` | `1.2` | Silence duration to end phrase |
| `BARGE_IN_PAUSE` | `jarvis_terminal.py` | `0.4` | Interrupt AI while it speaks |
| `WAKE_WORDS` | `jarvis_launcher.py` | `["hey jarvis", ...]` | Trigger phrases |
| `HTTP_PORT` | both | `8766` | Local server port |

---

## Troubleshooting

**"No module named pyaudio"**
- Windows: `pip install pipwin && pipwin install pyaudio`
- macOS: `brew install portaudio && pip3 install pyaudio`
- Linux: `sudo apt install portaudio19-dev && pip3 install pyaudio`

**Microphone not detected**
- Check system permissions (macOS: System Settings → Privacy → Microphone)
- Linux: verify your user is in the `audio` group

**Chrome windows don't open**
- Ensure Google Chrome is installed at its default path
- On Linux, `google-chrome` or `chromium-browser` must be on your `$PATH`

**WebSocket connection fails**
- Verify your `TOKEN` and `CAMP_ID` in `config.json`
- Check your internet connection

---

## License

MIT
