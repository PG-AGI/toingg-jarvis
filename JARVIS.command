#!/bin/bash
# ── JARVIS Launcher — double-click to run on Mac ──────────────────────────────
# Place this file in the same folder as jarvis_terminal.py
# First time: right-click → Open (to bypass Gatekeeper), after that double-click works.

cd "$(dirname "$0")"

echo "╔══════════════════════════════════╗"
echo "║     J.A.R.V.I.S  STARTING...    ║"
echo "╚══════════════════════════════════╝"
echo ""

# ── 1. Check Python ───────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌  Python3 not found."
    echo "    Install from https://www.python.org/downloads/ then try again."
    read -p "Press Enter to close..."
    exit 1
fi
echo "✅  Python: $(python3 --version)"

# ── 2. Install Homebrew if missing ────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo ""
    echo "📦  Installing Homebrew (needed for PortAudio)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Apple Silicon path
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
fi

# ── 3. Install PortAudio (required for pyaudio) ───────────────────────────────
if ! brew list portaudio &>/dev/null 2>&1; then
    echo "📦  Installing PortAudio..."
    brew install portaudio
fi
echo "✅  PortAudio ready"

# ── 4. Install Python packages ────────────────────────────────────────────────
echo ""
echo "📦  Checking Python packages..."

python3 -c "import pyaudio" 2>/dev/null || {
    echo "    Installing pyaudio..."
    PA_PREFIX="$(brew --prefix portaudio)"
    pip3 install pyaudio \
        --global-option=build_ext \
        --global-option="-I${PA_PREFIX}/include" \
        --global-option="-L${PA_PREFIX}/lib" -q \
        --break-system-packages 2>/dev/null || \
    pip3 install pyaudio -q --break-system-packages
}

python3 -c "import numpy" 2>/dev/null           || pip3 install numpy -q --break-system-packages
python3 -c "import websocket" 2>/dev/null        || pip3 install websocket-client -q --break-system-packages
python3 -c "import rich" 2>/dev/null             || pip3 install rich -q --break-system-packages
python3 -c "import speech_recognition" 2>/dev/null || pip3 install SpeechRecognition -q --break-system-packages
python3 -c "import playwright" 2>/dev/null       || python3 -m pip install playwright -q --break-system-packages
python3 -m playwright install chromium

echo "✅  All packages ready"
echo ""

# ── 5. Suppress TensorFlow Lite warnings on Mac (safe to ignore) ──────────────
export TF_CPP_MIN_LOG_LEVEL=2
export TF_FORCE_GPU_ALLOW_GROWTH=true
export CUDA_VISIBLE_DEVICES="-1"

# ── 6. Launch JARVIS Launcher (say "Hey Jarvis" to activate) ─────────────────
echo "🚀  Starting JARVIS Launcher..."
echo "    Say 'Hey Jarvis' to activate..."
echo ""
python3 jarvis_launcher.py 2>&1 | grep -v "XNNPACK\|allocator\|DEPRECATED_ENDPOINT\|OnSizeReceived\|handshake failed\|ssl_error"

# Keep terminal open if it crashes
echo ""
echo "JARVIS stopped."
read -p "Press Enter to close..."
