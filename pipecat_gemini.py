"""
Optional Pipecat/Gemini backend for J.A.R.V.I.S.

Model assisted: GPT-5.

This module keeps the existing Toingg backend as the default. When
config.json sets BACKEND=pipecat_gemini, jarvis_web.html connects to this
local WebSocket bridge and Gemini tool calls are routed to the launcher HTTP
API on localhost:8766.
"""

import asyncio
import base64
import json
import os
import struct
import sys
from urllib import request
from urllib.error import URLError


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LAUNCHER_BASE = "http://localhost:8766"
WS_PORT = 8767
DEFAULT_MODEL = "gemini-2.5-flash"


TOOL_DECLARATIONS = [
    {
        "name": "open_browser",
        "description": "Open one or more URLs in the JARVIS browser grid.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "urls": {"type": "array", "items": {"type": "string"}},
                "tabs": {"type": "array", "items": {"type": "object"}},
            },
        },
    },
    {
        "name": "close_tabs",
        "description": "Close browser slot windows opened by JARVIS.",
        "parameters": {
            "type": "object",
            "properties": {"auto": {"type": "boolean"}},
        },
    },
    {
        "name": "open_file",
        "description": "Open a local file through the launcher's native file handler.",
        "parameters": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_playwright",
        "description": "Run a browser automation action through /playwright_action.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["action"],
        },
    },
]


def load_config():
    try:
        with open(os.path.join(SCRIPT_DIR, "config.json"), "r") as f:
            return json.load(f)
    except Exception:
        return {}


def post_json(url, payload, timeout=10):
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                body = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                body = {"raw": raw}
            return {"ok": 200 <= resp.status < 300, "status": resp.status, "body": body}
    except URLError as exc:
        return {"ok": False, "status": 0, "error": str(exc)}


class LauncherToolClient:
    def __init__(self, base_url=LAUNCHER_BASE, poster=post_json):
        self.base_url = base_url.rstrip("/")
        self.poster = poster

    def open_browser(self, arguments):
        tabs = arguments.get("tabs")
        if tabs is None:
            urls = arguments.get("urls")
            if urls is None:
                urls = [arguments["url"]]
            tabs = [{"url": url} for url in urls]
        return self.poster(f"{self.base_url}/open_tabs", tabs[:4])

    def close_tabs(self, arguments):
        return self.poster(
            f"{self.base_url}/close_tabs",
            {"auto": bool(arguments.get("auto", False))},
        )

    def open_file(self, arguments):
        return self.poster(
            f"{self.base_url}/file_action",
            {"action": "open_file", "path": arguments["path"]},
        )

    def run_playwright(self, arguments):
        return self.poster(
            f"{self.base_url}/playwright_action",
            {
                "action": arguments["action"],
                "params": arguments.get("params") or {},
            },
        )


TOOL_METHODS = {
    "open_browser": "open_browser",
    "close_tabs": "close_tabs",
    "open_file": "open_file",
    "run_playwright": "run_playwright",
    "playwright_action": "run_playwright",
}


async def handle_tool_call(function_name, arguments, tool_call_id="", client=None):
    if isinstance(arguments, str):
        arguments = json.loads(arguments or "{}")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be a JSON object")
    client = client or LauncherToolClient()
    method_name = TOOL_METHODS.get(function_name)
    if not method_name:
        result = {"ok": False, "error": f"unknown tool: {function_name}"}
    else:
        method = getattr(client, method_name)
        result = method(arguments)
    return {
        "type": "FunctionCallResultFrame",
        "function_name": function_name,
        "tool_call_id": tool_call_id,
        "result": result,
    }


