"""
Pipecat + Google Gemini API Backend
=====================================
Real-time voice and multimodal conversations using Pipecat pipelines
with Gemini-powered reasoning, function calling, and tool execution.

Usage:
    BACKEND=pipecat_gemini python pipecat_gemini_backend.py

Requires:
    pip install pipecat google-generativeai
"""

import asyncio
import json
import logging
import os
import sys

# ── Optional dependency wrapper ────────────────────────────────────────────────

try:
    import google.generativeai as genai
except ImportError:
    genai = None

# Pipecat imports are lazy-loaded inside start() so missing deps don't
# crash the main launcher at import time.

logging.basicConfig(level=logging.INFO, format="%(asctime)s [PIPECAT] %(message)s")
log = logging.getLogger("pipecat_gemini")

# ── Config ─────────────────────────────────────────────────────────────────────

_DIR = os.path.dirname(os.path.abspath(__file__))

def _load_config():
    cfg_path = os.path.join(_DIR, "config.json")
    try:
        with open(cfg_path) as f:
            return json.load(f)
    except Exception:
        return {}

CONFIG = _load_config()
GEMINI_API_KEY = CONFIG.get("GEMINI_API_KEY") or CONFIG.get("TOKEN", "")
GEMINI_MODEL = CONFIG.get("GEMINI_MODEL", "gemini-2.0-flash")
HTTP_PORT = 8766
LAUNCHER_URL = f"http://localhost:{HTTP_PORT}"

# ── Tool definitions for Gemini ────────────────────────────────────────────────

TOOLS = [
    {
        "name": "open_browser",
        "description": "Open a URL in the browser. Use this to show web pages to the user.",
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL to open (e.g. https://example.com)"
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "close_tabs",
        "description": "Close all browser tabs that were opened.",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "open_file",
        "description": "Open a local file. Optional utility.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to open"
                }
            },
            "required": ["path"]
        }
    },
    {
        "name": "run_playwright",
        "description": "Execute a Playwright browser automation action like click, type, navigate, screenshot.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["navigate", "click", "type", "screenshot", "extract", "scroll"],
                    "description": "The action to perform"
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector for the target element (if applicable)"
                },
                "value": {
                    "type": "string",
                    "description": "Value to type or URL to navigate to (if applicable)"
                }
            },
            "required": ["action"]
        }
    },
    {
        "name": "playwright_actions",
        "description": "Execute multiple Playwright actions in sequence (e.g. navigate to a page, wait, click a button, extract text).",
        "parameters": {
            "type": "object",
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["navigate", "click", "type", "screenshot", "extract", "scroll", "wait"],
                                "description": "The action to perform"
                            },
                            "selector": {"type": "string", "description": "CSS selector"},
                            "value": {"type": "string", "description": "Value or URL"},
                            "timeout": {"type": "integer", "description": "Timeout in ms"}
                        },
                        "required": ["action"]
                    },
                    "description": "Ordered list of actions to perform"
                }
            },
            "required": ["actions"]
        }
    }
]


# ── HTTP tool executor ─────────────────────────────────────────────────────────

async def _call_http(endpoint: str, payload: dict = None) -> dict:
    """Call a local HTTP endpoint on the jarvis_launcher server."""
    import aiohttp
    url = f"{LAUNCHER_URL}{endpoint}"
    try:
        async with aiohttp.ClientSession() as session:
            if payload is not None:
                async with session.post(url, json=payload) as resp:
                    data = await resp.json() if resp.content_type == "application/json" else await resp.text()
                    return {"ok": resp.ok, "status": resp.status, "data": data}
            else:
                async with session.get(url) as resp:
                    data = await resp.json() if resp.content_type == "application/json" else await resp.text()
                    return {"ok": resp.ok, "status": resp.status, "data": data}
    except Exception as e:
        log.error(f"HTTP call to {endpoint} failed: {e}")
        return {"ok": False, "error": str(e)}


