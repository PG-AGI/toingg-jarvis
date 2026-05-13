@echo off
title J.A.R.V.I.S — Starting...
cd /d "%~dp0"

echo.
echo  ╔══════════════════════════════════╗
echo  ║     J.A.R.V.I.S  STARTING...    ║
echo  ╚══════════════════════════════════╝
echo.

:: ── 1. Check Python ──────────────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python not found.
    echo  Download from https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
echo  Python found.

:: ── 2. Install packages if missing ───────────────────────────────────────────
echo  Checking packages...
python -c "import pyaudio" >nul 2>&1       || python -m pip install pyaudio -q
python -c "import numpy" >nul 2>&1         || python -m pip install numpy -q
python -c "import websocket" >nul 2>&1     || python -m pip install websocket-client -q
python -c "import rich" >nul 2>&1          || python -m pip install rich -q
python -c "import speech_recognition" >nul 2>&1 || python -m pip install SpeechRecognition -q
python -c "import playwright" >nul 2>&1    || python -m pip install playwright -q
python -m playwright install chromium
echo  All packages ready.
echo.

:: ── 3. Launch JARVIS Launcher (say "Hey Jarvis" to activate) ────────────────
echo  Starting JARVIS Launcher...
echo  Say "Hey Jarvis" to activate...
echo.
python jarvis_launcher.py

echo.
echo  JARVIS stopped.
pause
