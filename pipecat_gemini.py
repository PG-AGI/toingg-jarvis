"""
PIPECAT / GEMINI BACKEND  — J.A.R.V.I.S alternative AI pipeline
===============================================================

Usage:
    set BACKEND=pipecat_gemini in config.json, then launch jarvis_launcher.py

Requirements:
    pip install pipecat-ai[google] websockets

The jarvis_launcher auto-detects BACKEND=pipecat_gemini and spawns this
module instead of the Toingg WebSocket flow.  This module runs a local
WebSocket server that jarvis_web.html connects to.

Supports:
  - Real-time voice via Gemini Multimodal Live
  - Tool calling (open_browser, close_tabs, file_action, playwright)
  - Backend switching via config.json
"""

import asyncio
import base64
import json
import os
import signal
import struct
import sys
import threading
import time
from urllib.parse import urlencode

import requests
import websockets
from loguru import logger

# ── Pipecat imports ─────────────────────────────────────────────────────────
try:
    from pipecat.adapters.schemas.function_schema import FunctionSchema
    from pipecat.adapters.schemas.tools_schema import ToolsSchema
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.frames.frames import InputAudioRawFrame, InputTextRawFrame, InterruptionFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.services.google.gemini_live.llm import (
        GeminiLiveLLMService,
    )
except ImportError as e:
    logger.error(f"Missing pipecat-ai[google]: {e}")
    logger.error("Install with: pip install 'pipecat-ai[google]'")
    sys.exit(1)

# ── Config ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LAUNCHER_PORT = 8766
WS_PORT = 8767
LAUNCHER_BASE = f"http://localhost:{LAUNCHER_PORT}"
BROWSER_AUDIO_SAMPLE_RATE = 8000
BROWSER_AUDIO_CHANNELS = 1


def load_config():
    cfg_path = os.path.join(SCRIPT_DIR, "config.json")
    try:
        with open(cfg_path) as f:
            return json.load(f)
    except Exception:
        logger.error("config.json not found or invalid")
        return {}


def _float32_b64_to_pcm16(audio_b64: str) -> bytes:
    """Convert jarvis_web.html float32 base64 chunks to 16-bit PCM frames."""
    raw = base64.b64decode(audio_b64)
    if len(raw) % 4:
        raise ValueError("audio payload length is not aligned to float32 samples")
    samples = struct.unpack(f"<{len(raw) // 4}f", raw)
    pcm = bytearray(len(samples) * 2)
    offset = 0
    for sample in samples:
        clamped = max(-1.0, min(1.0, float(sample)))
        pcm[offset:offset + 2] = int(clamped * 32767).to_bytes(
            2, "little", signed=True
        )
        offset += 2
    return bytes(pcm)


# ── Tool implementations ────────────────────────────────────────────────────
async def open_browser(url: str, tab_name: str = "JARVIS Result"):
    """Open a URL in a Chrome slot via the launcher HTTP server."""
    try:
        resp = requests.post(
            f"{LAUNCHER_BASE}/open_window",
            json={"url": url, "label": tab_name},
            timeout=10,
        )
        if resp.status_code == 200:
            return f"Opened {url} in browser"
        return f"Failed to open browser: HTTP {resp.status_code}"
    except requests.RequestException as e:
        return f"Browser launcher unavailable: {e}"


async def close_tabs(auto: bool = False):
    """Close all Chrome slot windows."""
    try:
        resp = requests.post(
            f"{LAUNCHER_BASE}/close_tabs",
            json={"auto": auto},
            timeout=10,
        )
        if resp.status_code == 200:
            return "Browser tabs closed"
        return f"Failed to close tabs: HTTP {resp.status_code}"
    except requests.RequestException as e:
        return f"Browser launcher unavailable: {e}"