async def execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return a human-readable result string."""
    log.info(f"Executing tool: {name}({json.dumps(args)})")

    if name == "open_browser":
        url = args.get("url", "")
        if not url.startswith("http"):
            url = "https://" + url
        result = await _call_http("/open_window", {"url": url})
        if result.get("ok"):
            return f"Opened {url} in browser"
        return f"Failed to open browser: {result.get('error', 'unknown')}"

    elif name == "close_tabs":
        result = await _call_http("/close_tabs", {})
        if result.get("ok"):
            return "Closed all browser tabs"
        return f"Failed to close tabs: {result.get('error', 'unknown')}"

    elif name == "open_file":
        path = args.get("path", "")
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
            return f"Opened file: {path}"
        except Exception as e:
            return f"Failed to open file: {e}"

    elif name == "run_playwright":
        action = args.get("action", "")
        selector = args.get("selector", "")
        value = args.get("value", "")
        # Forward to browserClient via HTTP or return instruction
        payload = {"action": action, "selector": selector, "value": value}
        result = await _call_http("/browser", payload)
        if result.get("ok"):
            return f"Playwright {action} completed"
        return f"Playwright {action} result: {result.get('data', 'done')}"

    elif name == "playwright_actions":
        actions = args.get("actions", [])
        results = []
        for action_item in actions:
            payload = {
                "action": action_item.get("action", ""),
                "selector": action_item.get("selector", ""),
                "value": action_item.get("value", ""),
            }
            result = await _call_http("/browser", payload)
            results.append(f"{payload['action']}: {'ok' if result.get('ok') else 'fail'}")
        return " | ".join(results)

    return f"Unknown tool: {name}"


# ── Gemini session ─────────────────────────────────────────────────────────────

class GeminiSession:
    """Manages a chat session with Gemini, handling tool calls."""

    def __init__(self, api_key: str, model: str = GEMINI_MODEL):
        if genai is None:
            raise ImportError("google-generativeai is not installed")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            tools=TOOLS
        )
        self.chat = self.model.start_chat(enable_automatic_function_calling=False)
        self.history = []

    async def send_message(self, text: str) -> str:
        """Send a text message to Gemini and handle any tool calls."""
        response = self.chat.send_message(text)
        return await self._handle_response(response)

    async def _handle_response(self, response) -> str:
        """Recursively handle Gemini responses, executing tool calls as needed."""
        if not response.candidates:
            return "(no response)"

        content = ""
        tool_results = []

        for part in response.candidates[0].content.parts:
            if part.text:
                content += part.text

            if hasattr(part, 'function_call') and part.function_call:
                fn = part.function_call
                fn_name = fn.name
                fn_args = {}
                for key, val in fn.args.items():
                    fn_args[key] = val

                # Execute the tool
                result_str = await execute_tool(fn_name, fn_args)
                tool_results.append((fn_name, fn_args, result_str))

                # Send result back to Gemini
                response = self.chat.send_message(
                    genai.types.Content(
                        parts=[
                            genai.types.Part(
                                function_response=genai.types.FunctionResponse(
                                    name=fn_name,
                                    response={"result": result_str}
                                )
                            )
                        ]
                    )
                )
                # Recursively handle next response (Gemini may respond verbally)
                next_content = await self._handle_response(response)
                if next_content:
                    content += "\n" + next_content

        return content.strip()


# ── Main entry point ───────────────────────────────────────────────────────────

def check_dependencies() -> bool:
    """Check if all required dependencies are available."""
    missing = []
    try:
        import google.generativeai as _g
    except ImportError:
        missing.append("google-generativeai")

    try:
        import pipecat as _p
    except ImportError:
        missing.append("pipecat")

    if missing:
        log.warning(f"Missing dependencies: {', '.join(missing)}")
        log.warning(f"Install with: pip install {' '.join(missing)}")
        return False
    return True


async def start_pipeline():
    """Start the Pipecat pipeline with Gemini integration."""
    log.info("Starting Pipecat + Gemini backend...")

    if not GEMINI_API_KEY or GEMINI_API_KEY == "your-token-here":
        log.error("No Gemini API key found. Set GEMINI_API_KEY in config.json")
        return

    # Initialize Gemini session
    session = GeminiSession(GEMINI_API_KEY)

    # For now, run a simple text-based interaction loop
    # Full Pipecat pipeline (STT → Gemini → TTS) to be added when audio devices available
    log.info("Gemini session ready. Tools registered: " +
             ", ".join(t["name"] for t in TOOLS))

    # Example: keep-alive loop
    try:
        while True:
            await asyncio.sleep(30)
            log.debug("Pipecat backend heartbeat")
    except asyncio.CancelledError:
        log.info("Pipecat backend shutting down")


def start():
    """Synchronous entry point - called from jarvis_launcher.py or standalone."""
    if not check_dependencies():
        log.error("Dependencies missing, cannot start Pipecat backend")
        return

    log.info("=" * 50)
    log.info("Pipecat + Gemini Backend v1.0")
    log.info(f"Model: {GEMINI_MODEL}")
    log.info(f"Tools: {len(TOOLS)} registered")
    log.info("=" * 50)

    asyncio.run(start_pipeline())


if __name__ == "__main__":
    start()
