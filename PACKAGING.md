# Packaging JARVIS

This project can be packaged into a standalone `dist/JARVIS` folder with
PyInstaller. The packaged app includes the Python launcher, browser client,
web UI files, visual UI, native file helpers, and the example configuration.

## Build Locally

Install the runtime and packaging dependencies first:

```bash
python -m pip install --upgrade pip
python -m pip install pyinstaller pyaudio numpy websocket-client rich SpeechRecognition playwright playwright-stealth
```

Linux and macOS also need PortAudio headers before installing `pyaudio`:

```bash
# Ubuntu/Debian
sudo apt-get install portaudio19-dev

# macOS
brew install portaudio
```

Build the package:

```bash
pyinstaller --clean --noconfirm jarvis_launcher.spec
```

The packaged application is written to `dist/JARVIS`.

## GitHub Actions Packages

The `Package JARVIS` workflow builds packages on:

- Windows
- macOS
- Linux

It runs for pull requests, pushes to `main`, and manual `workflow_dispatch`
runs. Each run uploads a platform-specific archive as a workflow artifact.

## After Downloading a Package

1. Copy `config.example.json` to `config.json`.
2. Add your Toingg token and campaign details.
3. Run the `JARVIS` executable from the extracted package folder.

The package still expects Chrome, Chromium, or Edge to be installed on the
host system for browser automation.