async def run_playwright(action: str, params: str = "{}"):
    """Execute a Playwright browser action via the launcher."""
    try:
        action_params = json.loads(params) if isinstance(params, str) else params
        resp = requests.post(
            f"{LAUNCHER_BASE}/playwright_action",
            json={"action": action, "params": action_params},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            return f"Playwright action '{action}' submitted"
        return f"Playwright action failed: HTTP {resp.status_code}"
    except requests.RequestException as e:
        return f"Launcher unavailable: {e}"


async def open_file(path: str):
    """Open a file via the launcher file_action endpoint."""
    try:
        resp = requests.post(
            f"{LAUNCHER_BASE}/file_action",
            json={"action": "open", "path": path},
            timeout=10,
        )
        if resp.status_code == 200:
            return f"Opened file: {path}"
        return f"File action failed: HTTP {resp.status_code}"
    except requests.RequestException as e:
        return f"Launcher unavailable: {e}"


# ── Tool definitions for Gemini ─────────────────────────────────────────────
TOOLS_SCHEMA = ToolsSchema(
    standard_tools=[
        FunctionSchema(
            name="open_browser",
            description="Open a URL in the Chrome browser grid. Use when the user asks to open a website or search the web.",
            properties={
                "url": {
                    "type": "string",
                    "description": "Full URL to open (include https://)",
                },
                "tab_name": {
                    "type": "string",
                    "description": "Display name for the browser tab",
                },
            },
            required=["url"],
        ),
        FunctionSchema(
            name="close_tabs",
            description="Close all browser slot windows opened by JARVIS.",
            properties={
                "auto": {
                    "type": "boolean",
                    "description": "If true, only close auto-closeable tabs",
                },
            },
            required=[],
        ),
        FunctionSchema(
            name="run_playwright",
            description="Execute a Playwright browser automation action (navigate, click, fill, get_text, screenshot).",
            properties={
                "action": {
                    "type": "string",
                    "description": "Playwright action type",
                    "enum": [
                        "navigate",
                        "click",
                        "fill",
                        "get_text",
                        "screenshot",
                        "open_url",
                        "wait",
                    ],
                },
                "params": {
                    "type": "string",
                    "description": "JSON string with action parameters",
                },
            },
            required=["action"],
        ),
        FunctionSchema(
            name="open_file",
            description="Open a file on the user's computer.",
            properties={
                "path": {
                    "type": "string",
                    "description": "Full path to the file to open",
                },
            },
            required=["path"],
        ),
    ]
)

TOOL_MAP = {
    "open_browser": open_browser,
    "close_tabs": close_tabs,
    "run_playwright": run_playwright,
    "open_file": open_file,
}


# ── Pipecat pipeline ────────────────────────────────────────────────────────
class JarvisGeminiPipeline:
    """Builds and manages the Pipecat pipeline for Gemini-powered voice AI."""

    def __init__(
        self,
        api_key: str,
        model: str = "models/gemini-2.5-flash-native-audio-preview-12-2025",
    ):
        self.api_key = api_key
        self.model = model
        self.pipeline = None
        self.task = None
        self.runner = None

    async def _handle_function_call(self, function_name, tool_call_id, arguments):
        """Execute a function called by Gemini and return the result."""
        func = TOOL_MAP.get(function_name)
        if not func:
            return {"error": f"Unknown function: {function_name}"}

        logger.info(f"Tool call: {function_name}({arguments})")
        try:
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            result = await func(**arguments)
            logger.info(f"Tool result: {result}")
            return {"result": result}
        except Exception as e:
            logger.error(f"Tool error: {e}")
            return {"error": str(e)}

    def build(self):
        """Construct the Pipecat pipeline with Gemini + tool calling."""
        system_instruction = (
            "You are JARVIS, an AI voice assistant. You can open browsers, close tabs, "
            "run web automation, and open files on the user's computer. "
            "Be helpful, concise, and conversational. When you perform an action, "
            "tell the user what you're doing."
        )
        llm = GeminiLiveLLMService(
            api_key=self.api_key,
            model=self.model,
            system_instruction=system_instruction,
            tools=TOOLS_SCHEMA,
            voice_id="Kore",
        )

        # Register tool call handler
        @llm.event_handler("on_function_call")
        async def on_tool_call(service, function_name, tool_call_id, arguments):
            return await self._handle_function_call(function_name, tool_call_id, arguments)

        self.pipeline = Pipeline([llm])
        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(
                allow_interruptions=True,
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
        )
        self.runner = PipelineRunner()
        return self

    async def run(self):
        """Start the pipeline runner."""
        if not self.runner or not self.task:
            self.build()
        logger.info("Starting Gemini Pipecat pipeline...")
        await self.runner.run(self.task)


# ── WebSocket bridge (jarvis_web.html compatible) ───────────────────────────
class JarvisWebSocketBridge:
    """
    Bridges jarvis_web.html's audio WebSocket to the Pipecat pipeline.
    Provides a local WS server on port 8767 that accepts audio chunks
    and forwards them through the pipeline.
    """

    def __init__(self, pipeline: JarvisGeminiPipeline):
        self.pipeline = pipeline
        self._clients: set = set()

    async def handle_ws(self, websocket):
        """Handle a connection from jarvis_web.html."""
        self._clients.add(websocket)
        logger.info(f"Web client connected ({len(self._clients)} active)")

        try:
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type", "")

                    if msg_type == "audio" or data.get("event") == "media":
                        media = data.get("media") if isinstance(data.get("media"), dict) else {}
                        audio_b64 = data.get("data") or media.get("payload", "")
                        if not audio_b64:
                            continue
                        pcm_audio = _float32_b64_to_pcm16(audio_b64)
                        if self.pipeline.task:
                            await self.pipeline.task.queue_frame(
                                InputAudioRawFrame(
                                    audio=pcm_audio,
                                    sample_rate=BROWSER_AUDIO_SAMPLE_RATE,
                                    num_channels=BROWSER_AUDIO_CHANNELS,
                                )
                            )

                    elif msg_type == "text":
                        if self.pipeline.task:
                            await self.pipeline.task.queue_frame(
                                InputTextRawFrame(data.get("text", ""))
                            )

                    elif msg_type == "stop":
                        if self.pipeline.task:
                            await self.pipeline.task.queue_frame(InterruptionFrame())

                except json.JSONDecodeError:
                    continue

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self._clients.discard(websocket)
            logger.info(f"Web client disconnected ({len(self._clients)} active)")

    async def start_server(self):
        """Start the WebSocket server for jarvis_web.html."""
        logger.info(f"WebSocket bridge listening on ws://localhost:{WS_PORT}")
        async with websockets.serve(self.handle_ws, "localhost", WS_PORT):
            await asyncio.Future()  # run forever


# ── Main entry point ────────────────────────────────────────────────────────
def main():
    config = load_config()

    api_key = config.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        logger.error(
            "GEMINI_API_KEY not found in config.json or GEMINI_API_KEY env var.\n"
            "Get a free key at https://aistudio.google.com/apikey"
        )
        sys.exit(1)

    logger.info("=== JARVIS Pipecat/Gemini Backend ===")
    logger.info(f"Launcher HTTP: {LAUNCHER_BASE}")
    logger.info(f"WebSocket:     ws://localhost:{WS_PORT}")

    async def run_all():
        pipeline = JarvisGeminiPipeline(api_key=api_key)
        pipeline.build()

        bridge = JarvisWebSocketBridge(pipeline)

        # Run pipeline and WS bridge concurrently
        await asyncio.gather(
            pipeline.run(),
            bridge.start_server(),
        )

    asyncio.run(run_all())


if __name__ == "__main__":
    main()