def float32_b64_to_pcm16(payload):
    raw = base64.b64decode(payload)
    if len(raw) % 4:
        raise ValueError("Float32 audio payload length must be divisible by 4")
    values = struct.unpack("<" + "f" * (len(raw) // 4), raw)
    pcm = bytearray()
    for value in values:
        value = max(-1.0, min(1.0, float(value)))
        pcm.extend(struct.pack("<h", int(value * 32767)))
    return bytes(pcm)


async def queue_audio_frame(task, payload, sample_rate=16000, channels=1, frame_class=None):
    frame_class = frame_class or _load_input_audio_frame_class()
    audio = float32_b64_to_pcm16(payload)
    frame = frame_class(audio=audio, sample_rate=sample_rate, num_channels=channels)
    await task.queue_frame(frame)
    return frame


def _load_input_audio_frame_class():
    from pipecat.frames.frames import InputAudioRawFrame

    return InputAudioRawFrame


def _load_input_text_frame_class():
    from pipecat.frames.frames import InputTextRawFrame

    return InputTextRawFrame


def _load_interruption_frame_class():
    from pipecat.frames.frames import InterruptionFrame

    return InterruptionFrame


class JarvisWebSocketBridge:
    def __init__(self, task, clients=None, audio_frame_class=None, text_frame_class=None, interruption_frame_class=None):
        self.task = task
        self.clients = clients if clients is not None else set()
        self.audio_frame_class = audio_frame_class
        self.text_frame_class = text_frame_class
        self.interruption_frame_class = interruption_frame_class

    async def handle_message(self, message):
        data = json.loads(message) if isinstance(message, str) else message
        event = str(data.get("event") or data.get("type") or "").lower()
        if event in ("media", "audio"):
            payload = data.get("media", {}).get("payload") or data.get("data") or data.get("payload")
            if not payload:
                return None
            sample_rate = int(data.get("sampleRate") or data.get("sample_rate") or 16000)
            return await queue_audio_frame(
                self.task,
                payload,
                sample_rate=sample_rate,
                frame_class=self.audio_frame_class,
            )
        if event == "text":
            frame_class = self.text_frame_class or _load_input_text_frame_class()
            frame = frame_class(data.get("text", ""))
            await self.task.queue_frame(frame)
            return frame
        if event in ("stop", "interrupt"):
            frame_class = self.interruption_frame_class or _load_interruption_frame_class()
            frame = frame_class()
            await self.task.queue_frame(frame)
            return frame
        return None

    async def handle_ws(self, websocket):
        self.clients.add(websocket)
        try:
            async for message in websocket:
                await self.handle_message(message)
        finally:
            self.clients.discard(websocket)


async def run_backend():
    try:
        import websockets
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineParams, PipelineTask
        from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService, GeminiLiveLLMSettings
    except ImportError as exc:
        print(f"Missing optional Pipecat/Gemini dependency: {exc}", file=sys.stderr)
        print("Install with: pip install 'pipecat-ai[google]' websockets", file=sys.stderr)
        sys.exit(1)

    cfg = load_config()
    api_key = os.environ.get("GEMINI_API_KEY") or cfg.get("GEMINI_API_KEY", "")
    if not api_key or api_key == "your-gemini-api-key-here":
        print("GEMINI_API_KEY is required for BACKEND=pipecat_gemini", file=sys.stderr)
        sys.exit(1)

    settings = GeminiLiveLLMSettings(
        api_key=api_key,
        model=cfg.get("GEMINI_MODEL", DEFAULT_MODEL),
        tools=TOOL_DECLARATIONS,
        modalities=["AUDIO"],
    )
    llm = GeminiLiveLLMService(settings=settings)
    client = LauncherToolClient()

    @llm.event_handler("on_function_call")
    async def on_function_call(service, function_name, tool_call_id, arguments):
        return await handle_tool_call(function_name, arguments, tool_call_id, client=client)

    pipeline = Pipeline([llm])
    task = PipelineTask(
        pipeline,
        params=PipelineParams(allow_interruptions=True, enable_metrics=True),
    )
    bridge = JarvisWebSocketBridge(task)
    runner = PipelineRunner()

    async def serve_ws():
        async with websockets.serve(bridge.handle_ws, "localhost", WS_PORT):
            await asyncio.Future()

    await asyncio.gather(runner.run(task), serve_ws())


def main():
    asyncio.run(run_backend())


if __name__ == "__main__":
    main()
